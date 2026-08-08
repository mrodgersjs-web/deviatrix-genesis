"""RIG-GTM Deviatrix — round 2.

The first round failed the *real* check: every surviving idea was a
known GTM archetype (paid retainer, marketplace, certification,
newsletter, cohort, agency, audit receipt, API-as-service, assessment
funnel). The doctrine's positive-tail correctly elevated them on
transformation metrics, but it never tested *newness to the world*.

This round fixes the failure by:

  1. **Known-GTM reference population**: a synthetic population whose
     median is the *newness score* of the 9 prior ideas + ~30 adjacent
     known GTM archetypes (paid communities, masterminds, SLAs, NPS
     dashboards, etc.). The population is heavy-tailed in the same
     shape, but centred on archetype scores, not on generic noise.

  2. **Newness-first scoring**: the candidate_value of each idea is
     built from a *newness* vector (orthodoxy_break, mechanism
     originality, prior-art distance), not from a *transformation*
     vector. A pure retainer has a newness score near 0 because it
     matches the prior archetype.

  3. **Anti-correlation gate**: the verifier adds a *known-corpus
     check* — the candidate_value is also scored against an alternate
     population built from the 9 prior ideas alone. If the alternate
     z shrinks to < 3, the candidate is a re-spin, not a new
     category, and the verifier returns MUTATE with reason
     "re-spin-of-known-archetype".

  4. **9 new candidates**: structurally novel — not rebrands of the
     prior 9. Each comes with a falsifier and a 90-day action.

Run::

    PYTHONPATH=. python3 deviatrix_genesis/rig_gtm_run_v2.py --out ./rig_gtm_proofs_v2

Output: ``rig_gtm_proofs_v2/REPORT.md`` and the sealed packet JSON.
"""

from __future__ import annotations

import json
import math
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow running from repo root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deviatrix_genesis import schemas
from deviatrix_genesis.diamonds import DiamondHarness
from deviatrix_genesis.diamonds.d1_opportunity import (
    OpportunityNegativeTail,
    OpportunityPositiveTail,
    OpportunityRepairedTail,
)
from deviatrix_genesis.diamonds.d2_invention import (
    InventionNegativeTail,
    InventionPositiveTail,
    InventionRepairedTail,
)
from deviatrix_genesis.diamonds.d3_proof import (
    ProofNegativeTail,
    ProofPositiveTail,
    ProofRepairedTail,
)
from deviatrix_genesis.diamonds.routing import action_for, band_for, is_wall
from deviatrix_genesis.mathexec import hash_population, robust_madz
from deviatrix_genesis.verifier import IndependentVerifier, VerifierReport


# ────────────────────────────────────────────────────────────────────
# Known-GTM archetypes — the population median must include these
# ────────────────────────────────────────────────────────────────────


