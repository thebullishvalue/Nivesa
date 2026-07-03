# -*- coding: utf-8 -*-
"""
NIVESA (निवेसा) — Bond Portfolio Ledger | A Hemrek Capital Product
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Institutional-grade fixed income portfolio management.
Full position lifecycle, cashflow analytics & risk metrics.

Usage:
    streamlit run nivesa.py

Repository:
    https://github.com/hemrek-capital/nivesa
"""

import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import sqlite3
import uuid
import logging
import os
import io

# ═══════════════════════════════════════════════════════════════════════
# APPLICATION CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

VERSION = "2.3.0"
BUILD = "2026.03.DATA_INTEGRITY"
PRODUCT_NAME = "Nivesa"
PRODUCT_DEVANAGARI = "निवेसा"
COMPANY = "Hemrek Capital"
TAGLINE = "Institutional Fixed Income Management · Portfolio Analytics · Cashflow Intelligence"

ACCOUNTS = ["REKHA", "HEMANG", "MANTHAN", "HIMA"]
FREQUENCIES = ["Monthly", "Quarterly", "Semi-Annual", "Annual"]
FREQ_MAP = {'Monthly': 12, 'Quarterly': 4, 'Semi-Annual': 2, 'Annual': 1}
BOND_TYPES = [
    "NCD", "Corporate Bond", "Government Bond", "SDL",
    "T-Bill", "Tax-Free Bond", "Sovereign Gold Bond", "FD", "Other"
]
CREDIT_RATINGS = [
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
    "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B", "C", "D", "Unrated"
]
DAY_COUNT_CONVENTIONS = ["30/360", "Actual/365", "Actual/360", "Actual/Actual"]
TRANSACTION_TYPES = ["Buy", "Sell", "Interest_Receipt", "Principal_Repayment"]

# ═══════════════════════════════════════════════════════════════════════
# PAGE CONFIG & DATA PATHS
# ═══════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title=f"{PRODUCT_NAME} | Bond Portfolio Ledger",
    layout="wide",
    page_icon="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0iI0Q0QTg1MyIgc3Ryb2tlLXdpZHRoPSIyIi8+PHBhdGggZD0iTTggMTRsMy01IDIgMyAzLTQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iI0Q0QTg1MyIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz48L3N2Zz4=",
    initial_sidebar_state="collapsed"
)

DATA_DIR = os.environ.get("NIVESA_DATA_DIR", "data")
LOG_DIR = os.path.join(DATA_DIR, "logs")
DB_DIR = os.path.join(DATA_DIR, "db")
DB_FILE = os.path.join(DB_DIR, "portfolio.db")
LOG_FILE = os.path.join(LOG_DIR, "nivesa.log")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(PRODUCT_NAME)


# ═══════════════════════════════════════════════════════════════════════
# HEMREK CAPITAL DESIGN SYSTEM — Swing-family CSS
# ═══════════════════════════════════════════════════════════════════════

