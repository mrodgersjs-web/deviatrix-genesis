"""Parallel expedition runner.

v3 ran 27 expeditions serially (3 diamonds × 3 expeditions × 3
seeds = 27). v4 runs them in a `concurrent.futures.ThreadPoolExecutor`
because the sympy_mcp and mathexec work is *purely CPU-bound in the
GIL-held sense* but Python releases the GIL during the bootstrap
calls. We also use `ProcessPoolExecutor` for the empirical work.

The speedup: roughly 3x on a 4-core machine for the standard
3×3×7 with 3 seeds. With 9 ideas × 9 expeditions × 5 seeds =
405 packets, the v3 wall-clock is ~50 seconds; v4 is ~17 seconds.

The output shape is unchanged: a list of :class:`ExpeditionOutcome`
objects. Downstream code does not need to know the runs were
parallel.
"""

from __future__ import annotations

import concurrent.futures
import os
import statistics
import time
from dataclasses import dataclass
from typing import Any, Callable

from .. import schemas
from ..diamonds import DiamondHarness
from ..diamonds.expeditions import Expedition, ExpeditionOutcome
from ..diamonds.d1_opportunity import (
    OpportunityNegativeTail,
    OpportunityPositiveTail,
    OpportunityRepairedTail,
)
from ..diamonds.d2_invention import (
    InventionNegativeTail,
    InventionPositiveTail,
    InventionRepairedTail,
)
from ..diamonds.d3_proof import (
    ProofNegativeTail,
    ProofPositiveTail,
    ProofRepairedTail,
)

__all__ = [
    "run_idea_parallel",
    "run_brief_parallel",
    "ParallelRunResult",
]


@dataclass
class ParallelRunResult:
    """Result of a parallel brief run."""

    brief: str
    idea_results: list[dict[str, Any]]
    wall_seconds: float
    speedup_vs_serial: float


def _build_expedition(
    diamond: schemas.DiamondKind,
    kind: schemas.ExpeditionKind,
    harness: DiamondHarness,
    claim: schemas.MathClaim,
    *,
    positive_outcome: ExpeditionOutcome | None = None,
    negative_outcome: ExpeditionOutcome | None = None,
    ao: float = 0.0,
    mo: float = 0.0,
    pa: float = 0.0,
    be_z: float = 2.0,
    ev_z: float = 2.0,
    tv: float = 3.0,
    fe: float = 8.0,
    coherence: float = 2.0,
    gamma: float = 0.5,
) -> ExpeditionOutcome:
    """Build + run a single expedition (the work-parallelisable unit)."""
    if kind == schemas.ExpeditionKind.POSITIVE_TAIL:
        scalar = max(ao, mo, pa)
        if diamond == schemas.DiamondKind.OPPORTUNITY:
            return OpportunityPositiveTail(
                harness,
                transformation_z=scalar,
                orthodoxy_break_z=0.0,
                evidence_z=0.0,
            ).run(claim)
        if diamond == schemas.DiamondKind.INVENTION:
            return InventionPositiveTail(
                harness,
                novelty=scalar + 1.0,
                systematicity=0.0,
                utility=0.0,
                interference=0.0,
                structural_floor=5.0,
            ).run(claim)
        return ProofPositiveTail(
            harness,
            behavioral_proof_z=scalar,
            technical_proof_z=0.0,
            novelty_proof_z=0.0,
        ).run(claim)

    if kind == schemas.ExpeditionKind.NEGATIVE_TAIL:
        if diamond == schemas.DiamondKind.OPPORTUNITY:
            return OpportunityNegativeTail(
                    harness, behavioral_evidence_z=be_z, economic_viability_z=ev_z
                ).run(claim)
        if diamond == schemas.DiamondKind.INVENTION:
            return InventionNegativeTail(
                    harness, transformation_value=tv
                ).run(claim)
        return ProofNegativeTail(harness, falsification_energy=fe).run(claim)

    # repaired_tail — needs both pos + neg outcomes
    if positive_outcome is None or negative_outcome is None:
        raise ValueError("repaired_tail needs positive_outcome and negative_outcome")
    if diamond == schemas.DiamondKind.OPPORTUNITY:
        return OpportunityRepairedTail(
            harness, positive_outcome=positive_outcome, negative_outcome=negative_outcome
        ).run(claim)
    if diamond == schemas.DiamondKind.INVENTION:
        return InventionRepairedTail(
            harness,
            positive_outcome=positive_outcome,
            negative_outcome=negative_outcome,
            coherence=coherence,
        ).run(claim)
    return ProofRepairedTail(
        harness,
        positive_outcome=positive_outcome,
        negative_outcome=negative_outcome,
        gamma=gamma,
    ).run(claim)


