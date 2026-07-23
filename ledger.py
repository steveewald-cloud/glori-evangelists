"""
Pure commission-ledger row computation for GLORi Evangelists.

Deliberately imports ONLY commission + datetime (no psycopg / no DB), so
this module — and the money-critical math it wraps — is unit-testable
without a live database. db.build_commission_ledger_for_month() (db.py)
wraps this in the actual fetch + upsert against Postgres.
"""
from datetime import datetime, date

from commission import account_month_commission, is_residual_qualified


def _as_date(value):
    """datetime/date coercion, mirrors main.py._as_date."""
    if isinstance(value, datetime):
        return value.date()
    return value


# The idempotency / no-double-pay contract, machine-checkable:
#   - LEDGER_CONFLICT_TARGET is the unique index the upsert conflicts on.
#   - LEDGER_UPDATE_COLUMNS is the ONLY set of columns the upsert's
#     DO UPDATE SET touches. It deliberately EXCLUDES paid, paid_date,
#     created_at, ledger_month, and client_id — so re-running a month never
#     changes whether/when a row was paid, never rewrites its creation
#     timestamp, and never moves it to a different (client, month) key.
LEDGER_CONFLICT_TARGET = ("client_id", "ledger_month")

LEDGER_UPDATE_COLUMNS = [
    "rep_id",
    "subscription_month",
    "commission_type",
    "mrr",
    "commission_amount",
    "ambassador_deduction",
    "net_commission",
]


def compute_ledger_row(client: dict, rep_status: str, new_accounts_ytd: int, ledger_month: date) -> dict:
    """Pure per-client Model D ledger computation for one ledger_month.

    client: dict with at least id, rep_id, mrr, subscription_start,
    is_ambassador_deal.
    rep_status: the client's assigned rep's `status` column value.
    new_accounts_ytd: count of that rep's new accounts in ledger_month's
    calendar year (input to is_residual_qualified).
    """
    # Calendar-month recognition: the subscription's start month IS month 1,
    # regardless of day-of-month. The ledger runs per calendar month (pinned to
    # the 1st) and billing is "on the 1st, partial first month prorated", so a
    # client that starts on any day of month M earns their month-1 commission
    # in month M — not the following month. (account_age_months' anniversary-day
    # semantics are for the live per-client display, not the money-recognition
    # ledger.) A ledger_month before the start resolves to <= 0, which the
    # engine treats as no commission.
    start = _as_date(client["subscription_start"])
    account_month = (ledger_month.year - start.year) * 12 + (ledger_month.month - start.month) + 1
    rep_employed = (rep_status == "active")
    residual_qualified = is_residual_qualified(new_accounts_ytd)

    comp = account_month_commission(
        client["mrr"],
        account_month,
        is_ambassador_deal=bool(client.get("is_ambassador_deal")),
        rep_employed=rep_employed,
        residual_qualified=residual_qualified,
    )

    return {
        "client_id": client["id"],
        "rep_id": client["rep_id"],
        "ledger_month": ledger_month,
        "subscription_month": account_month,
        "commission_type": comp["phase"],
        "mrr": client["mrr"],
        "commission_amount": comp["gross"],
        "ambassador_deduction": comp["ambassador_deduction"],
        "net_commission": comp["net"],
    }
