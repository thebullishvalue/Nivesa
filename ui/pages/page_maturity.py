"""
Nivesa — Analytics · Maturity: when does capital come back?

Reading order (Tattva's house grammar): ANSWER → ANCHOR → EVIDENCE → DETAIL.
  1. The answer for the whole book, with live numbers, and its KPI strip — weighted duration, average
     maturity, the next maturity, principal due in twelve months, matured positions not yet redeemed.
  2. The Ladder — the Account filter (2.8.0's "Filter by Account") directly above the 2.8.0 maturity
     ladder it filters: face (cyan) and cost (slate) per bucket, Matured in amber; then the 2.8.0 table,
     bond by bond, in ladder order.
Every figure comes from ``core.views`` (``maturity_ladder``, ``maturity_rows``, ``next_maturities``,
``matured_mask``, ``cashflow_projection`` / ``nearterm_cashflows`` / ``cashflow_totals``) or the
positions engine's totals; nothing here computes.
"""

from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go

from core.formatting import fmt_inr, fmt_inr_short, fmt_pct
from core.views import (cashflow_projection, cashflow_totals, is_empty_book, matured_mask, maturity_ladder,
                        maturity_rows, nearterm_cashflows, next_maturities)
from ui.book import load_book
from ui.components import render_chart_panel, render_empty_state, render_kpi_strip, render_section_header
from ui.components import render_sub_header, render_table_panel
from ui.pages._analytics import account_filter, plural, scope_of
from ui.palette import UI_CHART_HEIGHT_LARGE
from ui.theme import chart_color, chart_layout, style_axes

TOOLTIPS = {
    "duration": "Macaulay duration of the remaining projected cashflows (amortization included), weighted by "
                "cost basis over positions with a solvable yield; modified duration beside it.",
    "maturity": "Years to each bond's final maturity, weighted by cost basis.",
    "next": "The soonest maturity date among live positions not yet matured, and who holds it.",
    "due": "Principal projected to be repaid in the next twelve months — maturities and amortization — "
           "from the same projection the Cashflows page draws.",
    "matured": "Live positions past their maturity date that still carry face. Record the principal "
               "repayment under Operations → Record Transaction to retire one.",
}

#: The ladder's buckets by days to maturity (``core.book._maturity_bucket``), for the chart footer.
BUCKET_RULE = ("Buckets by days to maturity: 0-3M ≤ 90 · 3-6M ≤ 180 · 6-12M ≤ 365 · 1-2Y ≤ 730 · "
               "2-3Y ≤ 1,095 · 3-5Y ≤ 1,825 · 5Y+ beyond; Matured = past its maturity date.")


def maturity_kpis(df, totals: dict) -> list[dict]:
    """The book's maturity KPI strip."""
    nxt = next_maturities(df)
    if nxt.empty:
        nxt_value, nxt_sub = "—", "nothing left to mature"
    else:
        first = nxt.iloc[0]
        nxt_value = f"{pd.to_datetime(first['maturity_date']):%d %b %Y}"
        nxt_sub = f"{first['issuer']} · {first['account']}"
        if len(nxt) > 1:
            nxt_sub += f" · +{len(nxt) - 1} more"
    cdf, _mcf, _amort = cashflow_projection(df)
    prin12 = cashflow_totals(nearterm_cashflows(cdf))[1] if not cdf.empty else 0.0
    face = totals['Total Face Value']
    n_matured = int(matured_mask(df).sum())
    _mat_df, buckets = maturity_ladder(df)
    matured_face = float(buckets.loc["Matured", "Face"]) if "Matured" in buckets.index else 0.0
    return [
        {"label": "Weighted Duration", "value": f"{totals['Weighted Mac Duration']:.2f}y",
         "subtext": f"Modified {totals['Weighted Mod Duration']:.2f}y", "color_class": "neutral",
         "tooltip": TOOLTIPS["duration"]},
        {"label": "Avg Maturity", "value": f"{totals['Weighted Avg Maturity']:.2f}y",
         "subtext": "cost-weighted", "color_class": "neutral", "tooltip": TOOLTIPS["maturity"]},
        {"label": "Next Maturity", "value": nxt_value, "subtext": nxt_sub, "color_class": "info",
         "tooltip": TOOLTIPS["next"]},
        {"label": "Principal Due in 12M", "value": fmt_inr_short(prin12),
         "subtext": f"{fmt_pct(prin12 / face if face > 0 else 0)} of face outstanding", "color_class": "info",
         "tooltip": TOOLTIPS["due"]},
        {"label": "Matured, Unredeemed", "value": str(n_matured),
         "subtext": (f"{fmt_inr_short(matured_face)} of face still on the book" if n_matured
                     else "every matured bond is retired"),
         "color_class": "warning" if n_matured else "success", "tooltip": TOOLTIPS["matured"]},
    ]


