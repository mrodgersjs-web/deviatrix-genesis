"""Expedition base class — shared structure across D1/D2/D3.

Each expedition is a *self-contained* deviation trip:

  - **positive_tail**: search for constructive extremes
  - **negative_tail**: search for destructive inversions
  - **repaired_tail**: collide pos+neg into a coherent survivor

The expedition holds:
  - the harness (mutated in place — trace is appended)
  - its kind (positive/negative/repaired)
  - a counterexample / repair record (per expedition)
  - a list of produced proof packets

Subclasses override :meth:`objective` and :meth:`falsifier` to encode
the diamond-specific math. The shared ``run`` loop drives the harness
through Pass A → Pass B → Pass C and seals a proof packet.
"""

from __future__ import annotations

import abc
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .. import schemas
from ..mathexec.executor import (
    compute_deviation,
    pass_a_symbolic,
    pass_b_numerical,
    pass_c_adversarial,
)
from . import DiamondHarness

__all__ = ["Expedition", "ExpeditionOutcome"]


@dataclass
class ExpeditionOutcome:
    """The terminal state of an expedition run."""

    expedition: schemas.ExpeditionKind
    diamond: schemas.DiamondKind
    packets: list[schemas.MathProofPacket] = field(default_factory=list)
    pass_a_status: str = ""
    pass_b_status: str = ""
    pass_c_status: str = ""
    certified_z: float = 0.0
    band: str = ""
    notes: str = ""
    fail_route: dict[str, Any] | None = None
    n_grill_cycles: int = 0


class Expedition(abc.ABC):
    """Base class for D1/D2/D3 expeditions."""

    def __init__(
        self,
        harness: DiamondHarness,
        kind: schemas.ExpeditionKind,
    ) -> None:
        self.harness = harness
        self.kind = kind
        self.outcome = ExpeditionOutcome(
            expedition=kind,
            diamond=harness.diamond,
        )

    # subclasses override
    @abc.abstractmethod
    def objective(self) -> str:
        """Human-readable objective for the trace."""

    @abc.abstractmethod
    def falsifier(self) -> str:
        """What would refute the candidate this expedition emits."""

    @abc.abstractmethod
    def candidate_value(self) -> float:
        """The empirical scalar value the deviation is computed against."""

    @abc.abstractmethod
    def structural_distance(self) -> float:
        ...

    @abc.abstractmethod
    def behavioral_distance(self) -> float:
        ...

    # shared runner
    def run(
        self,
        claim: schemas.MathClaim,
        *,
        iqrsqpi_cycle: int = 0,
        alternate_corpus: list[float] | None = None,
        n_bootstrap: int = 200,
    ) -> ExpeditionOutcome:
        """Drive Pass A → B → C, then seal a packet."""
        run_id = f"{self.harness.diamond.value}-{self.kind.value}-{uuid.uuid4().hex[:8]}"
        packet = schemas.MathProofPacket(
            run_id=run_id,
            diamond=self.harness.diamond,
            expedition=self.kind,
            iqrsqpi_cycle=iqrsqpi_cycle,
            candidate_hash=claim.candidate_hash,
        )

        # Pass A
        packet.symbolic = pass_a_symbolic(claim)
        self.outcome.pass_a_status = packet.symbolic.status
        self.harness.trace(
            {
                "kind": "pass_a",
                "status": packet.symbolic.status,
                "expression": claim.expression,
            }
        )
        if packet.symbolic.status != "PASS":
            packet.routing.gate_status = schemas.GateStatus.MUTATE
            packet.routing.failure_class = schemas.FailureClass.SYMBOLIC_ERROR
            from . import apply_fail_route

            self.outcome.fail_route = apply_fail_route(
                self.harness,
                schemas.FailureClass.SYMBOLIC_ERROR,
                packet,
            )
            packet.seal()
            self.outcome.packets.append(packet)
            return self.outcome

        # Pass B
        packet.empirical = pass_b_numerical(
            claim,
            self.candidate_value(),
            alternate_corpus=alternate_corpus,
            n_bootstrap=n_bootstrap,
        )
        self.outcome.certified_z = packet.empirical.certified_z
        self.outcome.pass_b_status = "PASS" if abs(packet.empirical.certified_z) > 0 else "FAIL"
        self.harness.trace(
            {
                "kind": "pass_b",
                "certified_z": packet.empirical.certified_z,
                "mad_z": packet.empirical.robust_madz,
                "qn_z": packet.empirical.qn_z,
            }
        )

        # Pass C
        packet.adversarial = pass_c_adversarial(
            claim,
            packet.empirical,
            structural_distance=self.structural_distance(),
            behavioral_distance=self.behavioral_distance(),
        )
        self.outcome.pass_c_status = (
            "PASS"
            if abs(packet.empirical.certified_z) >= 3
            else "WEAK"
        )
        self.harness.trace(
            {
                "kind": "pass_c",
                "perturbations": len(packet.adversarial.perturbations_run),
                "falsification": packet.adversarial.falsification_result,
            }
        )

        # Deviation
        packet.deviation = compute_deviation(
            packet.empirical,
            structural=self.structural_distance(),
            behavioral=self.behavioral_distance(),
            direction=(
                schemas.Direction.POSITIVE
                if packet.empirical.certified_z >= 0
                else schemas.Direction.NEGATIVE
            ),
            target_band="+20σ" if self.kind == schemas.ExpeditionKind.POSITIVE_TAIL else "-20σ",
        )

        # Initial routing by sigma band
        from .routing import band_for

        packet.routing.band = band_for(packet.empirical.certified_z)
        packet.routing.gate_status = schemas.GateStatus.PASS
        packet.routing.notes = self.falsifier()

        packet.seal()
        self.outcome.packets.append(packet)
        self.outcome.band = packet.routing.band
        self.outcome.notes = self.falsifier()
        self.harness.n_packets += 1
        return self.outcome

    # helper for subclasses that want to record their own trace entries
    def note(self, key: str, value: Any) -> None:
        self.harness.trace({"kind": key, "value": value, "expedition": self.kind.value})
