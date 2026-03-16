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
    page_icon="📊",
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
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

        :root {
            --primary-color: #FFC300;
            --primary-rgb: 255, 195, 0;
            --background-color: #0F0F0F;
            --secondary-background-color: #1A1A1A;
            --bg-card: #1A1A1A;
            --bg-elevated: #2A2A2A;
            --text-primary: #EAEAEA;
            --text-secondary: #EAEAEA;
            --text-muted: #888888;
            --border-color: #2A2A2A;
            --border-light: #3A3A3A;

            --success-green: #10b981;
            --success-dark: #059669;
            --danger-red: #ef4444;
            --danger-dark: #dc2626;
            --warning-amber: #f59e0b;
            --info-cyan: #06b6d4;
            --neutral: #888888;
        }

        * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

        .main, [data-testid="stSidebar"] {
            background-color: var(--background-color);
            color: var(--text-primary);
        }

        .stApp > header { background-color: transparent; }
        #MainMenu {visibility: hidden;} footer {visibility: hidden;}

        .block-container {
            padding-top: 3.5rem;
            max-width: 90%;
            padding-left: 2rem;
            padding-right: 2rem;
        }

        /* ── Sidebar toggle button ── */
        [data-testid="collapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            background-color: var(--secondary-background-color) !important;
            border: 2px solid var(--primary-color) !important;
            border-radius: 8px !important;
            padding: 10px !important;
            margin: 12px !important;
            box-shadow: 0 0 15px rgba(var(--primary-rgb), 0.4) !important;
            z-index: 999999 !important;
            position: fixed !important;
            top: 14px !important;
            left: 14px !important;
            width: 40px !important;
            height: 40px !important;
            align-items: center !important;
            justify-content: center !important;
        }
        [data-testid="collapsedControl"]:hover {
            background-color: rgba(var(--primary-rgb), 0.2) !important;
            box-shadow: 0 0 20px rgba(var(--primary-rgb), 0.6) !important;
            transform: scale(1.05);
        }
        [data-testid="collapsedControl"] svg {
            stroke: var(--primary-color) !important;
            width: 20px !important;
            height: 20px !important;
        }
        [data-testid="stSidebar"] button[kind="header"] {
            background-color: transparent !important;
            border: none !important;
        }
        [data-testid="stSidebar"] button[kind="header"] svg {
            stroke: var(--primary-color) !important;
        }
        button[kind="header"] { z-index: 999999 !important; }

        [data-testid="stSidebar"] {
            background: var(--secondary-background-color);
            border-right: 1px solid var(--border-color);
        }

        /* ── Premium Header ── */
        .premium-header {
            background: var(--secondary-background-color);
            padding: 1.25rem 2rem;
            border-radius: 16px;
            margin-bottom: 1.5rem;
            box-shadow: 0 0 20px rgba(var(--primary-rgb), 0.1);
            border: 1px solid var(--border-color);
            position: relative;
            overflow: hidden;
            margin-top: 1rem;
        }
        .premium-header::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: radial-gradient(circle at 20% 50%, rgba(var(--primary-rgb),0.08) 0%, transparent 50%);
            pointer-events: none;
        }
        .premium-header h1 {
            margin: 0;
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.50px;
            position: relative;
        }
        .premium-header .tagline {
            color: var(--text-muted);
            font-size: 0.9rem;
            margin-top: 0.25rem;
            font-weight: 400;
            position: relative;
        }

        /* ── Metric Cards ── */
        .metric-card {
            background-color: var(--bg-card);
            padding: 1.25rem;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            box-shadow: 0 0 15px rgba(var(--primary-rgb), 0.08);
            margin-bottom: 0.5rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            height: 100%;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(0,0,0,0.3);
            border-color: var(--border-light);
        }
        .metric-card h4 {
            color: var(--text-muted);
            font-size: 0.75rem;
            margin-bottom: 0.5rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .metric-card h2 {
            color: var(--text-primary);
            font-size: 1.75rem;
            font-weight: 700;
            margin: 0;
            line-height: 1;
        }
        .metric-card .sub-metric {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 0.5rem;
            font-weight: 500;
        }
        .metric-card.success h2 { color: var(--success-green); }
        .metric-card.danger h2  { color: var(--danger-red); }
        .metric-card.warning h2 { color: var(--warning-amber); }
        .metric-card.info h2    { color: var(--info-cyan); }
        .metric-card.neutral h2 { color: var(--neutral); }
        .metric-card.primary h2 { color: var(--primary-color); }

        /* ── Table Styling ── */
        .table-container {
            width: 100%;
            overflow-x: auto;
            border-radius: 12px;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            padding: 0;
        }
        table.table {
            width: 100%;
            table-layout: auto;
            border-collapse: collapse;
            color: var(--text-primary);
        }
        table.table th, table.table td {
            padding: 0.85rem 1.1rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }
        table.table th {
            font-weight: 600;
            color: var(--primary-color);
            background-color: var(--bg-elevated);
            text-transform: uppercase;
            font-size: 0.78rem;
            letter-spacing: 0.05em;
        }
        table.table td { font-size: 0.9rem; }
        table.table tr:hover { background: var(--bg-elevated); }

        /* ── Tab styling ── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
            background: transparent;
            padding: 0;
            margin-top: 1.5rem;
            margin-bottom: 1.5rem;
        }
        .stTabs [data-baseweb="tab"] {
            color: var(--text-muted);
            border-bottom: 2px solid transparent;
            transition: color 0.3s, border-bottom 0.3s;
            background: transparent;
            font-weight: 600;
        }
        .stTabs [aria-selected="true"] {
            color: var(--primary-color) !important;
            border-bottom: 2px solid var(--primary-color);
            background: transparent !important;
        }

        .positive { color: var(--success-green) !important; }
        .negative { color: var(--danger-red) !important; }
        .neutral-text { color: var(--text-primary) !important; }

        /* ── Sections ── */
        .section-header {
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border-color);
        }
        .section-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
            margin: 0;
        }
        .section-subtitle {
            font-size: 0.95rem;
            color: var(--text-muted);
            margin: 0.25rem 0 0 0;
        }
        .section-divider {
            height: 1px;
            background: linear-gradient(90deg, transparent 0%, var(--border-color) 50%, transparent 100%);
            margin: 1.5rem 0;
        }

        .sidebar-title {
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--primary-color);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.75rem;
        }

        .info-box {
            background: var(--secondary-background-color);
            border: 1px solid var(--border-color);
            padding: 1.25rem;
            border-radius: 12px;
            margin: 0.5rem 0;
            box-shadow: 0 0 15px rgba(var(--primary-rgb), 0.08);
        }
        .info-box h4 { color: var(--primary-color); margin: 0 0 0.5rem 0; font-size: 1rem; font-weight: 700; }
        .info-box p  { color: var(--text-muted); margin: 0; font-size: 0.9rem; line-height: 1.6; }

        /* ── Buttons ── */
        .stButton>button, .stFormSubmitButton>button {
            border: 2px solid var(--primary-color) !important;
            background: transparent !important;
            color: var(--primary-color) !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
            padding: 0.75rem 2rem !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
        }
        .stButton>button:hover, .stFormSubmitButton>button:hover {
            box-shadow: 0 0 25px rgba(var(--primary-rgb), 0.6) !important;
            background: var(--primary-color) !important;
            color: #1A1A1A !important;
            transform: translateY(-2px) !important;
        }
        .stButton>button:active, .stFormSubmitButton>button:active {
            transform: translateY(0) !important;
        }

        .stDownloadButton>button {
            border: 2px solid var(--primary-color) !important;
            background: transparent !important;
            color: var(--primary-color) !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
            padding: 0.75rem 2rem !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
        }
        .stDownloadButton>button:hover {
            box-shadow: 0 0 25px rgba(var(--primary-rgb), 0.6) !important;
            background: var(--primary-color) !important;
            color: #1A1A1A !important;
            transform: translateY(-2px) !important;
        }

        /* ── Plotly charts ── */
        .stPlotlyChart {
            border-radius: 12px;
            background-color: var(--secondary-background-color);
            padding: 10px;
            border: 1px solid var(--border-color);
            box-shadow: 0 0 25px rgba(var(--primary-rgb), 0.1);
        }

        /* ── Form ── */
        .stForm {
            background: var(--bg-card) !important;
            padding: 1.5rem !important;
            border-radius: 12px !important;
            border: 1px solid var(--border-color) !important;
            box-shadow: 0 0 15px rgba(var(--primary-rgb), 0.08) !important;
        }

        /* ── Scrollbar ── */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--background-color); }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--border-light); }

        /* ── Badges ── */
        .badge {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 20px;
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.05em;
        }
        .badge-aaa     { background: rgba(16,185,129,0.15); color: #10b981; }
        .badge-aa      { background: rgba(6,182,212,0.15);  color: #06b6d4; }
        .badge-a       { background: rgba(245,158,11,0.15); color: #f59e0b; }
        .badge-bbb     { background: rgba(249,115,22,0.15); color: #f97316; }
        .badge-below   { background: rgba(239,68,68,0.15);  color: #ef4444; }
        .badge-unrated { background: rgba(136,136,136,0.15); color: #888; }
    </style>
    """, unsafe_allow_html=True)

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
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys=ON")
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

def calc_coupon_payment(face_value, coupon_rate, frequency):
    return face_value * coupon_rate / FREQ_MAP.get(frequency, 1)


def calc_accrued_interest(face_value, coupon_rate, frequency, last_coupon_date=None):
    freq = FREQ_MAP.get(frequency, 1)
    days = ((365.25 / freq) / 2) if last_coupon_date is None else (date.today() - last_coupon_date).days
    return face_value * coupon_rate / 365.25 * days


def calc_macaulay_duration(fv, coupon_rate, frequency, maturity_str, ytm):
    try:
        mat = pd.to_datetime(maturity_str)
        yrs = (mat - pd.to_datetime(date.today())).days / 365.25
        if yrs <= 0 or ytm <= 0: return 0.0
        freq = FREQ_MAP.get(frequency, 1)
        nper = max(1, int(yrs * freq))
        c = fv * coupon_rate / freq
        r = ytm / freq
        pv_w = pv_s = 0.0
        for t in range(1, nper + 1):
            cf = c + (fv if t == nper else 0)
            pv = cf / (1 + r) ** t
            pv_w += (t / freq) * pv
            pv_s += pv
        return pv_w / pv_s if pv_s else 0.0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0


def calc_modified_duration(mac, ytm, frequency):
    freq = FREQ_MAP.get(frequency, 1)
    return mac / (1 + ytm / freq) if ytm > 0 else mac


def calc_yield_to_cost(fv_pu, cost_pu, coupon_rate, maturity_str, frequency, ppy):
    try:
        days = (pd.to_datetime(maturity_str) - pd.to_datetime(date.today())).days
        if days <= 0 or cost_pu <= 0: return 0.0
        nper = days / 365.25 * ppy
        if nper <= 0: return 0.0
        pmt = calc_coupon_payment(fv_pu, coupon_rate, frequency)
        rate = npf.rate(nper=nper, pmt=pmt, pv=-cost_pu, fv=fv_pu)
        return 0.0 if np.isnan(rate) else rate * ppy
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
        face     = cur_u * si['face_value']
        ppy      = FREQ_MAP.get(si['frequency'], 1)
        cost_pu  = cost / cur_u if cur_u else 0
        fv_pu    = face / cur_u if cur_u else 0

        ytc = calc_yield_to_cost(fv_pu, cost_pu, si['coupon_rate'], si['maturity_date'], si['frequency'], ppy)
        use_y = ytc if ytc > 0 else si['coupon_rate']
        mac = calc_macaulay_duration(fv_pu, si['coupon_rate'], si['frequency'], si['maturity_date'], use_y)
        mod = calc_modified_duration(mac, use_y, si['frequency'])
        dtm = calc_days_to_maturity(si['maturity_date'])
        ann_cpn = cur_u * fv_pu * si['coupon_rate']
        acc_int = calc_accrued_interest(fv_pu, si['coupon_rate'], si['frequency']) * cur_u
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
            'holding_days': hold_days, 'total_income': int_recv,
            'bond_type':      mi['bond_type']      if mi is not None else 'NCD',
            'credit_rating':  mi['credit_rating']  if mi is not None else 'Unrated',
            'sector':         mi['sector']          if mi is not None else 'Financials',
        })

    if not positions: return pd.DataFrame(), {}
    df = pd.DataFrame(positions)
    tc = df['cost_basis'].sum()

    if tc > 0:
        df['weight'] = df['cost_basis'] / tc
        w = lambda col: (df[col] * df['weight']).sum()
    else:
        df['weight'] = 0
        w = lambda col: 0.0

    totals = {
        'Total Cost Basis':       tc,
        'Total Face Value':       df['position_face_value'].sum(),
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
CC = ['#FFC300','#10b981','#06b6d4','#f59e0b','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#6366f1']


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


def _render_metric(col, style, title, value, sub=""):
    """Render a single metric card into a Streamlit column."""
    sub_html = f"<div class='sub-metric'>{sub}</div>" if sub else ""
    col.markdown(
        f"<div class='metric-card {style}'><h4>{title}</h4>"
        f"<h2>{value}</h2>{sub_html}</div>",
        unsafe_allow_html=True,
    )


def _render_html_table(headers, rows_html):
    """Wrap header list and row HTML into a styled table."""
    th = "".join(f"<th>{h}</th>" for h in headers)
    return (
        f"<div class='table-container'><table class='table'>"
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
    st.markdown(
        "<div class='section'><div class='section-header'>"
        "<h3 class='section-title'>Portfolio Overview</h3>"
        "<p class='section-subtitle'>Fixed income snapshot with risk & return metrics</p>"
        "</div></div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    _render_metric(c1, "primary", "Total Invested (Cost)",
                   fmt_inr_short(totals['Total Cost Basis']),
                   f"Face Value: {fmt_inr_short(totals['Total Face Value'])}")
    _render_metric(c2, "info", "Portfolio Yield (WA)",
                   fmt_pct(totals['Weighted YTC']),
                   f"Nominal: {fmt_pct(totals['Weighted Nominal Yield'])}")
    _render_metric(c3, "warning", "Annual Coupon Income",
                   fmt_inr_short(totals['Total Annual Coupon']),
                   f"Monthly: ~{fmt_inr_short(totals['Total Annual Coupon'] / 12)}")
    _render_metric(c4, "", "Weighted Duration",
                   f"{totals['Weighted Mac Duration']:.2f}y",
                   f"Modified: {totals['Weighted Mod Duration']:.2f}y")
    _render_metric(c5, "", "Portfolio Composition",
                   str(totals['Num Positions']),
                   f"{totals['Num Issuers']} issuers · {totals['Num Accounts']} accounts")

    # ── Tabs ──
    tab_alloc, tab_pos, tab_mat, tab_cf, tab_issuer = st.tabs([
        "Allocation & Risk", "Positions", "Maturity Ladder",
        "Cashflow Schedule", "Issuer Detail",
    ])

    # ─────────────────────────────────────────────────────────────────────
    # TAB 1: Allocation & Risk (reimagined)
    # ─────────────────────────────────────────────────────────────────────
    with tab_alloc:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        sb = df[df['cost_basis'] > 0].copy()

        total_cost = totals['Total Cost Basis']

        if sb.empty:
            st.info("No positions with positive cost basis to display.")
        else:
            # Use positive-cost-basis total for accurate weight calculation
            total_cost_alloc = sb['cost_basis'].sum()

            # ── Account Capital Allocation Table ──
            st.markdown("#### Capital Allocation by Account")
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

            max_acct_wt = acct_agg['Wt'].max() if not acct_agg.empty and acct_agg['Wt'].max() > 0 else 1.0
            acct_rows = ""
            for _, r in acct_agg.iterrows():
                bar_pct = (r['Wt'] / max_acct_wt) * 100
                acct_rows += (
                    f"<tr><td style='font-weight:600'>{r['account']}</td>"
                    f"<td>{fmt_inr(r['Cost'])}</td><td>{fmt_inr(r['Face'])}</td>"
                    f"<td><div style='display:flex;align-items:center;gap:8px'>"
                    f"<div style='width:60px;height:6px;background:#2A2A2A;border-radius:3px;overflow:hidden'>"
                    f"<div style='width:{bar_pct:.0f}%;height:100%;background:#FFC300;border-radius:3px'></div></div>"
                    f"<span>{r['Wt']:.1%}</span></div></td>"
                    f"<td style='text-align:center'>{int(r['Pos'])}</td>"
                    f"<td style='text-align:center'>{int(r['Issuers'])}</td>"
                    f"<td>{fmt_pct(r['NY'])}</td><td>{fmt_pct(r['YC'])}</td>"
                    f"<td style='text-align:right'>{fmt_inr(r['Inc'])}</td></tr>"
                )
            st.markdown(
                _render_html_table(
                    ["Account", "Cost Basis", "Face Value", "Weight", "Pos", "Issuers", "Nominal", "YTC", "Annual Inc"],
                    acct_rows,
                ),
                unsafe_allow_html=True,
            )

        # ── Concentration Risk Table ──
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("#### Concentration Risk")

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

        max_wt = ir['Wt'].max() if not ir.empty and ir['Wt'].max() > 0 else 1.0
        rows = ""
        for _, r in ir.iterrows():
            bar_pct = (r['Wt'] / max_wt) * 100
            wc = '#ef4444' if r['Wt'] > 0.15 else '#f59e0b' if r['Wt'] > 0.10 else '#10b981'
            bar_html = (
                f"<div style='display:flex;align-items:center;gap:8px'>"
                f"<div style='width:60px;height:6px;background:#2A2A2A;border-radius:3px;overflow:hidden'>"
                f"<div style='width:{bar_pct:.0f}%;height:100%;background:{wc};border-radius:3px'></div></div>"
                f"<span>{r['Wt']:.1%}</span></div>"
            )
            rows += (
                f"<tr><td style='font-weight:600'>{r['issuer']}</td>"
                f"<td>{fmt_inr(r['Cost'])}</td><td>{fmt_inr(r['Face'])}</td>"
                f"<td>{bar_html}</td>"
                f"<td>{fmt_pct(r['NY'])}</td><td>{fmt_pct(r['YC'])}</td>"
                f"<td style='text-align:center'>{int(r['Pos'])}</td></tr>"
            )
        st.markdown(
            _render_html_table(
                ["Issuer", "Cost Basis", "Face Value", "Weight", "Nominal", "YTC", "Pos"],
                rows,
            ),
            unsafe_allow_html=True,
        )

    # ─────────────────────────────────────────────────────────────────────
    # TAB 2: Positions
    # ─────────────────────────────────────────────────────────────────────
    with tab_pos:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
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
            rows += (
                f"<tr><td><div style='font-weight:600'>{p['issuer']}</div>"
                f"<div style='font-size:0.75rem;color:#888'>{p['isin']}</div></td>"
                f"<td>{rating_badge(p['credit_rating'])}</td>"
                f"<td>{p['account']}</td>"
                f"<td style='text-align:right'>{int(p['current_units'])}</td>"
                f"<td style='text-align:right'>{fmt_inr(p['cost_basis'])}</td>"
                f"<td style='text-align:right'>{fmt_inr(p['position_face_value'])}</td>"
                f"<td style='text-align:right'>{fmt_pct(p['nominal_yield'])}</td>"
                f"<td style='text-align:right'>{fmt_pct(p['yield_to_cost'])}</td>"
                f"<td style='text-align:right'>{p['macaulay_duration']:.2f}y</td>"
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
        exp = filtered[export_cols].copy()
        exp['maturity_date'] = pd.to_datetime(exp['maturity_date']).dt.strftime('%Y-%m-%d')
        st.download_button("EXPORT CSV", exp.to_csv(index=False), "nivesa_positions.csv", "text/csv")

    # ─────────────────────────────────────────────────────────────────────
    # TAB 3: Maturity Ladder
    # ─────────────────────────────────────────────────────────────────────
    with tab_mat:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

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
        st.plotly_chart(fig, width='stretch')

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
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        cf_filter = st.selectbox(
            "Filter by Account",
            ['All'] + sorted(df['account'].unique().tolist()),
            key="cf_acct",
        )
        cf_df = df if cf_filter == 'All' else df[df['account'] == cf_filter]

        all_cf = []
        for _, p in cf_df.iterrows():
            fvpu = p['position_face_value'] / p['current_units'] if p['current_units'] > 0 else 0
            schedule = generate_cashflow_schedule(
                fvpu, p['coupon_rate'], p['frequency'], p['maturity_date'], p['current_units'],
            )
            for cf in schedule:
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
            st.plotly_chart(fig, width='stretch')

            total_cpn = cdf['coupon'].sum()
            total_prin = cdf['principal'].sum()
            s1, s2, s3 = st.columns(3)
            _render_metric(s1, "", "Future Coupons", fmt_inr_short(total_cpn))
            _render_metric(s2, "", "Principal Due", fmt_inr_short(total_prin))
            _render_metric(s3, "", "Total Future CF", fmt_inr_short(total_cpn + total_prin))

            cutoff = pd.to_datetime(date.today() + timedelta(days=365))
            n12 = cdf[cdf['date'] <= cutoff]
            if not n12.empty:
                st.markdown("#### Upcoming Cashflows (Next 12 Months)")
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
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

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


# ═══════════════════════════════════════════════════════════════════════
# PAGE: ADD SECURITY
# ═══════════════════════════════════════════════════════════════════════

def _render_section_header(title, subtitle):
    """Render a consistent section header."""
    st.markdown(
        f"<div class='section'><div class='section-header'>"
        f"<h3 class='section-title'>{title}</h3>"
        f"<p class='section-subtitle'>{subtitle}</p>"
        f"</div></div>",
        unsafe_allow_html=True,
    )


def page_add_security():
    _render_section_header("Add New Security", "Register a bond in the securities master before transacting")

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
            idate = st.date_input("Issue Date (optional)", value=None)
            dc = st.selectbox("Day Count", DAY_COUNT_CONVENTIONS)

        notes = st.text_area("Notes")
        submitted = st.form_submit_button("ADD SECURITY")

        if submitted:
            if not issuer or not isin:
                st.error("Issuer and ISIN are required.")
            elif mat <= date.today():
                st.error("Maturity date must be in the future.")
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
                    st.success(f"Security **{issuer}** ({isin}) added!")
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
    _render_section_header("Edit Security", "Update security master data and metadata")

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
        "FROM transactions WHERE bond_id=? GROUP BY account HAVING SUM(units) > 0",
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
            dc = st.selectbox(
                "Day Count", DAY_COUNT_CONVENTIONS,
                index=_safe_index(DAY_COUNT_CONVENTIONS, meta['day_count'] if meta is not None else None),
            )

        if txn_count > 0:
            st.warning(f"{txn_count} transactions exist. Editing face value changes all calculations retroactively.")

        if st.form_submit_button("UPDATE SECURITY"):
            if not issuer:
                st.error("Issuer required.")
            else:
                db_execute(
                    "UPDATE securities SET issuer=?, maturity_date=?, frequency=?, coupon_rate=?, face_value=? WHERE bond_id=?",
                    (issuer, mat.isoformat(), freq, cpn / 100, fv, bid),
                )
                db_execute(
                    "UPDATE security_metadata SET bond_type=?, credit_rating=?, day_count=?, listing=?, sector=? WHERE bond_id=?",
                    (btype, cr, dc, listing, sector, bid),
                )
                st.success(f"**{issuer}** updated!")
                logger.info(f"Updated security: {bid}")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: RECORD TRANSACTION
# ═══════════════════════════════════════════════════════════════════════

def page_record_transaction():
    _render_section_header("Record Transaction", "Record a Buy, Sell, Interest Receipt, or Principal Repayment")

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
        "COALESCE(m.credit_rating, 'Unrated') as credit_rating "
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
        elif ttype == 'Principal_Repayment':
            current_units = units_by_account.get(account, 0.0)
            amount = st.number_input("Total Amount", min_value=0.0, format="%.2f")
            if current_units > 0 and amount > 0:
                st.markdown(f"**Per Unit (this account): {fmt_inr(amount / current_units)}**")
            adjust_fv = st.checkbox("Adjust Face Value", value=True)
            if adjust_fv and total_units_all > 0 and amount > 0:
                fv_adj = amount / total_units_all
                st.markdown(f"Face value will be reduced by **{fmt_inr(fv_adj)}**/unit globally")
            units = 0.0
            price = 0.0
        else:
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            units = 0.0
            price = 0.0
            adjust_fv = False

        notes = st.text_area("Notes")

        if st.form_submit_button("RECORD TRANSACTION"):
            # Sell validation: check sufficient units before proceeding
            if ttype == 'Sell':
                held = db_query(
                    "SELECT SUM(units) as total FROM transactions WHERE bond_id=? AND account=?",
                    (bid, account),
                )
                raw = held['total'].iloc[0] if not held.empty else 0
                available = float(raw) if pd.notna(raw) else 0.0
                if units > available:
                    st.error(f"Insufficient units. Available: **{available:.0f}**, trying to sell: **{units:.0f}**")
                    st.stop()

            tid = str(uuid.uuid4())
            stored_units = -abs(units) if ttype == 'Sell' else abs(units)
            stored_amount = units * price if ttype in ["Buy", "Sell"] else amount

            # Compute per-unit adjustment for principal repayment
            # Use total units across ALL accounts so face_value (a global security attribute)
            # is reduced correctly regardless of how many accounts hold this bond
            adj_per_unit = 0.0
            if ttype == 'Principal_Repayment':
                held = db_query("SELECT units FROM transactions WHERE bond_id=?", (bid,))
                held_units = held['units'].sum() if not held.empty else 0.0
                adj_per_unit = amount / held_units if held_units > 0 else 0.0

            ok = db_execute(
                "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?)",
                (tid, bid, account, tdate.isoformat(), ttype, stored_units, price, stored_amount, notes),
            )
            if ok:
                st.success(f"**{ttype.replace('_', ' ')}** recorded!")
                logger.info(f"Recorded {ttype} for {bid}")
                if ttype == 'Principal_Repayment' and adjust_fv and adj_per_unit > 0:
                    db_execute("UPDATE securities SET face_value=face_value-? WHERE bond_id=?", (adj_per_unit, bid))
                    st.success(f"Face value adjusted by {fmt_inr(adj_per_unit)}/unit")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: EDIT TRANSACTION
# ═══════════════════════════════════════════════════════════════════════

def page_edit_transaction():
    _render_section_header("Edit Transaction", "Correct or delete an existing transaction entry")

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
        "COALESCE(m.credit_rating, 'Unrated') as credit_rating "
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
            else:
                u = 0
                p = 0.0
                a = st.number_input("Amount", min_value=0.0, format="%.2f", value=float(txn['amount']))

        notes = st.text_area("Notes", value=txn['notes'] or '')

        col_update, col_delete = st.columns([3, 1])
        with col_update:
            update_btn = st.form_submit_button("UPDATE", use_container_width=True)
        with col_delete:
            delete_btn = st.form_submit_button("DELETE", use_container_width=True)

        if update_btn:
            old_type = txn['transaction_type']
            old_amount = float(txn['amount'])
            bond_id = txn['bond_id']

            # Guard: prevent changing transaction type (Bug 5)
            if tt != old_type:
                st.error(f"Changing transaction type from **{old_type}** to **{tt}** is not allowed. "
                         "Delete this transaction and create a new one instead.")
            else:
                if tt in ["Buy", "Sell"]:
                    final_amount = u * p
                    final_price = p
                    final_units = -abs(u) if tt == 'Sell' else abs(u)

                    # Sell validation: ensure sufficient units
                    if tt == 'Sell':
                        held = db_query(
                            "SELECT SUM(units) as total FROM transactions "
                            "WHERE bond_id=? AND account=? AND transaction_id!=?",
                            (bond_id, acct, tid),
                        )
                        raw = held['total'].iloc[0] if not held.empty else 0
                        available = float(raw) if pd.notna(raw) else 0.0
                        if abs(final_units) > available:
                            st.error(f"Insufficient units. Available: **{available:.0f}**, trying to sell: **{abs(final_units):.0f}**")
                            st.stop()
                else:
                    final_amount = a
                    final_price = 0.0
                    final_units = 0.0

                ok = db_execute(
                    "UPDATE transactions SET account=?, trade_date=?, transaction_type=?, "
                    "units=?, price=?, amount=?, notes=? WHERE transaction_id=?",
                    (acct, td.isoformat(), tt, final_units, final_price, final_amount, notes, tid),
                )
                if ok:
                    # Reverse/adjust face value if editing a Principal_Repayment amount
                    if old_type == 'Principal_Repayment' and final_amount != old_amount:
                        all_held = db_query("SELECT units FROM transactions WHERE bond_id=?", (bond_id,))
                        total_units = all_held['units'].sum() if not all_held.empty else 0.0
                        if total_units > 0:
                            old_adj = old_amount / total_units
                            new_adj = final_amount / total_units
                            diff = new_adj - old_adj
                            if abs(diff) > 0.0001:
                                db_execute("UPDATE securities SET face_value=face_value-? WHERE bond_id=?", (diff, bond_id))
                    st.success("Transaction updated!")
                    st.rerun()

        if delete_btn:
            bond_id = txn['bond_id']
            old_type = txn['transaction_type']
            old_amount = float(txn['amount'])

            if db_execute("DELETE FROM transactions WHERE transaction_id=?", (tid,)):
                # Reverse face value adjustment if deleting a Principal_Repayment
                if old_type == 'Principal_Repayment':
                    all_held = db_query("SELECT units FROM transactions WHERE bond_id=?", (bond_id,))
                    total_units = all_held['units'].sum() if not all_held.empty else 0.0
                    if total_units > 0:
                        adj_per_unit = old_amount / total_units
                        db_execute("UPDATE securities SET face_value=face_value+? WHERE bond_id=?", (adj_per_unit, bond_id))
                st.success("Transaction deleted!")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: TRANSACTION LEDGER
# ═══════════════════════════════════════════════════════════════════════

def page_view_transactions():
    _render_section_header("Transaction Ledger", "Complete audit trail of all portfolio activity")

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
        units_display = f"{r['units']:,.0f}" if r['units'] != 0 else '-'
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
    _render_section_header("Securities Master", "Complete registry of all bonds in the system")

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
    "Dashboard":          lambda: page_dashboard(),
    "Securities Master":  lambda: page_securities_master(),
    "Add Security":       lambda: page_add_security(),
    "Edit Security":      lambda: page_edit_security(),
    "Record Transaction": lambda: page_record_transaction(),
    "Edit Transaction":   lambda: page_edit_transaction(),
    "Transaction Ledger": lambda: page_view_transactions(),
}


def main():
    db_init()

    # ── Sidebar ──
    with st.sidebar:
        st.markdown(
            f"<div style='text-align:center;padding:1rem 0;margin-bottom:1rem;'>"
            f"<div style='font-size:1.75rem;font-weight:800;color:#FFC300;'>{PRODUCT_NAME.upper()}</div>"
            f"<div style='color:#888;font-size:0.75rem;margin-top:0.25rem;'>"
            f"{PRODUCT_DEVANAGARI} | Bond Portfolio Ledger</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-title">Navigation</div>', unsafe_allow_html=True)

        page = st.radio("Nav", [
            "Dashboard", "Securities Master", "Add Security",
            "Edit Security", "Record Transaction",
            "Edit Transaction", "Transaction Ledger",
        ], label_visibility="collapsed")

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-title">Quick Stats</div>', unsafe_allow_html=True)

        sec_count = db_query("SELECT COUNT(*) as c FROM securities")['c'].iloc[0]
        txn_count = db_query("SELECT COUNT(*) as c FROM transactions")['c'].iloc[0]
        st.markdown(
            f"<div class='info-box'><p style='font-size:0.8rem;margin:0;color:var(--text-muted);line-height:1.8;'>"
            f"<strong>Securities:</strong> {sec_count}<br>"
            f"<strong>Transactions:</strong> {txn_count}<br>"
            f"<strong>Date:</strong> {datetime.now().strftime('%d %b %Y')}</p></div>",
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown(
            f"<div class='info-box'><p style='font-size:0.8rem;margin:0;color:var(--text-muted);line-height:1.5;'>"
            f"<strong>Version:</strong> {VERSION}<br><strong>Build:</strong> {BUILD}<br>"
            f"<strong>Engine:</strong> SQLite + NumPy Financial<br>"
            f"<strong>Product:</strong> {COMPANY}</p></div>",
            unsafe_allow_html=True,
        )

    # ── Header ──
    st.markdown(
        f'<div class="premium-header">'
        f'<h1>{PRODUCT_NAME.upper()} : Bond Portfolio Ledger</h1>'
        f'<div class="tagline">{TAGLINE}</div></div>',
        unsafe_allow_html=True,
    )

    # ── Route ──
    handler = PAGE_ROUTES.get(page)
    if handler:
        handler()


if __name__ == "__main__":
    main()
