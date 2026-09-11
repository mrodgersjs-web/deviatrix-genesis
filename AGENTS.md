# Deviatrix Genesis — AGENTS.md

## What This Is
Deviatrix Genesis is a mathematical idea validation pipeline. It runs 3 diamonds × 3 expeditions × 7 IQRSQPI stages with SymPy MCP as the mathematical transmission and independent robust statistics as the telemetry. The verifier alone terminates.

## Prime Agent
The prime agent (`deviatrix_genesis/v5/prime_agent.py`) wraps the full pipeline as an autonomous goal-driven agent.

### Quick Start
```bash
# Run a single brief
$HOME/bin/deviatrix-prime run --brief "GTM strategy for AI tools"

# Run autonomous (from Memory OS)
$HOME/bin/deviatrix-prime autonomous

# Check status
$HOME/bin/deviatrix-prime status

# View run history
$HOME/bin/deviatrix-prime history --trends

# Launch web dashboard
$HOME/bin/deviatrix-prime web --port 8080

# Run tests
$HOME/bin/deviatrix-prime test
```

### Full CLI
```bash
cd $HOME/Projects/deviatrix-genesis
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
cd $HOME/Projects/deviatrix-genesis
PYTHONPATH=. python3 -m unittest deviatrix_genesis.tests.test_deviatrix deviatrix_genesis.v3.tests.test_v3 deviatrix_genesis.v4.tests.test_memory_export deviatrix_genesis.v5.tests.test_v5 -v
```

134 tests pass across all versions.

## Jake L8 Job
- **Job ID:** `run-deviatrix`
- **Goal harness:** `$HOME/.jake/goal-harnesses/deviatrix-prime.md`
- **CLI wrapper:** `$HOME/bin/deviatrix-prime`

## Gate-D Boundary
Local pipeline runs are allowed. Memory OS writes are allowed (idempotent). Public exposure of results requires Mike approval.

## RIG lattice contract (stamped)

This repository runs the shared RIG lattice: loops in `.rig/loop.yaml`, pre-tool
hooks in `.rig/hooks/`, CI gate in `.github/workflows/rig-lattice.yml`. D85 rules
apply: every outward action needs a Gate-D request + typed approval; durable
builds need four ratios >= 0.85 and a sealed proof. Shared agent substrate lives
in Supabase schema `rig_shared` (see PROGRAM.md in rig-lattice-retrofit).
