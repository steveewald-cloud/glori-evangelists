# GLORi Evangelists — Project Instructions

quetrex_welcome: false

## What this is

The **GLORi Evangelists Platform** — the field sales force's own tool. Reps,
pipeline, clients, and the commission engine that pays them. Python/FastAPI,
deployed at `glori-evangelists.fly.dev`.

This is the **selling** side. It is not the Giving Engine and not the referral
program — see Nomenclature below, which is a legal boundary.

## Nomenclature — get this right

**Evangelists are paid GLORi sales reps. Ambassadors are referral customers.**
Two populations, two legal structures.

| | **Evangelists** (this project) | **Ambassadors** |
|---|---|---|
| Who | Paid GLORi field reps (1099 or salaried) | An existing GLORi **customer** |
| Does | Prospects, shares the vision, closes new business | Refers peers *after* becoming a happy customer |
| Paid | Cash commission + residual (Marketing51 Sales Commission Plan) | Account credit **or** a Bless — **never cash to a person** |
| Relationship | Disclosed agent of GLORi | Advocate / customer |
| Spec | `GLORi-Evangelists-FieldSalesForce-v1.0.html` | `GLORi-Ambassadors-Architecture-v1.1.html` |

Both specs live in `Glori-Holdings/glori-giving-engine` → `docs/specs/`.

### ⚠️ "ambassador" in this codebase is CORRECT — do not rename it

`AMBASSADOR_DEDUCTION = $250`, `is_ambassador_deal`, `ambassador_name`,
`total_ambassador_deductions` all refer to the **$250 deduction applied when a deal
arrives via an Ambassador referral**. That is the referral customer, used exactly
as the canonical specs define.

It is *not* a stale name for the sales rep. A blind Ambassador→Evangelist sweep
would corrupt the commission math. **Leave every one of these alone.**

The genuinely inverted usage was in the sibling `m51-ambassadors` landing repo
(fixed 2026-07-21, renamed `m51-evangelists`).

## Stack

- Python 3.12, FastAPI, Jinja2 templates, `psycopg` + `psycopg_pool`
- Postgres; schema in `schema.sql`
- Fly.io app `glori-evangelists`, deployed via `.github/workflows/`
- `commission.py` is the engine; `main.py` the routes; `db.py` the data layer

## Commission math is canonical

The exact rules live in `commission-prototype-LIVE-snapshot.html` (the `CFG` object
+ `computeRep`/`overrideFor`), canonically held in
`Glori-Holdings/glori-giving-engine` → `docs/specs/`. A byte-identical copy is
archived at `legacy/commission-prototype/public/index.html`.

Key config: 55/20/10/5 rate bands, $5K ramp latch, $1,500 draw (months 1–3,
recoverable), $300 onboarding (50% rep), 3% override (min 20 clients, max 5
reports), **$250 ambassador deduction**, eligibility haircut (30d warn / 50%
haircut / 60d pause), 10% giving layer.

Note the **Marketing51 Sales Commission Plan** (v1.0 §5) describes a different,
SMB-shaped structure — $4,000/mo **non-recoverable** 3-month ramp draw, ~6
deals/rep/month at a 25/50/25 Starter/Growth/Pro mix, full upfront + residual, no
house accounts. Reconcile before changing engine constants; don't assume the two
agree.

## `legacy/`

Archived, not built, not deployed. Two folders that were loose in `~/projects/`
and untracked. See `legacy/README.md`. Do not wire them into anything.

## Guardrails (inherited from the Giving Engine)

- **Insurance & Financial: hard-OFF** for impact/giving attribution (anti-rebating).
  v1.0 §4 also bars Evangelists from selling those lines pending licensing.
- Government/regulated buyers: no impact-promise, no referral mechanics, pending counsel.
- Impact figures must be the Giving Engine's real, LOI-backed numbers — never
  invented (FTC net-impression standard). Distinguish Pledged from Funded.
- An Evangelist's compensation **never** flows through Ambassador rewards.

## Workflow

- Feature branches only; squash-merge to main; PRs need human approval.
- Follow the `worktree-workflow` skill for isolated work + teardown.
- Fly access uses an explicit per-company API token, never `fly auth`.
- Note: `main` auto-deploys to Fly on push.
