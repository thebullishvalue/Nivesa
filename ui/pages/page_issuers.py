"""
Nivesa — Analytics · Issuers: where is the book concentrated?

Reading order (Tattva's house grammar): ANSWER → ANCHOR → EVIDENCE → DETAIL.
  1. The answer for the whole book, with live numbers, and its KPI strip — issuers, the largest issuer's
     weight, the five largest together, and how many sit at or above the caution line.
  2. Concentration by Issuer — the Account filter (2.8.0's "Filter by Account") directly above what it
     filters: each issuer's share of cost as horizontal bars (the heaviest 15), slate below the caution
     line, amber from 5% of cost, rose from 10% (``core.views.concentration_tier``); then 2.8.0's
     Concentration Risk table (every issuer) and, by security, its Issuer Detail table.
Every figure comes from ``core.views`` (``issuer_concentration``, ``issuer_detail``, ``top_issuers``,
``top_share``); nothing here computes.
"""

from __future__ import annotations

import html

import plotly.graph_objects as go

from core.formatting import fmt_inr, fmt_pct
from core.views import (CONCENTRATION_CAUTION, CONCENTRATION_DANGER, add_weight_columns, concentration_tier,
                        is_empty_book, issuer_concentration, issuer_detail, top_issuers, top_share)
from ui.book import load_book
from ui.components import render_chart_panel, render_empty_state, render_kpi_strip, render_section_header
from ui.components import render_sub_header, render_table_panel
from ui.pages._analytics import account_filter, plural, scope_of
from ui.theme import chart_color, chart_layout, chart_rgba, style_axes

#: How many issuers the concentration chart draws (the tables list every one).
TOP_N = 15

#: Metric-card tone and chart hue for each concentration tier.
_TONE = {"danger": "danger", "caution": "warning", "neutral": "neutral"}
_HUE = {"danger": "rose", "caution": "amber", "neutral": "slate"}

CAUTION_PCT = f"{CONCENTRATION_CAUTION:.0%}"
DANGER_PCT = f"{CONCENTRATION_DANGER:.0%}"

TOOLTIPS = {
    "issuers": "Distinct issuers across the book's live positions.",
    "largest": f"The heaviest issuer's share of the book's cost basis. Amber from {CAUTION_PCT}, rose from "
               f"{DANGER_PCT}.",
    "top5": "The five heaviest issuers' shares of cost, added: how much of the book rides on five names.",
    "lines": f"Issuers at or above the {CAUTION_PCT} caution line (amber); those at or above the "
             f"{DANGER_PCT} danger line (rose) are counted beside it.",
}


def _counts(ir) -> tuple[int, int]:
    """(issuers at or above the caution line, issuers at or above the danger line)."""
    tiers = [concentration_tier(w) for w in ir["Wt"]]
    return sum(t != "neutral" for t in tiers), sum(t == "danger" for t in tiers)


def issuer_kpis(ir, totals: dict) -> list[dict]:
    """The book's concentration KPI strip, from ``issuer_concentration`` over every account."""
    top = ir.iloc[0]
    n_line, n_danger = _counts(ir)
    return [
        {"label": "Issuers", "value": str(len(ir)),
         "subtext": f"{totals['Num Positions']} positions · {totals['Num Accounts']} accounts",
         "color_class": "neutral", "tooltip": TOOLTIPS["issuers"]},
        {"label": "Largest Issuer", "value": fmt_pct(top['Wt']), "subtext": str(top['issuer']),
         "color_class": _TONE[concentration_tier(top['Wt'])], "tooltip": TOOLTIPS["largest"]},
        {"label": "Top-5 Share", "value": fmt_pct(top_share(ir, 5)), "subtext": "the five heaviest issuers",
         "color_class": "neutral", "tooltip": TOOLTIPS["top5"]},
        {"label": f"At or Above {CAUTION_PCT}", "value": str(n_line),
         "subtext": f"{n_danger} at or above {DANGER_PCT}",
         "color_class": "danger" if n_danger else "warning" if n_line else "success", "tooltip": TOOLTIPS["lines"]},
    ]


def _answer(ir) -> str:
    top = ir.iloc[0]
    n_line, n_danger = _counts(ir)
    lines = (f"{plural(n_line, 'issuer')} sit{'s' if n_line == 1 else ''} at or above the {CAUTION_PCT} caution "
             f"line, {n_danger} at or above {DANGER_PCT}") if n_line else f"no issuer reaches {CAUTION_PCT}"
    return (f"{len(ir)} issuers; the largest, {top['issuer']}, is {fmt_pct(top['Wt'])} of cost and the five "
            f"largest together {fmt_pct(top_share(ir, 5))}. Across the book {lines}.")


