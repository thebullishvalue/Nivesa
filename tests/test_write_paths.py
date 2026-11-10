"""
The write paths are unchanged: every operation that writes to the book is driven, with identical inputs,
through the ORIGINAL 2.8.0 app (``tests/golden/app_2_8_0.py``) and through the 3.0 app, each on its own
fresh copy of ``data/``, both through Streamlit's AppTest — and the two databases must end identical, row
for row, in every table, with the same outcome on screen.

  · Operations: add security · edit security · record Buy, Sell, Interest_Receipt, Principal_Repayment
    (including the pro-rata repayment whose face step-down is claimed once, and the fat-finger price
    confirmation) · edit transaction (a buy, a repayment re-priced in place and one moved to another
    date) · delete transaction (a buy, a repayment that owns its face step-down) — and the rejections the
    original makes: missing fields, a duplicate ISIN, a past maturity, an issue date after maturity, a
    date after maturity, an unconfirmed off-par price, too few units, a repayment above outstanding face,
    a type change, and the chronology check that rolls back a sale or a deletion that would leave an
    account short.
  · The original is reached the way its user reached it — the sidebar "Navigation" selectbox; the new
    app by page switching (``_page_hash``), with the segmented-control shim ``tests/test_app.py`` uses.
  · The date is frozen to 2026-11-10 in both (the original's own ``date`` / ``datetime`` names; the 3.0
    modules' ``date``; Streamlit's date-input "today"). Generated ids are made deterministic in both
    (the original's ``uuid`` name; the 3.0 forms' ``uuid``), so new rows compare exactly; any id still
    unknown to the base book is normalised to its order of appearance. The tables hold no timestamps.
  · Outcome = what the final script run leaves on screen (a successful submit reruns the script; the
    elements the first run drew and the rerun did not are dropped, as a browser drops them): the success
    message (the original's toast; the new notice rail's "Saved" row), the rejection message
    (``st.error``; the rail's "Not saved" row) and the cautions (``st.warning``; the rail's "Check" row),
    markdown bold markers dropped — and a rejected step must leave the database untouched, an accepted
    one must change it.

Scenarios are chosen from the book by query (never by name: the book is private), so the file names no
holding. Nothing here touches the tracked ``data/``.
"""
from __future__ import annotations

import atexit
import datetime as _dt
import html
import importlib
import re
import shutil
import sqlite3
import sys
import tempfile
import types
import uuid as _uuid_mod
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from capture_golden import AS_OF, FrozenDate, FrozenDatetime
from core.config import ACCOUNTS

REPO = Path(__file__).resolve().parents[1]
ORIGINAL = REPO / "tests" / "golden" / "app_2_8_0.py"
APP = REPO / "app.py"
TODAY = AS_OF
D = _dt.date

# ── the harness module both apps draw their clock and ids from ───────────────
_H = types.ModuleType("_nivesa_harness")
_H.FrozenDate, _H.FrozenDatetime = FrozenDate, FrozenDatetime
_H.n = 0


def _uuid4():
    """Deterministic ids, distinct in their first 8 characters (the Edit Transaction picker shows those)."""
    _H.n += 1
    return f"{_H.n:08x}-feed-4000-8000-{_H.n:012x}"


_H.uuid4 = _uuid4
sys.modules["_nivesa_harness"] = _H

#: The original, executed as Streamlit executes it, with exactly two names rebound after their imports:
#: its clock (``date``, ``datetime``) and its id source (``uuid``). Nothing else is touched.
_ORIGINAL_SCRIPT = f'''
import _nivesa_harness as _H
_src = open({str(ORIGINAL)!r}, encoding="utf-8").read()
_clock, _ids = "from datetime import datetime, date, timedelta\\n", "import uuid\\n"
assert _src.count(_clock) == 1 and _src.count(_ids) == 1
_src = _src.replace(_clock, _clock + "import _nivesa_harness as _H; date, datetime = _H.FrozenDate, _H.FrozenDatetime\\n")
_src = _src.replace(_ids, _ids + "uuid = _H\\n")
exec(compile(_src, {str(ORIGINAL)!r}, "exec"), {{"__name__": "__main__", "__file__": {str(ORIGINAL)!r}}})
'''

