"""
Nivesa — Analytics · Issuers: where is the book concentrated?

PHASE 1 SEAM. The page is registered, framed by the shell and opens with its section header; the body
is being rebuilt on the Graphite system by the next builder. Its numbers already exist, verbatim from
2.8.0, in ``core.views``: issuer_concentration / issuer_detail.
"""

from __future__ import annotations

from core.formatting import fmt_pct
from core.views import add_weight_columns, is_empty_book, issuer_concentration
from ui.book import load_book
from ui.components import render_empty_state, render_section_header


def render_issuers_page() -> None:
    """Analytics · Issuers — where is the book concentrated?"""
    df, totals = load_book()
    if is_empty_book(df):
        render_section_header("Where the Book Is Concentrated", icon="scale", accent="amber")
        render_empty_state("No positions yet", "The ledger holds no live position.", eyebrow="Issuers")
        return
    ir = issuer_concentration(add_weight_columns(df))
    top = ir.iloc[0] if not ir.empty else None
    desc = f"{len(ir)} issuers." if top is None else (
        f"{len(ir)} issuers; the largest, {top['issuer']}, is {fmt_pct(top['Wt'])} of cost.")
    render_section_header("Where the Book Is Concentrated", desc, icon="scale", accent="amber")
    render_empty_state("Being rebuilt", "The concentration chart and the issuer detail table move here next; "
                       "every figure is unchanged.", eyebrow="Issuers")
