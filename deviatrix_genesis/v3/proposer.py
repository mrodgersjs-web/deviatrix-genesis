"""Formula proposer — convert a brief into MathClaim candidates.

The user passes a 1-paragraph GTM brief. The proposer emits 9
candidate ideas, each as a tuple of:

  * (name, formula, falsifier, anti_orthodoxy, mechanism_originality,
     prior_art_distance, owner_dept, action_90d)

The 9 candidates are *deterministic templates* that the brief
injects into. This replaces the v2 hand-tuned scalar inputs with a
*brief-driven* generator. The output is identical in shape to the
v2 ``IDEAS_V2`` so the conductor can consume it without changes.

Templates
=========

The 9 templates cover the 5 mechanism families the v2 run surfaced:

  1. Independent verification (Outcome-Escrow, Anti-Adversarial)
  2. Financial primitive (Doctrine-Bond, Smart-Contract)
  3. Portable reputation (Reputation-Primitive, Negative-Pick)
  4. Inverted-market (Reverse-Auction, Operator-as-Public-Good)
  5. Yield-curve (Doctrine-Bond again)

Each template accepts a brief keyword set and emits a name +
formula + falsifier. The newness scores are *learned* from the
real corpus via the corpus_loader.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .corpus_loader import load_corpus, score_corpus_entry

__all__ = ["GTMIdea", "propose_from_brief", "render_idea"]


@dataclass
class GTMIdea:
    name: str
    formula: str
    falsifier: str
    closest_known_archetype: str | None
    anti_orthodoxy_new: float = 0.0
    mechanism_originality_new: float = 0.0
    prior_art_distance_new: float = 0.0
    owner_dept: str = ""
    action_90d: str = ""
    mechanism_family: str = ""
    brief_keywords: list[str] = field(default_factory=list)


# ────────────────────────────────────────────────────────────────────
# The 9 templates
# ────────────────────────────────────────────────────────────────────


TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "Outcome-Escrow — customer pays only when the operator's claim is independently verified",
        "formula": "verifiable_outcome(x) * escrow_release(x) * anti_bait_and_switch(x)",
        "falsifier": "Any comparable outcome-escrow marketplace launches within 90 days OR < 5 customer-paid escrows OR < 1 independent-verification partner agrees to the protocol.",
        "owner_dept": "gtm",
        "mechanism_family": "independent_verification",
        "action_90d": "Design the outcome-escrow protocol (state-machine + verifier network), publish the spec, recruit 2 independent-verification partners (one auditor, one law firm), and on-board 3 customers willing to escrow $10K+ each.",
        "keywords": ["escrow", "outcome", "verifier", "verify", "claim", "payment-on-delivery"],
    },
    {
        "name": "Operator-as-Public-Good — free operators paid by visible-attribution in the output",
        "formula": "public_attribution(x) * downstream_revenue_share(x) * visibility_premium(x)",
        "falsifier": "Operators refuse the visibility-premium OR < $50K downstream revenue is generated in 90 days OR no measurable attribution delta between tagged and untagged outputs.",
        "owner_dept": "content",
        "mechanism_family": "inverted_market",
        "action_90d": "Design the attribution protocol (signed receipts + downstream conversion telemetry), publish the spec, instrument 3 public operators to test the visibility-premium, run a 90-day attribution measurement.",
        "keywords": ["attribution", "public-good", "free", "downstream", "revenue-share"],
    },
    {
        "name": "Anti-Adversarial Distribution — paid leads whose quality is provably not the seller's incentive",
        "formula": "adversarial_quality_proof(x) * negative_selection_resistance(x) * lead_lifetime_value(x)",
        "falsifier": "Lead quality regresses to the prior mean within 90 days OR the verification mechanism is reverse-engineered OR < 100 qualified leads delivered.",
        "owner_dept": "sales",
        "mechanism_family": "independent_verification",
        "action_90d": "Design the adversarial-quality protocol (third-party audit of the lead-source method), publish the spec, recruit 2 buyers willing to pay per-verified-lead (not per-lead), run a 90-day cohort.",
        "keywords": ["lead", "adversarial", "quality", "verified", "distribution"],
    },
    {
        "name": "Reverse-Auction Doctrine — customers post a problem; operators underbid each other on the right to fix it",
        "formula": "auction_revenue(x) * problem_clarity(x) * winner_take_all_proof(x)",
        "falsifier": "Operators refuse to underbid OR < 50 problems posted OR < 10 paid resolutions OR the underbid price floor collapses.",
        "owner_dept": "gtm",
        "mechanism_family": "inverted_market",
        "action_90d": "Design the reverse-auction protocol (problem-post + underbid window + escrow release), publish the spec, seed 10 problem posts from friendly customers, run a 90-day auction.",
        "keywords": ["auction", "underbid", "problem-post", "reverse", "marketplace"],
    },
    {
        "name": "Doctrine-Indexed Bond — investors fund operators against a verifiable doctrine-yield curve",
        "formula": "doctrine_yield(x) * default_recovery(x) * covenant_enforcement(x)",
        "falsifier": "No investor willing to fund under the doctrine-yield curve OR the yield curve is falsified by an operator OR < $100K deployed.",
        "owner_dept": "finance",
        "mechanism_family": "yield_curve",
        "action_90d": "Design the doctrine-yield curve (operator-output × verification-rate × duration), publish the spec, recruit 1 friendly investor, file the regulatory posture (likely Reg D / S or non-security per Howey), deploy $50K-$250K as the first cohort.",
        "keywords": ["bond", "yield", "investor", "doctrine", "curve", "finance"],
    },
    {
        "name": "Operator-Reputation Primitive — a portable, signed-receipt reputation object that follows the operator across products",
        "formula": "portable_reputation(x) * signed_receipt_chain(x) * cross_platform_inheritance(x)",
        "falsifier": "Operators refuse the primitive OR < 100 operators sign up OR no platform adopts the receipt format within 90 days.",
        "owner_dept": "strategy",
        "mechanism_family": "portable_reputation",
        "action_90d": "Design the reputation object schema (JSON-LD or signed CBOR), publish the spec, recruit 3 platforms willing to honour the receipt, run a 90-day pilot with 50 operators.",
        "keywords": ["reputation", "portable", "signed", "receipt", "cross-platform"],
    },
    {
        "name": "Negative-Pick Distribution — pay operators to *not* recommend competitors, with the option to disclose the payment",
        "formula": "negative_pick_payment(x) * optional_disclosure(x) * competitor_research_artefact(x)",
        "falsifier": "Operators refuse the disclosure option OR no customer activates a negative-pick OR the disclosure itself damages trust.",
        "owner_dept": "strategy",
        "mechanism_family": "portable_reputation",
        "action_90d": "Design the negative-pick contract (payment-for-non-recommendation + optional disclosure), publish the spec, recruit 3 operators willing to test, run a 90-day pilot with 10 customers.",
        "keywords": ["negative-pick", "non-recommend", "disclosure", "competitor"],
    },
    {
        "name": "Doctrine-as-Smart-Contract — RIG publishes the doctrine as executable code that pays operators when they meet it",
        "formula": "executable_doctrine(x) * automatic_payment(x) * verifiability_guarantee(x)",
        "falsifier": "No operator accepts the executable doctrine OR < 5 operators auto-paid OR the verification guarantee is reverse-engineered.",
        "owner_dept": "engineering",
        "mechanism_family": "financial_primitive",
        "action_90d": "Write the doctrine as a smart contract (Solidity or equivalent), publish the code + verification guarantees, deploy on testnet, audit the contract, recruit 5 operators to test auto-payment.",
        "keywords": ["smart-contract", "executable", "code", "doctrine", "auto-pay"],
    },
    {
        "name": "Counterfactual Receipt — customers pay for the *saved* outcome, not the delivered one, with the counterfactual independently reconstructed",
        "formula": "counterfactual_baseline(x) * saved_outcome_delta(x) * independent_reconstruction(x)",
        "falsifier": "No independent re-constructor agrees to the protocol OR < $50K saved-outcome payments in 90 days OR the baseline is challenged.",
        "owner_dept": "strategy",
        "mechanism_family": "independent_verification",
        "action_90d": "Design the counterfactual-receipt protocol (independent baseline reconstruction + delta measurement + payment-on-delta), publish the spec, recruit 2 re-constructor partners, run a 90-day pilot.",
        "keywords": ["counterfactual", "baseline", "saved", "delta", "reconstruct"],
    },
]


# ────────────────────────────────────────────────────────────────────
# Brief ingestion
# ────────────────────────────────────────────────────────────────────


def _extract_brief_keywords(brief: str) -> set[str]:
    """Tokenize a brief and return salient keywords."""
    return {t.lower() for t in re.findall(r"\b\w+\b", brief) if len(t) > 3}


def _match_score(idea_keywords: list[str], brief_keywords: set[str]) -> float:
    """Return a 0-1 score for how well an idea's keywords match the brief."""
    if not idea_keywords:
        return 0.5  # neutral
    matches = sum(1 for kw in idea_keywords if kw.lower() in brief_keywords)
    return matches / len(idea_keywords)


