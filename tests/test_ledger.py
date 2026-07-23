"""
Plain-assert unit tests for the commission-ledger writer's pure math
(ledger.py). No DB, no psycopg — ledger.py imports only commission +
datetime, so these run anywhere.

    python3 tests/test_ledger.py
"""
import os
import sys
from decimal import Decimal
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ledger
import commission as c


def _client(id=1, rep_id=1, mrr=400, subscription_start=None, is_ambassador_deal=False):
    return {
        "id": id,
        "rep_id": rep_id,
        "mrr": mrr,
        "subscription_start": subscription_start or date(2025, 1, 1),
        "is_ambassador_deal": is_ambassador_deal,
    }


def test_month1_growth_ambassador():
    # subscription_start == ledger_month -> account_month 1.
    client = _client(mrr=400, subscription_start=date(2026, 1, 1), is_ambassador_deal=True)
    row = ledger.compute_ledger_row(client, "active", 60, date(2026, 1, 1))
    assert row["commission_type"] == "commission"
    assert row["commission_amount"] == Decimal("80.00") or row["commission_amount"] == Decimal("80")
    assert row["ambassador_deduction"] == Decimal("250.00") or row["ambassador_deduction"] == Decimal("250")
    assert row["net_commission"] == Decimal("0")
    assert row["subscription_month"] == 1


def test_month1_growth_non_ambassador():
    client = _client(mrr=400, subscription_start=date(2026, 1, 1), is_ambassador_deal=False)
    row = ledger.compute_ledger_row(client, "active", 60, date(2026, 1, 1))
    assert row["commission_type"] == "commission"
    assert row["net_commission"] == Decimal("80")
    assert row["ambassador_deduction"] == Decimal("0")


def test_month13_residual_qualified():
    # account_age_months(2025-01-01, 2026-01-01) == 13.
    client = _client(mrr=400, subscription_start=date(2025, 1, 1))
    row = ledger.compute_ledger_row(client, "active", 50, date(2026, 1, 1))
    assert row["subscription_month"] == 13
    assert row["commission_type"] == "residual"
    assert row["net_commission"] == Decimal("20")  # 5% of 400


def test_month13_residual_not_qualified():
    client = _client(mrr=400, subscription_start=date(2025, 1, 1))
    row = ledger.compute_ledger_row(client, "active", 49, date(2026, 1, 1))
    assert row["subscription_month"] == 13
    assert row["commission_type"] == "residual"
    assert row["net_commission"] == Decimal("0")


def test_residual_gate_boundary_49_vs_50():
    # account_age_months(2022-01-01, 2026-01-01) == 49 -> residual phase.
    client = _client(mrr=1000, subscription_start=date(2022, 1, 1))
    row_49 = ledger.compute_ledger_row(client, "active", 49, date(2026, 1, 1))
    row_50 = ledger.compute_ledger_row(client, "active", 50, date(2026, 1, 1))
    assert row_49["subscription_month"] == 49
    assert row_49["net_commission"] == Decimal("0")
    assert row_50["net_commission"] == Decimal("50")  # 5% of 1000


def test_month61_expired():
    # account_age_months(2020-01-01, 2025-01-01) == 61 (5-year cap exceeded).
    client = _client(mrr=1000, subscription_start=date(2020, 1, 1))
    row = ledger.compute_ledger_row(client, "active", 100, date(2025, 1, 1))
    assert row["subscription_month"] == 61
    assert row["commission_type"] == "expired"
    assert row["net_commission"] == Decimal("0")


def test_rep_not_active_unemployed():
    client = _client(mrr=400, subscription_start=date(2026, 1, 1))
    for status in ("terminated", "on_leave", "inactive", None):
        row = ledger.compute_ledger_row(client, status, 100, date(2026, 1, 1))
        assert row["commission_type"] == "unemployed"
        assert row["net_commission"] == Decimal("0")


def test_net_never_negative():
    # No-clawback invariant: net = max(gross - deduction, 0), never < 0.
    for month1_start in (date(2026, 1, 1),):
        client = _client(mrr=100, subscription_start=month1_start, is_ambassador_deal=True)
        row = ledger.compute_ledger_row(client, "active", 0, month1_start)
        assert row["net_commission"] >= Decimal("0")
        # Starter ($100 mrr) gross is only $20 -- ambassador deduction of
        # $250 must not push net below zero.
        assert row["net_commission"] == Decimal("0")


def test_compute_ledger_row_is_deterministic():
    client = _client(mrr=400, subscription_start=date(2025, 6, 15), is_ambassador_deal=True)
    row1 = ledger.compute_ledger_row(client, "active", 55, date(2026, 6, 1))
    row2 = ledger.compute_ledger_row(client, "active", 55, date(2026, 6, 1))
    assert row1 == row2


