"""Adaptive convergence detector.

Tracks z-score distribution across iterative rounds and stops early when:
  1. No new survivors in N consecutive rounds.
  2. Median-z improvement < threshold for 2 consecutive rounds.
  3. Max rounds hit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .telemetry import ConvergenceMetrics

__all__ = ["ConvergenceDecision", "AdaptiveConvergence"]


@dataclass
class ConvergenceDecision:
    should_stop: bool
    reason: str
    round_number: int


class AdaptiveConvergence:
    """Evaluate round-over-round whether the idea space is exhausted."""

    def __init__(
        self,
        min_rounds: int = 2,
        max_rounds: int = 10,
        no_new_survivors_patience: int = 2,
        z_improvement_threshold: float = 0.1,
    ) -> None:
        self.min_rounds = min_rounds
        self.max_rounds = max_rounds
        self.patience = no_new_survivors_patience
        self.threshold = z_improvement_threshold

        # internal state
        self._prev_survivor_names: set[str] = set()
        self._rounds_since_new: int = 0
        self._plateau_streak: int = 0
        self._round_count: int = 0

    def update(self, metrics: ConvergenceMetrics, survivor_names: set[str]) -> ConvergenceDecision:
        self._round_count += 1

        # ── new-survivor check ──────────────────────────────────────
        new_names = survivor_names - self._prev_survivor_names
        if not new_names and self._round_count > 1:
            self._rounds_since_new += 1
        else:
            self._rounds_since_new = 0
        self._prev_survivor_names = survivor_names | self._prev_survivor_names

        # ── plateau check ───────────────────────────────────────────
        if abs(metrics.z_improvement_vs_prev) < self.threshold:
            self._plateau_streak += 1
        else:
            self._plateau_streak = 0

        # ── decision ────────────────────────────────────────────────
        if self._round_count < self.min_rounds:
            return ConvergenceDecision(False, "below_min_rounds", self._round_count)

        if self._rounds_since_new >= self.patience:
            return ConvergenceDecision(
                True, f"no_new_survivors_for_{self._rounds_since_new}_rounds", self._round_count
            )

        if self._plateau_streak >= 2:
            return ConvergenceDecision(
                True, f"z_plateau_for_{self._plateau_streak}_rounds", self._round_count
            )

        if self._round_count >= self.max_rounds:
            return ConvergenceDecision(True, "max_rounds_reached", self._round_count)

        return ConvergenceDecision(False, "improving", self._round_count)

    def reset(self) -> None:
        self._prev_survivor_names = set()
        self._rounds_since_new = 0
        self._plateau_streak = 0
        self._round_count = 0
