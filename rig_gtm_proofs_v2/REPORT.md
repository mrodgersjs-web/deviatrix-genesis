==============================================================================
RIG-GTM DEVIATRIX — round 2: known-corpus test
==============================================================================

Reference population hash: 3b5b14a1308c0224
Alternate (known-archetype) population hash: 3eb54ea4f5909354

Verifier summary:
  verifier_id       : verifier-rig-gtm-v2
  n_reports         : 81
  n_pass            : 63
  n_fail            : 0
  n_mutate          : 9
  n_escalate        : 9
  wall_breaches     : ['opportunity-repaired_tail-3a67e091', 'opportunity-repaired_tail-a39af811', 'opportunity-repaired_tail-2e40440a', 'opportunity-repaired_tail-5b37eddf', 'opportunity-repaired_tail-3de53cb3', 'opportunity-repaired_tail-42193141', 'opportunity-repaired_tail-3caf6c03', 'opportunity-repaired_tail-74929b4b', 'opportunity-repaired_tail-1e8525b8']

Candidates: 9   Survivors: 9

─── SURVIVORS (pass the known-corpus test) ───
#1. Doctrine-Indexed Bond — investors fund operators against a verifiable doctrine-yield curve
     composite z      :    18.91σ  → +10σ–20σ
     system action    : adversarial_proof
     wall breach?     : False
     overall verdict  : ESCALATE
     archetype z      : 4.65  (vs known-archetype-only population)
     is re-spin?      : False
     owner department : finance
     90-day action    : Design the doctrine-yield curve (operator-output × verification-rate × duration), publish the spec, recruit 1 friendly i…
     falsifier        : No investor willing to fund under the doctrine-yield curve OR the yield curve is falsified by an operator OR < $100K dep…
     per-diamond z:
        opportunity  pos=  19.01  neg=  -4.62  rep=  32.59  band=≥+30σ           verdict=ESCALATE
        invention    pos=  11.35  neg=  -6.79  rep=  12.25  band=+10σ–20σ        verdict=PASS    
        proof        pos=   9.38  neg=  -6.41  rep=  11.89  band=+10σ–20σ        verdict=PASS    
     sealed hashes    :
        opportunity_repaired          : 71f059a181c599c0…
        invention_repaired            : 70a73f64f62634ba…
        proof_repaired                : 7768fd5b29b59876…

#2. Operator-Reputation Primitive — a portable, signed-receipt reputation object that follows the operator across products
     composite z      :    18.91σ  → +10σ–20σ
     system action    : adversarial_proof
     wall breach?     : False
     overall verdict  : ESCALATE
     archetype z      : 4.65  (vs known-archetype-only population)
     is re-spin?      : False
     owner department : strategy
     90-day action    : Design the reputation object schema (JSON-LD or signed CBOR), publish the spec, recruit 3 platforms willing to honour th…
     falsifier        : Operators refuse the primitive OR < 100 operators sign up OR no platform adopts the receipt format within 90 days.…
     per-diamond z:
        opportunity  pos=  19.01  neg=  -4.62  rep=  32.59  band=≥+30σ           verdict=ESCALATE
        invention    pos=  11.35  neg=  -6.79  rep=  12.25  band=+10σ–20σ        verdict=PASS    
        proof        pos=   9.38  neg=  -6.41  rep=  11.89  band=+10σ–20σ        verdict=PASS    
     sealed hashes    :
        opportunity_repaired          : 977c819782722222…
        invention_repaired            : e169b1b190858f77…
        proof_repaired                : 6bcbf144519865e4…

