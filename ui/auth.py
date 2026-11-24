"""
Nivesa — the sign-in gate: one shared password in front of the whole app.

The password is read from ``NIVESA_PASSWORD`` (environment) or ``[auth] password`` in
``.streamlit/secrets.toml`` / the host's secrets panel — never from the repository. Set one wherever
the app is reachable by anyone but you: without it every page, the write forms included, is open.

  · compared in constant time (``hmac.compare_digest``);
  · after ``_FREE_TRIES`` wrong attempts in a session each further attempt waits ``_PENALTY_S`` longer;
  · "Sign out" in the rail ends the session's access.

With no password configured the app runs open, as before, and the notice rail says so on every page.
"""

from __future__ import annotations

import hmac
import os
import time

import streamlit as st

from core.config import PRODUCT_NAME, TAGLINE, logger
from ui.components import render_header, render_notice_rail

_OK = "_auth_ok"
_FAILS = "_auth_fails"
_FREE_TRIES = 3
_PENALTY_S = 2.0


def configured_password() -> "str | None":
    """The password the app is locked with, or None when it runs open."""
    env = os.environ.get("NIVESA_PASSWORD")
    if env:
        return env
    try:
        pw = st.secrets.get("auth", {}).get("password")
    except Exception:  # noqa: BLE001 — no secrets file at all is the ordinary local case
        pw = None
    return str(pw) if pw else None


def is_locked() -> bool:
    return configured_password() is not None


def open_notice() -> "list[dict]":
    """The rail's standing caveat when no password is set (empty when one is)."""
    if is_locked():
        return []
    return [{"kind": "warning", "title": "Open",
             "body": "No password is set, so anyone who can reach this app can read and change the ledger. "
                     "Set NIVESA_PASSWORD or [auth] password in the app's secrets."}]


def require_login() -> bool:
    """Draw the sign-in form and return False until this session has signed in (True when open)."""
    pw = configured_password()
    if pw is None or st.session_state.get(_OK):
        return True

    render_header(PRODUCT_NAME.upper(), TAGLINE)
    with st.form("signin"):
        given = st.text_input("Password", type="password", key="signin_pw")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        fails = int(st.session_state.get(_FAILS, 0))
        if fails >= _FREE_TRIES:
            time.sleep(_PENALTY_S * (fails - _FREE_TRIES + 1))
        if hmac.compare_digest(given.encode("utf-8"), pw.encode("utf-8")):
            st.session_state[_OK] = True
            st.session_state[_FAILS] = 0
            logger.info("Sign-in succeeded.")
            st.rerun()
        st.session_state[_FAILS] = fails + 1
        logger.warning(f"Sign-in failed ({fails + 1} in this session).")
        render_notice_rail([{"kind": "danger", "title": "Not signed in", "body": "That password is not right."}])
    return False


def render_sign_out() -> None:
    """The rail's Sign out button (only when a password is set)."""
    if is_locked() and st.button("Sign out", type="secondary", width="stretch", key="signout"):
        st.session_state[_OK] = False
        st.rerun()
