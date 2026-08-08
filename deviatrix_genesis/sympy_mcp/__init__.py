"""SymPy MCP — the dyno and mathematical transmission controller.

This module is the *mathematical transmission*, not the creativity engine.
It does not invent ideas. It parses, simplifies, checks, differentiates,
solves, and rejects symbolic structures emitted by an LLM generator.

Surface
-------

The module is importable without the optional ``mcp`` SDK. When the SDK
is present, :func:`start_server` launches a proper MCP server. When it is
absent, :data:`TOOL_NAMES` and :data:`RESOURCE_URIS` are still exported
so smoke checks can verify the surface.

Install the optional MCP dependency::

    pip install "deviatrix-genesis[mcp]"

Then start the server::

    python -m deviatrix_genesis.sympy_mcp

Auth boundary
-------------
The server runs **locally only**. No LLM provider credentials are passed
through the MCP transport. Callers that need to invoke the LLM do so
via the regular Python API or CLI; this server only validates math.
"""

from __future__ import annotations

import json
from typing import Any

__all__ = [
    "TOOL_NAMES",
    "RESOURCE_URIS",
    "PROMPT_NAMES",
    "tool_parse",
    "tool_simplify",
    "tool_solve",
    "tool_diff",
    "tool_integrate",
    "tool_check_assumptions",
    "tool_find_singularities",
    "tool_check_inequality",
    "tool_adversarial_substitution",
    "start_server",
]


# ── Surface declarations ─────────────────────────────────────────────────────
TOOL_NAMES: list[str] = [
    "sympy_parse",
    "sympy_simplify",
    "sympy_solve",
    "sympy_diff",
    "sympy_integrate",
    "sympy_check_assumptions",
    "sympy_find_singularities",
    "sympy_check_inequality",
    "sympy_adversarial_substitution",
]

RESOURCE_URIS: list[str] = [
    "sympy://version",
    "sympy://capabilities",
]

PROMPT_NAMES: list[str] = [
    "review_symbolic",
    "explain_failure",
]


def __getattr__(name: str) -> Any:
    """Lazy attribute access for tool functions and start_server."""
    if name in {
        "tool_parse",
        "tool_simplify",
        "tool_solve",
        "tool_diff",
        "tool_integrate",
        "tool_check_assumptions",
        "tool_find_singularities",
        "tool_check_inequality",
        "tool_adversarial_substitution",
        "start_server",
    }:
        from . import server

        return getattr(server, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def capabilities() -> dict[str, Any]:
    """Return a static description of the sympy_mcp surface."""
    return {
        "tools": TOOL_NAMES,
        "resources": RESOURCE_URIS,
        "prompts": PROMPT_NAMES,
        "version": __import__("sympy").__version__,
        "role": "symbolic transmission controller (not creativity engine)",
        "do_not_use_for": [
            "creative ideation",
            "freeform sigma narration",
            "estimator selection",
        ],
    }


def main() -> None:
    """Console entry: print capabilities then optionally start the server."""
    import argparse

    parser = argparse.ArgumentParser(description="sympy_mcp server")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Print the surface and exit (smoke check).",
    )
    args = parser.parse_args()

    if args.check:
        print(json.dumps(capabilities(), indent=2))
        return

    start_server()


if __name__ == "__main__":
    main()
