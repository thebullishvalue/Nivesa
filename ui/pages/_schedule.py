"""
Nivesa — the redemption schedule in the Operations pages.

  · ``render_schedule_editor`` (Edit Security): the bond's contractual instalments — what it pays back,
    when, per bond — with what has been paid, what is due and not recorded, and what is to come; entered
    as lines (``date, ₹ per bond``) or filled as N equal instalments, checked against the bond's terms.
  · ``render_due_repayments`` (Record Transaction): every scheduled instalment whose date has passed
    with no repayment recorded for an account that held the bond then — recorded for all of them, or for
    one security, in one step.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core import schedule as sch
from core.formatting import fmt_inr
from ui.components import render_note, render_sub_header, render_table_panel
from ui.notices import form_error, form_warning, set_notification

_EVERY = {"Monthly": 1, "Quarterly": 3, "Half-yearly": 6, "Yearly": 12}


def render_schedule_editor(bid: str, sec, meta) -> None:
    render_sub_header("Payment terms")
    face = sch.original_face(bid)
    maturity = pd.to_datetime(sec["maturity_date"]).date()
    issue = pd.to_datetime(meta["issue_date"]).date() if meta is not None and pd.notna(meta["issue_date"]) else None
    cur = sch.schedule_frame(bid)
    due = sch.due_unrecorded()
    due = due[due["bond_id"] == bid] if not due.empty else due

    if cur.empty:
        render_note(f"No schedule: the whole face ({fmt_inr(face)} per bond at issue) is treated as repaid at maturity, "
                    f"or on the pattern of the repayments already recorded. If this bond repays in instalments, "
                    f"enter them below from its offer document or the platform it was bought on.")
    else:
        today = date.today()
        due_dates = set(due["due_date"]) if not due.empty else set()
        view = pd.DataFrame({
            "due": pd.to_datetime(cur["due_date"]),
            "per_bond": cur["principal_per_unit"],
            "share": cur["principal_per_unit"] / face if face else 0.0,
            "status": [("Due, not recorded" if pd.to_datetime(d).date() in due_dates else
                        ("Recorded" if pd.to_datetime(d).date() <= today else "To come")) for d in cur["due_date"]],
        })
        total = float(cur["principal_per_unit"].sum())
        render_table_panel(
            view, "schedule", context=f"REDEMPTION SCHEDULE · {len(view)} instalments · {fmt_inr(total)} of {fmt_inr(face)} "
                                      f"per bond · {cur['source'].iloc[0] or 'entered'}",
            max_height=360, label_col="due",
            col_labels={"due": "Due", "per_bond": "Per bond", "share": "Of face", "status": "Status"},
            col_format={"per_bond": fmt_inr, "share": lambda v: f"{v:.2%}"},
        )

    with st.form("schedule_form"):
        day = interest_day_field("sched", sch.coupon_days().get(bid))
        lines = "\n".join(f"{pd.to_datetime(r['due_date']):%Y-%m-%d}, {r['principal_per_unit']:.2f}"
                          for _, r in cur.iterrows())
        fields = schedule_fields("sched", lines=lines,
                                 source=cur["source"].iloc[0] if not cur.empty and cur["source"].iloc[0] else "")
        saved = st.form_submit_button("Save payment terms", type="primary")

    if not saved:
        return
    try:
        rows = schedule_rows(fields, face)
    except ValueError as e:
        form_error(f"Payment terms not saved: {e}.")
        st.stop()
    errors, warnings = sch.check(rows, face=float(sec["face_value"]), issue=issue, maturity=maturity)
    if errors:
        form_error("Payment terms not saved — repayment schedule: " + "; ".join(errors) + ".")
        st.stop()
    for w in warnings:
        form_warning(w[0].upper() + w[1:] + ".")
    sch.set_coupon_day(bid, day)
    sch.replace_schedule(bid, rows, source=fields["source"] or "entered")
    what = f"{len(rows)} instalments" if rows else "repays at maturity"
    set_notification(f"Payment terms saved for **{sec['issuer']}**: {what}.", "success")
    st.rerun()


#: "Interest paid on": the maturity date's day (stored as none), a day of the month, or the month's last day.
INTEREST_DAYS = ["Maturity date's day"] + [f"{d}{'st' if d in (1, 21) else 'nd' if d in (2, 22) else 'rd' if d in (3, 23) else 'th'} of the month"
                                           for d in range(1, 31)] + ["Last day of the month"]


def interest_day_field(key: str, current: "int | None" = None) -> "int | None":
    """The bond's interest day, drawn inside the caller's form; None = the maturity date's day."""
    idx = 0 if current is None else (31 if int(current) >= 31 else int(current))
    pick = st.selectbox("Interest paid on", INTEREST_DAYS, index=idx, key=f"{key}_day",
                        help="The day of the month the bond pays its interest. Many NCDs pay on the 1st or at "
                             "month-end and make a last, shorter payment at maturity; most pay on the maturity "
                             "date's day. Interest is counted by actual days, on the bond's day count.")
    i = INTEREST_DAYS.index(pick)
    return None if i == 0 else i


