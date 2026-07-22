---
name: comp-boundaries
description: Legal/structural boundaries in the commission engine that must never be violated
metadata:
  type: project
---

The Evangelist comp plan (paid GLORi reps) must never mix with the Ambassador referral
program (customers).

**Why:** legal boundary stated in `COMP-PLAN-MODEL-D.md`. The `$250 ambassador deduction`
fires when a *deal* arrives via an Ambassador referral — it is NOT rep pay; it stays in
the engine regardless of comp-model changes.

**How to apply:** never rename `ambassador_*` identifiers (columns `is_ambassador_deal`,
`ambassador_name`, constant `AMBASSADOR_DEDUCTION`) or change the deduction semantics
(`max(month1_gross - 250, 0)`, applied only on an account's month 1). Also permanently
off-limits (never add back): leader override, Senior 25% tier. See [[project-model-d]].
</content>
