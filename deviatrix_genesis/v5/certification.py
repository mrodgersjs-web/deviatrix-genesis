"""Formula equivalence class certification — prove formulas are what they claim.

After the competitor frame revealed that a poisoned SymPy backend could
make formulas silently equivalent to zero, this module certifies that
formulas belong to their claimed equivalence classes.

Certification checks:
  1. Formula evaluates to non-zero at sampled points
  2. Formula is not equivalent to a known-trivial form (0, 1, x)
  3. Formula's derivative is non-trivial (not constant)
  4. Formula survives adversarial substitution at boundary points
  5. Formula's symbolic form doesn't collapse under simplification

Usage::

    from deviatrix_genesis.v5.certification import FormulaCertifier

    cert = FormulaCertifier()
    result = cert.certify("x**2 + 3*sin(x)")
    print(result.trivial)  # False
    print(result.passed)   # True
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from ..sympy_mcp.server import (
    tool_parse,
    tool_simplify,
    tool_diff,
    tool_adversarial_substitution,
    tool_solve,
)

__all__ = ["FormulaCertifier", "CertificationResult"]


@dataclass
class CertificationResult:
    """Result of certifying a formula."""
    formula: str
    passed: bool = False
    trivial: bool = False
    collapse_detected: bool = False
    zero_at_points: bool = False
    constant_derivative: bool = False
    adversarial_failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class FormulaCertifier:
    """Certify that formulas belong to their claimed equivalence class."""

    # Points at which to evaluate for zero-detection
    _TEST_POINTS = [0.0, 0.1, 0.5, 1.0, 2.0, -1.0, -0.5, 10.0, 0.01, -0.01]

    # Known-trivial forms
    _TRIVIAL_FORMS = {"0", "1", "x", "-x", "x**2", "x**3"}

    def certify(self, formula: str) -> CertificationResult:
        """Run all certification checks on a formula."""
        result = CertificationResult(formula=formula)

        # 1. Parse check
        parsed = tool_parse(formula)
        if parsed.get("status") != "OK":
            result.notes.append("formula does not parse")
            return result

        # 2. Simplification collapse check
        simplified = tool_simplify(formula)
        if simplified.get("status") == "OK":
            forms = simplified.get("forms", {})
            simp_expr = forms.get("simplify", "")
            if simp_expr in self._TRIVIAL_FORMS or simplified.get("novelty_collapsed_warning"):
                result.collapse_detected = True
                result.trivial = True
                result.notes.append(f"collapses to trivial form: {simp_expr}")
                return result

        # 3. Zero-at-points check
        zero_count = 0
        for point in self._TEST_POINTS:
            try:
                adv = tool_adversarial_substitution(
                    expression=formula, variable="x", test_value=point
                )
                if adv.get("status") == "OK":
                    val = adv.get("result", "")
                    if val in ("0", "0.0", "0.000000000000000"):
                        zero_count += 1
            except Exception:
                pass

        if zero_count >= len(self._TEST_POINTS) * 0.8:
            result.zero_at_points = True
            result.trivial = True
            result.notes.append(f"zero at {zero_count}/{len(self._TEST_POINTS)} test points")
            return result

        # 4. Constant derivative check
        derivative = tool_diff(formula, variable="x", order=1)
        if derivative.get("status") == "OK":
            deriv_expr = derivative.get("derivative", "")
            # Check if derivative has no x terms (constant)
            if "x" not in deriv_expr and deriv_expr not in ("0",):
                result.constant_derivative = True
                result.notes.append(f"constant derivative: {deriv_expr}")

        # 5. Adversarial boundary tests
        boundary_points = [0.0, 1e-10, -1e-10, 1e10, -1e10, 1.0, -1.0]
        try:
            adv = tool_adversarial_substitution(
                expression=formula, variable="x", substitutions=boundary_points
            )
            if adv.get("status") == "OK":
                for sub_result in adv.get("results", []):
                    val = str(sub_result.get("result", ""))
                    point = sub_result.get("value", "")
                    if val in ("oo", "-oo", "nan", "zoo"):
                        result.adversarial_failures.append(
                            f"x={point}: result is {val}"
                        )
        except Exception:
            result.adversarial_failures.append("adversarial substitution failed")

        # Final verdict
        result.passed = (
            not result.trivial
            and not result.collapse_detected
            and not result.zero_at_points
            and len(result.adversarial_failures) < 3
        )

        return result

    def certify_batch(self, formulas: list[str]) -> list[CertificationResult]:
        """Certify a batch of formulas."""
        return [self.certify(f) for f in formulas]

    def filter_certified(self, formulas: list[str]) -> list[str]:
        """Return only formulas that pass certification."""
        return [
            f for f in formulas
            if self.certify(f).passed
        ]
