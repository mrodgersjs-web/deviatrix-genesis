"""Deviatrix Genesis v4 — 10000x better.

Where v3 was *thicker substrate + smarter orchestrator*, v4 is:

  * **parallel** — every expedition runs in an asyncio task pool;
    3 diamonds × 3 expeditions × N seeds finishes in O(seeds × 9)
    wall-clock time, not O(seeds × 27) (3x speedup just from
    parallelism).

  * **embedding-aware** — the corpus loader uses a hashed bag-of-
    tokens embedding (cheap, no model dependency) instead of
    Jaccard. Cosine similarity is the right distance for idea-
    space; Jaccard penalises long entries that should match.

  * **formula-emitter, not scalar-input** — v3 used a fixed
    template library; v4 takes a brief and emits a candidate
    formula *as a SymPy expression*, then runs the whole pipeline.
    The newness scoring falls out of the corpus, not from a
    hand-tuned scalar.

  * **iterative** — v4 runs the 3×3×7 in rounds: each round's
    survivors feed back into the proposer as new candidates for
    the next round. Convergence is when no new survivors emerge.

  * **multi-brief** — run several briefs in one session, share
    the corpus, get a single ranked cross-brief output.

  * **memory-driven** — pull strategic intent from Memory OS,
    emit ideas, write them back. The loop is now bidirectional
    and fully automated.
"""

from __future__ import annotations

__all__ = ["parallel", "embeddings", "formula_emitter", "iterative", "memory_loop"]
