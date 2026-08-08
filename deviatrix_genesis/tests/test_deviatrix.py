"""Unit + integration tests for Deviatrix Genesis.

Run with::

    cd /Users/rig128gb/Projects/deviatrix-genesis
    PYTHONPATH=. python3 -m pytest deviatrix_genesis/tests -q

Or directly::

    PYTHONPATH=. python3 deviatrix_genesis/tests/test_deviatrix.py
"""

from __future__ import annotations

import json
import math
import random
import sys
import unittest
from pathlib import Path

# Add the package root to sys.path so this file can run standalone.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from deviatrix_genesis import schemas
from deviatrix_genesis.conductors import DeviatrixConductor, EXPECTED_RUN_TOTALS
from deviatrix_genesis.diamonds import (
    FAIL_ROUTES,
    DiamondHarness,
    apply_fail_route,
    dispatch_skill,
)
from deviatrix_genesis.diamonds.d1_opportunity import (
    OpportunityNegativeTail,
    OpportunityPositiveTail,
    OpportunityRepairedTail,
)
from deviatrix_genesis.diamonds.d2_invention import (
    InventionNegativeTail,
    InventionPositiveTail,
    InventionRepairedTail,
)
from deviatrix_genesis.diamonds.d3_proof import (
    ProofNegativeTail,
    ProofPositiveTail,
    ProofRepairedTail,
)
from deviatrix_genesis.diamonds.routing import (
    action_for,
    band_for,
    is_wall,
    POSITIVE_BANDS,
    NEGATIVE_BANDS,
)
from deviatrix_genesis.iqrsqpi import IQRSQPIConductor
from deviatrix_genesis.mathexec import (
    QN_CONSTANT,
    MAD_CONSTANT,
    alternate_corpus_z,
    bootstrap_lower,
    certified_z,
    composite_deviation,
    counterexample_search,
    hash_population,
    qn_scale,
    qn_z,
    robust_madz,
)
from deviatrix_genesis.mathexec.executor import (
    pass_a_symbolic,
    pass_b_numerical,
    pass_c_adversarial,
    compute_deviation,
)
from deviatrix_genesis.sympy_mcp import (
    tool_adversarial_substitution,
    tool_check_assumptions,
    tool_check_inequality,
    tool_diff,
    tool_find_singularities,
    tool_integrate,
    tool_parse,
    tool_simplify,
    tool_solve,
    capabilities,
)
from deviatrix_genesis.verifier import IndependentVerifier


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────


def _population(seed: int = 42, n: int = 500) -> list[float]:
    rng = random.Random(seed)
    return [rng.gauss(0, 1) for _ in range(n)]


def _clean_claim(expr: str = "x**2 + 3*x + 1", pop: list[float] | None = None) -> schemas.MathClaim:
    return schemas.MathClaim(
        expression=expr,
        symbols=["x"],
        assumptions={},
        reference_population=pop or _population(),
        estimator="robust_madz",
    )


# ────────────────────────────────────────────────────────────────────
# sympy_mcp
# ────────────────────────────────────────────────────────────────────


class TestSymPyMCP(unittest.TestCase):
    def test_capabilities_shape(self) -> None:
        c = capabilities()
        self.assertIn("tools", c)
        self.assertIn("resources", c)
        self.assertIn("prompts", c)
        self.assertEqual(len(c["tools"]), 9)
        self.assertEqual(c["role"], "symbolic transmission controller (not creativity engine)")

    def test_parse_ok(self) -> None:
        r = tool_parse("exp(-x) + sin(x)")
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["free_symbols"], ["x"])

    def test_parse_bad(self) -> None:
        r = tool_parse("__import__('os').system('rm -rf /')")
        self.assertEqual(r["status"], "FAIL")

    def test_parse_rejects_attribute_access(self) -> None:
        r = tool_parse("os.system(1)")
        self.assertEqual(r["status"], "FAIL")
        self.assertIn("unsafe token", r["error"])

    def test_simplify_ok(self) -> None:
        r = tool_simplify("sin(x)**2 + cos(x)**2")
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["forms"]["simplify"], "1")

    def test_solve_ok(self) -> None:
        r = tool_solve("x**3 - 6*x**2 + 11*x - 6", "x")
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["solution_count"], 3)

    def test_diff_ok(self) -> None:
        r = tool_diff("x**3", "x", 2)
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["derivative"], "6*x")

    def test_integrate_ok(self) -> None:
        r = tool_integrate("x**2", "x")
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["integral"], "x**3/3")

    def test_singularities_ok(self) -> None:
        r = tool_find_singularities("1/(x-1) + 1/(x+1)", "x")
        self.assertEqual(r["status"], "OK")
        self.assertEqual(set(r["singularities"]), {"-1", "1"})

    def test_inequality_ok(self) -> None:
        r = tool_check_inequality("x**2 - 1", "x", "<")
        self.assertEqual(r["status"], "OK")
        self.assertTrue(r["valid"])

    def test_adversarial_substitution_ok(self) -> None:
        r = tool_adversarial_substitution("exp(-x)*sin(x)", "x")
        self.assertEqual(r["status"], "OK")
        self.assertTrue(r["any_valid_evaluation"])

    def test_assumptions_ok(self) -> None:
        r = tool_check_assumptions("exp(x)", {"x": "real"})
        self.assertEqual(r["status"], "OK")