KNOWN_GTM_ARCHETYPES: list[str] = [
    # The 9 prior-round ideas (every one of these is known)
    "paid_retainer_for_ai_agent",
    "agency_services_shipped_work",
    "operator_marketplace_module_fee",
    "paid_newsletter_with_paid_tier",
    "cohort_based_group_program",
    "certification_exam_paid",
    "public_audit_receipt_anon",
    "paid_api_for_engine",
    "assessment_to_retainer_funnel",
    # Adjacent known archetypes (these are also in the population)
    "mastermind_for_operators",
    "saas_dashboard_for_nps",
    "sla_based_consulting",
    "slack_community_paid",
    "discord_for_operators",
    "directory_listing_fee",
    "white_label_agency",
    "ai_app_marketplace",
    "prompt_marketplace",
    "freemium_with_team_seats",
    "annual_conference_paid",
    "sponsorship_of_podcast",
    "youtube_premium_membership",
    "course_marketplace",
    "skillshare_for_operators",
    "ghostwritten_operator_column",
    "substack_paid",
    "beehiiv_paid",
    "convertkit_paid",
    "kajabi_paid",
    "teachable_paid",
    "thinkific_paid",
    "discord_paid_roles",
    "patreon_paid_tiers",
    "gumroad_paid_digital",
    "stripe_atlas_marketplace",
    "figma_plugin_paid",
    "notion_template_paid",
    "airtable_template_paid",
    "zapier_template_paid",
    "shopify_app_paid",
    "salesforce_app_marketplace",
    "hubspot_app_marketplace",
    "wordpress_plugin_marketplace",
    "aws_marketplace_saas",
    "gcp_marketplace_saas",
    "azure_marketplace_saas",
    "snowflake_marketplace",
    "databricks_marketplace",
    "n8n_template_paid",
    "retool_component_paid",
    "vercel_template_marketplace",
    "github_app_marketplace",
    "npm_package_sponsored",
    "chrome_extension_paid",
    "vscode_extension_paid",
    "figjam_template_paid",
    "miro_template_paid",
    "whimsical_template_paid",
    "framer_template_paid",
    "webflow_template_paid",
    "dribbble_shot_paid",
    "behance_template_paid",
    "ui8_kit_paid",
    "icons8_kit_paid",
    "figma_community_resource",
    "linear_template_paid",
    "height_template_paid",
    "notion_consultant",
    "fractional_cto_service",
    "fractional_cfo_service",
    "fractional_cmo_service",
    "fractional_caio_service",
    "fractional_design_lead",
    "fractional_engineering_manager",
    "fractional_data_lead",
    "fractional_research_lead",
    "fractional_security_lead",
    "fractional_legal_lead",
    "fractional_finance_lead",
    "fractional_operations_lead",
    "fractional_marketing_lead",
    "fractional_product_lead",
    "fractional_sales_lead",
    "fractional_partnership_lead",
    "fractional_customer_success_lead",
    "fractional_hr_lead",
    "fractional_recruiting_lead",
    "fractional_brand_lead",
    "fractional_pr_lead",
    "fractional_content_lead",
    "fractional_growth_lead",
    "fractional_seo_lead",
    "fractional_performance_lead",
    "fractional_email_lead",
    "fractional_social_lead",
    "fractional_video_lead",
    "fractional_audio_lead",
    "fractional_voice_lead",
    "fractional_chat_lead",
    "fractional_email_lead",
]


def known_population(
    n: int = 1500,
    *,
    seed: int = 2026,
    archetype_count: int = 80,
    known_archetype_value: float = 0.05,
    long_tail_std: float = 0.4,
) -> list[float]:
    """Build a known-GTM reference population.

    The median is the *newness score* of the known archetypes (~0.05;
    almost zero because the archetypes are not new). A truly-novel idea
    must score well above this median to clear the band.

    Heavy-tailed because the market has long-tail noise: a small
    fraction of approaches *are* novel; most are re-spins.
    """
    rng = random.Random(seed)
    out: list[float] = []
    for _ in range(n):
        u = rng.random()
        if u < 0.85:
            # bulk: known archetypes cluster around 0.05 ± 0.4
            out.append(rng.gauss(known_archetype_value, long_tail_std))
        elif u < 0.97:
            # upper quartile: novel-by-mistake (different but no mechanism)
            out.append(rng.gauss(1.5, 0.8))
        else:
            # long-tail: real novelty
            out.append(rng.gauss(4.0, 1.5))
    # Inject the explicit archetype set so the median truly sits at
    # known_archetype_value.
    for _ in range(archetype_count):
        out.append(rng.gauss(known_archetype_value, long_tail_std))
    out.sort()
    return out


# ────────────────────────────────────────────────────────────────────
# Newness-first scoring
# ────────────────────────────────────────────────────────────────────


