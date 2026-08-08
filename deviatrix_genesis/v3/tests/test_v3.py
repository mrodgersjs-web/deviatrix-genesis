"""Tests for Deviatrix Genesis v3.

Run with::

    PYTHONPATH=. python3 -m unittest deviatrix_genesis.v3.tests.test_v3 -v

These tests exercise the corpus_loader, proposer, collision engine,
calibration loop, ensemble, and Memory OS adapter without spinning
up the full 3×3×7 conductor (which is slow).

The full pipeline is exercised by ``test_pipeline_smoke``.
"""

from __future__ import annotations

import os
import statistics
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from deviatrix_genesis.v3.collision import fuse_survivors, HybridIdea
from deviatrix_genesis.v3.corpus_loader import (
    KNOWN_MECHANISM_PATTERNS,
    build_known_archetype_population,
    build_reference_population,
    load_corpus,
    load_gtm_substrate_corpus,
    load_jake_studio_corpus,
    load_memory_os_corpus,
    load_prior_run_corpus,
    score_corpus_entry,
)
from deviatrix_genesis.v3.proposer import (
    GTMIdea,
    TEMPLATES,
    propose_from_brief,
    render_idea,
)


# ────────────────────────────────────────────────────────────────────
# corpus_loader
# ────────────────────────────────────────────────────────────────────


class TestCorpusLoader(unittest.TestCase):
    def test_known_mechanism_patterns_nonempty(self) -> None:
        self.assertGreater(len(KNOWN_MECHANISM_PATTERNS), 5)

    def test_load_memory_os_returns_list(self) -> None:
        # Even if DB is missing, this should not raise.
        out = load_memory_os_corpus()
        self.assertIsInstance(out, list)

    def test_score_corpus_entry_returns_three_keys(self) -> None:
        from deviatrix_genesis.v3.corpus_loader import CorpusEntry

        entry = CorpusEntry(
            text="This is a sample corpus entry about escrow and verification.",
            source="test",
        )
        scores = score_corpus_entry(entry, [entry])
        self.assertEqual(set(scores.keys()), {"anti_orthodoxy", "mechanism_originality", "prior_art_distance"})

    def test_score_corpus_entry_mechanism_hits(self) -> None:
        from deviatrix_genesis.v3.corpus_loader import CorpusEntry

        # An entry that explicitly mentions "escrow" and "verifier"
        # should have non-zero mechanism_originality.
        a = CorpusEntry(text="escrow and verifier here", source="test")
        b = CorpusEntry(text="escrow", source="test")
        scores_a = score_corpus_entry(a, [a, b])
        self.assertGreater(scores_a["mechanism_originality"], 0)

    def test_build_reference_population_shape(self) -> None:
        from deviatrix_genesis.v3.corpus_loader import CorpusEntry

        corpus = [
            CorpusEntry(text=f"item {i} about escrow and verifier", source="test")
            for i in range(20)
        ]
        pop = build_reference_population(corpus, n=200, seed=2026)
        self.assertGreater(len(pop), 100)
        # median should be > 0 because real-corpus entries contribute
        self.assertGreater(statistics.median(pop), 0.0)

    def test_build_known_archetype_population_tight(self) -> None:
        from deviatrix_genesis.v3.corpus_loader import CorpusEntry

        corpus = [CorpusEntry(text="x", source="test") for _ in range(5)]
        pop = build_known_archetype_population(corpus, n=200, seed=2026)
        self.assertGreater(len(pop), 100)
        # MAD should be small (0.05 noise)
        med = statistics.median(pop)
        mad = statistics.median(abs(v - med) for v in pop)
        self.assertLess(mad, 0.2)

    def test_load_corpus_aggregates_all_sources(self) -> None:
        out = load_corpus()
        self.assertIsInstance(out, list)
        # If substrate or logs exist, the corpus should have entries
        if Path("~/.rig/departments").expanduser().exists():
            self.assertGreater(len(out), 0)


# ────────────────────────────────────────────────────────────────────
# proposer
# ────────────────────────────────────────────────────────────────────


class TestProposer(unittest.TestCase):
    def test_templates_complete(self) -> None:
        self.assertEqual(len(TEMPLATES), 9)
        for t in TEMPLATES:
            self.assertIn("name", t)
            self.assertIn("formula", t)
            self.assertIn("falsifier", t)
            self.assertIn("mechanism_family", t)

    def test_propose_from_brief_returns_n_ideas(self) -> None:
        ideas = propose_from_brief("Operator-first GTM with financial primitives", corpus=[], n=5)
        self.assertEqual(len(ideas), 5)
        for idea in ideas:
            self.assertIsInstance(idea, GTMIdea)
            self.assertGreater(idea.anti_orthodoxy_new, 0.0)
            self.assertGreater(idea.prior_art_distance_new, 0.0)

    def test_propose_ranks_by_brief_match(self) -> None:
        ideas_a = propose_from_brief("escrow verifier outcome", corpus=[], n=3)
        ideas_b = propose_from_brief("reputation portable signed", corpus=[], n=3)
        names_a = [i.name for i in ideas_a]
        names_b = [i.name for i in ideas_b]
        # Outcome-Escrow should appear in ideas_a; Operator-Reputation Primitive in ideas_b.
        self.assertTrue(any("Outcome-Escrow" in n for n in names_a))
        self.assertTrue(any("Operator-Reputation" in n for n in names_b))


