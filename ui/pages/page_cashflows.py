"""
Nivesa — Analytics · Cashflows: what comes in, and when?

Reading order (Tattva's house grammar): ANSWER → ANCHOR → EVIDENCE → DETAIL.
  1. The answer for the whole book, with live numbers.
  2. The Account filter (2.8.0's "Filter by Account") — it sits ABOVE the KPI strip because, as in 2.8.0,
     the three cards (Future Coupons · Principal Due · Total Future CF) are the chosen account's; the
     chart and the nearterm table below it follow the same choice.
  3. Month by Month — the projected monthly cashflows, coupon (emerald) stacked under principal (cyan).
     The window control in the panel header is a FORWARD horizon (3M/6M/1Y/2Y/ALL counted from this
     month, ``core.views.in_forward_window``); it slices the projection's months, it never re-projects.
  4. Nearterm Cashflows — every payment in the next twelve months (``nearterm_cashflows``).
Every figure comes from ``core.views`` (``cashflow_projection``, ``cashflow_totals``,
``nearterm_cashflows``); nothing here computes.
"""

from __future__ import annotations

import html

import plotly.graph_objects as go
import streamlit as st

from core.formatting import fmt_inr, fmt_inr_short
from core.views import (FORWARD_WINDOW_MONTHS, cashflow_projection, cashflow_totals, forward_window_end,
                        in_forward_window, is_empty_book, nearterm_cashflows)
from ui.book import load_book
from ui.components import WINDOWS, panel, render_chart_panel, render_empty_state, render_kpi_strip
from ui.components import render_section_header, render_table_panel
from ui.pages._analytics import account_filter, plural, scope_of
from ui.palette import UI_CHART_HEIGHT_LARGE
from ui.theme import chart_color, chart_layout, style_axes

TOOLTIPS = {
    "coupons": "Every coupon still to come on the chosen account's live positions, projected on each bond's "
               "own schedule (amortizing bonds on their declining balance), to final maturity.",
    "principal": "Face still to be repaid — at maturity, or on the inferred amortization cadence for bonds "
                 "that have repaid principal before.",
    "total": "Coupons plus principal: everything the chosen account's positions are still projected to pay.",
}

#: 2.8.0's amortization caveat, word for word.
AMORT_NOTE = ("Note: amortizing bonds (those with recorded principal repayments) have their remaining "
              "principal projected on the cadence inferred from past repayments, with coupons on the "
              "declining balance. This is an estimate — the contractual amortization schedule is not stored.")


def cashflow_kpis(cdf) -> list[dict]:
    """2.8.0's three cashflow cards for a projection (the chosen account's), values exactly as printed,
    with the next-twelve-month share and the last payment beside them."""
    cpn, prin, tot = cashflow_totals(cdf)
    n_cpn, n_prin, _n_tot = cashflow_totals(nearterm_cashflows(cdf))
    last = cdf['date'].max()
    return [
        {"label": "Future Coupons", "value": fmt_inr_short(cpn),
         "subtext": f"Next 12 months {fmt_inr_short(n_cpn)}", "color_class": "success",
         "tooltip": TOOLTIPS["coupons"]},
        {"label": "Principal Due", "value": fmt_inr_short(prin),
         "subtext": f"Next 12 months {fmt_inr_short(n_prin)}", "color_class": "info",
         "tooltip": TOOLTIPS["principal"]},
        {"label": "Total Future CF", "value": fmt_inr_short(tot),
         "subtext": f"Last payment {last:%d %b %Y}", "color_class": "neutral", "tooltip": TOOLTIPS["total"]},
    ]


def _answer(cdf_all) -> str:
    if cdf_all.empty:
        return "No future cashflows to project."
    cpn, prin, tot = cashflow_totals(cdf_all)
    _c, _p, n_tot = cashflow_totals(nearterm_cashflows(cdf_all))
    return (f"{fmt_inr_short(tot)} is projected to come in across the book — {fmt_inr_short(cpn)} of coupons "
            f"and {fmt_inr_short(prin)} of principal — the last on {cdf_all['date'].max():%d %b %Y}; "
            f"{fmt_inr_short(n_tot)} of it lands in the next twelve months.")


def _window() -> str:
    tf = st.session_state.get("tf_selected")
    return tf if tf in WINDOWS else "6M"


