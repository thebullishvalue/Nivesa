"""
Nivesa — Operations · Add Security: register a bond in the securities master.

The 2.8.0 form, restyled: a panel form, Tattva input wells, the one primary action. The submit handler
(validation messages, the INSERTs, the notification) is the 2.8.0 handler verbatim — validation errors
now land in the notice rail (``form_error``) instead of an ``st.error`` box.
"""

from __future__ import annotations

import uuid
from datetime import date

import streamlit as st

from core.config import BOND_TYPES, CREDIT_RATINGS, DAY_COUNT_CONVENTIONS, FREQUENCIES, logger
from core.db import db_execute, db_query
from ui.components import render_section_header
from ui.notices import form_error, set_notification


def render_add_security_page():
    """Operations · Add Security — register a bond in the master before it can be transacted."""
    render_section_header("Add Security", "Register a bond in the securities master before recording a transaction against it. Coupon is entered in percent; face value is per unit.", icon="cube", accent="cyan")

    with st.form("add_sec"):
        c1, c2 = st.columns(2, gap="small")
        with c1:
            issuer = st.text_input("Issuer Name")
            isin = st.text_input("ISIN")
            mat = st.date_input("Maturity Date")
            freq = st.selectbox("Coupon Frequency", FREQUENCIES)
        with c2:
            cpn = st.number_input("Coupon Rate (%)", 0.0, 100.0, step=0.01, format="%.2f")
            fv = st.number_input("Face Value (per unit)", min_value=0.0, step=100.0, value=1000.0)
            btype = st.selectbox("Bond Type", BOND_TYPES)
            cr = st.selectbox("Credit Rating", CREDIT_RATINGS)

        c3, c4 = st.columns(2, gap="small")
        with c3:
            sector = st.text_input("Sector", value="Financials")
            listing = st.selectbox("Listing", ["Unlisted", "NSE", "BSE", "Both"])
        with c4:
            idate = st.date_input("Issue Date", value=None)
            dc = st.selectbox("Day Count", DAY_COUNT_CONVENTIONS)

        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Add security", type="primary")

        if submitted:
            if not issuer or not isin:
                form_error("Issuer and ISIN are required.")
            elif mat <= date.today():
                form_error("Maturity date must be in the future.")
            elif idate is not None and mat <= idate:
                form_error("Maturity date must be after the issue date.")
            elif not db_query("SELECT 1 FROM securities WHERE isin=?", (isin,)).empty:
                form_error(f"ISIN **{isin}** already exists in the securities master.")
            else:
                bid = str(uuid.uuid4())
                ok = db_execute(
                    "INSERT INTO securities VALUES (?,?,?,?,?,?,?)",
                    (bid, issuer, isin, mat.isoformat(), freq, cpn / 100, fv),
                )
                if ok:
                    db_execute(
                        "INSERT INTO security_metadata "
                        "(bond_id, bond_type, credit_rating, day_count, issue_date, listing, sector, notes) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (bid, btype, cr, dc, idate.isoformat() if idate else None, listing, sector, notes),
                    )
                    set_notification(f"Security **{issuer}** ({isin}) added!", "success")
                    logger.info(f"Added security: {isin}")
                    st.rerun()
