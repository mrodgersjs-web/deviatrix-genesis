"""Memory-driven idea loop.

v3's pipeline runs on a fixed brief. v4's loop *queries Memory OS
for strategic intent* and uses the query result as the brief.

The loop:

  1. Query Memory OS for the latest *semantic* memories tagged
     with `intent:gtm` (or all top semantic memories).
  2. Concatenate the top-k memory contents as a brief.
  3. Run the iterative proposer on that brief.
  4. Write the survivors back as procedural memories.

This closes the loop: Memory OS → brief → Deviatrix → Memory OS.

The Memory OS schema's `source_type` distinguishes
`model_synthesized` (Deviatrix writes) from `human_approved`
(Mike's review). The loop is *only* the model_synthesized side;
Mike's promotion to `active` is the human_approved side.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..v3.memory_os import (
    DEFAULT_DB_PATH,
    DEFAULT_TENANT,
    MemoryOSAdapter,
    write_idea_as_memory,
)
from .iterative import run_iterative

__all__ = ["MemoryDrivenLoop", "build_brief_from_memory", "run_memory_loop"]


@dataclass
class MemoryDrivenLoop:
    """High-level orchestrator: Memory OS ↔ Deviatrix v4."""

    db_path: str = DEFAULT_DB_PATH
    tenant_id: str = DEFAULT_TENANT
    n_top_memories: int = 5
    n_per_round: int = 9
    n_rounds: int = 3
    population_size: int = 1000

    def __post_init__(self) -> None:
        self.adapter = MemoryOSAdapter(
            db_path=self.db_path, tenant_id=self.tenant_id
        )

    def build_brief(self) -> str:
        """Query Memory OS for the top semantic memories and build a brief."""
        return build_brief_from_memory(
            self.db_path, self.tenant_id, top_k=self.n_top_memories
        )

    def run(self, write_back: bool = True) -> dict[str, Any]:
        """Run the memory-driven loop."""
        brief = self.build_brief()
        from ..v3.corpus_loader import (
            build_known_archetype_population,
            build_reference_population,
            load_corpus,
        )

        corpus = load_corpus()
        population = build_reference_population(corpus, n=self.population_size, seed=2026)

        result = run_iterative(
            brief=brief,
            population=population,
            n_per_round=self.n_per_round,
            n_rounds=self.n_rounds,
        )

        # Optionally write survivors back to Memory OS
        write_receipts: list[dict[str, Any]] = []
        if write_back:
            for surv in result.survivors:
                receipt = write_idea_as_memory(
                    idea_name=surv["name"],
                    formula=str(surv.get("outcomes", {}).get("opportunity", {})),
                    falsifier="(see Deviatrix run)",
                    composite_z=surv["composite_z"],
                    archetype_z=surv["outcomes"].get("opportunity", {}).get("repaired_z", 5.0),
                    is_respin=False,
                    mechanism_family="(see Deviatrix run)",
                    parent_names=None,
                    action_90d="(see Deviatrix run)",
                    run_id=f"memory-loop-{self.tenant_id}",
                )
                write_receipts.append({
                    "name": surv["name"],
                    "accepted": receipt.accepted,
                    "memory_id": receipt.memory_id,
                })

        return {
            "brief": brief,
            "rounds": result.rounds,
            "survivors": result.survivors,
            "converged": result.converged,
            "n_rounds": result.n_rounds_run,
            "memory_os_writes": write_receipts,
        }


def build_brief_from_memory(
    db_path: str = DEFAULT_DB_PATH,
    tenant_id: str = DEFAULT_TENANT,
    top_k: int = 5,
) -> str:
    """Build a brief from the top-k active semantic memories.

    Strategy:
      * Read all active semantic memories.
      * Rank by `confidence * (1 - decay)` (newer + higher-confidence first).
      * Concatenate the top-k `content` blobs as the brief.
    """
    db = Path(db_path).expanduser()
    if not db.exists():
        return (
            "RIG GTM: operator-first, doctrine-published, financially primitive, "
            "structurally novel, independently verifiable, portable across products"
        )

    try:
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT memory_id, content_json, confidence FROM memories "
            "WHERE tenant_scope=? AND memory_type='semantic' "
            "AND initial_status='active' "
            "ORDER BY confidence DESC LIMIT ?",
            (tenant_id, top_k),
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        return (
            "RIG GTM: operator-first, doctrine-published, financially primitive"
        )

    if not rows:
        return (
            "RIG GTM: operator-first, doctrine-published, financially primitive"
        )

    parts: list[str] = []
    for mid, content_json, confidence in rows:
        try:
            import json as _json

            content = _json.loads(content_json) if isinstance(content_json, str) else content_json
            if isinstance(content, dict):
                # Pull the most "factual" sub-content
                facts = content.get("fact") or content.get("implication") or content.get("name")
                if facts:
                    parts.append(str(facts))
                elif "name" in content:
                    parts.append(str(content["name"]))
        except Exception:
            continue

    if not parts:
        return "RIG GTM: operator-first, doctrine-published"

    return "RIG STRATEGIC INTENT (from Memory OS): " + " | ".join(parts)


def run_memory_loop(
    db_path: str = DEFAULT_DB_PATH,
    tenant_id: str = DEFAULT_TENANT,
    write_back: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience: build a MemoryDrivenLoop and run it once."""
    loop = MemoryDrivenLoop(
        db_path=db_path, tenant_id=tenant_id, **kwargs
    )
    return loop.run(write_back=write_back)