def _concentration_figure(ir):
    """Issuer weights, heaviest on top, coloured by concentration tier; the two lines dotted."""
    rows = top_issuers(ir, TOP_N).iloc[::-1]
    weights = rows["Wt"].astype(float).tolist()
    tiers = [concentration_tier(w) for w in weights]
    fig = go.Figure(go.Bar(
        x=weights, y=[str(i) for i in rows["issuer"]], orientation="h",
        marker_color=[chart_color(_HUE[t]) for t in tiers], marker_line_width=0,
        text=[fmt_pct(w) for w in weights], textposition="outside", cliponaxis=False,
        textfont=dict(size=9, family="JetBrains Mono, monospace", color=chart_color("slate")),
        customdata=[[fmt_pct(w), fmt_inr(c)] for w, c in zip(weights, rows["Cost"])],
        hovertemplate="%{y}: %{customdata[0]} of cost · %{customdata[1]}<extra></extra>",
    ))
    height = max(240, 26 * len(rows) + 64)
    fig.update_layout(**{**chart_layout(height=height, show_legend=False), "hovermode": "closest"}, bargap=0.32)
    style_axes(fig, x_title="share of cost")
    top = max(weights) if weights else 0.0
    fig.update_xaxes(tickformat=".0%", range=[0, max(top * 1.16, CONCENTRATION_DANGER * 1.12)], showspikes=False)
    fig.update_yaxes(showgrid=False, zeroline=False, automargin=True, ticksuffix="  ")
    for level, hue, word in ((CONCENTRATION_CAUTION, "amber", "caution"), (CONCENTRATION_DANGER, "rose", "danger")):
        fig.add_vline(x=level, line=dict(color=chart_rgba(hue, 0.55), width=1, dash="dot"),
                      annotation_text=f"{level:.0%} {word}", annotation_position="top",
                      annotation_font=dict(size=9, family="JetBrains Mono, monospace", color=chart_color(hue)))
    fig.update_layout(margin=dict(t=24, l=12, r=56, b=38))
    return fig


#: 2.8.0's Concentration Risk table (issuer level) and Issuer Detail table (issuer × ISIN).
_CONC_COLS = (
    ("issuer", "Issuer", None),
    ("Cost", "Cost Basis", fmt_inr),
    ("Face", "Face Value", fmt_inr),
    ("Wt", "Weight", fmt_pct),
    ("NY", "Coupon (WA)", fmt_pct),
    ("YC", "Yield to Cost", lambda v: fmt_pct(v) if v > 0 else "—"),
    ("Pos", "Positions", lambda v: f"{int(v)}"),
)
_DETAIL_COLS = (
    ("issuer", "Issuer", None),
    ("isin", "ISIN", None),
    ("Units", "Units", lambda v: f"{int(v)}"),
    ("Cost", "Cost", fmt_inr),
    ("Face", "Face", fmt_inr),
    ("Wt", "Weight", fmt_pct),
    ("NY", "Coupon (WA)", fmt_pct),
    ("YC", "YTC", lambda v: fmt_pct(v) if v > 0 else "—"),
    ("Inc", "Annual Inc", fmt_inr),
)


def _table(frame, cols, key: str, context: str) -> None:
    view = frame[[c for c, _h, _f in cols]].reset_index(drop=True)
    render_table_panel(
        view, key, context=context, label_col="issuer",
        col_labels={c: h for c, h, _f in cols},
        col_format={c: f for c, _h, f in cols if f is not None},
    )


def render_issuers_page() -> None:
    """Analytics · Issuers — where is the book concentrated?"""
    title = "Issuers — Where Is the Book Concentrated?"
    df, totals = load_book()
    if is_empty_book(df):
        render_section_header(title, icon="scale", accent="amber")
        render_empty_state("No positions yet", "The ledger holds no live position.", eyebrow="Issuers")
        return
    df = add_weight_columns(df)
    ir_all = issuer_concentration(df)
    if ir_all.empty:
        render_section_header(title, icon="scale", accent="amber")
        render_empty_state("No issuers yet", "The ledger holds no live position.", eyebrow="Issuers")
        return

    render_section_header(title, _answer(ir_all), icon="scale", accent="amber")
    render_kpi_strip(issuer_kpis(ir_all, totals), max_cols=4, key="issuer-kpis")

    render_section_header(
        "Concentration by Issuer",
        f"Each issuer's share of cost within the account chosen below, heaviest first. Amber marks caution — "
        f"an issuer at {CAUTION_PCT} of cost or more; rose marks danger — {DANGER_PCT} or more; below "
        f"{CAUTION_PCT} the bar is slate.",
        icon="bar-chart", accent="amber")
    acct = account_filter(df, "iss_acct", help="Which account's issuers the chart and both tables show.")
    scope = scope_of(acct)
    ir = ir_all if acct == "All" else issuer_concentration(df, acct)
    if ir.empty:
        render_empty_state("No issuers in this account", "Choose another account above.", eyebrow="Issuers")
        return
    shown = min(TOP_N, len(ir))
    foot = (f"The {shown} heaviest of {len(ir)} issuers; the table below lists every one." if len(ir) > shown
            else f"All {plural(len(ir), 'issuer')}.")
    render_chart_panel(
        _concentration_figure(ir), "issuer-concentration",
        context=f"{scope} · share of cost by issuer · lines at {CAUTION_PCT} and {DANGER_PCT}",
        footer=html.escape(foot),
    )
    _table(ir, _CONC_COLS, "issuer-concentration-table",
           f"{scope} · {plural(len(ir), 'issuer')} · heaviest first")

    render_sub_header("By security")
    idd = issuer_detail(df, acct).reset_index()
    _table(idd, _DETAIL_COLS, "issuer-detail", f"{scope} · {plural(len(idd), 'security', 'securities')} · "
                                              f"issuer and ISIN, heaviest first")
