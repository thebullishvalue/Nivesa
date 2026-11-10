"""
Nivesa — Overview: what do we hold, and what does it earn?

Reading order (Tattva's house grammar): ANSWER → ANCHOR → EVIDENCE → DETAIL.
  1. The KPI strip — cost, yield to cost, coupon income, duration, positions: the five numbers the
     2.8.0 dashboard led with, printed exactly as it printed them ("N/A" now "—").
  2. Capital Allocation — the book by account (the 2.8.0 allocation table, every column).
  3. Where the Book Sits — each account's cost, stacked by the maturity ladder's own buckets.
Every figure comes from ``core.views``; nothing here computes.
"""

from __future__ import annotations

import plotly.graph_objects as go

from core.book import MATURITY_BUCKET_ORDER
from core.formatting import fmt_inr, fmt_inr_short, fmt_pct
from core.views import add_weight_columns, allocation_by_bucket, capital_allocation, is_empty_book
from ui.book import load_book
from ui.components import render_chart_panel, render_empty_state, render_kpi_strip, render_section_header
from ui.components import render_table_panel
from ui.palette import UI_CHART_HEIGHT_MEDIUM
from ui.theme import chart_color, chart_layout, chart_rgba, style_axes

TOOLTIPS = {
    "cost": "What the book cost: every live position's running average-cost basis, net of principal "
            "already returned. Face value is what the issuers owe back at maturity.",
    "yield": "Yield to cost, weighted by cost basis: each position's money-weighted yield on its actual "
             "cashflows, nominal at its own coupon frequency (comparable to the coupon). Positions whose "
             "yield cannot be solved (matured, nothing left to receive) are left out of the average.",
    "income": "Coupon the book earns in a year at today's outstanding face (face × coupon rate), and the "
              "monthly equivalent.",
    "duration": "Macaulay duration of the remaining projected cashflows (amortization included), weighted "
                "by cost basis over positions with a solvable yield; modified duration beside it.",
    "positions": "Live positions — one per security per account — and how many issuers and accounts hold "
                 "them.",
}


def overview_kpis(totals: dict) -> list[dict]:
    """The five KPI cards, from the positions engine's totals (2.8.0's metric-card values, verbatim
    formatting; a yield that cannot be solved prints "—" where 2.8.0 printed "N/A")."""
    wytc = totals['Weighted YTC']
    return [
        {"label": "Total Invested (Cost)", "value": fmt_inr_short(totals['Total Cost Basis']),
         "subtext": f"Face value {fmt_inr_short(totals['Total Face Value'])}", "color_class": "neutral",
         "tooltip": TOOLTIPS["cost"]},
        {"label": "Portfolio Yield (WA)", "value": fmt_pct(wytc) if wytc > 0 else "—",
         "subtext": f"Coupon {fmt_pct(totals['Weighted Nominal Yield'])}" if wytc > 0
         else f"Coupon {fmt_pct(totals['Weighted Nominal Yield'])} · no solvable yield",
         "color_class": "accent", "tooltip": TOOLTIPS["yield"]},
        {"label": "Annual Coupon Income", "value": fmt_inr_short(totals['Total Annual Coupon']),
         "subtext": f"Monthly ~{fmt_inr_short(totals['Total Annual Coupon'] / 12)}", "color_class": "success",
         "tooltip": TOOLTIPS["income"]},
        {"label": "Weighted Duration", "value": f"{totals['Weighted Mac Duration']:.2f}y",
         "subtext": f"Modified {totals['Weighted Mod Duration']:.2f}y", "color_class": "neutral",
         "tooltip": TOOLTIPS["duration"]},
        {"label": "Positions", "value": str(totals['Num Positions']),
         "subtext": f"{totals['Num Issuers']} issuers · {totals['Num Accounts']} accounts",
         "color_class": "neutral", "tooltip": TOOLTIPS["positions"]},
    ]


#: Capital Allocation columns: (source column, header, formatter) — the 2.8.0 table's nine columns.
_ALLOC_COLS = (
    ("account", "Account", None),
    ("Cost", "Cost Basis", fmt_inr),
    ("Face", "Face Value", fmt_inr),
    ("Wt", "Weight", fmt_pct),
    ("Pos", "Positions", lambda v: f"{int(v)}"),
    ("Issuers", "Issuers", lambda v: f"{int(v)}"),
    ("NY", "Coupon (WA)", fmt_pct),
    ("YC", "Yield to Cost", fmt_pct),
    ("Inc", "Annual Income", fmt_inr),
)


