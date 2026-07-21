# glori-evangelists

**GLORi Evangelists Platform** — the field sales force's own tool: reps, pipeline,
clients, and the commission engine that pays them.

Python 3.12 / FastAPI / Jinja2 / Postgres, deployed to Fly at
`glori-evangelists.fly.dev`. `main.py` holds the routes, `commission.py` the
engine, `db.py` the data layer, `schema.sql` the schema.

> The previous README described this repo as a "M51 Sales Rep & Leader Landing
> Page." That was never what it is — the recruiting landing page is the separate
> `m51-evangelists` repo.

## Nomenclature — this is a legal boundary, not a style choice

**Evangelists are paid GLORi sales reps. Ambassadors are referral customers.**

| | **Evangelists** (this project) | **Ambassadors** |
|---|---|---|
| Who | Paid GLORi field reps (1099 or salaried) | An existing GLORi **customer** |
| Does | Prospects, shares the vision, closes new business | Refers peers *after* becoming a happy customer |
| Paid | Cash commission + residual | Account credit **or** a Bless — **never cash to a person** |
| Relationship | Disclosed agent of GLORi | Advocate / customer |

The referral program was renamed "GLORi Evangelists" → "GLORi Ambassadors" in the
Ambassadors v1.1 spec, reserving "Evangelists" for the field sales force. An
Evangelist's compensation never flows through Ambassador rewards.

### ⚠️ `ambassador` in this codebase is correct — do not rename it

`AMBASSADOR_DEDUCTION` ($250), `is_ambassador_deal`, `ambassador_name`, and
`total_ambassador_deductions` refer to the **$250 deduction applied when a deal
arrives via an Ambassador referral**. That is the referral customer, exactly as the
specs define it — *not* a stale name for the rep.

A blind Ambassador→Evangelist sweep would corrupt the commission math.

## Commission math

Canonical source is `commission-prototype-LIVE-snapshot.html` (the `CFG` object +
`computeRep`/`overrideFor`) in `Glori-Holdings/glori-giving-engine` →
`docs/specs/`. A byte-identical copy is archived at
`legacy/commission-prototype/public/index.html`.

**Open:** `commission.py` implements the prototype's config ($1,500 *recoverable*
draw, months 1–3). Evangelists v1.0 §5 describes the Marketing51 Sales Commission
Plan differently — a **$4,000/mo non-recoverable** ramp draw, ~6 deals/rep/month at
a 25/50/25 mix. Those are not the same plan; confirm which governs before changing
engine constants.

## Reference specs

Both in `Glori-Holdings/glori-giving-engine` → `docs/specs/`:
`GLORi-Evangelists-FieldSalesForce-v1.0.html` (this program),
`GLORi-Ambassadors-Architecture-v1.1.html` (the referral program),
`GLORi-Giving-Engine-Architecture-v1.3.html` (taxonomy, universal API, trust boundary).

## Guardrails

- **Insurance & Financial: hard-OFF** for impact/giving attribution (anti-rebating).
  v1.0 §4 also bars Evangelists from selling those lines pending licensing.
- Government/regulated buyers: no impact-promise or referral mechanics, pending counsel.
- Impact figures must be the Giving Engine's real, LOI-backed numbers — never
  invented. Distinguish Pledged from Funded.

## `legacy/`

Archived, not built, not deployed — two folders that were loose in `~/projects/`
and untracked. See `legacy/README.md`.

## Deploy

`main` auto-deploys to Fly (`.github/workflows/`, needs `FLY_API_TOKEN`).
Fly access uses an explicit per-company API token, never `fly auth`.
