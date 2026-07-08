"""
Database connection pool and helpers for GLORi Evangelists Platform.
Uses psycopg3 + psycopg_pool (AsyncConnectionPool).
"""
import os
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from contextlib import asynccontextmanager

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
        """SELECT ledger_month, subscription_month, commission_type, mrr,
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
    # They were previously missing here, which caused a Jinja2
    # UndefinedError (surfaced as 500 Internal Server Error) as soon
    # as the first rep row existed and the templates tried to
    # number-format / divide by those undefined fields.
    result = await conn.execute(
        """SELECT r.id, r.name, r.email, r.status, r.is_ramp,
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
