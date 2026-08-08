"""Iterative proposer — runs the brief in rounds until convergence.

v3 runs the conductor once. v4 runs it in *rounds*:

  1. Round 1: emitter produces N candidates, run the parallel
     conductor, get survivors.
  2. Round 2: each survivor is fed back into the emitter as a
     *seed primitive*. The emitter composes new candidates that
     combine survivors with primitives the survivor doesn't
     contain.
  3. Repeat until no new survivors emerge or N rounds is hit.

The convergence condition is: when the survivor set is identical
(or nearly so) between rounds, the system has extracted all the
novel ideas the corpus can support. Stop.

Output: every survivor from every round, deduplicated, ranked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..v3.collision import fuse_survivors, HybridIdea
from ..v3.proposer import GTMIdea
from .formula_emitter import EmittedFormula, PRIMITIVE_VOCAB, emit_formulas
from .parallel import run_idea_parallel

__all__ = ["IterativeResult", "run_iterative"]


@dataclass
class IterativeResult:
    """Result of an iterative brief run."""

    brief: str
    rounds: list[dict[str, Any]]
    survivors: list[dict[str, Any]]
    converged: bool
    n_rounds_run: int


def _emit_to_gtm_idea(emit: EmittedFormula) -> GTMIdea:
    """Convert an EmittedFormula to a v3-compatible GTMIdea."""
    return GTMIdea(
        name=emit.name,
        formula=emit.formula,
        falsifier=emit.falsifier,
        closest_known_archetype=None,
        anti_orthodoxy_new=emit.anti_orthodoxy_new,
        mechanism_originality_new=emit.mechanism_originality_new,
        prior_art_distance_new=emit.prior_art_distance_new,
        owner_dept=emit.owner_dept,
        action_90d=emit.action_90d,
        mechanism_family=emit.mechanism_family,
    )


def _seed_corpus_newness(
    survivors: list[dict[str, Any]],
    prim_vocab: list[dict[str, str]],
) -> dict[str, tuple[float, float, float]]:
    """Convert survivor newness scores to a primitive-name → scores mapping.

    Each survivor is mapped to its dominant primitive (from its
    name); the survivor's composite_z becomes the primitive's
    mechanism_originality; archetype_z becomes anti_orthodoxy.
    """
    out: dict[str, tuple[float, float, float]] = {}
    for surv in survivors:
        name = surv["name"].lower()
        # Map to the first primitive whose name appears in the survivor's name
        for prim in prim_vocab:
            if prim["name"].replace("_", "-") in name:
                ao = float(surv.get("archetype_z_median", surv.get("archetype_z", 4.5)))
                mo = float(surv.get("composite_z_median", surv.get("composite_z", 4.5)))
                pa = ao  # proxy
                out[prim["name"]] = (ao, mo, pa)
                break
    return out


def run_iterative(
    brief: str,
    *,
    population: list[float],
    verifier: Any | None = None,
    n_per_round: int = 9,
    n_rounds: int = 4,
    convergence_tolerance: float = 0.1,
    corpus_newness: dict[str, tuple[float, float, float]] | None = None,
    seed: int = 2026,
) -> IterativeResult:
    """Run the brief iteratively. Stops when survivors converge."""
    history: list[dict[str, Any]] = []
    survivor_names_by_round: list[set[str]] = []
    all_survivors: list[dict[str, Any]] = []

    for round_idx in range(n_rounds):
        # Emit n candidates
        if round_idx == 0 and corpus_newness is None:
            emits = emit_formulas(brief, n=n_per_round, seed=seed + round_idx)
            ideas = [_emit_to_gtm_idea(e) for e in emits]
        else:
            seed_newness = corpus_newness or _seed_corpus_newness(all_survivors, PRIMITIVE_VOCAB)
            emits = emit_formulas(brief, n=n_per_round, corpus_newness=seed_newness, seed=seed + round_idx)
            ideas = [_emit_to_gtm_idea(e) for e in emits]

        # Run the parallel conductor
        round_survivors: list[dict[str, Any]] = []
        for idea in ideas:
            res = run_idea_parallel(idea, population, verifier=verifier)
            if res["composite_z"] > 0.0:  # threshold for "survivor" — anything above median
                round_survivors.append(res)
        round_survivors.sort(key=lambda r: -r["composite_z"])
        history.append(
            {
                "round": round_idx,
                "candidates": [i.name for i in ideas],
                "survivors": [s["name"] for s in round_survivors],
                "composite_z": [s["composite_z"] for s in round_survivors],
            }
        )
        survivor_names = {s["name"] for s in round_survivors}
        survivor_names_by_round.append(survivor_names)
        all_survivors.extend(round_survivors)

        # Check convergence: survivor-set overlap with prior round
        if round_idx > 0:
            prev = survivor_names_by_round[-2]
            jaccard = (
                len(prev & survivor_names) / len(prev | survivor_names)
                if (prev | survivor_names) else 1.0
            )
            if jaccard > 1.0 - convergence_tolerance:
                # converged — survivor set is stable
                return IterativeResult(
                    brief=brief,
                    rounds=history,
                    survivors=_dedupe_survivors(all_survivors),
                    converged=True,
                    n_rounds_run=round_idx + 1,
                )

    return IterativeResult(
        brief=brief,
        rounds=history,
        survivors=_dedupe_survivors(all_survivors),
        converged=False,
        n_rounds_run=n_rounds,
    )


def _dedupe_survivors(survivors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe by name, keeping the highest composite_z."""
    by_name: dict[str, dict[str, Any]] = {}
    for s in survivors:
        n = s["name"]
        if n not in by_name or s["composite_z"] > by_name[n]["composite_z"]:
            by_name[n] = s
    return sorted(by_name.values(), key=lambda r: -r["composite_z"])
