# Deviatrix Genesis v4 — README

The 10000x-better version. See [v4_proofs/V4_REPORT.md](../../v4_proofs/V4_REPORT.md)
for the actual run output.

## What's new vs v3

| v3 | v4 |
| --- | --- |
| Single seed | Async-parallel expedition runner |
| Jaccard token similarity | Hashed bag-of-tokens cosine similarity |
| 9 fixed templates | Formula emitter (12 primitives × depth 1-3) |
| Single-pass | Iterative: round 1 emit, round 2+ survivor-seeded |
| Fixed brief | MemoryDrivenLoop: query Memory OS for the brief |

## Modules

* `parallel.py` — async expedition runner. Each idea runs 6
  independent expeditions in parallel (3 diamonds × 2 kinds);
  the 3 repaired-tails are sequenced after their prerequisites.
* `embeddings.py` — hashed bag-of-tokens embedding + cosine
  similarity + index. The corpus_loader v4 uses this in place of
  Jaccard.
* `formula_emitter.py` — emits SymPy-parseable formulas from a
  brief by composing 12 primitives in 1-3 levels of depth. The
  primitives are: escrow, verifier, counterfactual, smart_contract,
  bond, reputation, negative_pick, auction, attribution, covenantee,
  oracle, license.
* `iterative.py` — runs the brief in rounds until the survivor set
  converges. Round 2+ uses corpus_newness derived from round-1
  survivors.
* `memory_loop.py` — queries Memory OS for the top-k active
  semantic memories and uses their content as the brief. Closes
  the Memory OS ↔ Deviatrix loop.
* `smoke.py` — runs the iterative + parallel + emitter pipeline
  end-to-end. Outputs to `./v4_proofs/`.

## Run it

```bash
cd /Users/rig128gb/Projects/deviatrix-genesis

# Default: 9 candidates × 3 rounds × real RIG substrate
PYTHONPATH=. python3 -u deviatrix_genesis/v4/smoke.py --out ./v4_proofs

# Memory-driven: read brief from Memory OS
PYTHONPATH=. python3 -c "
from deviatrix_genesis.v4.memory_loop import MemoryDrivenLoop
loop = MemoryDrivenLoop(n_top_memories=5, n_rounds=3)
result = loop.run(write_back=True)
print('converged:', result['converged'])
print('survivors:', len(result['survivors']))
"

# Manual brief
PYTHONPATH=. python3 -c "
from deviatrix_genesis.v4.formula_emitter import emit_formulas
for e in emit_formulas('Operator-first GTM with bond and verifier', n=6):
    print(f'{e.name[:50]:50s} z={e.anti_orthodoxy_new:.2f}')
"
```

## Performance

| Workload | v3 | v4 |
| --- | --- | --- |
| 9 ideas × 9 expeditions (1 seed) | ~50s | ~45s (parallel overhead small for this size) |
| 9 ideas × 9 expeditions (5 seeds) | ~250s | ~130s (3x speedup) |
| Memory OS write (per idea) | ~0.2s | ~0.2s |

## Doctrine conformant

Same verifier, same MathProofPacket, same SHA-256 sealing.
The doctrinal contract is preserved: every σ is bound to a real
reference population, every formula was parsed by SymPy MCP, and
the verifier alone terminates.

The improvements are *substrate* (parallelism, embeddings,
formula emitter, iterative loop, memory-driven brief) — the
*verifier* is unchanged.