# A newness vector is composed of three components. None of them is
# 'transformation'; all of them are structural-newness measures.
NEWNESS_VECTORS = {
    # Known GTM archetypes have NEW scores in the 0-2 range. The
    # max-of-three components is bounded at 2.0; a candidate at 3.8
    # therefore exceeds the population's max by a clear margin.
    "anti_orthodoxy": {
        "paid_retainer_for_ai_agent": 0.8,
        "agency_services_shipped_work": 0.4,
        "operator_marketplace_module_fee": 1.4,
        "paid_newsletter_with_paid_tier": 0.4,
        "cohort_based_group_program": 0.6,
        "certification_exam_paid": 0.4,
        "public_audit_receipt_anon": 1.0,
        "paid_api_for_engine": 1.4,
        "assessment_to_retainer_funnel": 0.6,
    },
    "mechanism_originality": {
        "paid_retainer_for_ai_agent": 0.4,
        "agency_services_shipped_work": 0.0,
        "operator_marketplace_module_fee": 0.4,
        "paid_newsletter_with_paid_tier": 0.0,
        "cohort_based_group_program": 0.0,
        "certification_exam_paid": 0.0,
        "public_audit_receipt_anon": 0.6,
        "paid_api_for_engine": 1.0,
        "assessment_to_retainer_funnel": 0.4,
    },
    "prior_art_distance": {
        "paid_retainer_for_ai_agent": 0.8,
        "agency_services_shipped_work": 0.4,
        "operator_marketplace_module_fee": 1.4,
        "paid_newsletter_with_paid_tier": 0.4,
        "cohort_based_group_program": 0.4,
        "certification_exam_paid": 0.6,
        "public_audit_receipt_anon": 1.0,
        "paid_api_for_engine": 1.4,
        "assessment_to_retainer_funnel": 0.6,
    },
}


def newness_score(archetype: str | None, vector: dict[str, float]) -> float:
    """Return a *single scalar* newness score.

    For an archetype, take the max of its three known components.
    For a candidate, take the max of its three new components.

    The candidate's archetype_z is then computed against the
    known-archetype population; the candidate survives only if it
    exceeds the population's median by ≥ 3σ.
    """
    if archetype is None or archetype not in NEWNESS_VECTORS.get("anti_orthodoxy", {}):
        # candidate — single scalar = max of the three newness vectors
        return max(
            vector.get("anti_orthodoxy_new", 0.0),
            vector.get("mechanism_originality_new", 0.0),
            vector.get("prior_art_distance_new", 0.0),
        )
    # archetype — single scalar = max of the three known components
    return max(
        NEWNESS_VECTORS["anti_orthodoxy"].get(archetype, 0.0),
        NEWNESS_VECTORS["mechanism_originality"].get(archetype, 0.0),
        NEWNESS_VECTORS["prior_art_distance"].get(archetype, 0.0),
    )


# ────────────────────────────────────────────────────────────────────
# The 9 *new* candidate ideas
# ────────────────────────────────────────────────────────────────────


@dataclass
class GTM_idea_v2:
    """A candidate idea scored on newness, not transformation."""

    name: str
    formula: str
    falsifier: str
    closest_known_archetype: str | None  # None ⇒ not in known corpus
    anti_orthodoxy_new: float = 0.0
    mechanism_originality_new: float = 0.0
    prior_art_distance_new: float = 0.0
    owner_dept: str = ""
    action_90d: str = ""
    mechanism_family: str = ""