#3. Outcome-Escrow — customer pays only when the operator's claim is independently verified
     composite z      :    18.46σ  → +10σ–20σ
     system action    : adversarial_proof
     wall breach?     : False
     overall verdict  : ESCALATE
     archetype z      : 4.53  (vs known-archetype-only population)
     is re-spin?      : False
     owner department : gtm
     90-day action    : Design the outcome-escrow protocol (state-machine + verifier network), publish the spec, recruit 2 independent-verificat…
     falsifier        : Any comparable outcome-escrow marketplace launches within 90 days OR < 5 customer-paid escrows OR < 1 independent-verifi…
     per-diamond z:
        opportunity  pos=  18.62  neg=  -4.62  rep=  31.82  band=≥+30σ           verdict=ESCALATE
        invention    pos=  11.15  neg=  -6.79  rep=  12.05  band=+10σ–20σ        verdict=PASS    
        proof        pos=   9.19  neg=  -6.41  rep=  11.50  band=+10σ–20σ        verdict=PASS    
     sealed hashes    :
        opportunity_repaired          : a238e0cdf5caa2ef…
        invention_repaired            : bf9a02415a9304f3…
        proof_repaired                : cf0ec599f2561443…

#4. Negative-Pick Distribution — pay operators to *not* recommend competitors, with the option to disclose the payment
     composite z      :    18.46σ  → +10σ–20σ
     system action    : adversarial_proof
     wall breach?     : False
     overall verdict  : ESCALATE
     archetype z      : 4.53  (vs known-archetype-only population)
     is re-spin?      : False
     owner department : strategy
     90-day action    : Design the negative-pick contract (payment-for-non-recommendation + optional disclosure), publish the spec, recruit 3 op…
     falsifier        : Operators refuse the disclosure option OR no customer activates a negative-pick OR the disclosure itself damages trust.…
     per-diamond z:
        opportunity  pos=  18.62  neg=  -4.62  rep=  31.82  band=≥+30σ           verdict=ESCALATE
        invention    pos=  11.15  neg=  -6.79  rep=  12.05  band=+10σ–20σ        verdict=PASS    
        proof        pos=   9.19  neg=  -6.41  rep=  11.50  band=+10σ–20σ        verdict=PASS    
     sealed hashes    :
        opportunity_repaired          : 7050757de6479c0b…
        invention_repaired            : 2fbf0ecf8ac74ff9…
        proof_repaired                : 2c756fc9b8e2e957…

#5. Operator-as-Public-Good — free operators paid by visible-attribution in the output
     composite z      :    18.00σ  → +10σ–20σ
     system action    : adversarial_proof
     wall breach?     : False
     overall verdict  : ESCALATE
     archetype z      : 4.42  (vs known-archetype-only population)
     is re-spin?      : False
     owner department : content
     90-day action    : Design the attribution protocol (signed receipts + downstream conversion telemetry), publish the spec, instrument 3 publ…
     falsifier        : Operators refuse the visibility-premium OR < $50K downstream revenue is generated in 90 days OR no measurable attributio…
     per-diamond z:
        opportunity  pos=  18.23  neg=  -4.62  rep=  31.04  band=≥+30σ           verdict=ESCALATE
        invention    pos=  10.95  neg=  -6.79  rep=  11.85  band=+10σ–20σ        verdict=PASS    
        proof        pos=   8.99  neg=  -6.41  rep=  11.12  band=+10σ–20σ        verdict=PASS    
     sealed hashes    :
        opportunity_repaired          : 76f2df567204d117…
        invention_repaired            : e79152789eebbcaa…
        proof_repaired                : 639e62e0f74c15bb…

#6. Doctrine-as-Smart-Contract — RIG publishes the doctrine as executable code that pays operators when they meet it
     composite z      :    18.00σ  → +10σ–20σ
     system action    : adversarial_proof
     wall breach?     : False
     overall verdict  : ESCALATE
     archetype z      : 4.42  (vs known-archetype-only population)
     is re-spin?      : False
     owner department : engineering
     90-day action    : Write the doctrine as a smart contract (Solidity or equivalent), publish the code + verification guarantees, deploy on t…
     falsifier        : No operator accepts the executable doctrine OR < 5 operators auto-paid OR the verification guarantee is reverse-engineer…
     per-diamond z:
        opportunity  pos=  18.23  neg=  -4.62  rep=  31.04  band=≥+30σ           verdict=ESCALATE
        invention    pos=  10.95  neg=  -6.79  rep=  11.85  band=+10σ–20σ        verdict=PASS    
        proof        pos=   8.99  neg=  -6.41  rep=  11.12  band=+10σ–20σ        verdict=PASS    
     sealed hashes    :
        opportunity_repaired          : 29d3229d9d9d5875…
        invention_repaired            : 01e0fad40b761423…
        proof_repaired                : 93e640b91bd27bff…

