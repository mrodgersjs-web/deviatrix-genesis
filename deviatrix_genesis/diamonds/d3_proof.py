"""Diamond 3 — Proof deviation.

  D3-A  positive_tail   unusually strong evidence: customer behavior,
                        willingness to switch, technical feasibility, cost
                        collapse, prior-art distance, mechanism performance,
                        defensibility.
                        p_D3+ = argmax [ z_behavioral_proof + z_technical_proof
                                          + z_novelty_proof ]
  D3-B  negative_tail   annihilation: nearest prior art, patent collision,
                        substitute products, customer indifference, physics
                        limits, unit-economics collapse, regulatory blocks,
                        manipulation risk, second-order externalities.
                        p_D3- = argmax E_falsification(p)
  D3-C  repaired_tail   final survivor must retain high constructive
                        deviation after the strongest destructive evidence
                        is applied:
                        z_survivor = z_positive − γ·E_falsification
                        survives iff z_survivor ≥ z_min AND E_total ≤ θ_D3
"""

from __future__ import annotations

import math

from .. import schemas
from . import DiamondHarness
from .expeditions import Expedition, ExpeditionOutcome

__all__ = [
    "ProofPositiveTail",
    "ProofNegativeTail",
    "ProofRepairedTail",
]


class _ProofBase(Expedition):
    diamond = schemas.DiamondKind.PROOF

    def objective(self) -> str:
        return {
            schemas.ExpeditionKind.POSITIVE_TAIL: (
                "Search for unusually strong evidence: behavioral, "
                "technical, and novelty proof."
            ),
            schemas.ExpeditionKind.NEGATIVE_TAIL: (
                "Annihilate the candidate via prior art, patent, "
                "substitute, customer indifference, physics, "
                "unit-economics, regulatory blocks, manipulation risk, "
                "second-order externalities."
            ),
            schemas.ExpeditionKind.REPAIRED_TAIL: (
                "Final survivor must retain high constructive deviation "
                "after the strongest destructive evidence is applied; "
                "z_survivor = z_positive − γ·E_falsification."
            ),
        }[self.kind]


class ProofPositiveTail(_ProofBase):
    def __init__(
        self,
        harness: DiamondHarness,
        *,
        behavioral_proof_z: float = 0.0,
        technical_proof_z: float = 0.0,
        novelty_proof_z: float = 0.0,
    ) -> None:
        super().__init__(harness, schemas.ExpeditionKind.POSITIVE_TAIL)
        self._b = behavioral_proof_z
        self._t = technical_proof_z
        self._n = novelty_proof_z

    def falsifier(self) -> str:
        return "Falsifier: candidate whose proof components sum below 3σ."

    def candidate_value(self) -> float:
        return self._b + self._t + self._n

    def structural_distance(self) -> float:
        return max(self._n, 0.0)

    def behavioral_distance(self) -> float:
        return max(self._b + self._t, 0.0) / 2.0


class ProofNegativeTail(_ProofBase):
    def __init__(
        self,
        harness: DiamondHarness,
        *,
        falsification_energy: float = 0.0,
    ) -> None:
        super().__init__(harness, schemas.ExpeditionKind.NEGATIVE_TAIL)
        # E_falsification is non-negative; bigger means the candidate is
        # *more* destroyed → negative-tail z gets more negative.
        self._e = falsification_energy

    def falsifier(self) -> str:
        return "Falsifier: candidate whose falsification energy is 0."

    def candidate_value(self) -> float:
        return -math.sqrt(self._e) if self._e > 0 else 0.0

    def structural_distance(self) -> float:
        return 0.0

    def behavioral_distance(self) -> float:
        return math.sqrt(self._e) if self._e > 0 else 0.0


class ProofRepairedTail(_ProofBase):
    def __init__(
        self,
        harness: DiamondHarness,
        *,
        positive_outcome: ExpeditionOutcome,
        negative_outcome: ExpeditionOutcome,
        gamma: float = 1.0,
        z_min: float = 5.0,
        theta_d3: float = 0.2,
    ) -> None:
        super().__init__(harness, schemas.ExpeditionKind.REPAIRED_TAIL)
        self.positive = positive_outcome
        self.negative = negative_outcome
        self.gamma = gamma
        self.z_min = z_min
        self.theta = theta_d3

    def falsifier(self) -> str:
        return (
            f"Falsifier: z_survivor < z_min ({self.z_min}) "
            f"OR E_total > θ_D3 ({self.theta})."
        )

    def candidate_value(self) -> float:
        z_pos = self.positive.certified_z
        e_fals = abs(self.negative.certified_z)  # |z| of the negative expedition
        # z_survivor = z_pos − γ·E_falsification
        return z_pos - self.gamma * e_fals

    def structural_distance(self) -> float:
        return self.positive.certified_z * 0.5

    def behavioral_distance(self) -> float:
        return self.positive.certified_z * 0.5
