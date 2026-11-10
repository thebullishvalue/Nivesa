# -*- coding: utf-8 -*-
"""
Nivesa — the views the UI reads: every aggregate the 2.8.0 dashboard computed inline, lifted into
pure functions, plus the shell's data (tape, command bar, freshness chip, notices, rail readout).

The aggregate bodies are the 2.8.0 ``page_dashboard`` / ``page_view_transactions`` /
``page_securities_master`` statements, verbatim: every statement line in the lifted functions below
appears character-for-character in ``tests/golden/app_2_8_0.py`` (``tests/test_source_identity.py``
asserts it). Lines that only adapt a statement to a function boundary (a parameter default, a
``return``) carry ``# seam``. ``tests/test_golden.py`` checks their output against the original code
path's values, captured with the date frozen.

Nothing here draws. ``date`` is a module global on purpose: the golden test freezes it.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from core.bonds import calc_days_to_maturity, generate_amortizing_schedule
from core.book import MATURITY_BUCKET_ORDER, _maturity_bucket, get_transaction_ledger_dataframe
from core.config import ACCOUNTS, PRODUCT_NAME, VERSION
from core.db import db_query
from core.formatting import fmt_inr, fmt_inr_short, fmt_pct

__all__ = [
    "add_weight_columns", "capital_allocation", "issuer_concentration", "positions_table", "positions_export",
    "maturity_ladder", "maturity_rows", "cashflow_projection", "cashflow_totals", "nearterm_cashflows",
    "issuer_detail", "ledger_tab", "ledger_page", "securities_master", "account_options",
    "allocation_by_bucket", "matured_mask", "maturing_soon", "tape_items", "command_bar", "book_notices",
    "rail_counts", "is_empty_book",
    "FORWARD_WINDOW_MONTHS", "forward_window_end", "in_forward_window", "CONCENTRATION_CAUTION",
    "CONCENTRATION_DANGER", "concentration_tier", "top_issuers", "top_share", "next_maturities",
]


# ═══════════════════════════════════════════════════════════════════════
# DASHBOARD AGGREGATES (2.8.0 page_dashboard, lifted verbatim)
# ═══════════════════════════════════════════════════════════════════════

def add_weight_columns(df):
    """The cost-weighting helper columns every grouped yield reads (mutates and returns ``df``)."""
    # Precompute weighted-yield helper columns (used across tabs)
    df['ny_c'] = df['nominal_yield'] * df['cost_basis']
    # YTC weighting excludes N/A (ytc<=0) positions from BOTH the numerator and
    # the denominator, matching the headline Weighted YTC. Zeroing only one side
    # would let a negative/NA position corrupt the group average.
    df['ytc_c'] = (df['yield_to_cost'] * df['cost_basis']).where(df['yield_to_cost'] > 0, 0.0)
    df['ytc_valid_c'] = df['cost_basis'].where(df['yield_to_cost'] > 0, 0.0)
    return df  # seam


def account_options(df):
    """The account filter's options: 'All' then the accounts that hold a position."""
    return ['All'] + sorted(df['account'].unique().tolist())  # seam


def capital_allocation(df):
    """Capital by account (positive cost basis only). Empty frame when nothing has a positive cost."""
    sb = df[df['cost_basis'] > 0].copy()
    if sb.empty:  # seam
        return pd.DataFrame()  # seam
    # Use positive-cost-basis total for accurate weight calculation
    total_cost_alloc = sb['cost_basis'].sum()
    acct_agg = sb.groupby('account').agg(
        Cost=('cost_basis', 'sum'),
        Face=('position_face_value', 'sum'),
        NY=('ny_c', 'sum'),
        YC=('ytc_c', 'sum'),
        ValidC=('ytc_valid_c', 'sum'),
        Pos=('bond_id', 'count'),
        Issuers=('issuer', 'nunique'),
        Inc=('annual_coupon_income', 'sum'),
    ).reset_index()
    acct_agg['Wt'] = acct_agg['Cost'] / total_cost_alloc if total_cost_alloc > 0 else 0
    acct_agg['NY'] = acct_agg.apply(lambda r: r['NY'] / r['Cost'] if r['Cost'] > 0 else 0, axis=1)
    acct_agg['YC'] = acct_agg.apply(lambda r: r['YC'] / r['ValidC'] if r['ValidC'] > 0 else 0, axis=1)
    acct_agg = acct_agg.sort_values('Cost', ascending=False)
    return acct_agg  # seam


