"""
The golden book: every number Nivesa 2.8.0 displayed, captured from the ORIGINAL code path
(``tests/golden/capture_golden.py`` over ``tests/golden/app_2_8_0.py``, date frozen to 2026-11-10),
reproduced by the refactored ``core`` package to a float tolerance of 1e-9.

Runs offline against a fresh copy of ``data/`` (never the tracked file). If the book itself has changed
since the capture (new transactions), the fingerprint differs and the module is skipped with the command
that re-captures it — a changed book is not a regression.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pandas as pd
import pytest

from capture_golden import (AS_OF, OUT, FrozenDate, FrozenDatetime, book_fingerprint, frame_records,
                            jsonable)

REPO = Path(__file__).resolve().parents[1]
GOLDEN = json.loads(Path(OUT).read_text(encoding="utf-8"))
FILTERS = ["All"] + GOLDEN["meta"]["accounts"]
TOL = 1e-9


def _same(a, b, path: str) -> None:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        assert math.isclose(float(a), float(b), rel_tol=TOL, abs_tol=TOL), f"{path}: {a!r} != {b!r}"
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


def assert_records(actual: list[dict], expected: list[dict], path: str) -> None:
    assert len(actual) == len(expected), f"{path}: {len(actual)} rows != {len(expected)}"
    for i, (ra, re_) in enumerate(zip(actual, expected)):
        assert set(ra) == set(re_), f"{path}[{i}] columns: {sorted(set(ra) ^ set(re_))}"
        for k in re_:
            _same(ra[k], re_[k], f"{path}[{i}].{k}")


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    """A fresh copy of the book, the date frozen in every core module, the positions computed once."""
    data = tmp_path_factory.mktemp("golden") / "data"
    shutil.copytree(REPO / "data", data)
    db = data / "db" / "portfolio.db"
    if book_fingerprint(str(db)) != GOLDEN["meta"]["fingerprint"]:
        pytest.skip("the book changed since the golden capture — re-capture with "
                    "`python tests/golden/capture_golden.py` (on the ORIGINAL code) before refactoring")
    import core.bonds
    import core.book
    import core.db
    import core.views
    mp = pytest.MonkeyPatch()
    mp.setattr(core.db, "DB_FILE", str(db))
    for m in (core.bonds, core.book, core.views):
        mp.setattr(m, "date", FrozenDate)
    core.db.db_init()
    df, totals = core.book.get_positions_dataframe()
    yield df, totals
    mp.undo()


def test_clock_is_frozen(book):
    import core.views
    assert core.views.date.today() == AS_OF and FrozenDatetime.now().date() == AS_OF


def test_positions_frame_and_totals(book):
    df, totals = book
    assert_records(frame_records(df), GOLDEN["positions"]["rows"], "positions")
    exp = GOLDEN["positions"]["totals"]
    assert set(totals) == set(exp)
    for k, v in exp.items():
        _same(jsonable(totals[k]), v, f"totals.{k}")


def test_transaction_ledger(book):
    from core.book import get_transaction_ledger_dataframe
    assert_records(frame_records(get_transaction_ledger_dataframe()), GOLDEN["ledger"], "ledger")


def test_helper_columns_and_capital_allocation(book):
    from core.views import add_weight_columns, capital_allocation
    df = add_weight_columns(book[0].copy())
    assert_records(frame_records(df[["bond_id", "account", "ny_c", "ytc_c", "ytc_valid_c"]]),
                   GOLDEN["dashboard"]["helper_columns"], "helper_columns")
    assert_records(frame_records(capital_allocation(df)), GOLDEN["dashboard"]["capital_allocation"],
                   "capital_allocation")


@pytest.mark.parametrize("flt", FILTERS)
def test_dashboard_aggregates_per_account_filter(book, flt):
    from core.formatting import fmt_inr_short
    from core.views import (add_weight_columns, cashflow_projection, cashflow_totals, issuer_concentration,
                            issuer_detail, ledger_tab, maturity_ladder, maturity_rows, nearterm_cashflows,
                            positions_export, positions_table)
    g = GOLDEN["dashboard"][flt]
    df = add_weight_columns(book[0].copy())

    assert_records(frame_records(issuer_concentration(df, flt)), g["concentration"], f"{flt}.concentration")
    pos = positions_table(df, flt)
    assert_records(frame_records(pos), g["positions"], f"{flt}.positions")
    assert_records(frame_records(positions_export(pos)), g["positions_export"], f"{flt}.positions_export")

    mat_df, buckets = maturity_ladder(df, flt)
    assert [[r["bond_id"], r["account"], r["mb"]] for _, r in mat_df.iterrows()] == g["maturity_frame_mb"]
    assert_records(frame_records(buckets.reset_index()), g["maturity_buckets"], f"{flt}.maturity_buckets")
    rows = [{k: jsonable(r[k], k) for k in ("bond_id", "account", "issuer", "position_face_value", "coupon_rate",
                                            "maturity_date", "days_to_maturity")} | {"bucket": r["mb"]}
            for _, r in maturity_rows(mat_df).iterrows()]
    assert_records(rows, g["maturity_rows"], f"{flt}.maturity_rows")

    assert_records(frame_records(issuer_detail(df, flt).reset_index()), g["issuer_detail"], f"{flt}.issuer_detail")
    assert_records(frame_records(ledger_tab(flt)), g["ledger_tab"], f"{flt}.ledger_tab")

    cdf, mcf, has_amort = cashflow_projection(df, flt)
    assert len(cdf) == g["cashflow_count"] and has_amort is g["has_amort"]
    assert_records(frame_records(mcf.drop(columns=["mo"])), g["cashflow_monthly"], f"{flt}.cashflow_monthly")
    cpn, prin, tot = cashflow_totals(cdf)
    for k, v in (("total_cpn", cpn), ("total_prin", prin), ("total", tot)):
        _same(float(v), g["cashflow_totals"][k], f"{flt}.cashflow_totals.{k}")
    assert_records(frame_records(nearterm_cashflows(cdf).drop(columns=["mo"])), g["nearterm"], f"{flt}.nearterm")
    # the three cashflow cards, as displayed
    assert [m[1] for m in g["metrics"]] == [fmt_inr_short(cpn), fmt_inr_short(prin), fmt_inr_short(cpn + prin)]


@pytest.mark.parametrize("key", list(GOLDEN["ledger_page"]))
def test_ledger_page_query(book, key):
    from core.views import ledger_page
    acct, typ, search = key.split("|")
    raw = ledger_page(acct, typ, search)
    assert_records(frame_records(raw), GOLDEN["ledger_page"][key]["raw"], f"ledger_page[{key}]")
    if not raw.empty:
        disp = raw.copy()
        disp["trade_date"] = pd.to_datetime(disp["trade_date"]).dt.strftime("%d %b %Y")
        assert_records(frame_records(disp), GOLDEN["ledger_page"][key]["display"], f"ledger_page[{key}].display")


def test_securities_master(book):
    from core.views import securities_master
    assert_records(frame_records(securities_master()), GOLDEN["securities_master"], "securities_master")


def test_overview_kpis_display_the_original_values(book):
    """The Overview KPI strip prints the same five values the 2.8.0 metric cards printed ("N/A" → "—")."""
    from ui.pages.page_overview import overview_kpis
    items = overview_kpis(book[1])
    want = [v if v != "N/A" else "—" for _t, v, _s in GOLDEN["dashboard"]["kpi_metrics"]]
    assert [i["value"] for i in items] == want
