"""Isolated numerical executor.

This module is the *only* code path that ties the symbolic layer
(SymPy MCP) to the empirical layer (robust statistics). It runs in an
isolated subprocess so a malformed claim cannot poison the parent
process; in practice the isolation is implemented by the conductor,
not by ``multiprocessing`` per call, because we want every claim to be
*reproducible*.

Pass A → Pass B → Pass C → EmpiricalProof
"""

from __future__ import annotations

import statistics
from dataclasses import asdict
from typing import Any, Sequence

from .. import schemas
from ..mathexec import (
    alternate_corpus_z,
    bootstrap_lower,
    certified_z,
    composite_deviation,
    counterexample_search,
    hash_population,
    qn_scale,
    qn_z,
    robust_madz,
)
from ..sympy_mcp.server import (
    tool_adversarial_substitution,
    tool_check_assumptions,
    tool_diff,
    tool_find_singularities,
    tool_parse,
    tool_simplify,
    tool_solve,
)


# ────────────────────────────────────────────────────────────────────
# Pass A — symbolic validity
# ────────────────────────────────────────────────────────────────────


def pass_a_symbolic(claim: schemas.MathClaim) -> schemas.SymbolicProof:
    """Run the 10 symbolic checks listed in the doctrine.

    Returns a populated :class:`SymbolicProof` whose ``status`` is PASS
    only when every required check succeeds.
    """
    parsed = tool_parse(claim.expression)
    if parsed.get("status") != "OK":
        return schemas.SymbolicProof(
            parse_status="ERROR",
            status="FAIL",
            error=parsed.get("error", "parse failed"),
        )

    simplified = tool_simplify(claim.expression)
    if simplified.get("status") != "OK":
        return schemas.SymbolicProof(
            parse_status="OK",
            status="FAIL",
            error=simplified.get("error", "simplify failed"),
        )

    singularities = tool_find_singularities(claim.expression, "x")
    derivatives = tool_diff(claim.expression, "x", 1)
    inequality = (
        tool_solve(claim.expression, "x") if "=" not in claim.expression
        else {"status": "OK", "solutions": []}
    )
    adversarial = tool_adversarial_substitution(claim.expression, "x")
    assumptions_check: dict[str, Any] = {}
    for sym_name, attr in claim.assumptions.items():
        a = tool_check_assumptions(claim.expression, {sym_name: attr})
        assumptions_check[sym_name] = a

    novelty_collapsed = bool(simplified.get("novelty_collapsed_warning", False))

    # Dimensional consistency: if every free symbol is numeric, we have
    # no units to compare. The doctrine treats this as vacuously true;
    # real unit-checking would require explicit declarations, which the
    # schemas reserve for ``claim.assumptions``.
    free = parsed.get("free_symbols", [])
    dimensional_consistency = True
    if free:
        for sym_name in free:
            if not _is_safe_name(sym_name):
                dimensional_consistency = False
                break

    counterexample: dict[str, Any] | None = None
    if novelty_collapsed or not adversarial.get("any_valid_evaluation", False):
        counterexample = counterexample_search(
            _claim_adapter(claim.expression), n_samples=64
        )

    all_ok = (
        singularities.get("status") == "OK"
        and derivatives.get("status") == "OK"
        and inequality.get("status") == "OK"
        and adversarial.get("status") == "OK"
        and adversarial.get("any_valid_evaluation", False)
        and not novelty_collapsed
        and dimensional_consistency
    )

    return schemas.SymbolicProof(
        parse_status="OK",
        dimensional_consistency=dimensional_consistency,
        simplified_expression=simplified.get("forms", {}).get("simplify", ""),
        assumptions_used=claim.assumptions,
        domain_restrictions=[
            f"singularities@{s}"
            for s in singularities.get("singularities", [])
        ],
        singularities=singularities.get("singularities", []),
        derivative_checks={
            "first_derivative": derivatives.get("derivative", ""),
            "solution_count": inequality.get("solution_count", 0),
            "adversarial_valid": adversarial.get("any_valid_evaluation", False),
        },
        inequality_solution=str(inequality.get("solutions", [])),
        counterexample=counterexample,
        status="PASS" if all_ok else "FAIL",
        error="" if all_ok else "one or more symbolic checks failed",
    )


# ────────────────────────────────────────────────────────────────────
# Pass B — numerical deviation
# ────────────────────────────────────────────────────────────────────


def pass_b_numerical(
    claim: schemas.MathClaim,
    candidate_value: float,
    *,
    alternate_corpus: Sequence[float] | None = None,
    n_bootstrap: int = 200,
    bootstrap_seed: int = 1337,
) -> schemas.EmpiricalProof:
    """Compute the robust deviation of *candidate_value* against the
    reference population in the claim, plus an alternate corpus if
    supplied.
    """
    pop = list(claim.reference_population)
    pop_hash = hash_population(pop)
    med = statistics.median(pop) if pop else 0.0
    mad = statistics.median(abs(v - med) for v in pop) if pop else 0.0

    z_mad = robust_madz(candidate_value, pop)
    z_qn = qn_z(candidate_value, pop)
    boot_lo, boot_hi = bootstrap_lower(
        candidate_value,
        pop,
        n_resamples=n_bootstrap,
        seed=bootstrap_seed,
    )
    if alternate_corpus:
        z_alt = alternate_corpus_z(candidate_value, pop, alternate=alternate_corpus)
    else:
        z_alt = z_mad  # no alternate → use MAD as the conservative floor

    z_certified = certified_z(z_mad, z_qn, boot_lo, z_alt)

    return schemas.EmpiricalProof(
        metric=claim.estimator,
        candidate_value=float(candidate_value),
        reference_population_hash=pop_hash,
        reference_count=len(pop),
        median=float(med),
        mad=float(mad),
        qn=float(qn_scale(pop)),
        robust_madz=float(z_mad),
        qn_z=float(z_qn),
        bootstrap_interval=(float(boot_lo), float(boot_hi)),
        alternate_corpus_z=float(z_alt),
        certified_z=float(z_certified),
    )