def issuer_concentration(df, conc_filter='All'):  # seam
    """Cost by issuer within the account filter, heaviest first (the Concentration Risk table)."""
    conc_df = df if conc_filter == 'All' else df[df['account'] == conc_filter]
    total_cost_conc = conc_df['cost_basis'].sum()

    ir = conc_df.groupby('issuer').agg(
        Cost=('cost_basis', 'sum'),
        Face=('position_face_value', 'sum'),
        NY=('ny_c', 'sum'),
        YC=('ytc_c', 'sum'),
        ValidC=('ytc_valid_c', 'sum'),
        Pos=('bond_id', 'count'),
    ).reset_index()
    ir['Wt'] = ir['Cost'] / total_cost_conc if total_cost_conc > 0 else 0
    ir['NY'] = ir.apply(lambda r: r['NY'] / r['Cost'] if r['Cost'] > 0 else 0, axis=1)
    ir['YC'] = ir.apply(lambda r: r['YC'] / r['ValidC'] if r['ValidC'] > 0 else 0, axis=1)
    ir = ir.sort_values('Cost', ascending=False)
    return ir  # seam


def positions_table(df, acct_filter='All'):  # seam
    """The positions within the account filter, largest cost first."""
    filtered = df if acct_filter == 'All' else df[df['account'] == acct_filter]
    filtered = filtered.sort_values('cost_basis', ascending=False)
    return filtered  # seam


def positions_export(filtered):
    """The positions CSV export frame (yields scaled to percent to match their '(%)' labels)."""
    export_cols = [
        'issuer', 'isin', 'account', 'credit_rating', 'current_units',
        'cost_basis', 'position_face_value', 'nominal_yield', 'yield_to_cost',
        'macaulay_duration', 'modified_duration', 'maturity_date',
        'annual_coupon_income', 'interest_received', 'days_to_maturity',
    ]
    col_map = {
        'issuer': 'Issuer', 'isin': 'ISIN', 'account': 'Account',
        'credit_rating': 'Rating', 'current_units': 'Units',
        'cost_basis': 'Cost Basis', 'position_face_value': 'Face Value',
        'nominal_yield': 'Coupon Rate (%)', 'yield_to_cost': 'YTC (%)',
        'macaulay_duration': 'Mac Duration', 'modified_duration': 'Mod Duration',
        'maturity_date': 'Maturity Date', 'annual_coupon_income': 'Annual Income',
        'interest_received': 'Interest Received', 'days_to_maturity': 'Days Left'
    }
    exp = filtered[export_cols].copy()
    exp['maturity_date'] = pd.to_datetime(exp['maturity_date']).dt.strftime('%Y-%m-%d')
    # Yield columns are stored as decimal fractions; the export labels
    # them '(%)', so scale to percent to match the label.
    exp['nominal_yield'] = (exp['nominal_yield'] * 100).round(4)
    exp['yield_to_cost'] = (exp['yield_to_cost'] * 100).round(4)
    exp = exp.rename(columns=col_map)
    return exp  # seam


def maturity_ladder(df, mat_filter='All'):  # seam
    """``(mat_df, bucket_agg)``: positions tagged with their ladder bucket (``mb``), and cost / face /
    count per bucket for the buckets that hold something, in ladder order."""
    mat_df = df.copy() if mat_filter == 'All' else df[df['account'] == mat_filter].copy()

    _today_ts = pd.Timestamp(date.today())
    mat_df['mb'] = mat_df.apply(
        lambda p: _maturity_bucket(
            p['days_to_maturity'],
            matured=pd.to_datetime(p['maturity_date']) < _today_ts,
        ),
        axis=1,
    )
    # Only show buckets that actually hold something, in ladder order.
    present = [b for b in MATURITY_BUCKET_ORDER if (mat_df['mb'] == b).any()]
    bucket_agg = (
        mat_df.groupby('mb')
        .agg(Cost=('cost_basis', 'sum'), Face=('position_face_value', 'sum'), N=('bond_id', 'count'))
        .reindex(present)
        .fillna(0)
    )
    return mat_df, bucket_agg  # seam


