"""Synthetic canary formulas — deterministic health tripwires.

Injects known-good and known-bad formulas into every pipeline run.
If the canary trips (known-good fails or known-bad passes), the
pipeline is unhealthy and results are suspect.

Canary types:
  * positive_canary: formula that MUST pass verification
  * negative_canary: formula that MUST fail verification
  * boundary_canary: formula at exactly ±30σ (wall test)

Usage::

    from deviatrix_genesis.v5.canaries import CanaryManager

    mgr = CanaryManager()
    canaries = mgr.get_canaries()
    # Inject into pipeline run
    # Check: positive_canary.passed == True
    # Check: negative_canary.passed == False
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["CanaryManager", "Canary"]


@dataclass
class Canary:
    """A synthetic formula used as a health tripwire."""
    name: str
    formula: str
    expected_pass: bool  # True = must pass, False = must fail
    canary_type: str     # positive, negative, boundary
    description: str = ""
    actual_pass: bool | None = None
    tripped: bool = False  # True if actual != expected


class CanaryManager:
    """Manage synthetic canary formulas."""

    # Known-good formulas that should always pass
    _POSITIVE_CANARIES = [
        ("simple_polynomial", "x**2 + 3*x + 1", "Basic polynomial"),
        ("trig_identity", "sin(x)**2 + cos(x)**2", "Pythagorean identity"),
        ("exponential_decay", "exp(-x) * x", "Exponential decay"),
    ]

    # Known-bad formulas that should always fail
    _NEGATIVE_CANARIES = [
        ("zero_constant", "0", "Zero — trivial"),
        ("one_constant", "1", "One — trivial"),
        ("just_x", "x", "Just the variable"),
    ]

    # Boundary formulas (should hit ±30σ wall)
    _BOUNDARY_CANARIES = [
        ("extreme_growth", "x**100", "Extreme polynomial growth"),
    ]

    def __init__(self) -> None:
        self._canaries: list[Canary] = self._build_canaries()

    def _build_canaries(self) -> list[Canary]:
        canaries = []

        for name, formula, desc in self._POSITIVE_CANARIES:
            canaries.append(Canary(
                name=name, formula=formula, expected_pass=True,
                canary_type="positive", description=desc,
            ))

        for name, formula, desc in self._NEGATIVE_CANARIES:
            canaries.append(Canary(
                name=name, formula=formula, expected_pass=False,
                canary_type="negative", description=desc,
            ))

        for name, formula, desc in self._BOUNDARY_CANARIES:
            canaries.append(Canary(
                name=name, formula=formula, expected_pass=False,
                canary_type="boundary", description=desc,
            ))

        return canaries

    def get_canaries(self) -> list[Canary]:
        """Get all canary formulas."""
        return list(self._canaries)

    def get_positive(self) -> list[Canary]:
        """Get positive canaries (must pass)."""
        return [c for c in self._canaries if c.canary_type == "positive"]

    def get_negative(self) -> list[Canary]:
        """Get negative canaries (must fail)."""
        return [c for c in self._canaries if c.canary_type == "negative"]

    def check_results(self, verifier_results: dict[str, bool]) -> dict[str, Any]:
        """Check canary results against expectations.

        Args:
            verifier_results: mapping of canary_name -> passed (bool)
        """
        tripped: list[Canary] = []
        healthy = True

        for canary in self._canaries:
            actual = verifier_results.get(canary.name)
            if actual is not None:
                canary.actual_pass = actual
                canary.tripped = (actual != canary.expected_pass)
                if canary.tripped:
                    tripped.append(canary)
                    healthy = False

        return {
            "healthy": healthy,
            "tripped": [
                {
                    "name": c.name,
                    "type": c.canary_type,
                    "expected": c.expected_pass,
                    "actual": c.actual_pass,
                    "description": c.description,
                }
                for c in tripped
            ],
            "total_canaries": len(self._canaries),
            "checked": sum(1 for c in self._canaries if c.actual_pass is not None),
        }

    def health_report(self) -> str:
        """Generate a human-readable health report."""
        lines = ["Canary Health Report"]
        lines.append(f"  Total canaries: {len(self._canaries)}")
        for c in self._canaries:
            status = "✓" if c.actual_pass == c.expected_pass else "✗" if c.actual_pass is not None else "?"
            lines.append(f"  [{status}] {c.name}: {c.description}")
        return "\n".join(lines)
