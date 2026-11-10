"""
The four Analytics pages (Positions · Cashflows · Maturity · Issuers) through AppTest, against the
throwaway copy of the book with the clock frozen to the golden capture's date:

  · every option of each page's Account filter (All + every account that holds a position — 2.8.0's
    options) renders with no exception, no "nan"/"None"/"N/A" text and none of the retired widgets, with
    the filterbar strip directly above what it filters and the account named in the panels' context;
  · the KPI strings on each page are the golden values the 2.8.0 code displayed, or the golden numbers
    through Nivesa's own formatters (``fmt_inr_short`` / ``fmt_pct``);
  · the Cashflows window renders for every forward horizon;
  · the presentation helpers added to ``core.views`` only slice: windows, top-N, concentration lines.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from capture_golden import AS_OF, OUT, FrozenDate, book_fingerprint
import test_app
from test_app import _assert_clean, _goto, _md

from core.formatting import fmt_inr_short, fmt_pct

REPO = Path(__file__).resolve().parents[1]
GOLDEN = json.loads(Path(OUT).read_text(encoding="utf-8"))
ACCOUNTS = ["All"] + GOLDEN["meta"]["accounts"]
TOTALS = GOLDEN["positions"]["totals"]
apptest = test_app.apptest      # the suite's AppTest fixture (with its segmented-control shim)
PAGES = {"positions": "pf", "cashflows": "cf_acct", "maturity": "mat_acct", "issuers": "iss_acct"}


@pytest.fixture
def frozen(monkeypatch):
    """The date frozen in every core module (as the golden test does) and the book cache emptied on both
    sides, so no figure computed on another clock leaks in or out."""
    import streamlit as st

    import core.bonds
    import core.book
    import core.db
    import core.views
    if book_fingerprint(core.db.DB_FILE) != GOLDEN["meta"]["fingerprint"]:
        pytest.skip("the book changed since the golden capture")
    for m in (core.bonds, core.book, core.views):
        monkeypatch.setattr(m, "date", FrozenDate)
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def _kpi_values(md: str) -> list[str]:
    import html
    return [html.unescape(v) for v in re.findall(r'class="metric-card [a-z]+">.*?<h2>(.*?)</h2>', md, flags=re.S)]


def _contexts(md: str) -> list[str]:
    import html
    return [html.unescape(v) for v in re.findall(r'<span class="ph-context">(.*?)</span>', md)]


def _open(apptest, url: str):
    at = apptest()
    at.run()
    _goto(at, url)
    _assert_clean(at, url)
    return at


def _pick(at, key: str, acct: str, where: str) -> str:
    box = at.selectbox(key=key)
    assert box.label == "Account" and list(box.options) == ACCOUNTS, where
    box.select(acct).run()
    md = _assert_clean(at, where)
    assert at.selectbox(key=key).value == acct, where
    return md


def _scope(acct: str) -> str:
    return "ALL ACCOUNTS" if acct == "All" else acct.upper()


# ── Positions ────────────────────────────────────────────────────────────────
def test_positions_page_kpis_are_the_golden_values(apptest, frozen):
    at = _open(apptest, "positions")
    md = _md(at)
    want = [str(TOTALS["Num Positions"]), fmt_inr_short(TOTALS["Total Cost Basis"]),
            fmt_inr_short(TOTALS["Total Face Value"]), fmt_pct(TOTALS["Weighted YTC"]),
            fmt_inr_short(TOTALS["Total Accrued Interest"])]
    kpis = _kpi_values(md)
    assert kpis[:5] == want
    # the 2.8.0 metric cards, as displayed: cost, yield, composition
    shown = {t: v for t, v, _s in GOLDEN["dashboard"]["kpi_metrics"]}
    assert kpis[1] == shown["Total Invested (Cost)"] and kpis[3] == shown["Portfolio Yield (WA)"]
    assert kpis[0] == shown["Portfolio Composition"]
    assert [b.label for b in at.get("download_button")] == ["Download positions (CSV)"]


@pytest.mark.parametrize("acct", ACCOUNTS)
def test_positions_page_every_account(apptest, frozen, acct):
    at = _open(apptest, "positions")
    md = _pick(at, PAGES["positions"], acct, f"positions/{acct}")
    n = len(GOLDEN["dashboard"][acct]["positions"])
    assert f"{_scope(acct)} · {n} position{'s' if n != 1 else ''} · largest cost first" in _contexts(md)


# ── Cashflows ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("acct", ACCOUNTS)
def test_cashflows_page_cards_are_the_golden_values_per_account(apptest, frozen, acct):
    at = _open(apptest, "cashflows")
    md = _pick(at, PAGES["cashflows"], acct, f"cashflows/{acct}")
    g = GOLDEN["dashboard"][acct]
    assert _kpi_values(md) == [v for _t, v, _s in g["metrics"]]          # 2.8.0's three cards, as printed
    ctx = _contexts(md)
    assert any(c.startswith(f"{_scope(acct)} · 6M · ") for c in ctx), ctx
    n12 = len(g["nearterm"])
    assert f"{_scope(acct)} · next 12 months · {n12} payment{'s' if n12 != 1 else ''}" in ctx
    assert ('<span class="k">Window</span>' in md)


@pytest.mark.parametrize("tf", ["3M", "6M", "1Y", "2Y", "ALL"])
def test_cashflows_page_every_forward_window(apptest, frozen, tf):
    at = apptest()
    at.session_state["tf_selected"] = tf
    at.run()
    _goto(at, "cashflows")
    md = _assert_clean(at, f"cashflows/{tf}")
    assert any(c.startswith(f"ALL ACCOUNTS · {tf} · ") for c in _contexts(md)), tf
    assert f'<span class="k">Window</span><span class="v">{tf}</span>' in md.replace("\n", "")


# ── Maturity ─────────────────────────────────────────────────────────────────
def test_maturity_page_kpis_are_the_golden_values(apptest, frozen):
    at = _open(apptest, "maturity")
    kpis = _kpi_values(_md(at))
    shown = {t: (v, s) for t, v, s in GOLDEN["dashboard"]["kpi_metrics"]}
    assert kpis[0] == shown["Weighted Duration"][0]
    assert f"Modified {TOTALS['Weighted Mod Duration']:.2f}y" == shown["Weighted Duration"][1].replace(": ", " ")
    assert kpis[1] == f"{TOTALS['Weighted Avg Maturity']:.2f}y"
    rows = [r for r in GOLDEN["dashboard"]["All"]["maturity_rows"] if r["bucket"] != "Matured"]
    first = min(r["maturity_date"] for r in rows)
    assert kpis[2] == FrozenDate.fromisoformat(first[:10]).strftime("%d %b %Y")
    assert kpis[3] == fmt_inr_short(sum(r["principal"] for r in GOLDEN["dashboard"]["All"]["nearterm"]))
    matured = sum(b["N"] for b in GOLDEN["dashboard"]["All"]["maturity_buckets"] if b["mb"] == "Matured")
    assert kpis[4] == str(int(matured))


@pytest.mark.parametrize("acct", ACCOUNTS)
def test_maturity_page_every_account(apptest, frozen, acct):
    at = _open(apptest, "maturity")
    md = _pick(at, PAGES["maturity"], acct, f"maturity/{acct}")
    g = GOLDEN["dashboard"][acct]
    nb, nr = len(g["maturity_buckets"]), len(g["maturity_rows"])
    ctx = _contexts(md)
    assert f"{_scope(acct)} · {nb} bucket{'s' if nb != 1 else ''} · face and cost by time to maturity · ₹ lakh" in ctx
    assert any(c.startswith(f"{_scope(acct)} · {nr} position") for c in ctx), ctx


# ── Issuers ──────────────────────────────────────────────────────────────────
def test_issuers_page_kpis_are_the_golden_values(apptest, frozen):
    at = _open(apptest, "issuers")
    kpis = _kpi_values(_md(at))
    conc = GOLDEN["dashboard"]["All"]["concentration"]
    assert kpis[0] == str(len(conc)) == str(TOTALS["Num Issuers"])
    assert kpis[1] == fmt_pct(conc[0]["Wt"])
    assert kpis[2] == fmt_pct(sum(r["Wt"] for r in conc[:5]))
    assert kpis[3] == str(sum(r["Wt"] >= 0.05 for r in conc))


@pytest.mark.parametrize("acct", ACCOUNTS)
def test_issuers_page_every_account(apptest, frozen, acct):
    at = _open(apptest, "issuers")
    md = _pick(at, PAGES["issuers"], acct, f"issuers/{acct}")
    g = GOLDEN["dashboard"][acct]
    ni, nd = len(g["concentration"]), len(g["issuer_detail"])
    ctx = _contexts(md)
    assert f"{_scope(acct)} · {ni} issuer{'s' if ni != 1 else ''} · heaviest first" in ctx
    assert any(c.startswith(f"{_scope(acct)} · {nd} securit") for c in ctx), ctx


# ── Anatomy, shared ──────────────────────────────────────────────────────────
def _layout(at) -> list[str]:
    """The main area's anatomy in render order: section headers, the filterbar, KPI strips, panels."""
    out = []
    for n in at.main:
        if type(n).__name__ == "Block" and n.proto is not None and n.proto.id:
            key = n.proto.id.split("-", 2)[2] if n.proto.id.startswith("$$ID-") else n.proto.id
            if key == "filterbar":
                out.append("FILTER")
            elif key.endswith("-kpis"):
                out.append("KPI")
            elif key.startswith("panel-"):
                out.append("PANEL")
        elif type(n).__name__ == "Markdown" and 'class="section-hdr' in n.value:
            out.append("HDR")
    return out