def maturity_rows(mat_df):
    """The ladder table's rows: bucket by bucket in ladder order, soonest first within a bucket."""
    parts = []  # seam
    for bucket in MATURITY_BUCKET_ORDER:
        parts.append(mat_df[mat_df['mb'] == bucket].sort_values('days_to_maturity'))  # seam
    return pd.concat(parts) if parts else mat_df.iloc[0:0]  # seam


def cashflow_projection(df, cf_filter='All'):  # seam
    """``(cdf, mcf, has_amort)``: every projected future cashflow (one row per position-date, with
    issuer/account), the monthly coupon/principal series, and whether any position amortizes.
    ``cdf``/``mcf`` are empty frames when nothing is projected."""
    cf_df = df if cf_filter == 'All' else df[df['account'] == cf_filter]

    # No recorded-receipt dedup is needed here: transaction dates are
    # capped at today (date_input max_value) while the projected schedule
    # emits only strictly-future dates, so the two sets can never overlap.
    # A dedup-by-exact-date block previously here was provably dead code.
    all_cf = []
    has_amort = False
    for _, p in cf_df.iterrows():
        # One projection entry point for every position — the SAME stream
        # the duration engine discounts. generate_amortizing_schedule steps
        # the balance down when a cadence was inferred and degenerates to a
        # bullet when it wasn't, so the two views can no longer diverge.
        if p['principal_repaid'] > 0:
            has_amort = True
        schedule = generate_amortizing_schedule(
            p['position_face_value'], p['coupon_rate'], p['frequency'],
            p['maturity_date'], p['amort_installment'], p['amort_months'],
        )
        for cf in schedule:
            cf['issuer'] = p['issuer']
            cf['account'] = p['account']
            all_cf.append(cf)

    if not all_cf:  # seam
        return pd.DataFrame(), pd.DataFrame(), has_amort  # seam
    cdf = pd.DataFrame(all_cf)
    cdf['date'] = pd.to_datetime(cdf['date'])
    cdf = cdf.sort_values('date')
    cdf['mo'] = cdf['date'].dt.to_period('M')

    mcf = cdf.groupby('mo').agg(
        Coupon=('coupon', 'sum'), Principal=('principal', 'sum'),
    ).reset_index()
    mcf['ms'] = mcf['mo'].astype(str)
    return cdf, mcf, has_amort  # seam


def cashflow_totals(cdf):
    """``(future coupons, principal due, total future cashflow)`` over a projection."""
    total_cpn = cdf['coupon'].sum()
    total_prin = cdf['principal'].sum()
    return total_cpn, total_prin, total_cpn + total_prin  # seam


def nearterm_cashflows(cdf):
    """The projected cashflows dated within the next 365 days."""
    cutoff = pd.to_datetime(date.today() + timedelta(days=365))
    n12 = cdf[cdf['date'] <= cutoff]
    return n12  # seam


def issuer_detail(df, iss_filter='All'):  # seam
    """Cost / face / yields / units / income by (issuer, ISIN) within the filter, heaviest first."""
    iss_df = df if iss_filter == 'All' else df[df['account'] == iss_filter]

    idd = iss_df.groupby(['issuer', 'isin']).agg(
        Cost=('cost_basis', 'sum'),
        Face=('position_face_value', 'sum'),
        NY=('ny_c', 'sum'),
        YC=('ytc_c', 'sum'),
        ValidC=('ytc_valid_c', 'sum'),
        Units=('current_units', 'sum'),
        Inc=('annual_coupon_income', 'sum'),
    )
    total_cost_iss = iss_df['cost_basis'].sum()
    idd['Wt'] = idd['Cost'] / total_cost_iss if total_cost_iss > 0 else 0
    idd['NY'] = idd.apply(lambda r: r['NY'] / r['Cost'] if r['Cost'] > 0 else 0, axis=1)
    idd['YC'] = idd.apply(lambda r: r['YC'] / r['ValidC'] if r['ValidC'] > 0 else 0, axis=1)
    idd = idd.sort_values('Cost', ascending=False)
    return idd  # seam