def _answer(df, totals) -> str:
    cdf, _mcf, _amort = cashflow_projection(df)
    prin12 = cashflow_totals(nearterm_cashflows(cdf))[1] if not cdf.empty else 0.0
    face = totals['Total Face Value']
    out = (f"Weighted duration {totals['Weighted Mac Duration']:.2f}y against an average maturity of "
           f"{totals['Weighted Avg Maturity']:.2f}y. {fmt_inr_short(prin12)} of principal comes back in the next "
           f"twelve months ({fmt_pct(prin12 / face if face > 0 else 0)} of face)")
    nxt = next_maturities(df)
    if not nxt.empty:
        first = nxt.iloc[0]
        out += (f"; the next bond to mature is {first['issuer']} ({first['account']}) on "
                f"{pd.to_datetime(first['maturity_date']):%d %b %Y}")
    n_matured = int(matured_mask(df).sum())
    out += (f". {plural(n_matured, 'position')} past maturity still carr{'ies' if n_matured == 1 else 'y'} face."
            if n_matured else ". Nothing past maturity is left unredeemed.")
    return out


def _ladder_figure(buckets):
    """2.8.0's maturity profile: face and cost per bucket, grouped, labelled in the short form."""
    x = list(buckets.index)
    fig = go.Figure()
    face_hues = [chart_color("amber") if b == "Matured" else chart_color("cyan") for b in x]
    for col, name, hues in (("Face", "Face Value", face_hues), ("Cost", "Cost Basis", chart_color("slate"))):
        vals = buckets[col].tolist()
        fig.add_trace(go.Bar(
            x=x, y=[v / 1e5 for v in vals], name=name, marker_color=hues, marker_line_width=0,
            text=[fmt_inr_short(v) for v in vals], textposition="outside", cliponaxis=False,
            textfont=dict(size=9, family="JetBrains Mono, monospace", color=chart_color("slate")),
            customdata=[[fmt_inr(v)] for v in vals],
            hovertemplate=f"{name}: %{{customdata[0]}}<extra></extra>",
        ))
    fig.update_layout(**chart_layout(height=UI_CHART_HEIGHT_LARGE), barmode="group", bargap=0.3,
                      bargroupgap=0.06, legend_traceorder="normal")
    style_axes(fig, y_title="₹ lakh")
    top = max(buckets["Face"].max(), buckets["Cost"].max()) / 1e5 if not buckets.empty else 1.0
    fig.update_yaxes(range=[0, top * 1.14 if top > 0 else 1])
    return fig


#: The ladder table: 2.8.0's seven columns.
_COLS = (
    ("mb", "Bucket", None),
    ("issuer", "Issuer", None),
    ("account", "Acct", None),
    ("position_face_value", "Face Value", fmt_inr),
    ("coupon_rate", "Coupon", fmt_pct),
    ("maturity_date", "Maturity", None),
    ("days_to_maturity", "Days Left", lambda v: f"{int(v)}d"),
)


def render_maturity_page() -> None:
    """Analytics · Maturity — when does capital come back?"""
    title = "Maturity — When Does Capital Come Back?"
    df, totals = load_book()
    if is_empty_book(df):
        render_section_header(title, icon="target")
        render_empty_state("No positions yet", "The ledger holds no live position.", eyebrow="Maturity")
        return

    render_section_header(title, _answer(df, totals), icon="target")
    render_kpi_strip(maturity_kpis(df, totals), max_cols=5, key="maturity-kpis")

    render_section_header(
        "The Ladder",
        "Face value (cyan) and cost (slate) by time to maturity, for the account chosen below. A bond past "
        "its maturity date that still carries face sits in Matured, in amber, until its principal "
        "repayment is recorded.",
        icon="bar-chart", accent="cyan")
    acct = account_filter(df, "mat_acct", help="Which account's positions the ladder and its table show.")
    scope = scope_of(acct)
    mat_df, buckets = maturity_ladder(df, acct)
    if mat_df.empty or buckets.empty:
        render_empty_state("No positions in this account", "Choose another account above.", eyebrow="Maturity")
        return
    render_chart_panel(
        _ladder_figure(buckets), "maturity-ladder",
        context=f"{scope} · {plural(len(buckets), 'bucket')} · face and cost by time to maturity · ₹ lakh",
        footer=html.escape(BUCKET_RULE),
    )
    render_sub_header("Bond by bond")
    rows = maturity_rows(mat_df)
    view = rows[[c for c, _h, _f in _COLS]].reset_index(drop=True)
    view["maturity_date"] = pd.to_datetime(view["maturity_date"])
    render_table_panel(
        view, "maturity-rows",
        context=f"{scope} · {plural(len(view), 'position')} · ladder order, soonest first within a bucket",
        label_col="issuer",
        col_labels={c: h for c, h, _f in _COLS},
        col_format={c: f for c, _h, f in _COLS if f is not None},
    )
