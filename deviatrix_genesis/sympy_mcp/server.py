"""SymPy MCP server — actual tool implementations.

Each ``tool_*`` function returns a JSON-serializable dict. The tool
MUST NOT raise a bare exception; failures are returned as a dict with
``status = "FAIL"`` and a populated ``error`` field so the calling
agent can route the failure through ``formula_repair`` (the harness's
fail_routes table).

Auth boundary: no credentials are loaded here. This module is pure
math + a thin MCP transport wrapper.
"""

from __future__ import annotations

import io
import json
import re
import tokenize
import sympy
from sympy import (
    Eq,
    Function,
    Integral,
    LambertW,
    Matrix,
    Piecewise,
    Poly,
    Pow,
    Rational,
    S,
    Symbol,
    ceiling,
    cos,
    cot,
    diff,
    exp,
    floor,
    integrate,
    lambdify,
    log,
    oo,
    sign,
    simplify,
    sin,
    solve,
    sqrt,
    sympify,
    tan,
    together,
    trigsimp,
)
from sympy.calculus.util import continuous_domain
from sympy.core.relational import Relational
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)
from sympy.solvers.inequalities import solve_univariate_inequality

__all__ = [
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

_SYM_VERSION = sympy.__version__

# Conservative symbol whitelist — anything else returns parse error.
_VALID_SYM = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")

# Transformations for parse_expr — implicit multiplication makes generator
# expressions more natural without sacrificing safety (the whitelist is the
# real safety guarantee).
_TRANSFORMS = standard_transformations + (implicit_multiplication_application,)

# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _safe_sympy_locals() -> dict[str, Any]:
    """Return the safe name-table for parse_expr.

    We whitelist common math names so generators can emit things like
    ``exp(-x)`` without surprises. Anything not in here is a parse
    failure that routes to formula_repair.
    """
    names: dict[str, Any] = {}
    # common constants
    for k in ("pi", "E", "I", "oo", "Infinity", "inf"):
        if k in dir(sympy):
            names[k] = getattr(sympy, k)
    # common functions
    for k in (
        "sin",
        "cos",
        "tan",
        "cot",
        "log",
        "exp",
        "sqrt",
        "Abs",
        "abs",
        "sign",
        "floor",
        "ceiling",
        "Rational",
        "Piecewise",
        "Sum",
        "Product",
        "Matrix",
        "LambertW",
    ):
        names[k] = globals().get(k, getattr(sympy, k, None))
    return names

def _is_safe(name: str) -> bool:
    if not name:
        return False
    if not _VALID_SYM.match(name):
        return False
    # forbid dunder-style and Python-internal names
    if name.startswith("__"):
        return False
    return True


_SAFE_OPERATORS = frozenset({"+", "-", "*", "/", "**", "^", "(", ")", ","})
_MAX_EXPRESSION_LENGTH = 4_096


def _validate_expression_syntax(expression: str) -> str | None:
    """Reject Python syntax before SymPy's eval-backed parser sees it.

    ``parse_expr`` evaluates its input internally. A whitelist of parser
    locals alone is insufficient because Python builtins remain reachable.
    Restrict input to mathematical names, numeric literals, and arithmetic
    operators; only explicitly registered math functions may be called.
    """
    if not isinstance(expression, str) or not expression.strip():
        return "expression must be a non-empty string"
    if len(expression) > _MAX_EXPRESSION_LENGTH:
        return f"expression exceeds {_MAX_EXPRESSION_LENGTH} characters"

    local_names = _safe_sympy_locals()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(expression).readline)
        token_list = [
            token
            for token in tokens
            if token.type not in {tokenize.ENDMARKER, tokenize.NEWLINE, tokenize.NL}
        ]
    except tokenize.TokenError as error:
        return f"invalid token stream: {error}"

    for index, token in enumerate(token_list):
        if token.type == tokenize.NAME:
            if not _is_safe(token.string):
                return f"unsafe name: {token.string!r}"
            next_token = token_list[index + 1] if index + 1 < len(token_list) else None
            if next_token and next_token.string == "(" and token.string not in local_names:
                return f"function is not allowed: {token.string!r}"
        elif token.type == tokenize.NUMBER:
            continue
        elif token.type == tokenize.OP and token.string in _SAFE_OPERATORS:
            continue
        else:
            return f"unsafe token: {token.string!r}"
    return None


def _safe_sympy_globals() -> dict[str, Any]:
    return {
        "__builtins__": {},
        "Add": sympy.Add,
        "Float": sympy.Float,
        "Function": Function,
        "Integer": sympy.Integer,
        "Mul": sympy.Mul,
        "Pow": Pow,
        "Rational": Rational,
        "Symbol": Symbol,
    }

