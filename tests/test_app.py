"""
The app, end to end through Streamlit's AppTest (1.52.2), against a throwaway copy of the book:

  · navigation is exactly the eleven pages, in the specified order and sections, Overview default;
  · every registered page renders with zero exceptions, under the page shell (tape → command bar →
    notice rail), opening with its own section header, with no "nan"/"None" text and none of the
    retired disclosure widgets (rule 133: no expander, tabs, caption, info/warning/success/error box,
    metric or dataframe);
  · the form pages render their forms once a security / transaction is picked (nothing is submitted
    against the book); a rejected entry lands in the notice rail, not in an error box;
  · an empty book is a cold start (masthead + landing) on Overview, while Operations stays reachable.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
APP = str(REPO / "app.py")

NAV = [("", "Overview"), ("Analytics", "Positions"), ("Analytics", "Cashflows"), ("Analytics", "Maturity"),
       ("Analytics", "Issuers"), ("Operations", "Record Transaction"), ("Operations", "Ledger"),
       ("Operations", "Securities"), ("Operations", "Add Security"), ("Operations", "Edit Security"),
       ("Operations", "Edit Transaction")]
ICONS = [":material/dashboard:", ":material/table_rows:", ":material/payments:", ":material/event:",
         ":material/domain:", ":material/add_card:", ":material/receipt_long:", ":material/inventory_2:",
         ":material/library_add:", ":material/edit_note:", ":material/edit:"]
FIRST_HEADER = {"overview": "Capital Allocation", "positions": "Positions — What Exactly Do We Hold?",
                "cashflows": "Cashflows — What Comes In, and When?",
                "maturity": "Maturity — When Does Capital Come Back?",
                "issuers": "Issuers — Where Is the Book Concentrated?",
                "record-transaction": "Record Transaction", "ledger": "The Ledger",
                "securities": "Securities Master", "add-security": "Add Security",
                "edit-security": "Edit Security", "edit-transaction": "Edit Transaction"}
PICKERS = {"record-transaction": "Select Security", "edit-security": "Select Security",
           "edit-transaction": "Select Transaction"}


@pytest.fixture
def apptest(monkeypatch):
    """AppTest with the segmented-control shim: AppTest 1.52.2 reads every button group's value as a
    LIST, but a single-select st.segmented_control (Appearance) holds a scalar, which AppTest would
    iterate character by character on the next run. Test-harness shim only — the app is unchanged."""
    from streamlit.testing.v1 import AppTest
    from streamlit.testing.v1 import element_tree as et

    def _indices(self):
        v = self.value
        vals = v if isinstance(v, (list, tuple)) else ([] if v is None else [v])
        return [self.options.index(self.format_func(x)) for x in vals]

    monkeypatch.setattr(et.ButtonGroup, "indices", property(_indices))
    return lambda: AppTest.from_file(APP, default_timeout=120)


def _md(at) -> str:
    """Every markdown block's HTML, the injected stylesheet excluded (it names every class)."""
    return " ".join(m.value for m in at.markdown if not m.value.lstrip().startswith("<style"))


def _text(md: str) -> str:
    return re.sub(r"<style.*?</style>|<[^>]+>", " ", md, flags=re.S)


def _assert_clean(at, where: str) -> str:
    import html
    assert not at.exception, (where, [e.message for e in at.exception])
    md = _md(at)
    assert "could not be drawn" not in md, where
    low = f" {html.unescape(_text(md)).lower()} "
    for bad in ("+nan", " nan ", " none ", "n/a"):
        assert bad not in low, (where, bad)
    assert not (at.expander or at.tabs or at.caption or at.info or at.warning or at.success or at.error
                or at.metric or at.dataframe or at.toast), (where, "rule 133")
    return md


def _goto(at, url: str):
    from streamlit.util import calc_md5
    at._page_hash = "" if url == "overview" else calc_md5(url)
    return at.run()


def test_navigation_registry_is_the_specified_order():
    import app as app_module
    assert [(p[0], p[1]) for p in app_module.PAGES] == NAV
    assert [p[2] for p in app_module.PAGES] == ICONS
    assert [p[3] for p in app_module.PAGES] == list(FIRST_HEADER)
    windowed = {p[3] for p in app_module.PAGES if p[5]}
    assert windowed == {"cashflows", "ledger"}
    assert app_module.APPEARANCES == ("Paper", "Slate")


