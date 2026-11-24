"""
The contractual redemption schedule (``core.schedule``) and what it drives.

  · entry: lines in either date order and separator, equal instalments to the paisa, the checks against
    the bond's face, issue and maturity;
  · maths: a bond bought at par that repays in instalments yields its coupon; the projected stream pays
    each instalment on its date and only the remainder at maturity;
  · the book: a schedule replaces the inferred cadence for every position in the bond;
  · due, not recorded: a past instalment with no repayment for an account that held the bond then is
    listed per account, a recorded one is not, and one step records them all with ONE face step-down per
    date, through the chronology check;
  · the pages: the due list and its button on Record Transaction, the editor on Edit Security, the rail.
"""
from __future__ import annotations

import datetime as _dt
import shutil
import sqlite3

import pandas as pd
import pytest

import core.bonds as bonds
import core.db
import fixture_book
from core import schedule as sch
from test_app import _goto, apptest  # noqa: F401 — the suite's AppTest fixture

D = _dt.date
CEDAR = fixture_book._bid(3)     # monthly 11%, face 1000 → 800 after two recorded 100/unit repayments
ALDER = fixture_book._bid(1)     # bullet, held by REKHA 20 · HEMANG 10 · MANTHAN 5


@pytest.fixture
def book(tmp_path, monkeypatch):
    db = fixture_book.build(tmp_path / "data")
    monkeypatch.setattr(core.db, "DB_FILE", str(db))
    core.db.db_init()
    assert sch.schedule_init()
    import streamlit as st
    st.cache_data.clear()
    yield str(db)
    st.cache_data.clear()


@pytest.fixture
def frozen(monkeypatch):
    import core.book
    import core.views

    class _F(_dt.date):
        @classmethod
        def today(cls):
            return D(2026, 11, 24)
    for m in (bonds, core.book, core.views, sch):
        monkeypatch.setattr(m, "date", _F)
    return D(2026, 11, 24)


# ── entry ────────────────────────────────────────────────────────────────────
def test_parse_lines_reads_both_date_orders_and_separators():
    rows = sch.parse_lines("2027-06-10, 100\n# a comment\n\n10-12-2027\t₹150.50\n2027-09-10 100")
    assert rows == [(D(2027, 6, 10), 100.0), (D(2027, 9, 10), 100.0), (D(2027, 12, 10), 150.5)]
    with pytest.raises(ValueError, match="line 1"):
        sch.parse_lines("tomorrow, lots")


def test_equal_instalments_sum_to_the_paisa():
    rows = sch.equal_instalments(D(2025, 8, 6), 3, 9, 100000)
    assert len(rows) == 9 and rows[0] == (D(2025, 8, 6), 11111.11) and rows[-1][0] == D(2027, 8, 6)
    assert round(sum(a for _d, a in rows), 2) == 100000.00


def test_checks_against_the_terms():
    face, issue, mat = 10000.0, D(2025, 1, 1), D(2027, 1, 1)
    ok = [(D(2026, 1, 1), 5000.0), (D(2027, 1, 1), 5000.0)]
    assert sch.check(ok, face=face, issue=issue, maturity=mat) == ([], [])
    errs, _w = sch.check([(D(2027, 6, 1), 10000.0)], face=face, issue=issue, maturity=mat)
    assert any("after maturity" in e for e in errs)
    errs, _w = sch.check([(D(2026, 1, 1), 6000.0), (D(2026, 6, 1), 6000.0)], face=face, issue=issue, maturity=mat)
    assert any("more than the face" in e for e in errs)
    errs, w = sch.check([(D(2026, 1, 1), 2500.0)], face=face, issue=issue, maturity=mat)
    assert not errs and "repaid at maturity" in w[0]


