"""
Nivesa — Operations · Securities: the master registry.

PHASE 1 SEAM. The page is registered, framed by the shell and opens with its section header; the body
is being rebuilt on the Graphite system by the next builder. Its numbers already exist, verbatim from
2.8.0, in ``core.views``: securities_master (type / rating / search filters).
"""

from __future__ import annotations

from core.views import securities_master
from ui.components import render_empty_state, render_section_header


def render_securities_page() -> None:
    """Operations · Securities — the master registry."""
    secs = securities_master()
    if secs.empty:
        render_section_header("The Securities Master", "No securities registered.", icon="cpu")
        render_empty_state("No securities yet", "The securities master is empty.", eyebrow="Securities",
                           action_label="Add one under Operations → Add Security.")
        return
    live = int((secs["days"] > 0).sum())
    render_section_header(
        "The Securities Master",
        f"{len(secs):,} securities registered; {live:,} not yet at maturity.",
        icon="cpu")
    render_empty_state("Being rebuilt", "The registry table, its filters and the CSV export move here next; "
                       "every figure is unchanged.", eyebrow="Securities")
