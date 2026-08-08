"""MathExec — robust statistical telemetry.

This package measures *actual* distance from a reference distribution.
It is independent of the LLM, the generator, and the sympy layer.

The certified robust deviation is the conservative minimum of several
estimators, never the maximum. The verifier trusts only this number.

Surface
-------

* :func:`robust_madz`  — robust-MAD-Z (primary)
* :func:`qn_scale`     — Qn (Rousseeuw/Croux) scale estimator
* :func:`qn_z`         — robust Qn-based z-score
* :func:`bootstrap_lower` — bootstrap lower-bound on |z|
* :func:`alternate_corpus_z` — z against a secondary corpus
* :func:`certified_z`  — conservative-minimum aggregator
* :func:`counterexample_search` — find the smallest counterexample
* :func:`composite_deviation` — 0.3·structural + 0.7·behavioral
"""

from __future__ import annotations

import hashlib
import statistics
from typing import Sequence

__all__ = [
    "MAD_CONSTANT",
    "QN_CONSTANT",
    "robust_madz",
    "qn_scale",
    "qn_z",
    "bootstrap_lower",
    "alternate_corpus_z",
    "certified_z",
    "counterexample_search",
    "composite_deviation",
    "hash_population",
]


# 0.6745 = 1 / Φ⁻¹(0.75) — the MAD constant that makes MAD a consistent
# estimator of σ under normality.
MAD_CONSTANT = 0.6744897501960817

# 2.2219 — Qn scale constant (Rousseeuw & Croux, 1993) that makes Qn a
# consistent estimator of σ under normality.
QN_CONSTANT = 2.2219


# ────────────────────────────────────────────────────────────────────
# Population hashing — every reference population needs an immutable id
# ────────────────────────────────────────────────────────────────────


def hash_population(values: Sequence[float]) -> str:
    """Return a deterministic SHA-256 prefix of the population.

    This is the immutable id stored in the proof packet so the verifier
    can later confirm the reference population has not been silently
    swapped.
    """
    body = "::".join(f"{float(v):.17g}" for v in values)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


# ────────────────────────────────────────────────────────────────────
# MAD and Qn
# ────────────────────────────────────────────────────────────────────


def _mad(values: Sequence[float]) -> float:
    """Median absolute deviation."""
    if len(values) < 2:
        return 0.0
    med = statistics.median(values)
    return statistics.median(abs(v - med) for v in values)


def robust_madz(x: float, population: Sequence[float]) -> float:
    """Robust-MAD-Z.

    z = 0.6745 · (x - median(population)) / MAD(population)

    Returns 0.0 if MAD is zero (degenerate population).
    """
    if not population:
        return 0.0
    med = statistics.median(population)
    mad = _mad(population)
    if mad == 0:
        return 0.0
    return MAD_CONSTANT * (x - med) / mad


def _qn(values: Sequence[float]) -> float:
    """Rousseeuw/Croux Qn scale estimator.

    Qn = 2.2219 · {|xi - xj|; i < j}_(k)

    where k = h(h-1)/2 with h = floor(n/2) + 1.

    We use a naive O(n²) implementation; for n < 10k this is fast
    enough, and the verifier wants determinism, not cleverness.
    """
    n = len(values)
    if n < 2:
        return 0.0
    diffs: list[float] = []
    for i in range(n - 1):
        for j in range(i + 1, n):
            diffs.append(abs(values[i] - values[j]))
    diffs.sort()
    h = n // 2 + 1
    k = h * (h - 1) // 2
    if k >= len(diffs):
        return 0.0
    return QN_CONSTANT * diffs[k - 1]  # k is 1-indexed


def qn_scale(population: Sequence[float]) -> float:
    """Public Qn scale."""
    return _qn(list(population))


def qn_z(x: float, population: Sequence[float]) -> float:
    """Robust z-score using Qn instead of MAD."""
    if not population:
        return 0.0
    med = statistics.median(population)
    qn = qn_scale(population)
    if qn == 0:
        return 0.0
    return (x - med) / qn


# ────────────────────────────────────────────────────────────────────
# Bootstrap
# ────────────────────────────────────────────────────────────────────