def ledger_tab(led_filter='All'):  # seam
    """The dashboard's Transaction Ledger tab: every transaction with its security, newest first."""
    ltdf = get_transaction_ledger_dataframe()
    filt_ledger = ltdf if led_filter == 'All' else ltdf[ltdf['account'] == led_filter]
    return filt_ledger  # seam


# ═══════════════════════════════════════════════════════════════════════
# LEDGER & SECURITIES PAGES (2.8.0 page_view_transactions / page_securities_master)
# ═══════════════════════════════════════════════════════════════════════

def ledger_page(filter_acct='All', filter_type='All', filter_search=''):  # seam
    """The Transaction Ledger page's query: account / type / issuer-search filters, newest first.
    Raw rows (``trade_date`` as stored); the page formats them."""
    query = (
        "SELECT t.trade_date, s.issuer, s.isin, t.account, t.transaction_type, "
        "t.units, t.price, t.amount, t.notes "
        "FROM transactions t JOIN securities s ON t.bond_id=s.bond_id WHERE 1=1"
    )
    params = []
    if filter_acct != 'All':
        query += " AND t.account=?"
        params.append(filter_acct)
    if filter_type != 'All':
        query += " AND t.transaction_type=?"
        params.append(filter_type)
    if filter_search:
        query += " AND s.issuer LIKE ?"
        params.append(f"%{filter_search}%")
    query += " ORDER BY t.trade_date DESC"

    ledger = db_query(query, tuple(params))
    return ledger  # seam


def securities_master(sm_type='All', sm_rating='All', sm_search=''):  # seam
    """The securities registry joined with its metadata, by issuer, under the page's filters; ``days``
    is days to maturity (floored at 0, as displayed). Empty frame when nothing is registered."""
    secs = db_query(
        "SELECT s.*, m.bond_type, m.credit_rating, m.sector, m.listing "
        "FROM securities s LEFT JOIN security_metadata m ON s.bond_id=m.bond_id "
        "ORDER BY s.issuer"
    )
    if secs.empty:  # seam
        return secs  # seam
    filtered_secs = secs.copy()
    if sm_type != 'All':
        filtered_secs = filtered_secs[filtered_secs['bond_type'] == sm_type]
    if sm_rating != 'All':
        filtered_secs = filtered_secs[filtered_secs['credit_rating'] == sm_rating]
    if sm_search:
        filtered_secs = filtered_secs[filtered_secs['issuer'].str.contains(sm_search, case=False, na=False)]
    filtered_secs['days'] = [calc_days_to_maturity(m) for m in filtered_secs['maturity_date']]  # seam
    return filtered_secs  # seam


# ═══════════════════════════════════════════════════════════════════════
# ANALYTICS SLICES — new in 3.0: windows, top-N and the concentration lines over the aggregates
# above. Slicing and classification only; every amount is one the lifted functions computed.
# ═══════════════════════════════════════════════════════════════════════

#: The Cashflows page's FORWARD windows, in calendar months. A window of n months is this month and
#: the n − 1 that follow (3M on 10 Nov = Nov · Dec · Jan), so each bar it keeps is a whole month of
#: the projection exactly as ``cashflow_projection`` summed it. "ALL" (any other key) keeps every month.
FORWARD_WINDOW_MONTHS = {"3M": 3, "6M": 6, "1Y": 12, "2Y": 24}


def forward_window_end(tf):
    """The first calendar month AFTER forward window ``tf`` (a monthly ``pd.Period``); None = no cut."""
    n = FORWARD_WINDOW_MONTHS.get(tf)
    if n is None:
        return None
    return pd.Timestamp(date.today()).to_period("M") + n


