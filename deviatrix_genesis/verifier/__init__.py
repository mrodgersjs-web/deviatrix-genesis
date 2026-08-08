"""Independent verifier — the brakes and finish-line authority.

The verifier reads proof packets (NOT LLM prose) and alone decides
PASS / FAIL / MUTATE / ESCALATE. The doctrine's *never_accepts* list:

  * narrated_sigma — claims like "this is 31σ" without a packet
  * self_reported_novelty — the candidate asserting its own novelty
  * unexecuted_formulas — formulas that never ran through SymPy MCP
  * hidden_retries — re-runs the generator didn't surface

A candidate cannot pass if any of the following hold:

  1. Symbolic pass != PASS
  2. Empirical certified_z is NaN or ±inf
  3. Adversarial falsification == "contradiction"
  4. Reference population hash is empty
  5. certified_z sits at or beyond 30σ (wall, not floor)
  6. composite_deviation is below the structural_floor for the diamond

The verifier signs every packet. The seal hash is the audit anchor.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

from .. import schemas
from ..diamonds.routing import band_for, is_wall

__all__ = ["IndependentVerifier", "VerifierReport"]


@dataclass
class VerifierReport:
    packet_run_id: str
    decision: schemas.GateStatus
    band: str
    wall_breach: bool
    reason: str
    signature: str
    timestamp: str
    failure_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_run_id": self.packet_run_id,
            "decision": self.decision.value,
            "band": self.band,
            "wall_breach": self.wall_breach,
            "reason": self.reason,
            "signature": self.signature,
            "timestamp": self.timestamp,
            "failure_flags": list(self.failure_flags),
        }


class IndependentVerifier:
    """The independent verifier.

    Single instance per conductor run; holds the verifier_id so the
    signature is attributable. Termination authority belongs to this
    object — nothing else may declare a candidate done.
    """

    def __init__(self, verifier_id: str = "verifier-001") -> None:
        self.verifier_id = verifier_id
        self.reports: list[VerifierReport] = []

    # ── Public API ─────────────────────────────────────────────────────

    def verify(self, packet: schemas.MathProofPacket) -> VerifierReport:
        """Verify a packet; return a :class:`VerifierReport`.

        The packet is mutated in place (its ``verifier`` field is
        populated) and then re-sealed so the audit hash is computed
        *after* the verifier has spoken.
        """
        flags: list[str] = []
        decision = schemas.GateStatus.PASS
        reason = "all checks passed"

        # 1. Symbolic pass
        if packet.symbolic.status != "PASS":
            flags.append("symbolic_not_pass")
            decision = schemas.GateStatus.FAIL
            reason = f"symbolic status = {packet.symbolic.status}"

        # 2. certified_z is finite
        if not math.isfinite(packet.empirical.certified_z):
            flags.append("certified_z_not_finite")
            decision = schemas.GateStatus.FAIL
            reason = "certified_z is NaN or ±inf"

        # 3. Adversarial falsification
        if packet.adversarial.falsification_result == "contradiction":
            flags.append("adversarial_contradiction")
            decision = schemas.GateStatus.FAIL
            reason = "adversarial pass found contradiction"

        # 4. Population hash present
        if not packet.empirical.reference_population_hash:
            flags.append("missing_population_hash")
            decision = schemas.GateStatus.FAIL
            reason = "reference population hash is empty"

        # 5. Wall breach (30σ) — no auto-pass
        wall = is_wall(packet.empirical.certified_z)
        if wall:
            flags.append("wall_breach")
            decision = schemas.GateStatus.ESCALATE
            reason = (
                f"certified_z = {packet.empirical.certified_z:.2f} hit the ±30σ wall"
            )

        # 6. Composite deviation floor (diamond-specific)
        floor = self._structural_floor(packet.diamond)
        if packet.deviation.structural_distance < floor:
            flags.append("below_structural_floor")
            if decision == schemas.GateStatus.PASS:
                decision = schemas.GateStatus.MUTATE
                reason = (
                    f"structural_distance {packet.deviation.structural_distance} "
                    f"< floor {floor}"
                )

        # Sign
        body = json.dumps(
            {
                "packet": packet.to_dict(),
                "flags": flags,
                "decision": decision.value,
                "reason": reason,
                "verifier_id": self.verifier_id,
            },
            sort_keys=True,
        )
        signature = hashlib.sha256(body.encode()).hexdigest()[:32]

        ts = _dt.datetime.now(_dt.timezone.utc).isoformat()

        report = VerifierReport(
            packet_run_id=packet.run_id,
            decision=decision,
            band=band_for(packet.empirical.certified_z),
            wall_breach=wall,
            reason=reason,
            signature=signature,
            timestamp=ts,
            failure_flags=flags,
        )

        # Populate the packet's verifier field
        packet.verifier.verifier_id = self.verifier_id
        packet.verifier.decision = decision
        packet.verifier.reason = reason
        packet.verifier.signature = signature
        packet.verifier.timestamp = ts

        # Re-seal so the audit hash reflects the verifier's decision
        packet.seal()

        self.reports.append(report)
        return report

    # ── Internal ───────────────────────────────────────────────────────

    @staticmethod
    def _structural_floor(diamond: schemas.DiamondKind) -> float:
        return {
            schemas.DiamondKind.OPPORTUNITY: 0.0,  # D1 has no explicit floor
            schemas.DiamondKind.INVENTION: 5.0,    # D2 doctrine: z_structural ≥ 5
            schemas.DiamondKind.PROOF: 0.0,
        }.get(diamond, 0.0)

    def summary(self) -> dict[str, Any]:
        return {
            "verifier_id": self.verifier_id,
            "n_reports": len(self.reports),
            "n_pass": sum(1 for r in self.reports if r.decision == schemas.GateStatus.PASS),
            "n_fail": sum(1 for r in self.reports if r.decision == schemas.GateStatus.FAIL),
            "n_mutate": sum(1 for r in self.reports if r.decision == schemas.GateStatus.MUTATE),
            "n_escalate": sum(
                1 for r in self.reports if r.decision == schemas.GateStatus.ESCALATE
            ),
            "wall_breaches": [r.packet_run_id for r in self.reports if r.wall_breach],
        }
