"""Example 3 — Wall breach and structural floor.

Demonstrates the verifier's two safety rails:

  1. certified_z ≥ 30σ  → ESCALATE  (30σ is the wall, not the floor)
  2. structural_distance < diamond floor → MUTATE

The doctrine forbids auto-passing at or beyond 30σ. The doctrine also
requires the D2 Invention diamond to clear z_structural ≥ 5σ; below
that the candidate must be mutated.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deviatrix_genesis import schemas
from deviatrix_genesis.diamonds import DiamondHarness
from deviatrix_genesis.diamonds.d2_invention import InventionPositiveTail
from deviatrix_genesis.verifier import IndependentVerifier


def main() -> int:
    rng = random.Random(0)
    pop = [rng.gauss(0, 1) for _ in range(500)]
    claim = schemas.MathClaim(
        expression="x**2 + 1", symbols=["x"], assumptions={}, reference_population=pop
    )
    verifier = IndependentVerifier(verifier_id="edge-verifier")

    # ── Case 1: candidate_value pushed past 30σ (wall breach)
    class WallBreach(InventionPositiveTail):
        def candidate_value(self) -> float:
            return 1e9

    h1 = DiamondHarness(diamond=schemas.DiamondKind.INVENTION)
    outcome1 = WallBreach(
        h1, novelty=100.0, systematicity=100.0, utility=100.0, interference=0.0
    ).run(claim)
    r1 = verifier.verify(outcome1.packets[0])
    print("Case 1 — wall breach:")
    print(f"  certified_z : {outcome1.certified_z:.2f}")
    print(f"  verifier    : {r1.decision.value}  reason={r1.reason}")
    print(f"  wall_breach : {r1.wall_breach}")
    print()

    # ── Case 2: structural_distance below the D2 5σ floor (mutate)
    class BelowFloor(InventionPositiveTail):
        def candidate_value(self) -> float:
            return 0.0

        def structural_distance(self) -> float:
            return 2.0  # below 5.0

        def behavioral_distance(self) -> float:
            return 0.0

    h2 = DiamondHarness(diamond=schemas.DiamondKind.INVENTION)
    outcome2 = BelowFloor(
        h2, novelty=1.0, systematicity=1.0, utility=1.0, interference=0.0
    ).run(claim)
    r2 = verifier.verify(outcome2.packets[0])
    print("Case 2 — below structural floor:")
    print(f"  certified_z    : {outcome2.certified_z:.2f}")
    print(f"  structural_dist: {outcome2.packets[0].deviation.structural_distance}")
    print(f"  verifier       : {r2.decision.value}  reason={r2.reason[:80]}")
    print(f"  flags          : {r2.failure_flags}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
