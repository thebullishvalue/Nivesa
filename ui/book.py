"""
Nivesa — the book, read once per change: the positions engine and the shell's figures, cached on the
database's own signature so every page of a run (and every run until the next write) reads the same
numbers without recomputing them.

The signature is the SQLite file and its write-ahead log (mtime + size) plus today's date: any write
through any path changes it, and the as-of date rolls the projections at midnight. ``Refresh`` in the
rail clears the cache outright.
"""

from __future__ import annotations

import os
from datetime import date

import pandas as pd
import streamlit as st

import core.db as _db
from core import views
from core.book import get_positions_dataframe


def _signature() -> tuple:
    parts: list = [date.today().isoformat(), _db.DB_FILE]
    for suffix in ("", "-wal"):
        try:
            stt = os.stat(_db.DB_FILE + suffix)
            parts.append((stt.st_mtime_ns, stt.st_size))
        except OSError:
            parts.append(None)
    return tuple(parts)


@st.cache_data(show_spinner=False, max_entries=4)
def _positions(sig: tuple):  # noqa: ARG001 — the cache key
    """The positions engine, run once per book state — and traced in the terminal when it runs."""
    from core.config import VERSION
    from core.logger_config import console
    console.header("Nivesa · Book", VERSION)
    console.main_header("Source", {"Database": os.path.basename(_db.DB_FILE), "As of": sig[0]})
    try:
        with console.task("Positions engine", "running average cost · accruals · yields") as t:
            df, totals = get_positions_dataframe()
            t.ok(f"{len(df)} positions" if len(df) else "empty book")
    except Exception:
        console.end_run("FAILED")
        raise
    if len(df):
        from core.formatting import fmt_inr, fmt_inr_short, fmt_pct
        console.summary("Book", {
            "Positions": f"{totals['Num Positions']} · {totals['Num Issuers']} issuers · "
                         f"{totals['Num Accounts']} accounts",
            "Face value": f"{fmt_inr(totals['Total Face Value'])} ({fmt_inr_short(totals['Total Face Value'])})",
            "Cost basis": fmt_inr(totals["Total Cost Basis"]),
            "Annual coupon": fmt_inr(totals["Total Annual Coupon"]),
            "Accrued interest": fmt_inr(totals["Total Accrued Interest"]),
            "Nominal yield": fmt_pct(totals["Weighted Nominal Yield"]),
            "Yield to cost": fmt_pct(totals["Weighted YTC"]),
            "Modified duration": f"{totals['Weighted Mod Duration']:.2f} years",
            "Avg maturity": f"{totals['Weighted Avg Maturity']:.2f} years",
        })
    console.end_run()
    return df, totals


@st.cache_data(show_spinner=False, max_entries=4)
def _shell(sig: tuple):  # noqa: ARG001 — the cache key
    df, totals = _positions(sig)
    return {
        "tape": views.tape_items(df),
        "bar": views.command_bar(df, totals),
        "notices": _notices(df),
        "empty": views.is_empty_book(df),
    }


def _notices(df) -> list[dict]:
    """The book's standing notices, a matured position listed once: under Repayments due when its
    schedule has the redemption waiting to be recorded, else under Matured, not redeemed."""
    from core.schedule import due_unrecorded
    due = due_unrecorded()
    keys = set(zip(due["bond_id"], due["account"])) if not due.empty else set()
    return views.book_notices(df, exclude=keys) + views.due_repayment_notices()


def load_book() -> "tuple[pd.DataFrame, dict]":
    """``(positions, totals)`` — a private copy each call (pages may add columns)."""
    df, totals = _positions(_signature())
    return df.copy(), dict(totals)


def shell_context() -> dict:
    """The shell's figures (tape, command bar, notices, rail readout), computed once per book state."""
    return _shell(_signature())


def clear() -> None:
    st.cache_data.clear()
