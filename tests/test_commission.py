"""
Plain-assert unit tests for the Model D commission engine (commission.py).

No external test-runner dependency (no pytest). Run directly:

    python3 tests/test_commission.py

Each test_* function raises AssertionError on failure. The __main__ runner
below executes them all, prints PASS/FAIL per case, and exits non-zero if
any case failed.
"""
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import commission as c


def _dec(x):
    return x if isinstance(x, Decimal) else Decimal(str(x))


def test_plan_mrr():
    assert c.PLAN_MRR == {"starter": 100, "growth": 400, "pro": 1000}, c.PLAN_MRR


def test_year1_commission_vectors():
    assert c.account_year1_commission(100) == Decimal("240")
    assert c.account_year1_commission(400) == Decimal("960")
    assert c.account_year1_commission(1000) == Decimal("2400")


def test_residual_year_vectors():
    assert c.account_residual_year(100) == Decimal("60")
    assert c.account_residual_year(400) == Decimal("240")
    assert c.account_residual_year(1000) == Decimal("600")


def test_lifetime_vectors():
    assert c.account_lifetime(100) == Decimal("480")
    assert c.account_lifetime(400) == Decimal("1920")
    assert c.account_lifetime(1000) == Decimal("4800")


def test_account_commission_phases():
    mrr = 400
    # Month 1 and month 12 -> 20% x MRR (commission phase)
    assert c.account_commission(mrr, 1) == _dec(mrr) * Decimal("0.20")
    assert c.account_commission(mrr, 12) == _dec(mrr) * Decimal("0.20")
    # Month 13 and month 60 -> 5% x MRR when qualified (residual phase)
    assert c.account_commission(mrr, 13, residual_qualified=True) == _dec(mrr) * Decimal("0.05")
    assert c.account_commission(mrr, 60, residual_qualified=True) == _dec(mrr) * Decimal("0.05")
    # Month 61+ -> 0 (5-year cap), regardless of qualification
    assert c.account_commission(mrr, 61, residual_qualified=True) == Decimal("0")
    assert c.account_commission(mrr, 120, residual_qualified=True) == Decimal("0")


def test_employment_gate():
    mrr = 400
    for month in (1, 6, 12, 13, 30, 60, 61, 120):
        assert c.account_commission(mrr, month, rep_employed=False) == Decimal("0"), month
    detail = c.account_month_commission(mrr, 5, rep_employed=False)
    assert detail["phase"] == "unemployed"
    assert detail["net"] == Decimal("0")


def test_residual_gate():
    mrr = 400
    # 49 new accounts this year -> not qualified -> $0 residual in month 13
    assert c.account_commission(mrr, 13, residual_qualified=c.is_residual_qualified(49)) == Decimal("0")
    # 50 new accounts this year -> qualified -> 5% residual in month 13
    assert c.account_commission(mrr, 13, residual_qualified=c.is_residual_qualified(50)) == _dec(mrr) * Decimal("0.05")
    # Commission (months 1-12) is never gated by residual qualification
    assert c.account_commission(mrr, 1, residual_qualified=False) == _dec(mrr) * Decimal("0.20")
    assert c.account_commission(mrr, 12, residual_qualified=False) == _dec(mrr) * Decimal("0.20")
    assert c.is_residual_qualified(49) is False
    assert c.is_residual_qualified(50) is True


def test_no_clawback_independence():
    """A later year's disqualification cannot retroactively zero a prior
    qualified year's residual — each ledger month is computed independently
    from that month's own inputs."""
    mrr = 400
    year2_qualified_residual = c.account_commission(mrr, 15, residual_qualified=True)
    year3_unqualified_residual = c.account_commission(mrr, 27, residual_qualified=False)
    assert year2_qualified_residual == _dec(mrr) * Decimal("0.05")
    assert year3_unqualified_residual == Decimal("0")
    # Re-computing year 2 with its own (True) input is unaffected by year 3.
    assert c.account_commission(mrr, 15, residual_qualified=True) == _dec(mrr) * Decimal("0.05")