#: Where each operation lives: (original "Navigation" option, new url path).
PAGES = {"add": ("Add Security", "add-security"), "edit_sec": ("Edit Security", "edit-security"),
         "record": ("Record Transaction", "record-transaction"), "edit_txn": ("Edit Transaction", "edit-transaction")}
#: Each submit button: (original label, new label).
SUBMIT = {"add": ("ADD SECURITY", "Add security"), "edit_sec": ("UPDATE SECURITY", "Update security"),
          "record": ("RECORD TRANSACTION", "Record transaction"), "update": ("UPDATE", "Update transaction"),
          "delete": ("DELETE", "Delete transaction")}
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_NOTICE = re.compile(r'<div class="notice (\w+)"><div class="n-title">(.*?)</div><div class="n-body">(.*?)</div></div>',
                     re.S)


def _plain(msg) -> str:
    return _BOLD.sub(r"\1", str(msg)).replace("`", "").strip()


# ── scenarios ────────────────────────────────────────────────────────────────
@dataclass
class Step:
    op: str                                   # add · edit_sec · record · edit_txn
    submit: str                               # a SUBMIT key
    expect: str                               # "ok" | "reject"
    message: str = ""                         # a substring of the expected message
    pick: object = None                       # picker value, or a callable(options) -> value
    pre: dict = field(default_factory=dict)   # widgets outside the form: {(kind, label): value}
    form: dict = field(default_factory=dict)  # widgets inside the form
    check: tuple = ()                         # checkbox labels to tick


@dataclass
class Case:
    name: str
    steps: list


def _q(db: str, sql: str, params=()):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def _facts(db: str) -> dict:
    """The book's shape, by query: which positions exist to buy, sell, repay, edit and delete."""
    today = TODAY.isoformat()
    held = _q(db, """
        SELECT s.bond_id, s.issuer, s.isin, t.account, SUM(t.units) AS u, s.face_value, s.maturity_date,
               MIN(t.trade_date) AS first_buy
        FROM transactions t JOIN securities s ON s.bond_id = t.bond_id
        WHERE t.transaction_type IN ('Buy', 'Sell') AND s.maturity_date > ?
        GROUP BY s.bond_id, t.account HAVING u >= 2 ORDER BY s.bond_id, t.account""", (today,))
    assert held, "the book holds no live position — these scenarios need one"
    by_bond: dict = {}
    for h in held:
        by_bond.setdefault(h[0], []).append(h)
    multi = next(v for v in by_bond.values() if len(v) >= 2)
    matured = _q(db, "SELECT bond_id, issuer, isin, maturity_date FROM securities WHERE maturity_date < ? "
                     "ORDER BY bond_id", (today,))
    buys = _q(db, """
        SELECT t.transaction_id, t.bond_id, t.account, t.trade_date, t.units, t.price FROM transactions t
        JOIN securities s ON s.bond_id = t.bond_id
        WHERE t.transaction_type = 'Buy' AND s.maturity_date > ? AND t.price BETWEEN s.face_value * 0.6
              AND s.face_value * 1.4 ORDER BY t.transaction_id""", (today,))
    prs = _q(db, """
        SELECT t.transaction_id, t.bond_id, t.account, t.trade_date, t.amount FROM transactions t
        WHERE t.transaction_type = 'Principal_Repayment' AND t.owns_face_adj = 1 ORDER BY t.transaction_id""")
    any_sec = _q(db, "SELECT bond_id, issuer, isin, maturity_date, face_value FROM securities ORDER BY bond_id")
    buys_of: dict = {}
    for tid, b, a in _q(db, "SELECT transaction_id, bond_id, account FROM transactions WHERE transaction_type = 'Buy' "
                            "ORDER BY trade_date, transaction_id"):
        buys_of.setdefault((b, a), []).append(tid)
    return {"held": held, "multi": multi, "matured": matured, "buys": buys, "prs": prs, "secs": any_sec,
            "buys_of": buys_of}


