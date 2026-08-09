"""Proof streaming — emit partial verification results as they complete.

Instead of waiting for all 3 passes (A, B, C) to complete, stream
each pass result immediately. Downstream consumers can act on partial
verification — e.g., start scoring as soon as Pass A completes.

Usage::

    from deviatrix_genesis.v5.proof_stream import ProofStream

    stream = ProofStream()

    # Emit as each pass completes
    stream.emit_pass("A", formula="x**2", status="PASS", z=None)
    stream.emit_pass("B", formula="x**2", status="PASS", z=5.2)
    stream.emit_pass("C", formula="x**2", status="PASS", z=5.1)

    # Get partial results
    partial = stream.get_partial("x**2")
    print(partial.composite_status)  # "partial_pass"
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ProofStream", "PartialProof"]


@dataclass
class PassResult:
    """Result of one verification pass."""
    pass_name: str  # A, B, C
    formula: str
    status: str  # PASS, FAIL, ERROR
    z: float | None = None
    timestamp: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PartialProof:
    """Aggregated partial proof across completed passes."""
    formula: str
    passes: list[PassResult] = field(default_factory=list)
    composite_status: str = "incomplete"  # incomplete, partial_pass, partial_fail, complete_pass, complete_fail

    @property
    def all_passes(self) -> dict[str, PassResult]:
        return {p.pass_name: p for p in self.passes}

    @property
    def latest_z(self) -> float | None:
        for p in reversed(self.passes):
            if p.z is not None:
                return p.z
        return None

    @property
    def can_proceed(self) -> bool:
        """True if Pass A passed (minimum viable verification)."""
        pa = self.all_passes.get("A")
        return pa is not None and pa.status == "PASS"


class ProofStream:
    """Stream partial verification results."""

    def __init__(self) -> None:
        self._proofs: dict[str, PartialProof] = {}
        self._events: list[dict[str, Any]] = []

    def emit_pass(
        self,
        pass_name: str,
        formula: str,
        status: str,
        z: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> PartialProof:
        """Emit a pass result and return the updated partial proof."""
        if formula not in self._proofs:
            self._proofs[formula] = PartialProof(formula=formula)

        proof = self._proofs[formula]
        pass_result = PassResult(
            pass_name=pass_name,
            formula=formula,
            status=status,
            z=z,
            timestamp=time.monotonic(),
            details=details or {},
        )

        # Replace if this pass was already emitted
        proof.passes = [p for p in proof.passes if p.pass_name != pass_name]
        proof.passes.append(pass_result)
        proof.passes.sort(key=lambda p: p.pass_name)

        # Update composite status
        proof.composite_status = self._compute_status(proof)

        # Log event
        self._events.append({
            "type": "pass_emitted",
            "formula": formula,
            "pass": pass_name,
            "status": status,
            "z": z,
            "timestamp": pass_result.timestamp,
        })

        return proof

    def get_partial(self, formula: str) -> PartialProof | None:
        """Get the current partial proof for a formula."""
        return self._proofs.get(formula)

    def get_all(self) -> dict[str, PartialProof]:
        """Get all partial proofs."""
        return dict(self._proofs)

    def get_actionable(self) -> list[PartialProof]:
        """Get proofs that have passed Pass A (can proceed to scoring)."""
        return [p for p in self._proofs.values() if p.can_proceed]

    def get_completed(self) -> list[PartialProof]:
        """Get proofs with all 3 passes completed."""
        return [
            p for p in self._proofs.values()
            if len(p.passes) >= 3
        ]

    def summary(self) -> dict[str, Any]:
        """Return a summary of the proof stream."""
        all_proofs = list(self._proofs.values())
        return {
            "total_formulas": len(all_proofs),
            "actionable": len(self.get_actionable()),
            "completed": len(self.get_completed()),
            "partial_pass": sum(1 for p in all_proofs if p.composite_status == "partial_pass"),
            "partial_fail": sum(1 for p in all_proofs if p.composite_status == "partial_fail"),
            "complete_pass": sum(1 for p in all_proofs if p.composite_status == "complete_pass"),
            "complete_fail": sum(1 for p in all_proofs if p.composite_status == "complete_fail"),
            "events": len(self._events),
        }

    def _compute_status(self, proof: PartialProof) -> str:
        statuses = [p.status for p in proof.passes]
        if len(statuses) < 3:
            if all(s == "PASS" for s in statuses):
                return "partial_pass"
            elif any(s == "FAIL" for s in statuses):
                return "partial_fail"
            return "incomplete"
        else:
            if all(s == "PASS" for s in statuses):
                return "complete_pass"
            elif any(s == "FAIL" for s in statuses):
                return "complete_fail"
            return "incomplete"