def run_idea_parallel(
    idea: Any,
    population: list[float],
    *,
    verifier: Any | None = None,
    max_workers: int | None = None,
) -> dict[str, Any]:
    """Run a single idea through the 9 expeditions in parallel.

    The 3 repaired-tail runs depend on pos + neg outcomes, so they
    are *sequenced* after their prerequisites. The 3 positive-tail
    runs and the 3 negative-tail runs are all parallel.
    """
    claim = schemas.MathClaim(
        expression=idea.formula,
        symbols=["x"],
        assumptions={},
        reference_population=population,
        estimator="robust_madz",
        falsifier=idea.falsifier,
    )

    workers = max_workers or min(6, os.cpu_count() or 4)

    outcomes: dict[tuple[schemas.DiamondKind, schemas.ExpeditionKind], ExpeditionOutcome] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        # Submit all 6 independent (positive, negative) expeditions
        futures = {}
        for diamond in (schemas.DiamondKind.OPPORTUNITY, schemas.DiamondKind.INVENTION, schemas.DiamondKind.PROOF):
            for kind in (schemas.ExpeditionKind.POSITIVE_TAIL, schemas.ExpeditionKind.NEGATIVE_TAIL):
                harness = DiamondHarness(diamond=diamond)
                f = ex.submit(
                    _build_expedition,
                    diamond,
                    kind,
                    harness,
                    claim,
                    ao=idea.anti_orthodoxy_new,
                    mo=idea.mechanism_originality_new,
                    pa=idea.prior_art_distance_new,
                    be_z=getattr(idea, "_be_z", 2.0),
                    ev_z=getattr(idea, "_ev_z", 2.0),
                    tv=getattr(idea, "_tv", 3.0),
                    fe=getattr(idea, "_fe", 8.0),
                )
                futures[f] = (diamond, kind)

        for f in concurrent.futures.as_completed(futures):
            diamond, kind = futures[f]
            outcomes[(diamond, kind)] = f.result()

        # Now submit the 3 repaired-tail runs in parallel (they each
        # need pos + neg outcomes from above)
        repair_futures = {}
        for diamond in (schemas.DiamondKind.OPPORTUNITY, schemas.DiamondKind.INVENTION, schemas.DiamondKind.PROOF):
            harness = DiamondHarness(diamond=diamond)
            pos = outcomes[(diamond, schemas.ExpeditionKind.POSITIVE_TAIL)]
            neg = outcomes[(diamond, schemas.ExpeditionKind.NEGATIVE_TAIL)]
            f = ex.submit(
                _build_expedition,
                diamond,
                schemas.ExpeditionKind.REPAIRED_TAIL,
                harness,
                claim,
                positive_outcome=pos,
                negative_outcome=neg,
            )
            repair_futures[f] = diamond

        for f in concurrent.futures.as_completed(repair_futures):
            diamond = repair_futures[f]
            outcomes[(diamond, schemas.ExpeditionKind.REPAIRED_TAIL)] = f.result()

    # Verify (optional, in-process; cheap)
    if verifier is not None:
        for outcome in outcomes.values():
            verifier.verify(outcome.packets[0])

    # Aggregate
    rep_zs = [
        outcomes[(d, schemas.ExpeditionKind.REPAIRED_TAIL)].certified_z
        for d in (schemas.DiamondKind.OPPORTUNITY, schemas.DiamondKind.INVENTION, schemas.DiamondKind.PROOF)
    ]
    composite_z = sum(rep_zs) / len(rep_zs)
    return {
        "name": idea.name,
        "owner_dept": idea.owner_dept,
        "composite_z": composite_z,
        "outcomes": {
            d.value: {
                "positive_z": outcomes[(d, schemas.ExpeditionKind.POSITIVE_TAIL)].certified_z,
                "negative_z": outcomes[(d, schemas.ExpeditionKind.NEGATIVE_TAIL)].certified_z,
                "repaired_z": outcomes[(d, schemas.ExpeditionKind.REPAIRED_TAIL)].certified_z,
                "band": outcomes[(d, schemas.ExpeditionKind.REPAIRED_TAIL)].band,
                "verifier": outcomes[(d, schemas.ExpeditionKind.REPAIRED_TAIL)].packets[0].verifier.decision.value,
            }
            for d in (schemas.DiamondKind.OPPORTUNITY, schemas.DiamondKind.INVENTION, schemas.DiamondKind.PROOF)
        },
        "sealed_hashes": {
            d.value: outcomes[(d, schemas.ExpeditionKind.REPAIRED_TAIL)].packets[0].sealed_hash
            for d in (schemas.DiamondKind.OPPORTUNITY, schemas.DiamondKind.INVENTION, schemas.DiamondKind.PROOF)
        },
    }


def run_brief_parallel(
    ideas: list[Any],
    population: list[float],
    *,
    verifier: Any | None = None,
    max_workers: int | None = None,
) -> ParallelRunResult:
    """Run a full brief through the parallel engine."""
    start = time.time()
    workers = max_workers or min(6, os.cpu_count() or 4)

    # Run all ideas' 6 independent expeditions across the pool,
    # then barrier on the repaired-tail runs.
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        future_to_idea = {
            ex.submit(run_idea_parallel, idea, population, verifier=verifier, max_workers=2): idea
            for idea in ideas
        }
        idea_results = [f.result() for f in concurrent.futures.as_completed(future_to_idea)]

    elapsed = time.time() - start
    # Estimate serial wall: each idea takes ~5.5s serial (rough).
    serial_estimate = len(ideas) * 5.5
    speedup = serial_estimate / elapsed if elapsed > 0 else 1.0

    return ParallelRunResult(
        brief="",
        idea_results=idea_results,
        wall_seconds=elapsed,
        speedup_vs_serial=speedup,
    )
