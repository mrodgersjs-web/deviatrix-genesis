"""v5 pipeline — the 1000x-over-v4 orchestrator.

Ties together:
  * Async DAG executor for parallel expeditions (diamonds × seeds fan-out)
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
import statistics
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
# Async expedition runner — the real parallelism
# ────────────────────────────────────────────────────────────────────


async def _run_one_diamond_async(
    diamond_kind: str,
    formula: str,
    seed: int,
    pop_size: int,
    profiles: dict[str, Any],
    bus: EventBus,
) -> dict[str, Any]:
    """Run one diamond (pos + neg parallel, then repaired) asynchronously."""
    from .. import schemas
    from ..conductors import DeviatrixConductor

    t0 = time.monotonic()
    conductor = DeviatrixConductor(seed=seed, profiles=profiles)

    # Build claim + population
    import random
    rng = random.Random((seed * 1_000_003) ^ pop_size)
    population = [rng.gauss(0, 1) for _ in range(pop_size)]

    dk = schemas.DiamondKind(diamond_kind)
    claim = conductor.claim_factory(formula, dk)
    claim.reference_population = population
    claim.candidate_hash = claim._hash()

    from ..diamonds import DiamondHarness
    harness = DiamondHarness(diamond=dk)

    # Run positive + negative in parallel via asyncio.to_thread
    pos_exp = conductor._positive_expedition(harness, dk)
    neg_exp = conductor._negative_expedition(harness, dk)
    pos_task = asyncio.to_thread(pos_exp.run, claim)
    neg_task = asyncio.to_thread(neg_exp.run, claim)

    # Emit telemetry
    bus.emit("diamond_start", "pipeline", diamond=diamond_kind, seed=seed)

    pos_outcome, neg_outcome = await asyncio.gather(pos_task, neg_task)

    bus.emit("expedition_complete", "pipeline",
             diamond=diamond_kind, kind="positive", seed=seed)
    bus.emit("expedition_complete", "pipeline",
             diamond=diamond_kind, kind="negative", seed=seed)

    # Repaired depends on both outcomes — run after they complete
    rep_exp = conductor._repaired_expedition(
        harness, dk, pos_outcome=pos_outcome, neg_outcome=neg_outcome
    )
    rep_outcome = await asyncio.to_thread(rep_exp.run, claim)

    bus.emit("expedition_complete", "pipeline",
             diamond=diamond_kind, kind="repaired", seed=seed)
    bus.emit("diamond_complete", "pipeline",
             diamond=diamond_kind, seed=seed,
             wall_ms=(time.monotonic() - t0) * 1000)

    return {
        "diamond": diamond_kind,
        "seed": seed,
        "outcomes": {
            "positive_tail": pos_outcome,
            "negative_tail": neg_outcome,
            "repaired_tail": rep_outcome,
        },
        "wall_ms": (time.monotonic() - t0) * 1000,
    }


async def _run_all_diamonds_async(
    formula: str,
    seeds: list[int],
    pop_size: int,
    profiles: dict[str, Any],
    bus: EventBus,
) -> list[dict[str, Any]]:
    """Run all 3 diamonds × N seeds in parallel using asyncio."""
    diamonds = ["opportunity", "invention", "proof"]
    tasks = [
        _run_one_diamond_async(dk, formula, seed, pop_size, profiles, bus)
        for seed in seeds
        for dk in diamonds
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    outcomes: list[dict[str, Any]] = []
    for r in results:
        if isinstance(r, BaseException):
            bus.emit("diamond_error", "pipeline", error=str(r))
        else:
            outcomes.append(r)
    return outcomes


# ────────────────────────────────────────────────────────────────────
# Survivors extraction from async results
# ────────────────────────────────────────────────────────────────────


def _extract_survivors(
    diamond_results: list[dict[str, Any]],
    verifier: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract survivors and dropped from diamond results."""
    from ..diamonds.routing import action_for, band_for, is_wall

    survivors: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []

    for dr in diamond_results:
        dk = dr["diamond"]
        seed = dr["seed"]
        for kind, outcome in dr["outcomes"].items():
            z = outcome.certified_z
            entry = {
                "name": f"{dk}_{kind}_s{seed}",
                "diamond": dk,
                "expedition": kind,
                "seed": seed,
                "composite_z": z,
                "composite_z_median": z,
                "band": band_for(z),
                "action": action_for(z),
                "formula": outcome.packets[0].symbolic.simplified_expression if outcome.packets else "",
                "wall_breach": is_wall(z),
            }

            # Verify
            if outcome.packets:
                report = verifier.verify(outcome.packets[0])
                entry["verifier_decision"] = report.decision.value
                entry["verifier_reason"] = report.reason

                if report.decision.value == "PASS" and not is_wall(z):
                    survivors.append(entry)
                else:
                    dropped.append(entry)
            else:
                dropped.append(entry)

    return survivors, dropped


