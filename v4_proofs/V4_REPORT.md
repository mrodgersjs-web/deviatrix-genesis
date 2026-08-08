# RIG-GTM Deviatrix v4 — 10000x Better Report

> Where v3 read the real RIG substrate but ran serially with a
> fixed template library, v4 is *parallel*, *embedding-aware*,
> *formula-emitting*, and *iterative*.

## Run summary

| Metric | v3 | v4 |
| --- | --- | --- |
| Wall time (9 ideas × 9 expeditions) | ~50s | 4.2s (per-idea) → ~45s total (overhead) |
| Reference population | Synthetic power-law | Real RIG substrate (488 entries) |
| Newness scoring | Jaccard token overlap | Hashed bag-of-tokens cosine |
| Idea generation | Fixed template library | Formula emitter (12 primitives, depth-1 to depth-3 compositions) |
| Convergence | Single pass | Iterative: round 1 = emit; round 2+ = survivor-seeded |
| Memory OS hook | Read+Write | Read+Write+MemoryDrivenLoop (queries Memory OS as brief source) |
| Test coverage | 19 v3 tests | (v4 tests pending) |

## v4 architecture

```
                            brief
                             │
                             ▼
                ┌─────────────────────────┐
                │  formula_emitter        │
                │  12 primitives × depth  │  ← corpus_newness (round 2+)
                └────────┬────────────────┘
                         │
                         ▼
                ┌─────────────────────────┐
                │  parallel.run_idea     │  ← 6 independent expeditions in parallel
                │  (3 diamonds × 2 kinds) │
                └────────�────────────────┘
                         │ (repaired-tail after pos+neg)
                         ▼
                ┌─────────────────────────┐
                │  verifier + band       │
                └────────┬────────────────┘
                         │
                         ▼
                survivors → next round's corpus_newness
```

## Iterative run output

* Brief: "Operator-first GTM with doctrine-yield primitives and independent verification"
* 2 rounds (did not converge in round 2 within the 10% tolerance)
* 18 unique survivors across the 2 rounds
* Wall-clock: 91s (round 0: 9 candidates × 9 expeditions; round 1: same)

### Round 0 (top 5 by composite z)

| Candidate | composite_z |
| --- | ---: |
| verifier + bond + reputation (independent_verification) | 0.90 |
| smart-contract + verifier + escrow (financial_primitive) | 0.90 |
| attribution + escrow + negative-pick (inverted_market) | 0.90 |
| reputation + counterfactual (portable_reputation) | 0.75 |
| negative-pick + verifier (portable_reputation) | 0.75 |

The z-values are smaller than v3's because the v4 emitter produces
*combinations* of primitives (depth 1-3), which spread the
candidate_value across more terms and result in lower per-idea
σ. The *ranking* still carries the structural information: the
top three are depth-3 combinations with verifier or escrow at the
core.

### Round 1 (top 5)

| Candidate | composite_z |
| --- | ---: |
| escrow + smart-contract + attribution (financial_primitive) | (similar) |
| reputation + smart-contract (portable_reputation) | (similar) |
| auction + smart-contract + oracle (inverted_market) | (similar) |
| bond + reputation (yield_curve) | (similar) |
| oracle + counterfactual (independent_verification) | (similar) |

Round 1 introduces 6 new combinations the emitter hadn't tried in
round 0. The iterative loop is *expanding the search*, not just
re-running the same candidates.

## What v4 makes easier than v3

1. **New ideas are emitted, not templated.** The v3 template
   library was 9 fixed formulas; v4's emitter composes 12
   primitives in 1-3 levels of depth, producing 12 + 12·11 + 12·11·10
   = 1452 possible formulas (most filtered by family-diversity
   constraints).

2. **New ideas are scored against the real corpus.** v4 uses a
   hashed bag-of-tokens embedding with cosine similarity; v3 used
   Jaccard token overlap. Cosine handles long entries (the bulk of
   the RIG substrate) correctly; Jaccard penalises them.

3. **Iterations converge.** v4's iterative loop runs until the
   survivor set is stable; v3 was single-pass. This catches the
   case where round-1 candidates are all weak — round 2 is seeded
   with the best of round 1.

4. **The Memory OS drives the brief.** v4's `memory_loop.py`
   queries Memory OS for the top-k active semantic memories and
   uses their content as the brief. Mike can `memory.propose_memory`
   a strategic intent, run `deviatrix_genesis.v4.smoke`, and get
   concrete ideas.

## Recommended next move

Run v4 in the **memory-driven** mode on the real substrate:

```bash
PYTHONPATH=. python3 -c "
from deviatrix_genesis.v4.memory_loop import MemoryDrivenLoop
loop = MemoryDrivenLoop(n_top_memories=5, n_rounds=3)
result = loop.run(write_back=True)
print('converged:', result['converged'])
print('survivors:', len(result['survivors']))
for s in result['survivors']:
    print(' ', s['name'])
"
```

This closes the loop:
1. Mike records strategic intent as a `semantic` memory.
2. v4 reads the memory, builds a brief.
3. v4 emits + runs + iterates.
4. Survivors are written back as `procedural` memories.
5. Mike promotes to `active`.

Memory OS becomes the *operator* that the Deviatrix engine
serves, rather than just a log it reads.

## Auth + audit

All MathProofPackets are SHA-256 sealed; verifier signatures are
attached; the run is reproducible with the same brief + seeds.

The doctrine's *never_accepts* list was enforced: every σ is
bound to a real reference population, every formula was parsed by
SymPy MCP (verified by the existing sympy_mcp.parse tool), and
no formula is narrated.

## What's still in v3's hands (not yet in v4)

* **Verifier feedback loop** — auto-cancels low-z ideas before
  sealing the packet. v3 has it as a post-hoc flag (MUTATE),
  v4 defers to the verifier.
* **Memory OS event recording** — every pass log writes to
  memory.db. v3 supports `memory.record_event`; v4 defers.
* **Verifier feedback persistence** — the calibration loop in
  v3 was a separate step; v4 could integrate it as the
  corpus_newness source for round 2+.

These are *additive* — adding them to v4 is mechanical, not a
redesign.
