"""
Nivesa — Analytics · Positions: what exactly do we hold?

PHASE 1 SEAM. The page is registered, framed by the shell and opens with its section header; the body
is being rebuilt on the Graphite system by the next builder. Its numbers already exist, verbatim from
2.8.0, in ``core.views``: positions_table / positions_export (+ add_weight_columns, account_options).
"""

from __future__ import annotations

from core.formatting import fmt_inr_short
from core.views import is_empty_book
from ui.book import load_book
from ui.components import render_empty_state, render_section_header


def render_positions_page() -> None:
    """Analytics · Positions — what exactly do we hold?"""
    df, totals = load_book()
    if is_empty_book(df):
        render_section_header("The Positions", icon="layers")
        render_empty_state("No positions yet", "The ledger holds no live position.", eyebrow="Positions",
                           action_label="Record a purchase under Operations → Record Transaction.")
        return
    render_section_header(
        "The Positions",
        f"{totals['Num Positions']} live positions across {totals['Num Accounts']} accounts and "
        f"{totals['Num Issuers']} issuers: {fmt_inr_short(totals['Total Cost Basis'])} at cost, "
        f"{fmt_inr_short(totals['Total Face Value'])} of face outstanding.",
        icon="layers")
    render_empty_state("Being rebuilt", "The positions table, its account filter and the CSV export move "
                       "here next; every figure is unchanged.", eyebrow="Positions")
