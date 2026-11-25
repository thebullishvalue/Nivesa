# -*- coding: utf-8 -*-
"""
NIVESA (निवेसा) — Bond Portfolio Ledger | Part of the Pragyam family by @thebullishvalue

One ledger of every bond across the family's accounts, read as a book: what it costs, what it
yields, what it pays and when it comes back.

The business logic lives in ``core`` (moved byte-for-byte from the 2.8.0 single file and proven
against it: ``tests/test_source_identity.py``, ``tests/test_golden.py``); this file is only the shell,
in Tattva 2.8.0's grammar ("Graphite"): appearance first → the database → the rail (Session ·
Appearance) → the page shell on every page (tape → command bar → notice rail) →
``st.navigation`` pages → footer. With no live position the Overview is the cold start (masthead +
landing); every Operations page stays reachable so the first security can be added.

Usage:
    streamlit run app.py              # NIVESA_DATA_DIR selects the data directory (default ./data)
"""

from __future__ import annotations

import html
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import (  # noqa: E402
    ACCOUNTS, BOND_TYPES, COMPANY, DAY_COUNT_CONVENTIONS, PRODUCT_NAME, TAGLINE, VERSION,
)
from core.audit import audit_init  # noqa: E402
from core.db import db_init  # noqa: E402
from core.schedule import schedule_init  # noqa: E402
from ui import book, storage  # noqa: E402
from ui.components import (  # noqa: E402
    WINDOWS, render_header, render_kpi_strip, render_nav_brand, render_section_header,
    render_outcome_grid, render_system_grid, render_ticker, render_top_bar, render_warning_box,
)
from ui.auth import open_notice, render_sign_out, require_login  # noqa: E402
from ui.notices import drain_notifications, open_rail  # noqa: E402
from ui.pages.page_audit import render_audit_page  # noqa: E402
from ui.pages.page_add_security import render_add_security_page  # noqa: E402
from ui.pages.page_cashflows import render_cashflows_page  # noqa: E402
from ui.pages.page_edit_security import render_edit_security_page  # noqa: E402
from ui.pages.page_edit_transaction import render_edit_transaction_page  # noqa: E402
from ui.pages.page_issuers import render_issuers_page  # noqa: E402
from ui.pages.page_ledger import render_ledger_page  # noqa: E402
from ui.pages.page_maturity import render_maturity_page  # noqa: E402
from ui.pages.page_overview import render_overview_page  # noqa: E402
from ui.pages.page_positions import render_positions_page  # noqa: E402
from ui.pages.page_record_transaction import render_record_transaction_page  # noqa: E402
from ui.pages.page_securities import render_securities_page  # noqa: E402
from ui.theme import inject_css  # noqa: E402

#: What the command bar describes: the whole book, every account.
SCOPE = "ALL ACCOUNTS"

#: The pages: the book at a glance (Overview); the four ways of reading it (Analytics) — what we hold,
#: what it pays, when it comes back, where it is concentrated; then the ledger's own operations, the
#: everyday entry first. (section, title, icon, url_path, render function, windowed). Windowed pages
#: carry the window control in their primary panel and show "Window" in the command bar.
PAGES = (
    ("", "Overview", ":material/dashboard:", "overview", render_overview_page, False),
    ("Analytics", "Positions", ":material/table_rows:", "positions", render_positions_page, False),
    ("Analytics", "Cashflows", ":material/payments:", "cashflows", render_cashflows_page, True),
    ("Analytics", "Maturity", ":material/event:", "maturity", render_maturity_page, False),
    ("Analytics", "Issuers", ":material/domain:", "issuers", render_issuers_page, False),
    ("Operations", "Record Transaction", ":material/add_card:", "record-transaction",
     render_record_transaction_page, False),
    ("Operations", "Ledger", ":material/receipt_long:", "ledger", render_ledger_page, True),
    ("Operations", "Securities", ":material/inventory_2:", "securities", render_securities_page, False),
    ("Operations", "Add Security", ":material/library_add:", "add-security", render_add_security_page, False),
    ("Operations", "Edit Security", ":material/edit_note:", "edit-security", render_edit_security_page, False),
    ("Operations", "Edit Transaction", ":material/edit:", "edit-transaction", render_edit_transaction_page, False),
    ("Operations", "Audit Trail", ":material/history:", "audit", render_audit_page, False),
)

