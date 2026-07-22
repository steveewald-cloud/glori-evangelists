"""
GLORi Evangelists Commission Engine
Full logic for all compensation tiers, ramp/steady state, upsells, ambassador deals.
"""
import os
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


PLAN_MRR = {
    "foundation": 100,
    "builder": 400,
    "performance": 1000,
}

ONBOARDING_FEE = 300
REP_ONBOARDING = 150
COMPANY_ONBOARDING = 150

RAMP_MONTH1_RATE = Decimal("0.55")
STEADY_MONTH1_RATE = Decimal("0.20")
MONTHS_2_6_RATE = Decimal("0.20")
MONTHS_7_12_RATE = Decimal("0.10")
RESIDUAL_RATE = Decimal("0.05")

RAMP_THRESHOLD = Decimal("5000.00")

# --- Ramp draw (configurable) ---------------------------------------------
# A draw is a guaranteed monthly floor for a rep still ramping (earnings under
# RAMP_THRESHOLD). It is a company-cost setting we turn ON or OFF, and it is
# ALWAYS **non-recoverable** — never repaid, never clawed back from future
# commission. It is a floor top-up, not a loan.
#
# Default OFF. New reps carry skin in the game: income depends on selling.
# Turn it on per-cohort/season by setting DRAW_ENABLED=true (and optionally
# DRAW_AMOUNT) in the environment; no code change or redeploy of logic needed.
DRAW_ENABLED = _env_bool("DRAW_ENABLED", False)
DRAW_AMOUNT = Decimal(os.environ.get("DRAW_AMOUNT", "1500.00"))

AMBASSADOR_DEDUCTION = Decimal("250.00")


def draw_for(is_ramp: bool, earned: Decimal | float) -> Decimal:
    """Non-recoverable ramp-draw top-up. Zero unless the draw is enabled AND the
    rep is ramping AND still under the threshold."""
    if DRAW_ENABLED and is_ramp and Decimal(str(earned)) < RAMP_THRESHOLD:
        return DRAW_AMOUNT
    return Decimal("0")

KINGDOM_GIVING_RATE = Decimal("0.10")
RESERVE_TARGET = Decimal("10000.00")
RESERVE_RATE = Decimal("0.10")


def get_subscription_month(subscription_start: date, ledger_month: date) -> int:
    """Return which month of the subscription this ledger_month represents (1-based)."""
    delta = relativedelta(ledger_month, subscription_start)
    return delta.years * 12 + delta.months + 1


def get_commission_tier(sub_month: int) -> tuple[Decimal, str]:
    """Return (rate, tier_name) for a given subscription month. Excludes month 1 logic (ramp vs steady handled separately)."""
    if sub_month == 1:
        return STEADY_MONTH1_RATE, "month1"
    elif 2 <= sub_month <= 6:
        return MONTHS_2_6_RATE, "months2_6"
    elif 7 <= sub_month <= 12:
        return MONTHS_7_12_RATE, "months7_12"
    else:
        return RESIDUAL_RATE, "residual"


def calculate_month1_commission(
    mrr: int,
    is_ramp: bool,
    is_ambassador_deal: bool,
) -> dict:
    """Calculate Month 1 commission with ramp/steady and ambassador deduction."""
    rate = RAMP_MONTH1_RATE if is_ramp else STEADY_MONTH1_RATE
    gross = Decimal(mrr) * rate
    ambassador_deduct = AMBASSADOR_DEDUCTION if is_ambassador_deal else Decimal("0")
    net = max(gross - ambassador_deduct, Decimal("0"))
    return {
        "rate": float(rate),
        "gross_commission": float(gross),
        "ambassador_deduction": float(ambassador_deduct),
        "net_commission": float(net),
        "commission_type": "month1",
        "is_ramp": is_ramp,
    }


def calculate_recurring_commission(
    mrr: int,
    sub_month: int,
) -> dict:
    """Calculate recurring commission for months 2+."""
    rate, tier = get_commission_tier(sub_month)
    amount = Decimal(mrr) * rate
    return {
        "rate": float(rate),
        "commission_amount": float(amount),
        "net_commission": float(amount),
        "commission_type": tier,
        "subscription_month": sub_month,
    }


def calculate_upsell_bonus(new_mrr: int, is_ramp: bool) -> dict:
    """Calculate one-time upsell bonus when client upgrades plans."""
    rate = RAMP_MONTH1_RATE if is_ramp else STEADY_MONTH1_RATE
    bonus = Decimal(new_mrr) * rate
    return {
        "rate": float(rate),
        "bonus_amount": float(bonus),
        "commission_type": "upsell_bonus",
        "is_ramp": is_ramp,
    }


def should_restart_reset(paused_at: date, restart_date: date) -> bool:
    """Returns True if pause > 6 months and commission clock resets."""
    delta = relativedelta(restart_date, paused_at)
    months_paused = delta.years * 12 + delta.months
    return months_paused >= 6


def calculate_kingdom_giving(
    gross_mrr: Decimal,
    founders_pool: Decimal,
    rep_commissions: Decimal,
    operating_costs: Decimal,
    current_reserve: Decimal,
) -> dict:
    """Calculate both giving layers and reserve for a given month."""
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


def estimate_rep_monthly_earnings(
    active_clients: list[dict],
    new_clients_this_month: list[dict],
    is_ramp: bool,
) -> dict:
    """
    Estimate total rep earnings for a given month.
    active_clients: list of {mrr, sub_month, is_ambassador_deal}
    new_clients_this_month: list of {mrr, is_ambassador_deal}
    """
    total = Decimal("0")
    breakdown = []

    # Onboarding fees for new clients
    for c in new_clients_this_month:
        total += Decimal(str(REP_ONBOARDING))
        breakdown.append({"type": "onboarding", "amount": REP_ONBOARDING, "client_mrr": c["mrr"]})

        # Month 1
        m1 = calculate_month1_commission(c["mrr"], is_ramp, c.get("is_ambassador_deal", False))
        total += Decimal(str(m1["net_commission"]))
        breakdown.append({"type": "month1", "amount": m1["net_commission"], "client_mrr": c["mrr"]})

    # Recurring for existing clients
    for c in active_clients:
        rec = calculate_recurring_commission(c["mrr"], c["sub_month"])
        total += Decimal(str(rec["net_commission"]))
        breakdown.append({"type": rec["commission_type"], "amount": rec["net_commission"], "client_mrr": c["mrr"]})

    draw = draw_for(is_ramp, total)
    total_with_draw = total + draw

    return {
        "commission_total": float(total),
        "draw": float(draw),
        "total_earnings": float(total_with_draw),
        "attainment_pct": float(min(total / RAMP_THRESHOLD * 100, 100)),
        "ramp_threshold": float(RAMP_THRESHOLD),
        "is_ramp": is_ramp,
        "breakdown": breakdown,
    }
