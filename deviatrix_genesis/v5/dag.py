"""Async DAG executor — true asyncio concurrency with dependency-aware scheduling.

Each expedition is a DAG node with explicit dependency edges.  Supports:
  * fan-out (parallel expeditions)
  * fan-in (ensemble aggregation)
  * conditional edges (skip nodes when deps don't meet criteria)
  * error isolation (one node failure doesn't kill the DAG)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

__all__ = ["DAGNode", "DAGResult", "DAGExecutor"]


# ────────────────────────────────────────────────────────────────────
# Node / result types
# ────────────────────────────────────────────────────────────────────


@dataclass
class DAGNode:
    """A single unit of work in the DAG."""

    id: str
    fn: Callable[..., Coroutine[Any, Any, Any]]
    dependencies: list[str] = field(default_factory=list)
    skip_if: Callable[[dict[str, Any]], bool] | None = None


@dataclass
class DAGResult:
    """Outcome of one node execution."""

    node_id: str
    value: Any = None
    error: str | None = None
    start_time: float = 0.0
    end_time: float = 0.0
    skipped: bool = False

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


# ────────────────────────────────────────────────────────────────────
# Executor
# ────────────────────────────────────────────────────────────────────


class DAGExecutor:
    """Execute a directed acyclic graph of :class:`DAGNode` objects.

    Usage::

        ex = DAGExecutor()
        ex.add_node(DAGNode("a", coro_a))
        ex.add_node(DAGNode("b", coro_b, dependencies=["a"]))
        results = await ex.execute()
    """

    def __init__(self) -> None:
        self._nodes: dict[str, DAGNode] = {}

    # ── construction ────────────────────────────────────────────────

    def add_node(self, node: DAGNode) -> None:
        self._nodes[node.id] = node

    def add_edge(self, from_id: str, to_id: str) -> None:
        if to_id not in self._nodes:
            raise KeyError(f"node {to_id!r} not registered")
        if from_id not in self._nodes[to_id].dependencies:
            self._nodes[to_id].dependencies.append(from_id)

    # ── execution ───────────────────────────────────────────────────

    async def execute(self) -> dict[str, DAGResult]:
        """Run the full DAG respecting dependency order.

        Returns a dict mapping node id → :class:`DAGResult`.
        """
        results: dict[str, DAGResult] = {}
        completed: set[str] = set()
        pending = set(self._nodes)

        while pending:
            # Collect nodes whose deps are all satisfied.
            ready: list[str] = []
            for nid in list(pending):
                node = self._nodes[nid]
                if all(d in completed for d in node.dependencies):
                    ready.append(nid)

            if not ready:
                # Deadlock or cycle — record as error for every remaining node.
                for nid in pending:
                    results[nid] = DAGResult(
                        node_id=nid, error="unsatisfied dependencies (cycle?)"
                    )
                    completed.add(nid)
                break

            # Fan-out all ready nodes concurrently.
            tasks: list[asyncio.Task[DAGResult]] = []
            for nid in ready:
                tasks.append(asyncio.create_task(self._run_node(nid, results)))

            done_tasks = await asyncio.gather(*tasks, return_exceptions=True)

            for nid, outcome in zip(ready, done_tasks):
                if isinstance(outcome, BaseException):
                    res = DAGResult(node_id=nid, error=str(outcome))
                else:
                    res = outcome
                results[nid] = res
                completed.add(nid)
                pending.discard(nid)

        return results

    # ── internal ────────────────────────────────────────────────────

    async def _run_node(self, nid: str, results: dict[str, DAGResult]) -> DAGResult:
        node = self._nodes[nid]

        # Conditional skip
        if node.skip_if is not None:
            dep_values = {d: results[d].value for d in node.dependencies if d in results}
            if node.skip_if(dep_values):
                return DAGResult(node_id=nid, skipped=True)

        # Resolve dependency values
        dep_values = {d: results[d].value for d in node.dependencies if d in results}

        start = time.monotonic()
        try:
            value = await node.fn(**dep_values)
            return DAGResult(node_id=nid, value=value, start_time=start, end_time=time.monotonic())
        except Exception as exc:
            return DAGResult(
                node_id=nid, error=f"{type(exc).__name__}: {exc}",
                start_time=start, end_time=time.monotonic(),
            )
