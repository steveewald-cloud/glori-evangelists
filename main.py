"""
GLORi Evangelists Platform - Main FastAPI Application
Rep dashboards, leadership BI, commission tracking, Kingdom giving.
"""
import os
import secrets
import hashlib
import calendar
from collections import defaultdict
from datetime import datetime, timedelta, date
from decimal import Decimal
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import db
import emailer
from commission import (
    account_month_commission,
    is_residual_qualified,
    milestone_bonuses,
    calculate_kingdom_giving,
    calculate_founders_pool,
    PLAN_MRR,
    RESIDUAL_GATE_ACCOUNTS,
    YEAR_TARGET_ACCOUNTS,
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
    return templates.TemplateResponse(request, "join.html", {
        "request": request,
        "applied": request.query_params.get("applied"),
    })


@app.post("/join/apply")
async def join_apply(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    product_interest: str = Form("marketing51"),
    message: str = Form(""),
):
    """Public recruiting lead-capture intake — no auth. Insert is the
    critical path; the leadership notification email is best-effort and
    must never block or fail the applicant's redirect."""
    async with db.get_conn() as conn:
        await db.create_applicant(conn, name, email, phone, product_interest, message, source="join")
        await conn.commit()

    try:
        admin_email = os.environ.get("ADMIN_EMAIL", "steve.ewald@glori.com")
        emailer.send_applicant_notification(admin_email, name, email, product_interest, message)
    except Exception:
        pass

    return RedirectResponse(url="/join?applied=1", status_code=303)


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

def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value


def _add_months(d: date, months: int) -> date:
    """Add N calendar months to a date, clamping the day to the target
    month's length (e.g. Jan 31 + 1 month -> Feb 28/29). Pure-stdlib
    replacement for dateutil.relativedelta(months=N)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _new_accounts_ytd(clients, as_of=None):
    """Count of a rep's clients whose subscription_start falls in the
    current calendar year — the input to is_residual_qualified()."""
    as_of = as_of or date.today()
    count = 0
    for c in clients:
        sub_start = _as_date(c.get("subscription_start"))
        if sub_start and sub_start.year == as_of.year:
            count += 1
    return count


def _milestone_windows(rep, clients):
    """sites_month1/quarter/year counts for milestone_bonuses(), relative
    to the rep's start_date."""
    start_date = _as_date(rep.get("start_date")) if rep else None
    if not start_date:
        return 0, 0, 0

    month1_end = _add_months(start_date, 1)
    quarter_end = _add_months(start_date, 3)
    year_end = _add_months(start_date, 12)

    sites_month1 = sites_quarter = sites_year = 0
    for c in clients:
        sub_start = _as_date(c.get("subscription_start"))
        if not sub_start or sub_start < start_date:
            continue
        if sub_start < month1_end:
            sites_month1 += 1
        if sub_start < quarter_end:
            sites_quarter += 1
        if sub_start < year_end:
            sites_year += 1
    return sites_month1, sites_quarter, sites_year


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

        rep_employed = bool(rep) and rep.get("status") == "active"
        new_accounts_ytd = _new_accounts_ytd(clients)
        residual_qualified = is_residual_qualified(new_accounts_ytd)

        earned = float(commission_this_month["total"]) if commission_this_month else 0
        draw = float(draw_for(earned))

        client_breakdown = []
        for c in clients:
            detail = account_month_commission(
                c["mrr"],
                c["subscription_month"],
                is_ambassador_deal=bool(c.get("is_ambassador_deal")),
                rep_employed=rep_employed,
                residual_qualified=residual_qualified,
            )
            client_breakdown.append({
                **c,
                "commission_this_month": float(detail["net"]),
                "phase": detail["phase"],
                "rate": float(detail["rate"]),
            })

        sites_month1, sites_quarter, sites_year = _milestone_windows(rep, clients)
        bonus_progress = milestone_bonuses(sites_month1, sites_quarter, sites_year)

    return templates.TemplateResponse(request, "rep_dashboard.html", {
        "request": request,
        "user": user,
        "rep": rep,
        "clients": client_breakdown,
        "prospects": prospects,
        "earned": earned,
        "commission_earned": earned,
        "draw": draw,
        "commission_history": commission_history,
        "plan_mrr": PLAN_MRR,
        "new_accounts_ytd": new_accounts_ytd,
        "residual_qualified": residual_qualified,
        "residual_gate": RESIDUAL_GATE_ACCOUNTS,
        "year_target": YEAR_TARGET_ACCOUNTS,
        "bonus_progress": bonus_progress,
        "sites_month1": sites_month1,
        "sites_quarter": sites_quarter,
        "sites_year": sites_year,
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
    target_plan: str = Form("growth"),
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

    # Model D: YTD new-account count per rep (vs the 50 residual gate / 100
    # target), derived from already-fetched client rows rather than a
    # dedicated query.
    this_year = date.today().year
    new_accounts_by_rep = defaultdict(int)
    for c in all_clients:
        sub_start = _as_date(c.get("subscription_start"))
        if sub_start and sub_start.year == this_year:
            new_accounts_by_rep[c.get("rep_id")] += 1

    for row in rep_attainment:
        ytd = row.get("new_accounts_ytd")
        if ytd is None:
            ytd = new_accounts_by_rep.get(row["id"], 0)
        row["new_accounts_ytd"] = ytd
        row["residual_qualified"] = is_residual_qualified(ytd)

    return templates.TemplateResponse(request, "leadership_dashboard.html", {
        "request": request,
        "user": user,
        "total_mrr": total_mrr,
        "arr": arr,
        "client_count": client_count,
        "mrr_by_plan": mrr_by_plan,
        "giving_live": giving_live,
        "rep_attainment": rep_attainment,
        "residual_gate": RESIDUAL_GATE_ACCOUNTS,
        "year_target": YEAR_TARGET_ACCOUNTS,
        "giving_summary": giving_summary,
        "all_clients": all_clients,
        "current_month": date.today().strftime("%B %Y"),
        "plan_mrr": PLAN_MRR,
        "ran": request.query_params.get("ran"),
        "ran_clients": request.query_params.get("clients"),
        "run_month_default": date.today().strftime("%Y-%m"),
    })


@app.post("/leadership/commission/run")
async def run_commission(
    request: Request,
    user=Depends(require_leadership),
    month: str = Form(""),
):
    """Money-critical: computes + upserts one commission_ledger row per
    active client for the given (or current) month. Idempotent — safe to
    re-run; see db.build_commission_ledger_for_month / ledger.py."""
    if month:
        try:
            y, m = month.split("-")
            ledger_month = date(int(y), int(m), 1)
        except (ValueError, TypeError):
            return RedirectResponse(url="/leadership?error=bad_month", status_code=303)
    else:
        today = date.today()
        ledger_month = date(today.year, today.month, 1)

    async with db.get_conn() as conn:
        summary = await db.build_commission_ledger_for_month(conn, ledger_month)
        await conn.commit()

    return RedirectResponse(
        url=f"/leadership?ran={ledger_month.strftime('%Y-%m')}&clients={summary['clients']}",
        status_code=303,
    )


@app.get("/leadership/applicants", response_class=HTMLResponse)
async def leadership_applicants(request: Request, user=Depends(require_leadership)):
    async with db.get_conn() as conn:
        applicants = await db.get_applicants(conn)
    return templates.TemplateResponse(request, "applicants.html", {
        "request": request,
        "user": user,
        "applicants": applicants,
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
        clients = await db.get_rep_clients(conn, rep_id)

    earned = float(commission["total"]) if commission else 0
    new_accounts_ytd = _new_accounts_ytd(clients)
    residual_qualified = is_residual_qualified(new_accounts_ytd)

    return JSONResponse({
        "rep_id": rep_id,
        "rep_name": rep["name"],
        "earned_this_month": earned,
        "commission_earned": earned,
        "new_accounts_ytd": new_accounts_ytd,
        "residual_qualified": residual_qualified,
        "residual_gate": RESIDUAL_GATE_ACCOUNTS,
        "year_target": YEAR_TARGET_ACCOUNTS,
        "draw": float(draw_for(earned)),
        "history": [dict(h) for h in history],
    })


@app.get("/health")
async def health():
    return {"status": "ok", "service": "glori-evangelists"}
