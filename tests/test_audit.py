"""
The audit trail and the sign-in gate.

  · every insert, update and delete on the three book tables leaves one ``audit_log`` row with the row
    as it was and as it became; an UPDATE that changes nothing leaves none;
  · the trail refuses UPDATE and DELETE;
  · ``audit_init`` is idempotent and picks up a column added to a tracked table;
  · with a password set the app shows only the sign-in form until the right password is given.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

import core.db as db
from core.audit import audit_entries, audit_init


@pytest.fixture
def book(tmp_path, monkeypatch):
    path = str(tmp_path / "portfolio.db")
    monkeypatch.setattr(db, "DB_FILE", path)
    db.db_init()
    assert audit_init()
    con = sqlite3.connect(path)
    yield con
    con.close()


def _sec(con, bid="B1", fv=1000.0):
    con.execute("INSERT INTO securities (bond_id, issuer, isin, maturity_date, frequency, coupon_rate, face_value) VALUES (?, 'Issuer & Co', ?, '2030-06-15', 'Annual', 0.1, ?)",
                (bid, f"INE{bid}", fv))
    con.commit()


def test_insert_update_delete_are_recorded(book):
    _sec(book)
    book.execute("UPDATE securities SET face_value=900 WHERE bond_id='B1'")
    book.execute("INSERT INTO transactions (transaction_id, bond_id, account, trade_date, transaction_type, "
                 "units, price, amount) VALUES ('T1', 'B1', 'REKHA', '2025-01-01', 'Buy', 5, 1000, 5000)")
    book.execute("DELETE FROM transactions WHERE transaction_id='T1'")
    book.commit()
    log = audit_entries().iloc[::-1]
    assert list(zip(log["table_name"], log["action"], log["row_id"])) == [
        ("securities", "INSERT", "B1"), ("securities", "UPDATE", "B1"),
        ("transactions", "INSERT", "T1"), ("transactions", "DELETE", "T1")]
    upd = log.iloc[1]
    assert json.loads(upd["old_row"])["face_value"] == 1000 and json.loads(upd["new_row"])["face_value"] == 900
    assert json.loads(log.iloc[3]["old_row"])["amount"] == 5000
    assert log["changed_at"].str.match(r"\d{4}-\d\d-\d\dT").all()


def test_no_op_update_is_not_a_change(book):
    _sec(book)
    book.execute("UPDATE securities SET face_value=face_value WHERE bond_id='B1'")
    book.commit()
    assert len(audit_entries()) == 1


def test_metadata_changes_are_recorded(book):
    _sec(book)
    book.execute("INSERT INTO security_metadata (bond_id) VALUES ('B1')")
    book.execute("UPDATE security_metadata SET credit_rating='AA' WHERE bond_id='B1'")
    book.commit()
    assert list(audit_entries()["table_name"])[:2] == ["security_metadata", "security_metadata"]


def test_trail_is_append_only(book):
    _sec(book)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        book.execute("UPDATE audit_log SET action='DELETE'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        book.execute("DELETE FROM audit_log")


def test_init_is_idempotent_and_follows_new_columns(book):
    assert audit_init() and audit_init()
    book.execute("ALTER TABLE securities ADD COLUMN extra TEXT")
    book.commit()
    assert audit_init()
    _sec(book)
    assert "extra" in json.loads(audit_entries().iloc[0]["new_row"])


def test_a_rolled_back_write_leaves_no_entry(book):
    _sec(book)
    try:
        with book:
            book.execute("UPDATE securities SET face_value=1 WHERE bond_id='B1'")
            raise RuntimeError
    except RuntimeError:
        pass
    assert len(audit_entries()) == 1


# ── sign-in ──────────────────────────────────────────────────────────────────
def test_password_gates_the_app(monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("NIVESA_PASSWORD", "correct horse")
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    assert not at.exception
    assert [t.label for t in at.text_input] == ["Password"]
    assert not any("Capital Allocation" in m.value for m in at.markdown)

    at.text_input[0].input("wrong")
    at.button[0].click().run()
    assert any("not right" in m.value for m in at.markdown)
    assert [t.label for t in at.text_input] == ["Password"]

    at.text_input[0].input("correct horse")
    at.button[0].click().run()
    assert not at.exception
    assert not any(t.label == "Password" for t in at.text_input)
    assert any(b.label == "Sign out" for b in at.button)


def test_open_app_says_it_is_open(monkeypatch):
    from ui import auth
    monkeypatch.delenv("NIVESA_PASSWORD", raising=False)
    monkeypatch.setattr(auth, "configured_password", lambda: None)
    assert auth.open_notice()[0]["title"] == "Open"
    monkeypatch.setattr(auth, "configured_password", lambda: "x")
    assert auth.open_notice() == []