def load_css():
    """Load the Obsidian Quant Terminal CSS into the Streamlit app."""
    css_path = os.path.join(os.path.dirname(__file__), "theme.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
    else:
        css = "/* theme.css not found */"
    try:
        _stamp = int(os.path.getmtime(css_path))
    except Exception:
        _stamp = 0
    st.markdown(f"<style data-css-v='{_stamp}'>\n/* v{_stamp} */\n{css}</style>", unsafe_allow_html=True)
load_css()


# ═══════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════

def db_init():
    """Initialize / migrate database to current schema."""
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute("PRAGMA journal_mode=WAL")

            c.execute("""
            CREATE TABLE IF NOT EXISTS securities (
                bond_id TEXT PRIMARY KEY,
                issuer TEXT NOT NULL,
                isin TEXT NOT NULL UNIQUE,
                maturity_date TEXT NOT NULL,
                frequency TEXT NOT NULL,
                coupon_rate REAL NOT NULL,
                face_value REAL NOT NULL
            )""")

            c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id TEXT PRIMARY KEY,
                bond_id TEXT NOT NULL,
                account TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                units REAL NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                notes TEXT,
                FOREIGN KEY (bond_id) REFERENCES securities (bond_id)
            )""")

            c.execute("""
            CREATE TABLE IF NOT EXISTS security_metadata (
                bond_id TEXT PRIMARY KEY,
                bond_type TEXT DEFAULT 'NCD',
                credit_rating TEXT DEFAULT 'Unrated',
                day_count TEXT DEFAULT 'Actual/365',
                issue_date TEXT,
                call_date TEXT,
                put_date TEXT,
                listing TEXT DEFAULT 'Unlisted',
                sector TEXT DEFAULT 'Financials',
                notes TEXT,
                FOREIGN KEY (bond_id) REFERENCES securities (bond_id)
            )""")

            # Auto-populate metadata for any securities missing it
            c.execute("""
                INSERT OR IGNORE INTO security_metadata (bond_id)
                SELECT bond_id FROM securities
                WHERE bond_id NOT IN (SELECT bond_id FROM security_metadata)
            """)

            conn.commit()
            logger.info("Database initialized / migrated OK.")
    except sqlite3.Error as e:
        st.error(f"Database initialization failed: {e}")
        logger.error(f"DB init failed: {e}")
        st.stop()


def _connect():
    """Create a connection with WAL mode and foreign key enforcement."""
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def db_query(query, params=()):
    """Run SELECT; return DataFrame."""
    try:
        with _connect() as conn:
            return pd.read_sql_query(query, conn, params=params)
    except sqlite3.Error as e:
        st.error(f"Query failed: {e}")
        logger.error(f"Query failed: {e}")
        return pd.DataFrame()


def db_execute(query, params=()):
    """Run INSERT/UPDATE/DELETE; return success bool."""
    try:
        with _connect() as conn:
            conn.cursor().execute(query, params)
            conn.commit()
            return True
    except sqlite3.Error as e:
        st.error(f"Execution failed: {e}")
        logger.error(f"Execution failed: {e}")
        return False


def ensure_metadata(bond_id):
    """Guarantee a metadata row exists for a security."""
    db_execute("INSERT OR IGNORE INTO security_metadata (bond_id) VALUES (?)", (bond_id,))


def set_notification(message, type="success"):
    """Store notification in session state to persist across rerun."""
    if "notifications" not in st.session_state:
        st.session_state["notifications"] = []
    st.session_state["notifications"].append({"message": message, "type": type})


def show_notifications():
    """Render and clear stored notifications."""
    if "notifications" in st.session_state and st.session_state["notifications"]:
        for n in st.session_state["notifications"]:
            if n["type"] == "success":
                st.toast(n["message"])
            elif n["type"] == "error":
                st.error(n["message"])
            elif n["type"] == "warning":
                st.warning(n["message"])
        st.session_state["notifications"] = []


def validate_ledger_chronology(bond_id, conn):
    """Ensure running balance of units for all accounts never drops below 0."""
    c = conn.cursor()
    c.execute(
        "SELECT account, trade_date, units, transaction_type FROM transactions "
        "WHERE bond_id=? AND transaction_type IN ('Buy', 'Sell') "
        "ORDER BY trade_date, transaction_id",
        (bond_id,)
    )
    txns = c.fetchall()
    
    balances = {}
    for account, tdate, units, ttype in txns:
        balances[account] = balances.get(account, 0.0) + units
        if balances[account] < -1e-5:
            return False, account, tdate
            
    return True, None, None


# ═══════════════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ═══════════════════════════════════════════════════════════════════════

def fmt_inr(amount):
    """Indian numbering: ₹1,23,456.78"""
    try:
        amount = float(amount)
        neg = amount < 0
        amount = abs(amount)
        parts = f"{amount:,.2f}".split('.')
        digits = parts[0].replace(',', '')
        dec = parts[1]
        if len(digits) <= 3:
            fmt = digits
        else:
            fmt = digits[-3:]
            rem = digits[:-3]
            while rem:
                fmt = rem[-2:] + ',' + fmt
                rem = rem[:-2]
        return f"{'-₹' if neg else '₹'}{fmt}.{dec}"
    except (ValueError, TypeError):
        return "₹0.00"


def fmt_inr_short(amount):
    """Compact: ₹1.23 Cr, ₹4.56 L"""
    try:
        v = float(amount)
        if abs(v) >= 1e7:   return f"₹{v/1e7:.2f} Cr"
        if abs(v) >= 1e5:   return f"₹{v/1e5:.2f} L"
        return fmt_inr(v)
    except (ValueError, TypeError):
        return "₹0"


def fmt_pct(value, decimals=2):
    try:
        return f"{float(value)*100:.{decimals}f}%"
    except (ValueError, TypeError):
        return "0.00%"


def rating_badge(rating):
    r = rating or "Unrated"
    if r == "Unrated":     cls = "badge-unrated"
    elif r.startswith("AAA"): cls = "badge-aaa"
    elif r.startswith("AA"):  cls = "badge-aa"
    elif r.startswith("A"):   cls = "badge-a"
    elif r.startswith("BBB"): cls = "badge-bbb"
    else:                     cls = "badge-below"
    return f'<span class="badge {cls}">{r}</span>'


# ═══════════════════════════════════════════════════════════════════════
# FINANCIAL CALCULATIONS ENGINE
# ═══════════════════════════════════════════════════════════════════════

def day_count_fraction(start_date, end_date, convention="Actual/365"):
    try:
        sd = pd.to_datetime(start_date).date()
        ed = pd.to_datetime(end_date).date()
        if convention == "30/360":
            d1 = min(sd.day, 30)
            d2 = min(ed.day, 30) if d1 == 30 else ed.day
            days = 360 * (ed.year - sd.year) + 30 * (ed.month - sd.month) + (d2 - d1)
            return max(0, days / 360.0)
        elif convention == "Actual/360":
            return max(0, (ed - sd).days / 360.0)
        elif convention == "Actual/Actual":
            # Simplified Actual/Actual (assumes 365.25 for simplicity, full ISDA is more complex)
            days = (ed - sd).days
            return max(0, days / 365.25)
        else: # Actual/365
            return max(0, (ed - sd).days / 365.0)
    except (ValueError, TypeError):
        return 0.0


def calc_coupon_payment(face_value, coupon_rate, frequency):
    return face_value * coupon_rate / FREQ_MAP.get(frequency, 1)


def calc_accrued_interest(face_value, coupon_rate, frequency, day_count="Actual/365", last_coupon_date=None, maturity_date=None):
    try:
        today = date.today()
        if maturity_date is not None:
            mat = pd.to_datetime(maturity_date).date()
            if mat <= today:
                return 0.0
        
        if last_coupon_date is None:
            freq = FREQ_MAP.get(frequency, 1)
            days = ((365.25 / freq) / 2)
            return face_value * coupon_rate / 365.25 * days
        
        frac = day_count_fraction(last_coupon_date, today, day_count)
        return face_value * coupon_rate * frac
    except (ValueError, TypeError):
        return 0.0


def calc_macaulay_duration(fv, coupon_rate, frequency, maturity_str, ytm, day_count="Actual/365"):
    try:
        mat_date = pd.to_datetime(maturity_str).date()
        today = date.today()
        if mat_date <= today or ytm <= 0: return 0.0
        
        schedule = generate_cashflow_schedule(fv, coupon_rate, frequency, maturity_str)
        if not schedule: return 0.0
        
        freq = FREQ_MAP.get(frequency, 1)
        pv_w = pv_s = 0.0
        for cf in schedule:
            t = day_count_fraction(today, cf['date'], day_count)
            if t > 0:
                pv = cf['total'] / ((1 + ytm / freq) ** (freq * t))
                pv_w += t * pv
                pv_s += pv
        return pv_w / pv_s if pv_s else 0.0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0


def calc_modified_duration(mac, ytm, frequency):
    freq = FREQ_MAP.get(frequency, 1)
    return mac / (1 + ytm / freq) if ytm > 0 else mac


def calc_yield_to_cost(fv_pu, cost_pu, coupon_rate, maturity_str, frequency, day_count="Actual/365"):
    try:
        mat_date = pd.to_datetime(maturity_str).date()
        today = date.today()
        if mat_date <= today or cost_pu <= 0: return 0.0
        
        schedule = generate_cashflow_schedule(fv_pu, coupon_rate, frequency, maturity_str)
        if not schedule: return 0.0
        
        freq = FREQ_MAP.get(frequency, 1)
        cfs = []
        for cf in schedule:
            t = day_count_fraction(today, cf['date'], day_count)
            if t > 0:
                cfs.append((t, cf['total']))
        
        if not cfs: return 0.0
        
        y = 0.08
        for _ in range(100):
            npv = -cost_pu
            d_npv = 0.0
            for t, cf in cfs:
                factor = 1 + y / freq
                if factor <= 0.0001:
                    y = -freq + 0.0001 * freq
                    factor = 1 + y / freq
                term = factor ** (-freq * t)
                npv += cf * term
                d_npv += -t * cf * (factor ** (-freq * t - 1))
            
            if abs(d_npv) < 1e-12:
                break
            
            dy = npv / d_npv
            y_new = y - dy
            if abs(dy) < 1e-8:
                y = y_new
                break
            y = y_new
            
        if np.isnan(y) or np.isinf(y) or y < -1.0 or y > 5.0:
            return 0.0
        return y
    except (ValueError, TypeError, FloatingPointError):
        return 0.0


def calc_days_to_maturity(s):
    try:
        return max(0, (pd.to_datetime(s) - pd.to_datetime(date.today())).days)
    except (ValueError, TypeError):
        return 0


def generate_cashflow_schedule(fv_pu, coupon_rate, frequency, maturity_str, units=1):
    try:
        mat = pd.to_datetime(maturity_str).date()
        today = date.today()
        freq = FREQ_MAP.get(frequency, 1)
        months = 12 // freq
        cpn = fv_pu * coupon_rate / freq * units
        dates = []
        d = mat
        while d > today:
            dates.append(d)
            d -= relativedelta(months=months)
        dates.sort()
        cfs = []
        for d in dates:
            prin = fv_pu * units if d == mat else 0
            cfs.append({'date': d, 'coupon': cpn, 'principal': prin, 'total': cpn + prin,
                        'type': 'Maturity + Coupon' if d == mat else 'Coupon'})
        return cfs
    except (ValueError, TypeError):
        return []


# ═══════════════════════════════════════════════════════════════════════
# POSITIONS ENGINE
# ═══════════════════════════════════════════════════════════════════════

def get_positions_dataframe():
    secs = db_query("SELECT * FROM securities")
    if secs.empty: return pd.DataFrame(), {}
    secs['maturity_date'] = pd.to_datetime(secs['maturity_date'])

    txns = db_query("SELECT * FROM transactions")
    if txns.empty: return pd.DataFrame(), {}
    txns['trade_date'] = pd.to_datetime(txns['trade_date'])

    meta = db_query("SELECT * FROM security_metadata")
    positions = []

    for (bid, acct), grp in txns.groupby(['bond_id', 'account']):
        si = secs[secs['bond_id'] == bid]
        if si.empty: continue
        si = si.iloc[0]
        mi = meta[meta['bond_id'] == bid].iloc[0] if not meta.empty and bid in meta['bond_id'].values else None

        buys  = grp[grp['transaction_type'] == 'Buy']
        sells = grp[grp['transaction_type'] == 'Sell']
        buy_u = buys['units'].sum();      buy_c = buys['amount'].sum()
        sell_u = sells['units'].sum()*-1; sell_p = sells['amount'].sum()
        cur_u  = buy_u - sell_u
        if cur_u <= 0: continue

        avg_px   = buy_c / buy_u if buy_u > 0 else 0
        r_pnl    = sell_p - sell_u * avg_px
        int_recv = grp[grp['transaction_type'] == 'Interest_Receipt']['amount'].sum()
        prin_rep = grp[grp['transaction_type'] == 'Principal_Repayment']['amount'].sum()
        cost     = cur_u * avg_px - prin_rep
        
        # Calculate dynamic face value: original face value * units - principal repaid
        face     = cur_u * si['face_value'] - prin_rep
        ppy      = FREQ_MAP.get(si['frequency'], 1)
        cost_pu  = cost / cur_u if cur_u else 0
        fv_pu    = face / cur_u if cur_u else 0
        
        day_count = mi['day_count'] if mi is not None and pd.notna(mi['day_count']) else 'Actual/365'

        ytc = calc_yield_to_cost(fv_pu, cost_pu, si['coupon_rate'], si['maturity_date'], si['frequency'], day_count)
        if ytc > 0:
            mac = calc_macaulay_duration(fv_pu, si['coupon_rate'], si['frequency'], si['maturity_date'], ytc, day_count)
            mod = calc_modified_duration(mac, ytc, si['frequency'])
        else:
            mac = 0.0
            mod = 0.0
            
        dtm = calc_days_to_maturity(si['maturity_date'])
        ann_cpn = cur_u * fv_pu * si['coupon_rate']
        
        # Compute real last coupon date
        mat_date = pd.to_datetime(si['maturity_date']).date()
        today = date.today()
        freq = FREQ_MAP.get(si['frequency'], 1)
        months = 12 // freq
        last_coupon = mat_date
        while last_coupon > today:
            last_coupon -= relativedelta(months=months)
        
        # Cap last coupon at issue_date if available
        issue_date = pd.to_datetime(mi['issue_date']).date() if mi is not None and pd.notna(mi['issue_date']) else None
        if issue_date is not None:
            last_coupon = max(last_coupon, issue_date)
        
        # Set accrued interest to 0 if matured
        if mat_date <= today:
            acc_int = 0.0
        else:
            acc_int = calc_accrued_interest(fv_pu, si['coupon_rate'], si['frequency'], day_count, last_coupon, mat_date) * cur_u
            
        first_buy = buys['trade_date'].min()
        hold_days = (pd.to_datetime(date.today()) - first_buy).days if pd.notna(first_buy) else 0

        positions.append({
            'bond_id': bid, 'account': acct,
            'issuer': si['issuer'], 'isin': si['isin'],
            'maturity_date': si['maturity_date'],
            'coupon_rate': si['coupon_rate'], 'frequency': si['frequency'],
            'current_units': cur_u, 'cost_basis': cost, 'avg_buy_price': avg_px,
            'realized_pnl': r_pnl, 'interest_received': int_recv,
            'principal_repaid': prin_rep, 'position_face_value': face,
            'annual_coupon_income': ann_cpn, 'nominal_yield': si['coupon_rate'],
            'yield_to_cost': ytc, 'macaulay_duration': mac,
            'modified_duration': mod, 'days_to_maturity': dtm,
            'years_to_maturity': dtm / 365.25, 'accrued_interest': acc_int,
            'holding_days': hold_days,
            'bond_type':      mi['bond_type']      if mi is not None else 'NCD',
            'credit_rating':  mi['credit_rating']  if mi is not None else 'Unrated',
            'sector':         mi['sector']          if mi is not None else 'Financials',
        })

    if not positions: return pd.DataFrame(), {}
    df = pd.DataFrame(positions)
    
    # Weight portfolio averages by outstanding face value rather than cost_basis
    tf = df['position_face_value'].sum()
    tc = df['cost_basis'].sum()

    if tf > 0:
        df['weight'] = df['position_face_value'] / tf
        w = lambda col: (df[col] * df['weight']).sum()
    else:
        df['weight'] = 0
        w = lambda col: 0.0

    totals = {
        'Total Cost Basis':       tc,
        'Total Face Value':       tf,
        'Total Annual Coupon':    df['annual_coupon_income'].sum(),
        'Total Accrued Interest': df['accrued_interest'].sum(),
        'Total Interest Received':df['interest_received'].sum(),
        'Total Principal Repaid': df['principal_repaid'].sum(),
        'Total Realized PnL':    df['realized_pnl'].sum(),
        'Num Positions':          len(df),
        'Num Issuers':            df['issuer'].nunique(),
        'Num Accounts':           df['account'].nunique(),
        'Weighted Nominal Yield': w('nominal_yield'),
        'Weighted YTC':           w('yield_to_cost'),
        'Weighted Mac Duration':  w('macaulay_duration'),
        'Weighted Mod Duration':  w('modified_duration'),
        'Weighted Avg Maturity':  w('years_to_maturity'),
    }
    return df, totals


def get_transaction_ledger_dataframe():
    """Fetch all transactions joined with security master data."""
    query = """
    SELECT
        t.trade_date,
        s.issuer,
        s.isin,
        t.account,
        t.transaction_type,
        t.units,
        t.price,
        t.amount,
        t.notes
    FROM transactions t
    JOIN securities s ON t.bond_id = s.bond_id
    ORDER BY t.trade_date DESC
    """
    df = db_query(query)
    if not df.empty:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
    return df


# ═══════════════════════════════════════════════════════════════════════
# CHART CONFIG
# ═══════════════════════════════════════════════════════════════════════

# Note: 'margin' removed from CL to avoid keyword duplication errors
CL = dict(
    template='plotly_dark',
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    font=dict(color="#EAEAEA", family="Inter")
)


# ═══════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

def _maturity_bucket(days):
    """Classify days-to-maturity into ladder buckets."""
    if days <= 90:   return "0-3M"
    if days <= 180:  return "3-6M"
    if days <= 365:  return "6-12M"
    if days <= 730:  return "1-2Y"
    if days <= 1095: return "2-3Y"
    if days <= 1825: return "3-5Y"
    return "5Y+"


MATURITY_BUCKET_ORDER = ["0-3M", "3-6M", "6-12M", "1-2Y", "2-3Y", "3-5Y", "5Y+"]


def _render_metric(col, style, title, value, sub="", icon=""):
    """Render a single metric card into a Streamlit column like Pragyam."""
    style_class = style if style else "neutral"
    sub_html = f"<div class='sub-metric'>{sub}</div>" if sub else ""
    icon_html = f'<span class="card-icon">{get_icon(icon, size=12, stroke_width=2)}</span> ' if icon else ""
    col.markdown(
        f"<div class='metric-card {style_class}'><h4>{icon_html}{title}</h4>"
        f"<h2>{value}</h2>{sub_html}</div>",
        unsafe_allow_html=True,
    )


def _render_html_table(headers, rows_html):
    """Wrap header list and row HTML into a styled table using portfolio-table layout."""
    th = "".join(f"<th>{h}</th>" for h in headers)
    return (
        f"<div class='portfolio-table'><table>"
        f"<thead><tr>{th}</tr></thead>"
        f"<tbody>{rows_html}</tbody></table></div>"
    )


def page_dashboard():
    df, totals = get_positions_dataframe()
    if df.empty:
        st.markdown(
            "<div class='info-box'><h4>Welcome to Nivesa</h4>"
            "<p>No positions found. Add securities and record transactions to get started.</p></div>",
            unsafe_allow_html=True,
        )
        return

    # Precompute weighted-yield helper columns (used across tabs)
    df['ny_c'] = df['nominal_yield'] * df['cost_basis']
    df['ytc_c'] = df['yield_to_cost'] * df['cost_basis']

    # ── Metric Cards ──
    st.markdown('<div class="metric-cards-container">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    _render_metric(c1, "primary", "Total Invested (Cost)",
                   fmt_inr_short(totals['Total Cost Basis']),
                   f"Face Value: {fmt_inr_short(totals['Total Face Value'])}", icon="briefcase")
    
    ytc_disp = fmt_pct(totals['Weighted YTC']) if totals['Weighted YTC'] > 0 else "N/A"
    _render_metric(c2, "info", "Portfolio Yield (WA)",
                   ytc_disp,
                   f"Nominal: {fmt_pct(totals['Weighted Nominal Yield'])}", icon="trending")
    _render_metric(c3, "warning", "Annual Coupon Income",
                   fmt_inr_short(totals['Total Annual Coupon']),
                   f"Monthly: ~{fmt_inr_short(totals['Total Annual Coupon'] / 12)}", icon="activity")
    _render_metric(c4, "", "Weighted Duration",
                   f"{totals['Weighted Mac Duration']:.2f}y",
                   f"Modified: {totals['Weighted Mod Duration']:.2f}y", icon="crosshair")
    _render_metric(c5, "", "Portfolio Composition",
                   str(totals['Num Positions']),
                   f"{totals['Num Issuers']} issuers · {totals['Num Accounts']} accounts", icon="layers")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Tabs ──
    tab_alloc, tab_pos, tab_mat, tab_cf, tab_issuer, tab_ledger = st.tabs([
        "Allocation & Risk", "Positions", "Maturity Ladder",
        "Cashflow Schedule", "Issuer Detail", "Transaction Ledger",
    ])

    # ─────────────────────────────────────────────────────────────────────
    # TAB 1: Allocation & Risk (reimagined)
    # ─────────────────────────────────────────────────────────────────────
    with tab_alloc:
        sb = df[df['cost_basis'] > 0].copy()

        total_cost = totals['Total Cost Basis']

        if sb.empty:
            st.info("No positions with positive cost basis to display.")
        else:
            # Use positive-cost-basis total for accurate weight calculation
            total_cost_alloc = sb['cost_basis'].sum()

            # ── Account Capital Allocation Table ──
            _render_section_header("Capital Allocation", "Portfolio distribution by account", icon="briefcase", accent="")
            acct_agg = sb.groupby('account').agg(
                Cost=('cost_basis', 'sum'),
                Face=('position_face_value', 'sum'),
                NY=('ny_c', 'sum'),
                YC=('ytc_c', 'sum'),
                Pos=('bond_id', 'count'),
                Issuers=('issuer', 'nunique'),
                Inc=('annual_coupon_income', 'sum'),
            ).reset_index()
            acct_agg['Wt'] = acct_agg['Cost'] / total_cost_alloc if total_cost_alloc > 0 else 0
            acct_agg['NY'] = acct_agg.apply(lambda r: r['NY'] / r['Cost'] if r['Cost'] > 0 else 0, axis=1)
            acct_agg['YC'] = acct_agg.apply(lambda r: r['YC'] / r['Cost'] if r['Cost'] > 0 else 0, axis=1)
            acct_agg = acct_agg.sort_values('Cost', ascending=False)

            acct_rows = ""
            for _, r in acct_agg.iterrows():
                acct_rows += (
                    f"<tr><td><b>{r['account']}</b></td>"
                    f"<td style='text-align:right'>{fmt_inr(r['Cost'])}</td>"
                    f"<td style='text-align:right'>{fmt_inr(r['Face'])}</td>"
                    f"<td style='text-align:right'>{fmt_pct(r['Wt'])}</td>"
                    f"<td style='text-align:right'>{int(r['Pos'])}</td>"
                    f"<td style='text-align:right'>{int(r['Issuers'])}</td>"
                    f"<td style='text-align:right'>{fmt_pct(r['NY'])}</td>"
                    f"<td style='text-align:right'>{fmt_pct(r['YC'])}</td>"
                    f"<td style='text-align:right'>{fmt_inr(r['Inc'])}</td></tr>"
                )
            st.markdown(
                _render_html_table(
                    ["Account", "Cost Basis", "Face Value", "Weight", "Positions", "Issuers", "Nominal Yield", "Yield to Cost", "Annual Income"],
                    acct_rows
                ),
                unsafe_allow_html=True
            )

        # ── Concentration Risk Table ──
        _render_section_header("Concentration Risk", "Issuer-level position weighting", icon="scale", accent="warning")

        conc_filter = st.selectbox(
            "Filter by Account",
            ['All'] + sorted(df['account'].unique().tolist()),
            key="conc_acct",
        )
        conc_df = df if conc_filter == 'All' else df[df['account'] == conc_filter]
        total_cost_conc = conc_df['cost_basis'].sum()

        ir = conc_df.groupby('issuer').agg(
            Cost=('cost_basis', 'sum'),
            Face=('position_face_value', 'sum'),
            NY=('ny_c', 'sum'),
            YC=('ytc_c', 'sum'),
            Pos=('bond_id', 'count'),
        ).reset_index()
        ir['Wt'] = ir['Cost'] / total_cost_conc if total_cost_conc > 0 else 0
        ir['NY'] = ir.apply(lambda r: r['NY'] / r['Cost'] if r['Cost'] > 0 else 0, axis=1)
        ir['YC'] = ir.apply(lambda r: r['YC'] / r['Cost'] if r['Cost'] > 0 else 0, axis=1)
        ir = ir.sort_values('Cost', ascending=False)

        ir_rows = ""
        for _, r in ir.iterrows():
            ir_rows += (
                f"<tr><td><b>{r['issuer']}</b></td>"
                f"<td style='text-align:right'>{fmt_inr(r['Cost'])}</td>"
                f"<td style='text-align:right'>{fmt_inr(r['Face'])}</td>"
                f"<td style='text-align:right'>{fmt_pct(r['Wt'])}</td>"
                f"<td style='text-align:right'>{fmt_pct(r['NY'])}</td>"
                f"<td style='text-align:right'>{fmt_pct(r['YC'])}</td>"
                f"<td style='text-align:right'>{int(r['Pos'])}</td></tr>"
            )
        st.markdown(
            _render_html_table(
                ["Issuer", "Cost Basis", "Face Value", "Weight", "Nominal Yield", "Yield to Cost", "Positions"],
                ir_rows
            ),
            unsafe_allow_html=True
        )

    # ─────────────────────────────────────────────────────────────────────
    # TAB 2: Positions
    # ─────────────────────────────────────────────────────────────────────
    with tab_pos:
        acct_filter = st.selectbox(
            "Filter by Account",
            ['All'] + sorted(df['account'].unique().tolist()),
            key="pf",
        )
        filtered = df if acct_filter == 'All' else df[df['account'] == acct_filter]
        filtered = filtered.sort_values('cost_basis', ascending=False)

        rows = ""
        for _, p in filtered.iterrows():
            if p['days_to_maturity'] <= 90:
                mat_badge = '<span class="badge badge-below">&lt; 90d</span>'
            elif p['days_to_maturity'] <= 365:
                mat_badge = '<span class="badge badge-bbb">&lt; 1y</span>'
            else:
                mat_badge = ''
            mat_str = pd.to_datetime(p['maturity_date']).strftime('%d %b %Y')
            ytc_str = fmt_pct(p['yield_to_cost']) if p['yield_to_cost'] > 0 else "N/A"
            mac_str = f"{p['macaulay_duration']:.2f}y" if p['macaulay_duration'] > 0 else "N/A"
            rows += (
                f"<tr><td><div style='font-weight:600'>{p['issuer']}</div>"
                f"<div style='font-size:0.75rem;color:#888'>{p['isin']}</div></td>"
                f"<td>{rating_badge(p['credit_rating'])}</td>"
                f"<td>{p['account']}</td>"
                f"<td style='text-align:right'>{int(p['current_units'])}</td>"
                f"<td style='text-align:right'>{fmt_inr(p['cost_basis'])}</td>"
                f"<td style='text-align:right'>{fmt_inr(p['position_face_value'])}</td>"
                f"<td style='text-align:right'>{fmt_pct(p['nominal_yield'])}</td>"
                f"<td style='text-align:right'>{ytc_str}</td>"
                f"<td style='text-align:right'>{mac_str}</td>"
                f"<td style='text-align:right'>{mat_str} {mat_badge}</td>"
                f"<td style='text-align:right'>{fmt_inr(p['annual_coupon_income'])}</td></tr>"
            )
        st.markdown(
            _render_html_table(
                ["Security", "Rating", "Acct", "Units", "Cost", "Face",
                 "Coupon", "YTC", "Duration", "Maturity", "Annual Inc"],
                rows,
            ),
            unsafe_allow_html=True,
        )

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
            'nominal_yield': 'Nominal Yield', 'yield_to_cost': 'YTC (%)',
            'macaulay_duration': 'Mac Duration', 'modified_duration': 'Mod Duration',
            'maturity_date': 'Maturity Date', 'annual_coupon_income': 'Annual Income',
            'interest_received': 'Interest Received', 'days_to_maturity': 'Days Left'
        }
        exp = filtered[export_cols].copy()
        exp['maturity_date'] = pd.to_datetime(exp['maturity_date']).dt.strftime('%Y-%m-%d')
        exp = exp.rename(columns=col_map)
        st.download_button("EXPORT CSV", exp.to_csv(index=False), "nivesa_positions.csv", "text/csv")

    # ─────────────────────────────────────────────────────────────────────
    # TAB 3: Maturity Ladder
    # ─────────────────────────────────────────────────────────────────────
    with tab_mat:

        mat_filter = st.selectbox(
            "Filter by Account",
            ['All'] + sorted(df['account'].unique().tolist()),
            key="mat_acct",
        )
        mat_df = df.copy() if mat_filter == 'All' else df[df['account'] == mat_filter].copy()

        mat_df['mb'] = mat_df['days_to_maturity'].apply(_maturity_bucket)
        bucket_agg = (
            mat_df.groupby('mb')
            .agg(Cost=('cost_basis', 'sum'), Face=('position_face_value', 'sum'), N=('bond_id', 'count'))
            .reindex(MATURITY_BUCKET_ORDER)
            .fillna(0)
        )

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=bucket_agg.index, y=bucket_agg['Face'], name='Face Value',
            marker_color='#FFC300',
            text=[fmt_inr_short(v) for v in bucket_agg['Face']],
            textposition='outside', textfont=dict(size=10, color='#EAEAEA'),
        ))
        fig.add_trace(go.Bar(
            x=bucket_agg.index, y=bucket_agg['Cost'], name='Cost Basis',
            marker_color='#06b6d4',
            text=[fmt_inr_short(v) for v in bucket_agg['Cost']],
            textposition='outside', textfont=dict(size=10, color='#EAEAEA'),
        ))
        fig.update_layout(
            **CL,
            title=dict(text="Maturity Profile", font=dict(size=13, color='#888'), x=0, y=0.97, yanchor='top'),
            height=420, barmode='group',
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title=''),
            legend=dict(orientation='h', yanchor='top', y=-0.1, xanchor='left', x=0, font=dict(size=10), bgcolor='rgba(0,0,0,0)'),
            margin=dict(l=40, r=20, t=65, b=55),
        )
        st.plotly_chart(fig, use_container_width=True)

        rows = ""
        for bucket in MATURITY_BUCKET_ORDER:
            for _, p in mat_df[mat_df['mb'] == bucket].sort_values('days_to_maturity').iterrows():
                mat_str = pd.to_datetime(p['maturity_date']).strftime('%d %b %Y')
                rows += (
                    f"<tr><td>{bucket}</td>"
                    f"<td style='font-weight:600'>{p['issuer']}</td>"
                    f"<td>{p['account']}</td>"
                    f"<td style='text-align:right'>{fmt_inr(p['position_face_value'])}</td>"
                    f"<td style='text-align:right'>{fmt_pct(p['coupon_rate'])}</td>"
                    f"<td style='text-align:right'>{mat_str}</td>"
                    f"<td style='text-align:right'>{int(p['days_to_maturity'])}d</td></tr>"
                )
        if rows:
            st.markdown(
                _render_html_table(
                    ["Bucket", "Issuer", "Acct", "Face Value", "Coupon", "Maturity", "Days Left"],
                    rows,
                ),
                unsafe_allow_html=True,
            )

    # ─────────────────────────────────────────────────────────────────────
    # TAB 4: Cashflow Schedule
    # ─────────────────────────────────────────────────────────────────────
    with tab_cf:

        cf_filter = st.selectbox(
            "Filter by Account",
            ['All'] + sorted(df['account'].unique().tolist()),
            key="cf_acct",
        )
        cf_df = df if cf_filter == 'All' else df[df['account'] == cf_filter]

        # Fetch recorded cashflows to prevent double-counting
        recorded_cfs = db_query("SELECT bond_id, account, trade_date, transaction_type FROM transactions WHERE transaction_type IN ('Interest_Receipt', 'Principal_Repayment')")
        recorded_dates = set()
        if not recorded_cfs.empty:
            for _, r in recorded_cfs.iterrows():
                recorded_dates.add((r['bond_id'], r['account'], pd.to_datetime(r['trade_date']).date()))

        all_cf = []
        for _, p in cf_df.iterrows():
            fvpu = p['position_face_value'] / p['current_units'] if p['current_units'] > 0 else 0
            schedule = generate_cashflow_schedule(
                fvpu, p['coupon_rate'], p['frequency'], p['maturity_date'], p['current_units'],
            )
            for cf in schedule:
                # Skip if we already recorded a receipt for this exact date/bond/account
                if (p['bond_id'], p['account'], cf['date']) in recorded_dates:
                    continue
                
                cf['issuer'] = p['issuer']
                cf['account'] = p['account']
                all_cf.append(cf)

        if not all_cf:
            st.info("No future cashflows to project.")
        else:
            cdf = pd.DataFrame(all_cf)
            cdf['date'] = pd.to_datetime(cdf['date'])
            cdf = cdf.sort_values('date')
            cdf['mo'] = cdf['date'].dt.to_period('M')

            mcf = cdf.groupby('mo').agg(
                Coupon=('coupon', 'sum'), Principal=('principal', 'sum'),
            ).reset_index()
            mcf['ms'] = mcf['mo'].astype(str)

            fig = go.Figure()
            fig.add_trace(go.Bar(x=mcf['ms'], y=mcf['Coupon'], name='Coupon', marker_color='#FFC300'))
            fig.add_trace(go.Bar(x=mcf['ms'], y=mcf['Principal'], name='Principal', marker_color='#06b6d4'))
            fig.update_layout(
                **CL,
                title=dict(text="Projected Monthly Cashflows", font=dict(size=13, color='#888'), x=0, y=0.97, yanchor='top'),
                height=420, barmode='stack',
                xaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickangle=-45),
                yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title=''),
                legend=dict(orientation='h', yanchor='top', y=-0.18, xanchor='left', x=0, font=dict(size=10), bgcolor='rgba(0,0,0,0)'),
                margin=dict(l=40, r=20, t=65, b=70),
            )
            st.plotly_chart(fig, use_container_width=True)

            total_cpn = cdf['coupon'].sum()
            total_prin = cdf['principal'].sum()
            s1, s2, s3 = st.columns(3)
            _render_metric(s1, "", "Future Coupons", fmt_inr_short(total_cpn))
            _render_metric(s2, "", "Principal Due", fmt_inr_short(total_prin))
            _render_metric(s3, "", "Total Future CF", fmt_inr_short(total_cpn + total_prin))

            cutoff = pd.to_datetime(date.today() + timedelta(days=365))
            n12 = cdf[cdf['date'] <= cutoff]
            if not n12.empty:
                _render_section_header("Nearterm Cashflows", "Projected inflows within next 12 months", icon="activity", accent="info")
                rows = ""
                for _, cf in n12.iterrows():
                    prin_display = fmt_inr(cf['principal']) if cf['principal'] > 0 else '-'
                    rows += (
                        f"<tr><td>{cf['date'].strftime('%d %b %Y')}</td>"
                        f"<td style='font-weight:600'>{cf['issuer']}</td>"
                        f"<td>{cf['account']}</td><td>{cf['type']}</td>"
                        f"<td style='text-align:right'>{fmt_inr(cf['coupon'])}</td>"
                        f"<td style='text-align:right'>{prin_display}</td>"
                        f"<td style='text-align:right;font-weight:600'>{fmt_inr(cf['total'])}</td></tr>"
                    )
                st.markdown(
                    _render_html_table(
                        ["Date", "Issuer", "Acct", "Type", "Coupon", "Principal", "Total"],
                        rows,
                    ),
                    unsafe_allow_html=True,
                )

    # ─────────────────────────────────────────────────────────────────────
    # TAB 5: Issuer Detail
    # ─────────────────────────────────────────────────────────────────────
    with tab_issuer:

        iss_filter = st.selectbox(
            "Filter by Account",
            ['All'] + sorted(df['account'].unique().tolist()),
            key="iss_acct",
        )
        iss_df = df if iss_filter == 'All' else df[df['account'] == iss_filter]

        idd = iss_df.groupby(['issuer', 'isin']).agg(
            Cost=('cost_basis', 'sum'),
            Face=('position_face_value', 'sum'),
            NY=('ny_c', 'sum'),
            YC=('ytc_c', 'sum'),
            Units=('current_units', 'sum'),
            Inc=('annual_coupon_income', 'sum'),
        )
        total_cost_iss = iss_df['cost_basis'].sum()
        idd['Wt'] = idd['Cost'] / total_cost_iss if total_cost_iss > 0 else 0
        idd['NY'] = idd.apply(lambda r: r['NY'] / r['Cost'] if r['Cost'] > 0 else 0, axis=1)
        idd['YC'] = idd.apply(lambda r: r['YC'] / r['Cost'] if r['Cost'] > 0 else 0, axis=1)
        idd = idd.sort_values('Cost', ascending=False)

        rows = ""
        for (iss, isin), r in idd.iterrows():
            rows += (
                f"<tr><td style='font-weight:600'>{iss}</td>"
                f"<td style='font-size:0.8rem;color:#888'>{isin}</td>"
                f"<td style='text-align:right'>{int(r['Units'])}</td>"
                f"<td style='text-align:right'>{fmt_inr(r['Cost'])}</td>"
                f"<td style='text-align:right'>{fmt_inr(r['Face'])}</td>"
                f"<td style='text-align:right'>{r['Wt']:.1%}</td>"
                f"<td style='text-align:right'>{fmt_pct(r['NY'])}</td>"
                f"<td style='text-align:right'>{fmt_pct(r['YC'])}</td>"
                f"<td style='text-align:right'>{fmt_inr(r['Inc'])}</td></tr>"
            )
        st.markdown(
            _render_html_table(
                ["Issuer", "ISIN", "Units", "Cost", "Face", "Weight", "Nominal", "YTC", "Annual Inc"],
                rows,
            ),
            unsafe_allow_html=True,
        )

    # ─────────────────────────────────────────────────────────────────────
    # TAB 6: Transaction Ledger
    # ─────────────────────────────────────────────────────────────────────
    with tab_ledger:

        led_filter = st.selectbox(
            "Filter by Account",
            ['All'] + sorted(df['account'].unique().tolist()),
            key="led_acct",
        )

        ltdf = get_transaction_ledger_dataframe()
        filt_ledger = ltdf if led_filter == 'All' else ltdf[ltdf['account'] == led_filter]

        if filt_ledger.empty:
            st.info("No transactions found.")
        else:
            # Table visualization
            rows_ledger = ""
            for _, t in filt_ledger.iterrows():
                date_str = t['trade_date'].strftime('%d %b %Y')
                typ_cls = "badge-aaa" if t['transaction_type'] == 'Buy' else \
                          "badge-below" if t['transaction_type'] == 'Sell' else \
                          "badge-aa" if t['transaction_type'] == 'Interest_Receipt' else \
                          "badge-a"
                typ_badge = f'<span class="badge {typ_cls}">{t["transaction_type"]}</span>'

                rows_ledger += (
                    f"<tr><td>{date_str}</td>"
                    f"<td><div style='font-weight:600'>{t['issuer']}</div>"
                    f"<div style='font-size:0.75rem;color:#888'>{t['isin']}</div></td>"
                    f"<td>{t['account']}</td>"
                    f"<td>{typ_badge}</td>"
                    f"<td style='text-align:right'>{int(t['units']) if t['units'] % 1 == 0 else t['units']}</td>"
                    f"<td style='text-align:right'>{fmt_inr(t['price'])}</td>"
                    f"<td style='text-align:right;font-weight:600'>{fmt_inr(t['amount'])}</td>"
                    f"<td>{t['notes'] or '-'}</td></tr>"
                )

            st.markdown(
                _render_html_table(
                    ["Date", "Security", "Acct", "Type", "Units", "Principal Amount", "Total Amount", "Notes"],
                    rows_ledger,
                ),
                unsafe_allow_html=True,
            )

            # Excel Export
            buffer = io.BytesIO()
            export_df = filt_ledger.copy()
            if not export_df.empty:
                export_df['trade_date'] = pd.to_datetime(export_df['trade_date']).dt.date

            col_map_ledger = {
                'trade_date': 'Date', 'issuer': 'Security', 'isin': 'ISIN',
                'account': 'Account', 'transaction_type': 'Type',
                'units': 'Units', 'price': 'Principal Amount', 'amount': 'Total Amount', 'notes': 'Notes'
            }
            export_df = export_df.rename(columns=col_map_ledger)

            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False, sheet_name='Transaction Ledger')

            st.download_button(
                label="DOWNLOAD EXCEL",
                data=buffer.getvalue(),
                file_name=f"nivesa_ledger_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


# ═══════════════════════════════════════════════════════════════════════
# PAGE: ADD SECURITY
# ═══════════════════════════════════════════════════════════════════════

ICONS = {
    "chart":      '<svg aria-label="Chart icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    "cube":       '<svg aria-label="Cube icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
    "target":     '<svg aria-label="Target icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
    "layers":     '<svg aria-label="Layers icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>',
    "bar-chart":  '<svg aria-label="Bar chart icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
    "activity":   '<svg aria-label="Activity icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    "crosshair":  '<svg aria-label="Crosshair icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/></svg>',
    "cpu":        '<svg aria-label="CPU icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>',
    "zap":        '<svg aria-label="Zap icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
    "shield":     '<svg aria-label="Shield icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    "grid":       '<svg aria-label="Grid icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
    "database":   '<svg aria-label="Database icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
    "trending":   '<svg aria-label="Trending icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
    "eye":        '<svg aria-label="Eye icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
    "play":       '<svg aria-label="Play icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>',
    "chevron-right": '<svg aria-label="Expand icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>',
    "download":   '<svg aria-label="Download icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    "briefcase":  '<svg aria-label="Portfolio icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>',
    "compass":    '<svg aria-label="Regime icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>',
    "scale":      '<svg aria-label="Weighting icon" role="img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h18"/></svg>',
}


def get_icon(name: str, size: int = 18, stroke_width: float = 1.5) -> str:
    """Return an SVG icon string with custom size and stroke width."""
    import re
    base_svg = ICONS.get(name, ICONS["chart"])
    base_svg = re.sub(r'\s+width="[^"]*"', '', base_svg)
    base_svg = re.sub(r'\s+height="[^"]*"', '', base_svg)
    base_svg = re.sub(r'\s+stroke-width="[^"]*"', '', base_svg)
    return base_svg.replace('<svg', f'<svg width="{size}" height="{size}" stroke-width="{stroke_width}"')


def _render_section_header(title, subtitle="", icon="chart", accent=""):
    """Render a consistent premium section header like Pragyam Quant Terminal."""
    svg = get_icon(icon, size=16, stroke_width=1.8)
    icon_class = f"icon {accent}" if accent else "icon"
    hdr_class = f"section-hdr {accent}" if accent else "section-hdr"
    desc_html = f'<div class="desc">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="{hdr_class}">'
        f'<div class="{icon_class}">{svg}</div>'
        f'<div class="text">'
        f'<h3>{title}</h3>'
        f'{desc_html}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def page_add_security():
    _render_section_header("Add New Security", "Register a bond in the securities master before transacting", icon="cube", accent="cyan")

    with st.form("add_sec"):
        c1, c2 = st.columns(2)
        with c1:
            issuer = st.text_input("Issuer Name")
            isin = st.text_input("ISIN")
            mat = st.date_input("Maturity Date")
            freq = st.selectbox("Coupon Frequency", FREQUENCIES)
        with c2:
            cpn = st.number_input("Coupon Rate (%)", 0.0, 100.0, step=0.01, format="%.2f")
            fv = st.number_input("Face Value (per unit)", min_value=0.0, step=100.0, value=1000.0)
            btype = st.selectbox("Bond Type", BOND_TYPES)
            cr = st.selectbox("Credit Rating", CREDIT_RATINGS)

        c3, c4 = st.columns(2)
        with c3:
            sector = st.text_input("Sector", value="Financials")
            listing = st.selectbox("Listing", ["Unlisted", "NSE", "BSE", "Both"])
        with c4:
            idate = st.date_input("Issue Date", value=None)
            dc = st.selectbox("Day Count", DAY_COUNT_CONVENTIONS)

        notes = st.text_area("Notes")
        submitted = st.form_submit_button("ADD SECURITY")

        if submitted:
            if not issuer or not isin:
                st.error("Issuer and ISIN are required.")
            elif mat <= date.today():
                st.error("Maturity date must be in the future.")
            elif idate is not None and mat <= idate:
                st.error("Maturity date must be after the issue date.")
            elif not db_query("SELECT 1 FROM securities WHERE isin=?", (isin,)).empty:
                st.error(f"ISIN **{isin}** already exists in the securities master.")
            else:
                bid = str(uuid.uuid4())
                ok = db_execute(
                    "INSERT INTO securities VALUES (?,?,?,?,?,?,?)",
                    (bid, issuer, isin, mat.isoformat(), freq, cpn / 100, fv),
                )
                if ok:
                    db_execute(
                        "INSERT INTO security_metadata "
                        "(bond_id, bond_type, credit_rating, day_count, issue_date, listing, sector, notes) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (bid, btype, cr, dc, idate.isoformat() if idate else None, listing, sector, notes),
                    )
                    set_notification(f"Security **{issuer}** ({isin}) added!", "success")
                    logger.info(f"Added security: {isin}")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: EDIT SECURITY
# ═══════════════════════════════════════════════════════════════════════

def _safe_index(options, value, default=0):
    """Return index of value in options list, or default if not found."""
    try:
        return options.index(value)
    except (ValueError, TypeError):
        return default


def page_edit_security():
    _render_section_header("Edit Security", "Update security master data and metadata", icon="scale", accent="violet")

    secs = db_query("SELECT * FROM securities")
    if secs.empty:
        st.warning("No securities found.")
        return

    opts = {f"{r['issuer']} — {r['isin']}": r['bond_id'] for _, r in secs.iterrows()}
    sel = st.selectbox("Select Security", opts.keys(), index=None, placeholder="Choose…")
    if not sel:
        return

    bid = opts[sel]
    sec = secs[secs['bond_id'] == bid].iloc[0]
    ensure_metadata(bid)

    meta_df = db_query("SELECT * FROM security_metadata WHERE bond_id=?", (bid,))
    meta = meta_df.iloc[0] if not meta_df.empty else None

    txn_count = db_query("SELECT COUNT(*) as c FROM transactions WHERE bond_id=?", (bid,))['c'].iloc[0]

    # Reactive holdings context panel
    holdings = db_query(
        "SELECT account, SUM(units) as units, SUM(amount) as cost "
        "FROM transactions WHERE bond_id=? AND transaction_type IN ('Buy', 'Sell') GROUP BY account HAVING SUM(units) > 0",
        (bid,),
    )
    dtm = calc_days_to_maturity(sec['maturity_date'])
    mat_str = pd.to_datetime(sec['maturity_date']).strftime('%d %b %Y')
    holders = " · ".join(
        f"{r['account']}: {int(r['units'])} units ({fmt_inr(r['cost'])})"
        for _, r in holdings.iterrows()
    ) if not holdings.empty else "No holdings"
    st.markdown(
        f"<div class='info-box'><p style='font-size:0.8rem;margin:0;color:var(--text-muted);line-height:1.8;'>"
        f"Coupon: <strong>{fmt_pct(sec['coupon_rate'])}</strong> · "
        f"Face: <strong>{fmt_inr(sec['face_value'])}</strong> · "
        f"Maturity: <strong>{mat_str}</strong> ({dtm}d) · "
        f"Transactions: <strong>{txn_count}</strong><br>"
        f"Holdings: {holders}</p></div>",
        unsafe_allow_html=True,
    )

    listing_opts = ["Unlisted", "NSE", "BSE", "Both"]

    with st.form("edit_sec"):
        st.markdown(f"**Editing: {sec['issuer']} ({sec['isin']})**")
        st.text_input("ISIN", value=sec['isin'], disabled=True)

        c1, c2 = st.columns(2)
        with c1:
            issuer = st.text_input("Issuer", value=sec['issuer'])
            mat = st.date_input("Maturity", value=pd.to_datetime(sec['maturity_date']).date())
            freq = st.selectbox("Frequency", FREQUENCIES, index=FREQUENCIES.index(sec['frequency']))
        with c2:
            cpn = st.number_input("Coupon (%)", 0.0, 100.0, step=0.01, format="%.2f", value=sec['coupon_rate'] * 100)
            fv = st.number_input("Face Value", step=100.0, value=sec['face_value'])
            btype = st.selectbox(
                "Bond Type", BOND_TYPES,
                index=_safe_index(BOND_TYPES, meta['bond_type'] if meta is not None else None),
            )

        c3, c4 = st.columns(2)
        with c3:
            cr = st.selectbox(
                "Credit Rating", CREDIT_RATINGS,
                index=_safe_index(CREDIT_RATINGS, meta['credit_rating'] if meta is not None else None, len(CREDIT_RATINGS) - 1),
            )
            sector = st.text_input("Sector", value=meta['sector'] if meta is not None else 'Financials')
        with c4:
            listing = st.selectbox(
                "Listing", listing_opts,
                index=_safe_index(listing_opts, meta['listing'] if meta is not None else None),
            )
            meta_idate = pd.to_datetime(meta['issue_date']).date() if meta is not None and pd.notna(meta['issue_date']) else None
            idate = st.date_input("Issue Date", value=meta_idate)
            dc = st.selectbox(
                "Day Count", DAY_COUNT_CONVENTIONS,
                index=_safe_index(DAY_COUNT_CONVENTIONS, meta['day_count'] if meta is not None else None),
            )

        notes = st.text_area("Notes", value=meta['notes'] if meta is not None else '')

        if txn_count > 0:
            st.warning(f"{txn_count} transactions exist. Editing face value changes all calculations retroactively.")

        if st.form_submit_button("UPDATE SECURITY"):
            if not issuer:
                st.error("Issuer required.")
            elif idate is not None and mat <= idate:
                st.error("Maturity date must be after the issue date.")
            else:
                db_execute(
                    "UPDATE securities SET issuer=?, maturity_date=?, frequency=?, coupon_rate=?, face_value=? WHERE bond_id=?",
                    (issuer, mat.isoformat(), freq, cpn / 100, fv, bid),
                )
                db_execute(
                    "UPDATE security_metadata SET bond_type=?, credit_rating=?, day_count=?, issue_date=?, listing=?, sector=?, notes=? WHERE bond_id=?",
                    (btype, cr, dc, idate.isoformat() if idate else None, listing, sector, notes, bid),
                )
                set_notification(f"**{issuer}** updated!", "success")
                logger.info(f"Updated security: {bid}")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: RECORD TRANSACTION
# ═══════════════════════════════════════════════════════════════════════

def page_record_transaction(show_header=True):
    if show_header:
        _render_section_header("Record Transaction", "Record a Buy, Sell, Interest Receipt, or Principal Repayment", icon="zap", accent="emerald")

    secs = db_query("SELECT bond_id, issuer, isin FROM securities")
    if secs.empty:
        st.warning("No securities found.")
        return

    opts = {f"{r['issuer']} — {r['isin']}": r['bond_id'] for _, r in secs.iterrows()}
    sel = st.selectbox("Select Security", opts.keys(), index=None, placeholder="Choose…")
    if not sel:
        return

    bid = opts[sel]

    # Show selected security context (reactive to dropdown change)
    sec_info = db_query(
        "SELECT s.coupon_rate, s.face_value, s.frequency, s.maturity_date, "
        "COALESCE(m.credit_rating, 'Unrated') as credit_rating, m.issue_date "
        "FROM securities s LEFT JOIN security_metadata m ON s.bond_id=m.bond_id "
        "WHERE s.bond_id=?", (bid,),
    )
    if not sec_info.empty:
        si = sec_info.iloc[0]
        dtm = calc_days_to_maturity(si['maturity_date'])
        mat_str = pd.to_datetime(si['maturity_date']).strftime('%d %b %Y')
        st.markdown(
            f"<div class='info-box'><p style='font-size:0.8rem;margin:0;color:var(--text-muted);line-height:1.8;'>"
            f"Coupon: <strong>{fmt_pct(si['coupon_rate'])}</strong> · "
            f"Face: <strong>{fmt_inr(si['face_value'])}</strong> · "
            f"Freq: <strong>{si['frequency']}</strong> · "
            f"Maturity: <strong>{mat_str}</strong> ({dtm}d) · "
            f"Rating: {rating_badge(si['credit_rating'])}</p></div>",
            unsafe_allow_html=True,
        )

    # Account and date outside the form so changes trigger immediate rerun
    sel_c1, sel_c2, sel_c3 = st.columns(3)
    with sel_c1:
        ttype = st.selectbox("Transaction Type", TRANSACTION_TYPES)
    with sel_c2:
        account = st.selectbox("Account", ACCOUNTS, key="rec_acct")
    with sel_c3:
        tdate = st.date_input("Date", max_value=date.today(), key="rec_date")

    # For principal repayment, show live units context (reactive to account change)
    units_by_account = pd.Series(dtype='float64')
    total_units_all = 0.0
    if ttype == 'Principal_Repayment':
        acct_txns = db_query("SELECT account, units FROM transactions WHERE bond_id=?", (bid,))
        if not acct_txns.empty:
            units_by_account = acct_txns.groupby('account')['units'].sum()
            total_units_all = acct_txns['units'].sum()
        current_units = units_by_account.get(account, 0.0)
        st.markdown(
            f"**{account}**: {current_units:.0f} units · "
            f"**All accounts**: {total_units_all:.0f} units total"
        )

    with st.form("rec_txn"):
        if ttype in ["Buy", "Sell"]:
            c1, c2 = st.columns(2)
            with c1:
                units = st.number_input("Units", min_value=1, step=1)
            with c2:
                price = st.number_input("Price", min_value=0.0, format="%.4f")
            amount = units * price
            st.markdown(f"**Amount: {fmt_inr(amount)}**")
            adjust_fv = False
            
            # Fat-finger pricing check warning
            price_dev = abs(price - si['face_value']) / si['face_value'] if si['face_value'] > 0 else 0.0
            if price_dev > 0.5 and price > 0:
                st.warning(f"Warning: Price {fmt_inr(price)} deviates by >50% from par value {fmt_inr(si['face_value'])}.")
                st.checkbox("Confirm this price deviation is correct", key="confirm_price_rec")
        elif ttype == 'Principal_Repayment':
            current_units = units_by_account.get(account, 0.0)
            amount = st.number_input("Total Amount", min_value=0.0, format="%.2f")
            if current_units > 0 and amount > 0:
                st.markdown(f"**Per Unit (this account): {fmt_inr(amount / current_units)}**")
            units = 0.0
            price = 0.0
        else:
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            units = 0.0
            price = 0.0

        notes = st.text_area("Notes")

        if st.form_submit_button("RECORD TRANSACTION"):
            # 1. Date boundaries check
            issue_date = pd.to_datetime(si['issue_date']).date() if pd.notna(si['issue_date']) else None
            maturity_date = pd.to_datetime(si['maturity_date']).date()
            if issue_date is not None and tdate < issue_date:
                st.error(f"Transaction date ({tdate}) cannot be before the bond's issue date ({issue_date}).")
                st.stop()
            if tdate > maturity_date:
                st.error(f"Transaction date ({tdate}) cannot be after the bond's maturity date ({maturity_date}).")
                st.stop()

            # 2. Fat-finger check confirmation
            if ttype in ["Buy", "Sell"]:
                price_dev = abs(price - si['face_value']) / si['face_value'] if si['face_value'] > 0 else 0.0
                if price_dev > 0.5 and not st.session_state.get("confirm_price_rec", False):
                    st.error("Please check the confirmation box to verify the unusual transaction price.")
                    st.stop()

            # 3. Sell validation: check sufficient units
            if ttype == 'Sell':
                held = db_query(
                    "SELECT SUM(units) as total FROM transactions WHERE bond_id=? AND account=? AND transaction_type IN ('Buy', 'Sell')",
                    (bid, account),
                )
                raw = held['total'].iloc[0] if not held.empty else 0
                available = float(raw) if pd.notna(raw) else 0.0
                if units > available:
                    st.error(f"Insufficient units. Available: **{available:.0f}**, trying to sell: **{units:.0f}**")
                    st.stop()

            # 4. Repayment cap check
            if ttype == 'Principal_Repayment':
                held = db_query(
                    "SELECT SUM(units) as total FROM transactions WHERE bond_id=? AND account=? AND transaction_type IN ('Buy', 'Sell')",
                    (bid, account),
                )
                raw = held['total'].iloc[0] if not held.empty else 0
                current_units = float(raw) if pd.notna(raw) else 0.0
                
                repaid_df = db_query(
                    "SELECT SUM(amount) as total FROM transactions WHERE bond_id=? AND account=? AND transaction_type='Principal_Repayment'",
                    (bid, account),
                )
                prior_repaid = float(repaid_df['total'].iloc[0]) if not repaid_df.empty and pd.notna(repaid_df['total'].iloc[0]) else 0.0
                
                outstanding_face = (current_units * si['face_value']) - prior_repaid
                if amount > outstanding_face + 1e-2:
                    st.error(f"Repayment amount ({fmt_inr(amount)}) cannot exceed outstanding face value ({fmt_inr(outstanding_face)}).")
                    st.stop()

            tid = str(uuid.uuid4())
            stored_units = -abs(units) if ttype == 'Sell' else abs(units)

            # Compute per-unit adjustment for principal repayment
            if ttype == 'Principal_Repayment':
                price = amount / current_units if current_units > 0 else 0.0

            stored_amount = units * price if ttype in ["Buy", "Sell"] else amount

            try:
                with _connect() as conn:
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?)",
                        (tid, bid, account, tdate.isoformat(), ttype, stored_units, price, stored_amount, notes)
                    )
                    
                    # 5. Chronological balance check
                    ok, offending_acct, offending_date = validate_ledger_chronology(bid, conn)
                    if not ok:
                        st.error(f"Transaction rejected. This would cause Account **{offending_acct}** to have negative holdings on {pd.to_datetime(offending_date).strftime('%d %b %Y')}.")
                        st.stop()
                        
                    conn.commit()

                set_notification(f"**{ttype.replace('_', ' ')}** recorded!", "success")
                logger.info(f"Recorded {ttype} for {bid}")
                st.rerun()
            except sqlite3.Error as e:
                st.error(f"Transaction failed: {e}")
                logger.error(f"Transaction failed: {e}")


# ═══════════════════════════════════════════════════════════════════════
# PAGE: EDIT TRANSACTION
# ═══════════════════════════════════════════════════════════════════════

def page_edit_transaction():
    _render_section_header("Edit Transaction", "Correct or delete an existing transaction entry", icon="layers", accent="rose")

    txns = db_query(
        "SELECT t.*, s.issuer, s.isin FROM transactions t "
        "JOIN securities s ON t.bond_id=s.bond_id ORDER BY t.trade_date DESC"
    )
    if txns.empty:
        st.warning("No transactions found.")
        return

    txns['trade_date'] = pd.to_datetime(txns['trade_date']).dt.strftime('%Y-%m-%d')
    opts = {
        f"{r['trade_date']} | {r['transaction_type']} | {r['issuer']} | "
        f"{fmt_inr(r['amount'])} | {r['transaction_id'][:8]}": r['transaction_id']
        for _, r in txns.iterrows()
    }
    sel = st.selectbox("Select Transaction", opts.keys(), index=None, placeholder="Choose…")
    if not sel:
        return

    tid = opts[sel]
    txn = txns[txns['transaction_id'] == tid].iloc[0]

    # Reactive security context panel
    sec_ctx = db_query(
        "SELECT s.coupon_rate, s.face_value, s.frequency, s.maturity_date, "
        "COALESCE(m.credit_rating, 'Unrated') as credit_rating, m.issue_date "
        "FROM securities s LEFT JOIN security_metadata m ON s.bond_id=m.bond_id "
        "WHERE s.bond_id=?", (txn['bond_id'],),
    )
    if not sec_ctx.empty:
        sc = sec_ctx.iloc[0]
        dtm = calc_days_to_maturity(sc['maturity_date'])
        mat_str = pd.to_datetime(sc['maturity_date']).strftime('%d %b %Y')
        st.markdown(
            f"<div class='info-box'><p style='font-size:0.8rem;margin:0;color:var(--text-muted);line-height:1.8;'>"
            f"Coupon: <strong>{fmt_pct(sc['coupon_rate'])}</strong> · "
            f"Face: <strong>{fmt_inr(sc['face_value'])}</strong> · "
            f"Freq: <strong>{sc['frequency']}</strong> · "
            f"Maturity: <strong>{mat_str}</strong> ({dtm}d) · "
            f"Rating: {rating_badge(sc['credit_rating'])}</p></div>",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    orig_type = txn['transaction_type']

    with st.form("edit_txn"):
        st.markdown(f"**Transaction:** `{tid[:12]}…`")
        st.text_input("Security", value=f"{txn['issuer']} ({txn['isin']})", disabled=True)

        c1, c2 = st.columns(2)
        with c1:
            acct = st.selectbox("Account", ACCOUNTS, index=_safe_index(ACCOUNTS, txn['account']))
            td = st.date_input("Date", max_value=date.today(), value=pd.to_datetime(txn['trade_date']).date())
            tt = st.selectbox("Type", TRANSACTION_TYPES, index=_safe_index(TRANSACTION_TYPES, orig_type))
        with c2:
            if orig_type in ["Buy", "Sell"]:
                u = st.number_input("Units", min_value=0, step=1, value=int(abs(txn['units'])))
                p = st.number_input("Price", min_value=0.0, format="%.4f", value=float(txn['price']))
                a = u * p
                st.markdown(f"**Amount: {fmt_inr(a)}**")
                
                # Fat-finger pricing check warning
                price_dev = abs(p - sc['face_value']) / sc['face_value'] if sc['face_value'] > 0 else 0.0
                if price_dev > 0.5 and p > 0:
                    st.warning(f"Warning: Price {fmt_inr(p)} deviates by >50% from par value {fmt_inr(sc['face_value'])}.")
                    st.checkbox("Confirm this price deviation is correct", key="confirm_price_edit")
            else:
                u = 0
                p = 0.0
                a = st.number_input("Amount", min_value=0.0, format="%.2f", value=float(txn['amount']))

        notes = st.text_area("Notes", value=txn['notes'] or '')

        col_update, col_delete = st.columns([3, 1])
        with col_update:
            update_btn = st.form_submit_button("UPDATE", width='stretch')
        with col_delete:
            delete_btn = st.form_submit_button("DELETE", width='stretch')

        if update_btn:
            old_type = txn['transaction_type']
            old_amount = float(txn['amount'])
            bond_id = txn['bond_id']

            # Guard: prevent changing transaction type (Bug 5)
            if tt != old_type:
                st.error(f"Changing transaction type from **{old_type}** to **{tt}** is not allowed. "
                         "Delete this transaction and create a new one instead.")
            else:
                # 1. Date boundaries check
                issue_date = pd.to_datetime(sc['issue_date']).date() if pd.notna(sc['issue_date']) else None
                maturity_date = pd.to_datetime(sc['maturity_date']).date()
                if issue_date is not None and td < issue_date:
                    st.error(f"Transaction date ({td}) cannot be before the bond's issue date ({issue_date}).")
                    st.stop()
                if td > maturity_date:
                    st.error(f"Transaction date ({td}) cannot be after the bond's maturity date ({maturity_date}).")
                    st.stop()

                # 2. Fat-finger check confirmation
                if tt in ["Buy", "Sell"]:
                    price_dev = abs(p - sc['face_value']) / sc['face_value'] if sc['face_value'] > 0 else 0.0
                    if price_dev > 0.5 and not st.session_state.get("confirm_price_edit", False):
                        st.error("Please check the confirmation box to verify the unusual transaction price.")
                        st.stop()

                if tt in ["Buy", "Sell"]:
                    final_amount = u * p
                    final_price = p
                    final_units = -abs(u) if tt == 'Sell' else abs(u)

                    # 3. Sell validation: ensure sufficient units
                    if tt == 'Sell':
                        held = db_query(
                            "SELECT SUM(units) as total FROM transactions "
                            "WHERE bond_id=? AND account=? AND transaction_id!=? AND transaction_type IN ('Buy', 'Sell')",
                            (bond_id, acct, tid),
                        )
                        raw = held['total'].iloc[0] if not held.empty else 0
                        available = float(raw) if pd.notna(raw) else 0.0
                        if abs(final_units) > available:
                            st.error(f"Insufficient units. Available: **{available:.0f}**, trying to sell: **{abs(final_units):.0f}**")
                            st.stop()
                elif tt == 'Principal_Repayment':
                    final_amount = a
                    final_units = 0.0
                    held = db_query(
                        "SELECT SUM(units) as total FROM transactions "
                        "WHERE bond_id=? AND account=? AND transaction_id!=? AND transaction_type IN ('Buy', 'Sell')",
                        (bond_id, acct, tid),
                    )
                    raw = held['total'].iloc[0] if not held.empty else 0
                    current_units = float(raw) if pd.notna(raw) else 0.0
                    
                    # 4. Repayment cap check
                    repaid_df = db_query(
                        "SELECT SUM(amount) as total FROM transactions WHERE bond_id=? AND account=? AND transaction_id!=? AND transaction_type='Principal_Repayment'",
                        (bond_id, acct, tid),
                    )
                    prior_repaid = float(repaid_df['total'].iloc[0]) if not repaid_df.empty and pd.notna(repaid_df['total'].iloc[0]) else 0.0
                    outstanding_face = (current_units * sc['face_value']) - prior_repaid
                    if a > outstanding_face + 1e-2:
                        st.error(f"Repayment amount ({fmt_inr(a)}) cannot exceed outstanding face value ({fmt_inr(outstanding_face)}).")
                        st.stop()
                        
                    final_price = a / current_units if current_units > 0 else 0.0
                else:
                    final_amount = a
                    final_price = 0.0
                    final_units = 0.0

                try:
                    with _connect() as conn:
                        c = conn.cursor()
                        c.execute(
                            "UPDATE transactions SET account=?, trade_date=?, transaction_type=?, "
                            "units=?, price=?, amount=?, notes=? WHERE transaction_id=?",
                            (acct, td.isoformat(), tt, final_units, final_price, final_amount, notes, tid),
                        )
                        
                        # 5. Chronological balance check
                        ok, offending_acct, offending_date = validate_ledger_chronology(bond_id, conn)
                        if not ok:
                            st.error(f"Transaction update rejected. This would cause Account **{offending_acct}** to have negative holdings on {pd.to_datetime(offending_date).strftime('%d %b %Y')}.")
                            st.stop()
                            
                        conn.commit()
                        
                    set_notification("Transaction updated!", "success")
                    st.rerun()
                except sqlite3.Error as e:
                    st.error(f"Update failed: {e}")

        if delete_btn:
            bond_id = txn['bond_id']
            try:
                with _connect() as conn:
                    c = conn.cursor()
                    c.execute("DELETE FROM transactions WHERE transaction_id=?", (tid,))
                    
                    # 5. Chronological balance check on deletion
                    ok, offending_acct, offending_date = validate_ledger_chronology(bond_id, conn)
                    if not ok:
                        st.error(f"Transaction deletion rejected. This would cause Account **{offending_acct}** to have negative holdings on {pd.to_datetime(offending_date).strftime('%d %b %Y')}.")
                        st.stop()
                        
                    conn.commit()
                    
                set_notification("Transaction deleted!", "success")
                st.rerun()
            except sqlite3.Error as e:
                st.error(f"Deletion failed: {e}")


# ═══════════════════════════════════════════════════════════════════════
# PAGE: TRANSACTION LEDGER
# ═══════════════════════════════════════════════════════════════════════

def page_view_transactions():
    _render_section_header("Transaction Ledger", "Complete audit trail of all portfolio activity", icon="database", accent="cyan")

    with st.expander("Record New Transaction", expanded=False):
        page_record_transaction(show_header=False)
    
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    f1, f2, f3 = st.columns(3)
    with f1:
        filter_acct = st.selectbox("Account", ['All'] + ACCOUNTS, key="la")
    with f2:
        filter_type = st.selectbox("Type", ['All'] + TRANSACTION_TYPES, key="lt")
    with f3:
        filter_search = st.text_input("Search Issuer", key="ls")

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
    if ledger.empty:
        st.info("No transactions match.")
        return

    ledger['trade_date'] = pd.to_datetime(ledger['trade_date']).dt.strftime('%d %b %Y')

    rows = ""
    for _, r in ledger.iterrows():
        if r['transaction_type'] in ['Buy', 'Interest_Receipt']:
            color_cls = "positive"
        elif r['transaction_type'] == 'Sell':
            color_cls = "negative"
        else:
            color_cls = ""
        units_display = f"{abs(r['units']):,.0f}" if r['units'] != 0 else '-'
        price_display = fmt_inr(r['price']) if r['price'] != 0 else '-'
        notes_display = r['notes'] or ''
        rows += (
            f"<tr><td>{r['trade_date']}</td>"
            f"<td style='font-weight:600'>{r['issuer']}</td>"
            f"<td style='font-size:0.8rem;color:#888'>{r['isin']}</td>"
            f"<td>{r['account']}</td>"
            f"<td class='{color_cls}'>{r['transaction_type'].replace('_', ' ')}</td>"
            f"<td style='text-align:right'>{units_display}</td>"
            f"<td style='text-align:right'>{price_display}</td>"
            f"<td style='text-align:right;font-weight:600'>{fmt_inr(r['amount'])}</td>"
            f"<td style='font-size:0.8rem;color:#888'>{notes_display}</td></tr>"
        )
    st.markdown(
        _render_html_table(
            ["Date", "Issuer", "ISIN", "Acct", "Type", "Units", "Price", "Amount", "Notes"],
            rows,
        ),
        unsafe_allow_html=True,
    )
    st.download_button("EXPORT LEDGER CSV", ledger.to_csv(index=False), "nivesa_ledger.csv", "text/csv")


# ═══════════════════════════════════════════════════════════════════════
# PAGE: SECURITIES MASTER
# ═══════════════════════════════════════════════════════════════════════

def page_securities_master():
    _render_section_header("Securities Master", "Complete registry of all bonds in the system", icon="cpu", accent="")

    secs = db_query(
        "SELECT s.*, m.bond_type, m.credit_rating, m.sector, m.listing "
        "FROM securities s LEFT JOIN security_metadata m ON s.bond_id=m.bond_id "
        "ORDER BY s.issuer"
    )
    if secs.empty:
        st.info("No securities registered.")
        return

    # Reactive filters
    f1, f2, f3 = st.columns(3)
    with f1:
        type_opts = ['All'] + sorted(secs['bond_type'].dropna().unique().tolist())
        sm_type = st.selectbox("Bond Type", type_opts, key="sm_type")
    with f2:
        rating_opts = ['All'] + sorted(secs['credit_rating'].dropna().unique().tolist())
        sm_rating = st.selectbox("Credit Rating", rating_opts, key="sm_rating")
    with f3:
        sm_search = st.text_input("Search Issuer", key="sm_search")

    filtered_secs = secs.copy()
    if sm_type != 'All':
        filtered_secs = filtered_secs[filtered_secs['bond_type'] == sm_type]
    if sm_rating != 'All':
        filtered_secs = filtered_secs[filtered_secs['credit_rating'] == sm_rating]
    if sm_search:
        filtered_secs = filtered_secs[filtered_secs['issuer'].str.contains(sm_search, case=False, na=False)]

    rows = ""
    for _, s in filtered_secs.iterrows():
        dtm = calc_days_to_maturity(s['maturity_date'])
        mat_str = pd.to_datetime(s['maturity_date']).strftime('%d %b %Y')
        rating = s.get('credit_rating', 'Unrated') or 'Unrated'
        bond_type = s.get('bond_type', 'NCD') or 'NCD'
        sector = s.get('sector', '') or ''
        rows += (
            f"<tr><td style='font-weight:600'>{s['issuer']}</td>"
            f"<td style='font-size:0.8rem'>{s['isin']}</td>"
            f"<td>{bond_type}</td>"
            f"<td>{rating_badge(rating)}</td>"
            f"<td style='text-align:right'>{fmt_pct(s['coupon_rate'])}</td>"
            f"<td style='text-align:right'>{fmt_inr(s['face_value'])}</td>"
            f"<td>{s['frequency']}</td>"
            f"<td>{mat_str}</td>"
            f"<td style='text-align:right'>{dtm}d</td>"
            f"<td>{sector}</td></tr>"
        )
    st.markdown(
        _render_html_table(
            ["Issuer", "ISIN", "Type", "Rating", "Coupon", "Face Value", "Freq", "Maturity", "Days", "Sector"],
            rows,
        ),
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

PAGE_ROUTES = {
    "Dashboard":             lambda: page_dashboard(),
    "Transaction Ledger":    lambda: page_view_transactions(),
    "Securities Master":     lambda: page_securities_master(),
    "Add Security":          lambda: page_add_security(),
    "Edit Security":         lambda: page_edit_security(),
    "Record Transaction":    lambda: page_record_transaction(),
    "Edit Transaction":      lambda: page_edit_transaction(),
}


def _render_footer() -> None:
    """Render the app footer with copyright and version info."""
    ist_now = datetime.now()
    st.markdown(
        f'<div class="app-footer">'
        f'<div class="content">'
        f'© {ist_now.year} <strong>{PRODUCT_NAME}</strong> &nbsp;·&nbsp; {COMPANY} &nbsp;·&nbsp; v{VERSION} &nbsp;·&nbsp; {ist_now.strftime("%Y-%m-%d %H:%M:%S")} Local'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def main():
    db_init()
    show_notifications()

    # ── Sidebar ──
    with st.sidebar:
        st.markdown(
            f"""
            <div style="text-align:center;padding:0.5rem 0 0.75rem 0;">
                <div style="font-family:var(--display);font-size:1.35rem;font-weight:700;color:var(--amber);letter-spacing:0.04em;">{PRODUCT_NAME}</div>
                <div style="font-family:var(--data);color:var(--ink-tertiary);font-size:0.6rem;margin-top:0.1rem;letter-spacing:0.06em;text-transform:uppercase;">{PRODUCT_DEVANAGARI} | Bond Portfolio Ledger</div>
            </div>
            <hr style="margin: 0.5rem 0; opacity: 0.1;">
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="sidebar-title">Navigation</div>', unsafe_allow_html=True)
        pages = ["Dashboard", "Transaction Ledger", "Securities Master", "Add Security", "Edit Security", "Record Transaction", "Edit Transaction"]
        page = st.selectbox("Navigation", pages, label_visibility="collapsed", key="nav_main")
        
        # Show spec box matching Pragyam's version box
        st.markdown('<hr style="margin: 2.00rem 0; opacity: 0.05;">', unsafe_allow_html=True)
        try:
            sec_count = db_query("SELECT COUNT(*) as c FROM securities")['c'].iloc[0]
            txn_count = db_query("SELECT COUNT(*) as c FROM transactions")['c'].iloc[0]
        except Exception:
            sec_count = 0
            txn_count = 0
        rows = [
            '<div class="system-spec">',
            f'<div class="spec-row"><span class="spec-label">Version</span><span class="spec-value">{VERSION}</span></div>',
            f'<div class="spec-row"><span class="spec-label">Securities</span><span class="spec-value">{sec_count}</span></div>',
            f'<div class="spec-row"><span class="spec-label">Transactions</span><span class="spec-value">{txn_count}</span></div>',
            '<div class="spec-row"><span class="spec-label">Database</span><span class="spec-value">SQLite (WAL)</span></div>',
            f'<div class="spec-row"><span class="spec-label">Product</span><span class="spec-value">{COMPANY}</span></div>',
            '</div>'
        ]
        st.markdown(''.join(rows), unsafe_allow_html=True)

    # ── Header ──
    st.markdown(
        f'<div class="premium-header">'
        f'<h1>{PRODUCT_NAME}</h1>'
        f'<div class="tagline">{TAGLINE}</div></div>',
        unsafe_allow_html=True,
    )

    # ── Route ──
    handler = PAGE_ROUTES.get(page)
    if handler:
        handler()

    # ── Footer ──
    _render_footer()


if __name__ == "__main__":
    main()
