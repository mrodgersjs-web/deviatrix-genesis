"""Causal inference — which formula features cause high z-scores.

Analyzes run history to find correlations between formula features
and z-score outcomes. Uses simple feature extraction + regression.

Usage::

    from deviatrix_genesis.v5.causal import CausalAnalyzer

    analyzer = CausalAnalyzer()
    report = analyzer.analyze(last_n=20)
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass
from typing import Any

from .run_history import RunHistory

__all__ = ["CausalAnalyzer", "CausalReport"]


@dataclass
class CausalReport:
    features: list[dict[str, Any]]
    top_positive: list[str]
    top_negative: list[str]
    notes: list[str]


class CausalAnalyzer:
    """Analyze which formula features correlate with high z-scores."""

    _FEATURE_PATTERNS = {
        "has_exp": r"exp\(",
        "has_log": r"log\(",
        "has_sin": r"sin\(",
        "has_cos": r"cos\(",
        "has_sqrt": r"sqrt\(",
        "has_power": r"\*\*",
        "has_division": r"/",
        "has_negation": r"-[a-z]",
        "complexity_high": lambda f: len(f) > 20,
        "complexity_low": lambda f: len(f) <= 10,
        "single_variable": lambda f: "y" not in f,
        "multi_variable": lambda f: "y" in f,
    }

    def analyze(self, last_n: int = 20) -> CausalReport:
        history = RunHistory()
        runs = history.recent_runs(limit=last_n)

        if not runs:
            return CausalReport(features=[], top_positive=[], top_negative=[], notes=["No runs"])

        # Extract features and z-scores
        feature_z: dict[str, list[float]] = {f: [] for f in self._FEATURE_PATTERNS}

        for run in runs:
            survivors = json.loads(run.survivors_json) if isinstance(run.survivors_json, str) else []
            for s in survivors:
                formula = s.get("formula", "")
                z = s.get("composite_z", 0.0)
                for fname, pattern in self._FEATURE_PATTERNS.items():
                    if callable(pattern):
                        has = pattern(formula)
                    else:
                        has = bool(re.search(pattern, formula))
                    if has:
                        feature_z[fname].append(z)

        # Compute statistics per feature
        features: list[dict[str, Any]] = []
        for fname, z_scores in feature_z.items():
            if not z_scores:
                continue
            features.append({
                "feature": fname,
                "count": len(z_scores),
                "mean_z": round(statistics.mean(z_scores), 2),
                "median_z": round(statistics.median(z_scores), 2),
            })

        features.sort(key=lambda f: -f["mean_z"])
        top_positive = [f["feature"] for f in features[:3] if f["mean_z"] > 0]
        top_negative = [f["feature"] for f in features[-3:] if f["mean_z"] < 0]

        return CausalReport(
            features=features,
            top_positive=top_positive,
            top_negative=top_negative,
            notes=[f"Analyzed {len(runs)} runs"],
        )

    def report(self, analysis: CausalReport) -> str:
        lines = ["# Causal Analysis Report\n"]
        lines.append(f"Runs analyzed: {analysis.notes[0] if analysis.notes else 'N/A'}\n")
        lines.append("## Feature → Z-Score Correlation\n")
        for f in analysis.features:
            bar = "█" * min(int(abs(f["mean_z"]) * 2), 20)
            sign = "+" if f["mean_z"] >= 0 else "-"
            lines.append(f"  {f['feature']:<20} {sign}{abs(f['mean_z']):>5.2f} ({f['count']}x) {bar}")
        if analysis.top_positive:
            lines.append(f"\n**Top positive features:** {', '.join(analysis.top_positive)}")
        if analysis.top_negative:
            lines.append(f"**Top negative features:** {', '.join(analysis.top_negative)}")
        return "\n".join(lines)
