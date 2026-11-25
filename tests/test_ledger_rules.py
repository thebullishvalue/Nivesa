"""
The rules every save keeps (3.6.0), through the real forms:

  · a purchase cannot be deleted (or moved) while repayments booked to its account depend on it;
  · an interest receipt or a principal repayment cannot be booked to an account holding none of the bond;
  · Edit Security writes the terms and the metadata in ONE transaction — a failure in the second leaves
    the first unwritten;
  · the face value is set by recorded repayments once there are any (the field is locked), and open
    otherwise;
  · a matured position whose redemption is listed under Repayments due is not listed again under Matured.
"""
from __future__ import annotations

import datetime as _dt
import sqlite3

import pandas as pd
import pytest

import core.db
import fixture_book
from core import schedule as sch
from test_app import _goto, apptest  # noqa: F401 — the suite's AppTest fixture

D = _dt.date
CEDAR = fixture_book._bid(3)      # HEMANG 6 · MANTHAN 10, repayments 2025-06-10 and 2026-06-10
DEODAR = fixture_book._bid(4)     # REKHA 50, bullet, two interest receipts


@pytest.fixture
def book(tmp_path, monkeypatch):
    db = fixture_book.build(tmp_path / "data")
    monkeypatch.setattr(core.db, "DB_FILE", str(db))
    core.db.db_init()
    sch.schedule_init()
    import streamlit as st
    st.cache_data.clear()
    yield str(db)
    st.cache_data.clear()


def _rows(db):
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT * FROM transactions ORDER BY transaction_id").fetchall(), \
            con.execute("SELECT * FROM securities ORDER BY bond_id").fetchall()
    finally:
        con.close()


def _md(at) -> str:
    return " ".join(m.value for m in at.markdown)


def _pick_txn(at, pred):
    box = next(s for s in at.selectbox if s.label == "Select Transaction")
    tid = core.db.db_query("SELECT transaction_id FROM transactions WHERE " + pred)["transaction_id"].iloc[0]
    box.select(next(o for o in box.options if o.endswith(f"| {tid[:8]}"))).run()
    return tid


# ── validate_ledger, directly ────────────────────────────────────────────────
def test_the_ledger_rules(book):
    con = sqlite3.connect(book)
    try:
        assert core.db.validate_ledger(CEDAR, con) is None
        con.execute("DELETE FROM transactions WHERE bond_id=? AND account='HEMANG' AND transaction_type='Buy'", (CEDAR,))
        assert "HEMANG" in core.db.validate_ledger(CEDAR, con) and "principal repayment" in core.db.validate_ledger(CEDAR, con)
        con.rollback()
        con.execute("UPDATE securities SET face_value=-5 WHERE bond_id=?", (CEDAR,))
        assert "below zero" in core.db.validate_ledger(CEDAR, con)
        con.rollback()
        con.execute("INSERT INTO transactions (transaction_id, bond_id, account, trade_date, transaction_type, units, "
                    "price, amount) VALUES ('x', ?, 'HIMA', '2026-01-01', 'Interest_Receipt', 0, 0, 100)", (DEODAR,))
        assert "HIMA" in core.db.validate_ledger(DEODAR, con) and "interest receipt" in core.db.validate_ledger(DEODAR, con)
    finally:
        con.close()


# ── through the forms ────────────────────────────────────────────────────────
def test_deleting_a_purchase_its_repayments_depend_on_is_rejected(book, apptest):
    before = _rows(book)
    at = apptest().run()
    _goto(at, "edit-transaction")
    _pick_txn(at, f"bond_id='{CEDAR}' AND account='HEMANG' AND transaction_type='Buy'")
    next(b for b in at.button if b.label == "Delete transaction").click().run()
    assert "Transaction deletion rejected. Account HEMANG would have a principal repayment on 10 Jun 2025 " \
           "without holding the bond." in _md(at)
    assert _rows(book) == before


def test_moving_a_purchase_after_its_repayments_is_rejected(book, apptest):
    before = _rows(book)
    at = apptest().run()
    _goto(at, "edit-transaction")
    _pick_txn(at, f"bond_id='{CEDAR}' AND account='HEMANG' AND transaction_type='Buy'")
    next(d for d in at.date_input if d.label == "Date").set_value(D(2026, 8, 1))
    next(b for b in at.button if b.label == "Update transaction").click().run()
    assert "Transaction update rejected. Account HEMANG would have a principal repayment" in _md(at)
    assert _rows(book) == before


def test_interest_for_an_account_holding_none_is_rejected(book, apptest):
    before = _rows(book)
    at = apptest().run()
    _goto(at, "record-transaction")
    box = next(s for s in at.selectbox if s.label == "Select Security")
    box.select(next(o for o in box.options if "Deodar" in o)).run()
    next(s for s in at.selectbox if s.label == "Transaction Type").select("Interest_Receipt").run()
    next(s for s in at.selectbox if s.label == "Account").select("HIMA").run()
    next(d for d in at.date_input if d.label == "Date").set_value(D(2026, 9, 5)).run()
    next(n for n in at.number_input if n.label == "Amount").set_value(3950.0)
    next(b for b in at.button if b.label == "Record transaction").click().run()
    assert "Transaction rejected. Account HIMA would have an interest receipt on 05 Sep 2026 without holding " \
           "the bond." in _md(at)
    assert _rows(book) == before


def test_edit_security_is_one_transaction(book, apptest):
    con = sqlite3.connect(book)
    con.execute("CREATE TRIGGER fail_meta BEFORE UPDATE ON security_metadata BEGIN SELECT RAISE(ABORT, 'disk full'); END")
    con.commit()
    con.close()
    at = apptest().run()
    _goto(at, "edit-security")
    box = next(s for s in at.selectbox if s.label == "Select Security")
    box.select(next(o for o in box.options if "Alder" in o)).run()
    next(t for t in at.text_input if t.label == "Issuer").input("Alder Finance Renamed")
    next(b for b in at.button if b.label == "Update security").click().run()
    assert "Update failed" in _md(at)
    assert core.db.db_query("SELECT issuer FROM securities WHERE bond_id=?", (fixture_book._bid(1),))["issuer"].iloc[0] \
        == "Alder Finance"                                    # the first UPDATE rolled back with the second


def test_face_value_is_locked_once_repayments_set_it(book, apptest):
    at = apptest().run()
    _goto(at, "edit-security")
    box = next(s for s in at.selectbox if s.label == "Select Security")
    box.select(next(o for o in box.options if "Cedar" in o)).run()
    assert next(n for n in at.number_input if n.label == "Face Value").disabled
    box = next(s for s in at.selectbox if s.label == "Select Security")
    box.select(next(o for o in box.options if "Alder" in o)).run()
    assert not next(n for n in at.number_input if n.label == "Face Value").disabled


# ── one warning per matured position ─────────────────────────────────────────
def test_a_matured_position_is_listed_once(book):
    import core.views as v
    from core.book import get_positions_dataframe
    df, _t = get_positions_dataframe()
    i = df.index[(df["bond_id"] == CEDAR) & (df["account"] == "MANTHAN")][0]
    df.loc[i, "maturity_date"] = pd.Timestamp("2026-10-01")          # pretend it matured unredeemed
    names = lambda ns: " ".join(n["body"] for n in ns if n["title"] == "Matured, not redeemed")
    assert "MANTHAN" in names(v.book_notices(df))
    assert "MANTHAN" not in names(v.book_notices(df, exclude={(CEDAR, "MANTHAN")}))
