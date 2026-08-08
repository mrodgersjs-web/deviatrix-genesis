"""Example 1 — Direct Python API.

Run a single D1 opportunity positive-tail expedition end-to-end and
print the resulting MathProofPacket as YAML-equivalent JSON.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

# Allow running from repo root.
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deviatrix_genesis import schemas
from deviatrix_genesis.diamonds import DiamondHarness
from deviatrix_genesis.diamonds.d1_opportunity import (
    OpportunityPositiveTail,
    OpportunityNegativeTail,
    OpportunityRepairedTail,
)
from deviatrix_genesis.diamonds.routing import band_for
from deviatrix_genesis.verifier import IndependentVerifier


def main() -> int:
    # A reference population: 500 normal samples
    rng = random.Random(42)
    pop = [rng.gauss(0, 1) for _ in range(500)]

    # The candidate formula (must parse cleanly through SymPy MCP)
    formula = "x**2 + 3*x + 1"
    claim = schemas.MathClaim(
        expression=formula,
        symbols=["x"],
        assumptions={},
        reference_population=pop,
        estimator="robust_madz",
        falsifier="certified_z < 3 after adversarial pass",
    )

    harness = DiamondHarness(diamond=schemas.DiamondKind.OPPORTUNITY)

    # 1. Positive-tail
    pos_exp = OpportunityPositiveTail(
        harness, transformation_z=6.0, orthodoxy_break_z=5.0, evidence_z=4.0
    )
    pos_outcome = pos_exp.run(claim)

    # 2. Negative-tail
    neg_exp = OpportunityNegativeTail(
        harness, behavioral_evidence_z=2.0, economic_viability_z=3.0
    )
    neg_outcome = neg_exp.run(claim)

    # 3. Repaired-tail (depends on pos + neg outcomes)
    rep_exp = OpportunityRepairedTail(
        harness, positive_outcome=pos_outcome, negative_outcome=neg_outcome
    )
    rep_outcome = rep_exp.run(claim)

    # 4. Verify all three packets
    v = IndependentVerifier(verifier_id="example-verifier")
    reports = [v.verify(o.packets[0]) for o in (pos_outcome, neg_outcome, rep_outcome)]

    # Pretty print
    for label, outcome, report in zip(
        ("positive_tail", "negative_tail", "repaired_tail"),
        (pos_outcome, neg_outcome, rep_outcome),
        reports,
    ):
        packet = outcome.packets[0]
        print("---", label, "---")
        print(f"  certified_z : {outcome.certified_z:.2f}")
        print(f"  band        : {band_for(outcome.certified_z)}")
        print(f"  pass_a      : {outcome.pass_a_status}")
        print(f"  pass_b      : {outcome.pass_b_status}")
        print(f"  pass_c      : {outcome.pass_c_status}")
        print(f"  verifier    : {report.decision.value}  ({report.reason[:60]})")
        print(f"  sealed_hash : {packet.sealed_hash}")
        print()

    # Full packet dump
    print("--- packet dump (first one) ---")
    print(json.dumps(pos_outcome.packets[0].to_dict(), indent=2, default=str)[:800] + "…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
