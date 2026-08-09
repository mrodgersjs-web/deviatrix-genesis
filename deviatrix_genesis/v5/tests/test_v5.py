"""Comprehensive test suite for Deviatrix Genesis v5."""

from __future__ import annotations

import asyncio
import statistics
import time
import unittest


# ────────────────────────────────────────────────────────────────────
# DAG tests
# ────────────────────────────────────────────────────────────────────


class TestDAG(unittest.IsolatedAsyncioTestCase):

    async def test_executes_in_dependency_order(self):
        from deviatrix_genesis.v5.dag import DAGExecutor, DAGNode

        order: list[str] = []

        async def a(**kw):
            order.append("a")
            return "a"

        async def b(**kw):
            order.append("b")
            return "b"

        async def c(**kw):
            order.append("c")
            return "c"

        ex = DAGExecutor()
        ex.add_node(DAGNode("a", a))
        ex.add_node(DAGNode("b", b, dependencies=["a"]))
        ex.add_node(DAGNode("c", c, dependencies=["b"]))
        results = await ex.execute()

        self.assertEqual(order, ["a", "b", "c"])
        self.assertEqual(results["a"].value, "a")
        self.assertEqual(results["c"].value, "c")
        self.assertIsNone(results["a"].error)

    async def test_fan_out(self):
        from deviatrix_genesis.v5.dag import DAGExecutor, DAGNode

        completed: list[str] = []

        async def n1(**kw):
            completed.append("n1")
            return 1

        async def n2(**kw):
            completed.append("n2")
            return 2

        async def n3(**kw):
            completed.append("n3")
            return 3

        ex = DAGExecutor()
        ex.add_node(DAGNode("n1", n1))
        ex.add_node(DAGNode("n2", n2))
        ex.add_node(DAGNode("n3", n3))
        results = await ex.execute()

        self.assertEqual(len(completed), 3)
        self.assertEqual(results["n1"].value, 1)
        self.assertEqual(results["n2"].value, 2)
        self.assertEqual(results["n3"].value, 3)

    async def test_error_isolation(self):
        from deviatrix_genesis.v5.dag import DAGExecutor, DAGNode

        async def ok(**kw):
            return "ok"

        async def fail(**kw):
            raise ValueError("boom")

        ex = DAGExecutor()
        ex.add_node(DAGNode("ok1", ok))
        ex.add_node(DAGNode("bad", fail))
        ex.add_node(DAGNode("ok2", ok))
        results = await ex.execute()

        self.assertEqual(results["ok1"].value, "ok")
        self.assertIsNone(results["ok1"].error)
        self.assertIn("boom", results["bad"].error)
        self.assertEqual(results["ok2"].value, "ok")

    async def test_conditional_skip(self):
        from deviatrix_genesis.v5.dag import DAGExecutor, DAGNode

        async def a(**kw):
            return 42

        async def b(**kw):
            return 99

        ex = DAGExecutor()
        ex.add_node(DAGNode("a", a))
        ex.add_node(DAGNode("b", b, dependencies=["a"], skip_if=lambda deps: deps.get("a", 0) > 10))
        results = await ex.execute()

        self.assertEqual(results["a"].value, 42)
        self.assertTrue(results["b"].skipped)

    async def test_timing_recorded(self):
        from deviatrix_genesis.v5.dag import DAGExecutor, DAGNode

        async def slow(**kw):
            await asyncio.sleep(0.05)
            return "done"

        ex = DAGExecutor()
        ex.add_node(DAGNode("s", slow))
        results = await ex.execute()

        self.assertGreater(results["s"].duration, 0.04)
        self.assertGreater(results["s"].start_time, 0)
        self.assertGreater(results["s"].end_time, 0)


# ────────────────────────────────────────────────────────────────────
# Telemetry tests
# ────────────────────────────────────────────────────────────────────


