"""End-to-end smoke for Deviatrix Genesis.

Run a synthetic idea through the full 3×3×7 conductor and produce a
written summary. This is the *minimum* the doctrine asks for: 3
diamonds × 3 expeditions × 7 IQRSQPI stages = 63 outer stages,
27+ grill cycles, 9 sealed MathProofPackets, 9 verifier decisions.

Usage::

    PYTHONPATH=. python3 deviatrix_genesis/smoke.py
    PYTHONPATH=. python3 deviatrix_genesis/smoke.py --formula "x**3 + x" --out ./proofs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root or from inside the package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deviatrix_genesis.conductors import DeviatrixConductor, EXPECTED_RUN_TOTALS


def smoke(
    *,
    formula: str = "x**2 + 3*x + 1",
    pop_size: int = 500,
    seed: int = 1337,
    out: Path | None = None,
) -> dict:
    conductor = DeviatrixConductor(
        seed=seed,
        output_dir=str(out) if out else None,
        verifier_id="verifier-smoke",
    )
    report = conductor.run(formula=formula, pop_size=pop_size)
    return report.to_dict()


def render_text(report: dict) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("DEVIATRIX GENESIS — smoke run")
    lines.append("=" * 72)
    lines.append(f"run_id    : {report['run_id']}")
    lines.append(f"started   : {report['started_at']}")
    lines.append(f"finished  : {report['finished_at']}")
    lines.append(f"packets   : {report['packet_count']}")
    lines.append("")
    lines.append("Doctrine run totals:")
    for k, v in report["run_totals"].items():
        lines.append(f"  {k:30s}: {v}")
    lines.append("")
    lines.append("Verifier summary:")
    for k, v in report["verifier_summary"].items():
        lines.append(f"  {k:30s}: {v}")
    lines.append("")
    for d_name, drep in report["diamond_reports"].items():
        lines.append(f"--- {d_name} ---")
        lines.append(f"  n_packets={drep['n_packets']}  n_trace={drep['n_trace']}")
        for kind, o in drep["outcomes"].items():
            lines.append(
                f"  {kind:18s} z={o['certified_z']:8.2f}  "
                f"band={o['band']:18s}  "
                f"verdict={o['verifier_decision']:8s}  "
                f"action={o['system_action']}"
            )
            lines.append(
                f"  {'':18s} pass_a={o['pass_a']:6s}  "
                f"pass_b={o['pass_b']:6s}  "
                f"pass_c={o['pass_c']:6s}  "
                f"sealed={o['sealed_hash'][:16]}…"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Deviatrix Genesis E2E smoke")
    p.add_argument("--formula", default="x**2 + 3*x + 1")
    p.add_argument("--pop-size", type=int, default=500)
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--out", help="directory for proof artifacts")
    args = p.parse_args()

    out = Path(args.out) if args.out else None
    report = smoke(
        formula=args.formula,
        pop_size=args.pop_size,
        seed=args.seed,
        out=out,
    )
    text = render_text(report)
    print(text)

    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / "smoke_report.json").write_text(
            json.dumps(report, indent=2, default=str)
        )
        (out / "smoke_report.txt").write_text(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
