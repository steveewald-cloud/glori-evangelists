---
name: tier-rename-propagation
description: The Foundation/Builder/Performance -> Starter/Growth/Pro rename tends to leave stragglers outside the primary engine/template scope
metadata:
  type: project
---

Model D renamed the three plan tiers (same price points): Foundation->Starter $100,
Builder->Growth $400, Performance->Pro $1,000. PLAN_MRR keys, main.py form defaults,
and the rep/leadership dropdowns were updated, but the rename was NOT fully coherent.

**Why:** COMP-PLAN-MODEL-D.md §1 requires handling the rename "coherently including any
DB plan-key/default and template references; do not break stored data assumptions (call
out any migration need)."

**How to apply:** When a tier/plan rename lands, check ALL of these surfaces, not just
the files in the stated edit scope:
- `schema.sql` — `clients.plan DEFAULT 'builder'` and `prospects.target_plan DEFAULT 'builder'` (stale keys).
- Existing DB rows still carry old plan strings — a data migration (or a documented call-out) is required.
- `templates/pipeline.html` — still offers foundation/builder/performance options.
- `templates/base.html` — defines `.badge-foundation/builder/performance` CSS but dashboards now emit `.badge-starter/growth/pro`, which have no styling.
- `PLAN_MRR.get(plan, 400)` (main.py add_client) masks unknown keys with a 400 default — coincidentally correct for Growth, wrong for a stale 'foundation'/'performance' lookup.

Money impact is limited because `clients.mrr` is stored per-row and commission is computed
from that column, not from PLAN_MRR[plan]. So stale plan keys are a coherence/display bug,
not an engine miscalculation — flag as major, not critical. See [[commission-engine-risk-areas]].
</content>
</invoke>
