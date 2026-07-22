---
name: commission-engine-risk-areas
description: Where the GLORi Evangelists commission money-math can silently diverge — dual sources of truth and legal-boundary identifiers
metadata:
  type: reference
---

Risk areas to scrutinize when reviewing `commission.py` / `main.py` / dashboards:

- **Dual commission sources.** `db.get_rep_commission_this_month` sums the persisted
  `commission_ledger.net_commission`, while `main.py` also computes a live per-client
  breakdown via `account_month_commission`. These two can diverge if the ledger-population
  job (not in the app-code diff) drifts from the engine. Rep dashboard shows the ledger
  total as "earned" but live values in the per-client table. Verify they use the same rules.

- **Legal-boundary identifiers.** `ambassador_*` (AMBASSADOR_DEDUCTION $250, is_ambassador_deal,
  ambassador_name) must NEVER be renamed or routed through rep pay — it is the customer
  referral program, not Evangelist comp. Per COMP-PLAN-MODEL-D.md legal boundary section.

- **Constants that must survive any engine rewrite:** $250 ambassador deduction (month-1 only,
  net = max(gross - 250, 0)); $300 onboarding fee -> $150 to rep (REP_ONBOARDING); 10% Kingdom
  giving + reserve/founders-pool (`calculate_kingdom_giving`, `calculate_founders_pool`);
  configurable draw toggle (`DRAW_ENABLED` default OFF, `draw_for()` kept but decoupled from ramp).

- **Model D locked vectors (check in CODE, not just tests):** yr1 20%x12 = 240/960/2400;
  residual 5%x12 = 60/240/600; lifetime 480/1920/4800; 100-site 25/50/25 mix = $114k acq /
  $28.5k per residual yr; residual gate >= 50 new accounts/yr, re-qualify annually, NO clawback;
  5-yr per-account cap (month > 60 -> $0); commission (months 1-12) never gated; employed-only.
</content>
