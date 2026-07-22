# Architecture Decision — Model D Comp-Engine Reconciliation

Governing spec: `COMP-PLAN-MODEL-D.md` (FULLY LOCKED, 2026-07-21). This plan encodes
Model D exactly. Scope is this repo only (`glori-evangelists`). The sibling
`glori-giving-engine`, Drive docs, and the xlsx are explicit follow-ups — do NOT touch.

`designer_required: false` — no new visual design system; template edits reuse existing
`base.html` components (attainment-box, cards, badges, kingdom-banner). Copy/label/data
changes only.

---

## 1. Technical approach

Model D collapses the former 55/20/20/10/5 banded engine into a single flat plan:

- **Commission:** 20% of MRR for an account's months **1–12**. Pure commission — no base,
  no draw dependency.
- **Residual:** 5% of MRR for an account's months **13–60** (years 2–5). Hard 5-year
  per-account cap: month > 60 → $0.
- **Employed-only:** both commission and residual are a function of the rep being employed
  in the ledger month. Rep gone → $0 going forward. **No clawback** of already-paid.
- **Residual qualification gate (annual, re-qualify):** in a given calendar year a rep
  earns the 5% residual **only if they produced ≥ 50 new accounts in that year**. A year
  with < 50 earns no new residual that year. Each year stands alone. Already-paid residual
  is never clawed back. Commission (months 1–12) is NOT gated — it is always 20%.
- **Stacking milestone bonuses** (cumulative, per rep, one-time each): Fast start $1,000 @
  10 sites in month 1; Quarter $2,500 @ 25 sites in 3 months; Year $10,000 @ 100 sites in
  12 months. All three = $13,500.
- **Tiers renamed:** Starter $100 / Growth $400 / Pro $1,000 (were Foundation/Builder/
  Performance — same price points). Rename propagates to DB plan-keys, schema defaults,
  and every template reference.
- **Removed:** 55/20/20/10/5 rate bands, `$5,000` ramp latch (`RAMP_THRESHOLD`), upsell
  bonus path (`calculate_upsell_bonus`), `get_commission_tier`, `should_restart_reset`
  (dead). No leader override, no Senior 25% tier — never add.
- **Kept, unchanged in behavior:** `$250` ambassador deduction on an ambassador-referred
  deal's month-1 (legal boundary — do NOT rename `ambassador_*` identifiers); `$300`
  onboarding fee, `$150` to rep; 10% Kingdom giving + reserve/founders-pool logic; the
  configurable draw toggle (`DRAW_ENABLED` env, default **OFF**, `draw_for()` retained).

### Representing the gate, the cap, and employment as function inputs

The engine is pure and stateless; the ledger/DB supplies the state. Each concept maps to
an explicit input:

| Model D concept | Function input | Source at call site |
|---|---|---|
| Account age → commission vs residual vs expired | `account_month: int` (1-based) | `db.get_rep_clients` already returns `subscription_month` via SQL `AGE()+1`; engine helper `account_age_months()` computes the same for tests |
| 5-year cap | `account_month > 60 → 0` | same input |
| Employed-only | `rep_employed: bool` | derived from `reps.status` / termination; default `True` |
| Residual gate (annual, re-qualify) | `residual_qualified: bool` (i.e. `new_accounts_this_year >= 50`) | computed by `is_residual_qualified(new_accounts_ytd)` from a per-rep YTD count |
| Milestone bonuses | three cumulative window counts: `sites_month1`, `sites_quarter`, `sites_year` | per-rep counts over subscription_start windows |

