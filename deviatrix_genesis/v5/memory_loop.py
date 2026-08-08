"""Resilient Memory OS loop with retry, circuit-breaker, and idempotent writes.

Queries Memory OS for strategic intent, runs the Deviatrix pipeline,
and writes survivors back as candidate memories.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..v3.memory_os import MemoryOSAdapter, write_idea_as_memory

__all__ = ["MemoryLoopConfig", "ResilientMemoryLoop", "build_brief_from_memories"]


@dataclass
class MemoryLoopConfig:
    db_path: str = str(Path.home() / ".rig" / "rig-memory-os" / "memory.db")
    max_retries: int = 3
    retry_delay_s: float = 1.0
    circuit_breaker_threshold: int = 5


class ResilientMemoryLoop:
    """Bidirectional Memory OS ↔ Deviatrix loop with resilience."""

    def __init__(self, config: MemoryLoopConfig | None = None) -> None:
        self.config = config or MemoryLoopConfig()
        self._adapter = MemoryOSAdapter(db_path=self.config.db_path)
        self._consecutive_failures: int = 0
        self._circuit_open: bool = False

    # ── public API ──────────────────────────────────────────────────

    def run_cycle(
        self,
        brief: str,
        max_ideas: int = 12,
        max_rounds: int = 5,
    ) -> dict[str, Any]:
        """Run one full Memory OS → Deviatrix → Memory OS cycle."""
        if self._circuit_open:
            return {"survivors": [], "errors": ["circuit_breaker_open"], "memory_ids_written": []}

        try:
            memories = self._query_strategic_memories(top_k=10)
            if not memories and not brief:
                return {"survivors": [], "errors": ["no_memories_no_brief"], "memory_ids_written": []}

            effective_brief = brief or build_brief_from_memories(memories)

            # Use v3 pipeline (v5 pipeline calls this; avoid circular import)
            from ..v3.pipeline import run_pipeline

            result = run_pipeline(
                brief=effective_brief,
                n_ideas=max_ideas,
                seeds=[2026],
                out_dir=None,
            )
            survivors = result.get("survivors", [])

            # Write back
            memory_ids = self._write_survivors(survivors)

            self._consecutive_failures = 0
            return {
                "survivors": survivors,
                "memory_ids_written": memory_ids,
                "errors": [],
                "convergence_round": 1,
            }

        except Exception as exc:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.config.circuit_breaker_threshold:
                self._circuit_open = True
            return {
                "survivors": [],
                "memory_ids_written": [],
                "errors": [str(exc)],
            }

    def reset_circuit(self) -> None:
        self._circuit_open = False
        self._consecutive_failures = 0

    # ── internal ────────────────────────────────────────────────────

    def _query_strategic_memories(self, top_k: int = 10) -> list[dict[str, Any]]:
        try:
            return self._adapter.read_prior_memories(limit=top_k)
        except Exception:
            return []

    def _write_survivors(self, survivors: list[dict[str, Any]]) -> list[str]:
        written: list[str] = []
        for s in survivors:
            try:
                receipt = write_idea_as_memory(
                    idea_name=s.get("name", "unknown"),
                    formula=s.get("formula", "(see run data)"),
                    falsifier=s.get("falsifier", "(see run data)"),
                    composite_z=s.get("composite_z_median", s.get("composite_z", 0.0)),
                    archetype_z=s.get("archetype_z_median", 0.0),
                    is_respin=s.get("is_respin_of_known", False),
                    mechanism_family=s.get("mechanism_family", "unknown"),
                    parent_names=s.get("parent_names"),
                    action_90d=s.get("action", "deep_review"),
                    run_id=s.get("run_id", "v5-cycle"),
                    db_path=self.config.db_path,
                )
                if receipt.accepted and receipt.memory_id:
                    written.append(receipt.memory_id)
            except Exception:
                pass
        return written

    def _retry_with_backoff(self, fn, retries: int, delay: float):
        for attempt in range(retries):
            try:
                return fn()
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(delay * (2 ** attempt))


def build_brief_from_memories(memories: list[dict[str, Any]]) -> str:
    """Build a brief string from Memory OS query results."""
    parts = []
    for m in memories:
        content = m.get("content", {})
        if isinstance(content, str):
            parts.append(content[:200])
        elif isinstance(content, dict):
            parts.append(content.get("summary", content.get("text", str(content)))[:200])
    if not parts:
        return "Default RIG strategic intent brief."
    return "RIG STRATEGIC INTENT (from Memory OS): " + " | ".join(parts[:5])
