"""Diamond 1 — Opportunity deviation.

Three expeditions:

  D1-A  positive_tail   search for opportunities far above the market median
                        in: transformation intensity, unserved demand,
                            workaround cost, orthodoxy fragility,
                            discontinuity magnitude, stranded-asset potential
  D1-B  negative_tail   search for needs people claim but do not act on,
                        markets sustained by subsidy/fashion, etc.
  D1-C  repaired_tail   crash positive against strongest negative objection,
                        emit contradiction-repaired candidate.

Objective (positive):

  o_D1+ = argmax_o [ z_transformation + z_orthodoxy_break + z_evidence ]
  subject to E_mechanism ≤ θ_D1

Objective (negative):

  o_D1- = argmin_o [ z_behavioral_evidence + z_economic_viability ]
"""

from __future__ import annotations

import math

from .. import schemas
from . import DiamondHarness
from .expeditions import Expedition, ExpeditionOutcome

__all__ = [
    "OpportunityPositiveTail",
    "OpportunityNegativeTail",
    "OpportunityRepairedTail",
]


class _OpportunityBase(Expedition):
    diamond = schemas.DiamondKind.OPPORTUNITY

    def objective(self) -> str:
        return {
            schemas.ExpeditionKind.POSITIVE_TAIL: (
                "Search for opportunities far above the market median in "
                "transformation intensity, unserved demand, workaround cost, "
                "orthodoxy fragility, discontinuity magnitude, stranded-asset potential."
            ),
            schemas.ExpeditionKind.NEGATIVE_TAIL: (
                "Search for needs people claim but do not act on, "
                "markets sustained by subsidy or fashion, customer requests "
                "that destroy value, orthodoxies whose inversion is worse, "
                "trends that cancel one another, opportunities already overfit "
                "by competitors."
            ),
            schemas.ExpeditionKind.REPAIRED_TAIL: (
                "Crash the positive opportunity against its strongest "
                "negative-tail objection; emit contradiction-repaired candidate."
            ),
        }[self.kind]


class OpportunityPositiveTail(_OpportunityBase):
    """D1-A — constructive category-creating candidates."""

    def __init__(
        self,
        harness: DiamondHarness,
        *,
        transformation_z: float = 0.0,
        orthodoxy_break_z: float = 0.0,
        evidence_z: float = 0.0,
    ) -> None:
        super().__init__(harness, schemas.ExpeditionKind.POSITIVE_TAIL)
        self._z_trans = transformation_z
        self._z_orth = orthodoxy_break_z
        self._z_evid = evidence_z

    def falsifier(self) -> str:
        return (
            "Falsifier: candidate whose certified_z falls below 3σ after "
            "anti-median pass, or whose mechanism energy exceeds θ_D1."
        )

    def candidate_value(self) -> float:
        # composite positive score, mapped to a z magnitude
        return (
            math.sqrt(self._z_trans ** 2 + self._z_orth ** 2 + self._z_evid ** 2)
            + self._z_trans
            + self._z_orth
            + self._z_evid
        )

    def structural_distance(self) -> float:
        return max(self._z_orth, 0.0)

    def behavioral_distance(self) -> float:
        return max(self._z_trans + self._z_evid, 0.0) / 2.0


class OpportunityNegativeTail(_OpportunityBase):
    """D1-B — anti-opportunities (the anti-map)."""

    def __init__(
        self,
        harness: DiamondHarness,
        *,
        behavioral_evidence_z: float = 0.0,
        economic_viability_z: float = 0.0,
    ) -> None:
        super().__init__(harness, schemas.ExpeditionKind.NEGATIVE_TAIL)
        # negative-tail z is the *negation* of how strong the anti-map signal is
        self._b_z = behavioral_evidence_z
        self._e_z = economic_viability_z

    def falsifier(self) -> str:
        return "Falsifier: anti-opportunity whose certified_z is above -3σ."

    def candidate_value(self) -> float:
        # The candidate sits at a low z; the negative expedition reports
        # the negation so its band mirrors the positive side.
        return -(self._b_z + self._e_z) / 2.0

    def structural_distance(self) -> float:
        return max(-self._e_z, 0.0)

    def behavioral_distance(self) -> float:
        return max(-self._b_z, 0.0)


class OpportunityRepairedTail(_OpportunityBase):
    """D1-C — repaired candidate after pos/neg crash."""

    def __init__(
        self,
        harness: DiamondHarness,
        *,
        positive_outcome: ExpeditionOutcome,
        negative_outcome: ExpeditionOutcome,
    ) -> None:
        super().__init__(harness, schemas.ExpeditionKind.REPAIRED_TAIL)
        self.positive = positive_outcome
        self.negative = negative_outcome

    def falsifier(self) -> str:
        return (
            "Falsifier: repaired candidate whose post-crash certified_z "
            "is below the pre-crash z, OR whose mechanism_energy > θ_D1."
        )

    def candidate_value(self) -> float:
        # Repair keeps most of the positive z, sheds more of the destructive
        # part. 0.3 (not 0.5) prevents the repair from re-scaling the
        # positive-tail magnitude past the ±30σ wall.
        z_pos = self.positive.certified_z
        z_neg = self.negative.certified_z  # negative
        return z_pos + 0.3 * z_neg

    def structural_distance(self) -> float:
        return max(self.positive.certified_z, 0.0) * 0.6

    def behavioral_distance(self) -> float:
        return max(self.positive.certified_z, 0.0) * 0.4
