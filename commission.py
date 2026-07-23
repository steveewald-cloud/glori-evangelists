"""
GLORi Evangelists Commission Engine — Model D

Single flat comp plan (COMP-PLAN-MODEL-D.md, locked 2026-07-21):
  - Commission: 20% of MRR for an account's months 1-12. Pure commission,
    no base, no draw dependency.
  - Residual: 5% of MRR for an account's months 13-60 (years 2-5). Hard
    5-year per-account cap (month > 60 -> $0).
  - Both commission and residual are employed-only: they stop the day the
    rep leaves. No clawback of already-paid amounts.
  - Residual qualification gate (annual, re-qualify): a rep earns the 5%
    residual in a given year only if they produced >= 50 new accounts that
    year. Commission (months 1-12) is never gated.
  - Stacking, one-time milestone bonuses: Fast start $1,000 @ 10 sites in
    month 1; Quarter $2,500 @ 25 sites in 3 months; Year $10,000 @ 100
    sites in 12 months. All three = $13,500.
  - Tiers: Starter $100 / Growth $400 / Pro $1,000.

Kept unchanged: the $250 ambassador deduction (legal boundary — do not
rename ambassador_* identifiers), the $300 onboarding fee ($150 to rep),
the 10% Kingdom giving + reserve/founders-pool logic, and the configurable
draw toggle (DRAW_ENABLED, default OFF).
"""
import os
from decimal import Decimal
from datetime import date


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# --- Tiers -------------------------------------------------------------
PLAN_MRR = {
    "starter": 100,
    "growth": 400,
    "pro": 1000,
}

# --- Onboarding ----------------------------------------------------------
ONBOARDING_FEE = 300
REP_ONBOARDING = 150
COMPANY_ONBOARDING = 150

# --- Model D rate/phase constants ----------------------------------------
COMMISSION_RATE = Decimal("0.20")      # months 1-12
RESIDUAL_RATE = Decimal("0.05")        # months 13-60
COMMISSION_MONTHS = 12
RESIDUAL_END_MONTH = 60                # 5-year per-account cap

RESIDUAL_GATE_ACCOUNTS = 50            # >= 50 new accounts/yr to earn residual
YEAR_TARGET_ACCOUNTS = 100             # stretch target / Year bonus threshold

# --- Enterprise (Quetrex) track: ARR-gated residual qualification ---------
# Same per-account math as marketing51 (20% mo 1-12, 5% mo 13-60, employed-
# only, 5-yr cap) — the ONLY difference is the annual residual gate: instead
# of a new-account COUNT, quetrex reps qualify on new-account ARR booked
# that year (a new account's ARR = its MRR * 12). No milestone bonuses on
# this track.
ENTERPRISE_RESIDUAL_GATE_ARR = 250000  # >= $250K ARR booked/yr to earn residual
ENTERPRISE_ANNUAL_TARGET_ARR = 500000  # stretch target (no bonus attached)

# --- Stacking, one-time milestone bonuses ---------------------------------
FAST_START_BONUS = 1000                # >= 10 new sites in month 1
QUARTER_BONUS = 2500                   # >= 25 new sites in 3 months
YEAR_BONUS = 10000                     # >= 100 new sites in 12 months

# --- Ambassador deduction (legal boundary — do not rename) ----------------
AMBASSADOR_DEDUCTION = Decimal("250.00")

# --- Kingdom giving / reserve / founders pool (unchanged) -----------------
KINGDOM_GIVING_RATE = Decimal("0.10")
RESERVE_TARGET = Decimal("10000.00")
RESERVE_RATE = Decimal("0.10")

# --- Draw (configurable, default OFF; infrastructure retained) -----------
# A draw is a guaranteed, non-recoverable monthly floor top-up. Default OFF
# per Model D section 1 — new reps carry skin in the game, income depends
# on selling. Turn it on with DRAW_ENABLED=true (optionally DRAW_AMOUNT) in
# the environment; no code change required.
DRAW_ENABLED = _env_bool("DRAW_ENABLED", False)
DRAW_AMOUNT = Decimal(os.environ.get("DRAW_AMOUNT", "1500.00"))


def draw_for(earned: "Decimal | float") -> Decimal:
    """Non-recoverable floor top-up. Zero unless DRAW_ENABLED and earned is
    still under DRAW_AMOUNT. Decoupled from any ramp/quota latch."""
    earned_d = earned if isinstance(earned, Decimal) else Decimal(str(earned))
    if DRAW_ENABLED and earned_d < DRAW_AMOUNT:
        return DRAW_AMOUNT - earned_d
    return Decimal("0")


def account_age_months(subscription_start: date, as_of: date) -> int:
    """1-based account month, mirroring the SQL AGE()+1 used in db.py.

    Pure-stdlib calendar-month diff (no python-dateutil dependency): counts
    completed calendar months between subscription_start and as_of, rolling
    back one month if as_of's day-of-month hasn't yet reached
    subscription_start's day-of-month (matches dateutil.relativedelta's
    `.months` field for this comparison)."""
    months = (as_of.year - subscription_start.year) * 12 + (
        as_of.month - subscription_start.month
    )
    if as_of.day < subscription_start.day:
        months -= 1
    return months + 1