def schedule_fields(key: str, *, lines: str = "", source: str = "") -> dict:
    """The schedule inputs, drawn inside the caller's form (Add Security and Edit Security share them):
    instalment lines, the equal-instalments fill, and the source. Returns their values."""
    text = st.text_area("One instalment per line: date, ₹ per bond", value=lines, height=140,
                        key=f"{key}_lines", placeholder="2027-03-27, 2500\n2027-06-27, 2500",
                        help="Leave empty for a bond that repays its whole face at maturity. Dates as YYYY-MM-DD "
                             "or DD-MM-YYYY; amounts are rupees per bond (against the face at issue). Instalments "
                             "still to come may not add up to more than the current face; any rest is repaid at "
                             "maturity.")
    q1, q2, q3, q4 = st.columns(4, gap="small")
    with q1:
        quick = st.checkbox("Fill equal instalments instead", key=f"{key}_quick")
    with q2:
        first = st.date_input("First instalment", value=None, key=f"{key}_first")
    with q3:
        every = st.selectbox("Every", list(_EVERY), index=1, key=f"{key}_every")
    with q4:
        count = st.number_input("Instalments", min_value=1, max_value=120, value=4, step=1, key=f"{key}_count")
    src = st.text_input("Schedule source", value=source, key=f"{key}_source",
                        placeholder="e.g. Key Information Document, platform repayment schedule")
    return {"text": text, "quick": quick, "first": first, "every": every, "count": int(count), "source": src.strip()}


def schedule_rows(fields: dict, face_at_issue: float) -> "list[tuple]":
    """The instalments the fields describe: N equal parts of ``face_at_issue`` from the first date, or the
    lines as typed (empty: no schedule). Raises ValueError with what to fix."""
    if fields["quick"]:
        if fields["first"] is None:
            raise ValueError("pick the date of the first instalment to fill equal instalments")
        return sch.equal_instalments(fields["first"], _EVERY[fields["every"]], fields["count"], face_at_issue)
    return sch.parse_lines(fields["text"])


def render_due_repayments() -> None:
    due = sch.due_unrecorded()
    if due.empty:
        return
    render_sub_header("Scheduled repayments not recorded")
    n_b = due["bond_id"].nunique()
    render_note(f"{len(due)} instalment entr{'ies' if len(due) != 1 else 'y'} across {n_b} securit{'ies' if n_b != 1 else 'y'} "
                f"({fmt_inr(due['amount'].sum())}) are past their scheduled date with no repayment recorded for an account "
                f"that held the bond then. Check each against your bank statement, then record them here.")
    view = due.assign(due_date=pd.to_datetime(due["due_date"]))[
        ["issuer", "isin", "due_date", "account", "units", "principal_per_unit", "amount"]]
    render_table_panel(
        view.reset_index(drop=True), "due-repayments",
        context=f"DUE, NOT RECORDED · {len(view)} entries · {fmt_inr(due['amount'].sum())}",
        max_height=360, label_col="issuer",
        col_labels={"issuer": "Issuer", "isin": "ISIN", "due_date": "Due", "account": "Account", "units": "Bonds",
                    "principal_per_unit": "Per bond", "amount": "Amount"},
        col_format={"principal_per_unit": fmt_inr, "amount": fmt_inr, "units": lambda v: f"{v:,.0f}"},
    )
    groups = {f"{r.issuer} — {r.isin}": r.bond_id for r in due.drop_duplicates("bond_id").itertuples()}
    with st.container(key="filterbar-due"):
        c1, c2 = st.columns([3, 1], gap="small")
        with c1:
            pick = st.selectbox("Record for", ["All securities above", *groups], key="due_pick")
        with c2:
            go = st.button("Record repayments", type="primary", width="stretch", key="due_record")
    if go:
        rows = due if pick == "All securities above" else due[due["bond_id"] == groups[pick]]
        ok, msg = sch.record_due(rows)
        if ok:
            set_notification(f"Scheduled repayments: {msg}.", "success")
            st.rerun()
        form_error(f"Not recorded: {msg}.")
