"""Doctrine auto-evolution — learns from run history to improve scoring.

Reads the persistent run history and proposes adjustments to:
  * Sigma-band routing boundaries
  * Scoring weights (anti_orthodoxy, mechanism_originality, prior_art_distance)
  * Convergence thresholds

The learner never auto-applies changes — it produces a proposal that
a human (or the pipeline's Gate-D) must approve.

Usage::

    from deviatrix_genesis.v5.doctrine_evolution import DoctrineLearner

    learner = DoctrineLearner()
    proposal = learner.analyze_history(last_n=20)
    print(proposal.summary())
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .run_history import RunHistory

__all__ = ["DoctrineLearner", "EvolutionProposal"]


@dataclass
class BandAdjustment:
    """Proposed adjustment to a sigma band boundary."""
    band_name: str
    current_lo: float
    current_hi: float
    proposed_lo: float
    proposed_hi: float
    reason: str
    confidence: float  # 0-1


@dataclass
class WeightAdjustment:
    """Proposed adjustment to scoring weights."""
    weight_name: str
    current_value: float
    proposed_value: float
    reason: str
    confidence: float


@dataclass
class EvolutionProposal:
    """A set of proposed doctrine changes."""
    band_adjustments: list[BandAdjustment] = field(default_factory=list)
    weight_adjustments: list[WeightAdjustment] = field(default_factory=list)
    convergence_adjustments: dict[str, Any] = field(default_factory=dict)
    analysis_notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = ["Doctrine Evolution Proposal"]
        lines.append(f"  Band adjustments: {len(self.band_adjustments)}")
        lines.append(f"  Weight adjustments: {len(self.weight_adjustments)}")
        for ba in self.band_adjustments:
            lines.append(f"    {ba.band_name}: [{ba.current_lo}, {ba.current_hi}] → [{ba.proposed_lo}, {ba.proposed_hi}] ({ba.reason})")
        for wa in self.weight_adjustments:
            lines.append(f"    {wa.weight_name}: {wa.current_value} → {wa.proposed_value} ({wa.reason})")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "band_adjustments": [
                {"band": ba.band_name, "current": [ba.current_lo, ba.current_hi],
                 "proposed": [ba.proposed_lo, ba.proposed_hi], "reason": ba.reason,
                 "confidence": ba.confidence}
                for ba in self.band_adjustments
            ],
            "weight_adjustments": [
                {"weight": wa.weight_name, "current": wa.current_value,
                 "proposed": wa.proposed_value, "reason": wa.reason,
                 "confidence": wa.confidence}
                for wa in self.weight_adjustments
            ],
            "convergence": self.convergence_adjustments,
            "notes": self.analysis_notes,
        }


class DoctrineLearner:
    """Analyzes run history and proposes doctrine improvements."""

    def __init__(self, history: RunHistory | None = None) -> None:
        self.history = history or RunHistory()

    def analyze_history(self, last_n: int = 20) -> EvolutionProposal:
        """Analyze the last N runs and propose improvements."""
        proposal = EvolutionProposal()
        runs = self.history.recent_runs(limit=last_n)

        if len(runs) < 3:
            proposal.analysis_notes.append("Not enough runs for analysis (need ≥3)")
            return proposal

        # ── Analyze z-score distribution ────────────────────────────
        all_best_z = [r.best_z for r in runs]
        all_median_z = [r.median_z for r in runs]
        survivor_counts = [r.n_survivors for r in runs]

        avg_best = statistics.mean(all_best_z)
        avg_median = statistics.mean(all_median_z)
        avg_survivors = statistics.mean(survivor_counts)

        proposal.analysis_notes.append(f"Analyzed {len(runs)} runs")
        proposal.analysis_notes.append(f"Avg best z: {avg_best:.2f}, avg median z: {avg_median:.2f}")
        proposal.analysis_notes.append(f"Avg survivors: {avg_survivors:.1f}")

        # ── Band boundary proposals ─────────────────────────────────
        # If most survivors cluster in one band, suggest widening it
        self._analyze_band_clustering(runs, proposal)

        # ── Weight proposals ────────────────────────────────────────
        self._analyze_weight_effectiveness(runs, proposal)

        # ── Convergence proposals ───────────────────────────────────
        round_counts = [r.n_rounds for r in runs]
        avg_rounds = statistics.mean(round_counts)
        if avg_rounds < 2:
            proposal.convergence_adjustments["suggestion"] = "Pipeline converges too fast — consider lowering min_rounds"
        elif avg_rounds > 8:
            proposal.convergence_adjustments["suggestion"] = "Pipeline runs many rounds — consider raising convergence threshold"

        return proposal

    def _analyze_band_clustering(
        self, runs: list[Any], proposal: EvolutionProposal
    ) -> None:
        """Check if survivors cluster in specific bands."""
        # Collect all survivor z-scores
        z_scores: list[float] = []
        for run in runs:
            survivors = json.loads(run.survivors_json) if isinstance(run.survivors_json, str) else run.survivors_json
            for s in survivors:
                z = s.get("composite_z", 0.0)
                z_scores.append(z)

        if not z_scores:
            return

        # Check clustering
        in_0_3 = sum(1 for z in z_scores if 0 <= z < 3)
        in_3_5 = sum(1 for z in z_scores if 3 <= z < 5)
        in_5_10 = sum(1 for z in z_scores if 5 <= z < 10)
        in_10_20 = sum(1 for z in z_scores if 10 <= z < 20)
        total = len(z_scores)

        # If >60% cluster in one band, suggest widening
        for count, lo, hi, name in [
            (in_0_3, 0, 3, "0σ–3σ"), (in_3_5, 3, 5, "+3σ–5σ"),
            (in_5_10, 5, 10, "+5σ–10σ"), (in_10_20, 10, 20, "+10σ–20σ"),
        ]:
            if count / total > 0.6:
                proposal.band_adjustments.append(BandAdjustment(
                    band_name=name, current_lo=lo, current_hi=hi,
                    proposed_lo=lo * 0.8, proposed_hi=hi * 1.2,
                    reason=f"{count}/{total} ({count/total*100:.0f}%) survivors cluster here",
                    confidence=min(count / total, 0.9),
                ))

    def _analyze_weight_effectiveness(
        self, runs: list[Any], proposal: EvolutionProposal
    ) -> None:
        """Check if scoring weights are producing good discrimination."""
        z_scores: list[float] = []
        for run in runs:
            survivors = json.loads(run.survivors_json) if isinstance(run.survivors_json, str) else run.survivors_json
            for s in survivors:
                z_scores.append(s.get("composite_z", 0.0))

        if len(z_scores) < 5:
            return

        # If z-score variance is low, weights aren't discriminating well
        if len(z_scores) > 1:
            z_stdev = statistics.stdev(z_scores)
            if z_stdev < 1.0:
                proposal.weight_adjustments.append(WeightAdjustment(
                    weight_name="composite_deviation_weight",
                    current_value=0.7,
                    proposed_value=0.8,
                    reason=f"Low z-score variance ({z_stdev:.2f}) — behavioral weight too low",
                    confidence=0.6,
                ))