def in_forward_window(frame, tf):
    """The rows of a projection frame — ``cdf`` or ``mcf`` from ``cashflow_projection``, both carry the
    month ``mo`` — inside forward window ``tf``, unchanged. The projection itself is untouched."""
    end = forward_window_end(tf)
    if end is None or frame is None or frame.empty:
        return frame
    return frame[frame["mo"] < end]


#: Issuer concentration lines, as a share of cost basis within the account filter: caution from 5%,
#: danger from 10%. Below the caution line an issuer is unremarkable.
CONCENTRATION_CAUTION = 0.05
CONCENTRATION_DANGER = 0.10


def concentration_tier(weight) -> str:
    """``"danger"`` at or above the danger line, ``"caution"`` at or above the caution line, else
    ``"neutral"`` (a missing weight is neutral)."""
    try:
        w = round(float(weight), 12)
    except (TypeError, ValueError):
        return "neutral"
    if w != w:
        return "neutral"
    if w >= CONCENTRATION_DANGER:
        return "danger"
    if w >= CONCENTRATION_CAUTION:
        return "caution"
    return "neutral"


def top_issuers(ir, n: int = 15):
    """The ``n`` heaviest rows of an ``issuer_concentration`` frame (it is already heaviest first)."""
    return ir.head(n)


def top_share(ir, n: int = 5) -> float:
    """The combined share of cost of the ``n`` heaviest issuers: their ``Wt``, added."""
    if ir is None or ir.empty:
        return 0.0
    return float(ir["Wt"].head(n).sum())


def next_maturities(df) -> pd.DataFrame:
    """The live positions that mature next — the maturity ladder's own rows (``maturity_ladder`` /
    ``maturity_rows``) outside the Matured bucket, on the soonest maturity date. Empty when nothing
    is left to mature."""
    mat_df, _ = maturity_ladder(df)
    rows = maturity_rows(mat_df)
    live = rows[rows["mb"] != "Matured"]
    if live.empty:
        return live
    when = pd.to_datetime(live["maturity_date"])
    return live[when == when.min()]


# ═══════════════════════════════════════════════════════════════════════
# SHELL DATA — new in 3.0 (presentation of the numbers above; no new maths)
# ═══════════════════════════════════════════════════════════════════════

def is_empty_book(df) -> bool:
    """True when the ledger holds no live position (cold start)."""
    return df is None or df.empty


def allocation_by_bucket(df) -> pd.DataFrame:
    """Cost basis by account × maturity bucket (accounts as rows, buckets as ladder-ordered columns) —
    the maturity ladder's own bucket tags, summed per account."""
    mat_df, _ = maturity_ladder(df)
    pv = mat_df.pivot_table(index="account", columns="mb", values="cost_basis", aggfunc="sum", fill_value=0.0)
    cols = [b for b in MATURITY_BUCKET_ORDER if b in pv.columns]
    pv = pv[cols]
    return pv.loc[pv.sum(axis=1).sort_values(ascending=False).index]


def matured_mask(df) -> pd.Series:
    """Positions past maturity that still carry face outstanding — the ladder's own ``matured`` test
    (maturity strictly before today) on a live position."""
    today_ts = pd.Timestamp(date.today())
    return (pd.to_datetime(df["maturity_date"]) < today_ts) & (df["position_face_value"] > 0)


def maturing_soon(df, days: int = 30) -> pd.DataFrame:
    """Live positions maturing within ``days`` (not yet matured), soonest first."""
    m = matured_mask(df)
    soon = df[~m & (pd.to_datetime(df["maturity_date"]) >= pd.Timestamp(date.today()))
              & (df["days_to_maturity"] <= days)]
    return soon.sort_values("days_to_maturity")


