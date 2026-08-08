# RIG Memory OS � Deviatrix Genesis v3 — Integration Guide

> How Deviatrix v3 reads RIG Memory OS as substrate and writes
> verified ideas back as candidate memories.

## The loop

```
   RIG Memory OS                Deviatrix v3
   ─────────────                ────────────
   memories (27+)    ─── read ──►  corpus_loader
                                    │
                                    ▼
                          proposer.propose_from_brief
                                    │
                                    ▼
                          ensemble.run_ensemble  (3×3×7, N seeds)
                                    │
                                    ▼
                          verifier + Collision Engine
                                    │
                                    ▼
                          memory_os.write_idea ─── write ──►  new procedural
                                                              candidate memory
```

## What v3 reads

`MemoryOSAdapter.read_corpus()` reads every active/candidate
memory from the RIG Memory OS SQLite database at
`~/.rig/rig-memory-os/memory.db`. Each memory's content is
flattened into searchable text and joined with the rest of the
corpus (department substrate, JakeStudio logs, prior Deviatrix
runs) to build the *real* reference population.

The corpus is scored on three newness vectors:

* **anti_orthodoxy** — 1 - mean cosine-similarity to the corpus
* **mechanism_originality** — count of distinct named mechanisms
  in the entry (escrow, verifier, smart-contract, etc.)
* **prior_art_distance** — 1 - max cosine-similarity to the corpus

The reference population's median is *real*, not synthetic. v1/v2
used a power-law synthetic; v3 uses RIG's actual substrate. A
truly-novel idea must exceed the *real* median by ≥ 3σ to
survive.

## What v3 writes

`MemoryOSAdapter.write_idea(...)` writes one verified idea as a
candidate memory. The payload conforms to the Memory OS
`validate_memory` schema:

* `memory_type = "procedural"` (an idea is a procedure/protocol)
* `source_type = "model_synthesized"`
* `sensitivity = "internal"`
* `status = "candidate"`
* `confidence` derived from `composite_z` (clamped to [0, 1])
* `observed_at`, `valid_from`, `learned_at` = now()
* `source_refs = ["deviatrix-genesis-v3://run/<run_id>"]`
* `provenance = ["agent:deviatrix-genesis-v3", "run_id:<run_id>"]`
* `retention_policy = "deviatrix-genesis-90d"` (90-day TTL)
* `content` carries: name, formula, falsifier, composite_z,
  archetype_z, is_respin_of_known, mechanism_family, parent_names,
  action_90d, run_id

Auth: the adapter uses the existing `coding-fleet.token` and
`rig-coding-fleet` operator. No new auth surface.

## Round-trip proof

```bash
$ PYTHONPATH=. python3 -c "
from deviatrix_genesis.v3.memory_os import MemoryOSAdapter
adapter = MemoryOSAdapter()
receipt = adapter.write_idea(
    idea_name='Test idea from Deviatrix v3',
    formula='test(x)',
    falsifier='any failure',
    composite_z=15.0,
    archetype_z=5.0,
    is_respin=False,
    mechanism_family='test',
    parent_names=None,
    action_90d='run 90 days',
    run_id='test-run-001',
)
print(receipt.accepted, receipt.memory_id)
"
True <memory_id>

$ sqlite3 ~/.rig/rig-memory-os/memory.db \
    "SELECT memory_type, source_type, status FROM memories \
     WHERE content_json LIKE '%Deviatrix v3%' ORDER BY created_at DESC LIMIT 1"
procedural|model_synthesized|candidate
```

## Schema notes

The Memory OS schema (read from
`~/.rig/rig-memory-os/app/src/rig_memory_os/models.py`):

* 8 valid memory_types: `working`, `episodic`, `semantic`,
  `entity`, `procedural`, `hierarchical`, `cached`, `prospective`
* 10 source_types including `model_synthesized` (used here)
* 4 sensitivity ranks: `public`/`internal`/`confidential`/`restricted`
* 6 memory statuses: `candidate`/`active`/`canonical`/`rejected`/`superseded`/`archived`

Deviatrix always writes as `procedural` + `candidate` + `internal`,
so Mike can review before promoting to `active`.

## Run it

```bash
cd /Users/rig128gb/Projects/deviatrix-genesis

# Full pipeline (no Memory OS write)
PYTHONPATH=. python3 -m deviatrix_genesis.v3.pipeline \
    --brief "Operator-first GTM with doctrine-yield primitives" \
    --n-seeds 3 --out ./v3_proofs

# With Memory OS write
PYTHONPATH=. python3 -m deviatrix_genesis.v3.pipeline \
    --brief "Operator-first GTM with doctrine-yield primitives" \
    --n-seeds 3 --out ./v3_proofs --write-memory-os

# Direct adapter use
PYTHONPATH=. python3 -c "
from deviatrix_genesis.v3.memory_os import MemoryOSAdapter
a = MemoryOSAdapter()
print(len(a.read_corpus()), 'memories in substrate')
receipt = a.write_idea(
    idea_name='Quick test', formula='x', falsifier='fail',
    composite_z=15.0, archetype_z=5.0, is_respin=False,
    mechanism_family='test', parent_names=None,
    action_90d='run 90d', run_id='quick-001',
)
print('accepted:', receipt.accepted)
"
```

## Why this matters for RIG Memory OS

Before v3, the Memory OS only stored what humans explicitly
recorded. Now it stores what the *conductor* records — and the
conductor reads prior memories to inform new candidates. That
closes the loop:

1. Mike records a strategic decision as a `semantic` memory.
2. The next v3 run reads it via `load_memory_os_corpus`.
3. The new idea is benchmarked against it via `archetype_z`.
4. The verified idea is written back as a `procedural` memory.
5. Mike promotes it to `active` if he agrees.

Memory OS becomes a *bidirectional* substrate for idea generation:
not just a log, but a feedback loop.
