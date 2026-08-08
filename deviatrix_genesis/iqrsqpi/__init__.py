"""IQRSQPI conductor — Intent → Question → Research → Solution → Quality → Proof → Integrate.

Each expedition runs the full 7-stage process with at least 3 grill cycles
(Q/R pairs). A stage advances only when:

    E_stage ≤ θ_stage   AND   E_open ≈ 0

The conductor is the *only* authority that drives stages. Individual
expeditions cannot self-advance.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from .. import schemas
from ..diamonds import DiamondHarness

__all__ = ["IQRSQPIConductor", "StageOutcome", "GrillCycle"]


# ────────────────────────────────────────────────────────────────────
# Stage and grill-cycle records
# ────────────────────────────────────────────────────────────────────


@dataclass
class StageOutcome:
    stage: schemas.IQRSQPIStage
    cycle: int
    passed: bool = False
    energy: float = 1.0
    theta: float = 0.2
    open_questions: int = 0
    notes: str = ""

    def can_advance(self) -> bool:
        # ``passed`` is the *output* of the gate, not an input.
        return self.energy <= self.theta and self.open_questions == 0


@dataclass
class GrillCycle:
    """One Question → Research pair inside a stage."""

    cycle_id: str
    question: str
    research: dict[str, Any] = field(default_factory=dict)
    resolved: bool = False


# ────────────────────────────────────────────────────────────────────
# Conductor
# ────────────────────────────────────────────────────────────────────


class IQRSQPIConductor:
    """Per-expedition IQRSQPI state machine.

    Drives 7 stages with at least 3 grill cycles. The ``advance`` gate
    enforces the doctrine's E_stage ≤ θ_stage rule.
    """

    STAGES: list[schemas.IQRSQPIStage] = [
        schemas.IQRSQPIStage.INTENT,
        schemas.IQRSQPIStage.QUESTION,
        schemas.IQRSQPIStage.RESEARCH,
        schemas.IQRSQPIStage.SOLUTION,
        schemas.IQRSQPIStage.QUALITY,
        schemas.IQRSQPIStage.PROOF,
        schemas.IQRSQPIStage.INTEGRATE,
    ]

    def __init__(
        self,
        harness: DiamondHarness,
        expedition: schemas.ExpeditionKind,
        *,
        theta_stage: float = 0.2,
        min_grill_cycles: int = 3,
    ) -> None:
        self.harness = harness
        self.expedition = expedition
        self.theta = theta_stage
        self.min_grill = min_grill_cycles
        self.run_id = f"iqrsqpi-{uuid.uuid4().hex[:8]}"
        self.stages: list[StageOutcome] = []
        self.grill: list[GrillCycle] = []
        self.completed = False
        self.halted_reason: str = ""

    # ─── Stage progression ────────────────────────────────────────────────

    def begin_stage(
        self,
        stage: schemas.IQRSQPIStage,
        *,
        energy: float = 0.5,
        notes: str = "",
    ) -> StageOutcome:
        cycle = sum(1 for s in self.stages if s.stage == stage) + 1
        outcome = StageOutcome(
            stage=stage,
            cycle=cycle,
            energy=energy,
            theta=self.theta,
            open_questions=0,
            notes=notes,
        )
        self.stages.append(outcome)
        self.harness.trace(
            {
                "kind": "iqrsqpi_begin_stage",
                "stage": stage.value,
                "cycle": cycle,
                "energy": energy,
            }
        )
        return outcome

    def complete_stage(
        self,
        outcome: StageOutcome,
        *,
        energy: float | None = None,
        open_questions: int | None = None,
    ) -> bool:
        """Mark a stage complete. Returns ``True`` if the gate is cleared."""
        if energy is not None:
            outcome.energy = energy
        if open_questions is not None:
            outcome.open_questions = open_questions
        passed = outcome.can_advance()
        outcome.passed = passed
        self.harness.trace(
            {
                "kind": "iqrsqpi_complete_stage",
                "stage": outcome.stage.value,
                "passed": passed,
                "energy": outcome.energy,
                "open_questions": outcome.open_questions,
            }
        )
        return passed

    # ─── Grill cycles ──────────────────────────────────────────────────────

    def grill_cycle(self, question: str, research: dict[str, Any]) -> GrillCycle:
        """Record a Q/R pair. Returns the cycle.

        A grill cycle is *resolved* when the calling conductor signals
        that the question is closed (e.g. by re-running the stage with
        fewer open_questions).
        """
        cycle = GrillCycle(
            cycle_id=f"grill-{len(self.grill)+1:03d}",
            question=question,
            research=research,
            resolved=False,
        )
        self.grill.append(cycle)
        self.harness.trace(
            {
                "kind": "grill_cycle",
                "cycle_id": cycle.cycle_id,
                "question": question[:120],
            }
        )
        return cycle

    def resolve_cycle(self, cycle: GrillCycle, resolution: str) -> None:
        cycle.research["resolution"] = resolution
        cycle.resolved = True

    # ─── Final integration ────────────────────────────────────────────────

    def integrate(self) -> dict[str, Any]:
        """Close out the expedition after all 7 stages pass and grill ≥ min.

        Returns the conductor summary.
        """
        n_passed = sum(1 for s in self.stages if s.passed)
        n_required_stages = len(self.STAGES)
        n_required_grill = self.min_grill

        if n_passed < n_required_stages:
            self.halted_reason = (
                f"only {n_passed}/{n_required_stages} stages passed"
            )
            self.completed = False
        elif len(self.grill) < n_required_grill:
            self.halted_reason = (
                f"only {len(self.grill)}/{n_required_grill} grill cycles"
            )
            self.completed = False
        else:
            self.completed = True

        summary = {
            "run_id": self.run_id,
            "diamond": self.harness.diamond.value,
            "expedition": self.expedition.value,
            "n_stages_passed": n_passed,
            "n_stages_required": n_required_stages,
            "n_grill_cycles": len(self.grill),
            "n_grill_required": n_required_grill,
            "completed": self.completed,
            "halted_reason": self.halted_reason,
            "stage_pass_flags": [s.passed for s in self.stages],
        }
        self.harness.trace({"kind": "iqrsqpi_integrate", "summary": summary})
        return summary

    # ─── Convenience: run all 7 stages with default grill ──────────────────

    def run_quick(
        self,
        *,
        grill_questions: list[str] | None = None,
        research_factory: Callable[[int, str], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Drive all 7 stages with default energy decay.

        The conductor does not *answer* the questions; it tracks them.
        The caller is expected to run actual IQRSQPI work in parallel
        and only consult this conductor for stage-gate eligibility.
        """
        default_questions = grill_questions or [
            "What is the candidate's deviation target?",
            "What is the candidate's mechanism specificity?",
            "What is the candidate's falsifier?",
        ]
        factory = research_factory or (lambda i, q: {"cycle": i, "stub": True})

        # Run the required minimum grill cycles
        for i, q in enumerate(default_questions[: max(self.min_grill, 1)], start=1):
            cycle = self.grill_cycle(q, factory(i, q))
            self.resolve_cycle(cycle, f"default-resolution-{i}")

        # Run all 7 stages with decaying energy
        for stage in self.STAGES:
            outcome = self.begin_stage(stage, energy=0.5, notes="quick run")
            self.complete_stage(outcome, energy=0.05, open_questions=0)

        return self.integrate()
