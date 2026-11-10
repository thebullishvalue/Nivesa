"""
Nivesa — Analytics · Positions: what exactly do we hold?

Reading order (Tattva's house grammar): ANSWER → ANCHOR → DETAIL.
  1. The answer, with live numbers, and the book's KPI strip — positions, cost, face, yield to cost,
     accrued interest, realized P&L — all from the positions engine's totals (the whole book).
  2. Position by Position — the Account filter (2.8.0's "Filter by Account": All + the accounts that hold
     a position) directly above the 2.8.0 positions table it filters, then the CSV export of exactly
     those rows (``positions_export``, unchanged).
Every figure comes from ``core.views`` / ``core.book``; nothing here computes.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.formatting import fmt_inr, fmt_inr_short, fmt_pct
from core.views import add_weight_columns, is_empty_book, positions_export, positions_table
from ui.book import load_book
from ui.components import render_empty_state, render_kpi_strip, render_note, render_section_header
from ui.components import render_table_panel
from ui.pages._analytics import account_filter, plural, scope_of

TOOLTIPS = {
    "positions": "Live positions — one per security per account — and how many issuers and accounts "
                 "hold them.",
    "cost": "Running average-cost basis of every live position, net of principal already returned; the "
            "principal returned so far is beside it.",
    "face": "What the issuers still owe back at maturity: units × face value, less principal already "
            "repaid. Weighted average maturity is cost-weighted, to each bond's final maturity.",
    "yield": "Yield to cost, weighted by cost basis: each position's money-weighted yield on its actual "
             "cashflows, nominal at its own coupon frequency. Positions whose yield cannot be solved are "
             "left out of the average.",
    "accrued": "Coupon earned since each position's last coupon date and not yet paid, at today's face.",
    "pnl": "Realized P&L on sales (against the running average cost at the time of sale) and on capital "
           "returned beyond cost. The ledger holds no market price, so there is no unrealized P&L.",
}


def _signed_inr(v) -> str:
    """Rupees with a sign: +₹… / −₹… ; zero carries none."""
    v = float(v)
    if abs(v) < 0.005:
        return fmt_inr(0)
    return ("+" if v > 0 else "−") + fmt_inr(abs(v))


def _signed_inr_short(v) -> str:
    v = float(v)
    if abs(v) < 0.005:
        return fmt_inr_short(0)
    return ("+" if v > 0 else "−") + fmt_inr_short(abs(v))


def positions_kpis(totals: dict) -> list[dict]:
    """The book's KPI strip, from the positions engine's totals."""
    wytc = totals['Weighted YTC']
    pnl = totals['Total Realized PnL']
    return [
        {"label": "Positions", "value": str(totals['Num Positions']),
         "subtext": f"{totals['Num Issuers']} issuers · {totals['Num Accounts']} accounts",
         "color_class": "neutral", "tooltip": TOOLTIPS["positions"]},
        {"label": "Cost Basis", "value": fmt_inr_short(totals['Total Cost Basis']),
         "subtext": f"Repaid {fmt_inr_short(totals['Total Principal Repaid'])}",
         "color_class": "neutral", "tooltip": TOOLTIPS["cost"]},
        {"label": "Face Outstanding", "value": fmt_inr_short(totals['Total Face Value']),
         "subtext": f"Avg maturity {totals['Weighted Avg Maturity']:.2f}y", "color_class": "info",
         "tooltip": TOOLTIPS["face"]},
        {"label": "Yield to Cost (WA)", "value": fmt_pct(wytc) if wytc > 0 else "—",
         "subtext": f"Coupon {fmt_pct(totals['Weighted Nominal Yield'])}" if wytc > 0
         else f"Coupon {fmt_pct(totals['Weighted Nominal Yield'])} · no solvable yield",
         "color_class": "accent", "tooltip": TOOLTIPS["yield"]},
        {"label": "Accrued Interest", "value": fmt_inr_short(totals['Total Accrued Interest']),
         "subtext": f"Received {fmt_inr_short(totals['Total Interest Received'])} to date",
         "color_class": "success", "tooltip": TOOLTIPS["accrued"]},
        {"label": "Realized P&L", "value": _signed_inr_short(pnl),
         "subtext": "sales and repayments",
         "color_class": "success" if pnl > 0.005 else "danger" if pnl < -0.005 else "neutral",
         "tooltip": TOOLTIPS["pnl"]},
    ]


def _answer(df, totals) -> str:
    wytc = totals['Weighted YTC']
    earns = f"yielding {fmt_pct(wytc)} to cost" if wytc > 0 else "with no solvable yield to cost"
    top = positions_table(df).iloc[0]
    return (f"{plural(int(totals['Num Positions']), 'live position')} across {totals['Num Accounts']} accounts and "
            f"{totals['Num Issuers']} issuers: {fmt_inr_short(totals['Total Cost Basis'])} at cost against "
            f"{fmt_inr_short(totals['Total Face Value'])} of face, {earns}. The largest single holding is "
            f"{top['issuer']} in {top['account']}, {fmt_inr_short(top['cost_basis'])} at cost.")


#: The positions table: (source column, header, formatter) — 2.8.0's columns, the security split into
#: issuer and ISIN. Yield to cost and duration print "—" where 2.8.0 printed "N/A". Realized P&L
#: (``_PNL``, sign-coloured) joins them whenever a position in view carries any.
_COLS = (
    ("issuer", "Issuer", None),
    ("isin", "ISIN", None),
    ("credit_rating", "Rating", None),
    ("account", "Acct", None),
    ("current_units", "Units", lambda v: f"{int(v)}"),
    ("cost_basis", "Cost", fmt_inr),
    ("position_face_value", "Face", fmt_inr),
    ("nominal_yield", "Coupon", fmt_pct),
    ("yield_to_cost", "YTC", lambda v: fmt_pct(v) if v > 0 else "—"),
    ("macaulay_duration", "Duration", lambda v: f"{v:.2f}y" if v > 0 else "—"),
    ("maturity_date", "Maturity", None),
    ("annual_coupon_income", "Annual Inc", fmt_inr),
)
_PNL = ("realized_pnl", "Realized P&L", _signed_inr)


def render_positions_page() -> None:
    """Analytics · Positions — what exactly do we hold?"""
    df, totals = load_book()
    if is_empty_book(df):
        render_section_header("Positions — What Exactly Do We Hold?", icon="layers")
        render_empty_state("No positions yet", "The ledger holds no live position.", eyebrow="Positions",
                           action_label="Record a purchase under Operations → Record Transaction.")
        return
    df = add_weight_columns(df)

    render_section_header("Positions — What Exactly Do We Hold?", _answer(df, totals), icon="layers")
    render_kpi_strip(positions_kpis(totals), max_cols=6, key="positions-kpis")

    render_section_header(
        "Position by Position",
        "One row per security per account, largest cost first. Yield to cost and duration print — where "
        "no yield can be solved (nothing left to receive); realized P&L gets a column, signed, once a "
        "position in view has any. The export carries every row the table shows.",
        icon="database")
    acct = account_filter(df, "pf", help="Which account's positions the table and the export show.")
    filtered = positions_table(df, acct)
    scope = scope_of(acct)
    if filtered.empty:
        render_empty_state("No positions in this account", "Choose another account above.",
                           eyebrow="Positions")
        return
    cols = _COLS + ((_PNL,) if (filtered["realized_pnl"].abs() >= 0.005).any() else ())
    view = filtered[[c for c, _h, _f in cols]].reset_index(drop=True)
    view["maturity_date"] = pd.to_datetime(view["maturity_date"])
    render_table_panel(
        view, "positions-table",
        context=f"{scope} · {plural(len(view), 'position')} · largest cost first",
        label_col="issuer",
        col_labels={c: h for c, h, _f in cols},
        col_format={c: f for c, _h, f in cols if f is not None},
        sign_color_cols={"realized_pnl"},
    )
    exp = positions_export(filtered)
    st.download_button("Download positions (CSV)", exp.to_csv(index=False), "nivesa_positions.csv", "text/csv",
                       key="dl-positions")
    render_note(f"{scope} · {plural(len(exp), 'position')} · yields in percent · adds modified duration, "
                f"interest received and days to maturity to the table's columns.")