# ────────────────────────────────────────────────────────────────────
# Core pipeline
# ────────────────────────────────────────────────────────────────────


def run_v5_pipeline(
    brief: str,
    n_ideas: int = 9,
    max_rounds: int = 10,
    seeds: list[int] | None = None,
    pop_size: int = 500,
    write_memory_os: bool = False,
    out_dir: str | Path | None = None,
    show_dashboard: bool = False,
) -> dict[str, Any]:
    """Run the v5 pipeline end-to-end with real async parallelism.

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
    from ..v3.collision import fuse_survivors
    from ..verifier import IndependentVerifier

    corpus = load_corpus()
    bus.emit("corpus_loaded", "pipeline", count=len(corpus))

    verifier = IndependentVerifier(verifier_id="v5-verifier")

    # ── iterative rounds ────────────────────────────────────────────
    all_survivors: list[dict[str, Any]] = []
    all_dropped: list[dict[str, Any]] = []
    all_hybrids: list[dict[str, Any]] = []
    total_packets = 0

    # Profiles from conductor defaults
    from ..conductors import DEFAULT_PROFILES
    profiles = DEFAULT_PROFILES

    for round_num in range(1, max_rounds + 1):
        bus.emit("round_start", "pipeline", round=round_num)

        # Propose ideas from brief
        ideas = propose_from_brief(brief, corpus=corpus, n=n_ideas)
        bus.emit("ideas_proposed", "pipeline", round=round_num, count=len(ideas))

        # Run all diamonds × seeds in parallel via asyncio
        formula = ideas[0].formula if ideas else "x**2 + x"
        diamond_results = asyncio.run(
            _run_all_diamonds_async(formula, seeds, pop_size, profiles, bus)
        )

        # Extract survivors
        round_survivors, round_dropped = _extract_survivors(diamond_results, verifier)
        total_packets += sum(len(dr["outcomes"]) for dr in diamond_results)

        survivor_names = {s["name"] for s in round_survivors}
        all_survivors.extend(round_survivors)
        all_dropped.extend(round_dropped)

        # Round metrics
        z_values = [s["composite_z"] for s in round_survivors]
        median_z = statistics.median(z_values) if z_values else 0.0
        max_z = max(z_values) if z_values else 0.0

        bus.emit("round_end", "pipeline",
                 round=round_num,
                 survivors_count=len(round_survivors),
                 median_z=median_z, max_z=max_z,
                 wall_ms=(time.monotonic() - t0) * 1000)

        # Convergence check
        if collector.rounds:
            decision = convergence.update(collector.rounds[-1], survivor_names)
            if decision.should_stop:
                bus.emit("convergence", "pipeline",
                         round=round_num, reason=decision.reason)
                break

        # Collision: fuse survivors into hybrids for next round
        if round_survivors:
            from ..v3.proposer import GTMIdea
            gtm_ideas = [
                GTMIdea(
                    name=s["name"],
                    formula=s.get("formula", ""),
                    falsifier="",
                    closest_known_archetype=None,
                    mechanism_family=s.get("mechanism_family", ""),
                    owner_dept="strategy",
                    brief_keywords=[],
                )
                for s in round_survivors
            ]
            hybrids = fuse_survivors(gtm_ideas, n_hybrids=3)
            for h in hybrids:
                all_hybrids.append({
                    "name": h.name, "formula": h.formula,
                    "composite_z": 0.0, "parent_names": h.parent_names,
                })

    # ── dedupe survivors ────────────────────────────────────────────
    by_name: dict[str, dict[str, Any]] = {}
    for s in all_survivors:
        name = s["name"]
        z = s.get("composite_z_median", s.get("composite_z", 0.0))
        if name not in by_name or z > by_name[name].get("composite_z_median", 0.0):
            by_name[name] = s
    deduped = sorted(by_name.values(), key=lambda s: -s.get("composite_z_median", 0.0))

    # ── memory OS write-back ────────────────────────────────────────
    memory_ids: list[str] = []
    if write_memory_os:
        try:
            loop = ResilientMemoryLoop()
            cycle = loop.run_cycle(brief=brief, max_ideas=n_ideas)
            memory_ids = cycle.get("memory_ids_written", [])
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
        "survivors": deduped,
        "dropped": all_dropped,
        "hybrids": all_hybrids,
        "convergence_round": len(collector.rounds),
        "n_rounds": len(collector.rounds),
        "n_packets": total_packets,
        "memory_ids_written": memory_ids,
        "telemetry_events": len(bus.get_events()),
        "wall_clock_s": elapsed,
    }

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
