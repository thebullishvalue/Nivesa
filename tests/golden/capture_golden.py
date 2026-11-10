"""
Capture the golden book from the ORIGINAL Nivesa 2.8.0 code (``app_2_8_0.py`` = ``app.py`` at commit
8090864), with the date frozen, against a throwaway copy of ``data/``.

Run by hand only (never by pytest) when the book itself changes:

    python tests/golden/capture_golden.py            # writes tests/golden/book_2026-11-10.json

How the inline dashboard aggregates are captured from the original code path: the original source is
loaded as text, one ``_CAP[...] = ...copy()`` line is inserted after each statement that finishes an
aggregate inside ``page_dashboard`` / ``page_view_transactions`` / ``page_securities_master`` (anchors are
asserted to match exactly once), and the instrumented copy is executed in Streamlit's bare mode with every
filter selectbox answered per account. Nothing in the original logic is edited; the inserted lines only
copy values out. ``_render_metric`` is intercepted to record the displayed KPI strings.

The file stores numbers in full precision. Free-text fields that would name the book's holdings (issuer,
ISIN, notes) are stored as short SHA-256 digests, so the golden file can sit in the repository without
spelling out the portfolio; ``tests/test_golden.py`` hashes the refactored output the same way.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import os
import shutil
import sqlite3
import sys
import tempfile
import types
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parent
REPO = GOLDEN_DIR.parents[1]
ORIGINAL = GOLDEN_DIR / "app_2_8_0.py"
AS_OF = _dt.date(2026, 11, 10)
OUT = GOLDEN_DIR / f"book_{AS_OF.isoformat()}.json"

#: Free-text columns hashed in the golden file (raw and display-renamed spellings).
HASH_COLS = {"issuer", "isin", "notes", "Issuer", "ISIN", "Notes", "Security"}


# ── frozen clock ──────────────────────────────────────────────────────────────
class FrozenDate(_dt.date):
    @classmethod
    def today(cls):
        return cls(AS_OF.year, AS_OF.month, AS_OF.day)


class FrozenDatetime(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(AS_OF.year, AS_OF.month, AS_OF.day, 12, 0, 0, tzinfo=tz)


# ── serialisation (shared with tests/test_golden.py) ─────────────────────────
def digest(x) -> str | None:
    if x is None:
        return None
    try:
        if isinstance(x, float) and math.isnan(x):
            return None
    except TypeError:
        pass
    return "h:" + hashlib.sha256(str(x).encode("utf-8")).hexdigest()[:16]


def jsonable(v, col: str = ""):
    import numpy as np
    import pandas as pd
    if col in HASH_COLS:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return digest(v)
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return None if math.isnan(f) else f
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.isoformat()
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, pd.Period):
        return str(v)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return str(v)


def frame_records(df) -> list[dict]:
    """A DataFrame as JSON records (index dropped; reset it first if it carries data)."""
    if df is None:
        return []
    return [{c: jsonable(v, str(c)) for c, v in row.items()} for row in df.to_dict(orient="records")]


def book_fingerprint(db_file: str) -> str:
    """Content digest of the three tables (sorted rows) — the golden is valid only for this book."""
    con = sqlite3.connect(db_file)
    try:
        h = hashlib.sha256()
        for t, cols in (("securities", "bond_id, issuer, isin, maturity_date, frequency, coupon_rate, face_value"),
                        ("transactions", "transaction_id, bond_id, account, trade_date, transaction_type, units, "
                                         "price, amount, notes"),
                        ("security_metadata", "bond_id, bond_type, credit_rating, day_count, issue_date, call_date, "
                                              "put_date, listing, sector, notes")):
            for r in sorted(con.execute(f"SELECT {cols} FROM {t}").fetchall(), key=repr):
                h.update(repr(r).encode("utf-8"))
        return h.hexdigest()
    finally:
        con.close()


# ── instrumentation ──────────────────────────────────────────────────────────
#: (anchor text in the original, line inserted AFTER it — or BEFORE when the tuple says so).
_INSERTS = (
    ("    df['ytc_valid_c'] = df['cost_basis'].where(df['yield_to_cost'] > 0, 0.0)\n",
     "    _CAP['df'] = df.copy()\n", "after"),
    ("            acct_agg = acct_agg.sort_values('Cost', ascending=False)\n",
     "            _CAP['acct_agg'] = acct_agg.copy()\n", "after"),
    ("        ir = ir.sort_values('Cost', ascending=False)\n",
     "        _CAP['concentration'] = ir.copy()\n", "after"),
    ("        filtered = filtered.sort_values('cost_basis', ascending=False)\n",
     "        _CAP['positions'] = filtered.copy()\n", "after"),
    ("        exp = exp.rename(columns=col_map)\n",
     "        _CAP['positions_export'] = exp.copy()\n", "after"),
    ("        fig = go.Figure()\n        fig.add_trace(go.Bar(\n            x=bucket_agg.index,",
     "        _CAP['maturity_frame'] = mat_df.copy(); _CAP['maturity_buckets'] = bucket_agg.copy()\n", "before"),
    ("                mat_str = pd.to_datetime(p['maturity_date']).strftime('%d %b %Y')\n"
     "                rows += (\n                    f\"<tr><td>{bucket}</td>\"",
     "                _CAP.setdefault('maturity_rows', []).append(dict(bucket=bucket, bond_id=p['bond_id'], "
     "account=p['account'], issuer=p['issuer'], position_face_value=p['position_face_value'], "
     "coupon_rate=p['coupon_rate'], maturity_date=p['maturity_date'], "
     "days_to_maturity=p['days_to_maturity']))\n", "before"),
    ("            mcf['ms'] = mcf['mo'].astype(str)\n",
     "            _CAP['cashflow_all'] = cdf.copy(); _CAP['cashflow_monthly'] = mcf.copy(); "
     "_CAP['has_amort'] = has_amort\n", "after"),
    ("            total_prin = cdf['principal'].sum()\n",
     "            _CAP['cashflow_totals'] = dict(total_cpn=total_cpn, total_prin=total_prin, "
     "total=total_cpn + total_prin)\n", "after"),
    ("            n12 = cdf[cdf['date'] <= cutoff]\n",
     "            _CAP['nearterm'] = n12.copy()\n", "after"),
    ("        idd = idd.sort_values('Cost', ascending=False)\n",
     "        _CAP['issuer_detail'] = idd.copy()\n", "after"),
    ("        filt_ledger = ltdf if led_filter == 'All' else ltdf[ltdf['account'] == led_filter]\n",
     "        _CAP['ledger_tab'] = filt_ledger.copy()\n", "after"),
    ("    ledger = db_query(query, tuple(params))\n",
     "    _CAP['ledger_page_raw'] = ledger.copy()\n", "after"),
    ("    ledger['trade_date'] = pd.to_datetime(ledger['trade_date']).dt.strftime('%d %b %Y')\n",
     "    _CAP['ledger_page'] = ledger.copy()\n", "after"),
    ("    rows = \"\"\n    for _, s in filtered_secs.iterrows():\n",
     "    _CAP['securities'] = filtered_secs.copy()\n", "before"),
)


def instrumented_source() -> str:
    src = ORIGINAL.read_text(encoding="utf-8")
    for anchor, line, where in _INSERTS:
        assert src.count(anchor) == 1, f"anchor not unique: {anchor[:60]!r}"
        src = src.replace(anchor, anchor + line if where == "after" else line + anchor)
    return src


class _Widgets:
    """Answers the filter widgets the way a user would pick them; everything else is real Streamlit."""

    def __init__(self, real_st, answers: dict):
        self._st, self._answers = real_st, answers

    def __getattr__(self, name):
        return getattr(self._st, name)

    def selectbox(self, label, options, index=0, *a, key=None, **k):
        options = list(options)
        if key in self._answers:
            return self._answers[key]
        if index is None:
            return None
        return options[index] if options else None

    def text_input(self, label, value="", *a, key=None, **k):
        return self._answers.get(key, value)


def load_original(data_dir: str):
    os.environ["NIVESA_DATA_DIR"] = data_dir
    mod = types.ModuleType("nivesa_original")
    mod.__file__ = str(ORIGINAL)
    mod.__dict__["_CAP"] = {}
    code = compile(instrumented_source(), str(ORIGINAL), "exec")
    exec(code, mod.__dict__)
    mod.date = FrozenDate
    mod.datetime = FrozenDatetime
    mod.__dict__["_METRICS"] = []

    def _metric(col, style, title, value, sub="", icon=""):
        mod.__dict__["_METRICS"].append([title, value, sub])
    mod._render_metric = _metric
    return mod


def capture(data_dir: str) -> dict:
    import pandas as pd
    import streamlit as real_st

    mod = load_original(data_dir)
    mod.db_init()
    df, totals = mod.get_positions_dataframe()
    accounts = sorted(df["account"].unique().tolist())
    ledger = mod.get_transaction_ledger_dataframe()

    out: dict = {
        "meta": {
            "as_of": AS_OF.isoformat(),
            "source": "app.py @ 8090864 (Nivesa 2.8.0), instrumented copy, bare-mode run",
            "fingerprint": book_fingerprint(os.path.join(data_dir, "db", "portfolio.db")),
            "accounts": accounts,
            "hashed_columns": sorted(HASH_COLS),
        },
        "positions": {"rows": frame_records(df), "totals": {k: jsonable(v) for k, v in totals.items()}},
        "ledger": frame_records(ledger),
        "dashboard": {},
        "ledger_page": {},
    }

    for flt in ["All"] + accounts:
        mod._CAP.clear()
        mod._METRICS.clear()
        keys = ("conc_acct", "pf", "mat_acct", "cf_acct", "iss_acct", "led_acct")
        mod.st = _Widgets(real_st, {k: flt for k in keys})
        mod.page_dashboard()
        cap = dict(mod._CAP)
        rec = {
            "concentration": frame_records(cap["concentration"]),
            "positions": frame_records(cap["positions"]),
            "positions_export": frame_records(cap["positions_export"]),
            "maturity_frame_mb": [[r["bond_id"], r["account"], r["mb"]] for _, r in cap["maturity_frame"].iterrows()],
            "maturity_buckets": frame_records(cap["maturity_buckets"].reset_index()),
            "maturity_rows": [{k: jsonable(v, k) for k, v in r.items()} for r in cap.get("maturity_rows", [])],
            "issuer_detail": frame_records(cap["issuer_detail"].reset_index()),
            "ledger_tab": frame_records(cap["ledger_tab"]),
            "metrics": mod._METRICS[5:],      # the three cashflow cards (the first five are the KPI row)
        }
        if "cashflow_monthly" in cap:
            rec["cashflow_monthly"] = frame_records(cap["cashflow_monthly"].drop(columns=["mo"]))
            rec["cashflow_count"] = int(len(cap["cashflow_all"]))
            rec["has_amort"] = bool(cap["has_amort"])
            rec["cashflow_totals"] = {k: jsonable(v) for k, v in cap["cashflow_totals"].items()}
            rec["nearterm"] = frame_records(cap["nearterm"].drop(columns=["mo"]))
        if flt == "All":
            out["dashboard"]["kpi_metrics"] = mod._METRICS[:5]
            out["dashboard"]["helper_columns"] = frame_records(cap["df"][["bond_id", "account", "ny_c", "ytc_c",
                                                                          "ytc_valid_c"]])
            out["dashboard"]["capital_allocation"] = frame_records(cap["acct_agg"])
        out["dashboard"][flt] = rec

    # The Transaction Ledger page — default filters, then each account and each type.
    variants = [("All", "All", "")] + [(a, "All", "") for a in accounts] + \
               [("All", t, "") for t in mod.TRANSACTION_TYPES]
    for acct, typ, search in variants:
        mod._CAP.clear()
        mod.st = _Widgets(real_st, {"la": acct, "lt": typ, "ls": search})
        mod.page_view_transactions()
        raw = mod._CAP.get("ledger_page_raw", pd.DataFrame())
        out["ledger_page"][f"{acct}|{typ}|{search}"] = {
            "raw": frame_records(raw),
            "display": frame_records(mod._CAP.get("ledger_page")),
        }

    # The Securities Master page — default filters.
    mod._CAP.clear()
    mod.st = _Widgets(real_st, {})
    mod.page_securities_master()
    secs = mod._CAP["securities"].copy()
    secs["days"] = [mod.calc_days_to_maturity(m) for m in secs["maturity_date"]]
    out["securities_master"] = frame_records(secs)
    return out


def main() -> None:
    tmp = tempfile.mkdtemp(prefix="nivesa-golden-")
    data_dir = os.path.join(tmp, "data")
    shutil.copytree(REPO / "data", data_dir)
    try:
        out = capture(data_dir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    OUT.write_text(json.dumps(out, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} · {len(out['positions']['rows'])} positions · "
          f"{len(out['ledger'])} ledger rows")


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    main()