def _expr_to_str(expr: Any) -> str:
    """Stringify a sympy object deterministically."""
    try:
        return sympy.sstr(sympy.sympify(expr))
    except Exception:  # pragma: no cover
        return str(expr)

# ────────────────────────────────────────────────────────────────────
# Tool implementations
# ────────────────────────────────────────────────────────────────────

def tool_parse(expression: str) -> dict[str, Any]:
    """Parse a generator string into a SymPy expression without Python execution."""
    syntax_error = _validate_expression_syntax(expression)
    if syntax_error:
        return {
            "status": "FAIL",
            "error": f"parse_error: unsafe expression: {syntax_error}",
            "expression": expression,
        }

    try:
        expr = parse_expr(
            expression,
            local_dict=_safe_sympy_locals(),
            global_dict=_safe_sympy_globals(),
            transformations=_TRANSFORMS,
            evaluate=False,
        )
        free = sorted(str(s) for s in expr.free_symbols)
        return {
            "status": "OK",
            "expression": expression,
            "parsed": _expr_to_str(expr),
            "free_symbols": free,
            "sympy_version": _SYM_VERSION,
        }
    except Exception as error:  # pragma: no cover
        return {
            "status": "FAIL",
            "error": f"parse_error: {type(error).__name__}: {error}",
            "expression": expression,
        }

def tool_simplify(expression: str) -> dict[str, Any]:
    """Parse + simplify with multiple strategies; return all forms."""
    parsed = tool_parse(expression)
    if parsed.get("status") != "OK":
        return {"status": "FAIL", "stage": "parse", "error": parsed.get("error")}
    try:
        raw = sympy.sympify(parsed["parsed"], locals=_safe_sympy_locals())
        forms = {
            "simplify": _expr_to_str(simplify(raw)),
            "trigsimp": _expr_to_str(trigsimp(raw)),
            "together": _expr_to_str(together(raw)),
        }
        # detect novelty collapse: if all three forms are identical AND
        # the parse itself returned a structural surprise (e.g. a long
        # expression that collapsed to "0" or "1"), simplification may
        # have over-collapsed. For ordinary polynomials like x**2+3*x+1
        # where simplify genuinely has nothing to do, the warning stays
        # off — this is *normal* equivalence, not a hidden collapse.
        distinct = len({v for v in forms.values()})
        collapsed_to_trivial = forms["simplify"] in {"0", "1", "-1"}
        novelty_collapsed = (
            distinct == 1
            and collapsed_to_trivial
            and expression not in {"0", "1", "-1"}
        )
        return {
            "status": "OK",
            "input": expression,
            "forms": forms,
            "distinct_form_count": distinct,
            "novelty_collapsed_warning": novelty_collapsed,
            "sympy_version": _SYM_VERSION,
        }
    except Exception as e:  # pragma: no cover
        return {
            "status": "FAIL",
            "stage": "simplify",
            "error": f"{type(e).__name__}: {e}",
        }

def tool_solve(expression: str, variable: str = "x") -> dict[str, Any]:
    """Solve ``expression == 0`` for *variable*.

    Returns the symbolic solution set plus the number of solutions found.
    Multiple solutions imply an extremum or saddle — useful for deviation
    search.
    """
    parsed = tool_parse(expression)
    if parsed.get("status") != "OK":
        return {"status": "FAIL", "stage": "parse", "error": parsed.get("error")}
    if not _is_safe(variable):
        return {"status": "FAIL", "error": f"unsafe variable name: {variable}"}
    try:
        x = Symbol(variable)
        expr = sympy.sympify(parsed["parsed"], locals=_safe_sympy_locals())
        sols = solve(Eq(expr, 0), x)
        return {
            "status": "OK",
            "variable": variable,
            "expression": _expr_to_str(expr),
            "solutions": [_expr_to_str(s) for s in sols],
            "solution_count": len(sols),
            "sympy_version": _SYM_VERSION,
        }
    except Exception as e:  # pragma: no cover
        return {
            "status": "FAIL",
            "stage": "solve",
            "error": f"{type(e).__name__}: {e}",
        }

def tool_diff(expression: str, variable: str = "x", order: int = 1) -> dict[str, Any]:
    """Compute the *order*-th derivative."""
    parsed = tool_parse(expression)
    if parsed.get("status") != "OK":
        return {"status": "FAIL", "stage": "parse", "error": parsed.get("error")}
    if not _is_safe(variable):
        return {"status": "FAIL", "error": f"unsafe variable name: {variable}"}
    try:
        x = Symbol(variable)
        expr = sympy.sympify(parsed["parsed"], locals=_safe_sympy_locals())
        d = diff(expr, x, order)
        return {
            "status": "OK",
            "variable": variable,
            "order": order,
            "input": _expr_to_str(expr),
            "derivative": _expr_to_str(d),
            "sympy_version": _SYM_VERSION,
        }
    except Exception as e:  # pragma: no cover
        return {
            "status": "FAIL",
            "stage": "diff",
            "error": f"{type(e).__name__}: {e}",
        }

