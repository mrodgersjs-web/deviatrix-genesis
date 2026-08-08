# Deviatrix Genesis

> The Deviatrix Genesis Idea Foundry — 3 diamonds × 3 expeditions × 7 IQRSQPI stages,
> with SymPy MCP as the mathematical transmission and independent robust
> statistics as the telemetry.

This package is the implementation of the doctrine in
`Deviatrix Genesis Idea Foundry.md`. It refuses to let the LLM fake
rigor with decorative equations: every σ claim is bound to a
numerically computed Robust-MAD-Z (or its Qn/alternate-corpus/lower-bound
cousin), every formula is parsed by SymPy MCP, and the *only* authority
that terminates a run is the independent verifier.

## What you get

| Layer            | Module                              | Authority |
| ---------------- | ----------------------------------- | --------- |
| Schemas          | `deviatrix_genesis.schemas`         | The *only* contracts between layers |
| SymPy MCP        | `deviatrix_genesis.sympy_mcp`       | Parse, simplify, solve, diff, integrate, assumptions, singularities, inequality, adversarial substitution |
| MathExec         | `deviatrix_genesis.mathexec`        | Robust-MAD-Z, Qn, bootstrap, alternate corpus, conservative_minimum |
| Executor         | `deviatrix_genesis.mathexec.executor` | Pass A (symbolic) → Pass B (numerical) → Pass C (adversarial) |
| Diamond harness  | `deviatrix_genesis.diamonds`        | H/E/T/C/S/L/V tuple + fail_routes |
| Three diamonds   | `deviatrix_genesis.diamonds.d1_opportunity` / `d2_invention` / `d3_proof` | positive_tail / negative_tail / repaired_tail expeditions |
| Sigma-band routing | `deviatrix_genesis.diamonds.routing` | Encoded table; 30σ is the wall, not the floor |
| IQRSQPI          | `deviatrix_genesis.iqrsqpi`         | 7 stages + ≥3 grill cycles per expedition |
| Verifier         | `deviatrix_genesis.verifier`        | Reads packets, signs, decides PASS/FAIL/MUTATE/ESCALATE |
| Conductor        | `deviatrix_genesis.conductors`      | Runs 3×3×7, writes artifacts |
| CLI              | `deviatrix_genesis.cli.main`        | `python -m deviatrix_genesis run-full` |
| **v3**           | `deviatrix_genesis.v3`              | Corpus loader, proposer, collision engine, ensemble, calibration, Memory OS adapter |
| **v4**           | `deviatrix_genesis.v4`              | Async parallel runner, hashed embeddings, formula emitter, iterative rounds, memory export |
| **v5**           | `deviatrix_genesis.v5`              | Async DAG executor, structured telemetry, adaptive convergence, cross-brief fusion, resilient Memory OS loop, live dashboard, benchmark harness |
| Tests            | `deviatrix_genesis.{v3,v4,v5}.tests` | **112 tests** across all 4 versions |
| Smoke            | `deviatrix_genesis.smoke`           | End-to-end synthetic-idea run |

## The doctrine in one paragraph

Three diamonds — Opportunity, Invention, Proof — each run three
expeditions (positive_tail, negative_tail, repaired_tail). Each
expedition runs Pass A (SymPy MCP symbolic validity), Pass B
(numerical robust deviation), and Pass C (adversarial perturbation).
A MathProofPacket is sealed by SHA-256 and signed by the
IndependentVerifier. The verifier alone decides PASS / FAIL /
MUTATE / ESCALATE. ±30σ is the wall, not the floor.

```
3 diamonds
× 3 expeditions
× 7 IQRSQPI stages
= 63 outer stages

3 diamonds × 3 expeditions × ≥3 grill cycles
= ≥27 grill cycles
```

## Install + run

```bash
cd /Users/rig128gb/Projects/deviatrix-genesis
PYTHONPATH=. python3 -m deviatrix_genesis run-full --formula "x**2 + 3*x + 1" --pop-size 500 --out ./proofs
```

CLI surface:

```text
deviatrix run-full        # 3×3×7
deviatrix run-diamond  opportunity|invention|proof
deviatrix run-expedition opportunity|invention|proof positive|negative|repaired
deviatrix status          # doctrine totals
deviatrix sympy-check     # sympy_mcp surface
deviatrix sympy-serve     # launch the MCP server
```

End-to-end smoke:

```bash
PYTHONPATH=. python3 deviatrix_genesis/smoke.py --formula "x**3 + x" --pop-size 500 --out ./proofs
```

## A typical smoke result

```
run_id    : deviatrix-2ed41e7f
packets   : 9
verifier  : {'n_reports': 9, 'n_pass': 8, 'n_mutate': 1, 'n_escalate': 0, 'wall_breaches': []}

--- opportunity ---
  positive_tail      z=   20.51  band=+20σ–30σ   verdict=PASS    action=mike_gated_review
  negative_tail      z=   -2.47  band=-0σ–3σ     verdict=PASS    action=reject
  repaired_tail      z=   16.63  band=+10σ–20σ   verdict=PASS    action=adversarial_proof

--- invention ---
  positive_tail      z=   12.09  band=+10σ–20σ   verdict=PASS    action=adversarial_proof
  negative_tail      z=   -2.47  band=-0σ–3σ     verdict=MUTATE  action=reject
  repaired_tail      z=    8.68  band=+5σ–10σ    verdict=PASS    action=deep_review

--- proof ---
  positive_tail      z=   12.52  band=+10σ–20σ   verdict=PASS    action=adversarial_proof
  negative_tail      z=   -2.79  band=-0σ–3σ     verdict=PASS    action=reject
  repaired_tail      z=    9.61  band=+5σ–10σ    verdict=PASS    action=deep_review
```

