# Copilot instructions for deviatrix-genesis

## What this repo is

An idea-exploration pipeline. Given a brief or a formula it generates candidate
ideas, checks every claim with symbolic math (SymPy) and robust statistics, seals
the results into proof packets with SHA-256 hashes, and lets an independent
verifier return PASS / FAIL / MUTATE / ESCALATE. The output is a trail of
checkable artifacts, not prose.

The three phases are Opportunity, Invention and Proof
(`deviatrix_genesis/diamonds/d1_opportunity.py`, `d2_invention.py`,
`d3_proof.py`). Each idea goes through a symbolic pass, a numerical pass and an
adversarial pass, walking the seven-stage workflow that lives in
`deviatrix_genesis/iqrsqpi/` (the module name is the internal shorthand).

## Layout

- `deviatrix_genesis/` the package: `cli/main.py` (`deviatrix` CLI: `run-full`,
  `run-diamond`, `run-expedition`, `status`, `sympy-check`, `sympy-serve`),
  `conductors/`, `diamonds/`, `mathexec/executor.py`, `sympy_mcp/` (a stdio MCP
  server wrapping SymPy).
- `deviatrix_genesis/v3/`, `v4/`, `v5/` successive engine versions with their
  own tests.
- `deviatrix_genesis/tests/` and the per-version `tests/` folders hold the
  pytest suite; `testpaths` in pyproject.toml is `deviatrix_genesis`.
- `examples/` runnable walkthroughs; `proofs/` sample sealed output.

## Setup and test commands

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Lint before every commit: `ruff check .` (CI lints the package with
`ruff check deviatrix_genesis`; run the whole tree anyway). The suite is not
instant, it takes several minutes, so run it once per change set and let it
finish. Smoke path: `pytest deviatrix_genesis/tests`.

## Conventions

- Conventional commit prefixes: feat, fix, test, docs, ci, build, chore.
- Every behavior change lands with a test in the same commit.
- Claims must be computed, never asserted: any formula the pipeline states is
  parsed and solved, any statistic comes from the run's own data, and the
  verifier reads sealed results instead of trusting the generator.
- Determinism: fixed seeds produce the same run. Proof packets are hashed, so a
  change in output is a change in the artifact and must be intentional.
- No secrets, no API keys, no machine paths such as `/Users/...` in tracked
  files.

## Truth rule

Any number in a README, docstring, or comment must come from a command you ran
in this repo (for example `pytest`, `wc -l`, or `python -m deviatrix_genesis
status`). Update the sentence in the same commit when the number changes. Never
keep a count from an older run, and never write a pass/fail verdict that no
command produced.