def _sec_label(issuer, isin) -> str:
    return f"{issuer} — {isin}"


def _txn_pick(tid: str):
    return lambda options: next(o for o in options if o.endswith(f"| {tid[:8]}"))


def _cases(f: dict) -> list[Case]:
    held = f["held"][0]
    bid, issuer, isin, acct, units, face, _maturity, first_buy = held
    sec = _sec_label(issuer, isin)
    units = int(units)
    m1, m2 = f["multi"][0], f["multi"][1]
    msec = _sec_label(m1[1], m1[2])
    sec0 = f["secs"][0]
    mat0 = D.fromisoformat(sec0[3])
    buy = f["buys"][0]
    pr = f["prs"][0] if f["prs"] else None
    other = next(a for a in ACCOUNTS if a != acct)
    # Ids restart at 1 for each app in each case, so the first entry a case records is this one in both.
    new_tid = f"{1:08x}-feed-4000-8000-{1:012x}"
    old_sec = _sec_label(f["matured"][0][1], f["matured"][0][2]) if f["matured"] else None

    def rec(ttype, account, when, *, expect, message="", form=None, check=(), security=sec):
        return Step("record", "record", expect, message, pick=security,
                    pre={("selectbox", "Transaction Type"): ttype, ("selectbox", "Account"): account,
                         ("date_input", "Date"): when},
                    form=form or {}, check=check)

    add_form = {("text_input", "Issuer Name"): "Harness Test Issuer", ("text_input", "ISIN"): "INHARNESS0001",
                ("date_input", "Maturity Date"): D(2031, 3, 31), ("selectbox", "Coupon Frequency"): "Quarterly",
                ("number_input", "Coupon Rate (%)"): 9.25, ("number_input", "Face Value (per unit)"): 1000.0,
                ("selectbox", "Bond Type"): "Corporate Bond", ("selectbox", "Credit Rating"): "AA",
                ("text_input", "Sector"): "Industrials", ("selectbox", "Listing"): "NSE",
                ("date_input", "Issue Date"): D(2026, 1, 15), ("selectbox", "Day Count"): "30/360",
                ("text_area", "Notes"): "write-path harness"}
    new_sec = _sec_label(add_form[("text_input", "Issuer Name")], add_form[("text_input", "ISIN")])
    edit_form = {("text_input", "Issuer"): "Harness Renamed Issuer", ("selectbox", "Frequency"): "Quarterly",
                 ("number_input", "Coupon (%)"): 11.11, ("selectbox", "Bond Type"): "Corporate Bond",
                 ("selectbox", "Credit Rating"): "A+", ("text_input", "Sector"): "Infrastructure",
                 ("selectbox", "Listing"): "BSE", ("date_input", "Issue Date"): D(2020, 1, 1),
                 ("selectbox", "Day Count"): "Actual/360", ("text_area", "Notes"): "edited by the harness"}
    sell_all = rec("Sell", acct, TODAY, expect="ok", message="Sell recorded!",
                   form={("number_input", "Units"): units, ("number_input", "Price"): float(face)})

    cases = [
        # ── add security ──
        Case("add-security", [Step("add", "add", "ok", "added!", form=add_form)]),
        Case("add-security-duplicate-isin", [Step("add", "add", "reject", "already exists in the securities master",
                                                  form={**add_form, ("text_input", "ISIN"): isin})]),
        Case("add-security-past-maturity", [Step("add", "add", "reject", "Maturity date must be in the future.",
                                                 form={**add_form, ("date_input", "Maturity Date"): TODAY})]),
        Case("add-security-missing-issuer", [Step("add", "add", "reject", "Issuer and ISIN are required.",
                                                  form={**add_form, ("text_input", "Issuer Name"): ""})]),
        # ── edit security ──
        Case("edit-security", [Step("edit_sec", "edit_sec", "ok", "Harness Renamed Issuer updated!",
                                    pick=_sec_label(sec0[1], sec0[2]), form=edit_form)]),
        Case("edit-security-issue-after-maturity", [Step(
            "edit_sec", "edit_sec", "reject", "Maturity date must be after the issue date.",
            pick=_sec_label(sec0[1], sec0[2]),
            form={**edit_form, ("date_input", "Issue Date"): mat0 + _dt.timedelta(days=1)})]),
        Case("edit-security-missing-issuer", [Step("edit_sec", "edit_sec", "reject", "Issuer required.",
                                                   pick=_sec_label(sec0[1], sec0[2]),
                                                   form={**edit_form, ("text_input", "Issuer"): ""})]),
        Case("add-security-then-buy", [
            Step("add", "add", "ok", "added!", form=add_form),
            rec("Buy", acct, TODAY, expect="ok", message="Buy recorded!", security=new_sec,
                form={("number_input", "Units"): 12, ("number_input", "Price"): 1000.0}),
        ]),
        Case("add-security-then-buy-before-issue", [
            Step("add", "add", "ok", "added!", form=add_form),
            rec("Buy", acct, D(2026, 1, 14), expect="reject", message="cannot be before the bond's issue date",
                security=new_sec, form={("number_input", "Units"): 12, ("number_input", "Price"): 1000.0}),
        ]),
        # ── record: Buy ──
        Case("record-buy", [rec("Buy", other, TODAY, expect="ok", message="Buy recorded!",
                                form={("number_input", "Units"): 7, ("number_input", "Price"): float(face)})]),
        Case("record-buy-off-par-confirmed", [
            rec("Buy", acct, D(2026, 11, 2), expect="reject", message="Please check the confirmation box",
                form={("number_input", "Units"): 3, ("number_input", "Price"): float(face) * 2.5}),
            rec("Buy", acct, D(2026, 11, 2), expect="ok", message="Buy recorded!",
                form={("number_input", "Units"): 3, ("number_input", "Price"): float(face) * 2.5},
                check=("Confirm this price deviation is correct",)),
        ]),
        Case("record-buy-after-maturity", [rec("Buy", acct, TODAY, expect="reject",
                                               message="cannot be after the bond's maturity date",
                                               security=old_sec,
                                               form={("number_input", "Units"): 1,
                                                     ("number_input", "Price"): 1000.0})]),
        # ── record: Sell ──
        Case("record-sell", [rec("Sell", acct, TODAY, expect="ok", message="Sell recorded!",
                                 form={("number_input", "Units"): 1, ("number_input", "Price"): float(face)})]),
        Case("record-sell-insufficient-units", [rec("Sell", acct, TODAY, expect="reject",
                                                    message="Insufficient units",
                                                    form={("number_input", "Units"): units + 5,
                                                          ("number_input", "Price"): float(face)})]),
        Case("record-sell-before-first-buy-rolls-back", [rec(
            "Sell", acct, D.fromisoformat(first_buy) - _dt.timedelta(days=1), expect="reject",
            message="to have negative holdings on",
            form={("number_input", "Units"): 1, ("number_input", "Price"): float(face)})]),
        # ── record: Interest_Receipt ──
        Case("record-interest", [rec("Interest_Receipt", acct, D(2026, 11, 1), expect="ok",
                                     message="Interest Receipt recorded!",
                                     form={("number_input", "Amount"): 1234.56,
                                           ("text_area", "Notes"): "coupon"})]),
        Case("record-interest-after-maturity", [rec("Interest_Receipt", acct, TODAY, expect="reject",
                                                    message="cannot be after the bond's maturity date",
                                                    security=old_sec,
                                                    form={("number_input", "Amount"): 500.0})]),
        # ── record: Principal_Repayment ──
        Case("record-repayment", [rec("Principal_Repayment", acct, TODAY, expect="ok",
                                      message="Principal Repayment recorded!",
                                      form={("number_input", "Total Amount"): round(units * face * 0.25, 2)})]),
        Case("record-repayment-above-outstanding", [rec(
            "Principal_Repayment", acct, TODAY, expect="reject", message="cannot exceed outstanding face value",
            form={("number_input", "Total Amount"): round(units * face + 100.0, 2)})]),
        Case("record-repayment-pro-rata-two-accounts", [
            rec("Principal_Repayment", m1[3], TODAY, expect="ok", message="Principal Repayment recorded!",
                security=msec, form={("number_input", "Total Amount"): round(int(m1[4]) * m1[5] * 0.5, 2)}),
            rec("Principal_Repayment", m2[3], TODAY, expect="ok", message="Principal Repayment recorded!",
                security=msec, form={("number_input", "Total Amount"): round(int(m2[4]) * m1[5] * 0.5, 2)}),
        ]),
        # ── edit transaction ──
        Case("edit-buy", [Step("edit_txn", "update", "ok", "Transaction updated!", pick=_txn_pick(buy[0]),
                               form={("number_input", "Units"): int(abs(buy[4])) + 1,
                                     ("text_area", "Notes"): "corrected"})]),
        Case("edit-buy-type-change", [Step("edit_txn", "update", "reject",
                                           "Changing transaction type from Buy to Sell is not allowed",
                                           pick=_txn_pick(buy[0]), form={("selectbox", "Type"): "Sell"})]),
        Case("edit-sell-insufficient-units", [
            rec("Sell", acct, TODAY, expect="ok", message="Sell recorded!",
                form={("number_input", "Units"): 1, ("number_input", "Price"): float(face)}),
            Step("edit_txn", "update", "reject", "Insufficient units", pick=_txn_pick(new_tid),
                 form={("number_input", "Units"): units + 10}),
        ]),
        # ── delete transaction ──
        Case("delete-buy", [Step("edit_txn", "delete", "ok", "Transaction deleted!", pick=_txn_pick(buy[0]))]),
        Case("delete-buy-under-a-sale-rolls-back", [
            sell_all,
            Step("edit_txn", "delete", "reject", "Transaction deletion rejected",
                 pick=_txn_pick(f["buys_of"][(bid, acct)][-1])),
        ]),
    ]
    if old_sec is None:     # no security past maturity in this book: those two rejections cannot be staged
        cases = [c for c in cases if c.name not in ("record-buy-after-maturity", "record-interest-after-maturity")]
    if pr is not None:
        cases += [
            Case("edit-repayment-reprice", [Step("edit_txn", "update", "ok", "Transaction updated!",
                                                 pick=_txn_pick(pr[0]),
                                                 form={("number_input", "Amount"): round(pr[4] * 0.9, 2)})]),
            Case("edit-repayment-move-date", [Step("edit_txn", "update", "ok", "Transaction updated!",
                                                   pick=_txn_pick(pr[0]),
                                                   form={("date_input", "Date"):
                                                         D.fromisoformat(pr[3]) - _dt.timedelta(days=1)})]),
            Case("edit-repayment-above-outstanding", [Step("edit_txn", "update", "reject",
                                                           "cannot exceed outstanding face value",
                                                           pick=_txn_pick(pr[0]),
                                                           form={("number_input", "Amount"): 1e12})]),
            Case("delete-repayment-owner", [Step("edit_txn", "delete", "ok", "Transaction deleted!",
                                                 pick=_txn_pick(pr[0]))]),
        ]
    return cases



