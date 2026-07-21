"""
GLORi Evangelists Platform - Main FastAPI Application
Rep dashboards, leadership BI, commission tracking, Kingdom giving.
"""
import os
import secrets
import hashlib
from datetime import datetime, timedelta, date
from decimal import Decimal
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import db
from commission import (
    calculate_month1_commission,
    calculate_recurring_commission,
    calculate_kingdom_giving,
    calculate_founders_pool,
    PLAN_MRR,
    RAMP_THRESHOLD,
    draw_for,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.apply_schema()
    await ensure_admin_user()
    yield
    await db.close_pool()


app = FastAPI(title="GLORi Evangelists Platform", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


# ─── Auth helpers ────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


async def ensure_admin_user():
    admin_email = os.environ.get("ADMIN_EMAIL", "steve.ewald@glori.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "GLORi2026!")
    async with db.get_conn() as conn:
        existing = await db.get_user_by_email(conn, admin_email)
        if not existing:
            await conn.execute(
                """INSERT INTO users (email, password_hash, role, name)
                   VALUES (%s, %s, 'admin', 'Steve Ewald')
                   ON CONFLICT (email) DO NOTHING""",
                (admin_email, hash_password(admin_password))
            )
            await conn.commit()


async def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    async with db.get_conn() as conn:
        return await db.get_session(conn, session_id)


async def require_user(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


async def require_leadership(request: Request):
    user = await get_current_user(request)
    if not user or user["role"] not in ("admin", "leadership"):
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


# ─── Public recruiting page ──────────────────────────────────────────────────

@app.get("/join", response_class=HTMLResponse)
async def join_page(request: Request):
    """Public GLORi Evangelist recruiting page. Folded in from the former
    standalone landing repo (m51-ambassadors) once it was clear Marketing51 is a
    GLORi product line, not a separate company — so there is one Evangelist
    program on one app. Covers Marketing51 (SMB) + Quetrex/Build.Glori (enterprise)."""
    return templates.TemplateResponse(request, "join.html", {"request": request})


# ─── Login / Logout ──────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


@app.post("/login")
async def login_post(request: Request, email: str = Form(...), password: str = Form(...)):
    async with db.get_conn() as conn:
        user = await db.get_user_by_email(conn, email)
        if not user or user["password_hash"] != hash_password(password):
            return templates.TemplateResponse(request, "login.html", {
                "request": request,
                "error": "Invalid email or password"
            })
        session_id = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(days=7)
        await db.create_session(conn, session_id, user["id"], expires)
        await conn.execute(
            "UPDATE users SET last_login = NOW() WHERE id = %s", (user["id"],)
        )
        await conn.commit()

    redirect_url = "/leadership" if user["role"] in ("admin", "leadership") else "/rep"
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie("session_id", session_id, httponly=True, max_age=604800)
    return response


@app.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id:
        async with db.get_conn() as conn:
            await db.delete_session(conn, session_id)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_id")
    return response


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    if user["role"] in ("admin", "leadership"):
        return RedirectResponse(url="/leadership")
    return RedirectResponse(url="/rep")


# ─── Rep Dashboard ───────────────────────────────────────────────────────────

@app.get("/rep", response_class=HTMLResponse)
async def rep_dashboard(request: Request, user=Depends(require_user)):
    async with db.get_conn() as conn:
        rep = await db.get_rep_by_id(conn, user["rep_id"]) if user["rep_id"] else None
        if not rep and user["role"] not in ("admin", "leadership"):
            return HTMLResponse("<h2>No rep profile found. Contact your administrator.</h2>")

        if rep:
            clients = await db.get_rep_clients(conn, rep["id"])
            prospects = await db.get_rep_prospects(conn, rep["id"])
            commission_this_month = await db.get_rep_commission_this_month(conn, rep["id"])
            commission_history = await db.get_rep_commission_history(conn, rep["id"])
        else:
            clients = []
            prospects = []
            commission_this_month = {"total": 0, "total_ambassador_deductions": 0}
            commission_history = []

        earned = float(commission_this_month["total"]) if commission_this_month else 0
        attainment = min(earned / 5000 * 100, 100)
        draw = float(draw_for(bool(rep and rep.get("is_ramp")), earned))

    return templates.TemplateResponse(request, "rep_dashboard.html", {
        "request": request,
        "user": user,
        "rep": rep,
        "clients": clients,
        "prospects": prospects,
        "earned": earned,
        "attainment": attainment,
        "draw": draw,
        "commission_history": commission_history,
        "ramp_threshold": float(RAMP_THRESHOLD),
        "plan_mrr": PLAN_MRR,
        "current_month": date.today().strftime("%B %Y"),
    })


@app.get("/rep/pipeline", response_class=HTMLResponse)
async def rep_pipeline(request: Request, user=Depends(require_user)):
    async with db.get_conn() as conn:
        rep = await db.get_rep_by_id(conn, user["rep_id"]) if user["rep_id"] else None
        prospects = await db.get_rep_prospects(conn, rep["id"]) if rep else []
    return templates.TemplateResponse(request, "pipeline.html", {
        "request": request,
        "user": user,
        "rep": rep,
        "prospects": prospects,
        "stages": ["audit", "demo", "committed", "migrated", "live", "lost"],
    })


@app.post("/rep/prospect/add")
async def add_prospect(
    request: Request,
    user=Depends(require_user),
    business_name: str = Form(...),
    contact_name: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    website_url: str = Form(""),
    vertical: str = Form("general"),
    city: str = Form(""),
    state: str = Form(""),
    target_plan: str = Form("builder"),
    notes: str = Form(""),
):
    async with db.get_conn() as conn:
        rep = await db.get_rep_by_id(conn, user["rep_id"]) if user["rep_id"] else None
        if not rep:
            raise HTTPException(status_code=400, detail="No rep profile")
        await conn.execute(
            """INSERT INTO prospects 
               (rep_id, business_name, contact_name, contact_email, contact_phone,
                website_url, vertical, city, state, target_plan, notes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (rep["id"], business_name, contact_name, contact_email, contact_phone,
             website_url, vertical, city, state, target_plan, notes)
        )
        await conn.commit()
    return RedirectResponse(url="/rep/pipeline", status_code=303)


@app.post("/rep/prospect/{prospect_id}/stage")
async def update_prospect_stage(
    prospect_id: int,
    request: Request,
    user=Depends(require_user),
    stage: str = Form(...),
):
    async with db.get_conn() as conn:
        await conn.execute(
            "UPDATE prospects SET stage = %s, updated_at = NOW() WHERE id = %s",
            (stage, prospect_id)
        )
        await conn.commit()
    return RedirectResponse(url="/rep/pipeline", status_code=303)


# ─── Leadership Dashboard ─────────────────────────────────────────────────────

@app.get("/leadership", response_class=HTMLResponse)
async def leadership_dashboard(request: Request, user=Depends(require_leadership)):
    async with db.get_conn() as conn:
        mrr_data = await db.get_total_mrr(conn)
        mrr_by_plan = await db.get_mrr_by_plan(conn)
        giving_summary = await db.get_latest_giving_summary(conn)
        rep_attainment = await db.get_rep_attainment_summary(conn)
        all_clients = await db.get_all_clients_with_reps(conn)

    total_mrr = float(mrr_data["total_mrr"]) if mrr_data else 0
    client_count = int(mrr_data["client_count"]) if mrr_data else 0
    arr = total_mrr * 12

    # Live giving calculation
    founders_pool_monthly = float(calculate_founders_pool(Decimal(str(arr))))
    total_rep_commissions = sum(float(r["earned_this_month"]) for r in rep_attainment)

    giving_live = calculate_kingdom_giving(
        gross_mrr=Decimal(str(total_mrr)),
        founders_pool=Decimal(str(founders_pool_monthly)),
        rep_commissions=Decimal(str(total_rep_commissions)),
        operating_costs=Decimal("2000"),
        current_reserve=Decimal("0"),
    )

    return templates.TemplateResponse(request, "leadership_dashboard.html", {
        "request": request,
        "user": user,
        "total_mrr": total_mrr,
        "arr": arr,
        "client_count": client_count,
        "mrr_by_plan": mrr_by_plan,
        "giving_live": giving_live,
        "rep_attainment": rep_attainment,
        "giving_summary": giving_summary,
        "all_clients": all_clients,
        "current_month": date.today().strftime("%B %Y"),
        "plan_mrr": PLAN_MRR,
    })


@app.get("/leadership/reps", response_class=HTMLResponse)
async def leadership_reps(request: Request, user=Depends(require_leadership)):
    async with db.get_conn() as conn:
        reps = await db.get_all_reps(conn)
        attainment = await db.get_rep_attainment_summary(conn)
    return templates.TemplateResponse(request, "reps_management.html", {
        "request": request,
        "user": user,
        "reps": reps,
        "attainment": attainment,
    })


@app.post("/leadership/reps/add")
async def add_rep(
    request: Request,
    user=Depends(require_leadership),
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    territory_state: str = Form(""),
    territory_region: str = Form(""),
    territory_vertical: str = Form("general"),
    start_date: str = Form(""),
    password: str = Form(...),
):
    async with db.get_conn() as conn:
        result = await conn.execute(
            """INSERT INTO reps (name, email, phone, territory_state, territory_region, territory_vertical, start_date)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (name, email, phone, territory_state, territory_region, territory_vertical,
             start_date or date.today().isoformat())
        )
        rep_row = await result.fetchone()
        rep_id = rep_row["id"]
        await conn.execute(
            """INSERT INTO users (rep_id, email, password_hash, role, name)
               VALUES (%s,%s,%s,'rep',%s)""",
            (rep_id, email, hash_password(password), name)
        )
        await conn.commit()
    return RedirectResponse(url="/leadership/reps", status_code=303)


@app.post("/leadership/clients/add")
async def add_client(
    request: Request,
    user=Depends(require_leadership),
    rep_id: int = Form(...),
    business_name: str = Form(...),
    contact_email: str = Form(""),
    plan: str = Form(...),
    subscription_start: str = Form(...),
    is_ambassador_deal: bool = Form(False),
    ambassador_name: str = Form(""),
):
    mrr = PLAN_MRR.get(plan, 400)
    async with db.get_conn() as conn:
        result = await conn.execute(
            """INSERT INTO clients (rep_id, business_name, contact_email, plan, mrr, 
               subscription_start, is_ambassador_deal, ambassador_name)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (rep_id, business_name, contact_email, plan, mrr,
             subscription_start, is_ambassador_deal, ambassador_name)
        )
        client_row = await result.fetchone()
        client_id = client_row["id"]

        # Record onboarding fee
        await conn.execute(
            """INSERT INTO onboarding_fees (rep_id, client_id, fee_date)
               VALUES (%s,%s,%s)""",
            (rep_id, client_id, subscription_start)
        )
        await conn.commit()
    return RedirectResponse(url="/leadership", status_code=303)


# ─── API endpoints for live data ─────────────────────────────────────────────

@app.get("/api/giving/live")
async def api_giving_live(user=Depends(require_user)):
    async with db.get_conn() as conn:
        mrr_data = await db.get_total_mrr(conn)
        rep_attainment = await db.get_rep_attainment_summary(conn)

    total_mrr = float(mrr_data["total_mrr"]) if mrr_data else 0
    arr = total_mrr * 12
    founders_pool_monthly = float(calculate_founders_pool(Decimal(str(arr))))
    total_rep_commissions = sum(float(r["earned_this_month"]) for r in rep_attainment)

    giving = calculate_kingdom_giving(
        gross_mrr=Decimal(str(total_mrr)),
        founders_pool=Decimal(str(founders_pool_monthly)),
        rep_commissions=Decimal(str(total_rep_commissions)),
        operating_costs=Decimal("2000"),
        current_reserve=Decimal("0"),
    )
    return JSONResponse(giving)


@app.get("/api/rep/{rep_id}/earnings")
async def api_rep_earnings(rep_id: int, user=Depends(require_user)):
    async with db.get_conn() as conn:
        rep = await db.get_rep_by_id(conn, rep_id)
        if not rep:
            raise HTTPException(status_code=404, detail="Rep not found")
        commission = await db.get_rep_commission_this_month(conn, rep_id)
        history = await db.get_rep_commission_history(conn, rep_id)

    earned = float(commission["total"]) if commission else 0
    return JSONResponse({
        "rep_id": rep_id,
        "rep_name": rep["name"],
        "earned_this_month": earned,
        "attainment_pct": min(earned / 5000 * 100, 100),
        "is_ramp": rep["is_ramp"],
        "draw": float(draw_for(rep["is_ramp"], earned)),
        "history": [dict(h) for h in history],
    })


@app.get("/health")
async def health():
    return {"status": "ok", "service": "glori-evangelists"}