def test_every_page_renders_under_the_shell(apptest):
    import html

    import app as app_module
    at = apptest()
    at.run()
    _assert_clean(at, "first run")
    # the rail: Book readout · Session · Appearance, brand above the nav
    rail = " ".join(m.value for m in at.sidebar.markdown if not m.value.lstrip().startswith("<style"))
    assert "nav-brand" in rail and "NIV" in rail and "rail-readout" in rail
    assert rail.index(">Book<") < rail.index(">Session<") < rail.index(">Appearance<")
    assert [b.label for b in at.sidebar.button] == ["Refresh"]
    for _section, title, _icon, url, _fn, windowed in app_module.PAGES:
        _goto(at, url)
        md = _assert_clean(at, title)
        assert 'class="command-bar' in md and 'class="ticker"' in md, title
        i_tape, i_bar = md.index('class="ticker"'), md.index('class="command-bar')
        assert i_tape < i_bar, title
        if "notice-rail" in md:
            assert i_bar < md.index('class="notice-rail"'), title
        assert ">NIV<" in md and "ALL ACCOUNTS" in md, title
        assert ('<span class="k">Window</span>' in md) is windowed, title
        assert FIRST_HEADER[url] in html.unescape(md), title
        assert "premium-header" not in md, title           # masthead only on cold start
    _goto(at, "overview")
    md = _md(at)
    for label in ("Total Invested (Cost)", "Portfolio Yield (WA)", "Annual Coupon Income", "Weighted Duration",
                  "Positions"):
        assert f">{label}<" in md, label
    from core.config import VERSION
    assert "app-footer" in md and "Hemrek Capital" in md and f"v{VERSION}" in md and " IST" in md


@pytest.mark.parametrize("url", list(PICKERS))
def test_form_pages_render_their_forms(apptest, url):
    at = apptest()
    at.run()
    _goto(at, url)
    _assert_clean(at, url)
    pick = [s for s in at.selectbox if s.label == PICKERS[url]]
    assert pick, url
    pick[0].select(pick[0].options[0]).run()
    md = _assert_clean(at, f"{url} picked")
    assert "terms-strip" in md, url
    assert at.button, f"{url}: the form's submit is missing"


def test_add_security_form_renders_and_rejects_into_the_notice_rail(apptest):
    at = apptest()
    at.run()
    _goto(at, "add-security")
    _assert_clean(at, "add-security")
    assert {t.label for t in at.text_input} >= {"Issuer Name", "ISIN", "Sector"}
    submit = [b for b in at.button if b.label == "Add security"]
    assert submit
    submit[0].click().run()                    # empty issuer/ISIN: rejected before any write
    md = _assert_clean(at, "add-security rejected")
    assert 'class="notice danger"' in md and "Issuer and ISIN are required." in md


def test_empty_book_is_a_cold_start(apptest, monkeypatch, tmp_path):
    import core.db
    monkeypatch.setattr(core.db, "DB_FILE", str(tmp_path / "empty.db"))
    at = apptest()
    at.run()
    md = _assert_clean(at, "cold start")
    assert "premium-header" in md and "lede-claim" in md and "outcome-grid" in md
    assert 'class="command-bar' not in md
    assert "Add a security under" in md
    _goto(at, "add-security")
    md = _assert_clean(at, "cold add-security")
    assert 'class="command-bar' in md and "NO POSITIONS" in md
    _goto(at, "record-transaction")
    md = _assert_clean(at, "cold record-transaction")
    assert "No securities yet" in md


def test_tracked_data_is_never_the_test_database():
    import os

    import core.db
    assert Path(core.db.DB_FILE).resolve() != (REPO / "data" / "db" / "portfolio.db").resolve()
    assert Path(os.environ["NIVESA_DATA_DIR"]).resolve() != (REPO / "data").resolve()


def test_golden_copy_helper_does_not_touch_tracked_data(tmp_path):
    """Sanity for anyone extending the suite: copying the book is the only way tests reach it."""
    shutil.copytree(REPO / "data", tmp_path / "data")
    assert (tmp_path / "data" / "db" / "portfolio.db").exists()
