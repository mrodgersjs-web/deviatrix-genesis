"""Diamond 2 — Invention deviation.

CHAOS and Collision search for category mutation.

  D2-A  positive_tail   constructive category mutation
                        i_D2+ = argmax [ λ1·N + λ2·S + λ3·U − λ4·I ]
                        subject to z_structural ≥ 5, K_coherence ≥ K_min,
                                    M_mechanism ≥ M_min
  D2-B  negative_tail   anti-solutions: remove core tech, reverse payer,
                        maximize pain, make incumbent advantage absolute,
                        enforce opposite physical architecture, design
                        the solution most likely to fail.
                        i_D2- = argmin TransformationValue(i)
  D2-C  repaired_tail   anti-unification → shared skeleton G, then
                        Amalgamate(G, R+_useful, R-_defensive).
"""

from __future__ import annotations

import math

from .. import schemas
from . import DiamondHarness
from .expeditions import Expedition, ExpeditionOutcome

__all__ = [
    "InventionPositiveTail",
    "InventionNegativeTail",
    "InventionRepairedTail",
]


class _InventionBase(Expedition):
    diamond = schemas.DiamondKind.INVENTION

    def objective(self) -> str:
        return {
            schemas.ExpeditionKind.POSITIVE_TAIL: (
                "CHAOS and Collision search for constructive category "
                "mutation: maximize novelty, systematicity, transformation "
                "utility; minimize interference."
            ),
            schemas.ExpeditionKind.NEGATIVE_TAIL: (
                "Generate anti-solutions: remove core tech, reverse payer, "
                "maximize customer pain, make incumbent advantage absolute, "
                "enforce opposite physical architecture, design the "
                "solution most likely to fail."
            ),
            schemas.ExpeditionKind.REPAIRED_TAIL: (
                "Anti-unification to find the shared skeleton G, then "
                "Amalgamate(G, R+_useful, R-_defensive)."
            ),
        }[self.kind]


class InventionPositiveTail(_InventionBase):
    def __init__(
        self,
        harness: DiamondHarness,
        *,
        novelty: float = 0.0,
        systematicity: float = 0.0,
        utility: float = 0.0,
        interference: float = 0.0,
        lam: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        structural_floor: float = 5.0,
    ) -> None:
        super().__init__(harness, schemas.ExpeditionKind.POSITIVE_TAIL)
        self.N = novelty
        self.S = systematicity
        self.U = utility
        self.I = interference
        self.lam = lam
        self.structural_floor = structural_floor

    def falsifier(self) -> str:
        return (
            f"Falsifier: candidate with z_structural < {self.structural_floor}σ "
            "or coherence/mechanism below min."
        )

    def candidate_value(self) -> float:
        return (
            self.lam[0] * self.N
            + self.lam[1] * self.S
            + self.lam[2] * self.U
            - self.lam[3] * self.I
        )

    def structural_distance(self) -> float:
        # The structural floor is enforced via the band routing; we
        # return the structural z as the candidate's *floor*.
        return max(self.structural_floor, (self.N + self.S) / 2.0)

    def behavioral_distance(self) -> float:
        return max(self.U - 0.5 * self.I, 0.0)


class InventionNegativeTail(_InventionBase):
    def __init__(
        self,
        harness: DiamondHarness,
        *,
        transformation_value: float = 0.0,
    ) -> None:
        super().__init__(harness, schemas.ExpeditionKind.NEGATIVE_TAIL)
        self._t = transformation_value

    def falsifier(self) -> str:
        return "Falsifier: anti-solution with transformation_value > 0."

    def candidate_value(self) -> float:
        # Negative expedition lives in the negative z-band
        return -abs(self._t)

    def structural_distance(self) -> float:
        return 0.0

    def behavioral_distance(self) -> float:
        return abs(self._t)


class InventionRepairedTail(_InventionBase):
    def __init__(
        self,
        harness: DiamondHarness,
        *,
        positive_outcome: ExpeditionOutcome,
        negative_outcome: ExpeditionOutcome,
        coherence: float = 0.0,
    ) -> None:
        super().__init__(harness, schemas.ExpeditionKind.REPAIRED_TAIL)
        self.positive = positive_outcome
        self.negative = negative_outcome
        self._k = coherence

    def falsifier(self) -> str:
        return (
            "Falsifier: amalgamated candidate whose shared skeleton G "
            "is empty, OR whose useful+defensive relations cancel."
        )

    def candidate_value(self) -> float:
        # Geometric mean of pos and |neg| gives a balanced repair score
        z_pos = self.positive.certified_z
        z_neg = abs(self.negative.certified_z)
        if z_pos == 0 and z_neg == 0:
            return 0.0
        # Use a soft-mean that prefers larger pos but penalises large neg
        return z_pos * math.exp(-0.1 * z_neg) + 0.3 * self._k

    def structural_distance(self) -> float:
        return self.positive.certified_z * 0.6

    def behavioral_distance(self) -> float:
        return self.positive.certified_z * 0.4 + 0.2 * self._k
