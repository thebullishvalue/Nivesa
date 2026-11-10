"""
Nivesa — Operations · Ledger: the audit trail.

PHASE 1 SEAM. The page is registered, framed by the shell and opens with its section header; the body
is being rebuilt on the Graphite system by the next builder. Its numbers already exist, verbatim from
2.8.0, in ``core.views``: ledger_page (account / type / search filters) and ledger_tab; core.book.get_transaction_ledger_dataframe.
"""

from __future__ import annotations

import pandas as pd

from core.views import ledger_page
from ui.components import render_empty_state, render_section_header


def render_ledger_page() -> None:
    """Operations · Ledger — the audit trail."""
    led = ledger_page()
    if led.empty:
        render_section_header("The Audit Trail", "No transactions yet.", icon="database", accent="cyan")
        render_empty_state("No transactions yet", "The ledger is empty.", eyebrow="Ledger",
                           action_label="Record one under Operations → Record Transaction.")
        return
    last = pd.to_datetime(led["trade_date"]).max()
    render_section_header(
        "The Audit Trail",
        f"{len(led):,} transactions, the latest on {last:%d %b %Y}, newest first.",
        icon="database", accent="cyan")
    render_empty_state("Being rebuilt", "The ledger table, its filters and the CSV / Excel exports move here "
                       "next; every figure is unchanged.", eyebrow="Ledger")
