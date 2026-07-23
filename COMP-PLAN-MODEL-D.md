# Evangelist Comp Plan — Model D (LOCKED 2026-07-21)

The single authoritative Evangelist compensation model. Collapses the three prior
models — **A** = Drive "v3 (No Draw)" doc, **B** = `templates/join.html` page, **C** =
`commission.py` code — into one. Supersedes the scattered state; the propagation
checklist (§5) drives every other surface to match this file.

**Legal boundary (unchanged):** this is the **Evangelist** plan — paid GLORi sales
reps, cash commission. It does **not** touch the Ambassadors referral program. The
`$250 ambassador deduction` in `commission.py` STAYS (it fires when a *deal* arrives
via an Ambassador referral; it is not rep pay). Never route Evangelist comp through
Ambassador rewards.

Provenance: structure worked out by Steve in the Ambassadors tab
(`COMP-PLAN-MODEL-D-KICKOFF-2026-07-21.md`); the two final open questions were locked
by Steve on 2026-07-21 (see §2).

---

## 1. Locked decisions (do not relitigate)

- **Core rate: 20%** of MRR. Pure commission — **no base, no draw.** (The draw toggle
  stays built and defaults **OFF**; leave it.)
- **No leader override. No Senior 25% tier.** Strip both from plan, page, and code.
- **Residual: 5% of recurring MRR, employed-only.** Stops the day the rep leaves.
  **5-year cap per account.**
- **Milestone bonuses STACK (cumulative), per rep:**
  | Milestone | Target | Bonus |
  |---|---|---|
  | Fast start | 10 sites in month 1 | **$1,000** |
  | Quarter | 25 sites in 3 months | **$2,500** |
  | Year | 100 sites in 12 months | **$10,000** + retention |
  A rep hitting all three earns **$13,500** in year-1 bonuses.
- **No clawbacks.**
- **"Subject to management change at any time."** — must appear in the Drive doc, the
  `/join` page, and the rep acknowledgment.
