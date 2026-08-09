"""Self-healing pipeline — auto-retry failed expeditions with different seeds.

When an expedition fails (verifier FAIL, wall breach, or exception),
the healer retries with a different seed up to max_retries times.

Usage::

    from deviatrix_genesis.v5.healer import HealingPipeline

    hp = HealingPipeline(max_retries=3)
    result = hp.run_with_healing(brief="GTM strategy")
"""

from __future__ import annotations

import time
from typing import Any

__all__ = ["HealingPipeline"]


class HealingPipeline:
    """Pipeline wrapper that auto-retries failed expeditions."""

    def __init__(self, max_retries: int = 3, base_seed: int = 2026) -> None:
        self.max_retries = max_retries
        self.base_seed = base_seed

    def run_with_healing(self, brief: str, **kwargs: Any) -> dict[str, Any]:
        """Run pipeline with auto-retry on failure."""
        from .pipeline import run_v5_pipeline

        best_result: dict[str, Any] | None = None
        best_survivors = 0
        attempts: list[dict[str, Any]] = []

        for attempt in range(self.max_retries):
            seed = self.base_seed + attempt * 1000
            t0 = time.monotonic()

            try:
                result = run_v5_pipeline(
                    brief=brief,
                    seeds=[seed],
                    **kwargs,
                )
                elapsed = time.monotonic() - t0

                survivors = result.get("survivors", [])
                attempts.append({
                    "attempt": attempt,
                    "seed": seed,
                    "survivors": len(survivors),
                    "wall_clock_s": elapsed,
                    "status": "ok",
                })

                if len(survivors) > best_survivors:
                    best_survivors = len(survivors)
                    best_result = result

                # If we got survivors, stop retrying
                if survivors:
                    break

            except Exception as exc:
                attempts.append({
                    "attempt": attempt,
                    "seed": seed,
                    "survivors": 0,
                    "status": f"error: {exc}",
                })

        if best_result is None:
            return {
                "survivors": [],
                "dropped": [],
                "hybrids": [],
                "healing_attempts": attempts,
                "status": "all_failed",
            }

        best_result["healing_attempts"] = attempts
        best_result["healing_retries"] = len(attempts) - 1
        return best_result