# ── maths ────────────────────────────────────────────────────────────────────
def test_amortizing_bond_at_par_yields_its_coupon(monkeypatch):
    class _F(_dt.date):
        @classmethod
        def today(cls):
            return D(2025, 1, 15)
    monkeypatch.setattr(bonds, "date", _F)
    txns = pd.DataFrame([{"trade_date": "2025-01-15", "transaction_type": "Buy", "units": 10.0, "price": 10000.0,
                          "amount": 100000.0}])
    plan = [(d, a * 10) for d, a in sch.equal_instalments(D(2025, 4, 15), 3, 8, 10000.0)]
    y = bonds.calc_position_yield_to_cost(txns, 0.12, "Quarterly", "2027-01-15", 10000.0, "Actual/365",
                                          future_principal=plan)
    # exactly the IRR of the flows built by hand (coupon on the balance before each instalment)…
    flows, bal = [(D(2025, 1, 15), -100000.0)], 100000.0
    for d, a in plan:
        flows.append((d, bal * 0.03 + a))
        bal -= a
    assert y == pytest.approx(bonds._xirr(flows, 4), abs=1e-12)
    # …which is the coupon, give or take the calendar (quarters of 90-92 days against a flat quarterly coupon)
    assert y == pytest.approx(0.12, abs=5e-4)
    # without the schedule the same position is a 2-year bullet: same yield, much longer life
    assert bonds.calc_position_yield_to_cost(txns, 0.12, "Quarterly", "2027-01-15", 10000.0) == pytest.approx(0.12, abs=2e-4)


def test_projection_pays_each_instalment_then_the_rest():
    s = bonds.generate_amortizing_schedule(3000, 0.12, "Monthly", "2027-06-10", 0, 0, as_of=D(2026, 11, 24),
                                           principal_plan=[(D(2027, 1, 10), 1000), (D(2027, 3, 10), 1000)])
    prin = {c["date"]: c["principal"] for c in s if c["principal"]}
    assert prin == {D(2027, 1, 10): 1000, D(2027, 3, 10): 1000, D(2027, 6, 10): 1000}
    assert next(c for c in s if c["date"] == D(2027, 2, 10))["coupon"] == pytest.approx(2000 * 0.01)


# ── the book ─────────────────────────────────────────────────────────────────
def test_schedule_replaces_the_inferred_cadence(book, frozen):
    from core.book import get_positions_dataframe
    from core.views import cashflow_projection
    before, _ = get_positions_dataframe()
    sch.replace_schedule(CEDAR, [(D(2025, 6, 10), 100), (D(2026, 6, 10), 100), (D(2027, 6, 10), 200),
                                 (D(2028, 6, 10), 200), (D(2028, 12, 10), 400)], source="test")
    df, _ = get_positions_dataframe()
    m = df[(df["bond_id"] == CEDAR) & (df["account"] == "MANTHAN")].iloc[0]
    assert m["has_schedule"] and m["principal_plan"] == [(D(2027, 6, 10), 2000), (D(2028, 6, 10), 2000),
                                                         (D(2028, 12, 10), 4000)]
    cdf, _mcf, has_amort = cashflow_projection(df)
    rows = cdf[(cdf["issuer"] == "Cedar Housing") & (cdf["account"] == "MANTHAN") & (cdf["principal"] > 0)]
    assert dict(zip(rows["date"].dt.date, rows["principal"])) == {D(2027, 6, 10): 2000, D(2028, 6, 10): 2000,
                                                                  D(2028, 12, 10): 4000}
    assert has_amort
    b = before[(before["bond_id"] == CEDAR) & (before["account"] == "MANTHAN")].iloc[0]
    assert m["macaulay_duration"] != pytest.approx(b["macaulay_duration"])   # a different stream, a different life
    other = df[df["bond_id"] == ALDER]
    assert other["principal_plan"].isna().all() and not other["has_schedule"].any()


# ── due, not recorded ────────────────────────────────────────────────────────
def test_due_lists_each_holding_account_once_and_skips_recorded(book):
    # 2025-06-10 and 2026-06-10 are recorded in the sample book; 2026-09-10 is not
    sch.replace_schedule(CEDAR, [(D(2025, 6, 10), 100), (D(2026, 6, 10), 100), (D(2026, 9, 10), 100),
                                 (D(2027, 6, 10), 100)])
    due = sch.due_unrecorded(D(2026, 11, 24))
    assert sorted(zip(due["account"], due["units"], due["amount"])) == [("HEMANG", 6.0, 600.0), ("MANTHAN", 10.0, 1000.0)]
    assert set(due["due_date"]) == {D(2026, 9, 10)}
    # a holder who bought after the date is not due anything for it
    sch.replace_schedule(ALDER, [(D(2024, 5, 15), 100)])
    due = sch.due_unrecorded(D(2026, 11, 24))
    assert list(due[due["bond_id"] == ALDER]["account"]) == ["REKHA"]       # HEMANG bought in June, MANTHAN in 2025


