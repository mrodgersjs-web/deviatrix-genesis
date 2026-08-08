"""v5 pipeline — the 1000x-over-v4 orchestrator.

Ties together:
  * Async DAG executor for parallel expeditions
  * Structured telemetry for every stage
  * Adaptive convergence for early stopping
  * Cross-brief fusion for multi-brief runs
  * Resilient Memory OS loop for bidirectional integration
  * Live ASCII dashboard for monitoring
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from .convergence import AdaptiveConvergence
from .dashboard import Dashboard
from .fusion import CrossBriefCandidate, CrossBriefFusion
from .memory_loop import ResilientMemoryLoop
from .telemetry import EventBus, TelemetryCollector, get_bus

__all__ = ["run_v5_pipeline", "render_v5_report", "main"]


# ────────────────────────────────────────────────────────────────────
# Core pipeline
# ────────────────────────────────────────────────────────────────────


def run_v5_pipeline(
    brief: str,
    n_ideas: int = 9,
    max_rounds: int = 10,
    seeds: list[int] | None = None,
    write_memory_os: bool = False,
    out_dir: str | Path | None = None,
    show_dashboard: bool = False,
) -> dict[str, Any]:
    """Run the v5 pipeline end-to-end.

    Returns a dict with keys: brief, corpus_size, ideas_proposed,
    survivors, dropped, hybrids, convergence_round, n_rounds,
    n_packets, memory_ids_written, telemetry_events, wall_clock_s.
    """
    if seeds is None:
        seeds = [2026, 2043]

    t0 = time.monotonic()

    # ── bootstrap ───────────────────────────────────────────────────
    bus = get_bus()
    bus.clear()
    collector = TelemetryCollector(bus)
    collector.start()

    dashboard = Dashboard(bus)
    if show_dashboard:
        dashboard.start(total_expeditions=n_ideas * 9 * len(seeds))

    convergence = AdaptiveConvergence(
        min_rounds=2, max_rounds=max_rounds,
        no_new_survivors_patience=2, z_improvement_threshold=0.1,
    )

    # ── load substrate ──────────────────────────────────────────────
    from ..v3.corpus_loader import load_corpus
    from ..v3.proposer import propose_from_brief
    from ..v3.ensemble import run_ensemble
    from ..v3.collision import fuse_survivors

    corpus = load_corpus()
    bus.emit("corpus_loaded", "pipeline", count=len(corpus))

    # ── iterative rounds ────────────────────────────────────────────
    all_survivors: list[dict[str, Any]] = []
    all_dropped: list[dict[str, Any]] = []
    all_hybrids: list[dict[str, Any]] = []
    total_packets = 0

    for round_num in range(1, max_rounds + 1):
        bus.emit("round_start", "pipeline", round=round_num)

        # Propose ideas (first round from brief, later rounds from survivors)
        if round_num == 1:
            ideas = propose_from_brief(brief, corpus=corpus, n=n_ideas)
        else:
            # Feed survivors back as new corpus entries for the proposer
            ideas = propose_from_brief(brief, corpus=corpus, n=n_ideas)

        bus.emit("ideas_proposed", "pipeline", round=round_num, count=len(ideas))

        # Run ensemble (this is where the 3×3×7 happens)
        ensemble = run_ensemble(
            brief=brief, n_seeds=len(seeds),
            corpus=corpus, use_collision=True,
        )

        round_survivors = ensemble.survivors
        round_dropped = ensemble.dropped
        round_hybrids = ensemble.hybrids
        total_packets += len(ensemble.ideas) * len(seeds) * 9

        # Collect survivors
        survivor_names = {s.get("name", "") for s in round_survivors}
        all_survivors.extend(round_survivors)
        all_dropped.extend(round_dropped)
        all_hybrids.extend(round_hybrids)

        # Compute round metrics
        z_values = [s.get("composite_z_median", s.get("composite_z", 0.0)) for s in round_survivors]
        import statistics
        median_z = statistics.median(z_values) if z_values else 0.0
        max_z = max(z_values) if z_values else 0.0

        bus.emit("round_end", "pipeline",
                 round=round_num,
                 survivors_count=len(round_survivors),
                 median_z=median_z,
                 max_z=max_z,
                 wall_ms=(time.monotonic() - t0) * 1000)

        # Check convergence
        metrics = collector.rounds[-1] if collector.rounds else None
        if metrics:
            decision = convergence.update(metrics, survivor_names)
            if decision.should_stop:
                bus.emit("convergence", "pipeline",
                         round=round_num, reason=decision.reason)
                break

        # Collision: fuse survivors into hybrids for next round
        if round_survivors:
            # Convert survivors to GTMIdea-like objects for fusion
            from ..v3.proposer import GTMIdea
            gtm_ideas = []
            for s in round_survivors:
                gtm_ideas.append(GTMIdea(
                    name=s.get("name", "unknown"),
                    formula=s.get("formula", ""),
                    falsifier=s.get("falsifier", ""),
                    closest_known_archetype=s.get("closest_known_archetype"),
                    mechanism_family=s.get("mechanism_family", ""),
                    owner_dept=s.get("owner_dept", "strategy"),
                    brief_keywords=[],
                ))
            hybrids = fuse_survivors(gtm_ideas, n_hybrids=3)
            for h in hybrids:
                all_hybrids.append({
                    "name": h.name,
                    "formula": h.formula,
                    "composite_z": 0.0,
                    "parent_names": h.parent_names,
                })

    # ── dedupe survivors ────────────────────────────────────────────
    by_name: dict[str, dict[str, Any]] = {}
    for s in all_survivors:
        name = s.get("name", "")
        z = s.get("composite_z_median", s.get("composite_z", 0.0))
        if name not in by_name or z > by_name[name].get("composite_z_median", 0.0):
            by_name[name] = s
    deduped_survivors = sorted(by_name.values(), key=lambda s: -s.get("composite_z_median", s.get("composite_z", 0.0)))

    # ── memory OS write-back ────────────────────────────────────────
    memory_ids: list[str] = []
    if write_memory_os:
        try:
            loop = ResilientMemoryLoop()
            cycle_result = loop.run_cycle(brief=brief, max_ideas=n_ideas)
            memory_ids = cycle_result.get("memory_ids_written", [])
            bus.emit("memory_write", "pipeline", count=len(memory_ids))
        except Exception as exc:
            bus.emit("memory_error", "pipeline", error=str(exc))

    # ── finish ──────────────────────────────────────────────────────
    collector.stop()
    dashboard.stop()
    elapsed = time.monotonic() - t0

    result: dict[str, Any] = {
        "brief": brief,
        "corpus_size": len(corpus),
        "ideas_proposed": n_ideas,
        "n_seeds": len(seeds),
        "seeds": seeds,
        "survivors": deduped_survivors,
        "dropped": all_dropped,
        "hybrids": all_hybrids,
        "convergence_round": len(collector.rounds),
        "n_rounds": len(collector.rounds),
        "n_packets": total_packets,
        "memory_ids_written": memory_ids,
        "telemetry_events": len(bus.get_events()),
        "wall_clock_s": elapsed,
    }

    # ── write output ────────────────────────────────────────────────
    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "data.json").write_text(json.dumps(result, indent=2, default=str))
        (out / "REPORT.md").write_text(render_v5_report(result))

    if show_dashboard:
        print(dashboard.render())

    return result


# ────────────────────────────────────────────────────────────────────
# Report renderer
# ────────────────────────────────────────────────────────────────────


def render_v5_report(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Deviatrix Genesis v5 — Run Report\n")
    lines.append(f"**Brief:** {result['brief']}\n")
    lines.append(f"**Corpus size:** {result['corpus_size']} entries\n")
    lines.append(f"**Ideas proposed:** {result['ideas_proposed']}\n")
    lines.append(f"**Seeds:** {result['seeds']}\n")
    lines.append(f"**Rounds run:** {result['n_rounds']}\n")
    lines.append(f"**Total packets:** {result['n_packets']}\n")
    lines.append(f"**Wall-clock:** {result['wall_clock_s']:.2f}s\n")
    lines.append(f"**Telemetry events:** {result['telemetry_events']}\n")

    survivors = result.get("survivors", [])
    lines.append(f"\n## Survivors ({len(survivors)})\n")
    for s in survivors:
        name = s.get("name", "unknown")
        z = s.get("composite_z_median", s.get("composite_z", 0.0))
        lines.append(f"  * **{name}** — composite_z = {z:.2f}")

    hybrids = result.get("hybrids", [])
    if hybrids:
        lines.append(f"\n## Hybrids ({len(hybrids)})\n")
        for h in hybrids:
            lines.append(f"  * {h.get('name', 'unknown')} — parents: {h.get('parent_names', [])}")

    memory_ids = result.get("memory_ids_written", [])
    if memory_ids:
        lines.append(f"\n## Memory OS writes ({len(memory_ids)})\n")
        for mid in memory_ids:
            lines.append(f"  * {mid}")

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description="Deviatrix v5 pipeline")
    p.add_argument("--brief", default="Operator-first GTM with financial primitives")
    p.add_argument("--n-ideas", type=int, default=9)
    p.add_argument("--max-rounds", type=int, default=10)
    p.add_argument("--seeds", default="2026,2043")
    p.add_argument("--write-memory-os", action="store_true")
    p.add_argument("--out", default=None)
    p.add_argument("--dashboard", action="store_true")
    args = p.parse_args()

    seeds = [int(s) for s in args.seeds.split(",")]
    result = run_v5_pipeline(
        brief=args.brief,
        n_ideas=args.n_ideas,
        max_rounds=args.max_rounds,
        seeds=seeds,
        write_memory_os=args.write_memory_os,
        out_dir=args.out,
        show_dashboard=args.dashboard,
    )
    print(render_v5_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