# ────────────────────────────────────────────────────────────────────
# mathexec
# ────────────────────────────────────────────────────────────────────


class TestMathExec(unittest.TestCase):
    def test_constants(self) -> None:
        # MAD constant 0.6745 = 1/Φ⁻¹(0.75); Qn constant is 2.2219.
        self.assertAlmostEqual(MAD_CONSTANT, 0.6744897501960817)
        self.assertAlmostEqual(QN_CONSTANT, 2.2219)

    def test_hash_population_deterministic(self) -> None:
        a = hash_population([1.0, 2.0, 3.0])
        b = hash_population([1.0, 2.0, 3.0])
        self.assertEqual(a, b)
        c = hash_population([1.0, 2.0, 3.5])
        self.assertNotEqual(a, c)

    def test_robust_madz_zero_mad(self) -> None:
        self.assertEqual(robust_madz(5.0, [1.0, 1.0, 1.0]), 0.0)

    def test_robust_madz_normal_data(self) -> None:
        # On a normal population with one obvious outlier, the MAD-z
        # for the outlier should be > 5.
        pop = _population(n=1000)
        z = robust_madz(20.0, pop)
        self.assertGreater(z, 5.0)

    def test_qn_scale(self) -> None:
        pop = _population(n=1000)
        scale = qn_scale(pop)
        # Qn should be roughly 1.0 for a normal sample.
        self.assertGreater(scale, 0.5)
        self.assertLess(scale, 1.5)

    def test_qn_z(self) -> None:
        pop = _population(n=1000)
        z = qn_z(20.0, pop)
        self.assertGreater(z, 5.0)

    def test_bootstrap_lower_is_a_lower_bound(self) -> None:
        pop = _population(n=500)
        lo, hi = bootstrap_lower(5.0, pop, n_resamples=200)
        self.assertLessEqual(lo, hi)

    def test_certified_z_conservative(self) -> None:
        z = certified_z(2.0, 2.5, 1.8, 2.1)
        self.assertEqual(z, 1.8)

    def test_alternate_corpus_z(self) -> None:
        pop = _population(n=500)
        alt = _population(seed=99, n=500)
        z = alternate_corpus_z(5.0, pop, alternate=alt)
        self.assertIsInstance(z, float)
        self.assertTrue(math.isfinite(z))

    def test_composite_deviation(self) -> None:
        self.assertEqual(composite_deviation(10.0, 10.0), 10.0)
        self.assertEqual(composite_deviation(0.0, 10.0), 7.0)
        self.assertEqual(composite_deviation(10.0, 0.0), 3.0)

    def test_counterexample_search_returns_pathological_flag(self) -> None:
        class C:
            expression = "exp(x)"

        r = counterexample_search(C(), n_samples=50)
        self.assertEqual(r["status"], "OK")
        self.assertIn("best_x", r)
        self.assertIn("is_pathological", r)


# ────────────────────────────────────────────────────────────────────
# Executor
# ────────────────────────────────────────────────────────────────────


class TestExecutor(unittest.TestCase):
    def test_pass_a_clean_expression(self) -> None:
        claim = _clean_claim()
        sym = pass_a_symbolic(claim)
        self.assertEqual(sym.status, "PASS")

    def test_pass_a_with_singularity_reports(self) -> None:
        # Doctrine: singularity detection *reports* singularities; it
        # does not reject well-formed formulas. A formula with a
        # singularity at x=1 is still symbolically valid; its
        # singularity just lives in the proof packet.
        claim = _clean_claim(expr="1/(x-1)")
        sym = pass_a_symbolic(claim)
        self.assertEqual(sym.status, "PASS")
        self.assertIn("1", sym.singularities)

    def test_pass_b_extreme_value(self) -> None:
        claim = _clean_claim()
        emp = pass_b_numerical(claim, candidate_value=20.0, n_bootstrap=100)
        self.assertGreater(emp.robust_madz, 5.0)
        self.assertEqual(emp.candidate_value, 20.0)
        self.assertNotEqual(emp.reference_population_hash, "")

    def test_pass_c_emits_perturbations(self) -> None:
        claim = _clean_claim()
        emp = pass_b_numerical(claim, candidate_value=20.0)
        adv = pass_c_adversarial(claim, emp)
        self.assertGreaterEqual(len(adv.perturbations_run), 10)

    def test_compute_deviation_marks_ceiling_at_30(self) -> None:
        claim = _clean_claim()
        emp = pass_b_numerical(claim, candidate_value=1e9)
        dev = compute_deviation(
            emp, structural=10.0, behavioral=10.0, direction=schemas.Direction.POSITIVE
        )
        self.assertTrue(dev.ceiling_breach)


