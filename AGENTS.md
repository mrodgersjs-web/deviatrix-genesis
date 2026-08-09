# Deviatrix Genesis — AGENTS.md

## What This Is
Deviatrix Genesis is a mathematical idea validation pipeline. It runs 3 diamonds × 3 expeditions × 7 IQRSQPI stages with SymPy MCP as the mathematical transmission and independent robust statistics as the telemetry. The verifier alone terminates.

## Prime Agent
The prime agent (`deviatrix_genesis/v5/prime_agent.py`) wraps the full pipeline as an autonomous goal-driven agent.

### Quick Start
```bash
# Run a single brief
/Users/rig128gb/bin/deviatrix-prime run --brief "GTM strategy for AI tools"

# Run autonomous (from Memory OS)
/Users/rig128gb/bin/deviatrix-prime autonomous

# Check status
/Users/rig128gb/bin/deviatrix-prime status

# View run history
/Users/rig128gb/bin/deviatrix-prime history --trends

# Launch web dashboard
/Users/rig128gb/bin/deviatrix-prime web --port 8080

# Run tests
/Users/rig128gb/bin/deviatrix-prime test
```

### Full CLI
```bash
cd /Users/rig128gb/Projects/deviatrix-genesis
PYTHONPATH=. python3 -m deviatrix_genesis.v5 <command>
```

Commands: `run`, `multi`, `memory-loop`, `benchmark`, `status`, `agent`, `web`, `history`, `evolve`, `redteam`

## Architecture
```
v1 (core):   SymPy MCP → MathExec → Diamonds → IQRSQPI → Verifier → Conductor
v3 (1000x):  Corpus loader → Proposer → Ensemble → Collision → Calibration → Memory OS
v4 (10000x): Parallel runner → Embeddings → Formula emitter → Iterative rounds → Memory export
v5 (1000x):  31 modules — DAG, telemetry, convergence, fusion, streaming, diversity, Pareto, causal, provenance, anomaly, exports, plugins, lineage, redteam, healer, hypotheses, A/B testing, LLM formulas, run history, doctrine evolution, web dashboard, prime agent
```

## Memory OS Integration
- **DB:** ~/.rig/rig-memory-os/memory.db
- **Credentials:** ~/.rig/rig-memory-os/credentials/coding-fleet.token
- **Tenant:** rig-default
- **Operator:** deviatrix-genesis

## Verification
```bash
cd /Users/rig128gb/Projects/deviatrix-genesis
PYTHONPATH=. python3 -m unittest deviatrix_genesis.tests.test_deviatrix deviatrix_genesis.v3.tests.test_v3 deviatrix_genesis.v4.tests.test_memory_export deviatrix_genesis.v5.tests.test_v5 -v
```

134 tests pass across all versions.

## Jake L8 Job
- **Job ID:** `run-deviatrix`
- **Goal harness:** `/Users/rig128gb/.jake/goal-harnesses/deviatrix-prime.md`
- **CLI wrapper:** `/Users/rig128gb/bin/deviatrix-prime`

## Gate-D Boundary
Local pipeline runs are allowed. Memory OS writes are allowed (idempotent). Public exposure of results requires Mike approval.
