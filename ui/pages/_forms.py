"""
Nivesa — what the Operations forms share: the security's terms read back above a form, the
option-index helper, and the empty state for a master with nothing in it yet.

The forms' write paths are the 2.8.0 handlers verbatim (``tests/test_source_identity.py`` compares
them); only the widgets around them are restyled.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.bonds import calc_days_to_maturity
from core.formatting import fmt_inr, fmt_pct
from ui.components import esc, render_empty_state


def _safe_index(options, value, default=0):
    """Return index of value in options list, or default if not found."""
    try:
        return options.index(value)
    except (ValueError, TypeError):
        return default


def render_terms(items: "list[tuple[str, str]]") -> None:
    """One k/v strip of a security's terms (or a position's holdings) — escaped, mono, tabular."""
    body = "".join(f'<span class="t-item"><span class="k">{esc(k)}</span><span class="v">{esc(v)}</span></span>'
                   for k, v in items if v not in (None, ""))
    if body:
        st.markdown(f'<div class="terms-strip">{body}</div>', unsafe_allow_html=True)


def security_terms(si, *, rating=True, freq=True) -> list[tuple[str, str]]:
    """The terms a form reads back: coupon, face per unit, frequency, maturity (days left), rating."""
    dtm = calc_days_to_maturity(si['maturity_date'])
    mat_str = pd.to_datetime(si['maturity_date']).strftime('%d %b %Y')
    items = [("Coupon", fmt_pct(si['coupon_rate'])), ("Face / unit", fmt_inr(si['face_value']))]
    if freq:
        items.append(("Frequency", str(si['frequency'])))
    items.append(("Maturity", f"{mat_str} · {dtm}d"))
    if rating:
        items.append(("Rating", str(si.get('credit_rating') or 'Unrated')))
    return items


def render_no_securities(page: str) -> None:
    """The master is empty — say so, and point at the page that fixes it."""
    render_empty_state(
        "No securities yet",
        "The securities master is empty, so there is nothing to pick here.",
        eyebrow=page,
        action_label="Add one under Operations → Add Security.",
    )


def render_no_transactions(page: str) -> None:
    render_empty_state(
        "No transactions yet",
        "The ledger is empty, so there is nothing to correct.",
        eyebrow=page,
        action_label="Record one under Operations → Record Transaction.",
    )