def test_idempotency_contract_conflict_target():
    assert ledger.LEDGER_CONFLICT_TARGET == ("client_id", "ledger_month")


def test_idempotency_contract_update_columns_exclude_paid_state():
    protected = {"paid", "paid_date", "created_at"}
    for col in protected:
        assert col not in ledger.LEDGER_UPDATE_COLUMNS, col
    # also never re-key the row via the conflict target columns
    assert "ledger_month" not in ledger.LEDGER_UPDATE_COLUMNS
    assert "client_id" not in ledger.LEDGER_UPDATE_COLUMNS


def test_mid_month_start_recognized_in_start_month():
    # Billing is on the 1st (partial first month prorated), so a client that
    # starts mid-month (the 15th) earns their month-1 commission in that SAME
    # calendar month — not the following month. The ledger uses calendar-month
    # indexing (start month == month 1), not anniversary-day semantics.
    client = _client(mrr=400, subscription_start=date(2026, 1, 15))
    row_jan = ledger.compute_ledger_row(client, "active", 0, date(2026, 1, 1))
    row_feb = ledger.compute_ledger_row(client, "active", 0, date(2026, 2, 1))
    assert row_jan["subscription_month"] == 1          # start month IS month 1
    assert row_jan["net_commission"] == 80             # 20% of $400, month 1
    assert row_feb["subscription_month"] == 2
    # A ledger month before the client existed yields no commission.
    row_dec = ledger.compute_ledger_row(client, "active", 0, date(2025, 12, 1))
    assert row_dec["subscription_month"] == 0
    assert row_dec["net_commission"] == 0


def test_quetrex_residual_gated_by_arr_not_count():
    # month13 residual client, quetrex track: gate_metric is ARR booked YTD,
    # not an account count. 249999 -> not qualified -> $0; 250000 -> qualified.
    client = _client(mrr=400, subscription_start=date(2025, 1, 1))
    row_under = ledger.compute_ledger_row(client, "active", 249999, date(2026, 1, 1), track="quetrex")
    row_over = ledger.compute_ledger_row(client, "active", 250000, date(2026, 1, 1), track="quetrex")
    assert row_under["subscription_month"] == 13
    assert row_under["commission_type"] == "residual"
    assert row_under["net_commission"] == Decimal("0")
    assert row_over["net_commission"] == Decimal("20")  # 5% of 400


def test_quetrex_month1_commission_unaffected_by_gate():
    # Commission phase (months 1-12) is never gated, on either track.
    client = _client(mrr=1000, subscription_start=date(2026, 1, 1))
    row = ledger.compute_ledger_row(client, "active", 0, date(2026, 1, 1), track="quetrex")
    assert row["commission_type"] == "commission"
    assert row["net_commission"] == Decimal("200")  # 20% of 1000


def test_marketing51_track_default_matches_legacy_positional_call():
    # track defaults to "marketing51" -- confirms the account-count path
    # (49/50 boundary) is unchanged whether or not track is passed explicitly.
    client = _client(mrr=400, subscription_start=date(2025, 1, 1))
    row_legacy = ledger.compute_ledger_row(client, "active", 49, date(2026, 1, 1))
    row_explicit = ledger.compute_ledger_row(client, "active", 49, date(2026, 1, 1), track="marketing51")
    assert row_legacy == row_explicit
    assert row_legacy["net_commission"] == Decimal("0")

    row_qualified = ledger.compute_ledger_row(client, "active", 50, date(2026, 1, 1), track="marketing51")
    assert row_qualified["net_commission"] == Decimal("20")


def test_as_date_coerces_datetime():
    dt = datetime(2026, 3, 4, 12, 30)
    assert ledger._as_date(dt) == date(2026, 3, 4)
    d = date(2026, 3, 4)
    assert ledger._as_date(d) == d


TESTS = [
    test_month1_growth_ambassador,
    test_month1_growth_non_ambassador,
    test_month13_residual_qualified,
    test_month13_residual_not_qualified,
    test_residual_gate_boundary_49_vs_50,
    test_month61_expired,
    test_rep_not_active_unemployed,
    test_net_never_negative,
    test_compute_ledger_row_is_deterministic,
    test_idempotency_contract_conflict_target,
    test_idempotency_contract_update_columns_exclude_paid_state,
    test_mid_month_start_recognized_in_start_month,
    test_quetrex_residual_gated_by_arr_not_count,
    test_quetrex_month1_commission_unaffected_by_gate,
    test_marketing51_track_default_matches_legacy_positional_call,
    test_as_date_coerces_datetime,
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
