## 2026-07-22 — Comp engine collapsed to Model D
**Decision**: Single flat comp plan — 20% MRR months 1-12 (commission), 5% MRR months 13-60 (residual, employed-only), 5-yr per-account cap, annual re-qualifying residual gate at >=50 new accounts/yr, stacking one-time bonuses ($1k/$2.5k/$10k). Tiers renamed Foundation/Builder/Performance -> Starter/Growth/Pro (same $100/$400/$1000). Removed 55/20/20/10/5 bands, $5k ramp latch, upsell path, leader override, Senior 25%.
**Reason**: COMP-PLAN-MODEL-D.md locked 2026-07-21 by Steve; collapses three drifted models (Drive doc / join.html / commission.py) into one authoritative plan.
**Impact**: commission.py engine API fully rewritten; main.py + db.py + schema.sql + templates propagate. Kept intact: $250 ambassador deduction (legal boundary), $300 onboarding ($150 rep), 10% Kingdom giving, DRAW_ENABLED toggle (default OFF, draw_for retained). Sibling glori-giving-engine + Drive docs + xlsx are separate follow-ups.