# ────────────────────────────────────────────────────────────────────
# collision
# ────────────────────────────────────────────────────────────────────


class TestCollision(unittest.TestCase):
    def test_fuse_survivors_produces_hybrids(self) -> None:
        ideas = [
            GTMIdea(
                name=f"idea-{i}",
                formula="x",
                falsifier="",
                closest_known_archetype=None,
                mechanism_family=fam,
                owner_dept="gtm",
                action_90d="",
            )
            for i, fam in enumerate([
                "independent_verification",
                "inverted_market",
                "portable_reputation",
                "yield_curve",
            ])
        ]
        hybrids = fuse_survivors(ideas, n_hybrids=3)
        self.assertEqual(len(hybrids), 3)
        for h in hybrids:
            self.assertIsInstance(h, HybridIdea)
            self.assertEqual(len(h.parents), 2)
            # Parents must come from different families
            self.assertNotEqual(h.parent_families[0], h.parent_families[1])

    def test_fuse_skips_same_family(self) -> None:
        # Two ideas with the same family should not fuse.
        ideas = [
            GTMIdea(name="a", formula="", falsifier="", closest_known_archetype=None,
                    mechanism_family="independent_verification", owner_dept="gtm", action_90d=""),
            GTMIdea(name="b", formula="", falsifier="", closest_known_archetype=None,
                    mechanism_family="independent_verification", owner_dept="gtm", action_90d=""),
        ]
        hybrids = fuse_survivors(ideas, n_hybrids=1)
        self.assertEqual(len(hybrids), 0)


# ────────────────────────────────────────────────────────────────────
# calibration
# ────────────────────────────────────────────────────────────────────


class TestCalibration(unittest.TestCase):
    def test_calibrate_empty_history_returns_defaults(self) -> None:
        from deviatrix_genesis.v3.calibration import calibrate

        cal = calibrate([])
        self.assertIn("ao_input", cal)
        self.assertIn("mo_input", cal)
        self.assertIn("pa_input", cal)
        for v in cal["ao_input"].values():
            self.assertEqual(v, 4.5)

    def test_propose_calibrated_scores_returns_three_keys(self) -> None:
        from deviatrix_genesis.v3.calibration import propose_calibrated_scores

        scores = propose_calibrated_scores([])
        self.assertEqual(set(scores.keys()), {"anti_orthodoxy_new", "mechanism_originality_new", "prior_art_distance_new"})

    def test_fit_linear(self) -> None:
        from deviatrix_genesis.v3.calibration import _fit_linear

        # Perfect linear data
        a, b = _fit_linear([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0])
        self.assertAlmostEqual(a, 2.0)
        self.assertAlmostEqual(b, 0.0)


# ────────────────────────────────────────────────────────────────────
# memory_os
# ────────────────────────────────────────────────────────────────────


class TestMemoryOSAdapter(unittest.TestCase):
    def test_payload_shape(self) -> None:
        from deviatrix_genesis.v3.memory_os import _build_memory_payload

        payload = _build_memory_payload(
            idea_name="test idea",
            formula="x**2",
            falsifier="any failure",
            composite_z=15.0,
            archetype_z=5.0,
            is_respin=False,
            mechanism_family="test",
            parent_names=None,
            action_90d="run 90 days",
            run_id="run-001",
        )
        self.assertEqual(payload["memory_type"], "procedural")
        self.assertEqual(payload["source_type"], "model_synthesized")
        self.assertEqual(payload["sensitivity"], "internal")
        self.assertIn("content", payload)
        self.assertIn("confidence", payload)
        # confidence is between 0 and 1
        self.assertGreaterEqual(payload["confidence"], 0.0)
        self.assertLessEqual(payload["confidence"], 1.0)

    def test_read_prior_memories_safe_with_missing_db(self) -> None:
        from deviatrix_genesis.v3.memory_os import read_prior_memories

        # Missing DB should return [] not raise.
        out = read_prior_memories(db_path="/nonexistent/path/memory.db")
        self.assertEqual(out, [])


# ────────────────────────────────────────────────────────────────────
# ensemble (skip slow runs in CI; just smoke)
# ────────────────────────────────────────────────────────────────────


class TestEnsembleSmoke(unittest.TestCase):
    def test_ensemble_with_1_seed(self) -> None:
        from deviatrix_genesis.v3.ensemble import run_ensemble

        result = run_ensemble(
            brief="Operator-first GTM with financial primitives",
            n_seeds=1,
            n_hybrids=2,
        )
        self.assertGreater(len(result.survivors), 0)
        self.assertGreaterEqual(len(result.hybrids), 0)


# ────────────────────────────────────────────────────────────────────
# full pipeline smoke
# ────────────────────────────────────────────────────────────────────


class TestPipelineSmoke(unittest.TestCase):
    def test_pipeline_runs(self) -> None:
        from deviatrix_genesis.v3.pipeline import run_pipeline

        # Use a small n_seeds for the smoke. The pipeline produces
        # artifacts only when out_dir is set.
        result = run_pipeline(
            brief="Operator-first GTM with doctrine-yield primitives",
            n_seeds=1,
            n_hybrids=1,
            write_to_memory_os=False,
            out_dir=None,
        )
        self.assertIn("brief", result)
        self.assertIn("survivors", result)
        self.assertGreater(len(result["survivors"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