def account_commission(
    mrr,
    account_month: int,
    rep_employed: bool = True,
    residual_qualified: bool = True,
) -> Decimal:
    """Core primitive. 0 if not employed; 20% of MRR for months 1-12;
    5% of MRR for months 13-60 only if residual_qualified; 0 otherwise
    (including month > 60, the 5-year cap)."""
    if not rep_employed:
        return Decimal("0")

    mrr_d = mrr if isinstance(mrr, Decimal) else Decimal(str(mrr))

    if 1 <= account_month <= COMMISSION_MONTHS:
        return mrr_d * COMMISSION_RATE
    if COMMISSION_MONTHS < account_month <= RESIDUAL_END_MONTH:
        if residual_qualified:
            return mrr_d * RESIDUAL_RATE
        return Decimal("0")
    return Decimal("0")


def account_month_commission(
    mrr,
    account_month: int,
    is_ambassador_deal: bool = False,
    rep_employed: bool = True,
    residual_qualified: bool = True,
) -> dict:
    """Display/ledger breakdown for a single account-month.

    phase in {"commission", "residual", "expired", "unemployed"}. The
    ambassador $250 deduction applies only on account_month == 1;
    net = max(gross - deduction, 0).
    """
    mrr_d = mrr if isinstance(mrr, Decimal) else Decimal(str(mrr))

    if not rep_employed:
        rate = Decimal("0")
        phase = "unemployed"
    elif 1 <= account_month <= COMMISSION_MONTHS:
        rate = COMMISSION_RATE
        phase = "commission"
    elif COMMISSION_MONTHS < account_month <= RESIDUAL_END_MONTH:
        phase = "residual"
        rate = RESIDUAL_RATE if residual_qualified else Decimal("0")
    else:
        rate = Decimal("0")
        phase = "expired"

    gross = mrr_d * rate
    ambassador_deduction = (
        AMBASSADOR_DEDUCTION if (is_ambassador_deal and account_month == 1) else Decimal("0")
    )
    net = max(gross - ambassador_deduction, Decimal("0"))

    return {
        "rate": rate,
        "phase": phase,
        "gross": gross,
        "ambassador_deduction": ambassador_deduction,
        "net": net,
        "account_month": account_month,
    }


def account_year1_commission(mrr) -> Decimal:
    """mrr * 20% * 12 -> Starter 240 / Growth 960 / Pro 2400."""
    mrr_d = mrr if isinstance(mrr, Decimal) else Decimal(str(mrr))
    return mrr_d * COMMISSION_RATE * 12


def account_residual_year(mrr) -> Decimal:
    """mrr * 5% * 12 -> Starter 60 / Growth 240 / Pro 600. One residual
    year per account."""
    mrr_d = mrr if isinstance(mrr, Decimal) else Decimal(str(mrr))
    return mrr_d * RESIDUAL_RATE * 12


def account_lifetime(mrr) -> Decimal:
    """year1 + 4 * residual_year -> Starter 480 / Growth 1920 / Pro 4800.
    5-year lifetime per retained account."""
    return account_year1_commission(mrr) + 4 * account_residual_year(mrr)


def is_residual_qualified(new_accounts_ytd: int) -> bool:
    """Residual qualification gate: new_accounts_ytd >= 50. Annual,
    re-qualify each year."""
    return new_accounts_ytd >= RESIDUAL_GATE_ACCOUNTS


def is_residual_qualified_enterprise(arr_booked_ytd) -> bool:
    """Enterprise (quetrex) residual qualification gate: a rep qualifies
    for the 5% residual in a given year only if they booked >= $250,000 in
    new-account ARR (MRR * 12) that year. Annual, re-qualify each year --
    mirrors is_residual_qualified's semantics, just on ARR instead of a
    account count."""
    arr_d = arr_booked_ytd if isinstance(arr_booked_ytd, Decimal) else Decimal(str(arr_booked_ytd))
    return arr_d >= ENTERPRISE_RESIDUAL_GATE_ARR


def is_residual_qualified_for_track(track: str, metric) -> bool:
    """Single resolver so ledger/db/main never branch on track
    independently: quetrex reps are gated on ARR booked YTD
    (is_residual_qualified_enterprise); every other track (marketing51,
    or anything unrecognized) is gated on new-account COUNT YTD
    (is_residual_qualified) -- unchanged behavior."""
    if track == "quetrex":
        return is_residual_qualified_enterprise(metric)
    return is_residual_qualified(metric)


def milestone_bonuses(sites_month1: int, sites_quarter: int, sites_year: int) -> dict:
    """Stacking, one-time bonuses. Fast start $1,000 (>= 10 sites mo1),
    Quarter $2,500 (>= 25 in 3mo), Year $10,000 (>= 100 in 12mo). All
    three = 13,500."""
    fast_start_earned = sites_month1 >= 10
    quarter_earned = sites_quarter >= 25
    year_earned = sites_year >= YEAR_TARGET_ACCOUNTS

    fast_start_amount = FAST_START_BONUS if fast_start_earned else 0
    quarter_amount = QUARTER_BONUS if quarter_earned else 0
    year_amount = YEAR_BONUS if year_earned else 0

    return {
        "fast_start_earned": fast_start_earned,
        "fast_start_amount": fast_start_amount,
        "quarter_earned": quarter_earned,
        "quarter_amount": quarter_amount,
        "year_earned": year_earned,
        "year_amount": year_amount,
        "total": fast_start_amount + quarter_amount + year_amount,
    }