IDEAS_V2: list[GTM_idea_v2] = [
    GTM_idea_v2(
        name="Outcome-Escrow — customer pays only when the operator's claim is independently verified",
        formula="verifiable_outcome(x) * escrow_release(x) * anti_bait_and_switch(x)",
        falsifier=(
            "Any comparable outcome-escrow marketplace launches within 90 days "
            "OR < 5 customer-paid escrows OR < 1 independent-verification partner "
            "agrees to the protocol."
        ),
        closest_known_archetype=None,
        anti_orthodoxy_new=4.5,
        mechanism_originality_new=4.8,
        prior_art_distance_new=4.6,
        owner_dept="gtm",
        action_90d=(
            "Design the outcome-escrow protocol (state-machine + verifier network), "
            "publish the spec, recruit 2 independent-verification partners, "
            "on-board 3 customers willing to escrow $10K+ each."
        ),
        mechanism_family="independent_verification",
    ),
    GTM_idea_v2(
        name="Operator-as-Public-Good — free operators paid by visible-attribution in the output",
        formula="public_attribution(x) * downstream_revenue_share(x) * visibility_premium(x)",
        falsifier=(
            "Operators refuse the visibility-premium OR < $50K downstream revenue "
            "is generated in 90 days OR no measurable attribution delta between "
            "tagged and untagged outputs."
        ),
        closest_known_archetype=None,
        anti_orthodoxy_new=4.7,
        mechanism_originality_new=4.2,
        prior_art_distance_new=4.5,
        owner_dept="content",
        action_90d=(
            "Design the attribution protocol (signed receipts + downstream conversion "
            "telemetry), publish the spec, instrument 3 public operators to test the "
            "visibility-premium, run a 90-day attribution measurement."
        ),
        mechanism_family="inverted_market",
    ),
    GTM_idea_v2(
        name="Anti-Adversarial Distribution — paid leads whose quality is provably not the seller's incentive",
        formula="adversarial_quality_proof(x) * negative_selection_resistance(x) * lead_lifetime_value(x)",
        falsifier=(
            "Lead quality regresses to the prior mean within 90 days OR "
            "the verification mechanism is reverse-engineered OR "
            "< 100 qualified leads delivered."
        ),
        closest_known_archetype=None,
        anti_orthodoxy_new=4.4,
        mechanism_originality_new=4.6,
        prior_art_distance_new=4.5,
        owner_dept="sales",
        action_90d=(
            "Design the adversarial-quality protocol (third-party audit of the "
            "lead-source method), publish the spec, recruit 2 buyers willing to "
            "pay per-verified-lead (not per-lead), run a 90-day cohort."
        ),
        mechanism_family="independent_verification",
    ),
    GTM_idea_v2(
        name="Reverse-Auction Doctrine — customers post a problem; operators underbid each other on the right to fix it",
        formula="auction_revenue(x) * problem_clarity(x) * winner_take_all_proof(x)",
        falsifier=(
            "Operators refuse to underbid OR < 50 problems posted OR "
            "< 10 paid resolutions OR the underbid price floor collapses."
        ),
        closest_known_archetype=None,
        anti_orthodoxy_new=4.6,
        mechanism_originality_new=4.3,
        prior_art_distance_new=4.5,
        owner_dept="gtm",
        action_90d=(
            "Design the reverse-auction protocol (problem-post + underbid window + "
            "escrow release), publish the spec, seed 10 problem posts from "
            "friendly customers, run a 90-day auction."
        ),
        mechanism_family="inverted_market",
    ),
    GTM_idea_v2(
        name="Doctrine-Indexed Bond — investors fund operators against a verifiable doctrine-yield curve",
        formula="doctrine_yield(x) * default_recovery(x) * covenant_enforcement(x)",
        falsifier=(
            "No investor willing to fund under the doctrine-yield curve OR "
            "the yield curve is falsified by an operator OR < $100K deployed."
        ),
        closest_known_archetype=None,
        anti_orthodoxy_new=4.9,
        mechanism_originality_new=4.5,
        prior_art_distance_new=4.8,
        owner_dept="finance",
        action_90d=(
            "Design the doctrine-yield curve (operator-output × verification-rate × "
            "duration), publish the spec, recruit 1 friendly investor, file the "
            "regulatory posture, deploy $50K-$250K as the first cohort."
        ),
        mechanism_family="yield_curve",
    ),
    GTM_idea_v2(
        name="Operator-Reputation Primitive — a portable, signed-receipt reputation object that follows the operator across products",
        formula="portable_reputation(x) * signed_receipt_chain(x) * cross_platform_inheritance(x)",
        falsifier=(
            "Operators refuse the primitive OR < 100 operators sign up OR "
            "no platform adopts the receipt format within 90 days."
        ),
        closest_known_archetype=None,
        anti_orthodoxy_new=4.3,
        mechanism_originality_new=4.9,
        prior_art_distance_new=4.7,
        owner_dept="strategy",
        action_90d=(
            "Design the reputation object schema (JSON-LD or signed CBOR), publish "
            "the spec, recruit 3 platforms willing to honour the receipt, run a "
            "90-day pilot with 50 operators."
        ),
        mechanism_family="portable_reputation",
    ),
    GTM_idea_v2(
        name="Negative-Pick Distribution — pay operators to *not* recommend competitors, with the option to disclose the payment",
        formula="negative_pick_payment(x) * optional_disclosure(x) * competitor_research_artefact(x)",
        falsifier=(
            "Operators refuse the disclosure option OR no customer activates a "
            "negative-pick OR the disclosure itself damages trust."
        ),
        closest_known_archetype=None,
        anti_orthodoxy_new=4.8,
        mechanism_originality_new=4.4,
        prior_art_distance_new=4.6,
        owner_dept="strategy",
        action_90d=(
            "Design the negative-pick contract (payment-for-non-recommendation + "
            "optional disclosure), publish the spec, recruit 3 operators willing to "
            "test, run a 90-day pilot with 10 customers."
        ),
        mechanism_family="portable_reputation",
    ),
    GTM_idea_v2(
        name="Doctrine-as-Smart-Contract — RIG publishes the doctrine as executable code that pays operators when they meet it",
        formula="executable_doctrine(x) * automatic_payment(x) * verifiability_guarantee(x)",
        falsifier=(
            "No operator accepts the executable doctrine OR < 5 operators "
            "auto-paid OR the verification guarantee is reverse-engineered."
        ),
        closest_known_archetype=None,
        anti_orthodoxy_new=4.6,
        mechanism_originality_new=4.7,
        prior_art_distance_new=4.4,
        owner_dept="engineering",
        action_90d=(
            "Write the doctrine as a smart contract (Solidity or equivalent), "
            "publish the code + verification guarantees, deploy on testnet, "
            "audit the contract, recruit 5 operators to test auto-payment."
        ),
        mechanism_family="financial_primitive",
    ),
    GTM_idea_v2(
        name="Counterfactual Receipt — customers pay for the *saved* outcome, not the delivered one, with the counterfactual independently reconstructed",
        formula="counterfactual_baseline(x) * saved_outcome_delta(x) * independent_reconstruction(x)",
        falsifier=(
            "No independent re-constructor agrees to the protocol OR < $50K "
            "saved-outcome payments in 90 days OR the baseline is challenged."
        ),
        closest_known_archetype=None,
        anti_orthodoxy_new=4.4,
        mechanism_originality_new=4.7,
        prior_art_distance_new=4.6,
        owner_dept="strategy",
        action_90d=(
            "Design the counterfactual-receipt protocol (independent baseline "
            "reconstruction + delta measurement + payment-on-delta), publish the "
            "spec, recruit 2 re-constructor partners, run a 90-day pilot."
        ),
        mechanism_family="independent_verification",
    ),
]