def test_record_due_steps_face_once_per_date_and_clears_the_list(book):
    sch.replace_schedule(CEDAR, [(D(2025, 6, 10), 100), (D(2026, 6, 10), 100), (D(2026, 9, 10), 100),
                                 (D(2026, 10, 10), 100)])
    due = sch.due_unrecorded(D(2026, 11, 24))
    assert len(due) == 4
    ok, msg = sch.record_due(due)
    assert ok and msg == "4 repayments recorded"
    con = sqlite3.connect(book)
    assert con.execute("SELECT face_value FROM securities WHERE bond_id=?", (CEDAR,)).fetchone()[0] == pytest.approx(600)
    owners = con.execute("SELECT trade_date, SUM(owns_face_adj) FROM transactions WHERE bond_id=? AND "
                         "transaction_type='Principal_Repayment' GROUP BY trade_date", (CEDAR,)).fetchall()
    assert all(n == 1 for _d, n in owners) and len(owners) == 4
    con.close()
    assert sch.due_unrecorded(D(2026, 11, 24)).empty
    assert sch.original_face(CEDAR) == pytest.approx(1000)


def test_schedule_changes_are_audited(book):
    from core.audit import audit_entries, audit_init
    assert audit_init()
    sch.replace_schedule(CEDAR, [(D(2027, 6, 10), 100)])
    log = audit_entries()
    assert "redemption_schedule" in set(log["table_name"])


def test_a_book_without_the_table_reads_as_no_schedules(tmp_path, monkeypatch):
    db = fixture_book.build(tmp_path / "old")
    monkeypatch.setattr(core.db, "DB_FILE", str(db))
    assert sch.schedules() == {} and sch.due_unrecorded().empty and sch.schedule_frame(CEDAR).empty


# ── the pages ────────────────────────────────────────────────────────────────
@pytest.fixture
def app_book(tmp_path, monkeypatch):
    """The app on its own copy of the sample book, with one instalment of Cedar due and unrecorded."""
    db = fixture_book.build(tmp_path / "data")
    monkeypatch.setattr(core.db, "DB_FILE", str(db))
    core.db.db_init()
    sch.schedule_init()
    sch.replace_schedule(CEDAR, [(D(2025, 6, 10), 100), (D(2026, 6, 10), 100), (D(2026, 9, 10), 100),
                                 (D(2028, 12, 10), 700)], source="test")
    import streamlit as st
    st.cache_data.clear()
    yield str(db)
    st.cache_data.clear()


def test_rail_and_record_page_list_the_due_instalment_and_record_it(app_book, apptest):
    at = apptest().run()
    _goto(at, "record-transaction")
    md = " ".join(m.value for m in at.markdown)
    assert "Repayments due" in md and "Scheduled repayments not recorded" in md
    assert not at.exception
    btn = next(b for b in at.button if b.label == "Record repayments")
    btn.click().run()
    assert not at.exception
    md = " ".join(m.value for m in at.markdown)
    assert "2 repayments recorded" in md and "Scheduled repayments not recorded" not in md
    assert sch.due_unrecorded().empty


def test_edit_security_saves_a_schedule_from_lines(app_book, apptest):
    at = apptest().run()
    _goto(at, "edit-security")
    box = next(s for s in at.selectbox if s.label == "Select Security")
    box.select(next(o for o in box.options if "Alder" in o)).run()
    assert not at.exception
    ta = next(t for t in at.text_area if t.label.startswith("Instalments"))
    ta.input("2027-03-15, 500\n2028-03-15, 500")
    next(b for b in at.button if b.label == "Save schedule").click().run()
    assert not at.exception
    assert sch.schedules()[ALDER] == [(D(2027, 3, 15), 500.0), (D(2028, 3, 15), 500.0)]
    md = " ".join(m.value for m in at.markdown)
    assert "Repayment schedule saved for Alder Finance: 2 instalments" in md
    assert "REDEMPTION SCHEDULE · 2 instalments · ₹1,000.00 of ₹1,000.00 per bond" in md


def test_edit_security_rejects_a_schedule_past_maturity(app_book, apptest):
    at = apptest().run()
    _goto(at, "edit-security")
    box = next(s for s in at.selectbox if s.label == "Select Security")
    box.select(next(o for o in box.options if "Alder" in o)).run()
    next(t for t in at.text_area if t.label.startswith("Instalments")).input("2030-01-01, 1000")
    next(b for b in at.button if b.label == "Save schedule").click().run()
    assert "after maturity" in " ".join(m.value for m in at.markdown)
    assert ALDER not in sch.schedules()
