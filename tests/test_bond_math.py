"""
The bond maths against answers worked out by hand, independent of any book on disk.

The golden tests prove the refactor reproduces 2.8.0's numbers on one captured book; they skip the
moment the book changes. These do not depend on the book at all: each case is a textbook bond whose
price, yield, duration or day count can be checked on paper, so a regression in ``core.bonds`` fails
here whatever the database holds.
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import pytest

import core.bonds as bonds
from core.formatting import fmt_inr, fmt_inr_short, fmt_pct


@pytest.fixture
def today(monkeypatch):
    """Freeze ``date.today()`` inside core.bonds (it reads a module-global ``date`` on purpose)."""
    def _freeze(d: _dt.date):
        class _Frozen(_dt.date):
            @classmethod
            def today(cls):
                return d
        monkeypatch.setattr(bonds, "date", _Frozen)
        return d
    return _freeze


# ── day counts ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("start,end,conv,want", [
    # ISDA Act/Act: 61 days in 2003 (a 365-day year) + 121 days in 2004 (a 366-day year)
    ("2003-11-01", "2004-05-01", "Actual/Actual", 61 / 365 + 121 / 366),
    ("2024-01-01", "2025-01-01", "Actual/Actual", 1.0),
    ("2024-01-01", "2024-07-01", "Actual/365", 182 / 365),
    ("2024-01-01", "2024-07-01", "Actual/360", 182 / 360),
    ("2024-01-15", "2024-07-15", "30/360", 0.5),
    ("2024-01-31", "2024-03-31", "30/360", 60 / 360),     # both 31sts roll to 30
    ("2024-07-01", "2024-01-01", "Actual/365", 0.0),      # backwards never goes negative
])
def test_day_count_fraction(start, end, conv, want):
    assert bonds.day_count_fraction(start, end, conv) == pytest.approx(want, abs=1e-12)


# ── the coupon grid: every date measured from maturity ───────────────────────
def test_month_end_maturity_keeps_month_end_coupons():
    """A monthly bond maturing on the 31st pays on each month's last day, never stuck on the 30th."""
    s = bonds.generate_cashflow_schedule(1000, 0.10, "Monthly", "2027-01-31", as_of=_dt.date(2026, 6, 1))
    assert [str(c["date"]) for c in s] == [
        "2026-06-30", "2026-07-31", "2026-08-31", "2026-09-30", "2026-10-31",
        "2026-11-30", "2026-12-31", "2027-01-31"]


def test_february_does_not_pull_later_dates_back():
    """Semi-annual from 2030-08-31: Feb pays on the 28th/29th, every August on the 31st."""
    s = bonds.generate_cashflow_schedule(1000, 0.08, "Semi-Annual", "2030-08-31", as_of=_dt.date(2028, 1, 1))
    assert [str(c["date"]) for c in s] == [
        "2028-02-29", "2028-08-31", "2029-02-28", "2029-08-31", "2030-02-28", "2030-08-31"]


def test_prev_coupon_date_on_month_end_grid():
    assert bonds.prev_coupon_date("2027-01-31", "Monthly", _dt.date(2026, 7, 15)) == _dt.date(2026, 6, 30)
    assert bonds.prev_coupon_date("2027-01-31", "Monthly", _dt.date(2026, 8, 31)) == _dt.date(2026, 8, 31)
    assert bonds.prev_coupon_date("2027-01-31", "Monthly", _dt.date(2026, 9, 15)) == _dt.date(2026, 8, 31)


def test_amortizing_schedule_month_end_and_totals():
    s = bonds.generate_amortizing_schedule(1200, 0.12, "Monthly", "2027-01-31", 100, 1,
                                           as_of=_dt.date(2026, 1, 31))
    dates = [str(c["date"]) for c in s]
    assert "2026-05-31" in dates and "2026-05-30" not in dates
    assert sum(c["principal"] for c in s) == pytest.approx(1200)      # every rupee comes back once
    assert s[0]["coupon"] == pytest.approx(1200 * 0.12 / 12)        # first coupon on the full balance


# ── schedules ────────────────────────────────────────────────────────────────
def test_bullet_schedule_pays_coupons_and_face_once():
    s = bonds.generate_cashflow_schedule(1000, 0.08, "Annual", "2030-06-15", units=3, as_of=_dt.date(2025, 6, 15))
    assert len(s) == 5
    assert all(c["coupon"] == pytest.approx(240) for c in s)
    assert [c["principal"] for c in s] == [0, 0, 0, 0, 3000]


def test_matured_bond_projects_nothing():
    assert bonds.generate_amortizing_schedule(1000, 0.1, "Annual", "2020-01-01", 0, 0,
                                              as_of=_dt.date(2025, 1, 1)) == []


# ── yield to cost ────────────────────────────────────────────────────────────
def test_par_bond_bought_on_a_coupon_date_yields_its_coupon():
    y = bonds.calc_yield_to_cost(1000, 1000, 0.10, "2030-06-15", "Semi-Annual", "30/360",
                                 as_of=_dt.date(2025, 6, 15))
    assert y == pytest.approx(0.10, abs=1e-9)


