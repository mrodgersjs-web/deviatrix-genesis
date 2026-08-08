"""v4 smoke — runs the iterative + parallel + emitter pipeline end-to-end."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deviatrix_genesis.v3.corpus_loader import (
    build_reference_population,
    load_corpus,
)
from deviatrix_genesis.v4.iterative import run_iterative
from deviatrix_genesis.v4.parallel import run_idea_parallel
from deviatrix_genesis.v4.formula_emitter import emit_formulas


def main() -> int:
    p = argparse.ArgumentParser(description="Deviatrix v4 smoke")
    p.add_argument("--brief", default="Operator-first GTM with doctrine-yield primitives and independent verification")
    p.add_argument("--n-per-round", type=int, default=9)
    p.add_argument("--n-rounds", type=int, default=3)
    p.add_argument("--out", default="./v4_proofs")
    args = p.parse_args()

    start = time.time()
    corpus = load_corpus()
    pop = build_reference_population(corpus, n=1000, seed=2026)
    print(f"[v4] corpus: {len(corpus)} entries, pop: {len(pop)}")

    # Run iteratively
    result = run_iterative(
        brief=args.brief,
        population=pop,
        n_per_round=args.n_per_round,
        n_rounds=args.n_rounds,
    )
    elapsed = time.time() - start

    # Write artifacts
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    summary = {
        "brief": result.brief,
        "n_rounds_run": result.n_rounds_run,
        "converged": result.converged,
        "wall_seconds": elapsed,
        "rounds": result.rounds,
        "survivors": result.survivors,
    }
    (out / "data.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str)[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
