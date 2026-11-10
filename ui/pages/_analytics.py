"""
Nivesa — what the four Analytics pages share: the panel-scoped Account filter and the words a panel
uses for the slice of the book it shows.

The Account filter is 2.8.0's per-tab "Filter by Account" selectbox — the same options (All, then the
accounts that hold a position, from ``core.views.account_options``) — moved into a filterbar strip
directly above the first thing it filters, so its position states its scope.
"""

from __future__ import annotations

import streamlit as st

from core.views import account_options

#: The command bar's scope word; a filtered panel names its account instead.
ALL_ACCOUNTS = "ALL ACCOUNTS"


def account_filter(df, key: str, *, help: str = "") -> str:  # noqa: A002 — Streamlit's own name
    """The filterbar strip with the Account selectbox; returns the chosen option ('All' or an account).
    The stored choice is reseeded to 'All' when it no longer names an account that holds a position."""
    options = account_options(df)
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]
    with st.container(key="filterbar"):
        return st.selectbox("Account", options, key=key, help=help or None)


def scope_of(acct: str) -> str:
    """The panel-context word for a filter choice: ALL ACCOUNTS, or the account's name."""
    return ALL_ACCOUNTS if acct == "All" else str(acct).upper()


def plural(n: int, word: str, many: str | None = None) -> str:
    return f"{n:,} {word if n == 1 else (many or word + 's')}"
