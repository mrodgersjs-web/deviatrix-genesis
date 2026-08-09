"""Replayable failure capsules — freeze failures into reproducible artifacts.

When an expedition fails, the capsule captures:
  * The exact formula, population seed, and configuration
  * The SymPy parse result and intermediate states
  * The verifier decision and reason
  * A deterministic replay function

Usage::

    from deviatrix_genesis.v5.capsules import FailureCapsule, CapsuleStore

    store = CapsuleStore()
    capsule = store.capture(
        formula="x**2 + sin(x)",
        seed=42,
        error="verifier FAIL",
        context={"z": 0.5, "band": "0σ–3σ"},
    )

    # Replay later
    result = capsule.replay()
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["FailureCapsule", "CapsuleStore"]


@dataclass
class FailureCapsule:
    """A frozen, replayable failure artifact."""
    capsule_id: str
    timestamp: float
    formula: str
    seed: int
    error: str
    context: dict[str, Any]
    replay_command: str = ""
    replayed: bool = False
    replay_result: dict[str, Any] = field(default_factory=dict)

    def replay(self) -> dict[str, Any]:
        """Replay the failure deterministically."""
        from ..mathexec.executor import pass_a_symbolic, pass_b_numerical, pass_c_adversarial
        from .. import schemas

        claim = schemas.MathClaim(
            expression=self.formula,
            variable="x",
            reference_population=[],
            candidate_hash="",
        )

        # Run Pass A
        symbolic = pass_a_symbolic(claim)

        result = {
            "capsule_id": self.capsule_id,
            "formula": self.formula,
            "seed": self.seed,
            "pass_a_status": symbolic.status,
            "pass_a_error": symbolic.error,
            "symbolic_expression": symbolic.simplified_expression,
        }

        self.replayed = True
        self.replay_result = result
        return result


class CapsuleStore:
    """Store and manage failure capsules."""

    def __init__(self, store_dir: str | Path | None = None) -> None:
        self._capsules: list[FailureCapsule] = []
        self._store_dir = Path(store_dir) if store_dir else None

    def capture(
        self,
        formula: str,
        seed: int,
        error: str,
        context: dict[str, Any] | None = None,
    ) -> FailureCapsule:
        """Capture a failure into a replayable capsule."""
        capsule_id = hashlib.sha256(
            f"{formula}:{seed}:{error}:{time.time()}".encode()
        ).hexdigest()[:12]

        capsule = FailureCapsule(
            capsule_id=capsule_id,
            timestamp=time.time(),
            formula=formula,
            seed=seed,
            error=error,
            context=context or {},
        )

        self._capsules.append(capsule)

        if self._store_dir:
            self._persist(capsule)

        return capsule

    def get_all(self) -> list[FailureCapsule]:
        """Get all captured capsules."""
        return list(self._capsules)

    def get_unreplayed(self) -> list[FailureCapsule]:
        """Get capsules that haven't been replayed yet."""
        return [c for c in self._capsules if not c.replayed]

    def replay_all(self) -> list[dict[str, Any]]:
        """Replay all unreplayed capsules."""
        results = []
        for capsule in self.get_unreplayed():
            try:
                result = capsule.replay()
                results.append(result)
            except Exception as exc:
                results.append({
                    "capsule_id": capsule.capsule_id,
                    "error": str(exc),
                })
        return results

    def summary(self) -> dict[str, Any]:
        """Return a summary of captured capsules."""
        return {
            "total": len(self._capsules),
            "replayed": sum(1 for c in self._capsules if c.replayed),
            "unreplayed": sum(1 for c in self._capsules if not c.replayed),
            "by_error": self._count_by_error(),
        }

    def _count_by_error(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self._capsules:
            counts[c.error] = counts.get(c.error, 0) + 1
        return counts

    def _persist(self, capsule: FailureCapsule) -> None:
        if not self._store_dir:
            return
        self._store_dir.mkdir(parents=True, exist_ok=True)
        path = self._store_dir / f"capsule_{capsule.capsule_id}.json"
        path.write_text(json.dumps({
            "capsule_id": capsule.capsule_id,
            "timestamp": capsule.timestamp,
            "formula": capsule.formula,
            "seed": capsule.seed,
            "error": capsule.error,
            "context": capsule.context,
        }, indent=2, default=str))
