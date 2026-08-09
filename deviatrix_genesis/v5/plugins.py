"""Plugin system — register custom diamonds, expeditions, and scorers.

Plugins are discovered via Python entry points (group: deviatrix_plugins)
or registered programmatically.

Usage::

    # Register a custom scorer
    from deviatrix_genesis.v5.plugins import registry

    @registry.scorer("my_scorer")
    def my_custom_scorer(formula: str, population: list[float]) -> float:
        return len(formula) / len(population)

    # Use plugins in pipeline
    scorers = registry.get_scorers()
"""

from __future__ import annotations

import importlib.metadata
from typing import Any, Callable

__all__ = ["PluginRegistry", "registry"]


class PluginRegistry:
    """Central registry for Deviatrix plugins."""

    def __init__(self) -> None:
        self._scorers: dict[str, Callable[..., float]] = {}
        self._transformers: dict[str, Callable[..., Any]] = {}
        self._validators: dict[str, Callable[..., bool]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Load plugins from entry points on first access."""
        if self._loaded:
            return
        self._loaded = True

        try:
            eps = importlib.metadata.entry_points()
            group = eps.select(group="deviatrix_plugins") if hasattr(eps, "select") else []
            for ep in group:
                try:
                    plugin = ep.load()
                    if hasattr(plugin, "register"):
                        plugin.register(self)
                except Exception:
                    pass
        except Exception:
            pass

    # ── Decorators ──────────────────────────────────────────────────

    def scorer(self, name: str) -> Callable:
        """Register a custom scorer function."""
        def decorator(fn: Callable[..., float]) -> Callable[..., float]:
            self._scorers[name] = fn
            return fn
        return decorator

    def transformer(self, name: str) -> Callable:
        """Register a formula transformer."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._transformers[name] = fn
            return fn
        return decorator

    def validator(self, name: str) -> Callable:
        """Register a formula validator."""
        def decorator(fn: Callable[..., bool]) -> Callable[..., bool]:
            self._validators[name] = fn
            return fn
        return decorator

    # ── Getters ─────────────────────────────────────────────────────

    def get_scorers(self) -> dict[str, Callable[..., float]]:
        self._ensure_loaded()
        return dict(self._scorers)

    def get_transformers(self) -> dict[str, Callable[..., Any]]:
        self._ensure_loaded()
        return dict(self._transformers)

    def get_validators(self) -> dict[str, Callable[..., bool]]:
        self._ensure_loaded()
        return dict(self._validators)

    def apply_scorers(self, formula: str, population: list[float]) -> dict[str, float]:
        """Run all registered scorers and return their results."""
        self._ensure_loaded()
        results: dict[str, float] = {}
        for name, scorer in self._scorers.items():
            try:
                results[name] = scorer(formula, population)
            except Exception:
                results[name] = 0.0
        return results

    def apply_transformers(self, formula: str) -> str:
        """Run all registered transformers in order."""
        self._ensure_loaded()
        result = formula
        for name, transformer in self._transformers.items():
            try:
                result = transformer(result)
            except Exception:
                pass
        return result

    def validate(self, formula: str) -> dict[str, bool]:
        """Run all registered validators."""
        self._ensure_loaded()
        results: dict[str, bool] = {}
        for name, validator in self._validators.items():
            try:
                results[name] = validator(formula)
            except Exception:
                results[name] = False
        return results


# Module-level singleton
registry = PluginRegistry()