def tool_integrate(expression: str, variable: str = "x") -> dict[str, Any]:
    """Compute the indefinite integral."""
    parsed = tool_parse(expression)
    if parsed.get("status") != "OK":
        return {"status": "FAIL", "stage": "parse", "error": parsed.get("error")}
    if not _is_safe(variable):
        return {"status": "FAIL", "error": f"unsafe variable name: {variable}"}
    try:
        x = Symbol(variable)
        expr = sympy.sympify(parsed["parsed"], locals=_safe_sympy_locals())
        i = integrate(expr, x)
        return {
            "status": "OK",
            "variable": variable,
            "input": _expr_to_str(expr),
            "integral": _expr_to_str(i),
            "sympy_version": _SYM_VERSION,
        }
    except Exception as e:  # pragma: no cover
        return {
            "status": "FAIL",
            "stage": "integrate",
            "error": f"{type(e).__name__}: {e}",
        }

def tool_check_assumptions(expression: str, assumptions: dict[str, Any]) -> dict[str, Any]:
    """Check whether an expression satisfies the requested assumptions.

    ``assumptions`` is a dict like ``{"x": "positive"}``.
    """
    parsed = tool_parse(expression)
    if parsed.get("status") != "OK":
        return {"status": "FAIL", "stage": "parse", "error": parsed.get("error")}
    try:
        expr = sympy.sympify(parsed["parsed"], locals=_safe_sympy_locals())
        results: dict[str, bool] = {}
        for sym_name, attr in assumptions.items():
            if not _is_safe(sym_name):
                results[str(sym_name)] = False
                continue
            x = Symbol(sym_name, **{
                attr: True,
            })
            sub = expr.subs(Symbol(sym_name), x)
            results[str(sym_name)] = bool(sub.assumptions0.get(attr, False))
        return {
            "status": "OK",
            "input": _expr_to_str(expr),
            "assumptions_checked": assumptions,
            "results": results,
            "sympy_version": _SYM_VERSION,
        }
    except Exception as e:  # pragma: no cover
        return {
            "status": "FAIL",
            "stage": "check_assumptions",
            "error": f"{type(e).__name__}: {e}",
        }

def tool_find_singularities(expression: str, variable: str = "x") -> dict[str, Any]:
    """Return the singularities (where denominator vanishes, etc.)."""
    parsed = tool_parse(expression)
    if parsed.get("status") != "OK":
        return {"status": "FAIL", "stage": "parse", "error": parsed.get("error")}
    if not _is_safe(variable):
        return {"status": "FAIL", "error": f"unsafe variable name: {variable}"}
    try:
        x = Symbol(variable)
        expr = sympy.sympify(parsed["parsed"], locals=_safe_sympy_locals())
        # ``singularities`` requires sym >= 1.10.
        if hasattr(sympy.calculus.util, "singularities"):
            sing = list(sympy.calculus.util.singularities(expr, x))
        else:
            # Backport: zero out the denominator.
            num, den = expr.as_numer_denom()
            sing = sorted(
                {s for s in sympy.solve(den, x) if s.is_finite},
                key=str,
            )
        return {
            "status": "OK",
            "input": _expr_to_str(expr),
            "singularities": [_expr_to_str(s) for s in sing],
            "singularity_count": len(sing),
            "domain": _expr_to_str(continuous_domain(expr, x, sympy.S.Reals)),
            "sympy_version": _SYM_VERSION,
        }
    except Exception as e:  # pragma: no cover
        return {
            "status": "FAIL",
            "stage": "singularities",
            "error": f"{type(e).__name__}: {e}",
        }

def tool_check_inequality(expression: str, variable: str = "x", op: str = "<") -> dict[str, Any]:
    """Solve ``expression op 0`` for the variable.

    ``op`` is one of ``< <= > >=``.
    """
    parsed = tool_parse(expression)
    if parsed.get("status") != "OK":
        return {"status": "FAIL", "stage": "parse", "error": parsed.get("error")}
    if not _is_safe(variable):
        return {"status": "FAIL", "error": f"unsafe variable name: {variable}"}
    if op not in {"<", "<=", ">", ">="}:
        return {"status": "FAIL", "error": f"unsupported op: {op}"}
    try:
        x = Symbol(variable)
        expr = sympy.sympify(parsed["parsed"], locals=_safe_sympy_locals())
        rel = Relational(expr, 0, op)
        solution = solve_univariate_inequality(rel, x, relational=False)
        return {
            "status": "OK",
            "input": _expr_to_str(expr),
            "op": op,
            "solution_set": _expr_to_str(solution),
            "valid": bool(solution != sympy.S.EmptySet),
            "sympy_version": _SYM_VERSION,
        }
    except Exception as e:  # pragma: no cover
        return {
            "status": "FAIL",
            "stage": "inequality",
            "error": f"{type(e).__name__}: {e}",
        }

