"""Deviatrix Genesis v5 — 1000x over v4.

v5 adds:
  * **async DAG executor** — true asyncio concurrency with dependency-aware scheduling.
  * **structured telemetry** — every stage emits events; convergence is measured, not guessed.
  * **adaptive convergence** — stops early when the idea space is exhausted.
  * **cross-brief fusion** — finds mechanism-complementary ideas across briefs.
  * **resilient Memory OS loop** — retry, circuit-breaker, idempotent writes.
  * **live dashboard** — ASCII + web telemetry dashboard for monitoring runs.
  * **benchmark harness** — compare v3 vs v5 objectively.
  * **LLM formula generation** — LLM-powered SymPy-parseable formula generation.
  * **persistent run history** — SQLite-backed run tracking with trend analysis.
  * **doctrine auto-evolution** — learns from run history to improve scoring.
  * **plugin system** — register custom scorers, transformers, validators.
  * **formula lineage** — track parent-child relationships across rounds.
  * **adversarial red-teaming** — LLM-driven attack on survivors.
  * **prime agent** — autonomous goal-driven agent wrapping the full pipeline.
  * **streaming pipeline** — real-time results as expeditions complete.
  * **population diversity** — anti-collapse reference population injection.
  * **Pareto optimization** — multi-objective survivor ranking.
  * **hypothesis generation** — automated falsifiable hypotheses from survivors.
  * **causal inference** — which formula features cause high z-scores.
  * **self-healing** — auto-retry failed expeditions with different seeds.
  * **provenance chain** — SHA-256 hash chain from brief to memory.
  * **A/B testing** — compare strategies head-to-head.
  * **anomaly detection** — flag unusual z-score patterns in real-time.
  * **export suite** — Markdown, JSON, CSV report generation.
"""

from __future__ import annotations

__all__ = [
    "dag", "telemetry", "convergence", "fusion", "memory_loop",
    "dashboard", "benchmark", "pipeline", "llm_formulas", "run_history",
    "doctrine_evolution", "web_dashboard", "plugins", "lineage",
    "redteam", "prime_agent", "memory_loop_cli",
    "streaming", "diversity", "pareto", "hypotheses", "causal",
    "healer", "provenance", "ab_testing", "anomaly", "exports",
]