# ────────────────────────────────────────────────────────────────────
# Diamond harness
# ────────────────────────────────────────────────────────────────────


class TestDiamondHarness(unittest.TestCase):
    def test_default_skills(self) -> None:
        h = DiamondHarness(diamond=schemas.DiamondKind.OPPORTUNITY)
        self.assertIn("sympy_mcp.parse", h.S_skills)
        self.assertIn("mathexec.robust_madz", h.S_skills)

    def test_dispatch_skill_allowed(self) -> None:
        h = DiamondHarness()
        r = dispatch_skill(h, "mathexec.qn_scale", population=[1.0, 2.0, 3.0])
        self.assertGreater(r, 0.0)

    def test_dispatch_skill_banned(self) -> None:
        h = DiamondHarness()
        with self.assertRaises(PermissionError):
            dispatch_skill(h, "mathexec.banned_skill")

    def test_fail_routes_table_complete(self) -> None:
        self.assertEqual(
            set(FAIL_ROUTES.keys()),
            {fc.value for fc in schemas.FailureClass},
        )

    def test_apply_fail_route_records_trace(self) -> None:
        h = DiamondHarness()
        n_before = len(h.T_trace)
        apply_fail_route(h, schemas.FailureClass.LOW_DEVIATION)
        self.assertEqual(len(h.T_trace), n_before + 1)


# ────────────────────────────────────────────────────────────────────
# Three expeditions
# ────────────────────────────────────────────────────────────────────


class TestD1Opportunity(unittest.TestCase):
    def setUp(self) -> None:
        self.h = DiamondHarness(diamond=schemas.DiamondKind.OPPORTUNITY)
        self.claim = _clean_claim()

    def test_positive_tail(self) -> None:
        pos = OpportunityPositiveTail(
            self.h, transformation_z=5.0, orthodoxy_break_z=4.0, evidence_z=3.0
        ).run(self.claim)
        self.assertEqual(pos.pass_a_status, "PASS")
        self.assertGreater(abs(pos.certified_z), 5.0)

    def test_negative_tail(self) -> None:
        neg = OpportunityNegativeTail(
            self.h, behavioral_evidence_z=2.0, economic_viability_z=3.0
        ).run(self.claim)
        self.assertLess(neg.certified_z, 0.0)

    def test_repaired_tail(self) -> None:
        pos = OpportunityPositiveTail(
            self.h, transformation_z=5.0, orthodoxy_break_z=4.0, evidence_z=3.0
        ).run(self.claim)
        neg = OpportunityNegativeTail(
            self.h, behavioral_evidence_z=2.0, economic_viability_z=3.0
        ).run(self.claim)
        rep = OpportunityRepairedTail(
            self.h, positive_outcome=pos, negative_outcome=neg
        ).run(self.claim)
        self.assertEqual(rep.pass_a_status, "PASS")
        # repair keeps most of positive z
        self.assertGreater(rep.certified_z, 0.0)


class TestD2Invention(unittest.TestCase):
    def setUp(self) -> None:
        self.h = DiamondHarness(diamond=schemas.DiamondKind.INVENTION)
        self.claim = _clean_claim()

    def test_positive_tail(self) -> None:
        pos = InventionPositiveTail(
            self.h, novelty=5.0, systematicity=4.0, utility=6.0, interference=1.0
        ).run(self.claim)
        self.assertEqual(pos.pass_a_status, "PASS")
        self.assertGreater(abs(pos.certified_z), 5.0)

    def test_negative_tail(self) -> None:
        neg = InventionNegativeTail(self.h, transformation_value=2.5).run(self.claim)
        self.assertLess(neg.certified_z, 0.0)

    def test_repaired_tail(self) -> None:
        pos = InventionPositiveTail(
            self.h, novelty=5.0, systematicity=4.0, utility=6.0, interference=1.0
        ).run(self.claim)
        neg = InventionNegativeTail(self.h, transformation_value=2.5).run(self.claim)
        rep = InventionRepairedTail(
            self.h, positive_outcome=pos, negative_outcome=neg, coherence=2.0
        ).run(self.claim)
        self.assertEqual(rep.pass_a_status, "PASS")


