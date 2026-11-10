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
    return get_positions_dataframe()


@st.cache_data(show_spinner=False, max_entries=4)
def _shell(sig: tuple):  # noqa: ARG001 — the cache key
    df, totals = _positions(sig)
    return {
        "tape": views.tape_items(df),
        "bar": views.command_bar(df, totals),
        "notices": views.book_notices(df),
        "rail": views.rail_counts(),
        "empty": views.is_empty_book(df),
    }


def load_book() -> "tuple[pd.DataFrame, dict]":
    """``(positions, totals)`` — a private copy each call (pages may add columns)."""
    df, totals = _positions(_signature())
    return df.copy(), dict(totals)


def shell_context() -> dict:
    """The shell's figures (tape, command bar, notices, rail readout), computed once per book state."""
    return _shell(_signature())


def clear() -> None:
    st.cache_data.clear()