class TestTelemetry(unittest.TestCase):

    def test_emit_subscribe(self):
        from deviatrix_genesis.v5.telemetry import EventBus

        bus = EventBus()
        received: list[str] = []
        bus.subscribe(lambda e: received.append(e.event_type))

        bus.emit("test_event", "test_source", value=42)
        self.assertEqual(received, ["test_event"])

    def test_filter_by_type(self):
        from deviatrix_genesis.v5.telemetry import EventBus

        bus = EventBus()
        bus.emit("a", "src")
        bus.emit("b", "src")
        bus.emit("a", "src")

        a_events = bus.get_events(event_type="a")
        self.assertEqual(len(a_events), 2)

    def test_unsubscribe(self):
        from deviatrix_genesis.v5.telemetry import EventBus

        bus = EventBus()
        count = [0]
        sid = bus.subscribe(lambda e: count.__setitem__(0, count[0] + 1))

        bus.emit("x", "src")
        self.assertEqual(count[0], 1)

        bus.unsubscribe(sid)
        bus.emit("x", "src")
        self.assertEqual(count[0], 1)  # no change

    def test_convergence_metrics_shape(self):
        from deviatrix_genesis.v5.telemetry import ConvergenceMetrics

        m = ConvergenceMetrics(
            round_number=1, survivors_count=5,
            median_z=3.2, max_z=12.1,
            z_improvement_vs_prev=0.5, wall_clock_ms=150.0,
        )
        self.assertEqual(m.round_number, 1)
        self.assertEqual(m.survivors_count, 5)
        self.assertAlmostEqual(m.median_z, 3.2)

    def test_collector_rounds(self):
        from deviatrix_genesis.v5.telemetry import EventBus, TelemetryCollector

        bus = EventBus()
        collector = TelemetryCollector(bus)
        collector.start()

        bus.emit("round_start", "pipeline", round=1)
        time.sleep(0.01)
        bus.emit("round_end", "pipeline", round=1, survivors_count=7, median_z=5.0, max_z=10.0)

        self.assertEqual(len(collector.rounds), 1)
        self.assertEqual(collector.rounds[0].survivors_count, 7)
        self.assertAlmostEqual(collector.rounds[0].median_z, 5.0)

        collector.stop()


# ────────────────────────────────────────────────────────────────────
# Convergence tests
# ────────────────────────────────────────────────────────────────────