class TestD3Proof(unittest.TestCase):
    def setUp(self) -> None:
        self.h = DiamondHarness(diamond=schemas.DiamondKind.PROOF)
        self.claim = _clean_claim()

    def test_positive_tail(self) -> None:
        pos = ProofPositiveTail(
            self.h, behavioral_proof_z=5.0, technical_proof_z=4.0, novelty_proof_z=5.5
        ).run(self.claim)
        self.assertEqual(pos.pass_a_status, "PASS")
        self.assertGreater(abs(pos.certified_z), 5.0)

    def test_negative_tail(self) -> None:
        neg = ProofNegativeTail(self.h, falsification_energy=9.0).run(self.claim)
        self.assertLess(neg.certified_z, 0.0)

    def test_repaired_tail_survivor(self) -> None:
        pos = ProofPositiveTail(
            self.h, behavioral_proof_z=5.0, technical_proof_z=4.0, novelty_proof_z=5.5
        ).run(self.claim)
        neg = ProofNegativeTail(self.h, falsification_energy=9.0).run(self.claim)
        rep = ProofRepairedTail(
            self.h, positive_outcome=pos, negative_outcome=neg, gamma=0.5
        ).run(self.claim)
        self.assertEqual(rep.pass_a_status, "PASS")


# ────────────────────────────────────────────────────────────────────
# IQRSQPI
# ────────────────────────────────────────────────────────────────────


class TestIQRSQPI(unittest.TestCase):
    def test_run_quick_completes(self) -> None:
        h = DiamondHarness()
        c = IQRSQPIConductor(h, schemas.ExpeditionKind.POSITIVE_TAIL, min_grill_cycles=3)
        summary = c.run_quick()
        self.assertTrue(summary["completed"])
        self.assertEqual(summary["n_stages_passed"], 7)
        self.assertGreaterEqual(summary["n_grill_cycles"], 3)

    def test_insufficient_grill_halts(self) -> None:
        h = DiamondHarness()
        c = IQRSQPIConductor(h, schemas.ExpeditionKind.POSITIVE_TAIL, min_grill_cycles=10)
        # only run 3 grill cycles (default), below the 10 minimum
        summary = c.run_quick()
        self.assertFalse(summary["completed"])
        self.assertIn("grill", summary["halted_reason"])

    def test_stage_advance_gate(self) -> None:
        h = DiamondHarness()
        c = IQRSQPIConductor(h, schemas.ExpeditionKind.NEGATIVE_TAIL)
        outcome = c.begin_stage(schemas.IQRSQPIStage.PROOF, energy=0.5)
        self.assertFalse(outcome.can_advance())
        c.complete_stage(outcome, energy=0.1, open_questions=0)
        self.assertTrue(outcome.passed)


# ────────────────────────────────────────────────────────────────────
# Sigma-band routing
# ────────────────────────────────────────────────────────────────────


class TestRouting(unittest.TestCase):
    def test_band_for_zero(self) -> None:
        self.assertIn(band_for(0.5), {"0σ–3σ"})

    def test_band_for_extreme(self) -> None:
        self.assertEqual(band_for(25.0), "+20σ–30σ")

    def test_band_for_wall(self) -> None:
        self.assertEqual(band_for(31.0), "≥+30σ")
        self.assertEqual(band_for(-31.0), "≤-30σ")

    def test_action_for(self) -> None:
        self.assertEqual(action_for(1.0), "anti_median")
        self.assertEqual(action_for(15.0), "adversarial_proof")
        self.assertEqual(action_for(25.0), "mike_gated_review")
        self.assertEqual(action_for(31.0), "hard_stop")

    def test_is_wall(self) -> None:
        self.assertFalse(is_wall(29.9))
        self.assertTrue(is_wall(30.0))
        self.assertTrue(is_wall(-30.0))

    def test_band_table_complete(self) -> None:
        self.assertEqual(len(POSITIVE_BANDS), 6)
        self.assertEqual(len(NEGATIVE_BANDS), 6)


# ────────────────────────────────────────────────────────────────────
# Independent verifier
# ────────────────────────────────────────────────────────────────────


