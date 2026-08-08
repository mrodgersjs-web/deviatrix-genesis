==============================================================================
RIG-GTM DEVIATRIX v3 — 1000x better pipeline
==============================================================================

Brief: Operator-first GTM with doctrine-yield primitives and independent verification
Corpus size: 487
Ideas proposed: 9
Seeds: [2026, 2043]

Notes: v3 ensemble over 2 seeds, 9 survivors, 0 dropped, 3 hybrids from Collision Engine

─── SURVIVORS (multi-seed median composite_z) ───
#1. Doctrine-as-Smart-Contract — RIG publishes the doctrine as executable code that 
     composite_z median:     6.44σ
     composite_z variance: 0.142
     archetype_z median: 10.38σ
     is_respin: False
     high_variance: False

#2. Operator-Reputation Primitive — a portable, signed-receipt reputation object tha
     composite_z median:     6.43σ
     composite_z variance: 0.141
     archetype_z median: 10.35σ
     is_respin: False
     high_variance: False

#3. Negative-Pick Distribution — pay operators to *not* recommend competitors, with 
     composite_z median:     6.43σ
     composite_z variance: 0.141
     archetype_z median: 10.35σ
     is_respin: False
     high_variance: False

#4. Outcome-Escrow — customer pays only when the operator's claim is independently v
     composite_z median:     6.43σ
     composite_z variance: 0.141
     archetype_z median: 10.34σ
     is_respin: False
     high_variance: False

#5. Anti-Adversarial Distribution — paid leads whose quality is provably not the sel
     composite_z median:     6.43σ
     composite_z variance: 0.141
     archetype_z median: 10.34σ
     is_respin: False
     high_variance: False

#6. Counterfactual Receipt — customers pay for the *saved* outcome, not the delivere
     composite_z median:     6.43σ
     composite_z variance: 0.141
     archetype_z median: 10.34σ
     is_respin: False
     high_variance: False

#7. Doctrine-Indexed Bond — investors fund operators against a verifiable doctrine-y
     composite_z median:     6.35σ
     composite_z variance: 0.140
     archetype_z median: 10.04σ
     is_respin: False
     high_variance: False

#8. Operator-as-Public-Good — free operators paid by visible-attribution in the outp
     composite_z median:     6.30σ
     composite_z variance: 0.139
     archetype_z median: 9.82σ
     is_respin: False
     high_variance: False

#9. Reverse-Auction Doctrine — customers post a problem; operators underbid each oth
     composite_z median:     6.30σ
     composite_z variance: 0.139
     archetype_z median: 9.82σ
     is_respin: False
     high_variance: False

─── DROPPED ───
  (none)

─── HYBRIDS (Collision Engine) ───
  - Hybrid [financial_primitive + portable_reputation] — Doctrine-as-Smart-Contract × Operator-Reputation Primitive
      parents: ['Doctrine-as-Smart-Contract — RIG publishes the doctrine as executable code that pays operators when they meet it', 'Operator-Reputation Primitive — a portable, signed-receipt reputation object that follows the operator across products']
      newness: {'anti_orthodoxy': 5.631196250040854, 'mechanism_originality': 1.7, 'prior_art_distance': 5.314678899082569}
  - Hybrid [portable_reputation + independent_verification] — Operator-Reputation Primitive × Outcome-Escrow
      parents: ['Operator-Reputation Primitive — a portable, signed-receipt reputation object that follows the operator across products', "Outcome-Escrow — customer pays only when the operator's claim is independently verified"]
      newness: {'anti_orthodoxy': 5.625323945917823, 'mechanism_originality': 1.7, 'prior_art_distance': 5.395238095238096}
  - Hybrid [portable_reputation + independent_verification] — Negative-Pick Distribution × Outcome-Escrow
      parents: ['Negative-Pick Distribution — pay operators to *not* recommend competitors, with the option to disclose the payment', "Outcome-Escrow — customer pays only when the operator's claim is independently verified"]
      newness: {'anti_orthodoxy': 5.625323945917823, 'mechanism_originality': 1.7, 'prior_art_distance': 5.395238095238096}
