"""
Nivesa — Operations · Record Transaction: a buy, sell, interest receipt or principal repayment.

The 2.8.0 form, restyled (it no longer also lives in an expander on the ledger — recording has one
place). The submit handler — the date bounds, the fat-finger price confirmation, the units-held and
repayment-cap checks, the INSERT, the pro-rata face step-down and the chronology check that rolls
the whole entry back — is the 2.8.0 handler verbatim; its messages land in the notice rail.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import date

import pandas as pd
import streamlit as st

from core.config import ACCOUNTS, TRANSACTION_TYPES, logger
from core.db import _connect, claim_face_adjustment, db_query, face_step_claimed, validate_ledger_chronology
from core.formatting import fmt_inr
from ui.components import render_note, render_section_header
from ui.notices import form_error, form_warning, set_notification
from ui.pages._forms import render_no_securities, render_terms, security_terms


def render_record_transaction_page():
    """Operations · Record Transaction — a buy, sell, interest receipt or principal repayment."""
    render_section_header("Record Transaction", "Record a buy, sell, interest receipt or principal repayment against a security in the master. Every entry is checked against the bond's dates, the units held and the running balance of every account before it is saved.", icon="zap", accent="emerald")

    secs = db_query("SELECT bond_id, issuer, isin FROM securities")
    if secs.empty:
        render_no_securities("Record Transaction")
        return

    opts = {f"{r['issuer']} — {r['isin']}": r['bond_id'] for _, r in secs.iterrows()}
    with st.container(key="filterbar"):
        sel = st.selectbox("Select Security", opts.keys(), index=None, placeholder="Choose…")
    if not sel:
        return

    bid = opts[sel]

    # Show selected security context (reactive to dropdown change)
    sec_info = db_query(
        "SELECT s.coupon_rate, s.face_value, s.frequency, s.maturity_date, "
        "COALESCE(m.credit_rating, 'Unrated') as credit_rating, m.issue_date "
        "FROM securities s LEFT JOIN security_metadata m ON s.bond_id=m.bond_id "
        "WHERE s.bond_id=?", (bid,),
    )
    if not sec_info.empty:
        si = sec_info.iloc[0]
        render_terms(security_terms(si))

    # Account and date outside the form so changes trigger immediate rerun
    sel_c1, sel_c2, sel_c3 = st.columns(3, gap="small")
    with sel_c1:
        ttype = st.selectbox("Transaction Type", TRANSACTION_TYPES)
    with sel_c2:
        account = st.selectbox("Account", ACCOUNTS, key="rec_acct")
    with sel_c3:
        tdate = st.date_input("Date", max_value=date.today(), key="rec_date")

    # For principal repayment, show live units context (reactive to account change)
    units_by_account = pd.Series(dtype='float64')
    total_units_all = 0.0
    if ttype == 'Principal_Repayment':
        acct_txns = db_query("SELECT account, units FROM transactions WHERE bond_id=?", (bid,))
        if not acct_txns.empty:
            units_by_account = acct_txns.groupby('account')['units'].sum()
            total_units_all = acct_txns['units'].sum()
        current_units = units_by_account.get(account, 0.0)
        render_note(f"{account} holds {current_units:.0f} units · all accounts {total_units_all:.0f} units")

    with st.form("rec_txn"):
        if ttype in ["Buy", "Sell"]:
            c1, c2 = st.columns(2, gap="small")
            with c1:
                units = st.number_input("Units", min_value=1, step=1)
            with c2:
                price = st.number_input("Price", min_value=0.0, format="%.4f")
            amount = units * price
            render_note(f"Amount {fmt_inr(amount)}")
            
            # Fat-finger pricing check warning
            price_dev = abs(price - si['face_value']) / si['face_value'] if si['face_value'] > 0 else 0.0
            if price_dev > 0.5 and price > 0:
                form_warning(f"Warning: Price {fmt_inr(price)} deviates by >50% from par value {fmt_inr(si['face_value'])}.")
                st.checkbox("Confirm this price deviation is correct", key="confirm_price_rec")
        elif ttype == 'Principal_Repayment':
            current_units = units_by_account.get(account, 0.0)
            amount = st.number_input("Total Amount", min_value=0.0, format="%.2f")
            if current_units > 0 and amount > 0:
                render_note(f"Per unit (this account) {fmt_inr(amount / current_units)}")
            units = 0.0
            price = 0.0
        else:
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            units = 0.0
            price = 0.0

        notes = st.text_area("Notes")

        if st.form_submit_button("Record transaction", type="primary"):
            # 1. Date boundaries check
            issue_date = pd.to_datetime(si['issue_date']).date() if pd.notna(si['issue_date']) else None
            maturity_date = pd.to_datetime(si['maturity_date']).date()
            if issue_date is not None and tdate < issue_date:
                form_error(f"Transaction date ({tdate}) cannot be before the bond's issue date ({issue_date}).")
                st.stop()
            if tdate > maturity_date:
                form_error(f"Transaction date ({tdate}) cannot be after the bond's maturity date ({maturity_date}).")
                st.stop()

            # 2. Fat-finger check confirmation
            if ttype in ["Buy", "Sell"]:
                price_dev = abs(price - si['face_value']) / si['face_value'] if si['face_value'] > 0 else 0.0
                if price_dev > 0.5 and not st.session_state.get("confirm_price_rec", False):
                    form_error("Please check the confirmation box to verify the unusual transaction price.")
                    st.stop()

            # 3. Sell validation: check sufficient units
            if ttype == 'Sell':
                held = db_query(
                    "SELECT SUM(units) as total FROM transactions WHERE bond_id=? AND account=? AND transaction_type IN ('Buy', 'Sell')",
                    (bid, account),
                )
                raw = held['total'].iloc[0] if not held.empty else 0
                available = float(raw) if pd.notna(raw) else 0.0
                if units > available:
                    form_error(f"Insufficient units. Available: **{available:.0f}**, trying to sell: **{units:.0f}**")
                    st.stop()

            # 4. Repayment cap check
            if ttype == 'Principal_Repayment':
                held = db_query(
                    "SELECT SUM(units) as total FROM transactions WHERE bond_id=? AND account=? AND transaction_type IN ('Buy', 'Sell')",
                    (bid, account),
                )
                raw = held['total'].iloc[0] if not held.empty else 0
                current_units = float(raw) if pd.notna(raw) else 0.0

                # face_value holds the CURRENT outstanding face per unit, so the
                # maximum still repayable is units*face_value. (Subtracting the
                # prior repaid total here as well double-counted amortization and
                # wrongly blocked legitimate repayments.)
                #
                # But a bond redeemed pro-rata across several accounts on the
                # same date steps face_value down only ONCE, when the first
                # account's entry claims it. Measuring the later accounts against
                # the already-reduced face rejected their legitimate share — on a
                # full redemption face_value hits 0 and the second account could
                # never record anything. Add the claimed step-down back so every
                # account in the group is checked against the same pre-redemption
                # face.
                outstanding_face = current_units * (si['face_value'] + face_step_claimed(bid, tdate.isoformat()))
                if amount > outstanding_face + 1e-2:
                    form_error(f"Repayment amount ({fmt_inr(amount)}) cannot exceed outstanding face value ({fmt_inr(outstanding_face)}).")
                    st.stop()

            tid = str(uuid.uuid4())
            stored_units = -abs(units) if ttype == 'Sell' else abs(units)

            # Compute per-unit adjustment for principal repayment
            if ttype == 'Principal_Repayment':
                price = amount / current_units if current_units > 0 else 0.0

            stored_amount = units * price if ttype in ["Buy", "Sell"] else amount

            try:
                with closing(_connect()) as conn, conn:
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO transactions "
                        "(transaction_id, bond_id, account, trade_date, transaction_type, units, price, amount, notes) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (tid, bid, account, tdate.isoformat(), ttype, stored_units, price, stored_amount, notes)
                    )

                    # Principal repayments amortize the bond: step the security's
                    # outstanding face value per unit down by this repayment's
                    # per-unit amount, so it stays the "CURRENT outstanding face
                    # per unit" that positions, YTC, and the repayment cap check
                    # all assume it already is. A bond redeemed pro-rata across
                    # multiple accounts on the same date must only apply this
                    # step-down once (see claim_face_adjustment).
                    if ttype == 'Principal_Repayment':
                        claim_face_adjustment(c, bid, tdate.isoformat(), tid, price)

                    # 5. Chronological balance check
                    ok, offending_acct, offending_date = validate_ledger_chronology(bid, conn)
                    if not ok:
                        form_error(f"Transaction rejected. This would cause Account **{offending_acct}** to have negative holdings on {pd.to_datetime(offending_date).strftime('%d %b %Y')}.")
                        st.stop()
                        
                    conn.commit()

                set_notification(f"**{ttype.replace('_', ' ')}** recorded!", "success")
                logger.info(f"Recorded {ttype} for {bid}")
                st.rerun()
            except sqlite3.Error as e:
                form_error(f"Transaction failed: {e}")
                logger.error(f"Transaction failed: {e}")
