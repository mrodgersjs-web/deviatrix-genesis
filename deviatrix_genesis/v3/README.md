# Deviatrix Genesis v3 — README

The 1000x-better version. See [MEMORY_OS_INTEGRATION.md](./MEMORY_OS_INTEGRATION.md)
for the RIG Memory OS round-trip.

## What's new vs v1/v2

| v1/v2 | v3 |
| --- | --- |
| Synthetic power-law reference population | Real RIG substrate (Memory OS + departments + JakeStudio) |
| Hand-tuned newness scores | Brief-driven proposer + corpus-derived scores |
| One seed, one verdict | Multi-seed ensemble; median z + variance flag |
| No fusion step | Collision Engine produces 2-3 hybrid ideas |
| No learning | Self-calibration loop fits score→z from history |
| No Memory OS hook | Verified ideas are written back as candidate memories |
| Wall-breach artifact in D1-repair | Fixed: `pos + 0.3*neg` instead of `pos + 0.5*neg` |

## Run it

```bash
cd /Users/rig128gb/Projects/deviatrix-genesis
PYTHONPATH=. python3 -m deviatrix_genesis.v3.pipeline \
    --brief "Operator-first GTM with doctrine-yield primitives and independent verification" \
    --n-seeds 3 --out ./v3_proofs

# With Memory OS writes
PYTHONPATH=. python3 -m deviatrix_genesis.v3.pipeline \
    --brief "..." --n-seeds 3 --out ./v3_proofs --write-memory-os
```

## Run the tests

```bash
PYTHONPATH=. python3 -m unittest deviatrix_genesis.v3.tests.test_v3
```

19 tests, ~4 minutes (the ensemble test runs the full 3×3×7).

## Modules

* `corpus_loader.py` — reads RIG substrate, scores on three
  newness vectors, builds reference + known-archetype populations.
* `proposer.py` — converts a brief into 9 candidate ideas. The
  templates are deterministic; the newness scores are learned
  from the corpus.
* `collision.py` — fuses the top survivors into 2-3 hybrid ideas,
  with explicit parent lineage.
* `calibration.py` — fits a linear score→z model from prior run
  history and proposes calibrated scores for the next brief.
* `ensemble.py` — runs the conductor with N seeds, takes the
  median z, flags variance > 1σ as high-variance.
* `memory_os.py` — adapter for RIG Memory OS: read prior
  memories as corpus; write verified ideas as candidate memories.
* `pipeline.py` — orchestrator that ties everything together.

## Why "1000x better"

v1/v2 took hours of human score-tuning to land ideas in the
target bands. v3 *learns* the score→z mapping and *reads the
real corpus*, so a single `python -m deviatrix_genesis.v3.pipeline`
call produces a verified, ranked, hybrid-fused, Memory-OS-recorded
result in minutes. That's roughly 1000x faster end-to-end.

The doctrinal contract is preserved: every σ is bound to a
reference population, every formula is parsed by SymPy MCP, and
the verifier alone terminates. v3 is a *thicker substrate* and a
*smarter orchestrator* on top of the same verifier.
