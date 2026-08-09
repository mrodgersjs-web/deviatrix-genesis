"""Deviatrix Genesis v5 — unified CLI.

Usage::

    python -m deviatrix_genesis.v5 run --brief "GTM strategy" --dashboard
    python -m deviatrix_genesis.v5 multi --briefs "A|B|C" --out ./results
    python -m deviatrix_genesis.v5 memory-loop --from-memory-os
    python -m deviatrix_genesis.v5 benchmark --brief "GTM" --engines v3,v5
    python -m deviatrix_genesis.v5 status
    python -m deviatrix_genesis.v5 agent --brief "GTM strategy"
    python -m deviatrix_genesis.v5 agent --autonomous
    python -m deviatrix_genesis.v5 web --port 8080
    python -m deviatrix_genesis.v5 history
    python -m deviatrix_genesis.v5 evolve
    python -m deviatrix_genesis.v5 redteam --brief "GTM strategy"
"""

from __future__ import annotations

import argparse
import json
import sys


def cmd_run(args: argparse.Namespace) -> int:
    from .pipeline import run_v5_pipeline, render_v5_report

    seeds = [int(s) for s in args.seeds.split(",")]
    result = run_v5_pipeline(
        brief=args.brief, n_ideas=args.n_ideas, max_rounds=args.max_rounds,
        seeds=seeds, write_memory_os=args.write_memory_os,
        out_dir=args.out, show_dashboard=args.dashboard,
    )
    print(render_v5_report(result))
    return 0


def cmd_multi(args: argparse.Namespace) -> int:
    from .pipeline import run_multi_brief

    briefs = [b.strip() for b in args.briefs.split("|")]
    seeds = [int(s) for s in args.seeds.split(",")]
    result = run_multi_brief(
        briefs=briefs, n_ideas=args.n_ideas, max_rounds=args.max_rounds,
        seeds=seeds, out_dir=args.out,
    )
    print(f"Cross-brief fusion: {len(result['cross_brief_hybrids'])} hybrids from {len(briefs)} briefs")
    for h in result["cross_brief_hybrids"]:
        print(f"  * {h['name']} — z={h['composite_z']:.2f} — {h['brief_sources']}")
    return 0