# ── driving one app ──────────────────────────────────────────────────────────
class _Driver:
    """One app on one copy of the book, driven by widget labels, as its user would drive it."""

    def __init__(self, which: str):
        from streamlit.testing.v1 import AppTest
        self.which = which
        self.at = (AppTest.from_string(_ORIGINAL_SCRIPT, default_timeout=180) if which == "original"
                   else AppTest.from_file(str(APP), default_timeout=180))
        self._run()                     # lands on the original's Dashboard / the new Overview

    def _run(self) -> None:
        self.at.run()
        assert not self.at.exception, (self.which, [e.message for e in self.at.exception])

    def goto(self, op: str) -> None:
        orig, url = PAGES[op]
        if self.which == "original":     # the sidebar "Navigation" selectbox
            nav = self.at.sidebar.selectbox(key="nav_main")
            if nav.value != orig:
                nav.set_value(orig)
                self._run()
        else:                            # st.navigation page switching
            from streamlit.util import calc_md5
            if self.at._page_hash != calc_md5(url):
                self.at._page_hash = calc_md5(url)
                self._run()

    def _w(self, kind: str, label: str):
        found = [w for w in getattr(self.at.main, kind) if w.label == label]
        assert len(found) == 1, (self.which, kind, label, len(found))
        return found[0]

    def _set(self, kind: str, label: str, value) -> None:
        w = self._w(kind, label)
        w.set_value(value(list(w.options)) if callable(value) else value)

    def do(self, step: Step) -> dict:
        self.goto(step.op)
        if step.pick is not None:
            self._set("selectbox", "Select Transaction" if step.op == "edit_txn" else "Select Security", step.pick)
            self._run()
        if step.pre:                     # the reactive controls above the form, then the form they shape
            for (kind, label), value in step.pre.items():
                self._set(kind, label, value)
            self._run()
        for (kind, label), value in step.form.items():
            self._set(kind, label, value)
        for label in step.check:
            self._w("checkbox", label).check()
        self._w("button", SUBMIT[step.submit][0 if self.which == "original" else 1]).click()
        self._run()
        return self.outcome()

    def outcome(self) -> dict:
        """What the user is told: saved (toast / "Saved" notice), not saved (error / "Not saved" notice) and
        the cautions (warning / "Check" notice) — as plain text."""
        if self.which == "original":
            return {"ok": [_plain(t.value) for t in self.at.toast],
                    "reject": [_plain(e.value) for e in self.at.main.error],
                    "check": [_plain(w.value).removeprefix("Warning: ") for w in self.at.main.warning]}
        rows = [(k, html.unescape(t), html.unescape(b)) for m in self.at.markdown
                for k, t, b in _NOTICE.findall(m.value)]
        return {"ok": [b for k, _t, b in rows if k == "success"],
                "reject": [b for k, _t, b in rows if k == "danger"],
                "check": [b for _k, t, b in rows if t == "Check"]}


