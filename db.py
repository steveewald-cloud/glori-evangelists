"""
Database connection pool and helpers for GLORi Evangelists Platform.
Uses psycopg3 + psycopg_pool (AsyncConnectionPool).
"""
import os
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from contextlib import asynccontextmanager

import ledger

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
            open=False,
        )
        await _pool.open()
    return _pool

@asynccontextmanager
async def get_conn():
    pool = await get_pool()
    async with pool.connection() as conn:
        yield conn

async def apply_schema():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        sql = f.read()
    async with get_conn() as conn:
        await conn.execute(sql)
        await conn.commit()
    print("Schema applied successfully.")

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

async def get_user_by_email(conn, email: str):
    result = await conn.execute(
        "SELECT * FROM users WHERE email = %s", (email,)
    )
    return await result.fetchone()

async def create_session(conn, id: str, user_id: int, expires):
    await conn.execute(
        """INSERT INTO sessions (id, user_id, expires_at)
           VALUES (%s, %s, %s)
           ON CONFLICT (id) DO NOTHING""",
        (id, user_id, expires)
    )

async def get_session(conn, id: str):
    result = await conn.execute(
        """SELECT u.* FROM sessions s
           JOIN users u ON u.id = s.user_id
           WHERE s.id = %s AND s.expires_at > NOW()""",
        (id,)
    )
    return await result.fetchone()

async def delete_session(conn, id: str):
    await conn.execute(
        "DELETE FROM sessions WHERE id = %s", (id,)
    )

async def get_all_reps(conn):
    result = await conn.execute(
        "SELECT * FROM reps WHERE status = 'active' ORDER BY name"
    )
    return await result.fetchall()

async def get_rep_by_id(conn, rep_id: int):
    result = await conn.execute(
        "SELECT * FROM reps WHERE id = %s", (rep_id,)
    )
    return await result.fetchone()

async def get_rep_clients(conn, rep_id: int):
    result = await conn.execute(
        """SELECT c.*,
           CAST(
             EXTRACT(YEAR FROM AGE(CURRENT_DATE, c.subscription_start)) * 12 +
             EXTRACT(MONTH FROM AGE(CURRENT_DATE, c.subscription_start)) + 1
           AS INTEGER) AS subscription_month
           FROM clients c
           WHERE c.rep_id = %s AND c.status = 'active'
           ORDER BY c.subscription_start""",
        (rep_id,)
    )
    return await result.fetchall()

async def get_rep_prospects(conn, rep_id: int):
    result = await conn.execute(
        """SELECT * FROM prospects
           WHERE rep_id = %s AND stage NOT IN ('live', 'lost')
           ORDER BY created_at DESC""",
        (rep_id,)
    )
    return await result.fetchall()

async def get_rep_commission_this_month(conn, rep_id: int):
    result = await conn.execute(
        """SELECT COALESCE(SUM(net_commission), 0) as total,
           COALESCE(SUM(ambassador_deduction), 0) as total_ambassador_deductions
           FROM commission_ledger
           WHERE rep_id = %s
           AND ledger_month = DATE_TRUNC('month', CURRENT_DATE)""",
        (rep_id,)
    )
    return await result.fetchone()

# Column list is INSERT order; the ON CONFLICT DO UPDATE SET clause is
# built from ledger.LEDGER_UPDATE_COLUMNS so the SQL and the (unit-tested,
# DB-free) idempotency contract in ledger.py can never drift apart.
_LEDGER_INSERT_COLUMNS = [
    "rep_id", "client_id", "ledger_month", "subscription_month",
    "commission_type", "mrr", "commission_amount", "ambassador_deduction",
    "net_commission",
]
_LEDGER_SET_CLAUSE = ", ".join(
    f"{col}=EXCLUDED.{col}" for col in ledger.LEDGER_UPDATE_COLUMNS
)
_LEDGER_UPSERT_SQL = f"""
    INSERT INTO commission_ledger ({", ".join(_LEDGER_INSERT_COLUMNS)})
    VALUES ({", ".join(["%s"] * len(_LEDGER_INSERT_COLUMNS))})
    ON CONFLICT ({", ".join(ledger.LEDGER_CONFLICT_TARGET)}) DO UPDATE SET
      {_LEDGER_SET_CLAUSE}
    WHERE commission_ledger.paid = false
"""