def tape_items(df, limit: int = 18) -> list[dict]:
    """The next projected cashflows for the running tape, nearest first: one item per (date, issuer,
    leg) — coupon legs ``CPN``, principal legs ``PRIN`` — summed across the accounts that hold it.
    Read from the same projection the Cashflows page draws (``cashflow_projection``)."""
    if is_empty_book(df):
        return []
    cdf, _, _ = cashflow_projection(df)
    if cdf.empty:
        return []
    g = cdf.groupby(["date", "issuer"], sort=True).agg(coupon=("coupon", "sum"), principal=("principal", "sum"))
    out: list[dict] = []
    for (d, issuer), r in g.iterrows():
        for leg, amt in (("CPN", r["coupon"]), ("PRIN", r["principal"])):
            if amt > 0:
                out.append({"date": pd.Timestamp(d).strftime("%d %b").upper(), "issuer": str(issuer).upper(),
                            "amount": fmt_inr(amt).replace(".00", ""), "leg": leg, "iso": pd.Timestamp(d).date()})
        if len(out) >= limit:
            break
    return out[:limit]


def command_bar(df, totals: dict) -> dict:
    """Everything the command bar prints, computed once: the book's value (cost basis), its yield,
    duration, position count, as-of date and the maturity chip."""
    today = date.today()
    asof = today.strftime("%d %b %Y")
    if is_empty_book(df):
        return {"value": "—", "yield": "—", "duration": "—", "positions": "0", "as_of": asof,
                "chip": ("NO POSITIONS", "neutral"), "matured": 0}
    wytc = totals.get("Weighted YTC", 0) or 0
    mac = totals.get("Weighted Mac Duration", 0) or 0
    n_matured = int(matured_mask(df).sum())
    return {
        "value": fmt_inr_short(totals["Total Cost Basis"]),
        "yield": fmt_pct(wytc) if wytc > 0 else "—",
        "duration": f"{mac:.2f}Y" if mac > 0 else "—",
        "positions": str(int(totals["Num Positions"])),
        "as_of": asof,
        "chip": ("CURRENT", "success") if n_matured == 0 else (f"{n_matured} MATURED", "warning"),
        "matured": n_matured,
    }


def book_notices(df) -> list[dict]:
    """The book's standing notices: matured positions still carrying face (warning) and positions
    maturing within 30 days (info). Each names the positions and the fix."""
    if is_empty_book(df):
        return []
    notices: list[dict] = []
    m = df[matured_mask(df)].sort_values("maturity_date")
    if not m.empty:
        names = "; ".join(f"{r['issuer']} ({r['account']}, {pd.to_datetime(r['maturity_date']):%d %b %Y})"
                          for _, r in m.iterrows())
        n = len(m)
        notices.append({
            "kind": "warning", "title": "Matured, not redeemed",
            "body": (f"{n} position{'s' if n != 1 else ''} past maturity still carr{'y' if n != 1 else 'ies'} "
                     f"{fmt_inr(m['position_face_value'].sum())} of face: {names}. Record the principal "
                     f"repayment under Operations → Record Transaction to retire it."),
        })
    s = maturing_soon(df)
    if not s.empty:
        names = "; ".join(f"{r['issuer']} ({r['account']}, {pd.to_datetime(r['maturity_date']):%d %b %Y})"
                          for _, r in s.iterrows())
        n = len(s)
        notices.append({
            "kind": "info", "title": "Maturing within 30 days",
            "body": f"{n} position{'s' if n != 1 else ''} · {fmt_inr(s['position_face_value'].sum())} of face: "
                    f"{names}.",
        })
    return notices


def rail_counts() -> list[tuple[str, str, str]]:
    """The rail's Book readout rows: securities, transactions, accounts, last entry, database, version."""
    secs = db_query("SELECT COUNT(*) AS c FROM securities")
    txns = db_query("SELECT COUNT(*) AS c, MAX(trade_date) AS last FROM transactions")
    n_sec = int(secs["c"].iloc[0]) if not secs.empty else 0
    n_txn = int(txns["c"].iloc[0]) if not txns.empty else 0
    last = txns["last"].iloc[0] if not txns.empty else None
    last_s = pd.to_datetime(last).strftime("%d %b %Y") if last is not None and pd.notna(last) else "—"
    return [
        ("Securities", f"{n_sec:,}", ""),
        ("Transactions", f"{n_txn:,}", ""),
        ("Accounts", str(len(ACCOUNTS)), ""),
        ("Last entry", last_s, ""),
        ("Database", "SQLite (WAL)", ""),
        ("Version", f"{PRODUCT_NAME} {VERSION}", "accent"),
    ]