#: Set by main() when the audit trail could not be switched on; the notice rail says so.
_AUDIT_OK = True

#: The page favicon — Tattva's mark pattern (a ring and a rising line), in the Paper cobalt.
_FAVICON = (  # Tattva's exact tab icon (its cobalt ring-and-line mark), in Tattva's own
              # base64 encoding — the same bytes, so the three apps' tabs match.
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My"
    "5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMTAiIG"
    "ZpbGw9Im5vbmUiIHN0cm9rZT0iIzNENkZFOCIgc3Ryb2tlLXdpZHRoPSIyIi8+PHBhdGggZD0iTTggMTRsMy01ID"
    "IgMyAzLTQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzNENkZFOCIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZW"
    "NhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz48L3N2Zz4="
)


# ─── Appearance ──────────────────────────────────────────────────────────────
#: The DURABLE record of the appearance choice — a plain session key, never a widget key.
#: Streamlit garbage-collects the state of any widget not instantiated during a run; a plain key
#: is never collected, so a run that stops early (a form's st.stop) cannot flip the theme back.
_THEME_CHOICE = "theme_choice"

#: The two appearances. Paper (light, for reading and print) LEADS, and the order is the
#: default: ``theme_choice()`` falls back to APPEARANCES[0] for any unset or unrecognised
#: value, so first-in-tuple IS first-run — one fact, so the toggle and the default agree.
APPEARANCES = ("Paper", "Slate")


def theme_choice() -> str:
    """The appearance the user last chose, always one of ``APPEARANCES``."""
    choice = st.session_state.get(_THEME_CHOICE)
    return choice if choice in APPEARANCES else APPEARANCES[0]


def _render_appearance_control() -> None:
    """The theme switch — LAST control in the rail, pinned to its foot by CSS
    (``.st-key-appearance``). Rendered exactly once per run."""
    with st.container(key="appearance"):
        st.markdown('<div class="sidebar-title">Appearance</div>', unsafe_allow_html=True)
        mode = st.segmented_control(
            "Appearance", list(APPEARANCES), key="theme_mode",
            default=theme_choice(), label_visibility="collapsed",
            help="Slate — dark, for working. Paper — light, for reading and print.",
        )
        # Mirror the widget into the DURABLE key and rerun, so the stylesheet at the top of
        # main() is re-injected with the new value (no half-themed run).
        if mode is not None and mode != theme_choice():
            st.session_state[_THEME_CHOICE] = mode
            st.rerun()


# ─── Cold start ──────────────────────────────────────────────────────────────
def _render_header() -> None:
    """Cold-start masthead only; once the book holds a position the command bar carries identity."""
    render_header(PRODUCT_NAME.upper(), TAGLINE)


#: The landing page's three segments, as data: Engines, Inputs & Scope, What It Shows, in the
#: order Arthagati reads them. Plain words first; a method's name only where it helps.
_ENGINES = (
    ("Positions", "The ledger · cost",
     "Rebuilds every holding from its transactions (purchases, sales, coupons received and "
     "principal repaid) in date order, so each account's position and average cost are always "
     "what the ledger says, never a figure typed by hand.",
     (("Built from", "Every recorded transaction"),
      ("Cost", "Running average, per account"),
      ("Checked", "Dates and balances, on entry"))),
    ("Yield", "Return · duration",
     "Works out each position's yield on its actual cash: what was paid, what has come in and "
     "what is still due, so it sits beside the coupon. Duration measures how long, on average, "
     "the money takes to come back.",
     (("Yield", "On actual cashflows"),
      ("Set beside", "The coupon rate"),
      ("Duration", "Macaulay and modified"))),
    ("Cashflows", "What comes back · when",
     "Projects every coupon and principal payment still to come, month by month, including "
     "bonds that repay in instalments, and lists the next twelve months line by line.",
     (("Horizon", "Every future payment"),
      ("Shown", "By month and by bond"),
      ("Includes", "Partial repayments"))),
)