def _freeze(mp: pytest.MonkeyPatch, which: str, data: Path) -> None:
    """Point one app at its copy and freeze its clock and ids (see the module docstring)."""
    import streamlit.elements.widgets.time_widgets as tw
    from streamlit.testing.v1 import element_tree as et

    def _indices(self):
        """AppTest 1.52.2 reads every button group's value as a LIST; a single-select segmented control
        (Appearance, the window) holds a scalar. Test-harness shim only, as in tests/test_app.py."""
        v = self.value
        vals = v if isinstance(v, (list, tuple)) else ([] if v is None else [v])
        return [self.options.index(self.format_func(x)) for x in vals]

    mp.setattr(et.ButtonGroup, "indices", property(_indices))

    from streamlit.runtime.forward_msg_queue import ForwardMsgQueue
    from streamlit.runtime.scriptrunner import ScriptRunnerEvent
    from streamlit.testing.v1 import local_script_runner as lsr
    real_run = lsr.LocalScriptRunner.run

    def _final_screen(self, *a, **k):
        """The screen the LAST script run leaves. A submit that succeeds reruns the script, and AppTest
        keeps every element the first run drew unless the rerun overwrote it — a browser drops those
        stale elements when the rerun finishes. The user's outcome is what the final run shows."""
        real_run(self, *a, **k)
        start = max(i for i, e in enumerate(self.events) if e == ScriptRunnerEvent.SCRIPT_STARTED)
        queue = ForwardMsgQueue()       # the runner's own queue semantics, over the final run only
        for e, d in zip(self.events[start:], self.event_data[start:]):
            if e == ScriptRunnerEvent.ENQUEUE_FORWARD_MSG:
                queue.enqueue(d["forward_msg"])
        return et.parse_tree_from_messages(queue._queue)

    mp.setattr(lsr.LocalScriptRunner, "run", _final_screen)
    mp.setattr(tw, "datetime", FrozenDatetime)            # a date input's default "today"
    if which == "original":
        mp.setenv("NIVESA_DATA_DIR", str(data))           # read by the original on every run
        return
    importlib.import_module("app")      # imports every page module, so each can be patched before the run
    import core.db
    mp.setattr(core.db, "DB_FILE", str(data / "db" / "portfolio.db"))
    for name, mod in list(sys.modules.items()):
        if not name.startswith(("core.", "ui.")) or mod is None:
            continue
        if getattr(mod, "date", None) is _dt.date:
            mp.setattr(mod, "date", FrozenDate)
        if getattr(mod, "datetime", None) is _dt.datetime:
            mp.setattr(mod, "datetime", FrozenDatetime)
        if getattr(mod, "uuid", None) is _uuid_mod:
            mp.setattr(mod, "uuid", _H)