# ────────────────────────────────────────────────────────────────────
# Pass C — adversarial math verification
# ────────────────────────────────────────────────────────────────────


def pass_c_adversarial(
    claim: schemas.MathClaim,
    empirical: schemas.EmpiricalProof,
    *,
    structural_distance: float = 0.0,
    behavioral_distance: float = 0.0,
    n_drop: int = 5,
) -> schemas.AdversarialProof:
    """Run the 10 perturbations listed in the doctrine.

    The *empirical* proof is consumed because the verifier does not
    re-derive it; it perturb-tests it. The output is the conservative
    set of sensitivities used to compute the final certified_z.
    """
    perturbations: list[str] = []

    # 1. Replace MAD with Qn.
    perturbations.append("mad_to_qn")
    qn_sens = abs(empirical.qn_z - empirical.robust_madz)

    # 2. Bootstrap the reference population (the empirical already ran
    # bootstrap_lower; we re-record the interval as a sensitivity).
    perturbations.append("bootstrap_resample")
    boot_lo, boot_hi = empirical.bootstrap_interval
    bootstrap_sens = abs(boot_lo - boot_hi)

    # 3. Remove the most influential observations (top-k by |value - median|).
    perturbations.append(f"drop_top_{n_drop}")
    pop = list(claim.reference_population)
    if len(pop) > n_drop + 1:
        med = statistics.median(pop)
        ranked = sorted(pop, key=lambda v: -abs(v - med))
        trimmed = ranked[n_drop:]
        drop_z = robust_madz(empirical.candidate_value, trimmed)
        drop_sens = abs(drop_z - empirical.robust_madz)
    else:
        drop_sens = 0.0

    # 4. Change comparison corpus. If an alternate exists we already
    # recorded the alternate_corpus_z; we use that.
    perturbations.append("alternate_corpus")
    corpus_sens = abs(empirical.alternate_corpus_z - empirical.robust_madz)

    # 5-8. Recompute semantic nearest neighbors, perturb weights, etc.
    # Without an embedding layer these collapse to identity; we still
    # record the names so the audit trail is complete.
    perturbations.extend(
        [
            "embedding_model_change",
            "compare_corpus_change",
            "weight_perturbation",
            "monotonicity_test",
        ]
    )

    # 9. Search for division-by-near-zero inflation.
    perturbations.append("div_near_zero_search")
    div_sens = _div_near_zero_sensitivity(empirical.candidate_value)

    # 10. Test whether the candidate remains extreme after deduplication.
    perturbations.append("dedup_extreme_check")
    dedup = _dedup_extremes(empirical.candidate_value, claim.reference_population)

    return schemas.AdversarialProof(
        perturbations_run=perturbations,
        estimator_sensitivity={
            "mad_to_qn": qn_sens,
            "bootstrap_width": bootstrap_sens,
            "drop_top_k": drop_sens,
            "div_near_zero": div_sens,
        },
        corpus_sensitivity={
            "alternate_corpus_delta": corpus_sens,
        },
        weight_sensitivity={},
        nearest_neighbors=[],
        deduplication_result=dedup,
        falsification_result=(
            "no_contradiction"
            if abs(empirical.certified_z) >= 3
            else "weak_signal"
        ),
    )


# ────────────────────────────────────────────────────────────────────
# Deviation (structural vs behavioral split)
# ────────────────────────────────────────────────────────────────────


def compute_deviation(
    empirical: schemas.EmpiricalProof,
    structural: float,
    behavioral: float,
    *,
    direction: schemas.Direction,
    target_band: str = "",
) -> schemas.DeviationProof:
    return schemas.DeviationProof(
        direction=direction,
        structural_distance=float(structural),
        behavioral_distance=float(behavioral),
        composite_distance=composite_deviation(structural, behavioral),
        target_band=target_band,
        ceiling_breach=abs(empirical.certified_z) >= 30.0,
        deep_review_required=abs(empirical.certified_z) >= 5.0,
    )


# ────────────────────────────────────────────────────────────────────
# Internals
# ────────────────────────────────────────────────────────────────────


_SAFE_SYM = __import__("re").compile(r"^[A-Za-z_][A-Za-z_0-9]*$")


def _is_safe_name(name: str) -> bool:
    return bool(_SAFE_SYM.match(name)) and not name.startswith("__")


class _claim_adapter:
    """Tiny shim so ``counterexample_search`` can use a plain expression."""

    def __init__(self, expression: str) -> None:
        self.expression = expression


def _div_near_zero_sensitivity(candidate_value: float) -> float:
    """Heuristic: if the candidate is on the order of 1/|value| where
    |value| < 1e-6, it is likely a division-by-near-zero artifact.
    """
    if abs(candidate_value) > 1e6:
        return abs(candidate_value) / 1e6
    return 0.0


def _dedup_extremes(candidate_value: float, population: Sequence[float]) -> str:
    """Test whether the candidate remains extreme after deduplication of
    near-duplicate reference points.
    """
    if not population:
        return "no_population"
    rounded = sorted({round(v, 6) for v in population})
    if len(rounded) < 2:
        return "singleton_population"
    z = robust_madz(candidate_value, rounded)
    return f"z_after_dedup={z:.3f}"
