"""
Nivesa — Operations · Edit Transaction: correct or delete one ledger entry.

The 2.8.0 form, restyled; Update is the primary action and Delete a secondary ("Delete transaction").
Both handlers — the type-change guard, date bounds, price confirmation, units and repayment-cap checks,
the UPDATE / DELETE, the face step-down re-pricing / release / re-claim and the chronology check that
rolls the change back — are the 2.8.0 handlers verbatim; their messages land in the notice rail.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date

import pandas as pd
import streamlit as st

from core.config import ACCOUNTS, TRANSACTION_TYPES
from core.db import (_connect, claim_face_adjustment, db_query, face_step_claimed, release_face_adjustment,
                     validate_ledger_chronology)
from core.formatting import fmt_inr
from ui.components import render_note, render_section_header
from ui.notices import form_error, form_warning, set_notification
from ui.pages._forms import _safe_index, render_no_transactions, render_terms, security_terms


def render_edit_transaction_page():
    """Operations · Edit Transaction — correct or delete one ledger entry."""
    render_section_header("Edit Transaction", "Correct or delete one entry in the ledger. A change is checked exactly as a new entry is; a type change is refused — delete the entry and record it again.", icon="layers", accent="rose")

    txns = db_query(
        "SELECT t.*, s.issuer, s.isin FROM transactions t "
        "JOIN securities s ON t.bond_id=s.bond_id ORDER BY t.trade_date DESC"
    )
    if txns.empty:
        render_no_transactions("Edit Transaction")
        return

    txns['trade_date'] = pd.to_datetime(txns['trade_date']).dt.strftime('%Y-%m-%d')
    opts = {
        f"{r['trade_date']} | {r['transaction_type']} | {r['issuer']} | "
        f"{fmt_inr(r['amount'])} | {r['transaction_id'][:8]}": r['transaction_id']
        for _, r in txns.iterrows()
    }
    with st.container(key="filterbar"):
        sel = st.selectbox("Select Transaction", opts.keys(), index=None, placeholder="Choose…")
    if not sel:
        return

    tid = opts[sel]
    txn = txns[txns['transaction_id'] == tid].iloc[0]

    # Reactive security context panel
    sec_ctx = db_query(
        "SELECT s.coupon_rate, s.face_value, s.frequency, s.maturity_date, "
        "COALESCE(m.credit_rating, 'Unrated') as credit_rating, m.issue_date "
        "FROM securities s LEFT JOIN security_metadata m ON s.bond_id=m.bond_id "
        "WHERE s.bond_id=?", (txn['bond_id'],),
    )
    if not sec_ctx.empty:
        sc = sec_ctx.iloc[0]
        render_terms(security_terms(sc))

    orig_type = txn['transaction_type']

    with st.form("edit_txn"):
        render_note(f"Transaction {tid[:12]}…")
        st.text_input("Security", value=f"{txn['issuer']} ({txn['isin']})", disabled=True)

        c1, c2 = st.columns(2, gap="small")
        with c1:
            acct = st.selectbox("Account", ACCOUNTS, index=_safe_index(ACCOUNTS, txn['account']))
            td = st.date_input("Date", max_value=date.today(), value=pd.to_datetime(txn['trade_date']).date())
            tt = st.selectbox("Type", TRANSACTION_TYPES, index=_safe_index(TRANSACTION_TYPES, orig_type))
        with c2:
            if orig_type in ["Buy", "Sell"]:
                u = st.number_input("Units", min_value=0, step=1, value=int(abs(txn['units'])))
                p = st.number_input("Price", min_value=0.0, format="%.4f", value=float(txn['price']))
                a = u * p
                render_note(f"Amount {fmt_inr(a)}")
                
                # Fat-finger pricing check warning
                price_dev = abs(p - sc['face_value']) / sc['face_value'] if sc['face_value'] > 0 else 0.0
                if price_dev > 0.5 and p > 0:
                    form_warning(f"Warning: Price {fmt_inr(p)} deviates by >50% from par value {fmt_inr(sc['face_value'])}.")
                    st.checkbox("Confirm this price deviation is correct", key="confirm_price_edit")
            else:
                u = 0
                p = 0.0
                a = st.number_input("Amount", min_value=0.0, format="%.2f", value=float(txn['amount']))

        notes = st.text_area("Notes", value=txn['notes'] or '')

        col_update, col_delete = st.columns([3, 1], gap="small")
        with col_update:
            update_btn = st.form_submit_button("Update transaction", type="primary", width='stretch')
        with col_delete:
            delete_btn = st.form_submit_button("Delete transaction", width='stretch')

        if update_btn:
            old_type = txn['transaction_type']
            old_amount = float(txn['amount'])
            bond_id = txn['bond_id']

            # Guard: prevent changing transaction type (Bug 5)
            if tt != old_type:
                form_error(f"Changing transaction type from **{old_type}** to **{tt}** is not allowed. "
                         "Delete this transaction and create a new one instead.")
            else:
                # 1. Date boundaries check
                issue_date = pd.to_datetime(sc['issue_date']).date() if pd.notna(sc['issue_date']) else None
                maturity_date = pd.to_datetime(sc['maturity_date']).date()
                if issue_date is not None and td < issue_date:
                    form_error(f"Transaction date ({td}) cannot be before the bond's issue date ({issue_date}).")
                    st.stop()
                if td > maturity_date:
                    form_error(f"Transaction date ({td}) cannot be after the bond's maturity date ({maturity_date}).")
                    st.stop()

                # 2. Fat-finger check confirmation
                if tt in ["Buy", "Sell"]:
                    price_dev = abs(p - sc['face_value']) / sc['face_value'] if sc['face_value'] > 0 else 0.0
                    if price_dev > 0.5 and not st.session_state.get("confirm_price_edit", False):
                        form_error("Please check the confirmation box to verify the unusual transaction price.")
                        st.stop()

                if tt in ["Buy", "Sell"]:
                    final_amount = u * p
                    final_price = p
                    final_units = -abs(u) if tt == 'Sell' else abs(u)

                    # 3. Sell validation: ensure sufficient units
                    if tt == 'Sell':
                        held = db_query(
                            "SELECT SUM(units) as total FROM transactions "
                            "WHERE bond_id=? AND account=? AND transaction_id!=? AND transaction_type IN ('Buy', 'Sell')",
                            (bond_id, acct, tid),
                        )
                        raw = held['total'].iloc[0] if not held.empty else 0
                        available = float(raw) if pd.notna(raw) else 0.0
                        if abs(final_units) > available:
                            form_error(f"Insufficient units. Available: **{available:.0f}**, trying to sell: **{abs(final_units):.0f}**")
                            st.stop()
                elif tt == 'Principal_Repayment':
                    final_amount = a
                    final_units = 0.0
                    held = db_query(
                        "SELECT SUM(units) as total FROM transactions "
                        "WHERE bond_id=? AND account=? AND transaction_id!=? AND transaction_type IN ('Buy', 'Sell')",
                        (bond_id, acct, tid),
                    )
                    raw = held['total'].iloc[0] if not held.empty else 0
                    current_units = float(raw) if pd.notna(raw) else 0.0
                    
                    # 4. Repayment cap check
                    # face_value = current outstanding face per unit; max
                    # repayable is units*face_value (see record-transaction path).
                    # Two step-downs may need adding back before the comparison:
                    # this row's own, if it currently owns one (face_value
                    # already reflects it), and any other owner in the group this
                    # row is moving TO.
                    face_before = sc['face_value'] + face_step_claimed(bond_id, td.isoformat(), exclude_tid=tid)
                    if int(txn['owns_face_adj']) == 1:
                        face_before += float(txn['price'])
                    outstanding_face = current_units * face_before
                    if a > outstanding_face + 1e-2:
                        form_error(f"Repayment amount ({fmt_inr(a)}) cannot exceed outstanding face value ({fmt_inr(outstanding_face)}).")
                        st.stop()
                        
                    final_price = a / current_units if current_units > 0 else 0.0
                else:
                    final_amount = a
                    final_price = 0.0
                    final_units = 0.0

                try:
                    with closing(_connect()) as conn, conn:
                        c = conn.cursor()
                        c.execute(
                            "UPDATE transactions SET account=?, trade_date=?, transaction_type=?, "
                            "units=?, price=?, amount=?, notes=? WHERE transaction_id=?",
                            (acct, td.isoformat(), tt, final_units, final_price, final_amount, notes, tid),
                        )

                        # Keep face_value in sync with the edited repayment. If
                        # this row still owns the step-down for the same (bond,
                        # date) group, just re-price it in place — running a
                        # full release+reclaim here would hand ownership to
                        # another same-date row (a different account's entry)
                        # and silently drop this edit. Only release/reclaim
                        # when the row is moving to a different date group or
                        # wasn't the owner to begin with.
                        if tt == 'Principal_Repayment':
                            old_date = txn['trade_date']
                            was_owner = int(txn['owns_face_adj']) == 1
                            if was_owner and old_date == td.isoformat():
                                if final_price != float(txn['price']):
                                    c.execute(
                                        "UPDATE securities SET face_value = face_value + ? - ? WHERE bond_id=?",
                                        (float(txn['price']), final_price, bond_id),
                                    )
                            else:
                                if was_owner:
                                    release_face_adjustment(c, bond_id, old_date, tid, float(txn['price']))
                                claim_face_adjustment(c, bond_id, td.isoformat(), tid, final_price)

                        # 5. Chronological balance check
                        ok, offending_acct, offending_date = validate_ledger_chronology(bond_id, conn)
                        if not ok:
                            form_error(f"Transaction update rejected. This would cause Account **{offending_acct}** to have negative holdings on {pd.to_datetime(offending_date).strftime('%d %b %Y')}.")
                            st.stop()
                            
                        conn.commit()
                        
                    set_notification("Transaction updated!", "success")
                    st.rerun()
                except sqlite3.Error as e:
                    form_error(f"Update failed: {e}")

        if delete_btn:
            bond_id = txn['bond_id']
            try:
                with closing(_connect()) as conn, conn:
                    c = conn.cursor()

                    # Reverse this repayment's per-unit face-value step-down
                    # (promoting another same-date repayment to own it, if one
                    # exists) BEFORE deleting the row, since the promotion
                    # query needs to see the sibling rows still in the table.
                    if orig_type == 'Principal_Repayment' and int(txn['owns_face_adj']) == 1:
                        release_face_adjustment(c, bond_id, txn['trade_date'], tid, float(txn['price']))

                    c.execute("DELETE FROM transactions WHERE transaction_id=?", (tid,))

                    # 5. Chronological balance check on deletion
                    ok, offending_acct, offending_date = validate_ledger_chronology(bond_id, conn)
                    if not ok:
                        form_error(f"Transaction deletion rejected. This would cause Account **{offending_acct}** to have negative holdings on {pd.to_datetime(offending_date).strftime('%d %b %Y')}.")
                        st.stop()
                        
                    conn.commit()
                    
                set_notification("Transaction deleted!", "success")
                st.rerun()
            except sqlite3.Error as e:
                form_error(f"Deletion failed: {e}")