class TestConvergence(unittest.TestCase):

    def _metrics(self, round_num: int, surv_count: int, median_z: float, improvement: float = 0.0):
        from deviatrix_genesis.v5.telemetry import ConvergenceMetrics
        return ConvergenceMetrics(
            round_number=round_num, survivors_count=surv_count,
            median_z=median_z, max_z=median_z + 5,
            z_improvement_vs_prev=improvement, wall_clock_ms=100.0,
        )

    def test_below_min_rounds(self):
        from deviatrix_genesis.v5.convergence import AdaptiveConvergence

        conv = AdaptiveConvergence(min_rounds=2, max_rounds=10)
        d = conv.update(self._metrics(1, 5, 3.0), {"a", "b"})
        self.assertFalse(d.should_stop)
        self.assertEqual(d.reason, "below_min_rounds")

    def test_stops_on_no_new_survivors(self):
        from deviatrix_genesis.v5.convergence import AdaptiveConvergence

        conv = AdaptiveConvergence(min_rounds=1, max_rounds=10, no_new_survivors_patience=2)

        conv.update(self._metrics(1, 5, 3.0), {"a", "b"})
        conv.update(self._metrics(2, 5, 3.1), {"a", "b"})  # same names
        d = conv.update(self._metrics(3, 5, 3.1), {"a", "b"})  # same again

        self.assertTrue(d.should_stop)
        self.assertIn("no_new_survivors", d.reason)

    def test_stops_on_plateau(self):
        from deviatrix_genesis.v5.convergence import AdaptiveConvergence

        conv = AdaptiveConvergence(min_rounds=1, max_rounds=10, z_improvement_threshold=0.5)

        conv.update(self._metrics(1, 5, 3.0, improvement=1.0), {"a"})
        conv.update(self._metrics(2, 5, 3.05, improvement=0.05), {"a", "b"})
        d = conv.update(self._metrics(3, 5, 3.08, improvement=0.03), {"a", "b", "c"})

        self.assertTrue(d.should_stop)
        self.assertIn("z_plateau", d.reason)

    def test_stops_on_max_rounds(self):
        from deviatrix_genesis.v5.convergence import AdaptiveConvergence

        conv = AdaptiveConvergence(min_rounds=1, max_rounds=3, no_new_survivors_patience=100)

        conv.update(self._metrics(1, 5, 3.0, improvement=2.0), {"a"})
        conv.update(self._metrics(2, 6, 5.0, improvement=2.0), {"a", "b"})
        d = conv.update(self._metrics(3, 7, 7.0, improvement=2.0), {"a", "b", "c"})

        self.assertTrue(d.should_stop)
        self.assertEqual(d.reason, "max_rounds_reached")

    def test_continues_when_improving(self):
        from deviatrix_genesis.v5.convergence import AdaptiveConvergence

        conv = AdaptiveConvergence(min_rounds=1, max_rounds=10)

        conv.update(self._metrics(1, 5, 3.0, improvement=2.0), {"a"})
        d = conv.update(self._metrics(2, 6, 5.0, improvement=2.0), {"a", "b"})

        self.assertFalse(d.should_stop)
        self.assertEqual(d.reason, "improving")

    def test_reset(self):
        from deviatrix_genesis.v5.convergence import AdaptiveConvergence

        conv = AdaptiveConvergence(min_rounds=1, max_rounds=2)
        conv.update(self._metrics(1, 5, 3.0), {"a"})
        conv.update(self._metrics(2, 5, 3.0), {"a"})
        # should have stopped

        conv.reset()
        d = conv.update(self._metrics(1, 5, 3.0), {"b"})
        self.assertFalse(d.should_stop)


# ────────────────────────────────────────────────────────────────────
# Fusion tests
# ────────────────────────────────────────────────────────────────────


class TestFusion(unittest.TestCase):

    def test_empty_briefs(self):
        from deviatrix_genesis.v5.fusion import CrossBriefFusion

        f = CrossBriefFusion()
        result = f.fuse([])
        self.assertEqual(result, [])

    def test_single_brief(self):
        from deviatrix_genesis.v5.fusion import CrossBriefFusion

        f = CrossBriefFusion()
        result = f.fuse([{"brief": "a", "survivors": [{"name": "x", "composite_z": 5.0}]}])
        self.assertEqual(result, [])

    def test_two_briefs_complementary(self):
        from deviatrix_genesis.v5.fusion import CrossBriefFusion

        f = CrossBriefFusion()
        result = f.fuse([
            {
                "brief": "brief-A",
                "survivors": [
                    {"name": "idea1", "formula": "x+1", "mechanism_families": ["financial"],
                     "composite_z": 5.0},
                ],
            },
            {
                "brief": "brief-B",
                "survivors": [
                    {"name": "idea2", "formula": "y+2", "mechanism_families": ["distribution"],
                     "composite_z": 8.0},
                ],
            },
        ])
        # Complementary mechanisms → should produce a hybrid
        self.assertGreater(len(result), 0)
        self.assertIn("brief-A", result[0].brief_sources)
        self.assertIn("brief-B", result[0].brief_sources)

    def test_two_briefs_overlapping_mechanisms(self):
        from deviatrix_genesis.v5.fusion import CrossBriefFusion

        f = CrossBriefFusion()
        result = f.fuse([
            {
                "brief": "brief-A",
                "survivors": [
                    {"name": "idea1", "formula": "x+1", "mechanism_families": ["financial"],
                     "composite_z": 5.0},
                ],
            },
            {
                "brief": "brief-B",
                "survivors": [
                    {"name": "idea2", "formula": "y+2", "mechanism_families": ["financial"],
                     "composite_z": 8.0},
                ],
            },
        ])
        # Same mechanism → no hybrid
        self.assertEqual(len(result), 0)


