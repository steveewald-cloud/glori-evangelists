# Legacy — archived, not built, not deployed

Two loose folders lived in `~/projects/` and were **not under version control
anywhere**. Archived here on 2026-07-21 so nothing is lost, then removed locally.

Neither is wired into this app. Nothing here is on a deploy path.

## `commission-app-node/` — abandoned Node rewrite

From `~/projects/glori-commission-app` (last touched 2026-07-14). A single-file
Express + Postgres reimplementation of this app, self-described in its header as
*"GLORi Evangelist Commission System — full application (v1)"*: session auth with
scrypt-hashed passwords, role-based access (rep / manager / admin / finance),
migrate-and-seed on boot, and the commission engine.

**It is incomplete.** `server.js` ends mid-function — `readSession()` is cut off
after its first line, and the file has no routes and no `app.listen()`. It was
never committed, never deployed, and its target Fly app (`glori-commission`) does
not resolve.

Kept only because it is the newest artifact of the Node approach and captures a
comp-plan-as-data design (`DEFAULT_PLAN` stored in settings, editable in Admin)
that the Python app does not have. If that idea is wanted, port the idea — not
the file.

**The live, authoritative implementation is the Python/FastAPI app at the root of
this repo** (`main.py`, `commission.py`, `db.py`), deployed at
`glori-evangelists.fly.dev`.

## `commission-prototype/` — the prototype wrapper

From `~/projects/glori-commission-deploy` (last touched 2026-07-12). An 11-line
static server wrapping `public/index.html`, targeting Fly app `glori-commission`
(also not resolving).

**Fully redundant.** `public/index.html` is **byte-identical** to
`docs/specs/commission-prototype-LIVE-snapshot.html` in
`Glori-Holdings/glori-giving-engine`, where it is the **canonical source of the
commission math** — the `CFG` object plus `computeRep`/`overrideFor` that the
backend must reproduce exactly.

Treat the giving-engine copy as canonical. This one is a duplicate kept only for
provenance.

## Nomenclature note

Both archived folders — and this app — use "ambassador" correctly. In commission
code, `AMBASSADOR_DEDUCTION` / `is_ambassador_deal` refers to the **$250 deduction
applied when a deal arrives via an Ambassador referral**. That is the referral
customer, exactly as the canonical specs define. It is *not* a stale name for the
sales rep, and must not be renamed. See the repo `README.md`.