def test_discount_bond_yield_matches_textbook_price():
    """5-year 8% annual bond priced at 10%: 80·a(5,10%) + 1000·v⁵ = 924.18."""
    price = sum(80 / 1.1 ** t for t in range(1, 6)) + 1000 / 1.1 ** 5
    assert price == pytest.approx(924.184, abs=1e-3)
    y = bonds.calc_yield_to_cost(1000, price, 0.08, "2030-06-15", "Annual", "30/360",
                                 as_of=_dt.date(2025, 6, 15))
    assert y == pytest.approx(0.10, abs=1e-9)


def test_premium_bond_yields_below_its_coupon():
    y = bonds.calc_yield_to_cost(1000, 1050, 0.09, "2029-03-01", "Quarterly", "30/360",
                                 as_of=_dt.date(2025, 3, 1))
    assert 0 < y < 0.09


def test_mid_period_purchase_pays_accrued_not_a_phantom_coupon():
    """Bought at par halfway through a period: the dirty price carries half a coupon, so the yield
    stays the coupon rate instead of gaining the half coupon the buyer did not earn."""
    y = bonds.calc_yield_to_cost(1000, 1000, 0.10, "2030-06-15", "Semi-Annual", "30/360",
                                 as_of=_dt.date(2025, 9, 15))
    assert y == pytest.approx(0.10, abs=2e-4)


def test_xirr_one_year_ten_percent():
    cfs = [(_dt.date(2025, 1, 1), -100.0), (_dt.date(2026, 1, 1), 110.0)]
    assert bonds._xirr(cfs, 1) == pytest.approx(0.10, abs=1e-9)
    # the same flows read as a nominal rate compounded twice a year
    assert bonds._xirr(cfs, 2) == pytest.approx(2 * (1.1 ** 0.5 - 1), abs=1e-9)


def test_xirr_needs_a_sign_change():
    assert bonds._xirr([(_dt.date(2025, 1, 1), 100.0), (_dt.date(2026, 1, 1), 110.0)]) == 0.0


def test_position_ytc_single_par_buy_is_the_coupon(today):
    today(_dt.date(2026, 1, 1))
    txns = pd.DataFrame([{"trade_date": "2025-06-15", "transaction_type": "Buy",
                          "units": 10.0, "price": 1000.0, "amount": 10000.0}])
    y = bonds.calc_position_yield_to_cost(txns, 0.10, "Annual", "2030-06-15", 1000.0)
    assert y == pytest.approx(0.10, abs=5e-4)


def test_position_ytc_of_matured_bond_is_na(today):
    today(_dt.date(2031, 1, 1))
    txns = pd.DataFrame([{"trade_date": "2025-06-15", "transaction_type": "Buy",
                          "units": 1.0, "price": 1000.0, "amount": 1000.0}])
    assert bonds.calc_position_yield_to_cost(txns, 0.10, "Annual", "2030-06-15", 1000.0) == 0.0


# ── duration ─────────────────────────────────────────────────────────────────
def test_macaulay_and_modified_duration_textbook(today):
    """5-year 8% annual at 10%: Macaulay 4.2814y, modified 4.2814 / 1.10 = 3.8922y."""
    today(_dt.date(2025, 6, 15))
    mac = bonds.calc_macaulay_duration(1000, 0.08, "Annual", "2030-06-15", 0.10, "30/360")
    assert mac == pytest.approx(4.2814, abs=1e-4)
    assert bonds.calc_modified_duration(mac, 0.10, "Annual") == pytest.approx(3.8922, abs=1e-4)


def test_zero_coupon_duration_is_its_maturity(today):
    today(_dt.date(2025, 6, 15))
    mac = bonds.calc_macaulay_duration(1000, 0.0, "Annual", "2030-06-15", 0.07, "30/360")
    assert mac == pytest.approx(5.0, abs=1e-9)


def test_duration_of_matured_bond_is_zero(today):
    today(_dt.date(2031, 1, 1))
    assert bonds.calc_macaulay_duration(1000, 0.08, "Annual", "2030-06-15", 0.10) == 0.0


# ── accrued interest ─────────────────────────────────────────────────────────
def test_accrued_at_half_a_period():
    a = bonds.accrued_at(1000, 0.10, "Semi-Annual", "2030-06-15", _dt.date(2025, 9, 15), "30/360")
    assert a == pytest.approx(25.0, abs=1e-9)


def test_accrued_is_zero_on_a_coupon_date():
    assert bonds.accrued_at(1000, 0.10, "Semi-Annual", "2030-06-15", _dt.date(2025, 12, 15), "30/360") == 0.0


# ── formatting ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("v,want", [
    (12345678.9, "₹1,23,45,678.90"), (999, "₹999.00"), (100000, "₹1,00,000.00"),
    (-2500.5, "-₹2,500.50"), ("bad", "₹0.00"),
])
def test_fmt_inr_indian_grouping(v, want):
    assert fmt_inr(v) == want