async def build_commission_ledger_for_month(conn, ledger_month):
    """Compute + upsert one commission_ledger row per active client for
    ledger_month (a first-of-month date). Idempotent: safe to re-run — a
    paid row is left completely untouched (paid/paid_date/created_at are
    never in the SET list, and the DO UPDATE only fires WHERE paid=false).
    Does NOT commit — caller commits (matches add_client/add_rep)."""
    clients_result = await conn.execute(
        """SELECT c.id, c.rep_id, c.mrr, c.subscription_start,
           c.is_ambassador_deal, r.status AS rep_status, r.track AS rep_track
           FROM clients c JOIN reps r ON r.id = c.rep_id
           WHERE c.status = 'active'"""
    )
    clients = await clients_result.fetchall()

    # Both YTD gate metrics computed in one pass: COUNT (marketing51 gate)
    # and ARR = SUM(mrr) * 12 (quetrex gate), grouped by rep, for accounts
    # started in ledger_month's calendar year.
    ytd_result = await conn.execute(
        """SELECT rep_id, COUNT(*) AS cnt, COALESCE(SUM(c.mrr), 0) * 12 AS arr
           FROM clients c
           WHERE status = 'active' AND EXTRACT(YEAR FROM subscription_start) = %s
           GROUP BY rep_id""",
        (ledger_month.year,),
    )
    ytd_rows = await ytd_result.fetchall()
    ytd_counts = {row["rep_id"]: row["cnt"] for row in ytd_rows}
    ytd_arr = {row["rep_id"]: row["arr"] for row in ytd_rows}

    paid_result = await conn.execute(
        """SELECT client_id FROM commission_ledger
           WHERE ledger_month = %s AND paid = true""",
        (ledger_month,),
    )
    paid_rows = await paid_result.fetchall()
    paid_client_ids = {row["client_id"] for row in paid_rows}

    gross_total = 0
    net_total = 0
    paid_skipped = 0

    for client in clients:
        track = client["rep_track"] or "marketing51"
        rep_id = client["rep_id"]
        metric = ytd_arr.get(rep_id, 0) if track == "quetrex" else ytd_counts.get(rep_id, 0)
        row = ledger.compute_ledger_row(
            client, client["rep_status"], metric, ledger_month, track=track
        )
        if client["id"] in paid_client_ids:
            paid_skipped += 1

        await conn.execute(
            _LEDGER_UPSERT_SQL,
            tuple(row[col] for col in _LEDGER_INSERT_COLUMNS),
        )
        gross_total += float(row["commission_amount"])
        net_total += float(row["net_commission"])

    return {
        "ledger_month": ledger_month.isoformat(),
        "clients": len(clients),
        "paid_skipped": paid_skipped,
        "gross_total": gross_total,
        "net_total": net_total,
    }


async def get_all_clients(conn):
    result = await conn.execute(
        """SELECT c.*, r.name as rep_name,
           CAST(
             EXTRACT(YEAR FROM AGE(CURRENT_DATE, c.subscription_start)) * 12 +
             EXTRACT(MONTH FROM AGE(CURRENT_DATE, c.subscription_start)) + 1
           AS INTEGER) AS subscription_month
           FROM clients c
           LEFT JOIN reps r ON r.id = c.rep_id
           WHERE c.status = 'active'
           ORDER BY c.subscription_start"""
    )
    return await result.fetchall()

async def get_all_prospects(conn):
    result = await conn.execute(
        """SELECT p.*, r.name as rep_name
           FROM prospects p
           LEFT JOIN reps r ON r.id = p.rep_id
           WHERE p.stage NOT IN ('lost')
           ORDER BY p.created_at DESC"""
    )
    return await result.fetchall()

# ─── Leadership / dashboard queries ──────────────────────────────────────────

async def get_rep_commission_history(conn, rep_id: int):
    result = await conn.execute(
        """SELECT id, ledger_month, subscription_month, commission_type, mrr,
           commission_amount, ambassador_deduction, net_commission, paid
           FROM commission_ledger WHERE rep_id = %s
           ORDER BY ledger_month DESC LIMIT 24""",
        (rep_id,),
    )
    return await result.fetchall()

async def get_total_mrr(conn):
    result = await conn.execute(
        """SELECT COALESCE(SUM(mrr), 0) AS total_mrr, COUNT(*) AS client_count
           FROM clients WHERE status = 'active'"""
    )
    return await result.fetchone()

async def get_mrr_by_plan(conn):
    result = await conn.execute(
        """SELECT plan, COALESCE(SUM(mrr), 0) AS mrr, COUNT(*) AS client_count
           FROM clients WHERE status = 'active' GROUP BY plan ORDER BY plan"""
    )
    return await result.fetchall()

async def get_latest_giving_summary(conn):
    result = await conn.execute(
        "SELECT * FROM giving_ledger ORDER BY ledger_month DESC LIMIT 1"
    )
    return await result.fetchone()