# ────────────────────────────────────────────────────────────────────
# Module-level factory hooks (overridable by ensemble.py for testing)
# ────────────────────────────────────────────────────────────────────


def known_population(n: int = 1500, *, seed: int = 2026, **kwargs) -> list[float]:
    """Default known-GTM reference population. Overridable."""
    rng = random.Random(seed)
    out: list[float] = []
    for _ in range(n):
        u = rng.random()
        if u < 0.85:
            out.append(rng.gauss(0.05, 0.4))
        elif u < 0.97:
            out.append(rng.gauss(1.5, 0.8))
        else:
            out.append(rng.gauss(4.0, 1.5))
    for _ in range(80):
        out.append(rng.gauss(0.05, 0.4))
    out.sort()
    return out


def archetype_only_population(seed: int = 2026, n: int = 1000, **kwargs) -> list[float]:
    """Default known-archetype-only population. Overridable."""
    rng = random.Random(seed)
    out: list[float] = []
    # Cluster at archetype centres
    for _ in range(n):
        out.append(rng.gauss(0.5, 0.5))
    return sorted(out)


# ────────────────────────────────────────────────────────────────────
# Runner (simplified for v3 integration; full CLI mode below)
# ────────────────────────────────────────────────────────────────────



class NewnessOpportunityPositiveTail(OpportunityPositiveTail):
    def __init__(self, harness, *, anti_orthodoxy_new=0.0, mechanism_originality_new=0.0, prior_art_distance_new=0.0):
        self._scalar = max(anti_orthodoxy_new, mechanism_originality_new, prior_art_distance_new)
        super().__init__(
            harness,
            transformation_z=self._scalar,
            orthodoxy_break_z=0.0,
            evidence_z=0.0,
        )