# ────────────────────────────────────────────────────────────────────
# Proposer
# ────────────────────────────────────────────────────────────────────


def propose_from_brief(
    brief: str,
    *,
    corpus: list | None = None,
    include_extra: list | None = None,
    n: int = 9,
) -> list[GTMIdea]:
    """Convert a brief into ``n`` GTMIdea candidates.

    The 9 templates are *ranked* by how well their keywords match
    the brief. The top ``n`` are returned, with newness scores
    *learned from the corpus* (not hard-coded).

    If ``include_extra`` is supplied (e.g. from an LLM), those ideas
    are appended after the templates.
    """
    if corpus is None:
        corpus = load_corpus()
    brief_keywords = _extract_brief_keywords(brief)

    # Score templates against brief
    ranked: list[tuple[float, dict[str, Any]]] = []
    for tmpl in TEMPLATES:
        score = _match_score(tmpl["keywords"], brief_keywords)
        ranked.append((score, tmpl))
    ranked.sort(key=lambda pair: -pair[0])

    # Compute corpus-derived newness for each template's mechanism family
    # by sampling a few entries from the corpus and averaging.
    family_newness: dict[str, dict[str, float]] = {}
    if corpus:
        # Pick the top-3 highest-newness entries per family keyword
        for fam_keyword in {t["mechanism_family"] for t in TEMPLATES}:
            matching = [
                e for e in corpus
                if any(re.search(rf"\b{kw}\b", e.text.lower())
                       for kw in TEMPLATES_BY_FAMILY[fam_keyword]["search_terms"])
            ]
            if not matching:
                matching = corpus[:3]
            scores = [score_corpus_entry(e, corpus) for e in matching[:5]]
            if scores:
                family_newness[fam_keyword] = {
                    "anti_orthodoxy": max(s["anti_orthodoxy"] for s in scores),
                    "mechanism_originality": max(s["mechanism_originality"] for s in scores),
                    "prior_art_distance": max(s["prior_art_distance"] for s in scores),
                }

    # Fall-back defaults (the v2 hand-tuned values, calibrated)
    DEFAULTS = {
        "anti_orthodoxy": 4.5,
        "mechanism_originality": 4.5,
        "prior_art_distance": 4.5,
    }

    out: list[GTMIdea] = []
    for score, tmpl in ranked[:n]:
        fams = family_newness.get(tmpl["mechanism_family"], DEFAULTS)
        # The corpus-derived scores are 0-1; scale to the v2 range
        # (which is roughly 0-5; we use 4-5 for novel, 1-2 for known).
        newness = {
            "anti_orthodoxy_new": 1.5 + fams.get("anti_orthodoxy", 0.5) * 4.0,
            "mechanism_originality_new": 1.5 + fams.get("mechanism_originality", 0.5) * 4.0,
            "prior_art_distance_new": 1.5 + fams.get("prior_art_distance", 0.5) * 4.0,
        }
        out.append(
            GTMIdea(
                name=tmpl["name"],
                formula=tmpl["formula"],
                falsifier=tmpl["falsifier"],
                closest_known_archetype=None,
                owner_dept=tmpl["owner_dept"],
                action_90d=tmpl["action_90d"],
                mechanism_family=tmpl["mechanism_family"],
                brief_keywords=tmpl["keywords"],
                **newness,
            )
        )

    if include_extra:
        for extra in include_extra:
            if isinstance(extra, GTMIdea):
                out.append(extra)
            elif isinstance(extra, dict):
                out.append(GTMIdea(**extra))

    return out


