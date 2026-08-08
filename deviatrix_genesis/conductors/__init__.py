"""Master conductor — 3 diamonds × 3 expeditions × 7 IQRSQPI stages.

The conductor wires everything together:

  1. For each diamond (Opportunity, Invention, Proof):
       a. Instantiate a DiamondHarness
       b. Run positive_tail, negative_tail, repaired_tail expeditions
       c. Each expedition drives the 7-stage IQRSQPI conductor
       d. Each packet is sealed by the IndependentVerifier

The total execution budget for one full run is:

  3 diamonds × 3 expeditions × 7 IQRSQPI stages
   = 63 outer stages

  3 diamonds × 3 expeditions × ≥3 grill cycles
   = ≥27 grill cycles

This matches the doctrine's run totals.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .. import schemas
from ..diamonds import DiamondHarness
from ..diamonds.d1_opportunity import (
    OpportunityNegativeTail,
    OpportunityPositiveTail,
    OpportunityRepairedTail,
)
from ..diamonds.d2_invention import (
    InventionNegativeTail,
    InventionPositiveTail,
    InventionRepairedTail,
)
from ..diamonds.d3_proof import (
    ProofNegativeTail,
    ProofPositiveTail,
    ProofRepairedTail,
)
from ..diamonds.expeditions import ExpeditionOutcome
from ..diamonds.routing import action_for, band_for, is_wall
from ..iqrsqpi import IQRSQPIConductor
from ..verifier import IndependentVerifier, VerifierReport

__all__ = ["DeviatrixConductor", "RunReport"]


# ────────────────────────────────────────────────────────────────────
# Run totals (doctrine)
# ────────────────────────────────────────────────────────────────────

EXPECTED_RUN_TOTALS = {
    "diamonds": 3,
    "expeditions_per_diamond": 3,
    "total_expeditions": 9,
    "iqrsqpi_stages": 7,
    "outer_stages": 63,                # 3 × 3 × 7
    "min_grill_per_expedition": 3,
    "min_total_grill": 27,             # 3 × 3 × 3
}


@dataclass
class RunReport:
    run_id: str
    started_at: str
    finished_at: str
    diamond_reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    packet_count: int = 0
    verifier_summary: dict[str, Any] = field(default_factory=dict)
    run_totals: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "diamond_reports": self.diamond_reports,
            "packet_count": self.packet_count,
            "verifier_summary": self.verifier_summary,
            "run_totals": self.run_totals,
        }


# ────────────────────────────────────────────────────────────────────
# Default scoring profiles (caller can override)
# ────────────────────────────────────────────────────────────────────


DEFAULT_PROFILES: dict[str, dict[str, dict[str, float]]] = {
    "opportunity": {
        "positive": {
            "transformation_z": 6.0,
            "orthodoxy_break_z": 5.0,
            "evidence_z": 4.0,
        },
        "negative": {
            "behavioral_evidence_z": 2.0,
            "economic_viability_z": 3.0,
        },
    },
    "invention": {
        "positive": {
            "novelty": 5.0,
            "systematicity": 4.0,
            "utility": 6.0,
            "interference": 1.0,
            "structural_floor": 5.0,
        },
        "negative": {
            "transformation_value": 2.5,
        },
    },
    "proof": {
        "positive": {
            "behavioral_proof_z": 5.0,
            "technical_proof_z": 4.0,
            "novelty_proof_z": 5.5,
        },
        "negative": {
            "falsification_energy": 8.0,
        },
    },
}


# ────────────────────────────────────────────────────────────────────
# Master conductor
# ────────────────────────────────────────────────────────────────────


class DeviatrixConductor:
    """Run the full 3 × 3 × 7 doctrine."""

    def __init__(
        self,
        *,
        run_id: str | None = None,
        reference_population_factory: Callable[[int], list[float]] | None = None,
        claim_factory: Callable[[str, schemas.DiamondKind], schemas.MathClaim] | None = None,
        profiles: dict[str, dict[str, dict[str, float]]] | None = None,
        verifier_id: str = "verifier-master",
        min_grill: int = 3,
        seed: int = 1337,
        output_dir: str | None = None,
    ) -> None:
        self.run_id = run_id or f"deviatrix-{random.Random(seed).randint(0, 1<<30):08x}"
        # Default population factory: create ONE RNG per call seeded
        # with the run seed + population size, then draw n samples from
        # the same advancing state. Re-seeding per iteration would
        # emit the same first sample n times.
        def _default_pop(n: int) -> list[float]:
            rng = random.Random((seed * 1_000_003) ^ n)
            return [rng.gauss(0, 1) for _ in range(n)]

        self.refpop_factory = reference_population_factory or _default_pop
        self.claim_factory = claim_factory or self._default_claim_factory
        self.profiles = profiles or DEFAULT_PROFILES
        self.verifier = IndependentVerifier(verifier_id=verifier_id)
        self.min_grill = min_grill
        self.seed = seed
        self.output_dir = Path(output_dir) if output_dir else None

        self.report = RunReport(
            run_id=self.run_id,
            started_at="",
            finished_at="",
            run_totals=EXPECTED_RUN_TOTALS.copy(),
        )

    # ── Public API ─────────────────────────────────────────────────────

    def run(
        self,
        *,
        formula: str = "x**2 + x",
        pop_size: int = 500,
    ) -> RunReport:
        import datetime as _dt

        self.report.started_at = _dt.datetime.now(_dt.timezone.utc).isoformat()

        # Diamond 1 — Opportunity
        self._run_diamond(
            diamond=schemas.DiamondKind.OPPORTUNITY,
            formula=formula,
            pop_size=pop_size,
        )
        # Diamond 2 — Invention
        self._run_diamond(
            diamond=schemas.DiamondKind.INVENTION,
            formula=formula,
            pop_size=pop_size,
        )
        # Diamond 3 — Proof
        self._run_diamond(
            diamond=schemas.DiamondKind.PROOF,
            formula=formula,
            pop_size=pop_size,
        )

        self.report.finished_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
        self.report.verifier_summary = self.verifier.summary()
        self.report.packet_count = self.verifier.summary()["n_reports"]

        if self.output_dir:
            self._write_artifacts()

        return self.report

    # ── Internal: per-diamond runner ───────────────────────────────────

    def _run_diamond(
        self,
        *,
        diamond: schemas.DiamondKind,
        formula: str,
        pop_size: int,
    ) -> dict[str, Any]:
        harness = DiamondHarness(diamond=diamond)
        population = self.refpop_factory(pop_size)
        claim = self.claim_factory(formula, diamond)
        claim.reference_population = population
        claim.candidate_hash = claim._hash()  # ensure fresh hash for new pop

        outcomes: dict[str, ExpeditionOutcome] = {}
        iqrsqpi_summaries: dict[str, dict[str, Any]] = {}

        # 1) Positive tail
        pos_exp = self._positive_expedition(harness, diamond)
        pos_outcome = pos_exp.run(claim)
        outcomes["positive_tail"] = pos_outcome
        iqrsqpi_summaries["positive_tail"] = self._iqrsqpi(
            harness, schemas.ExpeditionKind.POSITIVE_TAIL
        )
        self._verify_packet(pos_outcome)

        # 2) Negative tail
        neg_exp = self._negative_expedition(harness, diamond)
        neg_outcome = neg_exp.run(claim)
        outcomes["negative_tail"] = neg_outcome
        iqrsqpi_summaries["negative_tail"] = self._iqrsqpi(
            harness, schemas.ExpeditionKind.NEGATIVE_TAIL
        )
        self._verify_packet(neg_outcome)

        # 3) Repaired tail (needs pos/neg outcomes)
        rep_exp = self._repaired_expedition(
            harness, diamond, pos_outcome=pos_outcome, neg_outcome=neg_outcome
        )
        rep_outcome = rep_exp.run(claim)
        outcomes["repaired_tail"] = rep_outcome
        iqrsqpi_summaries["repaired_tail"] = self._iqrsqpi(
            harness, schemas.ExpeditionKind.REPAIRED_TAIL
        )
        self._verify_packet(rep_outcome)

        diamond_report = {
            "diamond": diamond.value,
            "n_packets": harness.n_packets,
            "n_trace": len(harness.T_trace),
            "iqrsqpi": iqrsqpi_summaries,
            "outcomes": {
                kind: {
                    "certified_z": o.certified_z,
                    "band": o.band,
                    "pass_a": o.pass_a_status,
                    "pass_b": o.pass_b_status,
                    "pass_c": o.pass_c_status,
                    "sealed_hash": o.packets[0].sealed_hash,
                    "verifier_decision": o.packets[0].verifier.decision.value,
                    "verifier_reason": o.packets[0].verifier.reason[:80],
                    "system_action": action_for(o.certified_z),
                    "wall_breach": is_wall(o.certified_z),
                }
                for kind, o in outcomes.items()
            },
        }
        self.report.diamond_reports[diamond.value] = diamond_report
        return diamond_report

    # ── Internal: expedition factories per diamond ─────────────────────

    def _positive_expedition(
        self, harness: DiamondHarness, diamond: schemas.DiamondKind
    ):
        if diamond == schemas.DiamondKind.OPPORTUNITY:
            p = self.profiles["opportunity"]["positive"]
            return OpportunityPositiveTail(harness, **p)
        if diamond == schemas.DiamondKind.INVENTION:
            p = self.profiles["invention"]["positive"]
            return InventionPositiveTail(harness, **p)
        p = self.profiles["proof"]["positive"]
        return ProofPositiveTail(harness, **p)

    def _negative_expedition(
        self, harness: DiamondHarness, diamond: schemas.DiamondKind
    ):
        if diamond == schemas.DiamondKind.OPPORTUNITY:
            p = self.profiles["opportunity"]["negative"]
            return OpportunityNegativeTail(harness, **p)
        if diamond == schemas.DiamondKind.INVENTION:
            p = self.profiles["invention"]["negative"]
            return InventionNegativeTail(harness, **p)
        p = self.profiles["proof"]["negative"]
        return ProofNegativeTail(harness, **p)

    def _repaired_expedition(
        self,
        harness: DiamondHarness,
        diamond: schemas.DiamondKind,
        *,
        pos_outcome: ExpeditionOutcome,
        neg_outcome: ExpeditionOutcome,
    ):
        if diamond == schemas.DiamondKind.OPPORTUNITY:
            return OpportunityRepairedTail(
                harness, positive_outcome=pos_outcome, negative_outcome=neg_outcome
            )
        if diamond == schemas.DiamondKind.INVENTION:
            return InventionRepairedTail(
                harness, positive_outcome=pos_outcome, negative_outcome=neg_outcome, coherence=2.0
            )
        return ProofRepairedTail(
            harness, positive_outcome=pos_outcome, negative_outcome=neg_outcome, gamma=0.5
        )

    # ── Internal: IQRSQPI driver ───────────────────────────────────────

    def _iqrsqpi(
        self,
        harness: DiamondHarness,
        expedition: schemas.ExpeditionKind,
    ) -> dict[str, Any]:
        conductor = IQRSQPIConductor(
            harness, expedition, min_grill_cycles=self.min_grill
        )
        return conductor.run_quick()

    # ── Internal: verifier ─────────────────────────────────────────────

    def _verify_packet(self, outcome: ExpeditionOutcome) -> VerifierReport:
        return self.verifier.verify(outcome.packets[0])

    # ── Internal: defaults ─────────────────────────────────────────────

    @staticmethod
    def _default_claim_factory(formula: str, diamond: schemas.DiamondKind) -> schemas.MathClaim:
        return schemas.MathClaim(
            expression=formula,
            symbols=["x"],
            assumptions={},
            estimator="robust_madz",
            expected_result=None,
            falsifier=(
                "certified_z < 3σ after adversarial pass, or "
                "composite deviation below diamond structural floor"
            ),
        )

    # ── Internal: artifact writing ─────────────────────────────────────

    def _write_artifacts(self) -> None:
        assert self.output_dir is not None
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Master summary
        (self.output_dir / "run_report.json").write_text(
            json.dumps(self.report.to_dict(), indent=2, default=str)
        )

        # Per-diamond detail
        for diamond_name, drep in self.report.diamond_reports.items():
            diamond_dir = self.output_dir / diamond_name
            diamond_dir.mkdir(parents=True, exist_ok=True)
            (diamond_dir / "report.json").write_text(
                json.dumps(drep, indent=2, default=str)
            )
            for kind_name, o in drep["outcomes"].items():
                (diamond_dir / f"{kind_name}.summary.json").write_text(
                    json.dumps(o, indent=2, default=str)
                )