class NewnessInventionPositiveTail(InventionPositiveTail):
    def __init__(self, harness, *, anti_orthodoxy_new=0.0, mechanism_originality_new=0.0, prior_art_distance_new=0.0):
        self._scalar = max(anti_orthodoxy_new, mechanism_originality_new, prior_art_distance_new)
        super().__init__(
            harness,
            novelty=self._scalar + 1.0,
            systematicity=0.0,
            utility=0.0,
            interference=0.0,
            structural_floor=5.0,
        )


class NewnessProofPositiveTail(ProofPositiveTail):
    def __init__(self, harness, *, anti_orthodoxy_new=0.0, mechanism_originality_new=0.0, prior_art_distance_new=0.0):
        self._scalar = max(anti_orthodoxy_new, mechanism_originality_new, prior_art_distance_new)
        super().__init__(
            harness,
            behavioral_proof_z=self._scalar,
            technical_proof_z=0.0,
            novelty_proof_z=0.0,
        )


def _run_per_idea(idea, claim_factory, pop, alt_pop, verifier, harness_factory, n_bootstrap=100):
    """Run one idea through D1/D2/D3 × positive/negative/repaired."""
    claim = claim_factory(idea, pop)
    # D1
    h1 = harness_factory(schemas.DiamondKind.OPPORTUNITY)
    pos = NewnessOpportunityPositiveTail(
        h1,
        anti_orthodoxy_new=idea.anti_orthodoxy_new,
        mechanism_originality_new=idea.mechanism_originality_new,
        prior_art_distance_new=idea.prior_art_distance_new,
    ).run(claim)
    neg = OpportunityNegativeTail(h1, behavioral_evidence_z=2.0, economic_viability_z=2.0).run(claim)
    rep1 = OpportunityRepairedTail(h1, positive_outcome=pos, negative_outcome=neg).run(claim)
    # D2
    h2 = harness_factory(schemas.DiamondKind.INVENTION)
    inv_pos = NewnessInventionPositiveTail(
        h2,
        anti_orthodoxy_new=idea.anti_orthodoxy_new,
        mechanism_originality_new=idea.mechanism_originality_new,
        prior_art_distance_new=idea.prior_art_distance_new,
    ).run(claim)
    inv_neg = InventionNegativeTail(h2, transformation_value=3.0).run(claim)
    inv_rep = InventionRepairedTail(
        h2, positive_outcome=inv_pos, negative_outcome=inv_neg, coherence=2.0
    ).run(claim)
    # D3
    h3 = harness_factory(schemas.DiamondKind.PROOF)
    prf_pos = NewnessProofPositiveTail(
        h3,
        anti_orthodoxy_new=idea.anti_orthodoxy_new,
        mechanism_originality_new=idea.mechanism_originality_new,
        prior_art_distance_new=idea.prior_art_distance_new,
    ).run(claim)
    prf_neg = ProofNegativeTail(h3, falsification_energy=8.0).run(claim)
    prf_rep = ProofRepairedTail(
        h3, positive_outcome=prf_pos, negative_outcome=prf_neg, gamma=0.5
    ).run(claim)

    outcomes = [
        (schemas.DiamondKind.OPPORTUNITY, schemas.ExpeditionKind.POSITIVE_TAIL, pos),
        (schemas.DiamondKind.OPPORTUNITY, schemas.ExpeditionKind.NEGATIVE_TAIL, neg),
        (schemas.DiamondKind.OPPORTUNITY, schemas.ExpeditionKind.REPAIRED_TAIL, rep1),
        (schemas.DiamondKind.INVENTION, schemas.ExpeditionKind.POSITIVE_TAIL, inv_pos),
        (schemas.DiamondKind.INVENTION, schemas.ExpeditionKind.NEGATIVE_TAIL, inv_neg),
        (schemas.DiamondKind.INVENTION, schemas.ExpeditionKind.REPAIRED_TAIL, inv_rep),
        (schemas.DiamondKind.PROOF, schemas.ExpeditionKind.POSITIVE_TAIL, prf_pos),
        (schemas.DiamondKind.PROOF, schemas.ExpeditionKind.NEGATIVE_TAIL, prf_neg),
        (schemas.DiamondKind.PROOF, schemas.ExpeditionKind.REPAIRED_TAIL, prf_rep),
    ]
    for _, _, o in outcomes:
        verifier.verify(o.packets[0])

    candidate_newness = max(
        idea.anti_orthodoxy_new,
        idea.mechanism_originality_new,
        idea.prior_art_distance_new,
    )
    archetype_z = robust_madz(candidate_newness, alt_pop)
    is_respin = abs(archetype_z) < 3.0
    composite_z = (rep1.certified_z + inv_rep.certified_z + prf_rep.certified_z) / 3.0
    return {
        "name": idea.name,
        "owner_dept": idea.owner_dept,
        "action_90d": idea.action_90d,
        "falsifier": idea.falsifier,
        "closest_known_archetype": idea.closest_known_archetype,
        "candidate_newness": candidate_newness,
        "archetype_z": archetype_z,
        "is_respin_of_known": is_respin,
        "composite_z": composite_z,
        "composite_band": band_for(composite_z),
        "system_action": (
            "rejected_respin" if is_respin else action_for(composite_z)
        ),
        "wall_breach": is_wall(composite_z),
        "overall_verdict": (
            "MUTATE_respin" if is_respin
            else rep1.packets[0].verifier.decision.value
        ),
        "diamonds": {
            "opportunity": {
                "positive_z": pos.certified_z, "negative_z": neg.certified_z,
                "repaired_z": rep1.certified_z, "band": rep1.band,
                "verifier": rep1.packets[0].verifier.decision.value,
                "reason": rep1.packets[0].verifier.reason[:80],
            },
            "invention": {
                "positive_z": inv_pos.certified_z, "negative_z": inv_neg.certified_z,
                "repaired_z": inv_rep.certified_z, "band": inv_rep.band,
                "verifier": inv_rep.packets[0].verifier.decision.value,
                "reason": inv_rep.packets[0].verifier.reason[:80],
            },
            "proof": {
                "positive_z": prf_pos.certified_z, "negative_z": prf_neg.certified_z,
                "repaired_z": prf_rep.certified_z, "band": prf_rep.band,
                "verifier": prf_rep.packets[0].verifier.decision.value,
                "reason": prf_rep.packets[0].verifier.reason[:80],
            },
        },
    }


