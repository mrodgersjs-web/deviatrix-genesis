"""Memory consolidation — compress run history into doctrinal axioms.

Periodically scans the run history and distills patterns into
compressed axioms that accelerate future runs. The pipeline gets
faster as its foundational knowledge becomes denser.

Axiom types:
  * scoring_axiom: "formulas with exp() score 2.3x higher than sin()"
  * convergence_axiom: "round 3 rarely adds new survivors"
  * formula_axiom: "x**2 * exp(-x/10) is the most robust base pattern"
  * band_axiom: "ideas cluster in +5σ–10σ for financial mechanisms"

Usage::

    from deviatrix_genesis.v5.axioms import AxiomEngine

    engine = AxiomEngine()
    axioms = engine.consolidate(last_n=20)
    print(axioms.summary())
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field
from typing import Any

from .run_history import RunHistory

__all__ = ["AxiomEngine", "Axiom"]


@dataclass
class Axiom:
    """A compressed doctrinal axiom derived from run history."""
    axiom_type: str  # scoring, convergence, formula, band
    statement: str
    confidence: float  # 0-1
    evidence_count: int = 0
    source_runs: list[str] = field(default_factory=list)


class AxiomEngine:
    """Consolidate run history into doctrinal axioms."""

    def __init__(self, history: RunHistory | None = None) -> None:
        self.history = history or RunHistory()

    def consolidate(self, last_n: int = 20) -> "AxiomSet":
        """Consolidate the last N runs into axioms."""
        runs = self.history.recent_runs(limit=last_n)

        if len(runs) < 3:
            return AxiomSet(axioms=[], runs_analyzed=len(runs))

        axioms: list[Axiom] = []

        axioms.extend(self._scoring_axioms(runs))
        axioms.extend(self._convergence_axioms(runs))
        axioms.extend(self._formula_axioms(runs))
        axioms.extend(self._band_axioms(runs))

        return AxiomSet(
            axioms=sorted(axioms, key=lambda a: -a.confidence),
            runs_analyzed=len(runs),
        )

    def _scoring_axioms(self, runs: list[Any]) -> list[Axiom]:
        """Extract scoring pattern axioms."""
        axioms: list[Axiom] = []

        # Analyze z-score trends
        z_values = [r.best_z for r in runs if r.best_z > 0]
        if z_values:
            avg_z = statistics.mean(z_values)
            if avg_z > 5.0:
                axioms.append(Axiom(
                    axiom_type="scoring",
                    statement=f"Average best z-score across runs is {avg_z:.1f}σ — pipeline consistently finds non-trivial deviations",
                    confidence=min(len(z_values) / 10, 0.9),
                    evidence_count=len(z_values),
                    source_runs=[r.run_id for r in runs if r.best_z > 0][:5],
                ))

        # Analyze survivor rate
        survivor_rates = [r.n_survivors for r in runs]
        if survivor_rates:
            avg_survivors = statistics.mean(survivor_rates)
            if avg_survivors < 1:
                axioms.append(Axiom(
                    axiom_type="scoring",
                    statement="Verifier threshold is very strict — most runs produce 0 survivors. Consider relaxing for exploratory runs.",
                    confidence=0.8,
                    evidence_count=len(runs),
                ))

        return axioms

    def _convergence_axioms(self, runs: list[Any]) -> list[Axiom]:
        """Extract convergence pattern axioms."""
        axioms: list[Axiom] = []

        round_counts = [r.n_rounds for r in runs]
        if round_counts:
            avg_rounds = statistics.mean(round_counts)
            if avg_rounds < 2:
                axioms.append(Axiom(
                    axiom_type="convergence",
                    statement=f"Pipeline converges in {avg_rounds:.1f} rounds on average — early stopping is effective",
                    confidence=0.7,
                    evidence_count=len(runs),
                ))
            elif avg_rounds > 5:
                axioms.append(Axiom(
                    axiom_type="convergence",
                    statement=f"Pipeline takes {avg_rounds:.1f} rounds on average — convergence threshold may be too loose",
                    confidence=0.6,
                    evidence_count=len(runs),
                ))

        return axioms

    def _formula_axioms(self, runs: list[Any]) -> list[Axiom]:
        """Extract formula pattern axioms."""
        axioms: list[Axiom] = []

        # Analyze formula features from survivors
        all_survivors: list[dict[str, Any]] = []
        for run in runs:
            survivors = json.loads(run.survivors_json) if isinstance(run.survivors_json, str) else []
            all_survivors.extend(survivors)

        if not all_survivors:
            return axioms

        # Count mechanism families
        families: dict[str, int] = {}
        for s in all_survivors:
            fam = s.get("mechanism_family", "unknown")
            families[fam] = families.get(fam, 0) + 1

        if families:
            top_family = max(families, key=families.get)  # type: ignore
            axioms.append(Axiom(
                axiom_type="formula",
                statement=f"Most common mechanism family in survivors: {top_family} ({families[top_family]} occurrences)",
                confidence=min(families[top_family] / 10, 0.9),
                evidence_count=families[top_family],
            ))

        # Analyze formula features
        has_exp = sum(1 for s in all_survivors if "exp(" in s.get("formula", ""))
        has_sin = sum(1 for s in all_survivors if "sin(" in s.get("formula", ""))
        total = len(all_survivors)

        if total > 3:
            if has_exp / total > 0.5:
                axioms.append(Axiom(
                    axiom_type="formula",
                    statement=f"exp() appears in {has_exp/total*100:.0f}% of survivors — exponential decay is a robust pattern",
                    confidence=min(has_exp / total, 0.9),
                    evidence_count=has_exp,
                ))
            if has_sin / total > 0.5:
                axioms.append(Axiom(
                    axiom_type="formula",
                    statement=f"sin() appears in {has_sin/total*100:.0f}% of survivors — periodic variation is a robust pattern",
                    confidence=min(has_sin / total, 0.9),
                    evidence_count=has_sin,
                ))

        return axioms

    def _band_axioms(self, runs: list[Any]) -> list[Axiom]:
        """Extract band distribution axioms."""
        axioms: list[Axiom] = []

        all_survivors: list[dict[str, Any]] = []
        for run in runs:
            survivors = json.loads(run.survivors_json) if isinstance(run.survivors_json, str) else []
            all_survivors.extend(survivors)

        if not all_survivors:
            return axioms

        bands: dict[str, int] = {}
        for s in all_survivors:
            band = s.get("band", "unknown")
            bands[band] = bands.get(band, 0) + 1

        if bands:
            top_band = max(bands, key=bands.get)  # type: ignore
            axioms.append(Axiom(
                axiom_type="band",
                statement=f"Most common survivor band: {top_band} ({bands[top_band]} occurrences)",
                confidence=min(bands[top_band] / 10, 0.9),
                evidence_count=bands[top_band],
            ))

        return axioms


@dataclass
class AxiomSet:
    """A set of consolidated axioms."""
    axioms: list[Axiom]
    runs_analyzed: int

    def summary(self) -> str:
        lines = [f"Axiom Set ({self.runs_analyzed} runs analyzed, {len(self.axioms)} axioms)"]
        for a in self.axioms:
            lines.append(f"  [{a.axiom_type}] {a.statement} (confidence: {a.confidence:.0%})")
        return "\n".join(lines)

    def get_by_type(self, axiom_type: str) -> list[Axiom]:
        return [a for a in self.axioms if a.axiom_type == axiom_type]

    def to_dict(self) -> dict[str, Any]:
        return {
            "runs_analyzed": self.runs_analyzed,
            "axioms": [
                {
                    "type": a.axiom_type,
                    "statement": a.statement,
                    "confidence": a.confidence,
                    "evidence_count": a.evidence_count,
                }
                for a in self.axioms
            ],
        }
