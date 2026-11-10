"""
Nivesa — Analytics · Cashflows: what comes in, and when?

PHASE 1 SEAM. The page is registered, framed by the shell and opens with its section header; the body
is being rebuilt on the Graphite system by the next builder. Its numbers already exist, verbatim from
2.8.0, in ``core.views``: cashflow_projection / cashflow_totals / nearterm_cashflows.
"""

from __future__ import annotations

from core.formatting import fmt_inr_short
from core.views import cashflow_projection, cashflow_totals, is_empty_book
from ui.book import load_book
from ui.components import render_empty_state, render_section_header


def render_cashflows_page() -> None:
    """Analytics · Cashflows — what comes in, and when?"""
    df, _totals = load_book()
    if is_empty_book(df):
        render_section_header("What Comes In, and When", icon="activity", accent="emerald")
        render_empty_state("No cashflows to project", "The ledger holds no live position.", eyebrow="Cashflows")
        return
    cdf, _mcf, _amort = cashflow_projection(df)
    if cdf.empty:
        render_section_header("What Comes In, and When", "No future cashflows to project.", icon="activity",
                              accent="emerald")
    else:
        cpn, prin, tot = cashflow_totals(cdf)
        render_section_header(
            "What Comes In, and When",
            f"{fmt_inr_short(tot)} is projected to come in: {fmt_inr_short(cpn)} of coupons and "
            f"{fmt_inr_short(prin)} of principal, the last on {cdf['date'].max():%d %b %Y}.",
            icon="activity", accent="emerald")
    render_empty_state("Being rebuilt", "The monthly cashflow chart, its window and the next-twelve-months "
                       "table move here next; every figure is unchanged.", eyebrow="Cashflows")