@pytest.mark.parametrize("url", list(PAGES))
def test_filterbar_sits_above_what_it_filters(apptest, frozen, url):
    """One Account filterbar per page, after the page's answer and directly above the first thing it
    filters: the panels on Positions / Maturity / Issuers (whose KPI strip is the whole book), the KPI
    strip itself on Cashflows (whose three cards are the chosen account's, as in 2.8.0)."""
    at = _open(apptest, url)
    lay = _layout(at)
    assert lay.count("FILTER") == 1 and lay.count("KPI") == 1, lay
    f = lay.index("FILTER")
    assert lay[0] == "HDR" and "PANEL" in lay[f + 1:], lay
    assert lay[f + 1] == ("KPI" if url == "cashflows" else "PANEL"), lay
    if url != "cashflows":
        assert lay[:3] == ["HDR", "KPI", "HDR"], lay
    assert len(at.selectbox) == 1 and at.selectbox[0].label == "Account"


def test_analytics_pages_name_no_colour_and_use_no_retired_widget():
    """Colours resolve per render (chart_color / chart_rgba), never as literals; rule 133 at the source."""
    for name in ("page_positions", "page_cashflows", "page_maturity", "page_issuers", "_analytics"):
        src = (REPO / "ui" / "pages" / f"{name}.py").read_text(encoding="utf-8")
        assert not re.search(r"#[0-9A-Fa-f]{6}\b|(?<!\w)rgba?\(", src), name
        for bad in ("st.dataframe", "st.expander", "st.tabs", "st.caption", "st.info", "st.warning",
                    "st.success", "st.error", "st.metric", "st.plotly_chart", "st.table"):
            assert bad not in src, (name, bad)


