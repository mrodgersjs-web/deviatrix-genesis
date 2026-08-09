"""Deviatrix Prime Agent — autonomous goal-driven idea validation.

The prime agent wraps the entire v5 pipeline as a self-contained agent
that can be invoked, run autonomously, and report results.

Capabilities:
  * Run single-brief or multi-brief pipelines
  * Query Memory OS for strategic intent
  * Write survivors back to Memory OS
  * Track run history and trend analysis
  * Generate doctrine evolution proposals
  * Serve live web dashboard
  * Self-verify results before reporting

Usage::

    # As a module
    from deviatrix_genesis.v5.prime_agent import DeviatrixAgent
    agent = DeviatrixAgent()
    result = agent.run("GTM strategy for AI tools")

    # As CLI
    python -m deviatrix_genesis.v5.prime_agent run --brief "GTM strategy"
    python -m deviatrix_genesis.v5.prime_agent autonomous --from-memory-os
    python -m deviatrix_genesis.v5.prime_agent status
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["DeviatrixAgent", "AgentResult"]


@dataclass
class AgentResult:
    """Outcome of an agent run."""
    status: str  # success | partial | failed
    brief: str
    survivors: list[dict[str, Any]]
    dropped: list[dict[str, Any]]
    hybrids: list[dict[str, Any]]
    quality: dict[str, Any]
    wall_clock_s: float
    run_id: str = ""
    memory_ids_written: list[str] = field(default_factory=list)
    doctrine_proposal: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Deviatrix Agent — {self.status}",
            f"  Brief: {self.brief[:60]}",
            f"  Survivors: {len(self.survivors)} | Dropped: {len(self.dropped)} | Hybrids: {len(self.hybrids)}",
            f"  Best z: {self.quality.get('z_max', 0):.2f} | Pass rate: {self.quality.get('pass_rate_pct', 0)}%",
            f"  Wall-clock: {self.wall_clock_s:.1f}s | Run ID: {self.run_id}",
        ]
        if self.memory_ids_written:
            lines.append(f"  Memory OS writes: {len(self.memory_ids_written)}")
        if self.doctrine_proposal:
            lines.append(f"  Doctrine proposals: {len(self.doctrine_proposal.get('band_adjustments', []))} band, {len(self.doctrine_proposal.get('weight_adjustments', []))} weight")
        if self.errors:
            lines.append(f"  Errors: {self.errors}")
        return "\n".join(lines)


class DeviatrixAgent:
    """The prime agent — runs the full Deviatrix pipeline autonomously."""

    def __init__(
        self,
        *,
        n_ideas: int = 9,
        max_rounds: int = 10,
        seeds: list[int] | None = None,
        write_memory_os: bool = False,
        track_history: bool = True,
        evolve_doctrine: bool = False,
    ) -> None:
        self.n_ideas = n_ideas
        self.max_rounds = max_rounds
        self.seeds = seeds or [2026, 2043]
        self.write_memory_os = write_memory_os
        self.track_history = track_history
        self.evolve_doctrine = evolve_doctrine

    def run(self, brief: str) -> AgentResult:
        """Run a single-brief pipeline."""
        from .pipeline import run_v5_pipeline

        t0 = time.monotonic()
        errors: list[str] = []

        try:
            result = run_v5_pipeline(
                brief=brief,
                n_ideas=self.n_ideas,
                max_rounds=self.max_rounds,
                seeds=self.seeds,
                write_memory_os=self.write_memory_os,
            )
        except Exception as exc:
            return AgentResult(
                status="failed", brief=brief, survivors=[], dropped=[],
                hybrids=[], quality={}, wall_clock_s=time.monotonic() - t0,
                errors=[str(exc)],
            )

        survivors = result.get("survivors", [])
        quality = result.get("quality", {})
        elapsed = time.monotonic() - t0

        # Doctrine evolution
        doctrine_proposal: dict[str, Any] = {}
        if self.evolve_doctrine:
            try:
                from .doctrine_evolution import DoctrineLearner
                learner = DoctrineLearner()
                proposal = learner.analyze_history(last_n=20)
                doctrine_proposal = proposal.to_dict()
            except Exception as exc:
                errors.append(f"doctrine_evolution: {exc}")

        status = "success" if survivors else "partial"

        return AgentResult(
            status=status,
            brief=brief,
            survivors=survivors,
            dropped=result.get("dropped", []),
            hybrids=result.get("hybrids", []),
            quality=quality,
            wall_clock_s=elapsed,
            run_id=result.get("run_id", ""),
            memory_ids_written=result.get("memory_ids_written", []),
            doctrine_proposal=doctrine_proposal,
            errors=errors,
        )

    def run_multi(self, briefs: list[str]) -> dict[str, Any]:
        """Run multi-brief with cross-fusion."""
        from .pipeline import run_multi_brief

        return run_multi_brief(
            briefs=briefs,
            n_ideas=self.n_ideas,
            max_rounds=self.max_rounds,
            seeds=self.seeds,
        )

    def run_autonomous(self) -> AgentResult:
        """Run from Memory OS — query strategic intent, run, write back."""
        from .memory_loop import ResilientMemoryLoop, build_brief_from_memories

        loop = ResilientMemoryLoop()
        memories = loop._query_strategic_memories(top_k=10)

        if not memories:
            return AgentResult(
                status="failed", brief="(from Memory OS)", survivors=[],
                dropped=[], hybrids=[], quality={}, wall_clock_s=0.0,
                errors=["no memories found in Memory OS"],
            )

        brief = build_brief_from_memories(memories)
        self.write_memory_os = True
        return self.run(brief)

    def status(self) -> dict[str, Any]:
        """Get agent status — run history, trends, telemetry."""
        from .run_history import RunHistory
        from .telemetry import get_bus

        bus = get_bus()
        history = RunHistory()

        return {
            "telemetry_events": len(bus.get_events()),
            "run_history": history.trend_analysis(),
            "config": {
                "n_ideas": self.n_ideas,
                "max_rounds": self.max_rounds,
                "seeds": self.seeds,
                "write_memory_os": self.write_memory_os,
                "track_history": self.track_history,
                "evolve_doctrine": self.evolve_doctrine,
            },
        }


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(prog="deviatrix-agent", description="Deviatrix Prime Agent")
    sub = p.add_subparsers(dest="command")

    # run
    run_p = sub.add_parser("run", help="Run single-brief pipeline")
    run_p.add_argument("--brief", default="Operator-first GTM with financial primitives")
    run_p.add_argument("--n-ideas", type=int, default=9)
    run_p.add_argument("--max-rounds", type=int, default=10)
    run_p.add_argument("--seeds", default="2026,2043")
    run_p.add_argument("--write-memory-os", action="store_true")
    run_p.add_argument("--evolve-doctrine", action="store_true")

    # autonomous
    auto_p = sub.add_parser("autonomous", help="Run from Memory OS autonomously")
    auto_p.add_argument("--n-ideas", type=int, default=9)
    auto_p.add_argument("--max-rounds", type=int, default=10)
    auto_p.add_argument("--evolve-doctrine", action="store_true")

    # multi
    multi_p = sub.add_parser("multi", help="Multi-brief cross-fusion")
    multi_p.add_argument("--briefs", required=True, help="Pipe-separated briefs")
    multi_p.add_argument("--n-ideas", type=int, default=9)
    multi_p.add_argument("--max-rounds", type=int, default=5)

    # status
    sub.add_parser("status", help="Show agent status")

    args = p.parse_args()
    if not args.command:
        p.print_help()
        return 1

    if args.command == "run":
        agent = DeviatrixAgent(
            n_ideas=args.n_ideas, max_rounds=args.max_rounds,
            seeds=[int(s) for s in args.seeds.split(",")],
            write_memory_os=args.write_memory_os,
            evolve_doctrine=args.evolve_doctrine,
        )
        result = agent.run(args.brief)
        print(result.summary())

    elif args.command == "autonomous":
        agent = DeviatrixAgent(
            n_ideas=args.n_ideas, max_rounds=args.max_rounds,
            evolve_doctrine=args.evolve_doctrine,
        )
        result = agent.run_autonomous()
        print(result.summary())

    elif args.command == "multi":
        agent = DeviatrixAgent(n_ideas=args.n_ideas, max_rounds=args.max_rounds)
        briefs = [b.strip() for b in args.briefs.split("|")]
        result = agent.run_multi(briefs)
        print(f"Cross-brief: {len(result.get('cross_brief_hybrids', []))} hybrids from {len(briefs)} briefs")

    elif args.command == "status":
        agent = DeviatrixAgent()
        status = agent.status()
        print(json.dumps(status, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
