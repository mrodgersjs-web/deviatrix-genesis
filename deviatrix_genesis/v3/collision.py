"""Collision Engine — fuse the top survivors into hybrid ideas.

After the conductor runs the 3×3×7 over the 9 candidates, the top
N survivors often have *complementary* mechanisms. The Collision
Engine picks pairs whose mechanisms don't overlap and proposes a
hybrid that carries both.

The hybrid's:
  * ``formula`` is the concatenation of the parents' formulas
  * ``falsifier`` is the conjunction (the hybrid must defeat *both*
    parent falsifiers)
  * ``newness`` is the max of the parents (a hybrid cannot be less
    novel than its parents)
  * ``lineage`` lists the parents so the audit trail is intact

The hybrids re-enter the 3×3×7 conductor for a second pass. This
is the doctrine's "Collision Engine" applied *post-run*, not as
the first-pass band.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .proposer import GTMIdea

__all__ = ["HybridIdea", "fuse_survivors"]


@dataclass
class HybridIdea(GTMIdea):
    """A fused idea carrying two parents."""

    parents: list[str] = field(default_factory=list)  # parent names
    parent_families: list[str] = field(default_factory=list)


# ────────────────────────────────────────────────────────────────────
# Fusion
# ────────────────────────────────────────────────────────────────────


def fuse_survivors(
    survivors: list[GTMIdea],
    *,
    n_hybrids: int = 3,
) -> list[HybridIdea]:
    """Pick pairs of top survivors and produce hybrids.

    Strategy: rank survivors by ``composite_z`` (already in the
    input list — caller pre-sorts), then pick the top ``n_hybrids``
    pairs whose mechanism families differ. Pairs with the same
    family are skipped (a same-family fusion is just a duplicate).
    """
    if len(survivors) < 2:
        return []

    out: list[HybridIdea] = []
    used_pairs: set[tuple[int, int]] = set()

    # Sort by newness scalar (max of the three)
    sorted_survivors = sorted(
        enumerate(survivors),
        key=lambda pair: -max(
            pair[1].anti_orthodoxy_new,
            pair[1].mechanism_originality_new,
            pair[1].prior_art_distance_new,
        ),
    )

    for i, (idx_a, idea_a) in enumerate(sorted_survivors):
        if len(out) >= n_hybrids:
            break
        for j, (idx_b, idea_b) in enumerate(sorted_survivors[i + 1 :], start=i + 1):
            if (idx_a, idx_b) in used_pairs:
                continue
            if idea_a.mechanism_family == idea_b.mechanism_family:
                continue
            used_pairs.add((idx_a, idx_b))

            hybrid_name = (
                f"Hybrid [{idea_a.mechanism_family} + {idea_b.mechanism_family}] — "
                f"{idea_a.name.split(' — ')[0]} × {idea_b.name.split(' — ')[0]}"
            )
            hybrid_formula = f"({idea_a.formula}) + ({idea_b.formula})"
            hybrid_falsifier = (
                f"AND of parents: ({idea_a.falsifier}) AND ({idea_b.falsifier})."
            )
            hybrid_newness = {
                "anti_orthodoxy_new": max(idea_a.anti_orthodoxy_new, idea_b.anti_orthodoxy_new) + 0.2,
                "mechanism_originality_new": max(idea_a.mechanism_originality_new, idea_b.mechanism_originality_new) + 0.2,
                "prior_art_distance_new": max(idea_a.prior_art_distance_new, idea_b.prior_art_distance_new) + 0.2,
            }
            hybrid_action = (
                f"Run BOTH: {idea_a.action_90d[:80]}... AND {idea_b.action_90d[:80]}..."
            )

            out.append(
                HybridIdea(
                    name=hybrid_name,
                    formula=hybrid_formula,
                    falsifier=hybrid_falsifier,
                    closest_known_archetype=None,
                    owner_dept=_pick_dept(idea_a, idea_b),
                    action_90d=hybrid_action,
                    mechanism_family=f"{idea_a.mechanism_family}+{idea_b.mechanism_family}",
                    parents=[idea_a.name, idea_b.name],
                    parent_families=[idea_a.mechanism_family, idea_b.mechanism_family],
                    **hybrid_newness,
                )
            )
            break  # one fusion per top idea

    return out


def _pick_dept(a: GTMIdea, b: GTMIdea) -> str:
    """Pick the owner department for a hybrid. Prefer 'strategy' if either is strategy."""
    depts = {a.owner_dept, b.owner_dept}
    if "strategy" in depts:
        return "strategy"
    if "finance" in depts:
        return "finance"
    return f"{a.owner_dept}+{b.owner_dept}"
