"""
Nivesa — Operations · Audit Trail: every change made to the book, newest first.

The rows come from ``audit_log`` (``core.audit``), which SQLite triggers write on every insert, update
and delete — the app cannot skip it and cannot edit it. Each row reads as one sentence: what changed,
on which security or transaction, from what to what.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from core.audit import audit_entries
from core.db import db_query
from core.formatting import fmt_inr
from ui.components import render_empty_state, render_note, render_section_header, render_table_panel

_LIMIT = 500
_TABLE = {"transactions": "Transaction", "securities": "Security", "security_metadata": "Security details",
          "bond_terms": "Payment terms", "redemption_schedule": "Instalment"}
_ACTION = {"INSERT": "Added", "UPDATE": "Changed", "DELETE": "Deleted"}

# A change reads in the ledger's own words, as the forms name each field, never as a column name: "Credit rating:
# Unrated → A", not "credit_rating: Unrated → A"; rupees Indian-grouped, dates as the book writes them, the coupon in
# percent, nothing for an empty field, and no internal ids.
_FIELD = {
    "account": "Account", "trade_date": "Date", "transaction_type": "Type", "units": "Units", "price": "Price",
    "amount": "Amount", "notes": "Notes", "issuer": "Issuer", "isin": "ISIN", "maturity_date": "Maturity",
    "frequency": "Frequency", "coupon_rate": "Coupon", "face_value": "Face value", "bond_type": "Bond type",
    "credit_rating": "Credit rating", "day_count": "Day count", "issue_date": "Issue date", "call_date": "Call date",
    "put_date": "Put date", "listing": "Listing", "sector": "Sector", "coupon_day": "Interest paid on",
    "due_date": "Due", "principal_per_unit": "Per bond", "source": "Source",
}
_HIDDEN = {"bond_id", "transaction_id", "schedule_id", "owns_face_adj"}
_MONEY = {"price", "amount", "face_value", "principal_per_unit"}


def _day(v) -> str:
    d = int(v)
    if d >= 31:
        return "last day of the month"
    return f"{d}{'st' if d in (1, 21) else 'nd' if d in (2, 22) else 'rd' if d in (3, 23) else 'th'}"


def _value(k: str, v) -> str:
    if v is None or (isinstance(v, str) and not v.strip()):
        return "—"
    try:
        if k in _MONEY:
            return fmt_inr(float(v))
        if k == "coupon_rate":
            return f"{float(v) * 100:.2f}%"
        if k == "units":
            return f"{float(v):,.0f}" if float(v).is_integer() else f"{float(v):,.4f}".rstrip("0")
        if k == "coupon_day":
            return _day(v)
        if k.endswith("_date"):
            return pd.Timestamp(v).strftime("%d %b %Y")
        if k == "transaction_type":
            return str(v).replace("_", " ").capitalize()
    except (TypeError, ValueError):
        pass
    return str(v)


def _pair(k: str, v) -> str:
    return f"{_FIELD.get(k, k.replace('_', ' ').capitalize())}: {_value(k, v)}"


def _load(s) -> dict:
    try:
        return json.loads(s) if isinstance(s, str) and s else {}
    except ValueError:
        return {}


def _subject(row, issuers: dict) -> str:
    """Which thing the entry is about, in words the ledger uses."""
    r = _load(row["new_row"]) or _load(row["old_row"])
    issuer = issuers.get(r.get("bond_id"), "")
    if row["table_name"] == "transactions":
        kind = str(r.get("transaction_type", "")).replace("_", " ")
        return " · ".join(x for x in (issuer, r.get("account"), kind, r.get("trade_date")) if x)
    return issuer or str(row["row_id"])[:12]


def _changes(row) -> str:
    old, new = _load(row["old_row"]), _load(row["new_row"])
    if row["action"] == "UPDATE":
        return " · ".join(f"{_FIELD.get(k, k)}: {_value(k, old.get(k))} → {_value(k, new.get(k))}"
                          for k in new if k not in _HIDDEN and old.get(k) != new.get(k))
    r = new or old
    keep = ("units", "price", "amount") if row["table_name"] == "transactions" else tuple(r)
    return " · ".join(_pair(k, r[k]) for k in keep if k in r and k not in _HIDDEN and r[k] not in (None, ""))


def render_audit_page() -> None:
    """Operations · Audit Trail — the append-only record of every change."""
    log = audit_entries(_LIMIT)
    if log.empty:
        render_section_header("Audit Trail", "No change has been recorded since the trail was switched on.",
                              icon="shield")
        render_empty_state("Nothing recorded yet", "Every add, edit and delete from now on appears here.",
                           eyebrow="Audit Trail")
        return

    secs = db_query("SELECT bond_id, issuer FROM securities")
    issuers = dict(zip(secs["bond_id"], secs["issuer"])) if not secs.empty else {}
    # a deleted security still has its issuer in the trail
    for _, r in log[log["table_name"] == "securities"].iterrows():
        d = _load(r["old_row"]) or _load(r["new_row"])
        issuers.setdefault(d.get("bond_id"), d.get("issuer", ""))

    render_section_header(
        "Audit Trail",
        f"{len(log):,} most recent changes to the book, newest first. Entries are written by the database "
        f"itself on every add, edit and delete, and cannot be changed or removed.",
        icon="shield",
    )
    view = pd.DataFrame({
        "when": pd.to_datetime(log["changed_at"], utc=True).dt.tz_convert("Asia/Kolkata")
                  .dt.strftime("%d %b %Y %H:%M:%S"),
        "what": log["table_name"].map(_TABLE).fillna(log["table_name"]) + " " + log["action"].map(_ACTION).str.lower(),
        "subject": log.apply(lambda r: _subject(r, issuers), axis=1),
        "changes": log.apply(_changes, axis=1),
    })
    render_table_panel(view, "audit", context=f"AUDIT TRAIL · last {len(view):,} · IST", max_height=640,
                       label_col="when", col_labels={"when": "When (IST)", "what": "What", "subject": "On",
                                                     "changes": "Changes"})
    st.download_button("Download the full audit trail (CSV)", audit_entries(10**9).to_csv(index=False),
                       "nivesa_audit.csv", "text/csv", key="audit-csv", on_click="ignore")
    render_note("A principal repayment leaves more than one entry: the transaction, and the step-down of the bond's face value it makes.")
