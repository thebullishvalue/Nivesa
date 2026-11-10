"""
Nivesa — Operations · Ledger: the audit trail — every entry the book is built from.

Tattva's "The Record" grammar, for a ledger: the section header states what the ledger holds, with live
numbers and the sign convention → a filterbar strip scoping the one table (the 2.8.0 page's own filters:
Account, Type, Search) → the table panel, windowed by trade date (the window control sits in its header),
newest first, capped on screen at 300 rows → the exports the 2.8.0 app offered, unchanged → a note.

The two exports are the 2.8.0 ones, byte for byte in content:
  · CSV — the Transaction Ledger page's export: the rows the three filters select, every date, trade
    dates as ``dd Mon yyyy`` (``nivesa_ledger.csv``);
  · Excel — the dashboard ledger tab's export: every transaction for the account filter (it never had a
    type or issuer filter), with its security, ISIN and notes (``nivesa_ledger_YYYYmmdd_HHMM.xlsx``).
The window and the row cap frame the screen only; neither export is cut by them.

The old "Record New Transaction" expander is gone (rule 133): recording has one page. Every figure comes
from ``core.views`` (``ledger_page`` / ``ledger_tab``, the 2.8.0 queries verbatim); nothing here computes.
"""

from __future__ import annotations

import io
from datetime import date, datetime

import pandas as pd
import streamlit as st

from core.config import ACCOUNTS, TRANSACTION_TYPES
from core.formatting import fmt_inr
from core.views import ledger_page, ledger_tab
from ui.components import (WINDOWS, esc, panel, render_empty_state, render_note, render_section_header,
                           render_table_panel, window_cutoff)

#: On-screen cap (HTML tables put every row in the DOM); the exports carry every row.
CAP = 300

#: The table's columns: (source column, header, formatter or None). Units keep the sign the book stores
#: (+ bought, − sold) and are tinted by it; a receipt or repayment moves cash, not units, so its units —
#: and a receipt's price — read "—", as 2.8.0 printed "-".
_COLS = (
    ("trade_date", "Date", None),
    ("issuer", "Issuer", None),
    ("isin", "ISIN", None),
    ("account", "Account", None),
    ("transaction_type", "Type", None),
    ("units", "Units", lambda v: "—" if v == 0 else f"{v:+,.0f}".replace("-", "−")),
    ("price", "Price / Unit", lambda v: "—" if v == 0 else fmt_inr(v)),
    ("amount", "Amount", fmt_inr),
    ("notes", "Notes", None),
)


def _type_label(t: str) -> str:
    return "All" if t == "All" else str(t).replace("_", " ")


def ledger_csv(ledger: pd.DataFrame) -> str:
    """The 2.8.0 Transaction Ledger page's CSV export, statement for statement (``page_view_transactions``):
    the filtered query's rows, every column, trade dates as ``dd Mon yyyy``."""
    ledger = ledger.copy()
    ledger['trade_date'] = pd.to_datetime(ledger['trade_date']).dt.strftime('%d %b %Y')
    return ledger.to_csv(index=False)


def ledger_xlsx(filt_ledger: pd.DataFrame) -> bytes:
    """The 2.8.0 dashboard ledger tab's Excel export, statement for statement (``page_dashboard``)."""
    # Excel Export
    buffer = io.BytesIO()
    export_df = filt_ledger.copy()
    if not export_df.empty:
        export_df['trade_date'] = pd.to_datetime(export_df['trade_date']).dt.date

    col_map_ledger = {
        'trade_date': 'Date', 'issuer': 'Security', 'isin': 'ISIN',
        'account': 'Account', 'transaction_type': 'Type',
        'units': 'Units', 'price': 'Price / Unit', 'amount': 'Total Amount', 'notes': 'Notes'
    }
    export_df = export_df.rename(columns=col_map_ledger)

    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name='Transaction Ledger')
    return buffer.getvalue()


def _n(k: int, one: str, many: str) -> str:
    return f"{k:,} {one if k == 1 else many}"


#: How each type is counted in the header's answer sentence.
_KIND = {"Buy": ("buy", "buys"), "Sell": ("sale", "sales"), "Interest_Receipt": ("interest receipt", "interest receipts"),
         "Principal_Repayment": ("principal repayment", "principal repayments")}


def _answer(full: pd.DataFrame) -> str:
    """The section's answer: how much the ledger holds, over what span, of which kinds — and how to read
    its signs."""
    dates = pd.to_datetime(full["trade_date"])
    counts = full["transaction_type"].value_counts()
    kinds = [_n(int(counts[t]), *_KIND[t]) for t in TRANSACTION_TYPES if counts.get(t, 0)]
    kinds_s = kinds[0] if len(kinds) == 1 else ", ".join(kinds[:-1]) + " and " + kinds[-1]
    return (f"{_n(len(full), 'entry', 'entries')} across {_n(full['account'].nunique(), 'account', 'accounts')} "
            f"and {_n(full['isin'].nunique(), 'security', 'securities')}, {dates.min():%d %b %Y} to "
            f"{dates.max():%d %b %Y}: {kinds_s}. Units carry the sign the book stores — + bought, − sold; a "
            f"receipt or a repayment moves cash, not units, so its units read —.")


