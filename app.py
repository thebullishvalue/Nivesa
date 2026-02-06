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
from plotly.subplots import make_subplots
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import sqlite3
import uuid
import logging
import os
import re
import json
import sys

# ═══════════════════════════════════════════════════════════════════════
# APPLICATION CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

VERSION = "2.0.8"
BUILD = "2026.02.DESIGN_FIX"
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
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()

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


def db_query(query, params=()):
    """Run SELECT; return DataFrame."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            return pd.read_sql_query(query, conn, params=params)
    except sqlite3.Error as e:
        st.error(f"Query failed: {e}")
        logger.error(f"Query failed: {e}")
        return pd.DataFrame()


def db_execute(query, params=()):
    """Run INSERT/UPDATE/DELETE; return success bool."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
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
    except:
        return "₹0"


def fmt_pct(value, decimals=2):
    try:    return f"{float(value)*100:.{decimals}f}%"
    except: return "0.00%"


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
    except:
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
    except:
        return 0.0


def calc_days_to_maturity(s):
    try:    return max(0, (pd.to_datetime(s) - pd.to_datetime(date.today())).days)
    except: return 0


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
    except:
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

def page_dashboard():
    df, T = get_positions_dataframe()
    if df.empty:
        st.markdown("""<div class='info-box'><h4>Welcome to Nivesa</h4>
        <p>No positions found. Add securities and record transactions to get started.</p></div>""", unsafe_allow_html=True)
        return

    # ── Metric row 1 ──
    st.markdown("""<div class='section'><div class='section-header'>
        <h3 class='section-title'>Portfolio Overview</h3>
        <p class='section-subtitle'>Fixed income snapshot with risk & return metrics</p>
    </div></div>""", unsafe_allow_html=True)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.markdown(f"<div class='metric-card primary'><h4>Total Invested (Cost)</h4><h2>{fmt_inr_short(T['Total Cost Basis'])}</h2><div class='sub-metric'>Face Value: {fmt_inr_short(T['Total Face Value'])}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card info'><h4>Portfolio Yield (WA)</h4><h2>{fmt_pct(T['Weighted YTC'])}</h2><div class='sub-metric'>Nominal: {fmt_pct(T['Weighted Nominal Yield'])}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card warning'><h4>Annual Coupon Income</h4><h2>{fmt_inr_short(T['Total Annual Coupon'])}</h2><div class='sub-metric'>Monthly: ~{fmt_inr_short(T['Total Annual Coupon']/12)}</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='metric-card'><h4>Weighted Duration</h4><h2>{T['Weighted Mac Duration']:.2f}y</h2><div class='sub-metric'>Modified: {T['Weighted Mod Duration']:.2f}y</div></div>", unsafe_allow_html=True)
    c5.markdown(f"<div class='metric-card'><h4>Portfolio Composition</h4><h2>{T['Num Positions']}</h2><div class='sub-metric'>{T['Num Issuers']} issuers · {T['Num Accounts']} accounts</div></div>", unsafe_allow_html=True)

    # ── Tabs ──
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Allocation & Risk", "Positions", "Maturity Ladder", "Cashflow Schedule", "Issuer Detail"])

    # ─── Allocation & Risk ───
    with tab1:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        df['ny_c'] = df['nominal_yield']*df['cost_basis']
        df['ytc_c'] = df['yield_to_cost']*df['cost_basis']

        # ── Row 1: Capital Allocation (Donut + Table) ──
        aa = df.groupby('account')['cost_basis'].sum().sort_values(ascending=False)
        total_aum = T['Total Cost Basis']
        
        if not aa.empty:
            colors_map = {acc: CC[i % len(CC)] for i, acc in enumerate(aa.index)}
            
            tbl_header = ["<b>Account</b>", "<b>Cost Basis</b>", "<b>% AUM</b>"]
            tbl_values = [
                [f"<b>{acc}</b>" for acc in aa.index], # Bold account names
                [fmt_inr_short(x) for x in aa.values],
                [f"{x/total_aum:.1%}" for x in aa.values]
            ]
            
            fig_alloc = make_subplots(
                rows=1, cols=2,
                column_widths=[0.35, 0.65],
                specs=[[{'type': 'domain'}, {'type': 'table'}]],
                horizontal_spacing=0.08
            )
            
            # Donut Chart
            fig_alloc.add_trace(go.Pie(
                labels=aa.index, 
                values=aa.values,
                hole=0.7, # Thinner ring looks more modern
                textinfo='none', # Clean look, rely on hover and table
                hoverinfo='label+value+percent',
                marker=dict(colors=[colors_map[x] for x in aa.index], line=dict(color='#1A1A1A', width=3)),
                showlegend=False
            ), row=1, col=1)
            
            # Table
            fig_alloc.add_trace(go.Table(
                header=dict(
                    values=tbl_header,
                    fill_color='#2A2A2A',
                    align=['left', 'right', 'right'],
                    font=dict(color='#FFC300', size=12, family='Inter'),
                    height=32,
                    line_width=0
                ),
                cells=dict(
                    values=tbl_values,
                    fill_color='rgba(0,0,0,0)',
                    align=['left', 'right', 'right'],
                    font=dict(color='#EAEAEA', size=13, family='Inter'),
                    height=32,
                    line=dict(color='#2A2A2A', width=1)
                )
            ), row=1, col=2)

            # Center Text
            fig_alloc.add_annotation(
                text="AUM", x=0.175, y=0.55, showarrow=False, font=dict(size=12, color='#888')
            )
            fig_alloc.add_annotation(
                text=fmt_inr_short(total_aum), x=0.175, y=0.45, showarrow=False, font=dict(size=16, color='#EAEAEA', weight='bold')
            )

            fig_alloc.update_layout(**CL,
                title=dict(text="Capital Allocation", font=dict(size=15, color='#EAEAEA'), x=0, y=0.98),
                height=320,
                margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_alloc, on_container_width=True)

        # ── Row 2: Portfolio Hierarchy (TreeMap) ──
        sb = df[df['cost_basis'] > 0].copy()
        if not sb.empty:
            fig_tree = px.treemap(
                sb, 
                path=[px.Constant("All Accounts"), 'account', 'issuer'], 
                values='cost_basis',
                color='account',
                color_discrete_map=colors_map if 'colors_map' in locals() else None, 
                color_discrete_sequence=CC
            )
            
            fig_tree.update_traces(
                root_color="#1A1A1A",
                textinfo="label+value+percent entry",
                textfont=dict(family='Inter', size=14),
                marker=dict(
                    line=dict(color='#0F0F0F', width=2),
                    pad=dict(t=5, l=5, r=5, b=5)
                ),
                hovertemplate='<b>%{label}</b><br>Amount: ₹%{value:,.0f}<br>Share: %{percentRoot:.1%}<extra></extra>'
            )
            
            fig_tree.update_layout(**CL,
                title=dict(text="Portfolio Hierarchy (Account → Issuer)", font=dict(size=15, color='#EAEAEA'), x=0, y=0.98),
                height=450,
                margin=dict(l=0, r=0, t=40, b=0),
                uniformtext=dict(minsize=10, mode='hide')
            )
            st.plotly_chart(fig_tree, on_container_width=True)

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("#### Concentration Risk")
        ir = df.groupby('issuer').agg(Cost=('cost_basis','sum'), Face=('position_face_value','sum'),
            NY=('ny_c','sum'), YC=('ytc_c','sum'), Pos=('bond_id','count')).reset_index()
        ir['Wt'] = ir['Cost']/T['Total Cost Basis'] if T['Total Cost Basis']>0 else 0
        ir['NY'] = ir.apply(lambda r: r['NY']/r['Cost'] if r['Cost']>0 else 0, axis=1)
        ir['YC'] = ir.apply(lambda r: r['YC']/r['Cost'] if r['Cost']>0 else 0, axis=1)
        ir = ir.sort_values('Cost', ascending=False)
        
        # Calculate Max Weight for relative scaling
        max_wt = ir['Wt'].max() if not ir.empty and ir['Wt'].max() > 0 else 1.0

        rows = ""
        for _,r in ir.iterrows():
            # Bar width is relative to the largest position in the list
            bar_w_pct = (r['Wt'] / max_wt) * 100
            
            # Color logic remains on absolute weight for risk warning
            wc = '#ef4444' if r['Wt']>.15 else '#f59e0b' if r['Wt']>.10 else '#10b981'
            
            rows += f"<tr><td style='font-weight:600'>{r['issuer']}</td><td>{fmt_inr(r['Cost'])}</td><td>{fmt_inr(r['Face'])}</td><td><div style='display:flex;align-items:center;gap:8px'><div style='width:60px;height:6px;background:#2A2A2A;border-radius:3px;overflow:hidden'><div style='width:{bar_w_pct:.0f}%;height:100%;background:{wc};border-radius:3px'></div></div><span>{r['Wt']:.1%}</span></div></td><td>{fmt_pct(r['NY'])}</td><td>{fmt_pct(r['YC'])}</td><td style='text-align:center'>{int(r['Pos'])}</td></tr>"
        st.markdown(f"<div class='table-container'><table class='table'><thead><tr><th>Issuer</th><th>Cost Basis</th><th>Face Value</th><th>Weight</th><th>Nominal</th><th>YTC</th><th>Pos</th></tr></thead><tbody>{rows}</tbody></table></div>", unsafe_allow_html=True)

    # ─── Positions ───
    with tab2:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        sa = st.selectbox("Filter by Account", ['All']+sorted(df['account'].unique().tolist()), key="pf")
        d = df if sa=='All' else df[df['account']==sa]
        d = d.sort_values('cost_basis', ascending=False)
        rows=""
        for _,p in d.iterrows():
            mb = '<span class="badge badge-below">< 90d</span>' if p['days_to_maturity']<=90 else ('<span class="badge badge-bbb">< 1y</span>' if p['days_to_maturity']<=365 else '')
            rows += f"<tr><td><div style='font-weight:600'>{p['issuer']}</div><div style='font-size:0.75rem;color:#888'>{p['isin']}</div></td><td>{rating_badge(p['credit_rating'])}</td><td>{p['account']}</td><td style='text-align:right'>{int(p['current_units'])}</td><td style='text-align:right'>{fmt_inr(p['cost_basis'])}</td><td style='text-align:right'>{fmt_inr(p['position_face_value'])}</td><td style='text-align:right'>{fmt_pct(p['nominal_yield'])}</td><td style='text-align:right'>{fmt_pct(p['yield_to_cost'])}</td><td style='text-align:right'>{p['macaulay_duration']:.2f}y</td><td style='text-align:right'>{pd.to_datetime(p['maturity_date']).strftime('%d %b %Y')} {mb}</td><td style='text-align:right'>{fmt_inr(p['annual_coupon_income'])}</td></tr>"
        st.markdown(f"<div class='table-container'><table class='table'><thead><tr><th>Security</th><th>Rating</th><th>Acct</th><th>Units</th><th>Cost</th><th>Face</th><th>Coupon</th><th>YTC</th><th>Duration</th><th>Maturity</th><th>Annual Inc</th></tr></thead><tbody>{rows}</tbody></table></div>", unsafe_allow_html=True)
        exp = d[['issuer','isin','account','credit_rating','current_units','cost_basis','position_face_value','nominal_yield','yield_to_cost','macaulay_duration','modified_duration','maturity_date','annual_coupon_income','interest_received','days_to_maturity']].copy()
        exp['maturity_date']=pd.to_datetime(exp['maturity_date']).dt.strftime('%Y-%m-%d')
        st.download_button("EXPORT CSV", exp.to_csv(index=False), "nivesa_positions.csv", "text/csv")

    # ─── Maturity Ladder ───
    with tab3:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        def mb(d):
            if d<=90: return "0-3M"
            if d<=180: return "3-6M"
            if d<=365: return "6-12M"
            if d<=730: return "1-2Y"
            if d<=1095: return "2-3Y"
            if d<=1825: return "3-5Y"
            return "5Y+"
        bo = ["0-3M","3-6M","6-12M","1-2Y","2-3Y","3-5Y","5Y+"]
        df['mb'] = df['days_to_maturity'].apply(mb)
        ba = df.groupby('mb').agg(Cost=('cost_basis','sum'),Face=('position_face_value','sum'),N=('bond_id','count')).reindex(bo).fillna(0)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=ba.index, y=ba['Face'], name='Face Value', marker_color='#FFC300',
            text=[fmt_inr_short(v) for v in ba['Face']], textposition='outside', textfont=dict(size=10,color='#EAEAEA')))
        fig.add_trace(go.Bar(x=ba.index, y=ba['Cost'], name='Cost Basis', marker_color='#06b6d4',
            text=[fmt_inr_short(v) for v in ba['Cost']], textposition='outside', textfont=dict(size=10,color='#EAEAEA')))
        fig.update_layout(**CL, title=dict(text="Maturity Profile",font=dict(size=13,color='#888'),x=0,y=0.97,yanchor='top'), height=420, barmode='group',
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)'), yaxis=dict(gridcolor='rgba(255,255,255,0.05)',title=''),
            legend=dict(orientation='h',yanchor='top',y=-0.1,xanchor='left',x=0,font=dict(size=10),bgcolor='rgba(0,0,0,0)'),
            margin=dict(l=40, r=20, t=65, b=55))
        st.plotly_chart(fig, on_container_width=True)

        rows=""
        for b in bo:
            bd = df[df['mb']==b]
            for _,p in bd.sort_values('days_to_maturity').iterrows():
                rows += f"<tr><td>{b}</td><td style='font-weight:600'>{p['issuer']}</td><td>{p['account']}</td><td style='text-align:right'>{fmt_inr(p['position_face_value'])}</td><td style='text-align:right'>{fmt_pct(p['coupon_rate'])}</td><td style='text-align:right'>{pd.to_datetime(p['maturity_date']).strftime('%d %b %Y')}</td><td style='text-align:right'>{int(p['days_to_maturity'])}d</td></tr>"
        if rows:
            st.markdown(f"<div class='table-container'><table class='table'><thead><tr><th>Bucket</th><th>Issuer</th><th>Acct</th><th>Face Value</th><th>Coupon</th><th>Maturity</th><th>Days Left</th></tr></thead><tbody>{rows}</tbody></table></div>", unsafe_allow_html=True)

    # ─── Cashflow Schedule ───
    with tab4:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        all_cf = []
        for _,p in df.iterrows():
            fvpu = p['position_face_value']/p['current_units'] if p['current_units']>0 else 0
            for cf in generate_cashflow_schedule(fvpu, p['coupon_rate'], p['frequency'], p['maturity_date'], p['current_units']):
                cf['issuer']=p['issuer']; cf['account']=p['account']; all_cf.append(cf)
        if all_cf:
            cdf = pd.DataFrame(all_cf); cdf['date']=pd.to_datetime(cdf['date']); cdf=cdf.sort_values('date')
            cdf['mo']=cdf['date'].dt.to_period('M')
            mcf=cdf.groupby('mo').agg(Coupon=('coupon','sum'),Principal=('principal','sum')).reset_index()
            mcf['ms']=mcf['mo'].astype(str)
            fig=go.Figure()
            fig.add_trace(go.Bar(x=mcf['ms'],y=mcf['Coupon'],name='Coupon',marker_color='#FFC300'))
            fig.add_trace(go.Bar(x=mcf['ms'],y=mcf['Principal'],name='Principal',marker_color='#06b6d4'))
            fig.update_layout(**CL,title=dict(text="Projected Monthly Cashflows",font=dict(size=13,color='#888'),x=0,y=0.97,yanchor='top'),height=420,barmode='stack',
                xaxis=dict(gridcolor='rgba(255,255,255,0.05)',tickangle=-45),yaxis=dict(gridcolor='rgba(255,255,255,0.05)',title=''),
                legend=dict(orientation='h',yanchor='top',y=-0.18,xanchor='left',x=0,font=dict(size=10),bgcolor='rgba(0,0,0,0)'),
                margin=dict(l=40, r=20, t=65, b=70))
            st.plotly_chart(fig, on_container_width=True)

            tc=cdf['coupon'].sum(); tp=cdf['principal'].sum()
            s1,s2,s3=st.columns(3)
            s1.markdown(f"<div class='metric-card'><h4>Future Coupons</h4><h2>{fmt_inr_short(tc)}</h2></div>",unsafe_allow_html=True)
            s2.markdown(f"<div class='metric-card'><h4>Principal Due</h4><h2>{fmt_inr_short(tp)}</h2></div>",unsafe_allow_html=True)
            s3.markdown(f"<div class='metric-card'><h4>Total Future CF</h4><h2>{fmt_inr_short(tc+tp)}</h2></div>",unsafe_allow_html=True)

            n12 = cdf[cdf['date']<=pd.to_datetime(date.today()+timedelta(days=365))]
            if not n12.empty:
                st.markdown("#### Upcoming Cashflows (Next 12 Months)")
                rows=""
                for _,cf in n12.iterrows():
                    rows+=f"<tr><td>{cf['date'].strftime('%d %b %Y')}</td><td style='font-weight:600'>{cf['issuer']}</td><td>{cf['account']}</td><td>{cf['type']}</td><td style='text-align:right'>{fmt_inr(cf['coupon'])}</td><td style='text-align:right'>{fmt_inr(cf['principal']) if cf['principal']>0 else '-'}</td><td style='text-align:right;font-weight:600'>{fmt_inr(cf['total'])}</td></tr>"
                st.markdown(f"<div class='table-container'><table class='table'><thead><tr><th>Date</th><th>Issuer</th><th>Acct</th><th>Type</th><th>Coupon</th><th>Principal</th><th>Total</th></tr></thead><tbody>{rows}</tbody></table></div>",unsafe_allow_html=True)
        else:
            st.info("No future cashflows to project.")

    # ─── Issuer Detail ───
    with tab5:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        idd = df.groupby(['issuer','isin']).agg(Cost=('cost_basis','sum'),Face=('position_face_value','sum'),
            NY=('ny_c','sum'),YC=('ytc_c','sum'),Units=('current_units','sum'),Inc=('annual_coupon_income','sum'))
        idd['Wt']=idd['Cost']/T['Total Cost Basis'] if T['Total Cost Basis']>0 else 0
        idd['NY']=idd.apply(lambda r:r['NY']/r['Cost'] if r['Cost']>0 else 0,axis=1)
        idd['YC']=idd.apply(lambda r:r['YC']/r['Cost'] if r['Cost']>0 else 0,axis=1)
        idd=idd.sort_values('Cost',ascending=False)
        rows=""
        for (iss,isin),r in idd.iterrows():
            rows+=f"<tr><td style='font-weight:600'>{iss}</td><td style='font-size:0.8rem;color:#888'>{isin}</td><td style='text-align:right'>{int(r['Units'])}</td><td style='text-align:right'>{fmt_inr(r['Cost'])}</td><td style='text-align:right'>{fmt_inr(r['Face'])}</td><td style='text-align:right'>{r['Wt']:.1%}</td><td style='text-align:right'>{fmt_pct(r['NY'])}</td><td style='text-align:right'>{fmt_pct(r['YC'])}</td><td style='text-align:right'>{fmt_inr(r['Inc'])}</td></tr>"
        st.markdown(f"<div class='table-container'><table class='table'><thead><tr><th>Issuer</th><th>ISIN</th><th>Units</th><th>Cost</th><th>Face</th><th>Weight</th><th>Nominal</th><th>YTC</th><th>Annual Inc</th></tr></thead><tbody>{rows}</tbody></table></div>",unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# PAGE: ADD SECURITY
# ═══════════════════════════════════════════════════════════════════════

def page_add_security():
    st.markdown("""<div class='section'><div class='section-header'>
        <h3 class='section-title'>Add New Security</h3>
        <p class='section-subtitle'>Register a bond in the securities master before transacting</p>
    </div></div>""", unsafe_allow_html=True)

    with st.form("add_sec"):
        c1,c2=st.columns(2)
        with c1:
            issuer=st.text_input("Issuer Name"); isin=st.text_input("ISIN")
            mat=st.date_input("Maturity Date",min_value=date.today()); freq=st.selectbox("Coupon Frequency",FREQUENCIES)
        with c2:
            cpn=st.number_input("Coupon Rate (%)",0.0,100.0,step=0.01,format="%.2f")
            fv=st.number_input("Face Value (per unit)",min_value=0.0,step=100.0,value=1000.0)
            btype=st.selectbox("Bond Type",BOND_TYPES); cr=st.selectbox("Credit Rating",CREDIT_RATINGS)
        c3,c4=st.columns(2)
        with c3: sector=st.text_input("Sector",value="Financials"); listing=st.selectbox("Listing",["Unlisted","NSE","BSE","Both"])
        with c4: idate=st.date_input("Issue Date (optional)",value=None); dc=st.selectbox("Day Count",DAY_COUNT_CONVENTIONS)
        notes=st.text_area("Notes"); submit=st.form_submit_button("ADD SECURITY")
        if submit:
            if not issuer or not isin: st.error("Issuer and ISIN are required.")
            else:
                bid=str(uuid.uuid4())
                if db_execute("INSERT INTO securities VALUES (?,?,?,?,?,?,?)",(bid,issuer,isin,mat.isoformat(),freq,cpn/100,fv)):
                    db_execute("INSERT INTO security_metadata (bond_id,bond_type,credit_rating,day_count,issue_date,listing,sector,notes) VALUES (?,?,?,?,?,?,?,?)",
                        (bid,btype,cr,dc,idate.isoformat() if idate else None,listing,sector,notes))
                    st.success(f"Security **{issuer}** ({isin}) added!"); logger.info(f"Added {isin}"); st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: EDIT SECURITY
# ═══════════════════════════════════════════════════════════════════════

def page_edit_security():
    st.markdown("""<div class='section'><div class='section-header'>
        <h3 class='section-title'>Edit Security</h3>
        <p class='section-subtitle'>Update security master data and metadata</p>
    </div></div>""", unsafe_allow_html=True)

    secs=db_query("SELECT * FROM securities")
    if secs.empty: st.warning("No securities found."); return
    opts={f"{r['issuer']} — {r['isin']}":r['bond_id'] for _,r in secs.iterrows()}
    sel=st.selectbox("Select Security",opts.keys(),index=None,placeholder="Choose…")
    if not sel: return
    bid=opts[sel]; s=secs[secs['bond_id']==bid].iloc[0]; ensure_metadata(bid)
    m=db_query("SELECT * FROM security_metadata WHERE bond_id=?",(bid,))
    m=m.iloc[0] if not m.empty else None
    tc=db_query("SELECT COUNT(*) as c FROM transactions WHERE bond_id=?",(bid,))['c'].iloc[0]

    with st.form("edit_sec"):
        st.markdown(f"**Editing: {s['issuer']} ({s['isin']})**"); st.text_input("ISIN",value=s['isin'],disabled=True)
        c1,c2=st.columns(2)
        with c1:
            issuer=st.text_input("Issuer",value=s['issuer'])
            mat=st.date_input("Maturity",value=pd.to_datetime(s['maturity_date']).date())
            freq=st.selectbox("Frequency",FREQUENCIES,index=FREQUENCIES.index(s['frequency']))
        with c2:
            cpn=st.number_input("Coupon (%)",0.0,100.0,step=0.01,format="%.2f",value=s['coupon_rate']*100)
            fv=st.number_input("Face Value",step=100.0,value=s['face_value'])
            btype=st.selectbox("Bond Type",BOND_TYPES,index=BOND_TYPES.index(m['bond_type']) if m and m['bond_type'] in BOND_TYPES else 0)
        c3,c4=st.columns(2)
        with c3:
            cr=st.selectbox("Credit Rating",CREDIT_RATINGS,index=CREDIT_RATINGS.index(m['credit_rating']) if m and m['credit_rating'] in CREDIT_RATINGS else len(CREDIT_RATINGS)-1)
            sector=st.text_input("Sector",value=m['sector'] if m else 'Financials')
        with c4:
            listing=st.selectbox("Listing",["Unlisted","NSE","BSE","Both"],index=["Unlisted","NSE","BSE","Both"].index(m['listing']) if m and m['listing'] in ["Unlisted","NSE","BSE","Both"] else 0)
            dc=st.selectbox("Day Count",DAY_COUNT_CONVENTIONS,index=DAY_COUNT_CONVENTIONS.index(m['day_count']) if m and m['day_count'] in DAY_COUNT_CONVENTIONS else 0)
        if tc>0: st.warning(f"⚠️ {tc} transactions exist. Editing face value changes all calculations retroactively.")
        if st.form_submit_button("UPDATE SECURITY"):
            if not issuer: st.error("Issuer required.")
            else:
                db_execute("UPDATE securities SET issuer=?,maturity_date=?,frequency=?,coupon_rate=?,face_value=? WHERE bond_id=?",(issuer,mat.isoformat(),freq,cpn/100,fv,bid))
                db_execute("INSERT OR REPLACE INTO security_metadata (bond_id,bond_type,credit_rating,day_count,listing,sector) VALUES (?,?,?,?,?,?)",(bid,btype,cr,dc,listing,sector))
                st.success(f"**{issuer}** updated!"); logger.info(f"Updated {bid}"); st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: RECORD TRANSACTION
# ═══════════════════════════════════════════════════════════════════════

def page_record_transaction():
    st.markdown("""<div class='section'><div class='section-header'>
        <h3 class='section-title'>Record Transaction</h3>
        <p class='section-subtitle'>Record a Buy, Sell, Interest Receipt, or Principal Repayment</p>
    </div></div>""", unsafe_allow_html=True)

    secs=db_query("SELECT bond_id,issuer,isin FROM securities")
    if secs.empty: st.warning("No securities found."); return
    opts={f"{r['issuer']} — {r['isin']}":r['bond_id'] for _,r in secs.iterrows()}
    sel=st.selectbox("Select Security",opts.keys(),index=None,placeholder="Choose…")
    if not sel: return
    bid=opts[sel]
    ttype=st.selectbox("Transaction Type",TRANSACTION_TYPES)

    ah=pd.Series(dtype='float64')
    if ttype=='Principal_Repayment':
        at=db_query("SELECT account,units FROM transactions WHERE bond_id=?",(bid,))
        if not at.empty: ah=at.groupby('account')['units'].sum()

    with st.form("rec_txn"):
        c1,c2=st.columns(2)
        with c1: account=st.selectbox("Account",ACCOUNTS); tdate=st.date_input("Date",max_value=date.today())
        with c2:
            if ttype in ["Buy","Sell"]:
                units=st.number_input("Units",min_value=1,step=1); price=st.number_input("Price",min_value=0.0,format="%.4f")
                amount=units*price; st.markdown(f"**Amount: {fmt_inr(amount)}**"); adj=False
            elif ttype=='Principal_Repayment':
                cu=ah.get(account,0.0); st.markdown(f"Applies to **{cu}** units in **{account}**")
                amount=st.number_input("Total Amount",min_value=0.0,format="%.2f")
                if cu>0 and amount>0: st.markdown(f"**Per Unit: {fmt_inr(amount/cu)}**")
                adj=st.checkbox("Adjust Face Value",value=True); units=0.0; price=0.0
            else:
                amount=st.number_input("Amount",min_value=0.0,format="%.2f"); units=0.0; price=0.0; adj=False
        notes=st.text_area("Notes")
        if st.form_submit_button("RECORD TRANSACTION"):
            tid=str(uuid.uuid4()); us=-abs(units) if ttype=='Sell' else abs(units)
            apu=0.0
            if ttype=='Principal_Repayment':
                at2=db_query("SELECT units FROM transactions WHERE bond_id=? AND account=?",(bid,account))
                cu2=at2['units'].sum() if not at2.empty else 0.0
                apu=amount/cu2 if cu2>0 else 0.0
            fa=units*price if ttype in ["Buy","Sell"] else amount
            if db_execute("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?)",(tid,bid,account,tdate.isoformat(),ttype,us,price,fa,notes)):
                st.success(f"**{ttype.replace('_',' ')}** recorded!"); logger.info(f"{ttype} {bid}")
                if ttype=='Principal_Repayment' and adj and apu>0:
                    db_execute("UPDATE securities SET face_value=face_value-? WHERE bond_id=?",(apu,bid))
                    st.success(f"Face value adjusted by {fmt_inr(apu)}/unit")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: EDIT TRANSACTION
# ═══════════════════════════════════════════════════════════════════════

def page_edit_transaction():
    st.markdown("""<div class='section'><div class='section-header'>
        <h3 class='section-title'>Edit Transaction</h3>
        <p class='section-subtitle'>Correct or delete an existing transaction entry</p>
    </div></div>""", unsafe_allow_html=True)

    txns=db_query("SELECT t.*,s.issuer,s.isin FROM transactions t JOIN securities s ON t.bond_id=s.bond_id ORDER BY t.trade_date DESC")
    if txns.empty: st.warning("No transactions found."); return
    txns['trade_date']=pd.to_datetime(txns['trade_date']).dt.strftime('%Y-%m-%d')
    opts={f"{r['trade_date']} | {r['transaction_type']} | {r['issuer']} | {fmt_inr(r['amount'])}":r['transaction_id'] for _,r in txns.iterrows()}
    sel=st.selectbox("Select Transaction",opts.keys(),index=None,placeholder="Choose…")
    if not sel: return
    tid=opts[sel]; t=txns[txns['transaction_id']==tid].iloc[0]
    st.markdown('<div class="section-divider"></div>',unsafe_allow_html=True)

    with st.form("edit_txn"):
        st.markdown(f"**Transaction:** `{tid[:12]}…`"); st.text_input("Security",value=f"{t['issuer']} ({t['isin']})",disabled=True)
        try: ai=ACCOUNTS.index(t['account'])
        except: ai=0
        try: ti=TRANSACTION_TYPES.index(t['transaction_type'])
        except: ti=0
        c1,c2=st.columns(2)
        with c1: acct=st.selectbox("Account",ACCOUNTS,index=ai); td=st.date_input("Date",max_value=date.today(),value=pd.to_datetime(t['trade_date']).date()); tt=st.selectbox("Type",TRANSACTION_TYPES,index=ti)
        with c2: u=st.number_input("Units",min_value=0,step=1,value=int(abs(t['units']))); p=st.number_input("Price",min_value=0.0,format="%.4f",value=t['price']); a=st.number_input("Amount",min_value=0.0,format="%.2f",value=t['amount'])
        notes=st.text_area("Notes",value=t['notes'] or '')
        cu,cd=st.columns([3,1])
        with cu: ubtn=st.form_submit_button("UPDATE",use_container_width=True)
        with cd: dbtn=st.form_submit_button("DELETE",use_container_width=True)
        if ubtn:
            if tt in ["Buy","Sell"]: fa,fp,fu=u*p,p,(-abs(u) if tt=='Sell' else abs(u))
            else: fa,fp,fu=a,0.0,0.0
            if db_execute("UPDATE transactions SET account=?,trade_date=?,transaction_type=?,units=?,price=?,amount=?,notes=? WHERE transaction_id=?",(acct,td.isoformat(),tt,fu,fp,fa,notes,tid)):
                st.success("Updated!"); st.rerun()
        if dbtn:
            if db_execute("DELETE FROM transactions WHERE transaction_id=?",(tid,)):
                st.success("Deleted!"); st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: TRANSACTION LEDGER
# ═══════════════════════════════════════════════════════════════════════

def page_view_transactions():
    st.markdown("""<div class='section'><div class='section-header'>
        <h3 class='section-title'>Transaction Ledger</h3>
        <p class='section-subtitle'>Complete audit trail of all portfolio activity</p>
    </div></div>""", unsafe_allow_html=True)

    f1,f2,f3=st.columns(3)
    with f1: fa=st.selectbox("Account",['All']+ACCOUNTS,key="la")
    with f2: ft=st.selectbox("Type",['All']+TRANSACTION_TYPES,key="lt")
    with f3: fs=st.text_input("Search Issuer",key="ls")

    q="SELECT t.trade_date,s.issuer,s.isin,t.account,t.transaction_type,t.units,t.price,t.amount,t.notes FROM transactions t JOIN securities s ON t.bond_id=s.bond_id WHERE 1=1"
    p=[]
    if fa!='All': q+=" AND t.account=?"; p.append(fa)
    if ft!='All': q+=" AND t.transaction_type=?"; p.append(ft)
    if fs: q+=" AND s.issuer LIKE ?"; p.append(f"%{fs}%")
    q+=" ORDER BY t.trade_date DESC"
    ldf=db_query(q,tuple(p))
    if ldf.empty: st.info("No transactions match."); return
    ldf['trade_date']=pd.to_datetime(ldf['trade_date']).dt.strftime('%d %b %Y')

    rows=""
    for _,r in ldf.iterrows():
        tc="positive" if r['transaction_type'] in ['Buy','Interest_Receipt'] else ("negative" if r['transaction_type']=='Sell' else "")
        u_fmt = f"{r['units']:,.0f}" if r['units']!=0 else '-'
        p_fmt = fmt_inr(r['price']) if r['price']!=0 else '-'
        n_fmt = r['notes'] or ''
        rows+=f"<tr><td>{r['trade_date']}</td><td style='font-weight:600'>{r['issuer']}</td><td style='font-size:0.8rem;color:#888'>{r['isin']}</td><td>{r['account']}</td><td class='{tc}'>{r['transaction_type'].replace('_',' ')}</td><td style='text-align:right'>{u_fmt}</td><td style='text-align:right'>{p_fmt}</td><td style='text-align:right;font-weight:600'>{fmt_inr(r['amount'])}</td><td style='font-size:0.8rem;color:#888'>{n_fmt}</td></tr>"
    st.markdown(f"<div class='table-container'><table class='table'><thead><tr><th>Date</th><th>Issuer</th><th>ISIN</th><th>Acct</th><th>Type</th><th>Units</th><th>Price</th><th>Amount</th><th>Notes</th></tr></thead><tbody>{rows}</tbody></table></div>",unsafe_allow_html=True)
    st.download_button("EXPORT LEDGER CSV",ldf.to_csv(index=False),"nivesa_ledger.csv","text/csv")


# ═══════════════════════════════════════════════════════════════════════
# PAGE: SECURITIES MASTER
# ═══════════════════════════════════════════════════════════════════════

def page_securities_master():
    st.markdown("""<div class='section'><div class='section-header'>
        <h3 class='section-title'>Securities Master</h3>
        <p class='section-subtitle'>Complete registry of all bonds in the system</p>
    </div></div>""", unsafe_allow_html=True)

    secs=db_query("SELECT s.*,m.bond_type,m.credit_rating,m.sector,m.listing FROM securities s LEFT JOIN security_metadata m ON s.bond_id=m.bond_id ORDER BY s.issuer")
    if secs.empty: st.info("No securities registered."); return
    rows=""
    for _,s in secs.iterrows():
        d=calc_days_to_maturity(s['maturity_date']); ms=pd.to_datetime(s['maturity_date']).strftime('%d %b %Y')
        r=s.get('credit_rating','Unrated') or 'Unrated'; bt=s.get('bond_type','NCD') or 'NCD'
        rows+=f"<tr><td style='font-weight:600'>{s['issuer']}</td><td style='font-size:0.8rem'>{s['isin']}</td><td>{bt}</td><td>{rating_badge(r)}</td><td style='text-align:right'>{fmt_pct(s['coupon_rate'])}</td><td style='text-align:right'>{fmt_inr(s['face_value'])}</td><td>{s['frequency']}</td><td>{ms}</td><td style='text-align:right'>{d}d</td><td>{s.get('sector','') or ''}</td></tr>"
    st.markdown(f"<div class='table-container'><table class='table'><thead><tr><th>Issuer</th><th>ISIN</th><th>Type</th><th>Rating</th><th>Coupon</th><th>Face Value</th><th>Freq</th><th>Maturity</th><th>Days</th><th>Sector</th></tr></thead><tbody>{rows}</tbody></table></div>",unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    db_init()

    # ── Sidebar ──
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:1rem 0;margin-bottom:1rem;">
            <div style="font-size:1.75rem;font-weight:800;color:#FFC300;">{PRODUCT_NAME.upper()}</div>
            <div style="color:#888;font-size:0.75rem;margin-top:0.25rem;">{PRODUCT_DEVANAGARI} | Bond Portfolio Ledger</div>
        </div>""", unsafe_allow_html=True)
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        st.markdown('<div class="sidebar-title">📊 Navigation</div>', unsafe_allow_html=True)
        page = st.radio("Nav", [
            "📈 Dashboard", "📋 Securities Master", "➕ Add Security",
            "✏️ Edit Security", "💰 Record Transaction",
            "🔧 Edit Transaction", "📖 Transaction Ledger",
        ], label_visibility="collapsed")

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-title">💡 Quick Stats</div>', unsafe_allow_html=True)
        sc=db_query("SELECT COUNT(*) as c FROM securities")['c'].iloc[0]
        tc=db_query("SELECT COUNT(*) as c FROM transactions")['c'].iloc[0]
        st.markdown(f"""<div class='info-box'><p style='font-size:0.8rem;margin:0;color:var(--text-muted);line-height:1.8;'>
            <strong>Securities:</strong> {sc}<br><strong>Transactions:</strong> {tc}<br>
            <strong>Date:</strong> {datetime.now().strftime('%d %b %Y')}</p></div>""", unsafe_allow_html=True)

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown(f"""<div class='info-box'><p style='font-size:0.8rem;margin:0;color:var(--text-muted);line-height:1.5;'>
            <strong>Version:</strong> {VERSION}<br><strong>Build:</strong> {BUILD}<br>
            <strong>Engine:</strong> SQLite + NumPy Financial<br><strong>Product:</strong> {COMPANY}</p></div>""", unsafe_allow_html=True)

    # ── Header ──
    st.markdown(f"""<div class="premium-header">
        <h1>{PRODUCT_NAME.upper()} : Bond Portfolio Ledger</h1>
        <div class="tagline">{TAGLINE}</div>
    </div>""", unsafe_allow_html=True)

    # ── Route ──
    if "Dashboard" in page:          page_dashboard()
    elif "Securities Master" in page: page_securities_master()
    elif "Add Security" in page:      page_add_security()
    elif "Edit Security" in page:     page_edit_security()
    elif "Record Transaction" in page:page_record_transaction()
    elif "Edit Transaction" in page:  page_edit_transaction()
    elif "Transaction Ledger" in page:page_view_transactions()


if __name__ == "__main__":
    main()