async def get_rep_attainment_summary(conn):
    # total_mrr_managed and mrr_target are required by
    # reps_management.html and leadership_dashboard.html templates.
    result = await conn.execute(
        """SELECT r.id, r.name, r.email, r.status, r.is_ramp, r.track,
           r.territory_state, r.territory_region, r.territory_vertical,
           COALESCE((SELECT SUM(cl.net_commission) FROM commission_ledger cl
             WHERE cl.rep_id = r.id
             AND cl.ledger_month = DATE_TRUNC('month', CURRENT_DATE)), 0)
             AS earned_this_month,
           COALESCE((SELECT COUNT(*) FROM clients c
             WHERE c.rep_id = r.id AND c.status = 'active'), 0) AS active_clients,
           COALESCE((SELECT SUM(c.mrr) FROM clients c
             WHERE c.rep_id = r.id AND c.status = 'active'), 0) AS total_mrr_managed,
           COALESCE((SELECT NULLIF(rq.mrr_target, 0) FROM rep_quotas rq
             WHERE rq.rep_id = r.id
             AND rq.quota_month = DATE_TRUNC('month', CURRENT_DATE)), 5000)
             AS mrr_target
           FROM reps r WHERE r.status = 'active'
           ORDER BY earned_this_month DESC, r.name"""
    )
    rows = await result.fetchall()
    for row in rows:
        earned = float(row["earned_this_month"] or 0)
        target = float(row["mrr_target"] or 5000)
        row["attainment_pct"] = round(min(earned / target * 100, 100), 1) if target > 0 else 0
    return rows

async def get_all_clients_with_reps(conn):
    result = await conn.execute(
        """SELECT c.*, r.name AS rep_name FROM clients c
           LEFT JOIN reps r ON r.id = c.rep_id
           WHERE c.status = 'active' ORDER BY c.subscription_start DESC"""
    )
    return await result.fetchall()

# ─── Invite-to-accept flow ────────────────────────────────────────────────────

async def get_user_by_rep_id(conn, rep_id: int):
    result = await conn.execute(
        "SELECT * FROM users WHERE rep_id = %s", (rep_id,)
    )
    return await result.fetchone()

async def get_user_by_invite_token(conn, token: str):
    result = await conn.execute(
        """SELECT * FROM users WHERE invite_token = %s
           AND invite_token_expires > NOW()""",
        (token,)
    )
    return await result.fetchone()

async def set_invite_token(conn, user_id: int, token: str, expires):
    await conn.execute(
        """UPDATE users SET invite_token = %s, invite_token_expires = %s,
           invited_at = NOW() WHERE id = %s""",
        (token, expires, user_id)
    )

async def accept_invite(conn, user_id: int, password_hash: str):
    await conn.execute(
        """UPDATE users SET password_hash = %s, invite_token = NULL,
           invite_token_expires = NULL, invite_accepted_at = NOW()
           WHERE id = %s""",
        (password_hash, user_id)
    )

# ─── Commission disputes ──────────────────────────────────────────────────────

async def create_dispute(conn, rep_id: int, ledger_id, client_name: str,
                          dispute_type: str, description: str):
    result = await conn.execute(
        """INSERT INTO commission_disputes
           (rep_id, ledger_id, client_name, dispute_type, description)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (rep_id, ledger_id, client_name, dispute_type, description)
    )
    row = await result.fetchone()
    return row["id"]

async def get_rep_disputes(conn, rep_id: int):
    result = await conn.execute(
        """SELECT d.*, cl.ledger_month, cl.commission_type, cl.net_commission
           FROM commission_disputes d
           LEFT JOIN commission_ledger cl ON cl.id = d.ledger_id
           WHERE d.rep_id = %s ORDER BY d.created_at DESC""",
        (rep_id,)
    )
    return await result.fetchall()

async def get_all_disputes(conn):
    result = await conn.execute(
        """SELECT d.*, r.name AS rep_name, r.email AS rep_email,
           cl.ledger_month, cl.commission_type, cl.net_commission
           FROM commission_disputes d
           LEFT JOIN reps r ON r.id = d.rep_id
           LEFT JOIN commission_ledger cl ON cl.id = d.ledger_id
           ORDER BY (d.status = 'open') DESC, d.created_at DESC"""
    )
    return await result.fetchall()

async def get_dispute_by_id(conn, dispute_id: int):
    result = await conn.execute(
        "SELECT * FROM commission_disputes WHERE id = %s", (dispute_id,)
    )
    return await result.fetchone()

async def resolve_dispute(conn, dispute_id: int, status: str,
                           resolution_notes: str, resolved_by: str):
    await conn.execute(
        """UPDATE commission_disputes
           SET status = %s, resolution_notes = %s, resolved_by = %s,
               resolved_at = NOW()
           WHERE id = %s""",
        (status, resolution_notes, resolved_by, dispute_id)
    )

# ─── Recruiting lead-capture intake ───────────────────────────────────────────

async def create_applicant(conn, name: str, email: str, phone: str,
                            product_interest: str, message: str, source: str = "join"):
    result = await conn.execute(
        """INSERT INTO evangelist_applicants
           (name, email, phone, product_interest, message, source)
           VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
        (name, email, phone, product_interest, message, source)
    )
    row = await result.fetchone()
    return row["id"]

async def get_applicants(conn):
    result = await conn.execute(
        "SELECT * FROM evangelist_applicants ORDER BY created_at DESC"
    )
    return await result.fetchall()