def _monthly_figure(mcf):
    """Coupon (emerald) stacked under principal (cyan), one bar per calendar month, in ₹ lakh."""
    x = mcf['mo'].dt.to_timestamp()
    fig = go.Figure()
    for col, name, hue in (("Coupon", "Coupon", "emerald"), ("Principal", "Principal", "cyan")):
        vals = mcf[col].tolist()
        fig.add_trace(go.Bar(
            x=x, y=[v / 1e5 for v in vals], name=name, marker_color=chart_color(hue), marker_line_width=0,
            customdata=[[fmt_inr(v)] for v in vals],
            hovertemplate=f"{name}: %{{customdata[0]}}<extra></extra>",
        ))
    fig.update_layout(**chart_layout(height=UI_CHART_HEIGHT_LARGE), barmode="stack", bargap=0.3,
                      legend_traceorder="normal")
    style_axes(fig, y_title="₹ lakh per month")
    fig.update_xaxes(type="date", hoverformat="%b %Y", tickformat="%b %Y")
    return fig


def _window_context(scope: str, tf: str, wm) -> str:
    if wm.empty:
        return f"{scope} · {tf} · ₹ lakh per month"
    first, last = wm['mo'].iloc[0], wm['mo'].iloc[-1]
    return f"{scope} · {tf} · {first.strftime('%b %Y')} → {last.strftime('%b %Y')} · ₹ lakh per month"


def render_cashflows_page() -> None:
    """Analytics · Cashflows — what comes in, and when?"""
    title = "Cashflows — What Comes In, and When?"
    df, _totals = load_book()
    if is_empty_book(df):
        render_section_header(title, icon="activity", accent="emerald")
        render_empty_state("No cashflows to project", "The ledger holds no live position.", eyebrow="Cashflows")
        return

    cdf_all, _mcf_all, _amort_all = cashflow_projection(df)
    render_section_header(title, _answer(cdf_all), icon="activity", accent="emerald")
    acct = account_filter(df, "cf_acct",
                          help="Which account's cashflows the cards, the chart and the nearterm table show.")
    scope = scope_of(acct)
    cdf, mcf, has_amort = cdf_all, _mcf_all, _amort_all
    if acct != "All":
        cdf, mcf, has_amort = cashflow_projection(df, acct)
    if cdf.empty:
        render_empty_state("No future cashflows to project.",
                           "Nothing held in this account is projected to pay again.", eyebrow="Cashflows")
        return

    render_kpi_strip(cashflow_kpis(cdf), max_cols=3, key="cashflow-kpis")

    tf = _window()
    n_months = FORWARD_WINDOW_MONTHS.get(tf)
    horizon = (f"this month and the {n_months - 1} after it" if n_months else "every projected month")
    render_section_header(
        "Month by Month",
        f"Projected coupon and principal per calendar month, coupons beneath. The window looks forward from "
        f"today — it shows {horizon}; the cards above count every month to the last maturity.",
        icon="bar-chart", accent="emerald")
    wm = in_forward_window(mcf, tf)
    wc = in_forward_window(cdf, tf)
    ctx = _window_context(scope, tf, wm)
    foot = ""
    if not wc.empty:
        w_cpn, w_prin, w_tot = cashflow_totals(wc)
        foot = (f"In this window: {fmt_inr_short(w_cpn)} of coupons and {fmt_inr_short(w_prin)} of principal, "
                f"{fmt_inr_short(w_tot)} in all.")
    if has_amort:
        foot = f"{foot} {AMORT_NOTE}".strip()
    if wm.empty:
        end = forward_window_end(tf)
        with panel("cashflow-monthly", context=ctx, footer=html.escape(foot), window=True):
            render_empty_state("Nothing due in this window",
                               html.escape(f"No coupon or principal falls before {end.strftime('%b %Y')}; "
                                           f"widen the window."),
                               eyebrow="Cashflows")
    else:
        render_chart_panel(_monthly_figure(wm), "cashflow-monthly", context=ctx, footer=html.escape(foot),
                           window=True)

    n12 = nearterm_cashflows(cdf)
    if n12.empty:
        render_section_header("Nearterm Cashflows", "Nothing is due in the next twelve months.", icon="activity",
                              accent="cyan")
        return
    n_cpn, n_prin, n_tot = cashflow_totals(n12)
    render_section_header(
        "Nearterm Cashflows",
        f"Every payment due in the next twelve months, soonest first: {fmt_inr_short(n_tot)} — "
        f"{fmt_inr_short(n_cpn)} of coupons and {fmt_inr_short(n_prin)} of principal.",
        icon="activity", accent="cyan")
    view = n12[["date", "issuer", "account", "type", "coupon", "principal", "total"]].reset_index(drop=True)
    render_table_panel(
        view, "cashflow-nearterm",
        context=f"{scope} · next 12 months · {plural(len(view), 'payment')}",
        label_col="date",
        col_labels={"date": "Date", "issuer": "Issuer", "account": "Acct", "type": "Type", "coupon": "Coupon",
                    "principal": "Principal", "total": "Total"},
        col_format={"coupon": fmt_inr, "principal": lambda v: fmt_inr(v) if v > 0 else "—", "total": fmt_inr},
    )
