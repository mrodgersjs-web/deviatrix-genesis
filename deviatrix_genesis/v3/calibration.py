"""Self-calibration loop.

v1/v2 needed hand-tuned scalar scores because the candidate_value
formula ``sqrt(z1²+z2²+z3²) + z1+z2+z3`` amplifies the sum and
pushed inputs past the ±30σ wall.

The calibration loop *learns* the score-to-z mapping from prior
run results and proposes inputs that land in target bands:

  * D1-repaired z ∈ [+5σ, +25σ]
  * D2-repaired z ∈ [+5σ, +20σ]
  * D3-repaired z ∈ [+5σ, +15σ]
  * Composite z (mean of D1/D2/D3 repaired) ∈ [+10σ, +20σ]

It works by fitting a simple linear model:

  predicted_z = a · input_score + b

and inverting to find the input that lands at the target.
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["CalibrationRecord", "calibrate", "propose_calibrated_scores"]


# ────────────────────────────────────────────────────────────────────
# Calibration record (one per idea per run)
# ────────────────────────────────────────────────────────────────────


@dataclass
class CalibrationRecord:
    """One observed data point: input scores → certified_z."""

    idea_name: str
    seed: int
    ao_input: float
    mo_input: float
    pa_input: float
    d1_rep_z: float
    d2_rep_z: float
    d3_rep_z: float
    composite_z: float
    is_respin: bool


# ────────────────────────────────────────────────────────────────────
# Fitting
# ────────────────────────────────────────────────────────────────────


def _fit_linear(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Fit y = a·x + b by least squares. Returns (a, b)."""
    if len(xs) < 2:
        return 1.0, 0.0
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var = sum((x - mean_x) ** 2 for x in xs)
    if var == 0:
        return 1.0, mean_y
    a = cov / var
    b = mean_y - a * mean_x
    return a, b


# ────────────────────────────────────────────────────────────────────
# Calibration loop
# ────────────────────────────────────────────────────────────────────


# Targets per-diamond for the repaired-tail z.
DEFAULT_TARGETS: dict[str, float] = {
    "d1_rep_z": 18.0,
    "d2_rep_z": 14.0,
    "d3_rep_z": 11.0,
}


def calibrate(
    history: list[CalibrationRecord],
) -> dict[str, dict[str, float]]:
    """Fit per-input-score to per-diamond z.

    Returns a dict of {input_field: {target_band: fitted_score}} —
    the score that, when fed into the input field, lands at the
    target band.
    """
    if not history:
        # No history: use the v2 hand-tuned defaults.
        return {
            "ao_input": {band: 4.5 for band in DEFAULT_TARGETS},
            "mo_input": {band: 4.5 for band in DEFAULT_TARGETS},
            "pa_input": {band: 4.5 for band in DEFAULT_TARGETS},
        }

    # Split history into per-band
    band_to_records: dict[str, list[CalibrationRecord]] = {
        "d1_rep_z": [h for h in history if not h.is_respin],
        "d2_rep_z": [h for h in history if not h.is_respin],
        "d3_rep_z": [h for h in history if not h.is_respin],
    }

    fitted: dict[str, dict[str, float]] = {
        "ao_input": {},
        "mo_input": {},
        "pa_input": {},
    }

    for band, records in band_to_records.items():
        if not records:
            continue
        # Take the max-input (max of the three) as the predictor
        # (because the candidate_value formula uses the *sum*, but
        # the max is a better proxy for the dominant mechanism).
        xs = [
            max(r.ao_input, r.mo_input, r.pa_input)
            for r in records
        ]
        ys = [
            getattr(r, band) for r in records
        ]
        a, b = _fit_linear(xs, ys)
        for target_name, target_z in DEFAULT_TARGETS.items():
            # Solve input = (target_z - b) / a
            if a == 0:
                fitted_value = xs[0] if xs else 4.5
            else:
                fitted_value = (target_z - b) / a
            # Clamp to a sane range
            fitted_value = max(0.5, min(8.0, fitted_value))
            fitted[band_to_input_field(band)][target_name] = fitted_value

    # If any target is missing, fill with the median observed
    for band in ("d1_rep_z", "d2_rep_z", "d3_rep_z"):
        for target_name in DEFAULT_TARGETS:
            field_name = band_to_input_field(band)
            if target_name not in fitted[field_name]:
                fitted[field_name][target_name] = 4.5

    return fitted


def band_to_input_field(band: str) -> str:
    return {
        "d1_rep_z": "ao_input",
        "d2_rep_z": "mo_input",
        "d3_rep_z": "pa_input",
    }[band]


def propose_calibrated_scores(
    history: list[CalibrationRecord] | None = None,
    *,
    target_band: str = "composite_z",
    target_z: float = 15.0,
) -> dict[str, float]:
    """Return a single set of calibrated scores for one new idea.

    This is the v3 replacement for hand-tuning. Pass ``history`` to
    enable learning from prior runs; without it, returns the
    hand-tuned defaults.
    """
    history = history or []
    cal = calibrate(history)
    # Use the average of the three calibrated targets
    return {
        "anti_orthodoxy_new": statistics.mean(cal["ao_input"].values()),
        "mechanism_originality_new": statistics.mean(cal["mo_input"].values()),
        "prior_art_distance_new": statistics.mean(cal["pa_input"].values()),
    }


# ────────────────────────────────────────────────────────────────────
# History persistence
# ────────────────────────────────────────────────────────────────────


def load_history(path: str | Path) -> list[CalibrationRecord]:
    p = Path(path)
    if not p.exists():
        return []
    records: list[CalibrationRecord] = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            records.append(CalibrationRecord(**data))
        except (json.JSONDecodeError, TypeError):
            continue
    return records


def append_history(
    path: str | Path,
    record: CalibrationRecord,
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(record.__dict__) + "\n")