# ── comparing the books ──────────────────────────────────────────────────────
_ID_COLS = {"bond_id", "transaction_id"}


def _snapshot(db: str, known: "set[str] | None" = None) -> dict:
    """Every table (and the schema), rows sorted; ids the base book does not know become ``<new-k>`` in
    order of appearance (deterministic in both apps, so this is a safeguard, not a mask)."""
    con = sqlite3.connect(db)
    try:
        out = {"__schema__": sorted(con.execute("SELECT type, name, sql FROM sqlite_master").fetchall(), key=repr)}
        for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall():
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")').fetchall()]
            out[t] = (cols, con.execute(f'SELECT * FROM "{t}"').fetchall())
    finally:
        con.close()
    if known is None:
        return out
    new = sorted({v for t, tab in out.items() if t != "__schema__" for r in tab[1]
                  for c, v in zip(tab[0], r) if c in _ID_COLS and v not in known})
    alias = {v: f"<new-{i}>" for i, v in enumerate(new, 1)}
    for t, tab in list(out.items()):
        if t == "__schema__":
            continue
        cols, rows = tab
        rows = [tuple(alias.get(v, v) if c in _ID_COLS else v for c, v in zip(cols, r)) for r in rows]
        out[t] = (cols, sorted(rows, key=repr))
    return out


