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

The genuinely inverted usage was in the former `m51-ambassadors` landing repo
(sales-rep page that called reps "Ambassadors"). Fixed 2026-07-21, then **folded
into this repo** as the public `GET /join` page — Marketing51 is a GLORi product
line, not a separate company, so there is one Evangelist program on one app. The
old repos (`m51-ambassadors`, `glori-ambassador`) are being archived.

## The `/join` recruiting page

`templates/join.html`, served at `GET /join` (public, no auth). Covers the two
in-scope product lines: **Marketing51** (SMB, the monthly commission table) and
**Quetrex / Build.Glori** (enterprise, sales-assisted — comp is bespoke per deal,
NOT the monthly table; v1.0 §5 flags enterprise comp as a separate open design).
Insurance/Financial are out of scope (licensing). When editing, keep "Ambassador"
referring only to the customer referral program, per the Nomenclature rule above.

## The ramp draw is configurable (and off by default)

`commission.py` → `DRAW_ENABLED` / `DRAW_AMOUNT` (env-driven) + `draw_for()`.
A draw is a guaranteed monthly floor for a ramping rep. It is **always
non-recoverable** (a floor top-up, never repaid) and **defaults OFF** — new reps
carry skin in the game, income depends on selling. Turn it on with
`DRAW_ENABLED=true` (optionally `DRAW_AMOUNT=…`) in the Fly environment; no code
change. All three draw call sites (`commission.py`, the rep dashboard, the
earnings API) go through `draw_for()`, so the flag governs everywhere.

**Amount when on is unreconciled:** prototype says $1,500; Evangelists v1.0 §5 says
$4,000/mo. Confirm with Steve before setting `DRAW_AMOUNT` for a real cohort. The
giving-engine has the same toggle at the config layer (`Draw.enabled`).

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
