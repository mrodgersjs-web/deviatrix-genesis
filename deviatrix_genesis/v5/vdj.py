"""VDJ Recombination of Lemma Fragments — biological formula generation.

Transplants the adaptive immune system's VDJ recombination mechanism
onto formula generation. Instead of sampling from a fixed template
library, formula fragments (Variable, Diversity, Joining segments)
are combinatorially stitched before any scoring pass.

The three segments:
  * V (Variable): core mathematical structures (x**2, log(x), sin(x))
  * D (Diversity): operators and transformations (*, +, **, compose)
  * J (Joining): boundary conditions and constraints (1/(1+x), exp(-x))

Random junctional diversity at V-D and D-J boundaries introduces
non-templated nucleotides (small constants, coefficient ranges).

Usage::

    from deviatrix_genesis.v5.vdj import VDJRecombinase

    recomb = VDJRecombinase(seed=42)
    formulas = recomb.generate(n=9, brief="GTM strategy")
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

from ..sympy_mcp.server import tool_parse

__all__ = ["VDJRecombinase", "VDJFormula"]


@dataclass
class VDJFormula:
    """A formula produced by VDJ recombination."""
    name: str
    formula: str
    v_segment: str
    d_segment: str
    j_segment: str
    junctional_diversity: str
    parseable: bool = False


# ────────────────────────────────────────────────────────────────────
# Segment libraries
# ────────────────────────────────────────────────────────────────────

V_SEGMENTS = [
    "x", "x**2", "x**3", "log(1 + x)", "sin(x)", "cos(x)",
    "exp(x)", "sqrt(abs(x))", "1/(1 + x)", "x * exp(-x)",
    "tan(x)", "atan(x)", "sinh(x)", "cosh(x)",
    "x * log(x + 1)", "x**2 * exp(-x)", "sin(x) * x",
]

D_SEGMENTS = [
    "+", "-", "*", "/", "**",
    "* (1 +", "+ (1 -", "/ (1 +",
    "* exp(-", "* sin(", "* cos(",
    "* log(1 +", "* sqrt(abs(",
    "** 2 +", "** 0.5 *",
]

J_SEGMENTS = [
    ")", " + 1)", " - 1)", " * 0.1)",
    " / (1 + x))", " + sin(x))", " * exp(-x/10))",
    " + 0.01)", " * (1 + 0.1 * sin(x)))",
    "/ (1 + x**2))", " + log(1 + abs(x)))",
]


# ────────────────────────────────────────────────────────────────────
# Junctional diversity (non-templated nucleotides)
# ────────────────────────────────────────────────────────────────────

_JUNCTIONAL_POOL = [
    "", " + 0.1", " - 0.05", " * 2", " * 0.5",
    " + 0.01 * x", " * (1 + 0.05)", " + sin(0.1*x)",
]


def _junctional_insert(rng: random.Random) -> str:
    """Generate a non-templated junctional insertion."""
    return rng.choice(_JUNCTIONAL_POOL)


# ────────────────────────────────────────────────────────────────────
# Recombinase
# ────────────────────────────────────────────────────────────────────


class VDJRecombinase:
    """Generate formulas via VDJ recombination with junctional diversity."""

    def __init__(self, seed: int = 2026) -> None:
        self.rng = random.Random(seed)

    def generate(self, n: int = 9, brief: str = "") -> list[VDJFormula]:
        """Generate n formulas via VDJ recombination."""
        formulas: list[VDJFormula] = []
        seen: set[str] = set()

        for i in range(n * 3):  # oversample to account for parse failures
            if len(formulas) >= n:
                break

            v = self.rng.choice(V_SEGMENTS)
            d = self.rng.choice(D_SEGMENTS)
            j = self.rng.choice(J_SEGMENTS)
            junction = _junctional_insert(self.rng)

            # Assemble: V D junction J
            raw = f"({v}) {d} ({junction}{j}"

            # Clean up double parens and empty junctions
            raw = raw.replace("()", "").replace("( )", "")
            if raw.count("(") > raw.count(")"):
                raw += ")" * (raw.count("(") - raw.count(")"))

            # Validate with SymPy
            result = tool_parse(raw)
            parseable = result.get("status") == "OK"
            formula_str = result.get("expression", raw) if parseable else raw

            if formula_str in seen:
                continue
            seen.add(formula_str)

            formulas.append(VDJFormula(
                name=f"vdj_{i:03d}",
                formula=formula_str,
                v_segment=v,
                d_segment=d,
                j_segment=j,
                junctional_diversity=junction,
                parseable=parseable,
            ))

        return [f for f in formulas if f.parseable][:n]

    def recombine_parents(self, parent_a: str, parent_b: str) -> VDJFormula:
        """Recombine two parent formulas by extracting their V/D/J segments."""
        # Extract the "core" from each parent (first significant term)
        va = re.findall(r'[a-z]+(?:\*\*\d+)?', parent_a)[:1]
        vb = re.findall(r'[a-z]+(?:\*\*\d+)?', parent_b)[:1]

        v = self.rng.choice(va + vb) if (va or vb) else "x"
        d = self.rng.choice(D_SEGMENTS)
        junction = _junctional_insert(self.rng)
        j = self.rng.choice(J_SEGMENTS)

        raw = f"({v}) {d} ({junction}{j}"
        if raw.count("(") > raw.count(")"):
            raw += ")" * (raw.count("(") - raw.count(")"))

        result = tool_parse(raw)
        parseable = result.get("status") == "OK"
        formula_str = result.get("expression", raw) if parseable else raw

        return VDJFormula(
            name=f"recomb_{hash(parent_a + parent_b) & 0xFFFF:04x}",
            formula=formula_str,
            v_segment=v,
            d_segment=d,
            j_segment=j,
            junctional_diversity=junction,
            parseable=parseable,
        )
