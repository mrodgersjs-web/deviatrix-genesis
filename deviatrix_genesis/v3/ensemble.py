"""Multi-seed ensemble.

v2 ran with one seed; if the population's RNG happened to land on
a particular shape, the verdict was lucky. v3 runs N seeds and
takes the median z across them; variance > 1σ is a verifier flag
(the candidate's deviation isn't robust to seed noise).

This is the doctrine's "Pass C" applied at the *run* level, not just
the per-packet level.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from ..rig_gtm_run_v2 import IDEAS_V2 as _V2_IDEAS
from .collision import fuse_survivors
from .corpus_loader import (
    build_known_archetype_population,
    build_reference_population,
    load_corpus,
)
from .proposer import GTMIdea, propose_from_brief

__all__ = ["EnsembleResult", "run_ensemble"]


@dataclass
class EnsembleResult:
    """The aggregate of N seeded runs."""

    brief: str
    ideas: list[dict[str, Any]]  # per-idea aggregate
    survivors: list[dict[str, Any]]
    dropped: list[dict[str, Any]]
    hybrids: list[dict[str, Any]]
    n_seeds: int
    seeds: list[int]
    verifier_summary: dict[str, Any]
    notes: str = ""


def run_ensemble(
    brief: str = "RIG GTM: operator-first, doctrine-published, financially primitive, structurally novel",
    *,
    n_seeds: int = 5,
    seeds: list[int] | None = None,
    n_hybrids: int = 3,
    corpus: list | None = None,
    use_collision: bool = True,
) -> EnsembleResult:
    """Run the v3 pipeline with N seeds and aggregate."""

    seeds = seeds or [2026 + i * 17 for i in range(n_seeds)]

    if corpus is None:
        corpus = load_corpus()

    # Use the v2 IDEAS_V2 (the calibrated 9 ideas); the proposer's
    # brief-driven scoring is layered on top via per-idea override.
    ideas = list(_V2_IDEAS)
    proposer_ideas = propose_from_brief(brief, corpus=corpus, n=len(ideas))

    # Override the v2 hand-tuned scores with the proposer's
    # corpus-derived scores (the brief-driven path).
    by_name = {p.name.split(" — ")[0]: p for p in proposer_ideas}
    for idea in ideas:
        for prefix in by_name:
            if prefix in idea.name:
                p = by_name[prefix]
                idea.anti_orthodoxy_new = p.anti_orthodoxy_new
                idea.mechanism_originality_new = p.mechanism_originality_new
                idea.prior_art_distance_new = p.prior_art_distance_new
                break

    # Aggregate per-seed results
    per_seed_results: list[dict[str, Any]] = []
    for seed in seeds:
        per_seed_results.append(_run_one_seed(ideas, seed, corpus))

    # Aggregate per-idea
    idea_names = {i.name for i in ideas}
    aggregate = []
    for name in idea_names:
        per_seed = [
            idea
            for r in per_seed_results
            for idea in r["all_ideas"]
            if idea["name"] == name
        ]
        if not per_seed:
            continue
        zs = [s["composite_z"] for s in per_seed]
        median_z = statistics.median(zs)
        variance = statistics.pstdev(zs) if len(zs) > 1 else 0.0
        archetype_zs = [s["archetype_z"] for s in per_seed]
        median_archetype_z = statistics.median(archetype_zs)
        is_respin = all(s["is_respin_of_known"] for s in per_seed)
        wall_breach_count = sum(1 for s in per_seed if s.get("wall_breach", False))
        aggregate.append(
            {
                "name": name,
                "composite_z_median": median_z,
                "composite_z_variance": variance,
                "composite_z_seeds": zs,
                "archetype_z_median": median_archetype_z,
                "is_respin_of_known": is_respin,
                "high_variance_flag": variance > 1.0,
                "wall_breach_count": wall_breach_count,
            }
        )

    # Survivors and dropped
    survivors = sorted(
        [a for a in aggregate if not a["is_respin_of_known"] and not a["high_variance_flag"]],
        key=lambda a: -a["composite_z_median"],
    )
    dropped = [a for a in aggregate if a["is_respin_of_known"] or a["high_variance_flag"]]

    # Collision Engine: fuse the top survivors
    hybrids: list[dict[str, Any]] = []
    if use_collision:
        # Reconstruct GTMIdea objects from the survivors' first-seed data
        survivor_ideas: list[GTMIdea] = []
        survivor_names = {s["name"] for s in survivors}
        survivor_lookup = {s["name"]: s for s in survivors}
        for idea in ideas:
            if idea.name in survivor_names:
                survivor_ideas.append(idea)
        fused = fuse_survivors(survivor_ideas, n_hybrids=n_hybrids)
        hybrids = [
            {
                "name": h.name,
                "parents": h.parents,
                "parent_families": h.parent_families,
                "newness": {
                    "anti_orthodoxy": h.anti_orthodoxy_new,
                    "mechanism_originality": h.mechanism_originality_new,
                    "prior_art_distance": h.prior_art_distance_new,
                },
            }
            for h in fused
        ]

    return EnsembleResult(
        brief=brief,
        ideas=aggregate,
        survivors=survivors,
        dropped=dropped,
        hybrids=hybrids,
        n_seeds=len(seeds),
        seeds=seeds,
        verifier_summary={},
        notes=(
            f"v3 ensemble over {len(seeds)} seeds, "
            f"{len(survivors)} survivors, {len(dropped)} dropped, "
            f"{len(hybrids)} hybrids from Collision Engine"
        ),
    )


def _run_one_seed(
    ideas: list,
    seed: int,
    corpus: list,
) -> dict[str, Any]:
    """Run v2 with a custom seed and population."""
    from ..rig_gtm_run_v2 import run_v2

    pop = build_reference_population(corpus, seed=seed)
    alt_pop = build_known_archetype_population(corpus, seed=seed)

    # Inject the populations by monkey-patching the v2 module
    import deviatrix_genesis.rig_gtm_run_v2 as v2_mod
    orig_pop_factory = v2_mod.known_population
    orig_alt_factory = v2_mod.archetype_only_population
    v2_mod.known_population = lambda *a, **kw: pop
    v2_mod.archetype_only_population = lambda *a, **kw: alt_pop

    try:
        report = run_v2(seed=seed)
    finally:
        v2_mod.known_population = orig_pop_factory
        v2_mod.archetype_only_population = orig_alt_factory

    return report