No clawback is a structural property: residual is evaluated per (account-month, that
year's qualification). A later unqualified year cannot retroactively zero a prior
qualified year because each ledger month is computed independently from that month's
inputs. The tests assert this independence.

---

## 2. New engine API (`commission.py`)

Constants (replace the removed banded/ramp constants):

```
PLAN_MRR = {"starter": 100, "growth": 400, "pro": 1000}
COMMISSION_RATE   = Decimal("0.20")   # months 1-12
RESIDUAL_RATE     = Decimal("0.05")   # months 13-60
COMMISSION_MONTHS = 12
RESIDUAL_END_MONTH = 60               # 5-year per-account cap
RESIDUAL_GATE_ACCOUNTS = 50           # >= 50 new accounts/yr to earn residual
YEAR_TARGET_ACCOUNTS   = 100          # stretch target / Year bonus threshold
ONBOARDING_FEE = 300; REP_ONBOARDING = 150; COMPANY_ONBOARDING = 150
AMBASSADOR_DEDUCTION = Decimal("250.00")             # unchanged, legal boundary
FAST_START_BONUS = 1000; QUARTER_BONUS = 2500; YEAR_BONUS = 10000
KINGDOM_GIVING_RATE = Decimal("0.10"); RESERVE_TARGET = Decimal("10000.00"); RESERVE_RATE = Decimal("0.10")
DRAW_ENABLED (env, default False); DRAW_AMOUNT (env, default 1500.00)
```

Functions:

- `account_age_months(subscription_start: date, as_of: date) -> int` — 1-based account
  month (mirrors the SQL used in `db.py`). Replaces `get_subscription_month`.
- `account_commission(mrr, account_month, rep_employed=True, residual_qualified=True) -> Decimal`
  — the core primitive. `0` if not employed; `mrr*0.20` for months 1–12; `mrr*0.05` for
  months 13–60 only if `residual_qualified`; `0` otherwise (incl. month > 60 cap).
- `account_month_commission(mrr, account_month, is_ambassador_deal=False, rep_employed=True, residual_qualified=True) -> dict`
  — display/ledger breakdown: `{rate, phase, gross, ambassador_deduction, net,
  account_month}` where `phase ∈ {"commission","residual","expired","unemployed"}`.
  Ambassador deduction applies only when `account_month == 1`; `net = max(gross - deduction, 0)`.
- `account_year1_commission(mrr) -> Decimal` → `mrr*0.20*12` (Starter 240 / Growth 960 / Pro 2400).
- `account_residual_year(mrr) -> Decimal` → `mrr*0.05*12` (Starter 60 / Growth 240 / Pro 600).
- `account_lifetime(mrr) -> Decimal` → year1 + 4×residual_year (Starter 480 / Growth 1920 / Pro 4800).
- `is_residual_qualified(new_accounts_ytd: int) -> bool` → `new_accounts_ytd >= 50`.
- `milestone_bonuses(sites_month1, sites_quarter, sites_year) -> dict` → per-milestone
  earned flags + amounts + `total` (all three = 13500). Stacking, one-time each.
- `rep_month_summary(clients, new_accounts_ytd=0, rep_employed=True) -> dict` — aggregates
  a rep's month: onboarding ($150/new account), per-account commission/residual (via
  `account_commission` with `residual_qualified = is_residual_qualified(new_accounts_ytd)`),
  `draw_for(total)`. Returns `{commission_earned, residual_earned, new_commission_earned,
  onboarding_total, draw, total_earnings, residual_qualified, breakdown}`. Replaces
  `estimate_rep_monthly_earnings`.
- `draw_for(earned: Decimal|float) -> Decimal` — RETAINED but decoupled from the removed
  `$5k` ramp latch. Non-recoverable floor top-up: `DRAW_AMOUNT - earned` when
  `DRAW_ENABLED and earned < DRAW_AMOUNT`, else `0`. Signature drops the `is_ramp` param.
  Default OFF ⇒ always `0`.
- `calculate_kingdom_giving(...)` — UNCHANGED.
- `calculate_founders_pool(...)` — UNCHANGED.

Removed: `get_commission_tier`, `calculate_month1_commission`, `calculate_recurring_commission`,
`calculate_upsell_bonus`, `should_restart_reset`, `estimate_rep_monthly_earnings`,
`RAMP_THRESHOLD`, `RAMP_MONTH1_RATE`, `MONTHS_2_6_RATE`, `MONTHS_7_12_RATE`.

---

## 3. File ownership map (zero overlap)

### Workstream A — Engine + Tests (FOUNDATIONAL; blocks B and C)
- `commission.py` — full rewrite to the API above.
- `tests/test_commission.py` — NEW. Plain-assert unit tests, no pytest. `if __name__ ==
  "__main__"` runner prints PASS/FAIL per case and `sys.exit(1)` on any failure. Runnable
  via `python3 tests/test_commission.py`.

