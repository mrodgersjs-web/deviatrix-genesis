"""Cross-brief fusion engine.

Takes survivors from multiple briefs and finds mechanism-complementary
pairs that could not emerge from any single brief alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..v4.embeddings import (
    EmbeddingIndex,
    HashedEmbedding,
    build_embedding_index,
    cosine_similarity,
)

__all__ = ["CrossBriefCandidate", "CrossBriefFusion"]


@dataclass
class CrossBriefCandidate:
    """A hybrid that fuses ideas from two different briefs."""

    name: str
    formula: str
    brief_sources: list[str] = field(default_factory=list)
    parent_names: list[str] = field(default_factory=list)
    mechanism_families: list[str] = field(default_factory=list)
    composite_z: float = 0.0


class CrossBriefFusion:
    """Find mechanism-complementary survivors across briefs."""

    def __init__(self) -> None:
        pass

    def fuse(self, brief_results: list[dict[str, Any]]) -> list[CrossBriefCandidate]:
        """Fuse survivors from multiple brief results.

        Each element of *brief_results* must have keys:
          ``brief`` (str) and ``survivors`` (list[dict]).
        """
        if len(brief_results) < 2:
            return []

        # Collect all survivors tagged with their source brief.
        all_survivors: list[tuple[str, dict[str, Any]]] = []
        for br in brief_results:
            brief_label = br.get("brief", "unknown")
            for s in br.get("survivors", []):
                all_survivors.append((brief_label, s))

        if not all_survivors:
            return []

        # Build embedding index
        texts = [s.get("name", "") + " " + s.get("formula", "") for _, s in all_survivors]
        idx = build_embedding_index(texts)

        # Find cross-brief pairs with complementary mechanisms
        hybrids: list[CrossBriefCandidate] = []
        seen: set[tuple[str, str]] = set()

        for i, (brief_a, surv_a) in enumerate(all_survivors):
            fam_a = set(surv_a.get("mechanism_families", []))
            name_a = surv_a.get("name", f"idea_{i}")

            for j, (brief_b, surv_b) in enumerate(all_survivors):
                if brief_a == brief_b:
                    continue  # same brief — skip
                if j <= i:
                    continue  # avoid duplicates

                fam_b = set(surv_b.get("mechanism_families", []))
                name_b = surv_b.get("name", f"idea_{j}")
                pair_key = tuple(sorted([name_a, name_b]))
                if pair_key in seen:
                    continue
                seen.add(pair_key)

                # Complementary = no mechanism overlap
                if fam_a & fam_b:
                    continue

                sim = cosine_similarity(idx.entries[i], idx.entries[j])
                diversity = 1.0 - sim  # higher = more different
                avg_z = (
                    surv_a.get("composite_z", 0.0) + surv_b.get("composite_z", 0.0)
                ) / 2.0
                score = diversity * avg_z

                hybrids.append(CrossBriefCandidate(
                    name=f"{name_a}×{name_b}",
                    formula=f"({surv_a.get('formula', '')}) * ({surv_b.get('formula', '')})",
                    brief_sources=[brief_a, brief_b],
                    parent_names=[name_a, name_b],
                    mechanism_families=sorted(fam_a | fam_b),
                    composite_z=score,
                ))

        return sorted(hybrids, key=lambda h: -h.composite_z)
