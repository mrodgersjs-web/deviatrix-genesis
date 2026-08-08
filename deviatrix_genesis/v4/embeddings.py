"""Embedding-aware corpus scoring.

v3 used Jaccard token similarity. Jaccard penalises long entries
that *should* match (because the union grows linearly while the
intersection grows sublinearly). v4 uses a hashed bag-of-tokens
embedding with cosine similarity — the right distance for idea
space.

The embedding is *cheap* (no model, no API): token → hash → fixed-
dimension vector. This is the standard "hashing trick" used in
`sklearn.feature_extraction.text.HashingVectorizer`. We add L2
normalisation so cosine reduces to a dot product.

The newness scoring (anti_orthodoxy / mechanism_originality /
prior_art_distance) is computed against the corpus with cosine
similarity. The output is a :class:`RealNeighbour` that the v3
corpus_loader can consume as a drop-in replacement for the Jaccard
score.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Sequence

__all__ = [
    "HashedEmbedding",
    "cosine_similarity",
    "score_with_embeddings",
    "build_embedding_index",
    "EmbeddingIndex",
]


# 2^16 = 65536 dimensions — same default as sklearn's HashingVectorizer.
EMBED_DIM = 65536


@dataclass
class HashedEmbedding:
    """A sparse hashed bag-of-tokens embedding.

    Stored as a dense dict of (index → weight) so we don't pay for
    the zero entries.
    """

    weights: dict[int, float] = field(default_factory=dict)
    norm: float = 0.0

    @classmethod
    def from_text(cls, text: str, *, dim: int = EMBED_DIM) -> "HashedEmbedding":
        """Build a TF embedding from text using the hashing trick.

        Tokenisation: split on non-alphanumeric, lowercase, drop
        tokens of length < 3. Each token is hashed via SHA-1
        (truncated to 4 bytes) into the index space. Weight is the
        sub-linear TF: 1 + log(count).
        """
        counts: Counter[str] = Counter()
        for tok in re.findall(r"\b\w+\b", text.lower()):
            if len(tok) >= 3:
                counts[tok] += 1
        weights: dict[int, float] = {}
        for tok, c in counts.items():
            h = hashlib.sha1(tok.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "little") % dim
            weights[idx] = weights.get(idx, 0.0) + (1.0 + math.log(c))
        norm = math.sqrt(sum(w * w for w in weights.values()))
        return cls(weights=weights, norm=norm)


def cosine_similarity(a: HashedEmbedding, b: HashedEmbedding) -> float:
    """Cosine similarity between two sparse hashed embeddings."""
    if a.norm == 0 or b.norm == 0:
        return 0.0
    # Sparse dot product: iterate over the smaller side.
    if len(a.weights) > len(b.weights):
        a, b = b, a
    s = 0.0
    for k, v in a.weights.items():
        if k in b.weights:
            s += v * b.weights[k]
    return s / (a.norm * b.norm)


@dataclass
class EmbeddingIndex:
    """An in-memory index of HashedEmbeddings for fast nearest-neighbour lookup."""

    entries: list[HashedEmbedding] = field(default_factory=list)
    metadata: list[dict[str, str]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def add(self, emb: HashedEmbedding, meta: dict[str, str] | None = None) -> None:
        self.entries.append(emb)
        self.metadata.append(meta or {})

    def similarity_to(self, query: HashedEmbedding, idx: int) -> float:
        return cosine_similarity(query, self.entries[idx])

    def all_similarities(self, query: HashedEmbedding) -> list[float]:
        return [cosine_similarity(query, e) for e in self.entries]


def build_embedding_index(texts: Iterable[str], *, metadata: Sequence[dict[str, str]] | None = None) -> EmbeddingIndex:
    """Build an index from a sequence of texts."""
    idx = EmbeddingIndex()
    meta_list = list(metadata) if metadata is not None else None
    for i, text in enumerate(texts):
        emb = HashedEmbedding.from_text(text)
        meta = meta_list[i] if meta_list and i < len(meta_list) else None
        idx.add(emb, meta)
    return idx


@dataclass
class NeighbourScores:
    """The newness scores for one entry against an index."""

    anti_orthodoxy: float
    mechanism_originality: float
    prior_art_distance: float
    mean_similarity: float
    max_similarity: float
    mechanism_hits: int


# Mechanism regex — same list as v3's corpus_loader
from ..v3.corpus_loader import KNOWN_MECHANISM_PATTERNS  # noqa: E402


def score_with_embeddings(
    text: str,
    index: EmbeddingIndex,
    *,
    exclude_self: bool = True,
) -> NeighbourScores:
    """Score one text against the corpus index using cosine similarity."""
    query = HashedEmbedding.from_text(text)
    if len(index) == 0:
        return NeighbourScores(0.0, 0.0, 0.0, 0.0, 0.0, 0)

    sims = index.all_similarities(query)
    if exclude_self and len(sims) > 0:
        # If the query is in the index, drop its own self-similarity.
        # The simplest heuristic: drop the maximum self-mimicking entry.
        max_sim = max(sims)
        if max_sim > 0.99:
            sims = [s for s in sims if s < 0.99]

    if not sims:
        return NeighbourScores(1.0, 0.0, 1.0, 0.0, 0.0, 0)

    mean_sim = sum(sims) / len(sims)
    max_sim = max(sims)
    anti_orthodoxy = max(0.0, min(1.0, 1.0 - mean_sim))
    prior_art_distance = max(0.0, min(1.0, 1.0 - max_sim))

    # Mechanism hits — same as v3
    text_lower = text.lower()
    mech_hits = sum(
        1 for pat in KNOWN_MECHANISM_PATTERNS if re.search(pat, text_lower)
    )
    mechanism_originality = min(1.0, mech_hits * 0.2)

    return NeighbourScores(
        anti_orthodoxy=anti_orthodoxy,
        mechanism_originality=mechanism_originality,
        prior_art_distance=prior_art_distance,
        mean_similarity=mean_sim,
        max_similarity=max_sim,
        mechanism_hits=mech_hits,
    )