# ────────────────────────────────────────────────────────────────────
# Family → search-term mapping
# ────────────────────────────────────────────────────────────────────


TEMPLATES_BY_FAMILY: dict[str, dict[str, Any]] = {
    "independent_verification": {
        "search_terms": [
            r"\bescrow\b", r"\bverifier?\b", r"\bverification\b",
            r"\boutcome\b", r"\badversarial\b", r"\bbaseline\b",
            r"\breconstruct(?:ion)?\b", r"\bproof\b",
        ],
    },
    "financial_primitive": {
        "search_terms": [
            r"\bbond\b", r"\byield\b", r"\bsmart[- ]?contract\b",
            r"\binvestor\b", r"\bdoctrine\b", r"\bexecutable\b",
        ],
    },
    "portable_reputation": {
        "search_terms": [
            r"\breputation\b", r"\bportable\b", r"\bsigned\b",
            r"\breceipt\b", r"\bdisclosure\b", r"\bcompetitor\b",
        ],
    },
    "inverted_market": {
        "search_terms": [
            r"\bauction\b", r"\bunderbid\b", r"\battribution\b",
            r"\bpublic[- ]?good\b", r"\bdownstream\b", r"\bvisibility\b",
        ],
    },
    "yield_curve": {
        "search_terms": [
            r"\byield\b", r"\bcurve\b", r"\bcovenant\b",
            r"\bdefault\b", r"\brecovery\b", r"\bdoctrine\b",
        ],
    },
}


def render_idea(idea: GTMIdea) -> str:
    return (
        f"[{idea.mechanism_family}] {idea.name}\n"
        f"  formula    : {idea.formula}\n"
        f"  dept       : {idea.owner_dept}\n"
        f"  newness    : ao={idea.anti_orthodoxy_new:.2f} "
        f"mo={idea.mechanism_originality_new:.2f} pa={idea.prior_art_distance_new:.2f}\n"
        f"  falsifier  : {idea.falsifier}\n"
        f"  90-day     : {idea.action_90d}\n"
    )
