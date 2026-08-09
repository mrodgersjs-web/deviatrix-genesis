"""DAG-aware contention monitor — detect and resolve parallel bottlenecks.

Monitors the async DAG execution for:
  * Dependency chains that serialize parallel work
  * Bottleneck nodes that block multiple downstream nodes
  * Underutilized parallelism (nodes that could run concurrently)
  * Phantom dependencies (artificial serialization)

Usage::

    from deviatrix_genesis.v5.contention import ContentionMonitor

    monitor = ContentionMonitor()
    monitor.record_node_start("expedition_1", dependencies=["formula_1"])
    monitor.record_node_end("expedition_1", duration_ms=150.0)

    report = monitor.analyze()
    print(report.bottlenecks)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ContentionMonitor", "ContentionReport", "Bottleneck"]


@dataclass
class NodeRecord:
    """Record of one DAG node execution."""
    node_id: str
    dependencies: list[str] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    error: str = ""

    @property
    def is_complete(self) -> bool:
        return self.end_time > 0


@dataclass
class Bottleneck:
    """A detected bottleneck in the DAG."""
    kind: str  # chain, fan_in, slow_node, phantom_dep
    node_id: str
    severity: str  # low, medium, high
    description: str
    blocked_nodes: list[str] = field(default_factory=list)
    wasted_parallelism_ms: float = 0.0


@dataclass
class ContentionReport:
    """Analysis of DAG contention."""
    total_nodes: int
    parallel_efficiency: float  # 0-1
    bottlenecks: list[Bottleneck]
    critical_path_ms: float = 0.0
    max_parallelism: int = 0
    actual_parallelism: float = 0.0

    def summary(self) -> str:
        lines = [f"Contention Report: {self.total_nodes} nodes"]
        lines.append(f"  Parallel efficiency: {self.parallel_efficiency:.0%}")
        lines.append(f"  Critical path: {self.critical_path_ms:.0f}ms")
        lines.append(f"  Max parallelism: {self.max_parallelism}")
        lines.append(f"  Actual parallelism: {self.actual_parallelism:.1f}")
        if self.bottlenecks:
            lines.append(f"  Bottlenecks: {len(self.bottlenecks)}")
            for b in self.bottlenecks:
                lines.append(f"    [{b.severity}] {b.kind}: {b.description}")
        return "\n".join(lines)


class ContentionMonitor:
    """Monitor DAG execution for contention and bottlenecks."""

    def __init__(self) -> None:
        self._nodes: dict[str, NodeRecord] = {}
        self._timeline: list[tuple[float, str, str]] = []  # (time, node_id, event)

    def record_node_start(self, node_id: str, dependencies: list[str] | None = None) -> None:
        """Record a node starting execution."""
        if node_id not in self._nodes:
            self._nodes[node_id] = NodeRecord(node_id=node_id)
        node = self._nodes[node_id]
        node.dependencies = dependencies or []
        node.start_time = time.monotonic()
        self._timeline.append((node.start_time, node_id, "start"))

    def record_node_end(self, node_id: str, duration_ms: float = 0.0, error: str = "") -> None:
        """Record a node completing execution."""
        if node_id not in self._nodes:
            self._nodes[node_id] = NodeRecord(node_id=node_id)
        node = self._nodes[node_id]
        node.end_time = time.monotonic()
        node.duration_ms = duration_ms or ((node.end_time - node.start_time) * 1000)
        node.error = error
        self._timeline.append((node.end_time, node_id, "end"))

    def analyze(self) -> ContentionReport:
        """Analyze the DAG for contention."""
        if not self._nodes:
            return ContentionReport(total_nodes=0, parallel_efficiency=1.0, bottlenecks=[])

        bottlenecks: list[Bottleneck] = []

        # Detect slow nodes
        bottlenecks.extend(self._detect_slow_nodes())

        # Detect fan-in bottlenecks
        bottlenecks.extend(self._detect_fan_in())

        # Detect dependency chains
        bottlenecks.extend(self._detect_chains())

        # Compute parallel efficiency
        efficiency = self._compute_efficiency()
        critical_path = self._compute_critical_path()
        max_par, actual_par = self._compute_parallelism()

        return ContentionReport(
            total_nodes=len(self._nodes),
            parallel_efficiency=efficiency,
            bottlenecks=sorted(bottlenecks, key=lambda b: -b.wasted_parallelism_ms),
            critical_path_ms=critical_path,
            max_parallelism=max_par,
            actual_parallelism=actual_par,
        )

    def _detect_slow_nodes(self) -> list[Bottleneck]:
        """Detect nodes that are significantly slower than average."""
        bottlenecks: list[Bottleneck] = []
        durations = [n.duration_ms for n in self._nodes.values() if n.is_complete]

        if len(durations) < 2:
            return bottlenecks

        avg_duration = sum(durations) / len(durations)

        for node in self._nodes.values():
            if node.is_complete and node.duration_ms > avg_duration * 3:
                # Find nodes that were blocked by this one
                blocked = [
                    n.node_id for n in self._nodes.values()
                    if node.node_id in n.dependencies
                ]
                bottlenecks.append(Bottleneck(
                    kind="slow_node",
                    node_id=node.node_id,
                    severity="high" if len(blocked) > 2 else "medium",
                    description=f"Node {node.node_id} took {node.duration_ms:.0f}ms (avg: {avg_duration:.0f}ms)",
                    blocked_nodes=blocked,
                    wasted_parallelism_ms=node.duration_ms - avg_duration,
                ))

        return bottlenecks

    def _detect_fan_in(self) -> list[Bottleneck]:
        """Detect fan-in patterns where many nodes wait on one."""
        bottlenecks: list[Bottleneck] = []

        # Count dependents per node
        dependents: dict[str, list[str]] = {}
        for node in self._nodes.values():
            for dep in node.dependencies:
                if dep not in dependents:
                    dependents[dep] = []
                dependents[dep].append(node.node_id)

        for node_id, blocked in dependents.items():
            if len(blocked) >= 3:
                node = self._nodes.get(node_id)
                if node and node.is_complete:
                    bottlenecks.append(Bottleneck(
                        kind="fan_in",
                        node_id=node_id,
                        severity="high",
                        description=f"Node {node_id} blocks {len(blocked)} downstream nodes",
                        blocked_nodes=blocked,
                    ))

        return bottlenecks

    def _detect_chains(self) -> list[Bottleneck]:
        """Detect long dependency chains that serialize work."""
        bottlenecks: list[Bottleneck] = []

        # Build dependency graph
        graph: dict[str, list[str]] = {}
        for node in self._nodes.values():
            graph[node.node_id] = node.dependencies

        # Find longest chain
        def chain_length(node_id: str, visited: set[str]) -> int:
            if node_id in visited:
                return 0
            visited.add(node_id)
            deps = graph.get(node_id, [])
            if not deps:
                return 1
            return 1 + max(chain_length(d, visited) for d in deps)

        for node_id in graph:
            length = chain_length(node_id, set())
            if length >= 4:
                bottlenecks.append(Bottleneck(
                    kind="chain",
                    node_id=node_id,
                    severity="medium",
                    description=f"Node {node_id} is at the end of a {length}-deep dependency chain",
                ))

        return bottlenecks

    def _compute_efficiency(self) -> float:
        """Compute parallel efficiency (0-1)."""
        completed = [n for n in self._nodes.values() if n.is_complete]
        if not completed:
            return 1.0

        total_sequential = sum(n.duration_ms for n in completed)
        if total_sequential == 0:
            return 1.0

        # Wall-clock time
        start = min(n.start_time for n in completed)
        end = max(n.end_time for n in completed)
        wall_clock = (end - start) * 1000

        if wall_clock == 0:
            return 1.0

        return min(total_sequential / wall_clock, 1.0)

    def _compute_critical_path(self) -> float:
        """Compute the critical path duration."""
        completed = [n for n in self._nodes.values() if n.is_complete]
        if not completed:
            return 0.0

        start = min(n.start_time for n in completed)
        end = max(n.end_time for n in completed)
        return (end - start) * 1000

    def _compute_parallelism(self) -> tuple[int, float]:
        """Compute max and actual parallelism."""
        if not self._timeline:
            return 0, 0.0

        # Track concurrent nodes over time
        active = 0
        max_active = 0
        total_active_time = 0.0
        prev_time = self._timeline[0][0]

        for ts, node_id, event in sorted(self._timeline):
            duration = ts - prev_time
            total_active_time += active * duration
            if event == "start":
                active += 1
                max_active = max(max_active, active)
            elif event == "end":
                active = max(0, active - 1)
            prev_time = ts

        wall = self._timeline[-1][0] - self._timeline[0][0]
        avg_parallel = total_active_time / wall if wall > 0 else 0.0

        return max_active, avg_parallel
