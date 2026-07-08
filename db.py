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