def test_milestone_bonuses_stacking():
    all_three = c.milestone_bonuses(10, 25, 100)
    assert all_three["total"] == 13500
    assert all_three["fast_start_earned"] and all_three["quarter_earned"] and all_three["year_earned"]

    only_fast_start = c.milestone_bonuses(10, 0, 0)
    assert only_fast_start["total"] == 1000

    only_quarter = c.milestone_bonuses(0, 25, 0)
    assert only_quarter["total"] == 2500

    only_year = c.milestone_bonuses(0, 0, 100)
    assert only_year["total"] == 10000

    none_earned = c.milestone_bonuses(9, 24, 99)
    assert none_earned["total"] == 0
    assert not (none_earned["fast_start_earned"] or none_earned["quarter_earned"] or none_earned["year_earned"])


def test_ambassador_deduction_and_onboarding_constants():
    ambassador = c.account_month_commission(400, 1, is_ambassador_deal=True)
    assert ambassador["ambassador_deduction"] == Decimal("250")
    assert ambassador["net"] == Decimal("0")

    non_ambassador = c.account_month_commission(400, 1, is_ambassador_deal=False)
    assert non_ambassador["net"] == Decimal("80")

    assert c.ONBOARDING_FEE == 300
    assert c.REP_ONBOARDING == 150
    assert c.COMPANY_ONBOARDING == 150
    assert c.AMBASSADOR_DEDUCTION == Decimal("250.00")


def test_100_site_mix():
    """25 starter / 50 growth / 25 pro, fully ramped."""
    mix = [100] * 25 + [400] * 50 + [1000] * 25
    year1_total = sum(c.account_year1_commission(mrr) for mrr in mix)
    residual_total = sum(c.account_residual_year(mrr) for mrr in mix)
    assert year1_total == Decimal("114000"), year1_total
    assert residual_total == Decimal("28500"), residual_total


def test_draw_off_by_default():
    assert c.DRAW_ENABLED is False
    assert c.draw_for(0) == Decimal("0")
    assert c.draw_for(100) == Decimal("0")
    assert c.draw_for(5000) == Decimal("0")


def test_account_month_commission_phase_labels():
    assert c.account_month_commission(400, 1)["phase"] == "commission"
    assert c.account_month_commission(400, 12)["phase"] == "commission"
    assert c.account_month_commission(400, 13, residual_qualified=True)["phase"] == "residual"
    assert c.account_month_commission(400, 60, residual_qualified=True)["phase"] == "residual"
    assert c.account_month_commission(400, 61)["phase"] == "expired"
    assert c.account_month_commission(400, 5, rep_employed=False)["phase"] == "unemployed"


def test_account_age_months():
    from datetime import date
    assert c.account_age_months(date(2026, 1, 1), date(2026, 1, 15)) == 1
    assert c.account_age_months(date(2026, 1, 1), date(2027, 1, 1)) == 13
    assert c.account_age_months(date(2026, 1, 1), date(2031, 1, 1)) == 61


def test_rep_month_summary_basic():
    clients = [
        {"mrr": 400, "account_month": 1, "is_new": True},
        {"mrr": 1000, "account_month": 13},
    ]
    # Not residual-qualified (ytd < 50): month-13 residual should be $0.
    summary = c.rep_month_summary(clients, new_accounts_ytd=10)
    assert summary["residual_qualified"] is False
    assert summary["commission_earned"] == Decimal("80")
    assert summary["residual_earned"] == Decimal("0")
    assert summary["onboarding_total"] == Decimal("150")
    assert summary["draw"] == Decimal("0")

    # Residual-qualified (ytd >= 50): month-13 account now earns 5%.
    summary_qualified = c.rep_month_summary(clients, new_accounts_ytd=50)
    assert summary_qualified["residual_qualified"] is True
    assert summary_qualified["residual_earned"] == Decimal("50")