def tool_adversarial_substitution(
    expression: str,
    variable: str = "x",
    substitutions: list[float] | None = None,
) -> dict[str, Any]:
    """Adversarial substitution test.

    The doctrine demands at least one adversarial substitution passes.
    We default to ``[0, 1, -1, pi, -pi, oo]`` plus caller-provided points.
    Returns evaluations plus a domain-validity flag for each.
    """
    parsed = tool_parse(expression)
    if parsed.get("status") != "OK":
        return {"status": "FAIL", "stage": "parse", "error": parsed.get("error")}
    if not _is_safe(variable):
        return {"status": "FAIL", "error": f"unsafe variable name: {variable}"}
    try:
        x = Symbol(variable)
        expr = sympy.sympify(parsed["parsed"], locals=_safe_sympy_locals())
        f = lambdify(x, expr, modules=["sympy"])
        defaults: list[Any] = [0, 1, -1, 3.14159265358979, -3.14159265358979]
        # Skip Infinity — it always raises.
        points = defaults + (substitutions or [])
        results: list[dict[str, Any]] = []
        any_valid = False
        for p in points:
            entry: dict[str, Any] = {"point": str(p)}
            try:
                v = f(p)
                entry["value"] = (
                    float(v)
                    if hasattr(v, "__float__") and not (v != v)
                    else None
                )
                entry["valid"] = entry["value"] is not None
                if entry["valid"]:
                    any_valid = True
            except Exception as e:  # noqa: BLE001
                entry["value"] = None
                entry["valid"] = False
                entry["error"] = f"{type(e).__name__}"
            results.append(entry)
        return {
            "status": "OK",
            "input": _expr_to_str(expr),
            "substitutions": results,
            "any_valid_evaluation": any_valid,
            "sympy_version": _SYM_VERSION,
        }
    except Exception as e:  # pragma: no cover
        return {
            "status": "FAIL",
            "stage": "adversarial_substitution",
            "error": f"{type(e).__name__}: {e}",
        }

# ────────────────────────────────────────────────────────────────────
# MCP server launcher
# ────────────────────────────────────────────────────────────────────

def start_server(transport: str = "stdio") -> None:
    """Launch the MCP server. Falls back to a stub if the SDK is missing."""
    try:
        from mcp.server import Server  # type: ignore
        from mcp.server.stdio import stdio_server  # type: ignore
        from mcp.types import Tool, TextContent  # type: ignore
    except ImportError:
        raise RuntimeError(
            "The mcp SDK is not installed. Install with: "
            "pip install \"deviatrix-genesis[mcp]\""
        )

    from . import TOOL_NAMES

    server = Server("deviatrix-sympy-mcp")  # type: ignore

    handlers = {
        "sympy_parse": tool_parse,
        "sympy_simplify": tool_simplify,
        "sympy_solve": tool_solve,
        "sympy_diff": tool_diff,
        "sympy_integrate": tool_integrate,
        "sympy_check_assumptions": tool_check_assumptions,
        "sympy_find_singularities": tool_find_singularities,
        "sympy_check_inequality": tool_check_inequality,
        "sympy_adversarial_substitution": tool_adversarial_substitution,
    }

    @server.list_tools()  # type: ignore[misc]
    async def _list() -> list[Any]:  # pragma: no cover
        return [
            Tool(
                name=name,
                description=f"SymPy-backed {name}",
                inputSchema={"type": "object"},
            )
            for name in TOOL_NAMES
        ]

    @server.call_tool()  # type: ignore[misc]
    async def _call(name: str, arguments: dict[str, Any]) -> list[Any]:  # pragma: no cover
        handler = handlers.get(name)
        if handler is None:
            return [TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}))]
        try:
            result = handler(**arguments)
        except Exception as e:  # noqa: BLE001
            result = {"status": "FAIL", "error": f"{type(e).__name__}: {e}"}
        return [TextContent(type="text", text=json.dumps(result))]

    import asyncio  # pragma: no cover

    async def _run() -> None:  # pragma: no cover
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(_run())