#7. Counterfactual Receipt — customers pay for the *saved* outcome, not the delivered one, with the counterfactual independently reconstructed
     composite z      :    18.00σ  → +10σ–20σ
     system action    : adversarial_proof
     wall breach?     : False
     overall verdict  : ESCALATE
     archetype z      : 4.42  (vs known-archetype-only population)
     is re-spin?      : False
     owner department : strategy
     90-day action    : Design the counterfactual-receipt protocol (independent baseline reconstruction + delta measurement + payment-on-delta),…
     falsifier        : No independent re-constructor agrees to the protocol OR < $50K saved-outcome payments in 90 days OR the baseline is chal…
     per-diamond z:
        opportunity  pos=  18.23  neg=  -4.62  rep=  31.04  band=≥+30σ           verdict=ESCALATE
        invention    pos=  10.95  neg=  -6.79  rep=  11.85  band=+10σ–20σ        verdict=PASS    
        proof        pos=   8.99  neg=  -6.41  rep=  11.12  band=+10σ–20σ        verdict=PASS    
     sealed hashes    :
        opportunity_repaired          : 6239d20b6126c540…
        invention_repaired            : a2c8236d1e9bd6d2…
        proof_repaired                : b9433ba7ac52082d…

#8. Anti-Adversarial Distribution — paid leads whose quality is provably not the seller's incentive
     composite z      :    17.55σ  → +10σ–20σ
     system action    : adversarial_proof
     wall breach?     : False
     overall verdict  : ESCALATE
     archetype z      : 4.30  (vs known-archetype-only population)
     is re-spin?      : False
     owner department : sales
     90-day action    : Design the adversarial-quality protocol (third-party audit of the lead-source method), publish the spec, recruit 2 buyer…
     falsifier        : Lead quality regresses to the prior mean within 90 days OR the verification mechanism is reverse-engineered OR < 100 qua…
     per-diamond z:
        opportunity  pos=  17.83  neg=  -4.62  rep=  30.27  band=≥+30σ           verdict=ESCALATE
        invention    pos=  10.76  neg=  -6.79  rep=  11.66  band=+10σ–20σ        verdict=PASS    
        proof        pos=   8.79  neg=  -6.41  rep=  10.73  band=+10σ–20σ        verdict=PASS    
     sealed hashes    :
        opportunity_repaired          : bdcf5727d9cb7af2…
        invention_repaired            : 0b386eee2a6bbdd9…
        proof_repaired                : 99ade2f013b4fce5…

#9. Reverse-Auction Doctrine — customers post a problem; operators underbid each other on the right to fix it
     composite z      :    17.55σ  → +10σ–20σ
     system action    : adversarial_proof
     wall breach?     : False
     overall verdict  : ESCALATE
     archetype z      : 4.30  (vs known-archetype-only population)
     is re-spin?      : False
     owner department : gtm
     90-day action    : Design the reverse-auction protocol (problem-post + underbid window + escrow release), publish the spec, seed 10 problem…
     falsifier        : Operators refuse to underbid OR < 50 problems posted OR < 10 paid resolutions OR the underbid price floor collapses.…
     per-diamond z:
        opportunity  pos=  17.83  neg=  -4.62  rep=  30.27  band=≥+30σ           verdict=ESCALATE
        invention    pos=  10.76  neg=  -6.79  rep=  11.66  band=+10σ–20σ        verdict=PASS    
        proof        pos=   8.79  neg=  -6.41  rep=  10.73  band=+10σ–20σ        verdict=PASS    
     sealed hashes    :
        opportunity_repaired          : 9d0b3d701e4b70a6…
        invention_repaired            : fe740391bfb3e9f3…
        proof_repaired                : 9df98efc2186245a…

─── DROPPED (re-spins of known archetypes) ───
(none)