- **Tiers:** Starter **$100** · Growth **$400** · Pro **$1,000** (monthly MRR).
  (Renames the code's Foundation/Builder/Performance — same three price points.)

## 2. The two questions Steve locked on 2026-07-21

**Q1 — how 20% and 5% relate over an account's life.** LOCKED:
> **20% of MRR for months 1–12, then 5% residual for months 13–60 (years 2–5),**
> both only while the rep is employed.

Year-1 pay and the 4-year residual tail come out **equal** per account (20%×12 =
5%×48) — easy to explain to reps.

**Q2 — residual qualification gate.** LOCKED (Steve overrode the kickoff's "universal"
recommendation):
> **A rep qualifies for the 5% residual by producing ≥ 50 new accounts per year
> (~1 per week).** 100/year remains the stretch **target** (and the Year-milestone
> bonus), not the residual gate.

Steve's rationale: the "100/yr is top-1%" argument is stale — the platform is
automated/robust and onboarding is fast, so ~1 site/week is a normal pace, not an
elite one. The stacking bonuses are the *volume* lever; the residual is the
*retention* lever; the 50/yr gate keeps residual tied to an active, producing rep.

**Gate mechanic — LOCKED (Steve, 2026-07-21): calendar/rolling year, re-qualify.**
A rep earns the 5% residual in a given year **only if they produced ≥ 50 new accounts
in that year**. A year with < 50 new accounts earns **no new residual that year**;
residual already paid in prior qualifying years is **never clawed back** (no
clawbacks). Each year stands alone — a rep re-qualifies annually. (Rejected:
trailing-12-month pace; qualify-once-permanent; lifetime-50.) The 5-year per-account
cap still bounds how long any single account can pay residual.

## 3. The model

### Per-account economics (retained account, rep employed & residual-qualified)

| | Starter ($100) | Growth ($400) | Pro ($1,000) |
|---|---|---|---|
| **Year 1** (20% × MRR × 12) | $240 | $960 | $2,400 |
| **Residual yrs 2–5** (5% × MRR × 48) | $240 | $960 | $2,400 |
| **5-yr lifetime / account** | **$480** | **$1,920** | **$4,800** |

Symmetry: year-1 pay = the 4-year residual tail, per account.

### Headline scenario — 100-site rep, 25/50/25 mix, fully ramped, 5-yr retention

Fully-ramped upper bound (all 100 accounts live a full year; a real year-1 ramps in
and lands lower):

- **Acquisition-year commission (20%):** 25×$240 + 50×$960 + 25×$2,400 = **$114,000**
- **Each residual year (5%):** 25×$60 + 50×$240 + 25×$600 = **$28,500/yr** × 4 = **$114,000**
- **Bonuses (stacked):** **$13,500**
- **5-yr total on that cohort:** **≈ $241,500**

Blended average account = $475 MRR. A rep with a *rolling* book earns new-account 20%
income plus an accumulating 5% residual stack each year — the dynamic the xlsx
scenario model (§5 #6) should show. Numbers above are one illustrative fully-ramped
cohort, not a ramped year-1 P&L. Note: under the §2 gate, a rep producing < 50/yr
earns commission but **no** residual that period.

## 4. Constants to preserve (confirm each survives)

Carried from the current engine unless Steve says otherwise:
- **$250 ambassador deduction** — deal arrives via Ambassador referral. STAYS.
- **$300 onboarding fee, 50% to rep ($150).** Keep.
- **10% giving layer (Kingdom giving).** Keep.
Dropped by Model D: 55/20/20/10/5 rate bands, $5k ramp latch, 3% override, recoverable
draw — all removed.

**Tier rename = a data migration, not just labels.** The keys stored in
`clients.plan` / `prospects.target_plan` change Foundation/Builder/Performance →
Starter/Growth/Pro. `schema.sql` carries an idempotent `UPDATE … WHERE plan IN
(legacy keys)` block (runs each startup via `db.apply_schema()`, self-noops once
migrated) plus the new `DEFAULT 'growth'`. `mrr` is unchanged (already stored per
row). Dashboards render `badge-{{plan}}` / `plan|title`, so stale keys would show
wrong until migrated.

## 5. Propagation checklist (drive every surface to Model D)

1. **Drive doc "v3 (No Draw)"** (`1P_MYexYOiMAEFxmmZt1TzucsnKRzv0FrwC1pqqoHdsM`) —
   rewrite from Model A (1× upfront + 5%) to Model D.
2. **Companion Drive docs — no draw:**
   - `Marketing51_Leadership_Summary.pdf` (still shows $4k draw ⚠)
   - **`Marketing51_Rep_Summary_and_Acknowledgment.pdf` — URGENT: signable, still shows
     $4k draw. Fix before anyone signs.**
   - `Marketing51_Commission_Model.xlsx` — rebuild on Model D.
3. **Recruiting page `templates/join.html`** — strip 25% Senior tier, 10% Leader
   override, $500 Fast Start; set 20% yr1 → 5% residual, the three stacking bonuses,
   the 50/yr residual gate, "subject to management change." (Page is the landing page
   served at `:8531` / `GET /join` — restart to verify after edit.)
4. **Code — reconcile both engines to Model D:**
   - `glori-evangelists/commission.py` (Model C today: 55/20/20/10/5 + $5k ramp + no override impl).
   - `glori-giving-engine/app/commission/plan_config.py` (`DEFAULT_CONFIG`).
   - Deliberately update the giving-engine **prototype-parity tests** (they pin to
     `docs/specs/commission-prototype-LIVE-snapshot.html`, which changes too).
   - Keep the §4 constants; add the 50/yr residual gate + 5-yr residual cap + bonus logic.
5. **Fold in open PRs:** `glori-evangelists#1` (/join + configurable draw) and
   `glori-giving-engine#14` (`Draw.enabled`). Model D rides on top of both.
6. **Rebuild the xlsx scenario model** on Model D with a rolling-book multi-year view.

## 6. Status

- **Model: FULLY LOCKED** (§1–§2, including the residual-gate mechanic).
- **Surfaces: all still on old models** — nothing propagated yet.
- **Open PRs:** `glori-evangelists#1` open/unmerged; branch `chore/archive-legacy-commission`.

## 7. Enterprise (Quetrex) track (Steve, 2026-07-23)

A second comp track for reps selling the **Quetrex / Build.Glori** enterprise
product line, alongside the existing **marketing51** (SMB) track above. A rep
belongs to exactly one track (`reps.track`).

**Per-account math is IDENTICAL to marketing51 — nothing below changes it:**
- 20% of MRR, months 1–12 (commission phase).
- 5% of MRR, months 13–60 (residual phase), employed-only, no clawbacks.
- Hard 5-year per-account cap (month > 60 → $0).
- Enterprise deals carry **custom MRR** (not the Starter/Growth/Pro tiers) —
  the add-client flow accepts a custom monthly MRR when the client's rep is
  on the quetrex track. `clients.mrr` is unchanged (already stored per row);
  these clients are labeled `plan = 'enterprise'` for display only.

**The ONLY difference is the residual qualification gate:**
- marketing51 gate: ≥ 50 new accounts booked that calendar year (§2).
- **quetrex gate: ≥ $250,000 in new-account ARR booked that calendar year**,
  where a new account's ARR = its MRR × 12. **$500,000/yr** is the stretch
  target (mirrors the marketing51 100-account target) — there is no bonus
  attached to it.
- Same annual re-qualify / no-clawback mechanic as §2: a year that misses the
  gate earns no new residual that year; residual already paid in a prior
  qualifying year is never clawed back.
- **No milestone bonuses on the quetrex track.** The $1,000 / $2,500 /
  $10,000 stacking bonuses (§1) stay marketing51-only.

**Classification:** Quetrex reps, like marketing51 reps, are **W-2 employees**
(Steve, 2026-07-23) — see `docs/evangelist-program/worker-classification-brief.md`.

All marketing51 sections (§1–§6) above are unchanged by this addition.