Each packet is SHA-256 sealed; each verdict is signed by the verifier.

## Tests

```bash
cd /Users/rig128gb/Projects/deviatrix-genesis
PYTHONPATH=. python3 -m unittest deviatrix_genesis.tests.test_deviatrix deviatrix_genesis.v3.tests.test_v3 deviatrix_genesis.v4.tests.test_memory_export deviatrix_genesis.v5.tests.test_v5 -v
```

112 tests across all 4 versions:

| Suite | Tests | Covers |
|-------|-------|--------|
| v1 (core) | 60 | sympy_mcp, mathexec, executor, harness, diamonds, IQRSQPI, routing, verifier, conductor, schemas, CLI |
| v3 | 19 | corpus loader, proposer, collision, ensemble, calibration, Memory OS adapter, pipeline |
| v4 | 3 | memory export idempotency, candidate blocking, deterministic IDs |
| v5 | 30 | DAG (order, fan-out, errors, skip, timing), telemetry (emit, filter, unsubscribe, metrics), convergence (no-new, plateau, max-rounds, improving, reset), fusion (empty, single, complementary, overlapping), memory loop (brief builder, circuit breaker), dashboard (render, sparkline, subscribe), pipeline smoke |

## v5 Pipeline

The v5 pipeline adds adaptive convergence, structured telemetry, and a live dashboard:

```bash
PYTHONPATH=. python3 -m deviatrix_genesis.v5.pipeline \
    --brief "Operator-first GTM with financial primitives" \
    --n-ideas 9 \
    --max-rounds 10 \
    --seeds 2026,2043 \
    --dashboard
```

Or programmatically:

```python
from deviatrix_genesis.v5.pipeline import run_v5_pipeline

result = run_v5_pipeline(
    brief="Operator-first GTM with financial primitives",
    n_ideas=9,
    max_rounds=10,
    seeds=[2026, 2043],
)
print(f"{len(result['survivors'])} survivors in {result['n_rounds']} rounds")
```

### Benchmark v3 vs v5

```bash
PYTHONPATH=. python3 -m deviatrix_genesis.v5.benchmark \
    --brief "Operator-first GTM with financial primitives" \
    --engines v3,v5
```

### Individual v5 components

```python
# Async DAG executor
from deviatrix_genesis.v5.dag import DAGExecutor, DAGNode
ex = DAGExecutor()
ex.add_node(DAGNode("a", my_coro))
ex.add_node(DAGNode("b", my_coro, dependencies=["a"]))
results = await ex.execute()

# Structured telemetry
from deviatrix_genesis.v5.telemetry import get_bus
bus = get_bus()
bus.subscribe(lambda evt: print(evt.event_type))
bus.emit("round_start", "pipeline", round=1)

# Adaptive convergence
from deviatrix_genesis.v5.convergence import AdaptiveConvergence
conv = AdaptiveConvergence(min_rounds=2, max_rounds=10)
decision = conv.update(metrics, survivor_names)

# Cross-brief fusion
from deviatrix_genesis.v5.fusion import CrossBriefFusion
f = CrossBriefFusion()
hybrids = f.fuse([{"brief": "A", "survivors": [...]}, {"brief": "B", "survivors": [...]}])

# Resilient Memory OS loop
from deviatrix_genesis.v5.memory_loop import ResilientMemoryLoop
loop = ResilientMemoryLoop()
result = loop.run_cycle(brief="GTM strategy")

# Live dashboard
from deviatrix_genesis.v5.dashboard import Dashboard
dash = Dashboard(bus)
dash.start()
print(dash.render())
```

## Auth boundary

No credentials, no LLM provider keys, no remote calls. The LLM is
expected to *emit* MathClaims; this package validates and routes them.

## Doctrine reference

The original spec is at
`/Users/rig128gb/Downloads/Deviatrix Genesis Idea Foundry.md`. The
package is line-by-line conformant to the doctrine:

- §1 *SymPy MCP's exact role*: enforced by `schemas.MathClaim` (the
  LLM may not emit freeform sigma) and `IndependentVerifier` (which
  reads only packets, not LLM prose).
- §2 *Three-pass MathExec protocol*: implemented in
  `mathexec/executor.py` (Pass A / Pass B / Pass C).
- §3 *Three expeditions per diamond*: `d1_opportunity.py`,
  `d2_invention.py`, `d3_proof.py` each define the three.
- §4 *Revised diamond harness tuple*: `diamonds.DiamondHarness` with
  H, E, T, C, S, L, V.
- §5 *Revised MathProofPacket*: `schemas.MathProofPacket` with the
  full YAML shape.
- §6 *Sigma-band routing*: `diamonds/routing.py` encodes the full
  positive + negative table.
- §7 *IQRSQPI execution count*: `iqrsqpi.IQRSQPIConductor` with 7
  stages and ≥3 grill cycles per expedition; advance gate at
  `E_stage ≤ θ_stage AND E_open ≈ 0`.
- §8 *Master Conductor patch*: `conductors.DeviatrixConductor`
  matches the YAML patch.

## License

This is a doctrine artifact, built for the Deviatrix Genesis program.
