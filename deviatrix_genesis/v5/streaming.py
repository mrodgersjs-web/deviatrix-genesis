"""Streaming pipeline — yields results as expeditions complete.

Instead of waiting for the full pipeline to finish, callers can
iterate over results in real-time as each diamond completes.

Usage::

    from deviatrix_genesis.v5.streaming import stream_pipeline

    for event in stream_pipeline(brief="GTM strategy"):
        if event["type"] == "diamond_complete":
            print(f"{event['diamond']}: z={event['best_z']:.2f}")
        elif event["type"] == "round_end":
            print(f"Round {event['round']}: {event['survivors']} survivors")
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Generator

__all__ = ["stream_pipeline"]


def stream_pipeline(
    brief: str,
    n_ideas: int = 3,
    max_rounds: int = 3,
    seeds: list[int] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Stream pipeline results as they complete.

    Yields dicts with 'type' key: round_start, idea_scored,
    diamond_complete, round_end, convergence, done.
    """
    if seeds is None:
        seeds = [2026]

    from ..v3.corpus_loader import load_corpus
    from ..v3.proposer import propose_from_brief
    from ..v4.formula_emitter import emit_formulas
    from ..v4.embeddings import build_embedding_index, score_with_embeddings
    from ..verifier import IndependentVerifier
    from .telemetry import EventBus

    bus = EventBus()
    corpus = load_corpus()
    corpus_texts = [e.text for e in corpus]
    embedding_index = build_embedding_index(corpus_texts)
    verifier = IndependentVerifier(verifier_id="stream-verifier")

    yield {"type": "corpus_loaded", "count": len(corpus)}

    for round_num in range(1, max_rounds + 1):
        yield {"type": "round_start", "round": round_num}

        # Emit formulas
        emitted = emit_formulas(brief, n=n_ideas)
        for ef in emitted:
            idea_text = f"{ef.name} {ef.formula}"
            scores = score_with_embeddings(idea_text, embedding_index)
            yield {
                "type": "idea_scored",
                "name": ef.name,
                "formula": ef.formula,
                "anti_orthodoxy": scores.anti_orthodoxy,
                "mechanism_originality": scores.mechanism_originality,
            }

        # Run diamonds — yield each as it completes
        from ..conductors import DeviatrixConductor, DEFAULT_PROFILES
        from .. import schemas

        formula = emitted[0].formula if emitted else "x**2 + x"
        seed = seeds[0]

        for dk in ["opportunity", "invention", "proof"]:
            t0 = time.monotonic()
            conductor = DeviatrixConductor(seed=seed, profiles=DEFAULT_PROFILES)
            import random
            rng = random.Random((seed * 1_000_003) ^ 500)
            population = [rng.gauss(0, 1) for _ in range(500)]

            diamond_kind = schemas.DiamondKind(dk)
            claim = conductor.claim_factory(formula, diamond_kind)
            claim.reference_population = population
            claim.candidate_hash = claim._hash()

            from ..diamonds import DiamondHarness
            harness = DiamondHarness(diamond=diamond_kind)

            # Positive
            pos_exp = conductor._positive_expedition(harness, diamond_kind)
            pos_outcome = pos_exp.run(claim)

            # Negative
            neg_exp = conductor._negative_expedition(harness, diamond_kind)
            neg_outcome = neg_exp.run(claim)

            # Repaired
            rep_exp = conductor._repaired_expedition(
                harness, diamond_kind, pos_outcome=pos_outcome, neg_outcome=neg_outcome
            )
            rep_outcome = rep_exp.run(claim)

            best_z = max(
                pos_outcome.certified_z, neg_outcome.certified_z, rep_outcome.certified_z,
                key=abs,
            )

            yield {
                "type": "diamond_complete",
                "diamond": dk,
                "round": round_num,
                "positive_z": pos_outcome.certified_z,
                "negative_z": neg_outcome.certified_z,
                "repaired_z": rep_outcome.certified_z,
                "best_z": best_z,
                "wall_ms": (time.monotonic() - t0) * 1000,
            }

        yield {"type": "round_end", "round": round_num, "survivors": 0}

    yield {"type": "done", "rounds": max_rounds}
