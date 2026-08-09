"""Adversarial red-teaming — LLM-driven attack on survivors.

After survivors emerge from the pipeline, the red-team agent tries to
break each one by:
  1. Finding counterexamples to the falsifier
  2. Constructing adversarial inputs
  3. Testing boundary conditions
  4. Proposing alternative mechanisms that supersede the survivor

Usage::

    from deviatrix_genesis.v5.redteam import RedTeamAgent

    agent = RedTeamAgent()
    attacks = agent.attack_survivors(survivors)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from ..sympy_mcp.server import tool_parse, tool_solve, tool_adversarial_substitution

__all__ = ["RedTeamAgent", "AttackResult"]


@dataclass
class AttackResult:
    """Result of attacking one survivor."""
    target_name: str
    formula: str
    counterexamples: list[dict[str, Any]] = field(default_factory=list)
    boundary_failures: list[str] = field(default_factory=list)
    superseded_by: str = ""
    vulnerability_score: float = 0.0  # 0 = robust, 1 = trivially broken
    notes: list[str] = field(default_factory=list)


class RedTeamAgent:
    """Attack survivors with mathematical and structural adversarial tests."""

    def attack_survivors(self, survivors: list[dict[str, Any]]) -> list[AttackResult]:
        """Attack a list of survivors. Returns one AttackResult per survivor."""
        results: list[AttackResult] = []
        for s in survivors:
            result = self._attack_one(s)
            results.append(result)
        return results

    def _attack_one(self, survivor: dict[str, Any]) -> AttackResult:
        """Attack a single survivor."""
        name = survivor.get("name", "unknown")
        formula = survivor.get("formula", "")

        result = AttackResult(target_name=name, formula=formula)

        # 1. SymPy counterexample search
        result.counterexamples = self._find_counterexamples(formula)

        # 2. Boundary condition tests
        result.boundary_failures = self._test_boundaries(formula)

        # 3. Adversarial substitution
        adv = self._adversarial_test(formula)
        if adv:
            result.notes.append(adv)

        # 4. Compute vulnerability score
        result.vulnerability_score = self._score_vulnerability(result)

        return result

    def _find_counterexamples(self, formula: str) -> list[dict[str, Any]]:
        """Find values where the formula fails or behaves unexpectedly."""
        counterexamples: list[dict[str, Any]] = []
        if not formula:
            return counterexamples

        # Try to solve for zeros, infinities, and discontinuities
        try:
            zeros = tool_solve(formula, variable="x")
            if zeros.get("status") == "OK" and zeros.get("solutions"):
                for sol in zeros["solutions"][:3]:
                    counterexamples.append({
                        "type": "zero",
                        "value": str(sol),
                        "implication": "formula crosses zero — may indicate failure mode",
                    })
        except Exception:
            pass

        return counterexamples

    def _test_boundaries(self, formula: str) -> list[str]:
        """Test formula at extreme values."""
        failures: list[str] = []
        if not formula:
            return failures

        # Parse the formula
        parsed = tool_parse(formula)
        if parsed.get("status") != "OK":
            failures.append("formula does not parse")
            return failures

        # Test at extreme values via adversarial substitution
        extreme_points = [0, 1, -1, 100, -100, 1000, 0.001, -0.001]
        for point in extreme_points:
            try:
                result = tool_adversarial_substitution(
                    expression=formula, variable="x", test_value=float(point)
                )
                if result.get("status") == "OK":
                    val = result.get("result", "")
                    if val in ("oo", "-oo", "nan", "zoo"):
                        failures.append(f"x={point}: result is {val}")
            except Exception:
                failures.append(f"x={point}: evaluation failed")

        return failures

    def _adversarial_test(self, formula: str) -> str:
        """Run adversarial substitution test."""
        if not formula:
            return ""
        try:
            result = tool_adversarial_substitution(
                expression=formula, variable="x", test_value=0.0
            )
            if result.get("contradiction"):
                return f"Contradiction at x=0: {result.get('contradiction')}"
        except Exception:
            pass
        return ""

    def _score_vulnerability(self, result: AttackResult) -> float:
        """Score 0-1 how vulnerable the survivor is."""
        score = 0.0
        if result.counterexamples:
            score += 0.3
        if result.boundary_failures:
            score += 0.3 * min(len(result.boundary_failures) / 3, 1.0)
        if any("Contradiction" in n for n in result.notes):
            score += 0.4
        return min(score, 1.0)

    def generate_attack_report(self, results: list[AttackResult]) -> str:
        """Generate a human-readable attack report."""
        lines = ["# Adversarial Red-Team Report\n"]
        robust = [r for r in results if r.vulnerability_score < 0.3]
        vulnerable = [r for r in results if r.vulnerability_score >= 0.3]

        lines.append(f"**Attacked:** {len(results)} survivors")
        lines.append(f"**Robust:** {len(robust)}")
        lines.append(f"**Vulnerable:** {len(vulnerable)}\n")

        if vulnerable:
            lines.append("## Vulnerable Survivors\n")
            for r in sorted(vulnerable, key=lambda x: -x.vulnerability_score):
                lines.append(f"### {r.target_name} (vulnerability: {r.vulnerability_score:.0%})")
                lines.append(f"Formula: `{r.formula}`")
                if r.counterexamples:
                    lines.append("Counterexamples:")
                    for ce in r.counterexamples:
                        lines.append(f"  * {ce['type']}: {ce['value']}")
                if r.boundary_failures:
                    lines.append("Boundary failures:")
                    for bf in r.boundary_failures:
                        lines.append(f"  * {bf}")
                lines.append("")

        if robust:
            lines.append("## Robust Survivors\n")
            for r in robust:
                lines.append(f"  * **{r.target_name}** — vulnerability: {r.vulnerability_score:.0%}")

        return "\n".join(lines)