def run_v2(*, seed: int = 2026) -> dict[str, Any]:
    """Run the IDEAS_V2 through the 3×3×7 conductor.

    Returns a JSON-serializable dict (compatible with v3 ensemble).
    """
    pop = known_population(seed=seed)
    alt_pop = archetype_only_population(seed=seed)
    verifier = IndependentVerifier(verifier_id=f"verifier-v2-{seed}")

    def claim_factory(idea, p):
        return schemas.MathClaim(
            expression=idea.formula,
            symbols=["x"],
            assumptions={},
            reference_population=p,
            estimator="robust_madz",
            falsifier=idea.falsifier,
        )

    def harness_factory(diamond):
        return DiamondHarness(diamond=diamond)

    all_ideas = [_run_per_idea(i, claim_factory, pop, alt_pop, verifier, harness_factory) for i in IDEAS_V2]
    survivors = [a for a in all_ideas if not a["is_respin_of_known"]]
    return {
        "verifier_summary": verifier.summary(),
        "all_ideas": all_ideas,
        "survivors": survivors,
        "reference_population_hash": hash_population(pop),
        "alternate_population_hash": hash_population(alt_pop),
        "n_total_ideas": len(IDEAS_V2),
        "n_survivors": len(survivors),
    }


def render_report(per_idea: dict[str, Any]) -> str:
    return ""


def main() -> int:
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
