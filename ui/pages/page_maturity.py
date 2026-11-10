"""
Nivesa — Analytics · Maturity: when does capital come back?

PHASE 1 SEAM. The page is registered, framed by the shell and opens with its section header; the body
is being rebuilt on the Graphite system by the next builder. Its numbers already exist, verbatim from
2.8.0, in ``core.views``: maturity_ladder / maturity_rows.
"""

from __future__ import annotations

from core.views import is_empty_book
from ui.book import load_book
from ui.components import render_empty_state, render_section_header


def render_maturity_page() -> None:
    """Analytics · Maturity — when does capital come back?"""
    df, totals = load_book()
    if is_empty_book(df):
        render_section_header("When Capital Comes Back", icon="target")
        render_empty_state("No positions yet", "The ledger holds no live position.", eyebrow="Maturity")
        return
    render_section_header(
        "When Capital Comes Back",
        f"Weighted duration {totals['Weighted Mac Duration']:.2f}y; weighted average maturity "
        f"{totals['Weighted Avg Maturity']:.2f}y.",
        icon="target")
    render_empty_state("Being rebuilt", "The maturity ladder chart and its bucket table move here next; "
                       "every figure is unchanged.", eyebrow="Maturity")