_SHOWS = (
    ("The book", "What every account holds, at cost and at face value, with its yield and its "
                 "coupon income."),
    ("Yield and duration", "Each position's yield on its actual cashflows beside its coupon, and "
                           "how long its money takes to come back."),
    ("Cashflows", "Every coupon and repayment still to come, month by month, and the next twelve "
                  "months line by line."),
    ("The ledger", "Every buy, sale, receipt and repayment, checked against the bond's dates and "
                   "each account's balance before it is saved."),
)


def _render_landing_page() -> None:
    """First run (an empty book): the claim, then Engines, Inputs & Scope and What It Shows —
    Arthagati's three, the last named for a ledger, which has no run."""
    st.markdown(
        '<div class="lede">'
        '<div class="lede-claim">Nivesa keeps one ledger of every bond across the family\'s accounts, and '
        'reads it as a book — what it costs, what it yields, what it pays and when it comes back.</div>'
        '<div class="lede-cta">Add a security under <strong>Operations</strong>, then record its '
        'purchase.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    render_section_header(
        "Engines",
        "Three engines read every bond in the ledger: what it cost, what it earns, and what it will "
        "pay and when.",
        icon="cpu",
    )
    render_system_grid(_ENGINES)
    render_section_header(
        "Inputs & Scope",
        "The accounts, instruments and conventions the ledger is set up for.",
        icon="database",
    )
    render_kpi_strip(
        [
            {"label": "Accounts", "value": str(len(ACCOUNTS)),
             "subtext": " · ".join(a.title() for a in ACCOUNTS)},
            {"label": "Instrument Types", "value": str(len(BOND_TYPES)),
             "subtext": "NCDs, corporate and government bonds, state loans, T-bills, tax-free and "
                        "gold bonds, and fixed deposits"},
            {"label": "Day-Count Conventions", "value": str(len(DAY_COUNT_CONVENTIONS)),
             "subtext": "How interest accrues between payment dates: " + " · ".join(DAY_COUNT_CONVENTIONS)},
        ],
        max_cols=3, key="landing-coverage",
    )
    render_section_header(
        "What It Shows",
        "Four things the book shows once a security and its purchase are recorded.",
        icon="target",
    )
    render_outcome_grid(_SHOWS)


def _render_footer() -> None:
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    st.markdown(
        f'<div class="app-footer"><div class="content">'
        f'© {ist_now.year} <strong>{html.escape(PRODUCT_NAME.upper())}</strong> &nbsp;·&nbsp; '
        f'{html.escape(COMPANY)} &nbsp;·&nbsp; v{html.escape(VERSION)} &nbsp;·&nbsp; '
        f'{ist_now.strftime("%Y-%m-%d %H:%M:%S IST")}'
        f'</div></div>',
        unsafe_allow_html=True,
    )


# ─── The rail: Session · Appearance ──────────────────────────────────────────
def _render_rail(ctx: dict) -> None:
    """A ledger has no instrument to pick and no model to read: the rail holds the pages, one
    session action and the appearance switch (the book itself is on every page's command bar)."""
    with st.sidebar:
        render_nav_brand()
        st.markdown('<div class="sidebar-title">Session</div>', unsafe_allow_html=True)
        if st.button("Refresh", type="secondary", width="stretch",
                     help="Re-read the ledger from the database and recompute the book (clears the cache)."):
            book.clear()
            st.rerun()
        render_sign_out()
        _render_appearance_control()