### Workstream B — Backend wiring (depends on A)
- `main.py` — drop dead imports (`calculate_month1_commission`, `calculate_recurring_commission`),
  import the new API; replace `RAMP_THRESHOLD`/`attainment` (÷5000) logic; update
  `draw_for(...)` call sites to the 1-arg signature; enrich `rep_dashboard` and
  `leadership_dashboard`/`api_rep_earnings` context with Model D fields (see §5 contract);
  `add_prospect` default `target_plan` `"builder"` → `"growth"`.
- `db.py` — add `new_accounts_ytd` (count of the rep's clients whose `subscription_start`
  is in the current calendar year) to `get_rep_attainment_summary`; expose it and keep
  `earned_this_month`. `mrr_target`/attainment_pct stay for backward-safety but are no
  longer the headline (see migration notes).
- `schema.sql` — change `clients.plan` and `prospects.target_plan` DEFAULT `'builder'` →
  `'growth'`; append idempotent tier-rename data migration (foundation→starter,
  builder→growth, performance→pro on both tables).

### Workstream C — App dashboards (depends on B for context vars, on A for plan keys)
- `templates/rep_dashboard.html` — replace the `$5k` attainment hero + `55/20/10/5` inline
  rate logic with Model D: Commission Earned this month, residual status/eligibility,
  YTD new-account count vs the 50 residual gate and 100 target, bonus progress. Remove
  "Ramp Phase — $1,500 draw active"; show draw only when `draw > 0`.
- `templates/leadership_dashboard.html` — plan labels Starter/Growth/Pro; rep table shows
  YTD new accounts vs 50 gate / 100 target and residual-qualified state instead of `$5k`
  MRR attainment; add-client + plan dropdowns use `starter/growth/pro`.
- `templates/base.html` — add `.badge-starter/.badge-growth/.badge-pro` CSS; repoint the
  cosmetic territory badges in `rep_dashboard.html` off the old plan class names.
- `templates/pipeline.html` — plan dropdown values/labels → starter/growth/pro.
- `templates/reps_management.html` — remove `$5K/mo threshold · $1,500 draw` copy and the
  `earned < 5000` ramp conditional; reflect Model D (no ramp/quota latch).

### Workstream D — Recruiting page (independent; parallel with all)
- `templates/join.html` — strip 25% Senior tier, 10% Leader override, `$500` Fast Start,
  and the Leader-track/override sections; set 20% yr1 → 5% residual; add the three stacking
  bonuses ($1k/$2.5k/$10k) and the 50-accounts/yr residual gate; rename tier cards +
  commission table to Starter/Growth/Pro; add the line "subject to management change at
  any time."

---

## 4. Dependency order

```
A (engine + tests)  ──►  B (main.py, db.py, schema.sql)  ──►  C (app dashboards)
                                                          
D (join.html) ── fully independent, run any time
```

- A must land first: B imports the new API; C renders the new plan keys/badges.
- B before C: C's templates render context keys that B produces (see §5). C developer may
  code against the §5 contract in parallel, integrating after B.
- D shares no files and no data contract with A/B/C — parallel from the start.

---

## 5. Template context contract (B produces → C consumes)

`rep_dashboard` context adds:
- `commission_earned: float` — rep's Model D commission this month (was `earned`).
- `new_accounts_ytd: int`, `residual_qualified: bool` (ytd ≥ 50), `residual_gate: 50`,
  `year_target: 100`.
- `bonus_progress: {fast_start, quarter, year}` — earned flags for milestone display.
- per-client enrichment: `commission_this_month`, `phase` (commission/residual/expired).
- `draw: float` (0 when `DRAW_ENABLED` off).
- Removed: `attainment`, `ramp_threshold`.

`leadership_dashboard` / `api_rep_earnings`: each rep row gains `new_accounts_ytd` and
`residual_qualified`; `plan_mrr` keys become `starter/growth/pro`.

---

## 6. Acceptance criteria

