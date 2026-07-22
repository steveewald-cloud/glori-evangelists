---
name: gotcha-schema-migrations
description: schema.sql re-runs on every startup and is the app's migration mechanism
metadata:
  type: project
---

`db.apply_schema()` reads and executes the ENTIRE `schema.sql` on every app startup.

**Why:** there is no Alembic/migration tool. Every statement uses `IF NOT EXISTS` /
`ADD COLUMN IF NOT EXISTS` guards so the file is safe to re-run against the live DB.

**How to apply:** to migrate live data (e.g. the Model D tier-key rename
foundation→starter etc.), append an *idempotent* `UPDATE ... WHERE plan IN (old values)`
to `schema.sql` — it self-noops after the first run. Do NOT create a separate migration
file; this repo has no runner for one. Never write a statement that isn't safe to execute
repeatedly.
</content>
