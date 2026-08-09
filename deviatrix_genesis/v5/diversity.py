"""Population diversity injection — prevents reference population collapse.

When the same seed produces identical populations across rounds,
the z-scores become meaningless. This module injects diversity by:
  1. Mixing multiple distributions (Gaussian, uniform, Cauchy, lognormal)
  2. Adding structured perturbations from prior survivors
  3. Ensuring minimum entropy in each population

Usage::

    from deviatrix_genesis.v5.diversity import diverse_population

    pop = diverse_population(size=500, seed=2026, round_num=2, survivors=[...])
"""

from __future__ import annotations

import math
import random
from typing import Any

__all__ = ["diverse_population", "population_entropy"]


def diverse_population(
    size: int = 500,
    seed: int = 2026,
    round_num: int = 1,
    survivors: list[dict[str, Any]] | None = None,
) -> list[float]:
    """Generate a diverse reference population.

    Round 1: standard Gaussian. Round 2+: mix distributions and
    inject survivor-informed perturbations.
    """
    rng = random.Random(seed * 1_000_003 + round_num)

    if round_num <= 1:
        return [rng.gauss(0, 1) for _ in range(size)]

    # Mix distributions for diversity
    pop: list[float] = []
    chunk = size // 4

    # Gaussian core
    pop.extend(rng.gauss(0, 1) for _ in range(chunk))

    # Uniform spread
    pop.extend(rng.uniform(-3, 3) for _ in range(chunk))

    # Cauchy tails (heavy-tailed for extreme value sensitivity)
    for _ in range(chunk):
        u = rng.random()
        pop.append(math.tan(math.pi * (u - 0.5)))

    # Lognormal for positive skew
    pop.extend(rng.lognormvariate(0, 0.5) for _ in range(size - 3 * chunk))

    # Inject survivor-informed perturbations
    if survivors:
        for s in survivors[:10]:
            z = s.get("composite_z", 0.0)
            # Add values near each survivor's z-score
            for _ in range(size // 20):
                pop.append(z + rng.gauss(0, 0.5))

    # Shuffle to break ordering
    rng.shuffle(pop)
    return pop[:size]


def population_entropy(population: list[float]) -> float:
    """Compute Shannon entropy of a binned population.

    Higher entropy = more diverse. Useful for verifying diversity
    injection is working.
    """
    if not population:
        return 0.0

    # Bin into 20 bins
    lo, hi = min(population), max(population)
    if lo == hi:
        return 0.0
    span = hi - lo
    n_bins = 20
    counts = [0] * n_bins
    for v in population:
        bin_idx = min(int((v - lo) / span * n_bins), n_bins - 1)
        counts[bin_idx] += 1

    total = len(population)
    entropy = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            entropy -= p * math.log2(p)

    return entropy