def cmd_memory_loop(args: argparse.Namespace) -> int:
    from .memory_loop import ResilientMemoryLoop, build_brief_from_memories

    loop = ResilientMemoryLoop()
    if args.from_memory_os:
        memories = loop._query_strategic_memories(top_k=args.top_k)
        brief = build_brief_from_memories(memories)
        print(f"[memory-loop] built brief from {len(memories)} memories")
    elif args.brief:
        brief = args.brief
    else:
        print("Error: provide --brief or --from-memory-os", file=sys.stderr)
        return 1

    print(f"[memory-loop] running: {brief[:80]}...")
    result = loop.run_cycle(brief=brief, max_ideas=args.max_ideas, max_rounds=args.max_rounds)
    print(f"[memory-loop] survivors: {len(result.get('survivors', []))}")
    print(f"[memory-loop] written: {len(result.get('memory_ids_written', []))}")
    if result.get("errors"):
        print(f"[memory-loop] errors: {result['errors']}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump(result, f, indent=2, default=str)
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from .benchmark import run_benchmark, render_comparison

    engines = [e.strip() for e in args.engines.split(",")]
    seeds = [int(s) for s in args.seeds.split(",")]
    results = run_benchmark(brief=args.brief, engines=engines, seeds=seeds)
    print(render_comparison(results))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from .telemetry import get_bus
    from .run_history import RunHistory

    bus = get_bus()
    events = bus.get_events()
    history = RunHistory()
    trends = history.trend_analysis()

    print(f"Event bus: {len(events)} events")
    for etype in set(e.event_type for e in events):
        count = sum(1 for e in events if e.event_type == etype)
        print(f"  {etype}: {count}")

    print(f"\nRun history: {trends.get('runs', 0)} runs")
    if trends.get("runs", 0) > 0:
        print(f"  Best z: {trends['best_z']['mean']:.2f} (max: {trends['best_z']['max']:.2f})")
        print(f"  Wall-clock: {trends['wall_clock']['mean']:.1f}s")
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    from .prime_agent import DeviatrixAgent

    agent = DeviatrixAgent(
        n_ideas=args.n_ideas, max_rounds=args.max_rounds,
        seeds=[int(s) for s in args.seeds.split(",")],
        write_memory_os=args.write_memory_os,
        evolve_doctrine=args.evolve_doctrine,
    )

    if args.autonomous:
        result = agent.run_autonomous()
    else:
        result = agent.run(args.brief)

    print(result.summary())
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    from .web_dashboard import create_app

    try:
        import uvicorn
    except ImportError:
        print("Install uvicorn: pip install uvicorn")
        return 1

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    from .run_history import RunHistory

    history = RunHistory()
    runs = history.recent_runs(limit=args.limit)

    if not runs:
        print("No runs recorded yet.")
        return 0

    print(f"{'Run ID':<20} {'Brief':<40} {'Surv':>5} {'Best Z':>8} {'Time':>8}")
    print("-" * 85)
    for r in runs:
        print(f"{r.run_id:<20} {r.brief[:40]:<40} {r.n_survivors:>5} {r.best_z:>8.2f} {r.wall_clock_s:>7.1f}s")

    if args.trends:
        trends = history.trend_analysis()
        print(f"\nTrends ({trends['runs']} runs):")
        print(f"  Best z: {trends['best_z']['mean']:.2f} ({trends['best_z']['trend']})")
        print(f"  Wall-clock: {trends['wall_clock']['mean']:.1f}s ({trends['wall_clock']['trend']})")

    return 0


def cmd_evolve(args: argparse.Namespace) -> int:
    from .doctrine_evolution import DoctrineLearner

    learner = DoctrineLearner()
    proposal = learner.analyze_history(last_n=args.last_n)

    print(proposal.summary())
    if args.out:
        with open(args.out, "w") as f:
            json.dump(proposal.to_dict(), f, indent=2)
        print(f"\nWrote {args.out}")
    return 0


def cmd_redteam(args: argparse.Namespace) -> int:
    from .pipeline import run_v5_pipeline
    from .redteam import RedTeamAgent

    result = run_v5_pipeline(
        brief=args.brief, n_ideas=args.n_ideas,
        max_rounds=args.max_rounds, seeds=[2026],
    )
    survivors = result.get("survivors", [])
    if not survivors:
        print("No survivors to red-team.")
        return 0

    agent = RedTeamAgent()
    attacks = agent.attack_survivors(survivors)
    print(agent.generate_attack_report(attacks))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="deviatrix-v5", description="Deviatrix Genesis v5 CLI")
    sub = p.add_subparsers(dest="command")

    # run
    run_p = sub.add_parser("run", help="Run single-brief pipeline")
    run_p.add_argument("--brief", default="Operator-first GTM with financial primitives")
    run_p.add_argument("--n-ideas", type=int, default=9)
    run_p.add_argument("--max-rounds", type=int, default=10)
    run_p.add_argument("--seeds", default="2026,2043")
    run_p.add_argument("--write-memory-os", action="store_true")
    run_p.add_argument("--out", default=None)
    run_p.add_argument("--dashboard", action="store_true")

    # multi
    multi_p = sub.add_parser("multi", help="Multi-brief cross-fusion")
    multi_p.add_argument("--briefs", required=True, help="Pipe-separated briefs")
    multi_p.add_argument("--n-ideas", type=int, default=9)
    multi_p.add_argument("--max-rounds", type=int, default=5)
    multi_p.add_argument("--seeds", default="2026,2043")
    multi_p.add_argument("--out", default=None)

    # memory-loop
    ml_p = sub.add_parser("memory-loop", help="Memory OS autonomous loop")
    ml_p.add_argument("--brief", default="")
    ml_p.add_argument("--from-memory-os", action="store_true")
    ml_p.add_argument("--top-k", type=int, default=10)
    ml_p.add_argument("--max-ideas", type=int, default=12)
    ml_p.add_argument("--max-rounds", type=int, default=5)
    ml_p.add_argument("--out", default=None)

    # benchmark
    bench_p = sub.add_parser("benchmark", help="Benchmark v3 vs v5")
    bench_p.add_argument("--brief", default="Operator-first GTM with financial primitives")
    bench_p.add_argument("--engines", default="v3,v5")
    bench_p.add_argument("--seeds", default="2026")

    # status
    sub.add_parser("status", help="Show telemetry + history status")

    # agent
    agent_p = sub.add_parser("agent", help="Run prime agent")
    agent_p.add_argument("--brief", default="Operator-first GTM with financial primitives")
    agent_p.add_argument("--autonomous", action="store_true", help="Run from Memory OS")
    agent_p.add_argument("--n-ideas", type=int, default=9)
    agent_p.add_argument("--max-rounds", type=int, default=10)
    agent_p.add_argument("--seeds", default="2026,2043")
    agent_p.add_argument("--write-memory-os", action="store_true")
    agent_p.add_argument("--evolve-doctrine", action="store_true")

    # web
    web_p = sub.add_parser("web", help="Launch web dashboard")
    web_p.add_argument("--port", type=int, default=8080)
    web_p.add_argument("--host", default="127.0.0.1")

    # history
    hist_p = sub.add_parser("history", help="Show run history")
    hist_p.add_argument("--limit", type=int, default=10)
    hist_p.add_argument("--trends", action="store_true")

    # evolve
    ev_p = sub.add_parser("evolve", help="Doctrine auto-evolution")
    ev_p.add_argument("--last-n", type=int, default=20)
    ev_p.add_argument("--out", default=None)

    # redteam
    rt_p = sub.add_parser("redteam", help="Adversarial red-team survivors")
    rt_p.add_argument("--brief", default="Operator-first GTM with financial primitives")
    rt_p.add_argument("--n-ideas", type=int, default=3)
    rt_p.add_argument("--max-rounds", type=int, default=2)

    args = p.parse_args()
    if not args.command:
        p.print_help()
        return 1

    dispatch = {
        "run": cmd_run,
        "multi": cmd_multi,
        "memory-loop": cmd_memory_loop,
        "benchmark": cmd_benchmark,
        "status": cmd_status,
        "agent": cmd_agent,
        "web": cmd_web,
        "history": cmd_history,
        "evolve": cmd_evolve,
        "redteam": cmd_redteam,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
