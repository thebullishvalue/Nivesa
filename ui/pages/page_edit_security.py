"""
Nivesa — Operations · Edit Security: correct a bond's terms and metadata.

The 2.8.0 form, restyled. The submit handler (validation, both UPDATEs, the notification) is the 2.8.0
handler verbatim; its messages and the retroactive-change caution land in the notice rail.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.bonds import calc_days_to_maturity
from core.config import BOND_TYPES, CREDIT_RATINGS, DAY_COUNT_CONVENTIONS, FREQUENCIES, logger
from core.db import db_execute, db_query, ensure_metadata
from core.formatting import fmt_inr, fmt_pct
from ui.components import render_note, render_section_header
from ui.notices import form_error, form_warning, set_notification
from ui.pages._forms import _safe_index, render_no_securities, render_terms


def render_edit_security_page():
    """Operations · Edit Security — correct a bond's terms and metadata."""
    render_section_header("Edit Security", "Correct a bond's terms or metadata. The ISIN is fixed; a change to face value or coupon re-prices every position in it.", icon="scale", accent="violet")

    secs = db_query("SELECT * FROM securities")
    if secs.empty:
        render_no_securities("Edit Security")
        return

    opts = {f"{r['issuer']} — {r['isin']}": r['bond_id'] for _, r in secs.iterrows()}
    with st.container(key="filterbar"):
        sel = st.selectbox("Select Security", opts.keys(), index=None, placeholder="Choose…")
    if not sel:
        return

    bid = opts[sel]
    sec = secs[secs['bond_id'] == bid].iloc[0]
    ensure_metadata(bid)

    meta_df = db_query("SELECT * FROM security_metadata WHERE bond_id=?", (bid,))
    meta = meta_df.iloc[0] if not meta_df.empty else None

    txn_count = db_query("SELECT COUNT(*) as c FROM transactions WHERE bond_id=?", (bid,))['c'].iloc[0]

    # Reactive holdings context panel
    holdings = db_query(
        "SELECT account, SUM(units) as units, SUM(amount) as cost "
        "FROM transactions WHERE bond_id=? AND transaction_type IN ('Buy', 'Sell') GROUP BY account HAVING SUM(units) > 0",
        (bid,),
    )
    dtm = calc_days_to_maturity(sec['maturity_date'])
    mat_str = pd.to_datetime(sec['maturity_date']).strftime('%d %b %Y')
    holders = " · ".join(
        f"{r['account']}: {int(r['units'])} units ({fmt_inr(r['cost'])})"
        for _, r in holdings.iterrows()
    ) if not holdings.empty else "No holdings"
    render_terms([
        ("Coupon", fmt_pct(sec['coupon_rate'])), ("Face / unit", fmt_inr(sec['face_value'])),
        ("Maturity", f"{mat_str} · {dtm}d"), ("Transactions", str(int(txn_count))), ("Holdings", holders),
    ])

    listing_opts = ["Unlisted", "NSE", "BSE", "Both"]

    with st.form("edit_sec"):
        render_note(f"Editing {sec['issuer']} · {sec['isin']}")
        st.text_input("ISIN", value=sec['isin'], disabled=True)

        c1, c2 = st.columns(2, gap="small")
        with c1:
            issuer = st.text_input("Issuer", value=sec['issuer'])
            mat = st.date_input("Maturity", value=pd.to_datetime(sec['maturity_date']).date())
            freq = st.selectbox("Frequency", FREQUENCIES, index=FREQUENCIES.index(sec['frequency']))
        with c2:
            cpn = st.number_input("Coupon (%)", 0.0, 100.0, step=0.01, format="%.2f", value=sec['coupon_rate'] * 100)
            fv = st.number_input("Face Value", step=100.0, value=sec['face_value'])
            btype = st.selectbox(
                "Bond Type", BOND_TYPES,
                index=_safe_index(BOND_TYPES, meta['bond_type'] if meta is not None else None),
            )

        c3, c4 = st.columns(2, gap="small")
        with c3:
            cr = st.selectbox(
                "Credit Rating", CREDIT_RATINGS,
                index=_safe_index(CREDIT_RATINGS, meta['credit_rating'] if meta is not None else None, len(CREDIT_RATINGS) - 1),
            )
            sector = st.text_input("Sector", value=meta['sector'] if meta is not None else 'Financials')
        with c4:
            listing = st.selectbox(
                "Listing", listing_opts,
                index=_safe_index(listing_opts, meta['listing'] if meta is not None else None),
            )
            meta_idate = pd.to_datetime(meta['issue_date']).date() if meta is not None and pd.notna(meta['issue_date']) else None
            idate = st.date_input("Issue Date", value=meta_idate)
            dc = st.selectbox(
                "Day Count", DAY_COUNT_CONVENTIONS,
                index=_safe_index(DAY_COUNT_CONVENTIONS, meta['day_count'] if meta is not None else None),
            )

        notes = st.text_area("Notes", value=meta['notes'] if meta is not None else '')

        if txn_count > 0:
            form_warning(f"{txn_count} transactions exist. Editing face value changes all calculations retroactively.")

        if st.form_submit_button("Update security", type="primary"):
            if not issuer:
                form_error("Issuer required.")
            elif idate is not None and mat <= idate:
                form_error("Maturity date must be after the issue date.")
            else:
                db_execute(
                    "UPDATE securities SET issuer=?, maturity_date=?, frequency=?, coupon_rate=?, face_value=? WHERE bond_id=?",
                    (issuer, mat.isoformat(), freq, cpn / 100, fv, bid),
                )
                db_execute(
                    "UPDATE security_metadata SET bond_type=?, credit_rating=?, day_count=?, issue_date=?, listing=?, sector=?, notes=? WHERE bond_id=?",
                    (btype, cr, dc, idate.isoformat() if idate else None, listing, sector, notes, bid),
                )
                set_notification(f"**{issuer}** updated!", "success")
                logger.info(f"Updated security: {bid}")
                st.rerun()
