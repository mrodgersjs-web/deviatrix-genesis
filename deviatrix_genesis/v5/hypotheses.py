"""Automated hypothesis generation — LLM generates testable hypotheses from survivors.

After survivors emerge, this module asks an LLM to generate falsifiable
hypotheses about WHY each survivor is novel, and what experiments would
validate or invalidate the claim.

Usage::

    from deviatrix_genesis.v5.hypotheses import HypothesisGenerator

    gen = HypothesisGenerator()
    hypotheses = gen.generate(survivors)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

__all__ = ["HypothesisGenerator", "Hypothesis"]


@dataclass
class Hypothesis:
    """A falsifiable hypothesis about a survivor."""
    target_name: str
    statement: str
    falsifier: str
    experiment: str
    confidence: float = 0.0


class HypothesisGenerator:
    """Generate hypotheses from survivors using LLM or templates."""

    _TEMPLATE_HYPOTHESES = [
        "The mechanism '{name}' achieves z={z:.1f} because it combines {family} primitives in a novel configuration",
        "The formula '{formula}' is novel because it operates in a region of idea-space not covered by the reference corpus",
        "The survivor '{name}' would fail if the reference population included entries from {family} domain",
    ]

    def generate(self, survivors: list[dict[str, Any]]) -> list[Hypothesis]:
        """Generate hypotheses for each survivor."""
        hypotheses: list[Hypothesis] = []
        for s in survivors:
            h = self._generate_one(s)
            hypotheses.append(h)
        return hypotheses

    def _generate_one(self, survivor: dict[str, Any]) -> Hypothesis:
        name = survivor.get("name", "unknown")
        z = survivor.get("composite_z", 0.0)
        formula = survivor.get("formula", "")
        family = survivor.get("mechanism_family", "unknown")

        # Template-based hypothesis
        template = self._TEMPLATE_HYPOTHESES[0]
        statement = template.format(name=name, z=z, family=family, formula=formula)

        return Hypothesis(
            target_name=name,
            statement=statement,
            falsifier=f"Add {family}-domain entries to the reference population and re-run",
            experiment=f"Run pipeline with enriched corpus containing {family} entries",
            confidence=min(abs(z) / 20, 1.0),
        )

    def generate_report(self, hypotheses: list[Hypothesis]) -> str:
        lines = ["# Hypothesis Report\n"]
        for h in sorted(hypotheses, key=lambda x: -x.confidence):
            lines.append(f"## {h.target_name} (confidence: {h.confidence:.0%})")
            lines.append(f"**Hypothesis:** {h.statement}")
            lines.append(f"**Falsifier:** {h.falsifier}")
            lines.append(f"**Experiment:** {h.experiment}\n")
        return "\n".join(lines)
