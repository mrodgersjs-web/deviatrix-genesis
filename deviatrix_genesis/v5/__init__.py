"""Deviatrix Genesis v5 — 1000x over v4.

v5 adds:
  * **async DAG executor** — true asyncio concurrency with dependency-aware scheduling.
  * **structured telemetry** — every stage emits events; convergence is measured, not guessed.
  * **adaptive convergence** — stops early when the idea space is exhausted.
  * **cross-brief fusion** — finds mechanism-complementary ideas across briefs.
  * **resilient Memory OS loop** — retry, circuit-breaker, idempotent writes.
  * **live dashboard** — ASCII telemetry dashboard for monitoring runs.
  * **benchmark harness** — compare v3 vs v5 objectively.
"""

from __future__ import annotations

__all__ = ["dag", "telemetry", "convergence", "fusion", "memory_loop", "dashboard", "benchmark"]