# ── core.views presentation helpers ─────────────────────────────────────────
def test_forward_window_slices_whole_months_from_this_month(monkeypatch):
    import pandas as pd

    import core.views as v
    monkeypatch.setattr(v, "date", FrozenDate)
    assert set(v.FORWARD_WINDOW_MONTHS) | {"ALL"} == set(__import__("ui.components", fromlist=["WINDOWS"]).WINDOWS)
    assert v.forward_window_end("ALL") is None and v.forward_window_end(None) is None
    assert str(v.forward_window_end("3M")) == "2027-02" and str(v.forward_window_end("1Y")) == "2027-11"
    mcf = pd.DataFrame({"mo": pd.period_range("2026-11", periods=30, freq="M"), "Coupon": range(30)})
    assert list(v.in_forward_window(mcf, "3M")["mo"].astype(str)) == ["2026-11", "2026-12", "2027-01"]
    assert len(v.in_forward_window(mcf, "2Y")) == 24 and len(v.in_forward_window(mcf, "ALL")) == 30
    assert AS_OF.isoformat() == "2026-11-10"


def test_concentration_lines_and_top_n():
    import pandas as pd

    import core.views as v
    assert (v.CONCENTRATION_CAUTION, v.CONCENTRATION_DANGER) == (0.05, 0.10)
    assert [v.concentration_tier(w) for w in (0.0, 0.0499, 0.05, 0.0999, 0.10, 0.4, float("nan"), None)] == [
        "neutral", "neutral", "caution", "caution", "danger", "danger", "neutral", "neutral"]
    ir = pd.DataFrame({"issuer": list("abcdefg"), "Wt": [0.3, 0.2, 0.15, 0.1, 0.1, 0.1, 0.05]})
    assert v.top_share(ir, 5) == pytest.approx(0.85) and len(v.top_issuers(ir, 3)) == 3
    assert v.top_share(ir.iloc[0:0], 5) == 0.0


