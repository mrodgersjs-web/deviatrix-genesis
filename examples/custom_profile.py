"""Example 2 — Custom profile, custom reference population.

A real Deviatrix run would supply:
  * a real reference population (a corpus of comparable ideas)
  * tuned per-diamond scoring profiles
  * a fixed run_id so the artifacts are deterministic across retries
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deviatrix_genesis.conductors import DeviatrixConductor


def market_population(n: int = 1000, *, seed: int = 0) -> list[float]:
    """Heavy-tailed distribution simulating 'idea market' metric noise."""
    rng = random.Random(seed)
    out: list[float] = []
    for _ in range(n):
        # 80% normal noise + 20% outlier tail (mimics long-tail markets)
        if rng.random() < 0.8:
            out.append(rng.gauss(0, 1))
        else:
            out.append(rng.gauss(0, 8))
    return out


def custom_profiles() -> dict:
    return {
        "opportunity": {
            "positive": {
                "transformation_z": 8.0,    # bigger positive pull
                "orthodoxy_break_z": 6.0,
                "evidence_z": 5.0,
            },
            "negative": {
                "behavioral_evidence_z": 3.0,
                "economic_viability_z": 4.0,
            },
        },
        "invention": {
            "positive": {
                "novelty": 6.0,
                "systematicity": 5.0,
                "utility": 7.0,
                "interference": 0.5,
                "structural_floor": 5.0,
            },
            "negative": {
                "transformation_value": 3.0,
            },
        },
        "proof": {
            "positive": {
                "behavioral_proof_z": 6.0,
                "technical_proof_z": 5.0,
                "novelty_proof_z": 6.5,
            },
            "negative": {
                "falsification_energy": 10.0,
            },
        },
    }


def main() -> int:
    c = DeviatrixConductor(
        run_id="deviatrix-custom-001",
        seed=2026,
        reference_population_factory=lambda n: market_population(n, seed=42),
        profiles=custom_profiles(),
        verifier_id="verifier-custom",
        output_dir="./proofs",
    )
    report = c.run(formula="x**2 + 2*x + 1", pop_size=1000)
    print(json.dumps(report.to_dict(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
