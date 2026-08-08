"""Comparative benchmark harness — v3 vs v5.

Runs the same brief through multiple engines and produces a side-by-side
comparison of wall-clock time, survivor quality, and convergence speed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any

__all__ = ["BenchmarkResult", "run_benchmark", "render_comparison"]


@dataclass
class BenchmarkResult:
    engine: str
    brief: str
    wall_clock_s: float
    n_survivors: int
    best_z: float
    median_z: float
    n_rounds: int
    n_packets: int


def run_benchmark(
    brief: str,
    engines: list[str] | None = None,
    seeds: list[int] | None = None,
) -> list[BenchmarkResult]:
    """Run *brief* through each engine and return results."""
    if engines is None:
        engines = ["v3"]
    if seeds is None:
        seeds = [2026]

    results: list[BenchmarkResult] = []

    for eng in engines:
        if eng == "v3":
            results.append(_bench_v3(brief, seeds))
        elif eng == "v5":
            results.append(_bench_v5(brief, seeds))
        else:
            raise ValueError(f"unknown engine: {eng!r}")

    return results


def _bench_v3(brief: str, seeds: list[int]) -> BenchmarkResult:
    from ..v3.pipeline import run_pipeline

    t0 = time.monotonic()
    result = run_pipeline(brief=brief, n_seeds=len(seeds))
    elapsed = time.monotonic() - t0

    survivors = result.get("survivors", [])
    z_values = [s.get("composite_z", 0.0) for s in survivors]

    return BenchmarkResult(
        engine="v3",
        brief=brief,
        wall_clock_s=elapsed,
        n_survivors=len(survivors),
        best_z=max(z_values) if z_values else 0.0,
        median_z=sorted(z_values)[len(z_values) // 2] if z_values else 0.0,
        n_rounds=1,
        n_packets=result.get("n_packets", 0),
    )


def _bench_v5(brief: str, seeds: list[int]) -> BenchmarkResult:
    try:
        from .pipeline import run_v5_pipeline
    except ImportError:
        return BenchmarkResult(
            engine="v5", brief=brief, wall_clock_s=0.0,
            n_survivors=0, best_z=0.0, median_z=0.0,
            n_rounds=0, n_packets=0,
        )

    t0 = time.monotonic()
    result = run_v5_pipeline(brief=brief, seeds=seeds)
    elapsed = time.monotonic() - t0

    survivors = result.get("survivors", [])
    z_values = [s.get("composite_z", 0.0) for s in survivors]

    return BenchmarkResult(
        engine="v5",
        brief=brief,
        wall_clock_s=elapsed,
        n_survivors=len(survivors),
        best_z=max(z_values) if z_values else 0.0,
        median_z=sorted(z_values)[len(z_values) // 2] if z_values else 0.0,
        n_rounds=result.get("n_rounds", 0),
        n_packets=result.get("n_packets", 0),
    )


def render_comparison(results: list[BenchmarkResult]) -> str:
    """Render benchmark results as a comparison table."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("  DEVIATRIX BENCHMARK — v3 vs v5")
    lines.append("=" * 72)
    header = f"  {'Engine':<8} {'Time':>8} {'Surv':>6} {'Best σ':>8} {'Med σ':>8} {'Rounds':>7} {'Pkts':>6}"
    lines.append(header)
    lines.append("  " + "-" * 68)
    for r in results:
        lines.append(
            f"  {r.engine:<8} {r.wall_clock_s:>7.2f}s {r.n_survivors:>6} "
            f"{r.best_z:>8.2f} {r.median_z:>8.2f} {r.n_rounds:>7} {r.n_packets:>6}"
        )
    lines.append("=" * 72)

    # Speedup
    if len(results) == 2 and results[1].wall_clock_s > 0:
        speedup = results[0].wall_clock_s / results[1].wall_clock_s
        lines.append(f"  Speedup: {speedup:.1f}x (v5/v3)")

    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Deviatrix benchmark")
    p.add_argument("--brief", default="Operator-first GTM with financial primitives")
    p.add_argument("--engines", default="v3,v5")
    p.add_argument("--seeds", default="2026")
    args = p.parse_args()

    engines = [e.strip() for e in args.engines.split(",")]
    seeds = [int(s) for s in args.seeds.split(",")]

    results = run_benchmark(brief=args.brief, engines=engines, seeds=seeds)
    print(render_comparison(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