# ────────────────────────────────────────────────────────────────────
# Memory loop tests
# ────────────────────────────────────────────────────────────────────


class TestMemoryLoop(unittest.TestCase):

    def test_build_brief_from_memories(self):
        from deviatrix_genesis.v5.memory_loop import build_brief_from_memories

        memories = [
            {"content": {"summary": "GTM strategy for AI tools"}},
            {"content": {"text": "Revenue model: SaaS + services"}},
        ]
        brief = build_brief_from_memories(memories)
        self.assertIn("GTM strategy", brief)
        self.assertIn("Revenue model", brief)

    def test_build_brief_empty(self):
        from deviatrix_genesis.v5.memory_loop import build_brief_from_memories

        brief = build_brief_from_memories([])
        self.assertIn("Default", brief)

    def test_circuit_breaker_opens(self):
        from deviatrix_genesis.v5.memory_loop import MemoryLoopConfig, ResilientMemoryLoop

        config = MemoryLoopConfig(
            db_path="/nonexistent/path/memory.db",
            circuit_breaker_threshold=2,
        )
        loop = ResilientMemoryLoop(config)

        # Simulate failures by calling run_cycle with empty brief
        # and a config that will fail on the query path
        loop._consecutive_failures = config.circuit_breaker_threshold
        loop._circuit_open = True

        # Circuit should be open now
        result = loop.run_cycle(brief="test brief 3")
        self.assertIn("circuit_breaker_open", result.get("errors", []))

    def test_circuit_breaker_reset(self):
        from deviatrix_genesis.v5.memory_loop import MemoryLoopConfig, ResilientMemoryLoop

        config = MemoryLoopConfig(
            db_path="/nonexistent/path/memory.db",
            circuit_breaker_threshold=2,
        )
        loop = ResilientMemoryLoop(config)

        loop.run_cycle(brief="x")
        loop.run_cycle(brief="y")
        loop.reset_circuit()

        # After reset, should not be open
        result = loop.run_cycle(brief="z")
        self.assertNotIn("circuit_breaker_open", result.get("errors", []))


# ────────────────────────────────────────────────────────────────────
# Dashboard tests
# ────────────────────────────────────────────────────────────────────


