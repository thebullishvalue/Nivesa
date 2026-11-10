"""
Nivesa — Operations · Securities: the master registry — every bond the ledger can transact.

Tattva's record grammar: the section header answers "what is registered" with live numbers → a filterbar
strip scoping the one table (the 2.8.0 page's own filters: Bond Type, Credit Rating, Search) → the
registry table panel, by issuer, every 2.8.0 column with the days to maturity → its CSV export.

The rows are ``core.views.securities_master`` — the 2.8.0 query and filters verbatim — and the cells are
printed as 2.8.0 printed them (an unset type reads NCD, an unset rating Unrated); nothing here computes.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.formatting import fmt_inr, fmt_pct
from core.views import securities_master
from ui.components import render_empty_state, render_note, render_section_header, render_table_panel

#: The table's columns: (source column, header, formatter or None) — the 2.8.0 registry's ten columns.
_COLS = (
    ("issuer", "Issuer", None),
    ("isin", "ISIN", None),
    ("bond_type", "Type", None),
    ("credit_rating", "Rating", None),
    ("coupon_rate", "Coupon", fmt_pct),
    ("face_value", "Face Value", fmt_inr),
    ("frequency", "Frequency", None),
    ("maturity_date", "Maturity", None),
    ("days", "Days to Maturity", lambda v: f"{int(v):,}d"),
    ("sector", "Sector", None),
)

#: The CSV export: the same rows and columns at full precision, the coupon in percent to match its label.
_EXPORT = {"issuer": "Issuer", "isin": "ISIN", "bond_type": "Type", "credit_rating": "Rating",
           "coupon_rate": "Coupon (%)", "face_value": "Face Value", "frequency": "Frequency",
           "maturity_date": "Maturity Date", "days": "Days to Maturity", "sector": "Sector", "listing": "Listing"}


def _text(v, default: str) -> str:
    """A metadata text cell as 2.8.0 printed it (``value or default``), NaN from the LEFT JOIN included."""
    return v if isinstance(v, str) and v else default


def _n(k: int, one: str, many: str) -> str:
    return f"{k:,} {one if k == 1 else many}"


def _answer(secs: pd.DataFrame) -> str:
    live = secs[secs["days"] > 0]
    types = secs["bond_type"].map(lambda v: _text(v, "NCD")).nunique()
    out = (f"{_n(len(secs), 'security', 'securities')} registered across "
           f"{_n(secs['issuer'].nunique(), 'issuer', 'issuers')} and {_n(types, 'bond type', 'bond types')}; "
           f"{len(live):,} {'is' if len(live) == 1 else 'are'} not yet at maturity")
    if not live.empty:
        nxt = live.sort_values("days").iloc[0]
        out += (f", the nearest maturing on {pd.to_datetime(nxt['maturity_date']):%d %b %Y} "
                f"({_n(int(nxt['days']), 'day', 'days')})")
    matured = len(secs) - len(live)
    out += (f", and {matured:,} at or past it." if matured else ".")
    return out + " Coupon is the annual rate; face value is the current outstanding face per unit."


def _filters(secs: pd.DataFrame) -> tuple[str, str, str]:
    """The 2.8.0 page's three filters (options from the whole registry), in a strip above the table."""
    with st.container(key="filterbar"):
        f1, f2, f3 = st.columns(3, gap="small")
        with f1:
            type_opts = ['All'] + sorted(secs['bond_type'].dropna().unique().tolist())
            sm_type = st.selectbox("Bond Type", type_opts, key="sm_type")
        with f2:
            rating_opts = ['All'] + sorted(secs['credit_rating'].dropna().unique().tolist())
            sm_rating = st.selectbox("Credit Rating", rating_opts, key="sm_rating")
        with f3:
            sm_search = st.text_input("Search", key="sm_search", placeholder="Filter by issuer name…")
    return sm_type, sm_rating, sm_search


def render_securities_page() -> None:
    """Operations · Securities — the master registry."""
    secs = securities_master()
    if secs.empty:
        render_section_header("Securities Master", "No securities registered.", icon="cube")
        render_empty_state("No securities yet", "The securities master is empty.", eyebrow="Securities",
                           action_label="Add one under Operations → Add Security.")
        return

    render_section_header("Securities Master", _answer(secs), icon="cube")
    sm_type, sm_rating, sm_search = _filters(secs)
    filtered = securities_master(sm_type, sm_rating, sm_search)
    if filtered.empty:
        render_empty_state("No securities match", "No security in the master matches these filters.",
                           eyebrow="Securities", action_label="Clear the search, or set Bond Type and Credit "
                                                             "Rating to All.")
        return

    view = filtered.copy()
    view["bond_type"] = view["bond_type"].map(lambda v: _text(v, "NCD"))
    view["credit_rating"] = view["credit_rating"].map(lambda v: _text(v, "Unrated"))
    view["sector"] = view["sector"].map(lambda v: _text(v, "—"))
    view["maturity_date"] = pd.to_datetime(view["maturity_date"])
    view = view[[c for c, _h, _f in _COLS]].reset_index(drop=True)

    scope = [f for f in (sm_type, sm_rating) if f != 'All'] + ([f"“{sm_search}”"] if sm_search else [])
    count = (f"{len(view):,} of {len(secs):,} securities" if len(view) != len(secs)
             else _n(len(view), "security", "securities"))
    render_table_panel(
        view, "securities",
        context=" · ".join(["SECURITIES MASTER", *scope, count, "by issuer"]),
        max_height=640, label_col="issuer",
        col_labels={c: h for c, h, _f in _COLS},
        col_format={c: f for c, _h, f in _COLS if f is not None},
    )

    exp = filtered[list(_EXPORT)].copy()
    exp["coupon_rate"] = (exp["coupon_rate"] * 100).round(4)
    exp["maturity_date"] = pd.to_datetime(exp["maturity_date"]).dt.strftime("%Y-%m-%d")
    exp = exp.rename(columns=_EXPORT)
    st.download_button(
        "Download the filtered securities master (CSV)" if len(view) != len(secs)
        else "Download the securities master (CSV)",
        exp.to_csv(index=False), "nivesa_securities.csv", "text/csv", key="securities-csv", on_click="ignore",
        help="The rows the filters select, every column at full precision; coupon in percent.")
    render_note(f"Securities master · {len(secs):,} registered · days to maturity count from today and stop at 0, "
                f"so a bond past maturity reads 0d · the export carries the rows on screen, with the listing.")
