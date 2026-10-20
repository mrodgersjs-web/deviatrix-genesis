# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- This commit switches the README CI badge to the shields.io workflow status URL and adds a 15 minute timeout to all three workflow jobs.
- This commit adds .github/copilot-instructions.md describing the idea pipeline, the diamonds and verifier modules, the pytest and ruff commands, and the truth rule for numbers in docs.
- This commit adds .github/CODEOWNERS, which assigns @mrodgersjs-web as the code owner for every file in the repo.

- This commit adds a ruff per-file ignore for E402 in `examples/*.py`, which insert the repo root on `sys.path` before importing, so `ruff check .` passes on the whole tree.

## [0.2.0] - 2026-10-19

### Changed

- `.github/workflows/ci.yml` runs the real suite: `pip install -e '.[dev]'`,
  ruff and `pytest` on Python 3.10-3.13, then executes the shipped example;
  the benchmark job stays main-only and waits for the test job.
  `deviatrix_genesis/tests/test_ci_workflow.py` asserts the workflow keeps
  those steps (4 tests).

- README rewritten in plain English: what the pipeline does, who it is for, and one
  runnable example; internal jargon replaced with plain terms.
- Tests now run with a single command from a clean install (`pip install -e '.[dev]'
  && pytest`); the long explicit unittest command is no longer needed.
- CI installs the package from `pyproject.toml` and runs the real suite on Python
  3.10 to 3.13, plus the runnable example.

### Added

- `pyproject.toml` packaging: sympy as a declared dependency, dev extras, `deviatrix`
  console script, ruff and coverage configuration.
- Community files: contributing guide, code of conduct, issue and pull request
  templates, dependabot configuration.
