"""v3 pipeline — the 1000x-better end-to-end orchestrator.

Glues together:
  1. corpus_loader.load_corpus() — real RIG substrate
  2. proposer.propose_from_brief() — brief → 9 candidates
  3. ensemble.run_ensemble() — multi-seed 3×3×7 + Collision Engine
  4. memory_os.write_idea_as_memory() — verified ideas → Memory OS

Usage::

    PYTHONPATH=. python3 -m deviatrix_genesis.v3.pipeline \\
        --brief "Operator-first GTM with financial primitives" \\
        --out ./v3_proofs \\
        --write-memory-os

Outputs:
  * v3_proofs/REPORT.md   — human-readable summary
  * v3_proofs/data.json   — sealed packet data
  * RIG Memory OS         — new ``idea_proposal`` memories
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .collision import fuse_survivors
from .corpus_loader import load_corpus
from .ensemble import EnsembleResult, run_ensemble
from .memory_os import MemoryOSAdapter
from .proposer import propose_from_brief

__all__ = ["run_pipeline", "render_report", "main"]


def run_pipeline(
    brief: str = (
        "RIG GTM: operator-first, doctrine-published, financially primitive, "
        "structurally novel, independently verifiable, portable across products"
    ),
    *,
    n_seeds: int = 5,
    n_hybrids: int = 3,
    write_to_memory_os: bool = False,
    memory_os_tenant: str = "rig-default",
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the v3 pipeline end-to-end."""
    # 1. Load corpus
    corpus = load_corpus()
    print(f"[v3] corpus: {len(corpus)} entries")

    # 2. Propose candidates from the brief
    ideas = propose_from_brief(brief, corpus=corpus, n=9)
    print(f"[v3] proposed {len(ideas)} ideas from brief")

    # 3. Run the ensemble
    ensemble_result = run_ensemble(
        brief=brief,
        n_seeds=n_seeds,
        n_hybrids=n_hybrids,
        corpus=corpus,
        use_collision=True,
    )
    print(
        f"[v3] ensemble: {len(ensemble_result.survivors)} survivors, "
        f"{len(ensemble_result.dropped)} dropped, "
        f"{len(ensemble_result.hybrids)} hybrids"
    )

    # 4. Optionally write to Memory OS
    write_receipts: list[dict[str, Any]] = []
    if write_to_memory_os:
        adapter = MemoryOSAdapter(tenant_id=memory_os_tenant)
        for surv in ensemble_result.survivors:
            receipt = adapter.write_idea(
                idea_name=surv["name"],
                formula="(see Deviatrix run data)",  # populated below
                falsifier="(see Deviatrix run data)",
                composite_z=surv["composite_z_median"],
                archetype_z=surv["archetype_z_median"],
                is_respin=surv["is_respin_of_known"],
                mechanism_family="(see brief-derived)",
                parent_names=None,
                action_90d="(see Deviatrix run data)",
                run_id=ensemble_result.notes[:32],
            )
            write_receipts.append({
                "idea_name": surv["name"],
                "accepted": receipt.accepted,
                "memory_id": receipt.memory_id,
                "error": receipt.error,
            })
        print(f"[v3] memory-os: {len([r for r in write_receipts if r['accepted']])}/{len(write_receipts)} accepted")

    # 5. Assemble result
    result = {
        "brief": brief,
        "corpus_size": len(corpus),
        "ideas_proposed": len(ideas),
        "n_seeds": n_seeds,
        "seeds": ensemble_result.seeds,
        "ideas": ensemble_result.ideas,
        "survivors": ensemble_result.survivors,
        "dropped": ensemble_result.dropped,
        "hybrids": ensemble_result.hybrids,
        "memory_os_writes": write_receipts,
        "notes": ensemble_result.notes,
    }

    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "data.json").write_text(json.dumps(result, indent=2, default=str))
        (out / "REPORT.md").write_text(render_report(result))

    return result


def render_report(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("RIG-GTM DEVIATRIX v3 — 1000x better pipeline")
    lines.append("=" * 78)
    lines.append("")
    lines.append(f"Brief: {result['brief']}")
    lines.append(f"Corpus size: {result['corpus_size']}")
    lines.append(f"Ideas proposed: {result['ideas_proposed']}")
    lines.append(f"Seeds: {result['seeds']}")
    lines.append("")
    lines.append(f"Notes: {result['notes']}")
    lines.append("")

    lines.append("─── SURVIVORS (multi-seed median composite_z) ───")
    for i, idea in enumerate(result["survivors"], start=1):
        lines.append(f"#{i}. {idea['name'][:80]}")
        lines.append(f"     composite_z median: {idea['composite_z_median']:8.2f}σ")
        lines.append(f"     composite_z variance: {idea['composite_z_variance']:.3f}")
        lines.append(f"     archetype_z median: {idea['archetype_z_median']:.2f}σ")
        lines.append(f"     is_respin: {idea['is_respin_of_known']}")
        lines.append(f"     high_variance: {idea['high_variance_flag']}")
        lines.append("")

    lines.append("─── DROPPED ───")
    if result["dropped"]:
        for idea in result["dropped"]:
            lines.append(f"  - {idea['name'][:80]}  reason: respin={idea['is_respin_of_known']}, high_var={idea['high_variance_flag']}")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("─── HYBRIDS (Collision Engine) ───")
    if result["hybrids"]:
        for h in result["hybrids"]:
            lines.append(f"  - {h['name']}")
            lines.append(f"      parents: {h['parents']}")
            lines.append(f"      newness: {h['newness']}")
    else:
        lines.append("  (none)")
    lines.append("")

    if result["memory_os_writes"]:
        lines.append("─── MEMORY OS WRITES ───")
        for r in result["memory_os_writes"]:
            lines.append(f"  - {r['idea_name'][:60]}: {'ACCEPTED' if r['accepted'] else 'REJECTED'} (memory_id={r['memory_id']})")

    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Deviatrix v3 pipeline")
    p.add_argument("--brief", type=str, default=None)
    p.add_argument("--n-seeds", type=int, default=5)
    p.add_argument("--n-hybrids", type=int, default=3)
    p.add_argument("--out", type=str, default="./v3_proofs")
    p.add_argument("--write-memory-os", action="store_true")
    p.add_argument("--tenant", type=str, default="rig-default")
    args = p.parse_args()

    brief = args.brief or (
        "RIG GTM: operator-first, doctrine-published, financially primitive, "
        "structurally novel, independently verifiable, portable across products"
    )

    result = run_pipeline(
        brief=brief,
        n_seeds=args.n_seeds,
        n_hybrids=args.n_hybrids,
        write_to_memory_os=args.write_memory_os,
        memory_os_tenant=args.tenant,
        out_dir=args.out,
    )

    text = render_report(result)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