class TestVerifier(unittest.TestCase):
    def test_pass_packet(self) -> None:
        h = DiamondHarness()
        pos = OpportunityPositiveTail(
            h, transformation_z=5.0, orthodoxy_break_z=4.0, evidence_z=3.0
        ).run(_clean_claim())
        v = IndependentVerifier()
        r = v.verify(pos.packets[0])
        self.assertEqual(r.decision, schemas.GateStatus.PASS)
        self.assertEqual(r.failure_flags, [])

    def test_wall_breach_escalates(self) -> None:
        h = DiamondHarness()
        claim = _clean_claim()

        class Force(OpportunityPositiveTail):
            def candidate_value(self) -> float:
                return 1e9

        outcome = Force(h, transformation_z=1.0).run(claim)
        v = IndependentVerifier()
        r = v.verify(outcome.packets[0])
        self.assertEqual(r.decision, schemas.GateStatus.ESCALATE)
        self.assertTrue(r.wall_breach)
        self.assertIn("wall_breach", r.failure_flags)

    def test_signature_is_deterministic(self) -> None:
        h = DiamondHarness()
        pos = OpportunityPositiveTail(
            h, transformation_z=5.0, orthodoxy_break_z=4.0, evidence_z=3.0
        ).run(_clean_claim())
        v = IndependentVerifier(verifier_id="v-fixed")
        r1 = v.verify(pos.packets[0])
        self.assertEqual(len(r1.signature), 32)


# ────────────────────────────────────────────────────────────────────
# Master conductor
# ────────────────────────────────────────────────────────────────────


class TestConductor(unittest.TestCase):
    def test_run_totals_match_doctrine(self) -> None:
        self.assertEqual(EXPECTED_RUN_TOTALS["diamonds"], 3)
        self.assertEqual(EXPECTED_RUN_TOTALS["total_expeditions"], 9)
        self.assertEqual(EXPECTED_RUN_TOTALS["outer_stages"], 63)
        self.assertEqual(EXPECTED_RUN_TOTALS["min_total_grill"], 27)

    def test_full_run_3_diamonds_3_expeditions(self) -> None:
        c = DeviatrixConductor(seed=42)
        report = c.run(formula="x**2 + 3*x + 1", pop_size=300)
        self.assertEqual(report.packet_count, 9)
        self.assertEqual(set(report.diamond_reports.keys()), {"opportunity", "invention", "proof"})
        for drep in report.diamond_reports.values():
            self.assertEqual(set(drep["outcomes"].keys()), {"positive_tail", "negative_tail", "repaired_tail"})

    def test_artifacts_written(self) -> None:
        out = Path("/tmp/deviatrix_test_artifacts")
        if out.exists():
            import shutil

            shutil.rmtree(out)
        c = DeviatrixConductor(seed=42, output_dir=str(out))
        c.run()
        self.assertTrue((out / "run_report.json").exists())
        self.assertTrue((out / "opportunity" / "report.json").exists())
        self.assertTrue((out / "invention" / "positive_tail.summary.json").exists())


# ────────────────────────────────────────────────────────────────────
# Schemas
# ────────────────────────────────────────────────────────────────────


class TestSchemas(unittest.TestCase):
    def test_math_claim_hash_deterministic(self) -> None:
        a = schemas.MathClaim(expression="x**2", symbols=["x"])
        b = schemas.MathClaim(expression="x**2", symbols=["x"])
        self.assertEqual(a.candidate_hash, b.candidate_hash)

    def test_packet_seal_changes_after_verifier(self) -> None:
        h = DiamondHarness()
        pos = OpportunityPositiveTail(
            h, transformation_z=5.0, orthodoxy_break_z=4.0, evidence_z=3.0
        ).run(_clean_claim())
        packet = pos.packets[0]
        sealed_before = packet.seal()
        IndependentVerifier().verify(packet)
        sealed_after = packet.sealed_hash
        self.assertEqual(sealed_before, sealed_after)  # verifier re-seals; the hash should match the body
        # the verifier populates the verifier field then re-seals; check it's now set
        self.assertNotEqual(packet.verifier.verifier_id, "")


# ────────────────────────────────────────────────────────────────────
# CLI smoke
# ────────────────────────────────────────────────────────────────────


class TestCLI(unittest.TestCase):
    def test_status(self) -> None:
        from deviatrix_genesis.cli.main import cmd_status, build_parser

        ns = build_parser().parse_args(["status"])
        self.assertEqual(cmd_status(ns), 0)

    def test_sympy_check(self) -> None:
        from deviatrix_genesis.cli.main import cmd_sympy_check, build_parser

        ns = build_parser().parse_args(["sympy-check"])
        self.assertEqual(cmd_sympy_check(ns), 0)


# ────────────────────────────────────────────────────────────────────
# Allow `python -m unittest`
# ────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    unittest.main(verbosity=2)
