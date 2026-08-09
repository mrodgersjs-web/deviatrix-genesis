"""A/B testing framework — compare formula generation strategies head-to-head.

Run two strategies on the same brief and compare survivors, z-scores,
and convergence speed.

Usage::

    from deviatrix_genesis.v5.ab_testing import ABTest

    test = ABTest()
    result = test.compare(
        brief="GTM strategy",
        strategy_a={"name": "template", "use_llm": False},
        strategy_b={"name": "llm", "use_llm": True},
    )
    print(result.summary())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ABTest", "ABResult"]


@dataclass
class ABResult:
    """Result of an A/B comparison."""
    strategy_a: dict[str, Any]
    strategy_b: dict[str, Any]
    winner: str
    metrics: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        lines = ["A/B Test Result"]
        a = self.strategy_a
        b = self.strategy_b
        lines.append(f"  A ({a.get('name', '?')}): {a.get('survivors', 0)} survivors, best_z={a.get('best_z', 0):.2f}, {a.get('wall_s', 0):.1f}s")
        lines.append(f"  B ({b.get('name', '?')}): {b.get('survivors', 0)} survivors, best_z={b.get('best_z', 0):.2f}, {b.get('wall_s', 0):.1f}s")
        lines.append(f"  Winner: {self.winner}")
        return "\n".join(lines)


class ABTest:
    """Compare two strategies on the same brief."""

    def compare(
        self,
        brief: str,
        strategy_a: dict[str, Any],
        strategy_b: dict[str, Any],
        n_ideas: int = 3,
        max_rounds: int = 2,
        seeds: list[int] | None = None,
    ) -> ABResult:
        """Run both strategies and compare."""
        if seeds is None:
            seeds = [2026]

        result_a = self._run_strategy(brief, strategy_a, n_ideas, max_rounds, seeds)
        result_b = self._run_strategy(brief, strategy_b, n_ideas, max_rounds, seeds)

        # Determine winner
        score_a = result_a.get("survivors", 0) * 10 + result_a.get("best_z", 0)
        score_b = result_b.get("survivors", 0) * 10 + result_b.get("best_z", 0)
        winner = "A" if score_a > score_b else "B" if score_b > score_a else "Tie"

        return ABResult(
            strategy_a=result_a,
            strategy_b=result_b,
            winner=winner,
            metrics={"score_a": score_a, "score_b": score_b},
        )

    def _run_strategy(
        self, brief: str, strategy: dict[str, Any],
        n_ideas: int, max_rounds: int, seeds: list[int],
    ) -> dict[str, Any]:
        from .pipeline import run_v5_pipeline

        t0 = time.monotonic()
        try:
            result = run_v5_pipeline(
                brief=brief, n_ideas=n_ideas, max_rounds=max_rounds, seeds=seeds,
            )
            survivors = result.get("survivors", [])
            z_values = [s.get("composite_z", 0.0) for s in survivors]
            return {
                "name": strategy.get("name", "unnamed"),
                "survivors": len(survivors),
                "best_z": max(z_values) if z_values else 0.0,
                "median_z": sorted(z_values)[len(z_values) // 2] if z_values else 0.0,
                "wall_s": time.monotonic() - t0,
                "status": "ok",
            }
        except Exception as exc:
            return {
                "name": strategy.get("name", "unnamed"),
                "survivors": 0, "best_z": 0.0, "median_z": 0.0,
                "wall_s": time.monotonic() - t0,
                "status": f"error: {exc}",
            }