def test_fmt_short_and_pct():
    assert fmt_inr_short(25_000_000) == "₹2.50 Cr"
    assert fmt_inr_short(450_000) == "₹4.50 L"
    assert fmt_pct(0.0875) == "8.75%"


# ── the issuers' own conventions (3.5.0), reproduced from platform cashflow statements ────────
def test_actual_actual_counts_the_payment_year():
    """Indian NCD interest: actual days over the days in the year the coupon is PAID — Rs 2 lakh at 12%:
    31 days paid 4 Jan 2028 = 2,032.78 (31/366); 30 days paid 4 Dec 2027 = 1,972.60 (30/365);
    28 days paid 4 Mar 2029 on Rs 1 lakh = 920.55 (28/365)."""
    f = bonds.coupon_fraction
    assert 200000 * 0.12 * f(_dt.date(2027, 12, 4), _dt.date(2028, 1, 4), "Actual/Actual") == pytest.approx(2032.79, abs=0.01)
    assert 200000 * 0.12 * f(_dt.date(2027, 11, 4), _dt.date(2027, 12, 4), "Actual/Actual") == pytest.approx(1972.60, abs=0.01)
    assert 100000 * 0.12 * f(_dt.date(2029, 2, 4), _dt.date(2029, 3, 4), "Actual/Actual") == pytest.approx(920.55, abs=0.01)


def test_interest_day_and_the_broken_last_period():
    """Indel 24 Aug 2032 pays on the 1st and makes its last payment at maturity (1 Aug, then 24 Aug)."""
    s = bonds.generate_cashflow_schedule(1000, 0.115, "Monthly", "2032-08-24", units=500, as_of=_dt.date(2032, 5, 15),
                                         coupon_day=1, coupon_dc="Actual/Actual")
    assert [str(c["date"]) for c in s] == ["2032-06-01", "2032-07-01", "2032-08-01", "2032-08-24"]
    # statement: 1 Jul 2032 4,713.11 · 1 Aug 4,870.22 · 24 Aug 3,613.39 (leap year: /366)
    assert [round(c["coupon"], 2) for c in s[1:]] == [4713.11, 4870.22, 3613.39]


def test_month_end_interest_day_clips_to_short_months():
    s = bonds.generate_cashflow_schedule(100000, 0.125, "Monthly", "2030-03-12", units=8, as_of=_dt.date(2029, 12, 15),
                                         coupon_day=31, coupon_dc="Actual/Actual")
    assert [str(c["date"]) for c in s] == ["2029-12-31", "2030-01-31", "2030-02-28", "2030-03-12"]
    # statement (Tapir 12 Mar 2030, 8 bonds): 31 Jan 8,493.15 · 28 Feb 7,671.23 · 12 Mar 3,287.67
    assert [round(c["coupon"], 2) for c in s[1:]] == [8493.15, 7671.23, 3287.67]


def test_no_interest_before_issue():
    """Issued 31 Jul, pays on the 10th: the first coupon covers 31 Jul - 10 Aug, not 10 Jul - 10 Aug."""
    s = bonds.generate_cashflow_schedule(10000, 0.105, "Monthly", "2028-08-10", units=50, as_of=_dt.date(2026, 8, 1),
                                         coupon_dc="Actual/Actual", issue_date=_dt.date(2026, 7, 31))
    assert str(s[0]["date"]) == "2026-08-10" and round(s[0]["coupon"], 2) == round(500000 * 0.105 * 10 / 365, 2)


def test_each_lot_earns_coupons_only_while_held(today):
    """Two lots a month apart: the second earns nothing for the month before it was bought, and pays the
    accrued interest from the last coupon to its own date. The engine's flows equal the hand-built ones."""
    today(_dt.date(2026, 6, 1))
    txns = pd.DataFrame([
        {"trade_date": "2026-01-10", "transaction_type": "Buy", "units": 10.0, "price": 10000.0, "amount": 100000.0},
        {"trade_date": "2026-02-20", "transaction_type": "Buy", "units": 10.0, "price": 10000.0, "amount": 100000.0},
    ])
    cap = []
    real = bonds._xirr
    bonds._xirr = lambda cfs, f=1: (cap.extend(cfs), real(cfs, f))[1]
    try:
        bonds.calc_position_yield_to_cost(txns, 0.12, "Monthly", "2026-12-01", 10000.0, "Actual/Actual",
                                          coupon_dc="Actual/Actual")
    finally:
        bonds._xirr = real
    got = {}
    for d, a in cap:
        got[d] = round(got.get(d, 0) + a, 2)
    f = lambda a, b: bonds.coupon_fraction(a, b, "Actual/Actual")
    D = _dt.date
    assert got[D(2026, 2, 1)] == round(100000 * 0.12 * f(D(2026, 1, 1), D(2026, 2, 1)), 2)          # lot 1 only
    assert got[D(2026, 3, 1)] == round(200000 * 0.12 * f(D(2026, 2, 1), D(2026, 3, 1)), 2)          # both lots
    assert got[D(2026, 2, 20)] == round(-100000 - 100000 * 0.12 * f(D(2026, 2, 1), D(2026, 2, 20)), 2)  # lot 2 + its accrued