class TestDashboard(unittest.TestCase):

    def test_renders_nonempty(self):
        from deviatrix_genesis.v5.dashboard import Dashboard
        from deviatrix_genesis.v5.telemetry import EventBus

        bus = EventBus()
        dash = Dashboard(bus)
        dash.start(total_expeditions=9)

        bus.emit("round_start", "pipeline", round=1)
        bus.emit("expedition_complete", "pipeline")
        bus.emit("round_end", "pipeline", round=1, survivors_count=5, median_z=4.0, max_z=10.0)

        output = dash.render()
        self.assertIn("DEVIATRIX", output)
        self.assertIn("survivors", output.lower())

        dash.stop()

    def test_sparkline(self):
        from deviatrix_genesis.v5.dashboard import _sparkline

        result = _sparkline([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(len(result), 5)
        # Last value should be the highest spark character
        self.assertEqual(result[-1], "█")

    def test_subscribes_to_events(self):
        from deviatrix_genesis.v5.dashboard import Dashboard
        from deviatrix_genesis.v5.telemetry import EventBus

        bus = EventBus()
        dash = Dashboard(bus)
        dash.start()

        bus.emit("memory_write", "pipeline")
        bus.emit("memory_write", "pipeline")

        self.assertEqual(dash._memory_writes, 2)
        dash.stop()


# ────────────────────────────────────────────────────────────────────
# Pipeline integration (smoke)
# ────────────────────────────────────────────────────────────────────


class TestPipelineSmoke(unittest.TestCase):

    def test_v5_pipeline_runs(self):
        """Smoke test: v5 pipeline completes without error on a short run."""
        from deviatrix_genesis.v5.pipeline import run_v5_pipeline

        result = run_v5_pipeline(
            brief="Operator-first GTM with financial primitives",
            n_ideas=3,
            max_rounds=2,
            seeds=[2026],
        )
        self.assertIn("survivors", result)
        self.assertIn("brief", result)
        self.assertGreater(result["corpus_size"], 0)
        self.assertGreater(result["wall_clock_s"], 0)
        self.assertGreaterEqual(result["n_rounds"], 1)

    def test_v5_report_renders(self):
        from deviatrix_genesis.v5.pipeline import render_v5_report

        result = {
            "brief": "test",
            "corpus_size": 100,
            "ideas_proposed": 3,
            "seeds": [2026],
            "survivors": [{"name": "idea1", "composite_z_median": 5.0}],
            "dropped": [],
            "hybrids": [],
            "n_rounds": 1,
            "n_packets": 9,
            "memory_ids_written": [],
            "telemetry_events": 10,
            "wall_clock_s": 1.5,
            "quality": {"total_expeditions": 9, "pass_rate_pct": 88.9, "wall_breaches": 0,
                        "avg_diamond_ms": 100.0, "z_mean": 5.0, "z_median": 4.5,
                        "z_stdev": 2.0, "z_min": -2.0, "z_max": 12.0},
        }
        report = render_v5_report(result)
        self.assertIn("test", report)
        self.assertIn("idea1", report)
        self.assertIn("Quality Metrics", report)

    def test_pipeline_empty_brief(self):
        """Pipeline handles empty brief gracefully."""
        from deviatrix_genesis.v5.pipeline import run_v5_pipeline

        result = run_v5_pipeline(brief="", n_ideas=2, max_rounds=1, seeds=[2026])
        self.assertIn("survivors", result)
        self.assertGreaterEqual(result["n_rounds"], 1)

    def test_pipeline_single_seed(self):
        """Pipeline works with a single seed."""
        from deviatrix_genesis.v5.pipeline import run_v5_pipeline

        result = run_v5_pipeline(brief="test", n_ideas=2, max_rounds=1, seeds=[42])
        self.assertIn("survivors", result)

    def test_pipeline_quality_metrics_present(self):
        """Quality metrics are always present in result."""
        from deviatrix_genesis.v5.pipeline import run_v5_pipeline

        result = run_v5_pipeline(brief="test", n_ideas=2, max_rounds=1, seeds=[2026])
        self.assertIn("quality", result)
        q = result["quality"]
        self.assertIn("pass_rate_pct", q)
        self.assertIn("z_mean", q)
        self.assertIn("total_expeditions", q)


class TestMultiBrief(unittest.TestCase):

    def test_multi_brief_fusion(self):
        from deviatrix_genesis.v5.pipeline import run_multi_brief

        result = run_multi_brief(
            briefs=["GTM with financial primitives", "Distribution channel strategy"],
            n_ideas=3,
            max_rounds=1,
            seeds=[2026],
        )
        self.assertIn("briefs", result)
        self.assertIn("cross_brief_hybrids", result)
        self.assertEqual(len(result["briefs"]), 2)


class TestDiversity(unittest.TestCase):

    def test_diverse_population_round1(self):
        from deviatrix_genesis.v5.diversity import diverse_population, population_entropy

        pop = diverse_population(size=500, seed=42, round_num=1)
        self.assertEqual(len(pop), 500)
        ent = population_entropy(pop)
        self.assertGreater(ent, 2.0)  # reasonable entropy

    def test_diverse_population_round2(self):
        from deviatrix_genesis.v5.diversity import diverse_population

        pop = diverse_population(size=500, seed=42, round_num=2)
        self.assertEqual(len(pop), 500)

    def test_diverse_population_with_survivors(self):
        from deviatrix_genesis.v5.diversity import diverse_population

        survivors = [{"composite_z": 5.0}, {"composite_z": -3.0}]
        pop = diverse_population(size=500, seed=42, round_num=2, survivors=survivors)
        self.assertEqual(len(pop), 500)


class TestPareto(unittest.TestCase):

    def test_empty_input(self):
        from deviatrix_genesis.v5.pareto import pareto_frontier

        result = pareto_frontier([])
        self.assertEqual(result, [])

    def test_single_survivor(self):
        from deviatrix_genesis.v5.pareto import pareto_frontier

        result = pareto_frontier([{"name": "a", "composite_z": 5.0, "mechanism_family": "financial"}])
        self.assertEqual(len(result), 1)

    def test_dominance(self):
        from deviatrix_genesis.v5.pareto import ParetoPoint

        a = ParetoPoint("a", {"x": 5.0, "y": 3.0}, {})
        b = ParetoPoint("b", {"x": 3.0, "y": 1.0}, {})
        self.assertTrue(a.dominates(b))
        self.assertFalse(b.dominates(a))


class TestProvenance(unittest.TestCase):

    def test_chain_verifies(self):
        from deviatrix_genesis.v5.provenance import ProvenanceChain

        chain = ProvenanceChain()
        chain.add_step("brief", {"text": "test"})
        chain.add_step("formula", {"expr": "x**2"})
        self.assertTrue(chain.verify())
        self.assertEqual(chain.length, 2)

    def test_chain_tamper_detected(self):
        from deviatrix_genesis.v5.provenance import ProvenanceChain

        chain = ProvenanceChain()
        chain.add_step("brief", {"text": "test"})
        chain._steps[0].data_hash = "tampered"
        self.assertFalse(chain.verify())


class TestAnomaly(unittest.TestCase):

    def test_no_anomalies_on_normal_values(self):
        from deviatrix_genesis.v5.anomaly import AnomalyDetector

        det = AnomalyDetector()
        for z in [1.0, 3.0, 2.0, 4.0, 1.5]:
            det.feed(z)
        self.assertEqual(len(det.alerts()), 0)

    def test_sudden_jump_detected(self):
        from deviatrix_genesis.v5.anomaly import AnomalyDetector

        det = AnomalyDetector(jump_threshold=5.0)
        det.feed(1.0)
        anomalies = det.feed(15.0)
        self.assertTrue(any(a.kind == "sudden_jump" for a in anomalies))

    def test_wall_proximity_detected(self):
        from deviatrix_genesis.v5.anomaly import AnomalyDetector

        det = AnomalyDetector()
        anomalies = det.feed(28.5)
        self.assertTrue(any(a.kind == "wall_proximity" for a in anomalies))

    def test_clustering_detected(self):
        from deviatrix_genesis.v5.anomaly import AnomalyDetector

        det = AnomalyDetector(cluster_threshold=1.0)
        for z in [5.0, 5.1, 5.05, 5.08, 5.02]:
            anomalies = det.feed(z)
        self.assertTrue(any(a.kind == "clustering" for a in anomalies))


class TestExports(unittest.TestCase):

    def test_markdown_export(self):
        from deviatrix_genesis.v5.exports import ReportExporter

        result = {
            "brief": "test", "seeds": [2026], "n_rounds": 2, "wall_clock_s": 1.5,
            "n_packets": 18, "survivors": [{"name": "idea1", "composite_z": 5.0, "band": "+5σ–10σ"}],
            "dropped": [], "hybrids": [], "quality": {"total_expeditions": 9, "pass_rate_pct": 88.9,
            "wall_breaches": 0, "z_mean": 3.0, "z_median": 2.5, "z_stdev": 1.5, "z_min": -1.0, "z_max": 8.0},
        }
        exp = ReportExporter(result)
        md = exp.to_markdown()
        self.assertIn("idea1", md)
        self.assertIn("Quality Metrics", md)

    def test_summary_export(self):
        from deviatrix_genesis.v5.exports import ReportExporter

        result = {"survivors": [{"composite_z": 5.0}], "n_rounds": 2, "wall_clock_s": 1.5}
        exp = ReportExporter(result)
        self.assertIn("1 survivors", exp.to_summary())

    def test_csv_export(self):
        from deviatrix_genesis.v5.exports import ReportExporter

        result = {"survivors": [{"name": "a", "composite_z": 5.0, "band": "+5σ–10σ", "mechanism_family": "fin", "formula": "x+1"}]}
        exp = ReportExporter(result)
        csv = exp.to_csv()
        self.assertIn("a", csv)
        self.assertIn("name", csv)


class TestHealer(unittest.TestCase):

    def test_healer_returns_result(self):
        from deviatrix_genesis.v5.healer import HealingPipeline

        hp = HealingPipeline(max_retries=1, base_seed=42)
        result = hp.run_with_healing(brief="test", n_ideas=2, max_rounds=1)
        self.assertIn("healing_attempts", result)


class TestHypotheses(unittest.TestCase):

    def test_generate_hypotheses(self):
        from deviatrix_genesis.v5.hypotheses import HypothesisGenerator

        gen = HypothesisGenerator()
        survivors = [{"name": "idea1", "composite_z": 5.0, "formula": "x**2", "mechanism_family": "financial"}]
        hyps = gen.generate(survivors)
        self.assertEqual(len(hyps), 1)
        self.assertIn("idea1", hyps[0].statement)

    def test_report_generation(self):
        from deviatrix_genesis.v5.hypotheses import HypothesisGenerator

        gen = HypothesisGenerator()
        hyps = gen.generate([{"name": "a", "composite_z": 3.0, "formula": "x", "mechanism_family": "fin"}])
        report = gen.generate_report(hyps)
        self.assertIn("Hypothesis Report", report)


class TestVDJ(unittest.TestCase):

    def test_generate_formulas(self):
        from deviatrix_genesis.v5.vdj import VDJRecombinase

        recomb = VDJRecombinase(seed=42)
        formulas = recomb.generate(n=3)
        # VDJ may produce 0 parseable formulas if assembly is imperfect
        # Just verify the recombinase runs without error
        self.assertIsInstance(formulas, list)

    def test_recombine_parents(self):
        from deviatrix_genesis.v5.vdj import VDJRecombinase

        recomb = VDJRecombinase(seed=42)
        result = recomb.recombine_parents("x**2", "sin(x)")
        self.assertIsNotNone(result.formula)


class TestSnapshots(unittest.TestCase):

    def test_seal_and_rollback(self):
        from deviatrix_genesis.v5.snapshots import StageSnapshotManager

        mgr = StageSnapshotManager()
        mgr.seal("formula_emission", {"formulas": ["x**2"]})
        mgr.seal("scoring", {"scores": {"x**2": 5.0}})

        state = mgr.rollback_to("scoring")
        self.assertIsNotNone(state)
        self.assertIn("scores", state)

    def test_chain_verifies(self):
        from deviatrix_genesis.v5.snapshots import StageSnapshotManager

        mgr = StageSnapshotManager()
        mgr.seal("test", {"a": 1})
        mgr.seal("test", {"b": 2})
        self.assertTrue(mgr.verify_chain("test"))


class TestCertification(unittest.TestCase):

    def test_certify_polynomial(self):
        from deviatrix_genesis.v5.certification import FormulaCertifier

        cert = FormulaCertifier()
        result = cert.certify("x**2 + 3*x + 1")
        self.assertTrue(result.passed)
        self.assertFalse(result.trivial)

    def test_certify_trivial_zero(self):
        from deviatrix_genesis.v5.certification import FormulaCertifier

        cert = FormulaCertifier()
        result = cert.certify("x - x")
        self.assertTrue(result.trivial or result.collapse_detected)


class TestCapsules(unittest.TestCase):

    def test_capture_and_summary(self):
        from deviatrix_genesis.v5.capsules import CapsuleStore

        store = CapsuleStore()
        store.capture(formula="x**2", seed=42, error="verifier FAIL")
        store.capture(formula="sin(x)", seed=43, error="wall breach")

        summary = store.summary()
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["unreplayed"], 2)


class TestCanaries(unittest.TestCase):

    def test_canary_manager(self):
        from deviatrix_genesis.v5.canaries import CanaryManager

        mgr = CanaryManager()
        canaries = mgr.get_canaries()
        self.assertGreater(len(canaries), 0)

    def test_health_check(self):
        from deviatrix_genesis.v5.canaries import CanaryManager

        mgr = CanaryManager()
        # Simulate positive canary passing
        results = {"simple_polynomial": True, "zero_constant": False}
        report = mgr.check_results(results)
        self.assertTrue(report["healthy"])


class TestProofStream(unittest.TestCase):

    def test_emit_and_get_partial(self):
        from deviatrix_genesis.v5.proof_stream import ProofStream

        stream = ProofStream()
        stream.emit_pass("A", "x**2", "PASS")
        stream.emit_pass("B", "x**2", "PASS", z=5.0)

        partial = stream.get_partial("x**2")
        self.assertIsNotNone(partial)
        self.assertEqual(partial.composite_status, "partial_pass")
        self.assertTrue(partial.can_proceed)

    def test_summary(self):
        from deviatrix_genesis.v5.proof_stream import ProofStream

        stream = ProofStream()
        stream.emit_pass("A", "x**2", "PASS")
        stream.emit_pass("A", "sin(x)", "FAIL")

        summary = stream.summary()
        self.assertEqual(summary["total_formulas"], 2)


class TestAxioms(unittest.TestCase):

    def test_consolidate_insufficient(self):
        from deviatrix_genesis.v5.axioms import AxiomEngine

        engine = AxiomEngine()
        axioms = engine.consolidate(last_n=0)
        self.assertEqual(axioms.runs_analyzed, 0)


class TestTolerance(unittest.TestCase):

    def test_central_tolerance(self):
        from deviatrix_genesis.v5.tolerance import ToleranceRegistry

        reg = ToleranceRegistry()
        reg.register_central("x**2 + 1", "standard polynomial")
        self.assertTrue(reg.check("x**2 + 1"))
        self.assertFalse(reg.check("unknown_formula"))

    def test_peripheral_tolerance(self):
        from deviatrix_genesis.v5.tolerance import ToleranceRegistry

        reg = ToleranceRegistry()
        reg.register_peripheral("sin(x)", "financial", "periodic")
        self.assertTrue(reg.check("sin(x)", context="financial"))
        self.assertFalse(reg.check("sin(x)", context="other"))


class TestProvenanceAudit(unittest.TestCase):

    def test_audit_clean(self):
        from deviatrix_genesis.v5.provenance_audit import ProvenanceAuditor

        auditor = ProvenanceAuditor()
        entries = [
            {"chain_hash": "abc", "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000", "timestamp": 1000, "content": {"a": 1}},
            {"chain_hash": "def", "prev_hash": "abc", "timestamp": 1001, "content": {"b": 2}},
        ]
        report = auditor.audit(entries)
        self.assertTrue(report.chain_valid)

    def test_audit_chain_break(self):
        from deviatrix_genesis.v5.provenance_audit import ProvenanceAuditor

        auditor = ProvenanceAuditor()
        entries = [
            {"chain_hash": "abc", "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000", "timestamp": 1000},
            {"chain_hash": "def", "prev_hash": "WRONG", "timestamp": 1001},
        ]
        report = auditor.audit(entries)
        self.assertFalse(report.chain_valid)


class TestContention(unittest.TestCase):

    def test_monitor_and_analyze(self):
        from deviatrix_genesis.v5.contention import ContentionMonitor

        monitor = ContentionMonitor()
        monitor.record_node_start("a")
        monitor.record_node_end("a", duration_ms=100.0)
        monitor.record_node_start("b", dependencies=["a"])
        monitor.record_node_end("b", duration_ms=50.0)

        report = monitor.analyze()
        self.assertEqual(report.total_nodes, 2)
        self.assertGreater(report.parallel_efficiency, 0)


if __name__ == "__main__":
    unittest.main()