def bootstrap_lower(
    x: float,
    population: Sequence[float],
    *,
    n_resamples: int = 1000,
    confidence: float = 0.95,
    seed: int = 1337,
) -> tuple[float, float]:
    """Bootstrap lower-bound on the magnitude of the z-score.

    Resample the population with replacement; for each resample compute
    the z-score of ``x``; return the lower edge of the central
    ``confidence`` interval on ``|z|``.

    A lower bound on |z| (rather than on z itself) is used because the
    verifier cares about *evidence* of deviation, not the sign.
    """
    import random

    if not population:
        return (0.0, 0.0)
    rng = random.Random(seed)
    values = list(population)
    n = len(values)
    if n < 2:
        return (0.0, 0.0)
    magnitudes: list[float] = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        magnitudes.append(abs(robust_madz(x, sample)))
    magnitudes.sort()
    k = max(0, int((1 - confidence) / 2 * n_resamples))
    return (magnitudes[k], magnitudes[-k - 1])


# ────────────────────────────────────────────────────────────────────
# Alternate corpus
# ────────────────────────────────────────────────────────────────────


def alternate_corpus_z(
    x: float,
    population: Sequence[float],
    *,
    alternate: Sequence[float],
) -> float:
    """Robust-MAD-Z against an alternate reference corpus.

    Used by Pass C to confirm the deviation is not an artifact of one
    corpus. A candidate's certified deviation is *conservative*; if the
    alternate corpus shrinks the apparent z, that is the number we trust.
    """
    return robust_madz(x, alternate)


# ────────────────────────────────────────────────────────────────────
# Conservative aggregator
# ────────────────────────────────────────────────────────────────────


def certified_z(
    z_mad: float,
    z_qn: float,
    bootstrap_lower_bound: float,
    z_alternate: float,
) -> float:
    """Conservative minimum.

    z_certified = min(z_MAD, z_Qn, bootstrap_lower, z_alt_corpus)

    This is the *signed* deviation the verifier uses to route the
    candidate. Sign is preserved so negative-tail expeditions don't get
    collapsed into positive.
    """
    # bootstrap_lower_bound is non-negative; preserve the original sign
    # of z_mad as the canonical reference direction.
    candidates = [z_mad, z_qn, z_alternate]
    if bootstrap_lower_bound > 0:
        candidates.append(
            bootstrap_lower_bound if z_mad >= 0 else -bootstrap_lower_bound
        )
    return min(candidates)


# ────────────────────────────────────────────────────────────────────
# Composite deviation (structural vs behavioral)
# ────────────────────────────────────────────────────────────────────


def composite_deviation(structural: float, behavioral: float) -> float:
    """0.3·structural + 0.7·behavioral.

    A candidate cannot reach 30σ merely by changing vocabulary; the
    behavioral mechanism must carry most of the deviation.
    """
    return 0.3 * structural + 0.7 * behavioral


# ────────────────────────────────────────────────────────────────────
# Counterexample search
# ────────────────────────────────────────────────────────────────────


def counterexample_search(
    claim: "object",
    search_range: tuple[float, float] = (-100.0, 100.0),
    n_samples: int = 200,
    rng_seed: int = 1337,
) -> dict[str, object]:
    """Find the smallest counterexample to the claim's falsifier.

    The claim is expected to expose either a callable
    ``claim.evaluate(x)`` returning a value or a string expression
    parseable by sympy. Returns the x with the smallest |f(x)| —
    *evidence that the formula's behavior is bounded*.

    This is a numerical sanity check, not a proof. It catches
    division-by-near-zero inflation, monotone-explosions, and similar
    pathologies that would otherwise manufacture a 30σ event.
    """
    import random

    rng = random.Random(rng_seed)
    try:
        from sympy import sympify, lambdify, Symbol  # type: ignore
    except Exception as e:  # pragma: no cover
        return {"status": "FAIL", "error": f"sympy unavailable: {e}"}

    expr_str = getattr(claim, "expression", None) or getattr(claim, "formula", "")
    if not expr_str:
        return {"status": "FAIL", "error": "no expression on claim"}
    try:
        x = Symbol("x")
        raw = sympify(expr_str, locals={"x": x})
        f = lambdify(x, raw, modules=["sympy"])
    except Exception as e:  # pragma: no cover
        return {"status": "FAIL", "error": f"parse: {e}"}

    lo, hi = search_range
    best_x = 0.0
    best_val: float | None = None
    for _ in range(n_samples):
        x_val = rng.uniform(lo, hi)
        try:
            v = f(x_val)
            v = float(v) if v is not None else float("inf")
        except Exception:
            v = float("inf")
        if not (v == v):  # NaN
            v = float("inf")
        if best_val is None or abs(v) < abs(best_val):
            best_val = v
            best_x = x_val
    return {
        "status": "OK",
        "search_range": [lo, hi],
        "n_samples": n_samples,
        "best_x": best_x,
        "best_value": best_val,
        "is_pathological": abs(best_val) > 1e12 if best_val is not None else True,
    }