def _known_ids(db: str) -> set:
    snap = _snapshot(db)
    return {v for t, tab in snap.items() if t != "__schema__" for r in tab[1]
            for c, v in zip(tab[0], r) if c in _ID_COLS}


# ── the matrix ───────────────────────────────────────────────────────────────
_BASE = Path(tempfile.mkdtemp(prefix="nivesa-writepaths-")) / "data"
shutil.copytree(REPO / "data", _BASE)
atexit.register(shutil.rmtree, _BASE.parent, True)
_BASE_DB = str(_BASE / "db" / "portfolio.db")
assert Path(_BASE).resolve() != (REPO / "data").resolve()
CASES = _cases(_facts(_BASE_DB))
KNOWN = _known_ids(_BASE_DB)


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_write_path_matches_the_original(case, tmp_path, monkeypatch):
    runs: dict = {}
    for which in ("original", "new"):
        data = tmp_path / which / "data"
        shutil.copytree(_BASE, data)
        db = str(data / "db" / "portfolio.db")
        _H.n = 0
        with monkeypatch.context() as mp:
            _freeze(mp, which, data)
            drv = _Driver(which)
            before = _snapshot(db, KNOWN)
            steps = []
            for i, step in enumerate(case.steps):
                out = drv.do(step)
                after = _snapshot(db, KNOWN)
                where = f"{case.name} · step {i + 1} · {which}"
                # the scenario does what it says, in this app
                if step.expect == "ok":
                    assert any(step.message in m for m in out["ok"]) and not out["reject"], (where, out)
                    assert after != before, (where, "an accepted entry left the book unchanged")
                else:
                    assert any(step.message in m for m in out["reject"]) and not out["ok"], (where, out)
                    assert after == before, (where, "a rejected entry changed the book")
                steps.append((out, after))
                before = after
        runs[which] = steps
    for i, ((o_out, o_db), (n_out, n_db)) in enumerate(zip(runs["original"], runs["new"])):
        where = f"{case.name} · step {i + 1}"
        assert n_out == o_out, (where, "what the user is told differs", o_out, n_out)
        assert n_db.keys() == o_db.keys(), (where, sorted(n_db.keys() ^ o_db.keys()))
        for t in o_db:
            assert n_db[t] == o_db[t], (where, f"table {t} differs from the original's")