def test_helpers_on_the_golden_book(frozen):
    import core.views as v
    from core.book import get_positions_dataframe
    df, _t = get_positions_dataframe()
    df = v.add_weight_columns(df)
    for acct in ACCOUNTS:
        conc = GOLDEN["dashboard"][acct]["concentration"]
        ir = v.issuer_concentration(df, acct)
        assert v.top_share(ir, 5) == pytest.approx(sum(r["Wt"] for r in conc[:5]), abs=1e-12)
    nxt = v.next_maturities(df)
    rows = [r for r in GOLDEN["dashboard"]["All"]["maturity_rows"] if r["bucket"] != "Matured"]
    first = min(r["maturity_date"] for r in rows)
    assert len(nxt) == sum(r["maturity_date"] == first for r in rows) and len(nxt) >= 1


def _table_html(at) -> str:
    """Every iframe table's document on the page (``render_data_table`` draws into components.html)."""
    out = []
    for n in at.main:
        proto = getattr(n, "proto", None)
        doc = getattr(proto, "srcdoc", "") if proto is not None else ""
        if doc:
            out.append(doc)
    return " ".join(out)


def test_positions_realized_pnl_column_appears_signed_when_any_position_has_one(apptest, frozen, monkeypatch):
    """The book has no realized P&L today, so the column is absent; give two positions some and it
    appears, signed (+₹ / −₹) and sign-coloured, with nan/None nowhere."""
    import ui.pages.page_positions as pp
    real = pp.load_book

    def fake():
        df, totals = real()
        df.loc[df.index[0], "realized_pnl"] = 1234.5
        df.loc[df.index[1], "realized_pnl"] = -99.0
        return df, totals

    at = _open(apptest, "positions")
    assert "Realized P&amp;L" not in _table_html(at) and "Realized P&L" not in _table_html(at)
    monkeypatch.setattr(pp, "load_book", fake)
    at.run()
    _assert_clean(at, "positions with P&L")
    doc = _table_html(at)
    assert "Realized P&amp;L" in doc and "+₹1,234.50" in doc and "−₹99.00" in doc


def test_maturity_page_shows_a_matured_position_in_amber(apptest, frozen, monkeypatch):
    """The book has nothing past maturity today; move one live position's maturity into the past and the
    ladder grows a Matured bucket (face bar amber), the table lists it under Matured and the KPI counts it."""
    import pandas as pd

    import ui.pages.page_maturity as pm
    real = pm.load_book

    def fake():
        df, totals = real()
        df["maturity_date"] = pd.to_datetime(df["maturity_date"])
        df.loc[df.index[0], "maturity_date"] = pd.Timestamp("2026-10-01")
        df.loc[df.index[0], "days_to_maturity"] = 0
        return df, totals

    monkeypatch.setattr(pm, "load_book", fake)
    at = _open(apptest, "maturity")
    md = _md(at)
    kpis = _kpi_values(md)
    assert kpis[4] == "1" and 'class="metric-card warning"><span class="label">Matured, Unredeemed' in md
    assert ">Matured<" in _table_html(at)
    spec = " ".join(getattr(getattr(n, "proto", None), "spec", "") or "" for n in at.main
                    if type(n).__name__ == "UnknownElement")
    assert '"Matured"' in spec and "#96660F" in spec          # Paper's amber, resolved at render


@pytest.mark.parametrize("url", list(PAGES))
def test_analytics_pages_on_an_empty_book(apptest, monkeypatch, tmp_path, url):
    """With no live position each page keeps its header and says so in one empty state."""
    import core.db
    monkeypatch.setattr(core.db, "DB_FILE", str(tmp_path / "empty.db"))
    at = apptest()
    at.run()
    _goto(at, url)
    md = _assert_clean(at, f"empty {url}")
    assert 'class="empty-state"' in md and 'class="section-hdr' in md and not at.selectbox