# ─── The page shell ──────────────────────────────────────────────────────────
def _top_bar(ctx: dict, *, windowed: bool = False) -> None:
    """The page shell, identical on every page: the TAPE (the next cashflows) above the COMMAND BAR
    (the book and its standing) above the NOTICE RAIL (form outcomes and the book's caveats). The bar
    names the window only on pages whose primary panel it frames."""
    bar = ctx["bar"]
    render_ticker(ctx["tape"])
    meta = [("Yield (WA)", bar["yield"]), ("Duration", bar["duration"]), ("Positions", bar["positions"])]
    if windowed:
        tf = st.session_state.get("tf_selected")
        meta.append(("Window", tf if tf in WINDOWS else "6M"))
    meta.append(("As of", bar["as_of"]))
    render_top_bar(target=SCOPE, eyebrow="Book", value_text=bar["value"],
                   status_label=bar["chip"][0], status_tone=bar["chip"][1], meta_items=meta)
    audit = [] if _AUDIT_OK else [{"kind": "danger", "title": "Audit off",
                                   "body": "The audit trail could not be switched on; changes are not being "
                                           "recorded. See the log."}]
    open_rail(drain_notifications() + storage.notices() + audit + open_notice() + list(ctx["notices"]))


def _safe_render(name: str, fn) -> None:
    """Render a page's content; a failure says which page and why, and the app stays up.
    (Streamlit's own stop/rerun signals are BaseExceptions and pass straight through.)"""
    try:
        fn()
    except Exception as e:  # noqa: BLE001 — one page, not the app
        render_warning_box(f"{name} could not be drawn", f"{type(e).__name__}: {e}")


def _page_fn(title: str, url: str, render, windowed: bool):
    def _page() -> None:
        ctx = book.shell_context()
        if url == "overview" and ctx["empty"]:
            _render_header()
            _render_landing_page()
            return
        _top_bar(ctx, windowed=windowed)
        _safe_render(title, render)
    _page.__name__ = f"page_{url.replace('-', '_')}"
    return _page


def _render_pages() -> None:
    if st.session_state.get("tf_selected") not in WINDOWS:
        st.session_state["tf_selected"] = "6M"
    sections: dict[str, list] = {}
    for section, title, icon, url, render, windowed in PAGES:
        sections.setdefault(section, []).append(
            st.Page(_page_fn(title, url, render, windowed), title=title, icon=icon, url_path=url,
                    default=(title == PAGES[0][1])))
    st.navigation(sections, position="sidebar").run()
    _render_footer()


# ─── Main ────────────────────────────────────────────────────────────────────
def _terminal() -> None:
    """The terminal's masthead (once per process) and the ledger's own log in the run trace.

    The ledger keeps its file log (``data/logs``) as before; the console shows the same events
    in the family's form. The per-rerun "Database initialized" line stays in the file only.
    """
    from core.config import DB_FILE, TAGLINE
    from core.logger_config import capture_library_output, console, route_logging
    capture_library_output()
    h = route_logging(console, names=(PRODUCT_NAME,))
    h.addFilter(lambda r: "initialized / migrated" not in r.getMessage())
    console.banner(PRODUCT_NAME, VERSION, TAGLINE, {"Maintainer": COMPANY, "Database": DB_FILE})


def main() -> None:
    st.set_page_config(page_title="NIVESA | Bond Portfolio Ledger", page_icon=_FAVICON, layout="wide",
                       initial_sidebar_state="expanded")
    # Resolve the appearance BEFORE anything is styled, from the DURABLE key — so CSS, charts,
    # tables and iframes agree on one value for the whole run.
    st.session_state["theme"] = "light" if theme_choice() == "Paper" else "dark"
    inject_css(theme=st.session_state["theme"])
    _terminal()
    if not require_login():
        _render_footer()                # the sign-in page ends on the family footer, as every page does
        return
    # The book's home is the private store when one is set up (ui.storage): load it before the database
    # is opened, and never open a stale or empty copy when it cannot be loaded.
    if not storage.load_book():
        return
    try:
        # Read by default_chart_context: a panel's context line reads "ALL ACCOUNTS · 6M · units".
        st.session_state["active_target"] = SCOPE
        st.session_state.pop("_notice_slot", None)      # a slot belongs to the run that made it
        db_init()
        schedule_init()             # before audit_init, so the trail covers the schedule too
        global _AUDIT_OK
        _AUDIT_OK = audit_init()
        ctx = book.shell_context()
        _render_rail(ctx)
        _render_pages()
    finally:
        # Every write path ends its run with st.rerun() (or st.stop() on a rejection): both pass through
        # here, so a saved change reaches the store before the next run draws its result.
        storage.save_book()


if __name__ == "__main__":
    main()