def _filters() -> tuple[str, str, str]:
    """The 2.8.0 page's three filters, in a strip directly above the table they scope."""
    with st.container(key="filterbar"):
        f1, f2, f3 = st.columns(3, gap="small")
        with f1:
            acct = st.selectbox("Account", ['All'] + ACCOUNTS, key="la")
        with f2:
            typ = st.selectbox("Type", ['All'] + TRANSACTION_TYPES, key="lt", format_func=_type_label)
        with f3:
            search = st.text_input("Search", key="ls", placeholder="Filter by issuer name…")
    return acct, typ, search


def render_ledger_page() -> None:
    """Operations · Ledger — the audit trail."""
    full = ledger_page()
    if full.empty:
        render_section_header("The Ledger", "No transactions yet.", icon="database", accent="cyan")
        render_empty_state("No transactions yet", "The ledger is empty.", eyebrow="Ledger",
                           action_label="Record one under Operations → Record Transaction.")
        return

    render_section_header("The Ledger", _answer(full), icon="database", accent="cyan")
    acct, typ, search = _filters()
    filtered = bool(acct != 'All' or typ != 'All' or search)
    led = ledger_page(acct, typ, search)

    tf = st.session_state.get("tf_selected")
    tf = tf if tf in WINDOWS else "6M"
    view = led.copy()
    view["trade_date"] = pd.to_datetime(view["trade_date"])
    cut = window_cutoff(pd.Timestamp(date.today()), tf)
    if cut is not None:
        view = view[view["trade_date"] >= cut]
    view["transaction_type"] = view["transaction_type"].map(_type_label)
    view["notes"] = view["notes"].map(lambda s: s if isinstance(s, str) and s.strip() else "—")
    view = view[[c for c, _h, _f in _COLS]].reset_index(drop=True)

    scope = [acct if acct != 'All' else "ALL ACCOUNTS"]
    if typ != 'All':
        scope.append(_type_label(typ).upper())
    if search:
        scope.append(f"“{search}”")
    context = " · ".join(scope + [tf, (f"{len(view):,} of {len(led):,} transactions" if len(view) != len(led)
                                       else _n(len(view), "transaction", "transactions"))])
    if view.empty:
        # The panel (and its window control) stays put, so the window is never lost to a filter.
        with panel("ledger", context=context, window=True):
            if led.empty:
                render_empty_state("No transactions match", "No entry in the ledger matches these filters.",
                                   eyebrow="Ledger", action_label="Clear the search, or set Account and Type to All.")
            else:
                newest = pd.to_datetime(led["trade_date"]).max()
                render_empty_state(
                    f"Nothing in the last {tf}",
                    f"The newest matching entry is dated {esc(f'{newest:%d %b %Y}')}.",
                    eyebrow="Ledger", action_label="Widen the window to ALL to see every entry.")
    else:
        render_table_panel(
            view, "ledger", context=context, window=True,
            max_rows=CAP, keep="first", max_height=560, label_col="trade_date",
            col_labels={c: h for c, h, _f in _COLS},
            col_format={c: f for c, _h, f in _COLS if f is not None},
            sign_color_cols={"units"},
            footer=(esc(f"Showing the newest {CAP:,} of {len(view):,} — the export has all of them.")
                    if len(view) > CAP else ""),
        )

    xl = ledger_tab(acct)
    with st.container(key="ledger-exports", horizontal=True, gap="small"):
        if not led.empty:
            st.download_button(
                "Download the filtered ledger (CSV)" if filtered else "Download the ledger (CSV)",
                ledger_csv(led), "nivesa_ledger.csv", "text/csv", key="ledger-csv", on_click="ignore",
                help="The rows the filters select, every date — the window and the row cap frame the screen only.")
        if not xl.empty:
            st.download_button(
                "Download every transaction (Excel)" if acct == 'All'
                else f"Download every {acct} transaction (Excel)",
                ledger_xlsx(xl), f"nivesa_ledger_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="ledger-xlsx",
                on_click="ignore",
                help="Every transaction for the Account filter (type and search do not apply), with its "
                     "security, ISIN and notes.")
    render_note(f"Full ledger · {len(full):,} entries · CSV = the rows the filters select · Excel = every "
                f"entry for {acct if acct != 'All' else 'every account'} · the window and the {CAP:,}-row cap "
                f"apply to the screen, never to the exports.")