def test_enterprise_constants():
    assert c.ENTERPRISE_RESIDUAL_GATE_ARR == 250000
    assert c.ENTERPRISE_ANNUAL_TARGET_ARR == 500000


def test_enterprise_residual_gate_boundary():
    assert c.is_residual_qualified_enterprise(249999) is False
    assert c.is_residual_qualified_enterprise(250000) is True
    # Decimal input works too.
    assert c.is_residual_qualified_enterprise(Decimal("249999.99")) is False
    assert c.is_residual_qualified_enterprise(Decimal("250000.00")) is True


def test_is_residual_qualified_for_track_routing():
    # quetrex routes to the ARR gate.
    assert c.is_residual_qualified_for_track("quetrex", 249999) is False
    assert c.is_residual_qualified_for_track("quetrex", 250000) is True
    # marketing51 (and any other/legacy value) routes to the account-count gate.
    assert c.is_residual_qualified_for_track("marketing51", 49) is False
    assert c.is_residual_qualified_for_track("marketing51", 50) is True


def test_account_commission_math_identical_across_tracks():
    """account_commission/account_month_commission take a resolved
    residual_qualified boolean and never branch on track themselves --
    confirm the math is bit-for-bit identical regardless of which track
    produced that boolean."""
    mrr = 400
    for track in ("marketing51", "quetrex"):
        metric_qualified = 50 if track == "marketing51" else 250000
        metric_unqualified = 49 if track == "marketing51" else 249999

        qualified = c.is_residual_qualified_for_track(track, metric_qualified)
        unqualified = c.is_residual_qualified_for_track(track, metric_unqualified)

        assert c.account_commission(mrr, 1, residual_qualified=qualified) == Decimal("80")
        assert c.account_commission(mrr, 13, residual_qualified=qualified) == Decimal("20")
        assert c.account_commission(mrr, 61, residual_qualified=qualified) == Decimal("0")

        assert c.account_commission(mrr, 13, residual_qualified=unqualified) == Decimal("0")


def test_calculate_kingdom_giving_and_founders_pool_unchanged():
    pool = c.calculate_founders_pool(Decimal("120000"))
    assert pool == Decimal("120000") * Decimal("0.50") / 12

    giving = c.calculate_kingdom_giving(
        gross_mrr=Decimal("10000"),
        founders_pool=Decimal("500"),
        rep_commissions=Decimal("2000"),
        operating_costs=Decimal("1000"),
        current_reserve=Decimal("0"),
    )
    assert giving["giving_layer1"] == 1000.0
    assert giving["total_kingdom_giving"] > 0


TESTS = [
    test_plan_mrr,
    test_year1_commission_vectors,
    test_residual_year_vectors,
    test_lifetime_vectors,
    test_account_commission_phases,
    test_employment_gate,
    test_residual_gate,
    test_no_clawback_independence,
    test_milestone_bonuses_stacking,
    test_ambassador_deduction_and_onboarding_constants,
    test_100_site_mix,
    test_draw_off_by_default,
    test_account_month_commission_phase_labels,
    test_account_age_months,
    test_rep_month_summary_basic,
    test_enterprise_constants,
    test_enterprise_residual_gate_boundary,
    test_is_residual_qualified_for_track_routing,
    test_account_commission_math_identical_across_tracks,
    test_calculate_kingdom_giving_and_founders_pool_unchanged,
]


def main():
    failures = 0
    for test in TESTS:
        name = test.__name__
        try:
            test()
        except AssertionError as e:
            failures += 1
            print(f"FAIL: {name} — {e}")
        except Exception as e:
            failures += 1
            print(f"FAIL: {name} — unexpected error: {e!r}")
        else:
            print(f"PASS: {name}")

    total = len(TESTS)
    passed = total - failures
    print(f"\n{passed}/{total} tests passed.")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
