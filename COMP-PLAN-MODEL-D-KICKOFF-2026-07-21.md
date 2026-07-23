# Evangelist Comp Plan — "Model D" kickoff (2026-07-21)

Fired over from the **Ambassadors** tab, where Steve worked out the target structure.
This is the paste-ready brief to collapse the three existing comp models (A = Drive
doc, B = `/join` page, C = the code) into ONE and propagate it. Read
`COMP-PLAN-BRIEF-2026-07-21.md` (in the Ambassadors repo) for the three-model
backstory; this file is the decisions + the model + the propagation checklist.

**Keep the legal boundary:** this is the **Evangelist** (paid rep, cash) plan. Do
NOT wire it into the Ambassadors referral app. The `$250 ambassador deduction` in
`commission.py` STAYS (it fires when a deal arrives via an Ambassador referral).

---

## 1. Locked decisions (Steve, 2026-07-21 — do not relitigate)

- **Core rate: 20%.** Pure commission, **no base, no draw** (draw toggle already
  built, defaults OFF — leave it).
- **No leader override, no Senior 25% tier.** Strip both from the plan and the page.
- **Milestone bonuses STACK (cumulative), per rep:**
  | Milestone | Target | Bonus |
  |---|---|---|
  | Fast start | 10 sites in month 1 | **$1,000** |
  | Quarter | 25 sites in 3 months | **$2,500** |
  | Year | 100 sites in 12 months | **$10,000** + retention |
  A rep who hits all three earns **$13,500** in bonuses across year 1.
- **Retention residual: 5% of recurring**, **employed-only** — stops the day the rep
  leaves ("or until someone leaves"), **5-year cap** per account.
- **Entire plan is "subject to management change at any time."** Put that line in the
  doc, the page, and the rep acknowledgment.
- **No clawbacks.**

## 2. Recommendation on the ONE open structural question

**How the 20% and the 5% relate over an account's life** is the only thing not yet
locked. Recommended (and modeled below):

> **20% of MRR for months 1–12, then 5% residual for months 13–60 (years 2–5),**
> both only while the rep is employed.

This is the clean blend: Model B's year-1 rate + Model A's residual tail, minus the
overrides. **Steve must confirm** vs. the two alternatives (20% ongoing + 5% tail =
~2× cost; or 20% first-month-only + 5% residual = leaner).

**Retention gate (Steve asked):** keep the 5% residual **universal**, NOT gated on
100 sites. At ~6 deals/mo, 100/yr is a top-1% bar; gating there means most reps earn
no residual and the recruiting pitch overpromises. Let the **stacking bonuses** be
the volume lever and the **residual** be the retention lever. If a gate is truly
wanted, set it low (~10 active accounts), not 100/yr.

---

## 3. The model (recommended structure)

Tiers (monthly MRR): **Starter $100 · Growth $400 · Pro $1,000.**

### Per-account economics (retained account, rep stays employed)

| | Starter ($100) | Growth ($400) | Pro ($1,000) |
|---|---|---|---|
| **Year 1 commission** (20% × MRR × 12) | $240 | $960 | $2,400 |
| **Residual yrs 2–5** (5% × MRR × 48) | $240 | $960 | $2,400 |
| **5-yr lifetime / account** | **$480** | **$1,920** | **$4,800** |

Note the symmetry: 20%×12 months = 5%×48 months, so year-1 pay and the 4-year
residual tail are **equal** per account. Easy to explain to reps.

### Headline rep scenario — the 100-site / $10k-bonus rep

Assume a 25 / 50 / 25 mix (Starter/Growth/Pro) → 25 Starter, 50 Growth, 25 Pro,
all retained, rep stays 5 years. **Fully-ramped run-rate** (all 100 accounts live a
full year — an upper bound; a real year-1 ramps in and lands lower):

- **Acquisition-year commission (20%):** 25×$240 + 50×$960 + 25×$2,400
  = $6,000 + $48,000 + $60,000 = **$114,000**
- **Each residual year (5%):** $1,500 + $12,000 + $15,000 = **$28,500/yr** × 4 = **$114,000**
- **Bonuses (stacked):** **$13,500**
- **5-yr total on that cohort:** **≈ $241,500**

Blended average account = $475 MRR. A productive rep with a *rolling* book earns
both new-account 20% income and an accumulating 5% residual stack each year — that
dynamic is what the xlsx scenario model (deliverable #6 below) should show. The
numbers above are one illustrative, fully-ramped cohort, not a ramped year-1 P&L.

---

## 4. Propagation checklist (make all surfaces match Model D)

1. **Drive doc — rewrite "v3 (No Draw)"** (`1P_MYexYOiMAEFxmmZt1TzucsnKRzv0FrwC1pqqoHdsM`).
   It's currently Model A (1× upfront + 5%). Rewrite to Model D (20% yr1 → 5% yr2–5,
   stacking bonuses, employed-only residual, "subject to change").
2. **Companion Drive docs — same structure, no draw:**
   - `Marketing51_Leadership_Summary.pdf` (still shows $4k draw ⚠)
   - **`Marketing51_Rep_Summary_and_Acknowledgment.pdf` — URGENT, it's *signable* and
     still shows the $4k draw. Fix before anyone signs.**
   - `Marketing51_Commission_Model.xlsx` — rebuild the math on Model D.
3. **Recruiting page — `templates/join.html`** (Model B today). Strip the 25% Senior
   tier, 10% Leader override, and $500 Fast Start. Set: 20% yr1 → 5% residual,
   the three stacking bonuses, "subject to management change." (Page currently not
   serving on :8531 — restart after edit to verify.)
4. **Code — reconcile both engines to Model D:**
   - `glori-evangelists/commission.py` (Model C: 55/20/20/10/5 + $5k ramp).
   - `glori-giving-engine/app/commission/plan_config.py` (`DEFAULT_CONFIG`).
   - Update the giving-engine **prototype-parity tests** deliberately (they pin to
     `docs/specs/commission-prototype-LIVE-snapshot.html` — that snapshot changes too).
   - Keep `$250 ambassador deduction`, `$300 onboarding (50% rep)`, 10% giving layer
     unless Steve says otherwise — confirm each survives the new structure.
5. **Fold in the open PRs:** glori-evangelists#1 (/join + configurable draw) and
   glori-giving-engine#14 (`Draw.enabled`, CI green). Model D rides on top of both.
6. **Rebuild the xlsx scenario model** on Model D with a rolling-book multi-year view.

## 5. Suggested first move in the Evangelist tab

Confirm the §2 20%-duration decision with Steve, then read the v3 Doc + `join.html`
+ `commission.py` side by side so the three-way gap is concrete, then drive the
propagation as a Workflow (architect → parallel edits per surface → QA parity tests
→ reviewer). Nothing is merged yet — both comp PRs are open, so this can land clean.
