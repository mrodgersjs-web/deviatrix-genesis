"""Command-line entry for Deviatrix Genesis.

Subcommands:

    deviatrix run-full   --formula "x**2 + 3*x + 1" --pop-size 500 --out ./proofs
    deviatrix run-diamond <opportunity|invention|proof> [--formula F] [--out DIR]
    deviatrix run-expedition <opportunity|invention|proof> <positive|negative|repaired> ...
    deviatrix status     show doctrine doctrine totals

Auth boundary: no credentials are loaded; the CLI only orchestrates
local execution. The sympy_mcp subcommand launches the MCP server.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .. import schemas
from ..conductors import DeviatrixConductor, EXPECTED_RUN_TOTALS


def cmd_run_full(args: argparse.Namespace) -> int:
    out = Path(args.out) if args.out else None
    c = DeviatrixConductor(
        seed=args.seed,
        output_dir=str(out) if out else None,
        verifier_id=args.verifier_id,
    )
    report = c.run(formula=args.formula, pop_size=args.pop_size)
    _print_run_summary(report)
    return 0


def cmd_run_diamond(args: argparse.Namespace) -> int:
    out = Path(args.out) if args.out else None
    diamond = schemas.DiamondKind(args.diamond)
    c = DeviatrixConductor(
        seed=args.seed,
        output_dir=str(out) if out else None,
        verifier_id=args.verifier_id,
    )
    report = c.run(formula=args.formula, pop_size=args.pop_size)
    drep = report.diamond_reports[diamond.value]
    print(f"--- {diamond.value} ---")
    for kind, o in drep["outcomes"].items():
        print(
            f"  {kind:18s} z={o['certified_z']:8.2f} band={o['band']:18s} "
            f"verdict={o['verifier_decision']:8s} action={o['system_action']}"
        )
    return 0


def cmd_run_expedition(args: argparse.Namespace) -> int:
    """Run a single expedition: positive/negative/repaired for one diamond."""
    out = Path(args.out) if args.out else None
    diamond = schemas.DiamondKind(args.diamond)

    # Build a minimal DeviatrixConductor and call _run_diamond with a
    # monkey-patched set of profiles that only fires the chosen kind.
    from ..diamonds import DiamondHarness
    from ..diamonds.expeditions import ExpeditionOutcome
    from ..iqrsqpi import IQRSQPIConductor
    from ..verifier import IndependentVerifier

    c = DeviatrixConductor(
        seed=args.seed,
        output_dir=str(out) if out else None,
        verifier_id=args.verifier_id,
    )
    h = DiamondHarness(diamond=diamond)
    pop = c.refpop_factory(args.pop_size)
    claim = c.claim_factory(args.formula, diamond)
    claim.reference_population = pop
    claim.candidate_hash = claim._hash()

    if args.kind == "positive":
        exp = c._positive_expedition(h, diamond)
    elif args.kind == "negative":
        exp = c._negative_expedition(h, diamond)
    elif args.kind == "repaired":
        # Repaired needs pos + neg outcomes first; we run both inline.
        pos_exp = c._positive_expedition(h, diamond)
        pos_o = pos_exp.run(claim)
        neg_exp = c._negative_expedition(h, diamond)
        neg_o = neg_exp.run(claim)
        exp = c._repaired_expedition(h, diamond, pos_outcome=pos_o, neg_outcome=neg_o)
    else:
        raise SystemExit(f"unknown expedition kind: {args.kind}")

    outcome: ExpeditionOutcome = exp.run(claim)
    conductor = IQRSQPIConductor(h, exp.kind, min_grill_cycles=c.min_grill)
    summary = conductor.run_quick()
    report = c.verifier.verify(outcome.packets[0])

    print(f"--- {diamond.value} / {args.kind} ---")
    print(f"  certified_z : {outcome.certified_z:.2f}")
    print(f"  band        : {outcome.band}")
    print(f"  pass_a      : {outcome.pass_a_status}")
    print(f"  pass_b      : {outcome.pass_b_status}")
    print(f"  pass_c      : {outcome.pass_c_status}")
    print(f"  iqrsqpi     : {summary['completed']} (grill={summary['n_grill_cycles']})")
    print(f"  verifier    : {report.decision.value}  reason={report.reason[:80]}")
    print(f"  sealed_hash : {outcome.packets[0].sealed_hash}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    print(json.dumps(EXPECTED_RUN_TOTALS, indent=2))
    return 0


def cmd_sympy_check(_: argparse.Namespace) -> int:
    from ..sympy_mcp import capabilities

    print(json.dumps(capabilities(), indent=2))
    return 0


def cmd_sympy_serve(_: argparse.Namespace) -> int:
    from ..sympy_mcp import start_server

    start_server()
    return 0


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────


def _print_run_summary(report: Any) -> None:
    print(f"run_id    : {report.run_id}")
    print(f"packets   : {report.packet_count}")
    print(f"verifier  : {json.dumps(report.verifier_summary, indent=2)}")
    print(f"totals    : {json.dumps(report.run_totals, indent=2)}")
    for d_name, drep in report.diamond_reports.items():
        print(f"\n--- {d_name} ---")
        for kind, o in drep["outcomes"].items():
            z = o["certified_z"]
            print(
                f"  {kind:18s} z={z:8.2f} band={o['band']:18s} "
                f"verdict={o['verifier_decision']:8s} action={o['system_action']}"
            )


# ────────────────────────────────────────────────────────────────────
# Argparse
# ────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="deviatrix",
        description="Deviatrix Genesis Idea Foundry (3×3×7)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_full = sub.add_parser("run-full", help="run the full 3×3×7 conductor")
    p_full.add_argument("--formula", default="x**2 + 3*x + 1")
    p_full.add_argument("--pop-size", type=int, default=500)
    p_full.add_argument("--seed", type=int, default=1337)
    p_full.add_argument("--verifier-id", default="verifier-master")
    p_full.add_argument("--out", help="output directory for proof artifacts")
    p_full.set_defaults(func=cmd_run_full)

    p_d = sub.add_parser("run-diamond", help="run a single diamond (3 expeditions)")
    p_d.add_argument("diamond", choices=[d.value for d in schemas.DiamondKind])
    p_d.add_argument("--formula", default="x**2 + 3*x + 1")
    p_d.add_argument("--pop-size", type=int, default=500)
    p_d.add_argument("--seed", type=int, default=1337)
    p_d.add_argument("--verifier-id", default="verifier-master")
    p_d.add_argument("--out", help="output directory for proof artifacts")
    p_d.set_defaults(func=cmd_run_diamond)

    p_e = sub.add_parser("run-expedition", help="run a single expedition")
    p_e.add_argument("diamond", choices=[d.value for d in schemas.DiamondKind])
    p_e.add_argument("kind", choices=["positive", "negative", "repaired"])
    p_e.add_argument("--formula", default="x**2 + 3*x + 1")
    p_e.add_argument("--pop-size", type=int, default=500)
    p_e.add_argument("--seed", type=int, default=1337)
    p_e.add_argument("--verifier-id", default="verifier-master")
    p_e.add_argument("--out", help="output directory for proof artifacts")
    p_e.set_defaults(func=cmd_run_expedition)

    p_status = sub.add_parser("status", help="show doctrine totals")
    p_status.set_defaults(func=cmd_status)

    p_sym = sub.add_parser("sympy-check", help="print sympy_mcp surface and exit")
    p_sym.set_defaults(func=cmd_sympy_check)

    p_serve = sub.add_parser("sympy-serve", help="launch sympy_mcp stdio server")
    p_serve.set_defaults(func=cmd_sympy_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
