# -*- coding: utf-8 -*-
"""
Nivesa — the contractual redemption schedule: when a bond pays its principal back, and how much per
bond each time.

Many NCDs do not repay at maturity but in instalments (quarterly, half-yearly, …) set out in their
offer document. The ledger records what was RECEIVED (Principal_Repayment transactions, which step the
face value down); this table records what is DUE, once per security:

    redemption_schedule (schedule_id, bond_id, due_date, principal_per_unit, source, notes)

``principal_per_unit`` is rupees per bond on that date, against the bond's ORIGINAL face. The schedule
drives the projections (cashflows, yield to cost, duration) and the "repayments due" list: a scheduled
date that has passed with no repayment recorded for an account holding the bond on that date is shown,
and can be recorded for every such account in one step (``record_due``), through the same face
step-down and chronology check the Record Transaction form uses.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import date, timedelta

import pandas as pd

from core.config import logger
from core.db import _connect, claim_face_adjustment, db_query, validate_ledger_chronology

_TABLE = """
CREATE TABLE IF NOT EXISTS redemption_schedule (
    schedule_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    bond_id            TEXT NOT NULL REFERENCES securities (bond_id),
    due_date           TEXT NOT NULL,
    principal_per_unit REAL NOT NULL CHECK (principal_per_unit > 0),
    source             TEXT,
    notes              TEXT,
    UNIQUE (bond_id, due_date)
)"""

#: The bond's interest day, when it is not the maturity date's day (1-31; 31 = month-end). One row per
#: bond that has one; none means interest falls on the maturity date's day each period.
_TERMS = """
CREATE TABLE IF NOT EXISTS bond_terms (
    bond_id    TEXT PRIMARY KEY REFERENCES securities (bond_id),
    coupon_day INTEGER CHECK (coupon_day BETWEEN 1 AND 31)
)"""

#: A recorded repayment this many days either side of a scheduled date counts as that instalment
#: (issuers pay on the next business day; entries are made on the day the money arrives).
MATCH_DAYS = 20


def schedule_init() -> bool:
    try:
        with closing(_connect()) as conn, conn:
            conn.execute(_TABLE)
            conn.execute(_TERMS)
        return True
    except sqlite3.Error as e:
        logger.error(f"Redemption schedule init failed: {e}")
        return False


def _exists() -> bool:
    try:
        with closing(_connect()) as conn:
            return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='redemption_schedule'"
                                ).fetchone() is not None
    except sqlite3.Error:
        return False


def schedules() -> "dict[str, list[tuple[date, float]]]":
    """Every bond's schedule: bond_id → [(due_date, principal_per_unit)], in date order (empty when the
    book has no schedule table yet)."""
    if not _exists():
        return {}
    df = db_query("SELECT bond_id, due_date, principal_per_unit FROM redemption_schedule ORDER BY bond_id, due_date")
    out: dict = {}
    for _, r in df.iterrows():
        out.setdefault(r["bond_id"], []).append((pd.to_datetime(r["due_date"]).date(), float(r["principal_per_unit"])))
    return out


def _terms_exist() -> bool:
    try:
        with closing(_connect()) as conn:
            return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='bond_terms'").fetchone() is not None
    except sqlite3.Error:
        return False


def coupon_days() -> "dict[str, int]":
    """bond_id → interest day, for the bonds that have one (empty when the book has no terms table)."""
    if not _terms_exist():
        return {}
    df = db_query("SELECT bond_id, coupon_day FROM bond_terms WHERE coupon_day IS NOT NULL")
    return {r["bond_id"]: int(r["coupon_day"]) for _, r in df.iterrows()}


def set_coupon_day(bond_id: str, day: "int | None") -> None:
    """Set (1-31) or clear (None: the maturity date's day) a bond's interest day."""
    with closing(_connect()) as conn, conn:
        if day is None:
            conn.execute("DELETE FROM bond_terms WHERE bond_id=?", (bond_id,))
        else:
            conn.execute("INSERT INTO bond_terms (bond_id, coupon_day) VALUES (?, ?) "
                         "ON CONFLICT(bond_id) DO UPDATE SET coupon_day=excluded.coupon_day", (bond_id, int(day)))


def schedule_frame(bond_id: str) -> pd.DataFrame:
    if not _exists():
        return pd.DataFrame(columns=["due_date", "principal_per_unit", "source", "notes"])
    return db_query("SELECT due_date, principal_per_unit, source, notes FROM redemption_schedule "
                    "WHERE bond_id=? ORDER BY due_date", (bond_id,))


def original_face(bond_id: str) -> float:
    """Face per bond at issue: today's face plus every step-down a recorded repayment has made."""
    r = db_query(
        "SELECT s.face_value + COALESCE((SELECT SUM(price) FROM transactions t WHERE t.bond_id=s.bond_id "
        "AND t.transaction_type='Principal_Repayment' AND t.owns_face_adj=1), 0) AS f "
        "FROM securities s WHERE s.bond_id=?", (bond_id,))
    return float(r["f"].iloc[0]) if not r.empty and pd.notna(r["f"].iloc[0]) else 0.0


def parse_lines(text: str) -> "list[tuple[date, float]]":
    """``YYYY-MM-DD, amount`` (or ``DD-MM-YYYY``; comma, tab or spaces) per line → [(date, amount)].
    Raises ValueError naming the first line it cannot read."""
    rows = []
    for n, line in enumerate((text or "").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p for p in line.replace("\t", ",").replace(";", ",").replace(" ", ",").split(",") if p]
        if len(parts) < 2:
            raise ValueError(f"line {n}: expected a date and an amount, got “{line}”")
        try:
            d = pd.to_datetime(parts[0], dayfirst=not parts[0][:4].isdigit()).date()
            a = float(parts[-1].replace("₹", "").replace("_", ""))
        except (ValueError, TypeError):
            raise ValueError(f"line {n}: could not read “{line}”") from None
        rows.append((d, a))
    return sorted(rows)


def equal_instalments(first: date, every_months: int, count: int, total: float) -> "list[tuple[date, float]]":
    """``count`` equal instalments of ``total`` every ``every_months`` months from ``first``, the last
    taking the rounding (amounts to the paisa)."""
    from dateutil.relativedelta import relativedelta
    each = round(total / count, 2)
    out = [(first + relativedelta(months=every_months * k), each) for k in range(count)]
    out[-1] = (out[-1][0], round(total - each * (count - 1), 2))
    return out


def check(rows, *, face: float, issue: "date | None", maturity: date,
          today: "date | None" = None) -> "tuple[list[str], list[str]]":
    """``(errors, warnings)`` for a schedule against the bond's terms.

    ``face`` is the bond's CURRENT face per bond — the one figure both the Add and the Edit form know.
    Instalments dated after ``today`` are what is still to be repaid, so they may not add up to more
    than it; if they add up to less, the rest is repaid at maturity. Instalments on or before today
    are already reflected in the current face (a bond added part-way through its life, or one whose
    repayments are recorded), so only their dates and amounts are checked."""
    today = today or date.today()
    errors, warnings = [], []
    if not rows:
        return errors, warnings
    dates = [d for d, _a in rows]
    if len(set(dates)) != len(dates):
        errors.append("a date appears twice")
    if any(a <= 0 for _d, a in rows):
        errors.append("every amount must be above zero")
    if any(d > maturity for d in dates):
        errors.append(f"a date falls after maturity ({maturity:%d %b %Y})")
    if issue is not None and any(d <= issue for d in dates):
        errors.append(f"a date falls on or before the issue date ({issue:%d %b %Y})")
    ahead = sum(a for d, a in rows if d > today)
    if face > 0 and ahead > face + 0.5:
        errors.append(f"the instalments still to come add up to ₹{ahead:,.2f}, more than the current face of "
                      f"₹{face:,.2f}")
    elif face > 0 and face - ahead > 0.5:
        warnings.append(f"the instalments still to come add up to ₹{ahead:,.2f} of a ₹{face:,.2f} face; the "
                        f"remaining ₹{face - ahead:,.2f} is treated as repaid at maturity")
    return errors, warnings


def replace_schedule(bond_id: str, rows, source: str = "entered", notes: "str | None" = None) -> None:
    """Replace a bond's whole schedule in one transaction (an empty ``rows`` clears it)."""
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM redemption_schedule WHERE bond_id=?", (bond_id,))
        conn.executemany(
            "INSERT INTO redemption_schedule (bond_id, due_date, principal_per_unit, source, notes) VALUES (?,?,?,?,?)",
            [(bond_id, d.isoformat(), float(a), source, notes) for d, a in rows])
    logger.info(f"Redemption schedule set for {bond_id}: {len(rows)} instalments")


def due_unrecorded(today: "date | None" = None) -> pd.DataFrame:
    """Scheduled instalments on or before ``today`` that an account holding the bond on that date has
    no repayment recorded for (within ``MATCH_DAYS``). One row per (bond, date, account) with the units
    held then and the amount due; empty when everything is recorded."""
    today = today or date.today()
    cols = ["bond_id", "issuer", "isin", "due_date", "account", "units", "principal_per_unit", "amount"]
    if not _exists():
        return pd.DataFrame(columns=cols)
    sch = db_query("SELECT r.bond_id, r.due_date, r.principal_per_unit, s.issuer, s.isin "
                   "FROM redemption_schedule r JOIN securities s USING (bond_id) WHERE r.due_date <= ? "
                   "ORDER BY s.issuer, r.due_date", (today.isoformat(),))
    if sch.empty:
        return pd.DataFrame(columns=cols)
    tx = db_query("SELECT bond_id, account, trade_date, transaction_type, units FROM transactions "
                  "WHERE bond_id IN (%s)" % ",".join("?" * sch["bond_id"].nunique()), tuple(sch["bond_id"].unique()))
    tx["trade_date"] = pd.to_datetime(tx["trade_date"])
    out = []
    for _, s in sch.iterrows():
        due = pd.Timestamp(s["due_date"])
        t = tx[tx["bond_id"] == s["bond_id"]]
        # units held at the start of the due date (a sale on the day still had the bonds on record)
        held = t[t["transaction_type"].isin(["Buy", "Sell"]) & (t["trade_date"] < due)].groupby("account")["units"].sum()
        reps = t[t["transaction_type"] == "Principal_Repayment"]
        for acct, units in held.items():
            if units <= 1e-9:
                continue
            near = reps[(reps["account"] == acct) & ((reps["trade_date"] - due).abs() <= timedelta(days=MATCH_DAYS))]
            if near.empty:
                out.append({"bond_id": s["bond_id"], "issuer": s["issuer"], "isin": s["isin"],
                            "due_date": due.date(), "account": acct, "units": float(units),
                            "principal_per_unit": float(s["principal_per_unit"]),
                            "amount": round(float(units) * float(s["principal_per_unit"]), 2)})
    return pd.DataFrame(out, columns=cols)


def record_due(rows: pd.DataFrame) -> "tuple[bool, str]":
    """Record ``rows`` (from ``due_unrecorded``) as Principal_Repayment entries in ONE transaction, in
    date order, each through the face step-down claim and the chronology check — all or nothing."""
    if rows is None or rows.empty:
        return False, "nothing to record"
    rows = rows.sort_values(["due_date", "account"])
    try:
        with closing(_connect()) as conn, conn:
            c = conn.cursor()
            for _, r in rows.iterrows():
                tid, d = str(uuid.uuid4()), pd.Timestamp(r["due_date"]).date().isoformat()
                c.execute("INSERT INTO transactions (transaction_id, bond_id, account, trade_date, transaction_type, "
                          "units, price, amount, notes) VALUES (?,?,?,?,?,?,?,?,?)",
                          (tid, r["bond_id"], r["account"], d, "Principal_Repayment", 0.0,
                           float(r["principal_per_unit"]), float(r["amount"]), "Scheduled instalment"))
                claim_face_adjustment(c, r["bond_id"], d, tid, float(r["principal_per_unit"]))
            for bid in rows["bond_id"].unique():
                ok, acct, when = validate_ledger_chronology(bid, conn)
                if not ok:
                    raise sqlite3.IntegrityError(f"{acct} would hold negative units on {when}")
            face = c.execute("SELECT MIN(face_value) FROM securities WHERE bond_id IN (%s)"
                             % ",".join("?" * rows["bond_id"].nunique()), tuple(rows["bond_id"].unique())).fetchone()[0]
            if face is not None and face < -0.01:
                raise sqlite3.IntegrityError("a face value would fall below zero — check the schedule")
        n = len(rows)
        logger.info(f"Recorded {n} scheduled repayment(s)")
        return True, f"{n} repayment{'s' if n != 1 else ''} recorded"
    except sqlite3.Error as e:
        logger.error(f"Recording scheduled repayments failed: {e}")
        return False, str(e)