def rep_month_summary(clients: list, new_accounts_ytd: int = 0, rep_employed: bool = True) -> dict:
    """Aggregates a rep's month.

    clients: list of dicts, each with at least {mrr, account_month} and
    optionally {is_ambassador_deal, is_new}. is_new defaults to
    account_month == 1 (i.e. the account's very first ledger month).

    $150 onboarding per new account; per-account commission/residual via
    account_commission with residual_qualified = is_residual_qualified
    (new_accounts_ytd); plus draw_for(total).
    """
    residual_qualified = is_residual_qualified(new_accounts_ytd)

    commission_earned = Decimal("0")
    residual_earned = Decimal("0")
    new_commission_earned = Decimal("0")
    onboarding_total = Decimal("0")
    breakdown = []

    for c in clients:
        mrr = c["mrr"]
        account_month = c["account_month"]
        is_ambassador_deal = c.get("is_ambassador_deal", False)
        is_new = c.get("is_new", account_month == 1)

        detail = account_month_commission(
            mrr,
            account_month,
            is_ambassador_deal=is_ambassador_deal,
            rep_employed=rep_employed,
            residual_qualified=residual_qualified,
        )
        net = detail["net"]

        onboarding = Decimal("0")
        if is_new:
            onboarding = Decimal(str(REP_ONBOARDING))
            onboarding_total += onboarding

        if detail["phase"] == "commission":
            commission_earned += net
            if is_new:
                new_commission_earned += net
        elif detail["phase"] == "residual":
            residual_earned += net

        breakdown.append({
            **detail,
            "mrr": mrr,
            "is_new": is_new,
            "onboarding": onboarding,
        })

    total = commission_earned + residual_earned + onboarding_total
    draw = draw_for(total)
    total_earnings = total + draw

    return {
        "commission_earned": commission_earned,
        "residual_earned": residual_earned,
        "new_commission_earned": new_commission_earned,
        "onboarding_total": onboarding_total,
        "draw": draw,
        "total_earnings": total_earnings,
        "residual_qualified": residual_qualified,
        "breakdown": breakdown,
    }


def calculate_kingdom_giving(
    gross_mrr: Decimal,
    founders_pool: Decimal,
    rep_commissions: Decimal,
    operating_costs: Decimal,
    current_reserve: Decimal,
) -> dict:
    """Calculate both giving layers and reserve for a given month.
    UNCHANGED from the prior engine."""
    giving_layer1 = gross_mrr * KINGDOM_GIVING_RATE

    net_remainder = gross_mrr - giving_layer1 - founders_pool - rep_commissions - operating_costs

    if net_remainder < 0:
        net_remainder = Decimal("0")

    reserve_needed = max(RESERVE_TARGET - current_reserve, Decimal("0"))
    if current_reserve >= RESERVE_TARGET:
        reserve_amount = Decimal("0")
        giving_layer2 = net_remainder
        reserve_target_met = True
    else:
        reserve_amount = min(net_remainder * RESERVE_RATE, reserve_needed)
        giving_layer2 = net_remainder - reserve_amount
        reserve_target_met = (current_reserve + reserve_amount) >= RESERVE_TARGET

    total_kingdom = giving_layer1 + giving_layer2

    return {
        "gross_mrr": float(gross_mrr),
        "giving_layer1": float(giving_layer1),
        "founders_pool": float(founders_pool),
        "rep_commissions": float(rep_commissions),
        "operating_costs": float(operating_costs),
        "net_remainder": float(net_remainder),
        "reserve_amount": float(reserve_amount),
        "giving_layer2": float(giving_layer2),
        "total_kingdom_giving": float(total_kingdom),
        "reserve_target_met": reserve_target_met,
        "kingdom_pct_of_mrr": float(total_kingdom / gross_mrr * 100) if gross_mrr > 0 else 0,
    }


def calculate_founders_pool(annual_gross_mrr: Decimal) -> Decimal:
    """
    Founders pool calculated on marginal ARR brackets.
    50% on first $250K ARR, stepping down as revenue scales.
    This is a simplified approximation - actual brackets defined in operating agreement.
    UNCHANGED from the prior engine.
    """
    arr = annual_gross_mrr
    pool = Decimal("0")
    if arr <= 250000:
        pool = arr * Decimal("0.50")
    elif arr <= 500000:
        pool = Decimal("125000") + (arr - 250000) * Decimal("0.40")
    elif arr <= 1000000:
        pool = Decimal("225000") + (arr - 500000) * Decimal("0.30")
    else:
        pool = Decimal("375000") + (arr - 1000000) * Decimal("0.20")
    # Return monthly pool
    return pool / 12
