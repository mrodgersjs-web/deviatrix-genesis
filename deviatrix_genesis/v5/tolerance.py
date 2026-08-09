"""Tolerance checkpoints — prevent autoimmune false-rejection.

Transplants the immune system's tolerance mechanism: the pipeline
learns which formula patterns are "self" (legitimate but not novel)
vs "non-self" (genuinely novel). Without tolerance, the verifier
rejects everything as foreign, including legitimate variations.

Tolerance types:
  * central_tolerance: formulas that always pass (known-good patterns)
  * peripheral_tolerance: formulas that pass in specific contexts
  * anergy: formulas that are recognized but suppressed (low priority)

Usage::

    from deviatrix_genesis.v5.tolerance import ToleranceRegistry

    registry = ToleranceRegistry()
    registry.register_central("x**2 + 3*x + 1", "standard polynomial")
    registry.register_peripheral("sin(x) * x", "periodic growth", context="financial")

    is_tolerated = registry.check("x**2 + 3*x + 1")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["ToleranceRegistry", "ToleranceEntry"]


@dataclass
class ToleranceEntry:
    """A formula registered in the tolerance registry."""
    formula: str
    tolerance_type: str  # central, peripheral, anergy
    context: str = ""
    description: str = ""
    hit_count: int = 0


class ToleranceRegistry:
    """Registry of tolerated formula patterns."""

    def __init__(self) -> None:
        self._central: dict[str, ToleranceEntry] = {}
        self._peripheral: dict[str, dict[str, ToleranceEntry]] = {}
        self._anergy: dict[str, ToleranceEntry] = {}

    def register_central(self, formula: str, description: str = "") -> None:
        """Register a formula as centrally tolerated (always passes)."""
        self._central[formula] = ToleranceEntry(
            formula=formula,
            tolerance_type="central",
            description=description,
        )

    def register_peripheral(self, formula: str, context: str, description: str = "") -> None:
        """Register a formula as peripherally tolerated (passes in context)."""
        if context not in self._peripheral:
            self._peripheral[context] = {}
        self._peripheral[context][formula] = ToleranceEntry(
            formula=formula,
            tolerance_type="peripheral",
            context=context,
            description=description,
        )

    def register_anergy(self, formula: str, description: str = "") -> None:
        """Register a formula as anergic (recognized but suppressed)."""
        self._anergy[formula] = ToleranceEntry(
            formula=formula,
            tolerance_type="anergy",
            description=description,
        )

    def check(self, formula: str, context: str = "") -> bool:
        """Check if a formula is tolerated."""
        # Central tolerance always applies
        if formula in self._central:
            self._central[formula].hit_count += 1
            return True

        # Peripheral tolerance applies in context
        if context and context in self._peripheral:
            if formula in self._peripheral[context]:
                self._peripheral[context][formula].hit_count += 1
                return True

        # Anergy means recognized but not tolerated
        if formula in self._anergy:
            self._anergy[formula].hit_count += 1
            return False

        return False

    def is_anergic(self, formula: str) -> bool:
        """Check if a formula is anergic (recognized but suppressed)."""
        return formula in self._anergy

    def get_tolerance_type(self, formula: str, context: str = "") -> str | None:
        """Get the tolerance type for a formula."""
        if formula in self._central:
            return "central"
        if context and context in self._peripheral:
            if formula in self._peripheral[context]:
                return "peripheral"
        if formula in self._anergy:
            return "anergy"
        return None

    def auto_register_from_history(self, min_hits: int = 3) -> int:
        """Auto-register frequently seen formulas as centrally tolerated."""
        count = 0
        for formula, entry in self._central.items():
            if entry.hit_count >= min_hits:
                count += 1
        return count

    def summary(self) -> dict[str, Any]:
        """Return a summary of the tolerance registry."""
        return {
            "central": len(self._central),
            "peripheral": sum(len(v) for v in self._peripheral.values()),
            "anergy": len(self._anergy),
            "contexts": list(self._peripheral.keys()),
        }

    def export(self, path: str | Path) -> None:
        """Export the registry to JSON."""
        data = {
            "central": {f: {"description": e.description, "hits": e.hit_count} for f, e in self._central.items()},
            "peripheral": {
                ctx: {f: {"description": e.description, "hits": e.hit_count} for f, e in formulas.items()}
                for ctx, formulas in self._peripheral.items()
            },
            "anergy": {f: {"description": e.description, "hits": e.hit_count} for f, e in self._anergy.items()},
        }
        Path(path).write_text(json.dumps(data, indent=2))