def _allocation_answer(acct, totals) -> str:
    """The section's answer sentence, with the live numbers."""
    top = acct.iloc[0]
    wytc = totals['Weighted YTC']
    earns = f"earning {fmt_pct(wytc)} to cost" if wytc > 0 else "with no solvable yield to cost"
    return (f"{fmt_inr_short(totals['Total Cost Basis'])} at cost across {len(acct)} accounts and "
            f"{totals['Num Issuers']} issuers, {earns} and paying {fmt_inr_short(totals['Total Annual Coupon'])} "
            f"a year in coupons. {top['account']} carries the most: {fmt_inr_short(top['Cost'])}, "
            f"{fmt_pct(top['Wt'])} of the book.")


def _bucket_hue(bucket: str, i: int, n: int) -> str:
    """Matured is the one caution in the ladder (amber); live buckets are one hue (accent), nearest
    darkest — intensity is opacity of one hue, ordered by time to maturity."""
    if bucket == "Matured":
        return chart_color("amber")
    return chart_rgba("accent", round(1.0 - 0.65 * (i / max(1, n - 1)), 3))


def _book_sits_figure(pv):
    fig = go.Figure()
    live = [b for b in pv.columns if b != "Matured"]
    for b in pv.columns:
        i = live.index(b) if b in live else 0
        vals = pv[b].tolist()
        fig.add_trace(go.Bar(
            x=list(pv.index), y=[v / 1e5 for v in vals], name=b, marker_color=_bucket_hue(b, i, len(live)),
            marker_line_width=0,
            customdata=[[fmt_inr_short(v)] for v in vals],
            hovertemplate=f"{b}: %{{customdata[0]}}<extra></extra>",
        ))
    fig.update_layout(**chart_layout(height=UI_CHART_HEIGHT_MEDIUM), barmode="stack", bargap=0.45,
                      legend_traceorder="normal")
    style_axes(fig, y_title="cost basis (₹ lakh)")
    return fig


def render_overview_page() -> None:
    df, totals = load_book()
    if is_empty_book(df):          # the app shows the cold start instead; this guards a direct call
        render_empty_state("No positions yet", "The ledger holds no live position.", eyebrow="Overview",
                           action_label="Add a security under Operations, then record its purchase.")
        return

    render_kpi_strip(overview_kpis(totals), max_cols=5, key="overview-kpis")

    df = add_weight_columns(df)
    acct = capital_allocation(df)
    if acct.empty:
        render_section_header("Capital Allocation", icon="layers")
        render_empty_state("No positions with positive cost basis to display.",
                           "Every live position has been fully repaid at cost.", eyebrow="Capital Allocation")
    else:
        render_section_header("Capital Allocation", _allocation_answer(acct, totals), icon="layers")
        view = acct[[c for c, _h, _f in _ALLOC_COLS]].reset_index(drop=True)
        render_table_panel(
            view, "overview-allocation",
            context=f"ALL ACCOUNTS · {len(acct)} accounts · cost basis by account",
            label_col="account",
            col_labels={c: h for c, h, _f in _ALLOC_COLS},
            col_format={c: f for c, _h, f in _ALLOC_COLS if f is not None},
            footer="Weights are of positive-cost-basis capital; yields are cost-weighted, yield to cost over "
                   "positions with a solvable yield.",
        )

    pv = allocation_by_bucket(df)
    if not pv.empty:
        near = [b for b in ("0-3M", "3-6M", "6-12M") if b in pv.columns]
        near_cost = float(pv[near].sum().sum()) if near else 0.0
        total = float(pv.sum().sum())
        matured = float(pv["Matured"].sum()) if "Matured" in pv.columns else 0.0
        desc = (f"{fmt_pct(near_cost / total if total else 0)} of cost comes back within a year "
                f"({fmt_inr_short(near_cost)})")
        desc += (f"; {fmt_inr_short(matured)} sits in positions already past maturity." if matured > 0
                 else "; nothing is past maturity.")
        render_section_header("Where the Book Sits", desc, icon="bar-chart")
        render_chart_panel(
            _book_sits_figure(pv), "overview-ladder",
            context="ALL ACCOUNTS · cost basis by account · stacked by maturity bucket",
            footer=f"Buckets are the maturity ladder's: {' · '.join(b for b in MATURITY_BUCKET_ORDER)}.",
        )