**Engine / tests (Workstream A) — `python3 tests/test_commission.py` exits 0:**
1. `PLAN_MRR == {"starter":100,"growth":400,"pro":1000}`.
2. `account_year1_commission` = 240 / 960 / 2400 (Starter/Growth/Pro).
3. `account_residual_year` = 60 / 240 / 600.
4. `account_lifetime` = 480 / 1920 / 4800.
5. `account_commission` phases: month 1 & 12 → 20%×MRR; month 13 & 60 → 5%×MRR (qualified);
   month 61 → 0 (5-yr cap); month > 60 → 0.
6. Employment gate: `rep_employed=False` → 0 for any month.
7. Residual gate: month-13 with `new_accounts_ytd=49` → residual 0; with 50 → 5%×MRR.
   Commission months 1–12 return 20% even when ytd < 50 (gate does not touch commission).
8. No clawback: a qualified year's residual value is independent of any later year's
   qualification (function computed per-month from that month's inputs).
9. `milestone_bonuses`: (10,25,100)→13500; (10,0,0)→1000; (0,25,0)→2500; (0,0,100)→10000;
   (9,24,99)→0.
10. Ambassador: `account_month_commission(400, 1, is_ambassador_deal=True)` reports
    `ambassador_deduction == 250` and `net == 0` (max(80−250,0)); non-ambassador month-1
    net == 80. `ONBOARDING_FEE == 300`, `REP_ONBOARDING == 150`.
11. 100-site 25/50/25 mix: Σ `account_year1_commission` = 114000; Σ `account_residual_year`
    = 28500.
12. `draw_for(0) == 0` with `DRAW_ENABLED` default OFF.

**Backend (Workstream B):** app imports cleanly (`python3 -c "import main"` with no engine
ImportError); no residual references to `RAMP_THRESHOLD`/removed functions; `db.get_rep_
attainment_summary` returns `new_accounts_ytd`; schema applies idempotently and re-running
the tier-rename migration is a no-op.

**Dashboards (Workstream C):** rep + leadership pages render with no `$5k`/55%/ramp
attainment; plan badges/dropdowns show Starter/Growth/Pro; rep dashboard shows commission
earned, residual eligibility, YTD accounts vs 50 gate & 100 target, bonus progress.

**Recruiting (Workstream D):** `/join` shows no Senior 25% / Leader override / $500 Fast
Start; shows 20%→5% residual, the three stacking bonuses, the 50/yr gate, Starter/Growth/
Pro, and "subject to management change at any time."

---

## 7. Migration notes

- **Tier plan-key rename is a live-data migration.** `clients.plan` and
  `prospects.target_plan` store `'foundation'|'builder'|'performance'`. Model D renames the
  canonical keys to `starter|growth|pro`. Because `schema.sql` is re-run on every startup
  (`db.apply_schema`) with `IF NOT EXISTS` guards, the rename ships as idempotent
  `UPDATE ... WHERE plan IN ('foundation','builder','performance')` statements appended to
  `schema.sql` (naturally no-op after the first run) plus the DEFAULT change to `'growth'`.
  `PLAN_MRR.get(plan, 400)` in `add_client` keeps a safe fallback. After migration,
  templates render `badge-{{plan}}` = `badge-starter/growth/pro`, so `base.html` must add
  those classes.
- **`commission_ledger.commission_type`** historical rows keep the old strings
  (`month1`/`months2_6`/`months7_12`/`residual`); Model D writes `commission`/`residual`/
  `onboarding`. This is display-only; no ledger backfill required. History views tolerate
  both.
- **`reps.is_ramp` and `rep_quotas.mrr_target`/DEFAULT 5000 are retained but deprecated.**
  Model D has no ramp latch or $5k quota; the columns stay to avoid a destructive live-DB
  change, but nothing in the comp path reads `is_ramp` for rate, and the dashboards stop
  surfacing `$5k` attainment. Safe to drop in a later cleanup PR (out of scope here).
- **Draw stays built but OFF.** `DRAW_ENABLED` default False ⇒ `draw_for` returns 0; the
  `is_ramp` argument is removed from its signature (only call sites in `main.py` change).
- **`ambassador_*` identifiers are untouched** (legal boundary): column names, the $250
  constant name, and the deduction semantics (`max(gross−250, 0)` on month-1) are preserved
  exactly.
</content>
</invoke>
