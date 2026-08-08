"""Sigma-band routing table.

Encoded verbatim from the doctrine:

Positive tail:

    | Certified robust deviation | Interpretation                | System action       |
    | < 0σ                       | Worse than median             | negative-tail archive or reject |
    | 0σ to +3σ                  | Commodity neighborhood        | Anti-Median Engine   |
    | +3σ to +5σ                 | Differentiated but ordinary   | Collision Engine     |
    | +5σ to +10σ                | Strong deviation              | Deep review          |
    | +10σ to +20σ               | Category-shaping candidate    | Adversarial proof    |
    | +20σ to below +30σ         | Extreme-tail candidate        | Mike-gated review    |
    | at or beyond ±30σ          | Ceiling breach                | Hard stop            |

Negative tail (mirror):

    | Certified deviation         | Meaning                          |
    | -3σ to -5σ                  | Weak anti-pattern                |
    | -5σ to -10σ                 | Material failure architecture    |
    | -10σ to -20σ                | Strong destructive countermodel  |
    | -20σ to above -30σ          | Extreme anti-idea                |
    | at or below -30σ            | Ceiling breach                   |

30σ is the **wall, not the floor**. No candidate at or beyond 30σ
auto-passes.
"""

from __future__ import annotations

from typing import NamedTuple

__all__ = ["band_for", "BAND_TABLE"]


class Band(NamedTuple):
    label: str
    interpretation: str
    action: str
    is_wall: bool = False


POSITIVE_BANDS: list[tuple[float, float, Band]] = [
    (0.0, 3.0, Band("0σ–3σ", "commodity_neighborhood", "anti_median")),
    (3.0, 5.0, Band("+3σ–5σ", "differentiated", "collision")),
    (5.0, 10.0, Band("+5σ–10σ", "strong_deviation", "deep_review")),
    (10.0, 20.0, Band("+10σ–20σ", "category_shaping", "adversarial_proof")),
    (20.0, 30.0, Band("+20σ–30σ", "extreme_tail", "mike_gated_review")),
    (30.0, float("inf"), Band("≥+30σ", "ceiling_breach", "hard_stop", True)),
]

NEGATIVE_BANDS: list[tuple[float, float, Band]] = [
    (-3.0, 0.0, Band("-0σ–3σ", "below_median", "reject")),
    (-5.0, -3.0, Band("-3σ–5σ", "weak_anti_pattern", "note")),
    (-10.0, -5.0, Band("-5σ–10σ", "failure_architecture", "hostile_test")),
    (-20.0, -10.0, Band("-10σ–20σ", "destructive_countermodel", "hostile_test")),
    (-30.0, -20.0, Band("-20σ–30σ", "extreme_anti_idea", "mike_gated_review")),
    (-float("inf"), -30.0, Band("≤-30σ", "ceiling_breach", "hard_stop", True)),
]


def band_for(z: float) -> str:
    """Return the band label for *z*."""
    if z >= 0:
        for lo, hi, b in POSITIVE_BANDS:
            if lo <= z < hi:
                return b.label
        return "≥+30σ"
    for hi, lo, b in NEGATIVE_BANDS:
        if hi <= z < lo:
            return b.label
    return "≤-30σ"


def action_for(z: float) -> str:
    """Return the system action string for *z*."""
    if z >= 0:
        for lo, hi, b in POSITIVE_BANDS:
            if lo <= z < hi:
                return b.action
        return "hard_stop"
    for hi, lo, b in NEGATIVE_BANDS:
        if hi <= z < lo:
            return b.action
    return "hard_stop"


def is_wall(z: float) -> bool:
    """True if *z* has hit the ±30σ ceiling."""
    return abs(z) >= 30.0


BAND_TABLE = {
    "positive": [b for _, _, b in POSITIVE_BANDS],
    "negative": [b for _, _, b in NEGATIVE_BANDS],
}
