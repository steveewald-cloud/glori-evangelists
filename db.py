"""
Database connection pool and helpers for GLORi Evangelists Platform.
"""
import os
import psycopg
from psycopg.rows import dict_row
from contextlib import asynccontextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await psycopg.AsyncConnectionPool.open(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            connection_kwargs={"row_factory": dict_row},
        )
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


# --- User / Session helpers ---

async def get_user_by_email(conn, email: str):
    result = await conn.execute(
        "SELECT * FROM users WHERE email = %s", (email,)
    )
    return await result.fetchone()


async def create_session(conn, session_id: str, user_id: int, expires):
    await conn.execute(
        """INSERT INTO sessions (session_id, user_id, expires_at)
           VALUES (%s, %s, %s)
           ON CONFLICT (session_id) DO NOTHING""",
        (session_id, user_id, expires)
    )


async def get_session(conn, session_id: str):
    result = await conn.execute(
        """SELECT u.* FROM sessions s
           JOIN users u ON u.id = s.user_id
           WHERE s.session_id = %s AND s.expires_at > NOW()""",
        (session_id,)
    )
    return await result.fetchone()


async def delete_session(conn, session_id: str):
    await conn.execute(
        "DELETE FROM sessions WHERE session_id = %s", (session_id,)
    )


# --- Rep helpers ---

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


async def get_rep_commission_history(conn, rep_id: int, months: int = 6):
    result = await conn.execute(
        """SELECT
             ledger_month,
             SUM(net_commission) as total_commission,
             COUNT(DISTINCT client_id) as client_count
           FROM commission_ledger
           WHERE rep_id = %s
           GROUP BY ledger_month
           ORDER BY ledger_month DESC
           LIMIT %s""",
        (rep_id, months)
    )
    return await result.fetchall()


# --- Company / Leadership helpers ---

async def get_total_mrr(conn):
    result = await conn.execute(
        "SELECT COALESCE(SUM(mrr), 0) as total_mrr, COUNT(*) as client_count FROM clients WHERE status = 'active'"
    )
    return await result.fetchone()


async def get_mrr_by_plan(conn):
    result = await conn.execute(
        """SELECT plan, COUNT(*) as client_count, COALESCE(SUM(mrr), 0) as mrr
           FROM clients WHERE status = 'active'
           GROUP BY plan ORDER BY mrr DESC"""
    )
    return await result.fetchall()


async def get_all_clients_with_reps(conn):
    result = await conn.execute(
        """SELECT c.*, r.name as rep_name, r.territory_region,
           CAST(
             EXTRACT(YEAR FROM AGE(CURRENT_DATE, c.subscription_start)) * 12 +
             EXTRACT(MONTH FROM AGE(CURRENT_DATE, c.subscription_start)) + 1
           AS INTEGER) AS subscription_month
           FROM clients c
           LEFT JOIN reps r ON r.id = c.rep_id
           WHERE c.status = 'active'
           ORDER BY c.subscription_start DESC""",
    )
    return await result.fetchall()


async def get_rep_attainment_summary(conn):
    result = await conn.execute(
        """SELECT
             r.id, r.name, r.territory_region, r.quota_mrr, r.status,
             r.ramp_start_date,
             COALESCE(SUM(c.mrr), 0) as current_mrr,
             COUNT(c.id) as client_count
           FROM reps r
           LEFT JOIN clients c ON c.rep_id = r.id AND c.status = 'active'
           WHERE r.status = 'active'
           GROUP BY r.id, r.name, r.territory_region, r.quota_mrr, r.status, r.ramp_start_date
           ORDER BY current_mrr DESC"""
    )
    return await result.fetchall()


async def get_kingdom_giving_summary(conn):
    result = await conn.execute(
        """SELECT
             DATE_TRUNC('month', c.subscription_start) as month,
             COALESCE(SUM(c.mrr * 0.10), 0) as layer1_giving,
             COALESCE(SUM(c.mrr), 0) as total_mrr
           FROM clients c
           WHERE c.status = 'active'
           GROUP BY DATE_TRUNC('month', c.subscription_start)
           ORDER BY month DESC
           LIMIT 12"""
    )
    return await result.fetchall()


async def get_prospects_by_stage(conn):
    result = await conn.execute(
        """SELECT stage, COUNT(*) as count, COALESCE(SUM(
             CASE plan
               WHEN 'performance' THEN 1000
               WHEN 'builder' THEN 400
               WHEN 'diy' THEN 100
               ELSE 400
             END
           ), 0) as potential_mrr
           FROM prospects
           WHERE stage NOT IN ('live', 'lost')
           GROUP BY stage"""
    )
    return await result.fetchall()
