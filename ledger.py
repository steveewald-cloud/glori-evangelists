"""
Pure commission-ledger row computation for GLORi Evangelists.

Deliberately imports ONLY commission + datetime (no psycopg / no DB), so
this module — and the money-critical math it wraps — is unit-testable
without a live database. db.build_commission_ledger_for_month() (db.py)
wraps this in the actual fetch + upsert against Postgres.
"""
from datetime import datetime, date

from commission import account_age_months, account_month_commission, is_residual_qualified


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
    account_month = account_age_months(_as_date(client["subscription_start"]), ledger_month)
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
