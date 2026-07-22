---
name: stack
description: Tech stack and file layout of the glori-evangelists app
metadata:
  type: project
---

FastAPI app (`main.py`) + `db.py` (psycopg3 async, `AsyncConnectionPool`, `dict_row`) +
Jinja2 templates in `templates/` (all extend `base.html`, which holds the CSS incl. badge
classes). Commission logic is isolated in `commission.py` (pure functions). `db.py`
computes account age in SQL as `EXTRACT(...AGE(CURRENT_DATE, subscription_start)) + 1`
(1-based `subscription_month`) — mirror this in any engine helper.

Key tables: `reps`, `clients` (has `plan`, `mrr`, `subscription_start`, `is_ambassador_deal`,
`ambassador_name`), `prospects`, `commission_ledger`, `onboarding_fees`, `giving_ledger`,
`rep_quotas`. The commission_ledger is READ by main.py but is populated by an external/
absent monthly job — this repo has no ledger-writing scheduler.

Deploy: Fly.io. Per-company FLY_API_TOKEN in project `.env.local` (never `fly auth`).
</content>
