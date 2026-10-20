"""Checks that .github/workflows/ci.yml runs the real suite on every supported Python.

Task this file addresses: the workflow is configuration, and a wrong step or
matrix entry is only noticed when CI fails after a push. This test reads the
workflow file and asserts what it must keep containing:

- it runs on push and pull_request with read-only contents permission;
- the test job installs the package and runs pytest across Python 3.10-3.13;
- lint runs on the package and the shipped example is executed;
- the benchmark job stays main-only and waits for the test job.
"""

from __future__ import annotations

import unittest
from pathlib import Path

CI = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"


class TestCiWorkflow(unittest.TestCase):
    def setUp(self) -> None:
        self.text = CI.read_text(encoding="utf-8")

    def test_triggers_and_permissions(self) -> None:
        self.assertIn("push:", self.text)
        self.assertIn("pull_request:", self.text)
        self.assertIn("permissions:\n  contents: read", self.text)

    def test_matrix_runs_the_suite_on_supported_pythons(self) -> None:
        self.assertIn('python-version: ["3.10", "3.11", "3.12", "3.13"]', self.text)
        self.assertIn("pip install -e '.[dev]'", self.text)
        self.assertIn("run: pytest", self.text)

    def test_lint_and_shipped_example_run(self) -> None:
        self.assertIn("ruff check deviatrix_genesis", self.text)
        self.assertIn("python examples/python_api.py", self.text)

    def test_benchmark_stays_main_only_and_after_tests(self) -> None:
        self.assertIn("if: github.ref == 'refs/heads/main'", self.text)
        self.assertIn("needs: [test]", self.text)


if __name__ == "__main__":
    unittest.main()
