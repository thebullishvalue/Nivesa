# -*- coding: utf-8 -*-
"""
NIVESH (निवेश) - Bond Portfolio Ledger | A Hemrek Capital Product
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Institutional-grade fixed income portfolio management.
Full position lifecycle, cashflow analytics & risk metrics.
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

# --- Constants ---
VERSION = "v2.0.0"
PRODUCT_NAME = "Nivesh"
COMPANY = "Hemrek Capital"

ACCOUNTS = ["REKHA", "HEMANG", "MANTHAN", "HIMA"]
FREQUENCIES = ["Monthly", "Quarterly", "Semi-Annual", "Annual"]
FREQ_MAP = {'Monthly': 12, 'Quarterly': 4, 'Semi-Annual': 2, 'Annual': 1}
BOND_TYPES = ["NCD", "Corporate Bond", "Government Bond", "SDL", "T-Bill", "Tax-Free Bond", "Sovereign Gold Bond", "FD", "Other"]
CREDIT_RATINGS = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B", "C", "D", "Unrated"]
DAY_COUNT_CONVENTIONS = ["30/360", "Actual/365", "Actual/360", "Actual/Actual"]
TRANSACTION_TYPES = ["Buy", "Sell", "Interest_Receipt", "Principal_Repayment"]

# --- Page Config ---
st.set_page_config(
    page_title="NIVESH | Bond Portfolio Ledger",
    layout="wide",
    page_icon="📊",
    initial_sidebar_state="collapsed"
)

# --- Data Directories ---
DATA_DIR = "data"
LOG_DIR = os.path.join(DATA_DIR, "logs")
DB_DIR = os.path.join(DATA_DIR, "db")
DB_FILE = os.path.join(DB_DIR, "portfolio.db")
LOG_FILE = os.path.join(LOG_DIR, "bond_tracker_v2.log")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ═══════════════════════════════════════════════════════════════════════
# HEMREK CAPITAL DESIGN SYSTEM (Swing-family CSS)
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
        
        /* Sidebar toggle button */
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
        
        /* Premium Header */
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
        
        /* Metric Cards */
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
        .metric-card.danger h2 { color: var(--danger-red); }
        .metric-card.warning h2 { color: var(--warning-amber); }
        .metric-card.info h2 { color: var(--info-cyan); }
        .metric-card.neutral h2 { color: var(--neutral); }
        .metric-card.primary h2 { color: var(--primary-color); }

        /* Table Styling */
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

        /* Tab styling */
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

        /* Section styling */
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
        .info-box p { color: var(--text-muted); margin: 0; font-size: 0.9rem; line-height: 1.6; }

        /* Buttons */
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
        
        /* Download button */
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
        
        /* Plotly charts */
        .stPlotlyChart {
            border-radius: 12px;
            background-color: var(--secondary-background-color);
            padding: 10px;
            border: 1px solid var(--border-color);
            box-shadow: 0 0 25px rgba(var(--primary-rgb), 0.1);
        }
        
        /* Form styling */
        .stForm {
            background: var(--bg-card) !important;
            padding: 1.5rem !important;
            border-radius: 12px !important;
            border: 1px solid var(--border-color) !important;
            box-shadow: 0 0 15px rgba(var(--primary-rgb), 0.08) !important;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--background-color); }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--border-light); }
        
        /* Expander */
        .streamlit-expanderHeader {
            background-color: var(--bg-card) !important;
            border-radius: 8px !important;
            color: var(--text-primary) !important;
        }
        
        /* Badge / Pill */
        .badge {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 20px;
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.05em;
        }
        .badge-aaa { background: rgba(16,185,129,0.15); color: #10b981; }
        .badge-aa { background: rgba(6,182,212,0.15); color: #06b6d4; }
        .badge-a { background: rgba(245,158,11,0.15); color: #f59e0b; }
        .badge-bbb { background: rgba(249,115,22,0.15); color: #f97316; }
        .badge-below { background: rgba(239,68,68,0.15); color: #ef4444; }
        .badge-unrated { background: rgba(136,136,136,0.15); color: #888; }
        
        /* Cashflow bar */
        .cf-bar {
            height: 8px;
            border-radius: 4px;
            background: linear-gradient(90deg, var(--primary-color), var(--success-green));
            transition: width 0.5s ease;
        }
    </style>
    """, unsafe_allow_html=True)

load_css()


# ═══════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════

def db_init():
    """Initialize database with institutional-grade schema."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Securities Master
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS securities (
                bond_id TEXT PRIMARY KEY,
                issuer TEXT NOT NULL,
                isin TEXT NOT NULL UNIQUE,
                maturity_date TEXT NOT NULL,
                frequency TEXT NOT NULL,
                coupon_rate REAL NOT NULL,
                face_value REAL NOT NULL
            )
            """)
            
            # Transactions Ledger (immutable source of truth)
            cursor.execute("""
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
            )
            """)
            
            # Extended Security Metadata (new - optional enrichment)
            cursor.execute("""
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
            )
            """)
            
            conn.commit()
            logging.info("Database initialized successfully.")
    except sqlite3.Error as e:
        st.error(f"Database initialization failed: {e}")
        logging.error(f"Database initialization failed: {e}")
        st.stop()

def db_query(query, params=()):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            return pd.read_sql_query(query, conn, params=params)
    except sqlite3.Error as e:
        st.error(f"Database query failed: {e}")
        logging.error(f"Database query failed: {e}")
        return pd.DataFrame()

def db_execute(query, params=()):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return True
    except sqlite3.Error as e:
        st.error(f"Database execution failed: {e}")
        logging.error(f"Database execution failed: {e}")
        return False

def ensure_metadata(bond_id):
    """Ensure metadata row exists for a security."""
    existing = db_query("SELECT bond_id FROM security_metadata WHERE bond_id = ?", (bond_id,))
    if existing.empty:
        db_execute("INSERT OR IGNORE INTO security_metadata (bond_id) VALUES (?)", (bond_id,))


# ═══════════════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ═══════════════════════════════════════════════════════════════════════

def fmt_inr(amount):
    """Format amount in Indian numbering system."""
    try:
        amount = float(amount)
        is_negative = amount < 0
        amount = abs(amount)
        amount_str = f"{amount:,.2f}"
        parts = amount_str.split('.')
        integer_part = parts[0].replace(',', '')
        decimal_part = parts[1] if len(parts) > 1 else '00'
        
        if len(integer_part) <= 3:
            formatted = integer_part
        else:
            formatted = integer_part[-3:]
            remaining = integer_part[:-3]
            while remaining:
                formatted = remaining[-2:] + ',' + formatted
                remaining = remaining[:-2]
        
        prefix = "-₹" if is_negative else "₹"
        return f"{prefix}{formatted}.{decimal_part}"
    except (ValueError, TypeError):
        return "₹0.00"

def fmt_inr_short(amount):
    """Format in lakhs/crores for compact display."""
    try:
        amount = float(amount)
        if abs(amount) >= 1e7:
            return f"₹{amount/1e7:.2f} Cr"
        elif abs(amount) >= 1e5:
            return f"₹{amount/1e5:.2f} L"
        else:
            return fmt_inr(amount)
    except:
        return "₹0"

def fmt_pct(value, decimals=2):
    """Format as percentage."""
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except:
        return "0.00%"

def rating_badge(rating):
    """Return HTML badge for credit rating."""
    if not rating or rating == 'Unrated':
        return f'<span class="badge badge-unrated">{rating or "Unrated"}</span>'
    elif rating.startswith('AAA'):
        return f'<span class="badge badge-aaa">{rating}</span>'
    elif rating.startswith('AA'):
        return f'<span class="badge badge-aa">{rating}</span>'
    elif rating.startswith('A'):
        return f'<span class="badge badge-a">{rating}</span>'
    elif rating.startswith('BBB'):
        return f'<span class="badge badge-bbb">{rating}</span>'
    else:
        return f'<span class="badge badge-below">{rating}</span>'

def color_value(value, fmt_func=fmt_inr):
    """Return colored HTML for positive/negative values."""
    cls = "positive" if value >= 0 else "negative"
    sign = "+" if value > 0 else ""
    return f'<span class="{cls}">{sign}{fmt_func(value)}</span>'


# ═══════════════════════════════════════════════════════════════════════
# FINANCIAL CALCULATIONS ENGINE
# ═══════════════════════════════════════════════════════════════════════

def calc_coupon_payment(face_value, coupon_rate, frequency):
    freq = FREQ_MAP.get(frequency, 1)
    return face_value * coupon_rate / freq

def calc_accrued_interest(face_value, coupon_rate, frequency, last_coupon_date=None):
    """Calculate accrued interest since last coupon date."""
    freq = FREQ_MAP.get(frequency, 1)
    if last_coupon_date is None:
        # Approximate: assume mid-period
        period_days = 365.25 / freq
        days_accrued = period_days / 2
    else:
        days_accrued = (date.today() - last_coupon_date).days
    
    daily_coupon = face_value * coupon_rate / 365.25
    return daily_coupon * days_accrued

def calc_macaulay_duration(face_value, coupon_rate, frequency, maturity_date_str, ytm):
    """Calculate Macaulay Duration."""
    try:
        maturity = pd.to_datetime(maturity_date_str)
        today = pd.to_datetime(date.today())
        years_to_maturity = (maturity - today).days / 365.25
        
        if years_to_maturity <= 0 or ytm <= 0:
            return 0.0
        
        freq = FREQ_MAP.get(frequency, 1)
        nper = int(years_to_maturity * freq)
        if nper <= 0:
            return 0.0
        
        periodic_coupon = face_value * coupon_rate / freq
        periodic_ytm = ytm / freq
        
        pv_weighted_sum = 0.0
        pv_sum = 0.0
        
        for t in range(1, nper + 1):
            time_years = t / freq
            cf = periodic_coupon
            if t == nper:
                cf += face_value
            pv = cf / (1 + periodic_ytm) ** t
            pv_weighted_sum += time_years * pv
            pv_sum += pv
        
        if pv_sum == 0:
            return 0.0
        
        return pv_weighted_sum / pv_sum
    except Exception:
        return 0.0

def calc_modified_duration(macaulay_duration, ytm, frequency):
    """Modified Duration = Macaulay / (1 + ytm/freq)"""
    freq = FREQ_MAP.get(frequency, 1)
    if ytm <= 0:
        return macaulay_duration
    return macaulay_duration / (1 + ytm / freq)

def calc_yield_to_cost(face_value_per_unit, cost_per_unit, coupon_rate, maturity_date_str, frequency, periods_per_year):
    """Calculate Yield to Cost (YTC) using IRR approach."""
    try:
        maturity_date = pd.to_datetime(maturity_date_str)
        today = pd.to_datetime(date.today())
        days_to_maturity = (maturity_date - today).days
        
        if days_to_maturity <= 0 or cost_per_unit <= 0:
            return 0.0

        nper = (days_to_maturity / 365.25) * periods_per_year
        if nper <= 0:
            return 0.0
        
        pmt = calc_coupon_payment(face_value_per_unit, coupon_rate, frequency)
        pv = -cost_per_unit
        fv = face_value_per_unit

        periodic_rate = npf.rate(nper=nper, pmt=pmt, pv=pv, fv=fv)
        
        if np.isnan(periodic_rate):
            return 0.0

        return periodic_rate * periods_per_year
    except Exception:
        return 0.0

def calc_days_to_maturity(maturity_date_str):
    try:
        maturity = pd.to_datetime(maturity_date_str)
        return max(0, (maturity - pd.to_datetime(date.today())).days)
    except:
        return 0

def calc_years_to_maturity(maturity_date_str):
    return calc_days_to_maturity(maturity_date_str) / 365.25

def generate_cashflow_schedule(face_value, coupon_rate, frequency, maturity_date_str, units=1):
    """Generate future cashflow schedule for a bond position."""
    try:
        maturity = pd.to_datetime(maturity_date_str).date()
        today = date.today()
        freq = FREQ_MAP.get(frequency, 1)
        months_per_period = 12 // freq
        
        coupon_per_period = face_value * coupon_rate / freq * units
        
        cashflows = []
        cf_date = maturity
        
        # Walk backwards from maturity to find all future coupon dates
        dates = []
        d = maturity
        while d > today:
            dates.append(d)
            d = d - relativedelta(months=months_per_period)
        
        dates.sort()
        
        for i, d in enumerate(dates):
            cf = coupon_per_period
            if d == maturity:
                cf += face_value * units  # Add principal at maturity
            cashflows.append({
                'date': d,
                'coupon': coupon_per_period,
                'principal': face_value * units if d == maturity else 0,
                'total': cf,
                'type': 'Maturity + Coupon' if d == maturity else 'Coupon'
            })
        
        return cashflows
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════
# POSITIONS ENGINE (Core Analytics)
# ═══════════════════════════════════════════════════════════════════════

def get_positions_dataframe():
    """Build the complete portfolio positions state from all tables."""
    
    securities_df = db_query("SELECT * FROM securities")
    if securities_df.empty:
        return pd.DataFrame(), {}

    securities_df['maturity_date'] = pd.to_datetime(securities_df['maturity_date'])
    
    transactions_df = db_query("SELECT * FROM transactions")
    if transactions_df.empty:
        return pd.DataFrame(), {}
    
    transactions_df['trade_date'] = pd.to_datetime(transactions_df['trade_date'])
    
    # Fetch metadata
    metadata_df = db_query("SELECT * FROM security_metadata")
    
    positions = []
    
    for (bond_id, account), group in transactions_df.groupby(['bond_id', 'account']):
        security_info = securities_df[securities_df['bond_id'] == bond_id]
        if security_info.empty:
            continue
        security_info = security_info.iloc[0]
        
        # Get metadata
        meta = metadata_df[metadata_df['bond_id'] == bond_id].iloc[0] if not metadata_df.empty and bond_id in metadata_df['bond_id'].values else None

        buy_trades = group[group['transaction_type'] == 'Buy']
        sell_trades = group[group['transaction_type'] == 'Sell']
        
        total_buy_units = buy_trades['units'].sum()
        total_buy_cost = buy_trades['amount'].sum()
        total_sell_units = sell_trades['units'].sum() * -1
        total_sell_proceeds = sell_trades['amount'].sum()
        
        current_units = total_buy_units - total_sell_units
        if current_units <= 0:
            continue
            
        avg_buy_price = (total_buy_cost / total_buy_units) if total_buy_units > 0 else 0
        cost_of_sold = total_sell_units * avg_buy_price
        realized_pnl = total_sell_proceeds - cost_of_sold
        
        interest_received = group[group['transaction_type'] == 'Interest_Receipt']['amount'].sum()
        principal_repaid = group[group['transaction_type'] == 'Principal_Repayment']['amount'].sum()
        
        cost_basis = (current_units * avg_buy_price) - principal_repaid
        position_face_value = current_units * security_info['face_value']
        
        # Yields
        nominal_yield = security_info['coupon_rate']
        periods_per_year = FREQ_MAP.get(security_info['frequency'], 1)
        
        cost_basis_per_unit = cost_basis / current_units if current_units > 0 else 0
        fv_per_unit = position_face_value / current_units if current_units > 0 else 0

        ytc = calc_yield_to_cost(
            fv_per_unit, cost_basis_per_unit,
            security_info['coupon_rate'],
            security_info['maturity_date'],
            security_info['frequency'],
            periods_per_year
        )
        
        # Duration calculations
        mac_dur = calc_macaulay_duration(
            fv_per_unit, security_info['coupon_rate'],
            security_info['frequency'], security_info['maturity_date'],
            ytc if ytc > 0 else nominal_yield
        )
        mod_dur = calc_modified_duration(mac_dur, ytc if ytc > 0 else nominal_yield, security_info['frequency'])
        
        annual_coupon = current_units * fv_per_unit * security_info['coupon_rate']
        days_to_mat = calc_days_to_maturity(security_info['maturity_date'])
        years_to_mat = days_to_mat / 365.25
        
        # Accrued interest estimate
        accrued_int = calc_accrued_interest(
            fv_per_unit, security_info['coupon_rate'],
            security_info['frequency']
        ) * current_units
        
        # First buy date for this position
        first_buy_date = buy_trades['trade_date'].min()
        holding_days = (pd.to_datetime(date.today()) - first_buy_date).days if pd.notna(first_buy_date) else 0
        
        # Total income = interest received + accrued
        total_income = interest_received
        
        positions.append({
            'bond_id': bond_id,
            'account': account,
            'issuer': security_info['issuer'],
            'isin': security_info['isin'],
            'maturity_date': security_info['maturity_date'],
            'coupon_rate': security_info['coupon_rate'],
            'frequency': security_info['frequency'],
            'current_units': current_units,
            'cost_basis': cost_basis,
            'avg_buy_price': avg_buy_price,
            'realized_pnl': realized_pnl,
            'interest_received': interest_received,
            'principal_repaid': principal_repaid,
            'position_face_value': position_face_value,
            'annual_coupon_income': annual_coupon,
            'nominal_yield': nominal_yield,
            'yield_to_cost': ytc,
            'macaulay_duration': mac_dur,
            'modified_duration': mod_dur,
            'days_to_maturity': days_to_mat,
            'years_to_maturity': years_to_mat,
            'accrued_interest': accrued_int,
            'holding_days': holding_days,
            'total_income': total_income,
            'bond_type': meta['bond_type'] if meta is not None else 'NCD',
            'credit_rating': meta['credit_rating'] if meta is not None else 'Unrated',
            'sector': meta['sector'] if meta is not None else 'Financials',
        })

    if not positions:
        return pd.DataFrame(), {}
        
    positions_df = pd.DataFrame(positions)
    
    # Portfolio-level aggregates
    total_cost = positions_df['cost_basis'].sum()
    total_face = positions_df['position_face_value'].sum()
    total_annual_coupon = positions_df['annual_coupon_income'].sum()
    total_accrued = positions_df['accrued_interest'].sum()
    total_interest = positions_df['interest_received'].sum()
    total_principal_repaid = positions_df['principal_repaid'].sum()
    
    if total_cost > 0:
        positions_df['weight'] = positions_df['cost_basis'] / total_cost
        w_nominal = (positions_df['nominal_yield'] * positions_df['weight']).sum()
        w_ytc = (positions_df['yield_to_cost'] * positions_df['weight']).sum()
        w_mac_dur = (positions_df['macaulay_duration'] * positions_df['weight']).sum()
        w_mod_dur = (positions_df['modified_duration'] * positions_df['weight']).sum()
        w_years = (positions_df['years_to_maturity'] * positions_df['weight']).sum()
    else:
        positions_df['weight'] = 0
        w_nominal = w_ytc = w_mac_dur = w_mod_dur = w_years = 0.0

    portfolio_yield_on_cost = total_annual_coupon / total_cost if total_cost > 0 else 0
    
    totals = {
        'Total Cost Basis': total_cost,
        'Total Face Value': total_face,
        'Total Annual Coupon': total_annual_coupon,
        'Total Accrued Interest': total_accrued,
        'Total Interest Received': total_interest,
        'Total Principal Repaid': total_principal_repaid,
        'Total Realized PnL': positions_df['realized_pnl'].sum(),
        'Num Positions': len(positions_df),
        'Num Issuers': positions_df['issuer'].nunique(),
        'Num Accounts': positions_df['account'].nunique(),
        'Weighted Nominal Yield': w_nominal,
        'Weighted YTC': w_ytc,
        'Weighted Macaulay Duration': w_mac_dur,
        'Weighted Modified Duration': w_mod_dur,
        'Weighted Avg Maturity': w_years,
        'Portfolio Yield on Cost': portfolio_yield_on_cost,
    }
    
    return positions_df, totals


# ═══════════════════════════════════════════════════════════════════════
# CHART HELPERS (Plotly with Swing theme)
# ═══════════════════════════════════════════════════════════════════════

CHART_LAYOUT = dict(
    template='plotly_dark',
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    font=dict(color="#EAEAEA", family="Inter"),
    margin=dict(l=10, r=10, t=50, b=40),
)

CHART_COLORS = ['#FFC300', '#10b981', '#06b6d4', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1']


# ═══════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

def page_dashboard():
    positions_df, totals = get_positions_dataframe()
    
    if positions_df.empty:
        st.markdown("""
        <div class='info-box'>
            <h4>Welcome to Nivesh</h4>
            <p>No positions found. Add securities and record transactions to get started.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # ─── Top Metric Cards ───
    st.markdown("""
        <div class='section'>
            <div class='section-header'>
                <h3 class='section-title'>Portfolio Overview</h3>
                <p class='section-subtitle'>Fixed income portfolio snapshot with risk & return metrics</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
            <div class='metric-card primary'>
                <h4>Total Invested (Cost)</h4>
                <h2>{fmt_inr_short(totals['Total Cost Basis'])}</h2>
                <div class='sub-metric'>Face Value: {fmt_inr_short(totals['Total Face Value'])}</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div class='metric-card info'>
                <h4>Portfolio Yield (WA)</h4>
                <h2>{fmt_pct(totals['Weighted YTC'])}</h2>
                <div class='sub-metric'>Nominal: {fmt_pct(totals['Weighted Nominal Yield'])}</div>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
            <div class='metric-card warning'>
                <h4>Annual Coupon Income</h4>
                <h2>{fmt_inr_short(totals['Total Annual Coupon'])}</h2>
                <div class='sub-metric'>Monthly: ~{fmt_inr_short(totals['Total Annual Coupon']/12)}</div>
            </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
            <div class='metric-card'>
                <h4>Weighted Duration</h4>
                <h2>{totals['Weighted Macaulay Duration']:.2f}y</h2>
                <div class='sub-metric'>Modified: {totals['Weighted Modified Duration']:.2f}y</div>
            </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown(f"""
            <div class='metric-card'>
                <h4>Portfolio Composition</h4>
                <h2>{totals['Num Positions']}</h2>
                <div class='sub-metric'>{totals['Num Issuers']} issuers · {totals['Num Accounts']} accounts</div>
            </div>
        """, unsafe_allow_html=True)
    
    # ─── Second row: Income stats ───
    col6, col7, col8, col9, col10 = st.columns(5)
    with col6:
        st.markdown(f"""
            <div class='metric-card success'>
                <h4>Total Interest Received</h4>
                <h2>{fmt_inr_short(totals['Total Interest Received'])}</h2>
                <div class='sub-metric'>Lifetime cashflows</div>
            </div>
        """, unsafe_allow_html=True)
    with col7:
        st.markdown(f"""
            <div class='metric-card'>
                <h4>Principal Repaid</h4>
                <h2>{fmt_inr_short(totals['Total Principal Repaid'])}</h2>
                <div class='sub-metric'>Capital returned</div>
            </div>
        """, unsafe_allow_html=True)
    with col8:
        st.markdown(f"""
            <div class='metric-card'>
                <h4>Accrued Interest</h4>
                <h2>{fmt_inr_short(totals['Total Accrued Interest'])}</h2>
                <div class='sub-metric'>Estimated unreceived</div>
            </div>
        """, unsafe_allow_html=True)
    with col9:
        pnl = totals['Total Realized PnL']
        pnl_cls = 'success' if pnl >= 0 else 'danger'
        st.markdown(f"""
            <div class='metric-card {pnl_cls}'>
                <h4>Realized P&L</h4>
                <h2>{"+" if pnl > 0 else ""}{fmt_inr_short(pnl)}</h2>
                <div class='sub-metric'>From sold positions</div>
            </div>
        """, unsafe_allow_html=True)
    with col10:
        st.markdown(f"""
            <div class='metric-card'>
                <h4>Avg Maturity</h4>
                <h2>{totals['Weighted Avg Maturity']:.1f}y</h2>
                <div class='sub-metric'>Weighted average</div>
            </div>
        """, unsafe_allow_html=True)
    
    # ─── Dashboard Tabs ───
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Allocation & Risk", "Positions", "Maturity Ladder",
        "Cashflow Schedule", "Issuer Detail"
    ])
    
    # ── TAB 1: Allocation & Risk ──
    with tab1:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        ch1, ch2 = st.columns(2)
        
        with ch1:
            # Issuer concentration
            issuer_alloc = positions_df.groupby('issuer')['cost_basis'].sum().sort_values(ascending=False)
            fig_issuer = go.Figure(data=[go.Pie(
                labels=issuer_alloc.index,
                values=issuer_alloc.values,
                hole=0.55,
                marker=dict(colors=CHART_COLORS[:len(issuer_alloc)]),
                textinfo='label+percent',
                textfont=dict(size=10, color='#EAEAEA'),
                hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<br>%{percent}<extra></extra>"
            )])
            fig_issuer.update_layout(
                **CHART_LAYOUT,
                title=dict(text="Issuer Concentration", font=dict(size=12, color='#888888'), x=0),
                height=350,
                showlegend=False,
            )
            st.plotly_chart(fig_issuer, use_container_width=True)
        
        with ch2:
            # Account allocation
            acct_alloc = positions_df.groupby('account')['cost_basis'].sum().sort_values(ascending=False)
            fig_acct = go.Figure(data=[go.Bar(
                x=acct_alloc.index,
                y=acct_alloc.values,
                marker_color=CHART_COLORS[:len(acct_alloc)],
                text=[fmt_inr_short(v) for v in acct_alloc.values],
                textposition='outside',
                textfont=dict(size=10, color='#EAEAEA'),
                hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"
            )])
            fig_acct.update_layout(
                **CHART_LAYOUT,
                title=dict(text="Account-wise Allocation", font=dict(size=12, color='#888888'), x=0),
                height=350,
                showlegend=False,
                xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
                yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title=''),
            )
            st.plotly_chart(fig_acct, use_container_width=True)
        
        ch3, ch4 = st.columns(2)
        
        with ch3:
            # Credit quality distribution
            rating_alloc = positions_df.groupby('credit_rating')['cost_basis'].sum().sort_values(ascending=False)
            rating_colors = {
                'AAA': '#10b981', 'AA+': '#14b8a6', 'AA': '#06b6d4', 'AA-': '#0ea5e9',
                'A+': '#f59e0b', 'A': '#f97316', 'A-': '#fb923c',
                'BBB+': '#ef4444', 'BBB': '#dc2626', 'Unrated': '#888888'
            }
            colors = [rating_colors.get(r, '#888888') for r in rating_alloc.index]
            
            fig_rating = go.Figure(data=[go.Bar(
                x=rating_alloc.index,
                y=rating_alloc.values,
                marker_color=colors,
                text=[fmt_inr_short(v) for v in rating_alloc.values],
                textposition='outside',
                textfont=dict(size=10, color='#EAEAEA'),
                hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"
            )])
            fig_rating.update_layout(
                **CHART_LAYOUT,
                title=dict(text="Credit Quality Distribution", font=dict(size=12, color='#888888'), x=0),
                height=350,
                showlegend=False,
                xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
                yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title=''),
            )
            st.plotly_chart(fig_rating, use_container_width=True)
        
        with ch4:
            # Yield vs Duration scatter
            fig_scatter = go.Figure()
            for acct in positions_df['account'].unique():
                acct_data = positions_df[positions_df['account'] == acct]
                fig_scatter.add_trace(go.Scatter(
                    x=acct_data['modified_duration'],
                    y=acct_data['yield_to_cost'] * 100,
                    mode='markers',
                    name=acct,
                    marker=dict(
                        size=acct_data['cost_basis'] / positions_df['cost_basis'].max() * 30 + 8,
                        opacity=0.8,
                    ),
                    text=acct_data['issuer'],
                    hovertemplate="<b>%{text}</b><br>Duration: %{x:.2f}y<br>YTC: %{y:.2f}%<br>Account: " + acct + "<extra></extra>"
                ))
            fig_scatter.update_layout(
                **CHART_LAYOUT,
                title=dict(text="Yield vs Duration (bubble = size of position)", font=dict(size=12, color='#888888'), x=0),
                height=350,
                xaxis=dict(title='Modified Duration (years)', gridcolor='rgba(255,255,255,0.05)'),
                yaxis=dict(title='Yield to Cost (%)', gridcolor='rgba(255,255,255,0.05)'),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, font=dict(size=10)),
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        
        # Concentration risk table
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("#### Concentration Risk")
        
        # Compute yield components for weighted averages
        positions_df['ny_comp'] = positions_df['nominal_yield'] * positions_df['cost_basis']
        positions_df['ytc_comp'] = positions_df['yield_to_cost'] * positions_df['cost_basis']
        
        issuer_risk = positions_df.groupby('issuer').agg(
            Cost=('cost_basis', 'sum'),
            Face=('position_face_value', 'sum'),
            NY_Comp=('ny_comp', 'sum'),
            YTC_Comp=('ytc_comp', 'sum'),
            Positions=('bond_id', 'count'),
        ).reset_index()
        
        issuer_risk['Weight'] = issuer_risk['Cost'] / totals['Total Cost Basis'] if totals['Total Cost Basis'] > 0 else 0
        issuer_risk['WA Nominal'] = issuer_risk.apply(lambda r: r['NY_Comp']/r['Cost'] if r['Cost'] > 0 else 0, axis=1)
        issuer_risk['WA YTC'] = issuer_risk.apply(lambda r: r['YTC_Comp']/r['Cost'] if r['Cost'] > 0 else 0, axis=1)
        issuer_risk = issuer_risk.sort_values('Cost', ascending=False)
        
        # Build HTML table
        rows_html = ""
        for _, r in issuer_risk.iterrows():
            wt = r['Weight']
            wt_bar_color = '#ef4444' if wt > 0.25 else '#f59e0b' if wt > 0.15 else '#10b981'
            rows_html += f"""
            <tr>
                <td style='font-weight:600;'>{r['issuer']}</td>
                <td>{fmt_inr(r['Cost'])}</td>
                <td>{fmt_inr(r['Face'])}</td>
                <td>
                    <div style='display:flex; align-items:center; gap:8px;'>
                        <div style='width:60px; height:6px; background:#2A2A2A; border-radius:3px; overflow:hidden;'>
                            <div style='width:{wt*100:.0f}%; height:100%; background:{wt_bar_color}; border-radius:3px;'></div>
                        </div>
                        <span>{wt:.1%}</span>
                    </div>
                </td>
                <td>{fmt_pct(r['WA Nominal'])}</td>
                <td>{fmt_pct(r['WA YTC'])}</td>
                <td style='text-align:center;'>{int(r['Positions'])}</td>
            </tr>
            """
        
        st.markdown(f"""
            <div class='table-container'>
                <table class='table'>
                    <thead>
                        <tr>
                            <th>Issuer</th><th>Cost Basis</th><th>Face Value</th>
                            <th>Weight</th><th>Nominal Yield</th><th>Yield to Cost</th><th>Positions</th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
        """, unsafe_allow_html=True)
    
    # ── TAB 2: All Positions ──
    with tab2:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        # Account filter
        accts = ['All'] + sorted(positions_df['account'].unique().tolist())
        sel_acct = st.selectbox("Filter by Account", accts, key="pos_acct_filter")
        
        disp = positions_df.copy()
        if sel_acct != 'All':
            disp = disp[disp['account'] == sel_acct]
        
        disp = disp.sort_values('cost_basis', ascending=False)
        
        rows_html = ""
        for _, p in disp.iterrows():
            ytc_cls = "positive" if p['yield_to_cost'] > 0 else ""
            mat_badge = ""
            if p['days_to_maturity'] <= 90:
                mat_badge = '<span class="badge badge-below">< 90d</span>'
            elif p['days_to_maturity'] <= 365:
                mat_badge = '<span class="badge badge-bbb">< 1y</span>'
            
            rows_html += f"""
            <tr>
                <td>
                    <div style='font-weight:600;'>{p['issuer']}</div>
                    <div style='font-size:0.75rem; color:#888;'>{p['isin']}</div>
                </td>
                <td>{rating_badge(p['credit_rating'])}</td>
                <td>{p['account']}</td>
                <td style='text-align:right;'>{int(p['current_units'])}</td>
                <td style='text-align:right;'>{fmt_inr(p['cost_basis'])}</td>
                <td style='text-align:right;'>{fmt_inr(p['position_face_value'])}</td>
                <td class='{ytc_cls}' style='text-align:right;'>{fmt_pct(p['nominal_yield'])}</td>
                <td class='{ytc_cls}' style='text-align:right;'>{fmt_pct(p['yield_to_cost'])}</td>
                <td style='text-align:right;'>{p['macaulay_duration']:.2f}y</td>
                <td style='text-align:right;'>
                    {pd.to_datetime(p['maturity_date']).strftime('%d %b %Y')}
                    {mat_badge}
                </td>
                <td style='text-align:right;'>{fmt_inr(p['annual_coupon_income'])}</td>
            </tr>
            """
        
        st.markdown(f"""
            <div class='table-container'>
                <table class='table'>
                    <thead><tr>
                        <th>Security</th><th>Rating</th><th>Account</th><th>Units</th>
                        <th>Cost Basis</th><th>Face Value</th><th>Coupon</th><th>YTC</th>
                        <th>Duration</th><th>Maturity</th><th>Annual Income</th>
                    </tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
        """, unsafe_allow_html=True)
        
        # Download
        export_df = disp[['issuer','isin','account','credit_rating','current_units','cost_basis',
                          'position_face_value','nominal_yield','yield_to_cost',
                          'macaulay_duration','modified_duration','maturity_date','annual_coupon_income',
                          'interest_received','days_to_maturity']].copy()
        export_df['maturity_date'] = pd.to_datetime(export_df['maturity_date']).dt.strftime('%Y-%m-%d')
        export_df['nominal_yield'] = export_df['nominal_yield'].apply(lambda x: f"{x*100:.2f}%")
        export_df['yield_to_cost'] = export_df['yield_to_cost'].apply(lambda x: f"{x*100:.2f}%")
        
        csv = export_df.to_csv(index=False)
        st.download_button("EXPORT POSITIONS CSV", csv, "nivesh_positions.csv", "text/csv")
    
    # ── TAB 3: Maturity Ladder ──
    with tab3:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        # Bucket by maturity
        def maturity_bucket(days):
            if days <= 90: return "0-3 Months"
            elif days <= 180: return "3-6 Months"
            elif days <= 365: return "6-12 Months"
            elif days <= 730: return "1-2 Years"
            elif days <= 1095: return "2-3 Years"
            elif days <= 1825: return "3-5 Years"
            else: return "5+ Years"
        
        positions_df['maturity_bucket'] = positions_df['days_to_maturity'].apply(maturity_bucket)
        bucket_order = ["0-3 Months", "3-6 Months", "6-12 Months", "1-2 Years", "2-3 Years", "3-5 Years", "5+ Years"]
        
        bucket_agg = positions_df.groupby('maturity_bucket').agg(
            Cost=('cost_basis', 'sum'),
            Face=('position_face_value', 'sum'),
            Count=('bond_id', 'count')
        ).reindex(bucket_order).fillna(0)
        
        fig_ladder = go.Figure()
        fig_ladder.add_trace(go.Bar(
            x=bucket_agg.index,
            y=bucket_agg['Face'],
            name='Face Value',
            marker_color='#FFC300',
            text=[fmt_inr_short(v) for v in bucket_agg['Face']],
            textposition='outside',
            textfont=dict(size=10, color='#EAEAEA'),
            hovertemplate="<b>%{x}</b><br>Face: ₹%{y:,.0f}<extra></extra>"
        ))
        fig_ladder.add_trace(go.Bar(
            x=bucket_agg.index,
            y=bucket_agg['Cost'],
            name='Cost Basis',
            marker_color='#06b6d4',
            text=[fmt_inr_short(v) for v in bucket_agg['Cost']],
            textposition='outside',
            textfont=dict(size=10, color='#EAEAEA'),
            hovertemplate="<b>%{x}</b><br>Cost: ₹%{y:,.0f}<extra></extra>"
        ))
        fig_ladder.update_layout(
            **CHART_LAYOUT,
            title=dict(text="Maturity Profile", font=dict(size=12, color='#888888'), x=0),
            height=400,
            barmode='group',
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title=''),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, font=dict(size=10)),
        )
        st.plotly_chart(fig_ladder, use_container_width=True)
        
        # Maturity detail table
        rows_html = ""
        for bucket in bucket_order:
            bdata = positions_df[positions_df['maturity_bucket'] == bucket]
            if bdata.empty:
                continue
            for _, p in bdata.sort_values('days_to_maturity').iterrows():
                rows_html += f"""
                <tr>
                    <td>{bucket}</td>
                    <td style='font-weight:600;'>{p['issuer']}</td>
                    <td>{p['account']}</td>
                    <td style='text-align:right;'>{fmt_inr(p['position_face_value'])}</td>
                    <td style='text-align:right;'>{fmt_pct(p['coupon_rate'])}</td>
                    <td style='text-align:right;'>{pd.to_datetime(p['maturity_date']).strftime('%d %b %Y')}</td>
                    <td style='text-align:right;'>{int(p['days_to_maturity'])}d</td>
                </tr>
                """
        
        st.markdown(f"""
            <div class='table-container'>
                <table class='table'>
                    <thead><tr>
                        <th>Bucket</th><th>Issuer</th><th>Account</th>
                        <th>Face Value</th><th>Coupon</th><th>Maturity</th><th>Days Left</th>
                    </tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
        """, unsafe_allow_html=True)
    
    # ── TAB 4: Cashflow Schedule ──
    with tab4:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        all_cashflows = []
        for _, p in positions_df.iterrows():
            cfs = generate_cashflow_schedule(
                p['position_face_value'] / p['current_units'] if p['current_units'] > 0 else 0,
                p['coupon_rate'], p['frequency'], p['maturity_date'], p['current_units']
            )
            for cf in cfs:
                cf['issuer'] = p['issuer']
                cf['account'] = p['account']
                all_cashflows.append(cf)
        
        if all_cashflows:
            cf_df = pd.DataFrame(all_cashflows)
            cf_df['date'] = pd.to_datetime(cf_df['date'])
            cf_df = cf_df.sort_values('date')
            
            # Monthly aggregation for chart
            cf_df['month'] = cf_df['date'].dt.to_period('M')
            monthly_cf = cf_df.groupby('month').agg(
                Coupon=('coupon', 'sum'),
                Principal=('principal', 'sum'),
                Total=('total', 'sum')
            ).reset_index()
            monthly_cf['month_str'] = monthly_cf['month'].astype(str)
            
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Bar(
                x=monthly_cf['month_str'], y=monthly_cf['Coupon'],
                name='Coupon', marker_color='#FFC300',
                hovertemplate="<b>%{x}</b><br>Coupon: ₹%{y:,.0f}<extra></extra>"
            ))
            fig_cf.add_trace(go.Bar(
                x=monthly_cf['month_str'], y=monthly_cf['Principal'],
                name='Principal', marker_color='#06b6d4',
                hovertemplate="<b>%{x}</b><br>Principal: ₹%{y:,.0f}<extra></extra>"
            ))
            fig_cf.update_layout(
                **CHART_LAYOUT,
                title=dict(text="Projected Monthly Cashflows", font=dict(size=12, color='#888888'), x=0),
                height=400,
                barmode='stack',
                xaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickangle=-45),
                yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title=''),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, font=dict(size=10)),
            )
            st.plotly_chart(fig_cf, use_container_width=True)
            
            # Summary stats
            total_future_coupons = cf_df['coupon'].sum()
            total_future_principal = cf_df['principal'].sum()
            
            scol1, scol2, scol3 = st.columns(3)
            with scol1:
                st.markdown(f"""<div class='metric-card'><h4>Total Future Coupons</h4>
                <h2>{fmt_inr_short(total_future_coupons)}</h2></div>""", unsafe_allow_html=True)
            with scol2:
                st.markdown(f"""<div class='metric-card'><h4>Total Principal Due</h4>
                <h2>{fmt_inr_short(total_future_principal)}</h2></div>""", unsafe_allow_html=True)
            with scol3:
                st.markdown(f"""<div class='metric-card'><h4>Total Future Cashflows</h4>
                <h2>{fmt_inr_short(total_future_coupons + total_future_principal)}</h2></div>""", unsafe_allow_html=True)
            
            # Detailed schedule (next 12 months)
            next_12m = cf_df[cf_df['date'] <= pd.to_datetime(date.today() + timedelta(days=365))]
            if not next_12m.empty:
                st.markdown("#### Upcoming Cashflows (Next 12 Months)")
                rows_html = ""
                for _, cf in next_12m.iterrows():
                    rows_html += f"""
                    <tr>
                        <td>{cf['date'].strftime('%d %b %Y')}</td>
                        <td style='font-weight:600;'>{cf['issuer']}</td>
                        <td>{cf['account']}</td>
                        <td>{cf['type']}</td>
                        <td style='text-align:right;'>{fmt_inr(cf['coupon'])}</td>
                        <td style='text-align:right;'>{fmt_inr(cf['principal']) if cf['principal'] > 0 else '-'}</td>
                        <td style='text-align:right; font-weight:600;'>{fmt_inr(cf['total'])}</td>
                    </tr>
                    """
                st.markdown(f"""
                    <div class='table-container'>
                        <table class='table'>
                            <thead><tr>
                                <th>Date</th><th>Issuer</th><th>Account</th><th>Type</th>
                                <th>Coupon</th><th>Principal</th><th>Total</th>
                            </tr></thead>
                            <tbody>{rows_html}</tbody>
                        </table>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No future cashflows to project.")
    
    # ── TAB 5: Issuer Detail ──
    with tab5:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        issuer_detail = positions_df.groupby(['issuer', 'isin']).agg(
            Cost=('cost_basis', 'sum'),
            Face=('position_face_value', 'sum'),
            NY_Comp=('ny_comp', 'sum'),
            YTC_Comp=('ytc_comp', 'sum'),
            Units=('current_units', 'sum'),
            Income=('annual_coupon_income', 'sum'),
        )
        
        issuer_detail['Weight'] = issuer_detail['Cost'] / totals['Total Cost Basis'] if totals['Total Cost Basis'] > 0 else 0
        issuer_detail['Nominal'] = issuer_detail.apply(lambda r: r['NY_Comp']/r['Cost'] if r['Cost'] > 0 else 0, axis=1)
        issuer_detail['YTC'] = issuer_detail.apply(lambda r: r['YTC_Comp']/r['Cost'] if r['Cost'] > 0 else 0, axis=1)
        issuer_detail = issuer_detail.sort_values('Cost', ascending=False)
        
        rows_html = ""
        for (issuer, isin), r in issuer_detail.iterrows():
            rows_html += f"""
            <tr>
                <td style='font-weight:600;'>{issuer}</td>
                <td style='font-size:0.8rem; color:#888;'>{isin}</td>
                <td style='text-align:right;'>{int(r['Units'])}</td>
                <td style='text-align:right;'>{fmt_inr(r['Cost'])}</td>
                <td style='text-align:right;'>{fmt_inr(r['Face'])}</td>
                <td style='text-align:right;'>{r['Weight']:.1%}</td>
                <td style='text-align:right;'>{fmt_pct(r['Nominal'])}</td>
                <td style='text-align:right;'>{fmt_pct(r['YTC'])}</td>
                <td style='text-align:right;'>{fmt_inr(r['Income'])}</td>
            </tr>
            """
        
        st.markdown(f"""
            <div class='table-container'>
                <table class='table'>
                    <thead><tr>
                        <th>Issuer</th><th>ISIN</th><th>Units</th>
                        <th>Cost Basis</th><th>Face Value</th><th>Weight</th>
                        <th>Nominal</th><th>YTC</th><th>Annual Income</th>
                    </tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# PAGE: ADD SECURITY
# ═══════════════════════════════════════════════════════════════════════

def page_add_security():
    st.markdown("""
        <div class='section'>
            <div class='section-header'>
                <h3 class='section-title'>Add New Security</h3>
                <p class='section-subtitle'>Register a bond in the securities master before transacting</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    with st.form("add_security_form"):
        col1, col2 = st.columns(2)
        with col1:
            issuer = st.text_input("Issuer Name")
            isin = st.text_input("ISIN")
            maturity_date = st.date_input("Maturity Date", min_value=date.today())
            frequency = st.selectbox("Coupon Frequency", FREQUENCIES)
        with col2:
            coupon_rate_pct = st.number_input("Coupon Rate (%)", min_value=0.0, max_value=100.0, step=0.01, format="%.2f")
            face_value = st.number_input("Face Value (per unit)", min_value=0.0, step=100.0, value=1000.0)
            bond_type = st.selectbox("Bond Type", BOND_TYPES)
            credit_rating = st.selectbox("Credit Rating", CREDIT_RATINGS)
        
        col3, col4 = st.columns(2)
        with col3:
            sector = st.text_input("Sector", value="Financials")
            listing = st.selectbox("Listing", ["Unlisted", "NSE", "BSE", "Both"])
        with col4:
            issue_date = st.date_input("Issue Date (optional)", value=None)
            day_count = st.selectbox("Day Count Convention", DAY_COUNT_CONVENTIONS)
        
        notes = st.text_area("Notes")
        submit = st.form_submit_button("ADD SECURITY")
        
        if submit:
            if not issuer or not isin:
                st.error("Issuer and ISIN are required.")
            else:
                bond_id = str(uuid.uuid4())
                coupon_rate = coupon_rate_pct / 100.0
                
                success = db_execute(
                    "INSERT INTO securities (bond_id, issuer, isin, maturity_date, frequency, coupon_rate, face_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (bond_id, issuer, isin, maturity_date.isoformat(), frequency, coupon_rate, face_value)
                )
                if success:
                    db_execute(
                        """INSERT INTO security_metadata 
                           (bond_id, bond_type, credit_rating, day_count, issue_date, listing, sector, notes) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (bond_id, bond_type, credit_rating, day_count,
                         issue_date.isoformat() if issue_date else None,
                         listing, sector, notes)
                    )
                    st.success(f"Security **{issuer}** ({isin}) added successfully!")
                    logging.info(f"Added security {isin}")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: EDIT SECURITY
# ═══════════════════════════════════════════════════════════════════════

def page_edit_security():
    st.markdown("""
        <div class='section'>
            <div class='section-header'>
                <h3 class='section-title'>Edit Security</h3>
                <p class='section-subtitle'>Update security master data and metadata</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    securities_df = db_query("SELECT * FROM securities")
    if securities_df.empty:
        st.warning("No securities found. Please add a security first.")
        return

    options = {f"{r['issuer']} — {r['isin']}": r['bond_id'] for _, r in securities_df.iterrows()}
    selected = st.selectbox("Select Security", options.keys(), index=None, placeholder="Choose a security...")
    
    if not selected:
        return
        
    bond_id = options[selected]
    sec = securities_df[securities_df['bond_id'] == bond_id].iloc[0]
    
    # Ensure metadata exists
    ensure_metadata(bond_id)
    meta = db_query("SELECT * FROM security_metadata WHERE bond_id = ?", (bond_id,))
    meta = meta.iloc[0] if not meta.empty else None
    
    # Transaction count warning
    count_df = db_query("SELECT COUNT(*) as count FROM transactions WHERE bond_id = ?", (bond_id,))
    txn_count = count_df['count'].iloc[0] if not count_df.empty else 0

    with st.form("edit_security_form"):
        st.markdown(f"**Editing: {sec['issuer']} ({sec['isin']})**")
        st.text_input("ISIN", value=sec['isin'], disabled=True)
        
        col1, col2 = st.columns(2)
        with col1:
            issuer = st.text_input("Issuer", value=sec['issuer'])
            maturity_date = st.date_input("Maturity Date", value=pd.to_datetime(sec['maturity_date']).date())
            frequency = st.selectbox("Frequency", FREQUENCIES,
                                     index=FREQUENCIES.index(sec['frequency']))
        with col2:
            coupon_rate_pct = st.number_input("Coupon Rate (%)", min_value=0.0, max_value=100.0,
                                              step=0.01, format="%.2f", value=sec['coupon_rate'] * 100.0)
            face_value = st.number_input("Face Value (per unit)", step=100.0, value=sec['face_value'])
            bond_type = st.selectbox("Bond Type", BOND_TYPES,
                                     index=BOND_TYPES.index(meta['bond_type']) if meta is not None and meta['bond_type'] in BOND_TYPES else 0)
        
        col3, col4 = st.columns(2)
        with col3:
            credit_rating = st.selectbox("Credit Rating", CREDIT_RATINGS,
                                         index=CREDIT_RATINGS.index(meta['credit_rating']) if meta is not None and meta['credit_rating'] in CREDIT_RATINGS else len(CREDIT_RATINGS)-1)
            sector = st.text_input("Sector", value=meta['sector'] if meta is not None else 'Financials')
        with col4:
            listing = st.selectbox("Listing", ["Unlisted", "NSE", "BSE", "Both"],
                                   index=["Unlisted", "NSE", "BSE", "Both"].index(meta['listing']) if meta is not None and meta['listing'] in ["Unlisted", "NSE", "BSE", "Both"] else 0)
            day_count = st.selectbox("Day Count", DAY_COUNT_CONVENTIONS,
                                     index=DAY_COUNT_CONVENTIONS.index(meta['day_count']) if meta is not None and meta['day_count'] in DAY_COUNT_CONVENTIONS else 0)
        
        if txn_count > 0:
            st.warning(f"⚠️ This security has {txn_count} transactions. Editing face value will retroactively change calculations.")
        
        submit = st.form_submit_button("UPDATE SECURITY")
        
        if submit:
            if not issuer:
                st.error("Issuer is required.")
            else:
                coupon_rate = coupon_rate_pct / 100.0
                db_execute(
                    "UPDATE securities SET issuer=?, maturity_date=?, frequency=?, coupon_rate=?, face_value=? WHERE bond_id=?",
                    (issuer, maturity_date.isoformat(), frequency, coupon_rate, face_value, bond_id)
                )
                db_execute(
                    """INSERT OR REPLACE INTO security_metadata 
                       (bond_id, bond_type, credit_rating, day_count, listing, sector) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (bond_id, bond_type, credit_rating, day_count, listing, sector)
                )
                st.success(f"Security **{issuer}** updated successfully!")
                logging.info(f"Updated security {bond_id}")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: RECORD TRANSACTION
# ═══════════════════════════════════════════════════════════════════════

def page_record_transaction():
    st.markdown("""
        <div class='section'>
            <div class='section-header'>
                <h3 class='section-title'>Record Transaction</h3>
                <p class='section-subtitle'>Record a Buy, Sell, Interest Receipt, or Principal Repayment</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    securities_df = db_query("SELECT bond_id, issuer, isin FROM securities")
    if securities_df.empty:
        st.warning("No securities found. Please add a security first.")
        return

    sec_options = {f"{r['issuer']} — {r['isin']}": r['bond_id'] for _, r in securities_df.iterrows()}
    selected = st.selectbox("Select Security", sec_options.keys(), index=None, placeholder="Choose a security...")
    
    if not selected:
        return
        
    bond_id = sec_options[selected]
    transaction_type = st.selectbox("Transaction Type", TRANSACTION_TYPES)
    
    # Pre-fetch holdings for Principal Repayment
    account_holdings = pd.Series(dtype='float64')
    if transaction_type == 'Principal_Repayment':
        all_txns = db_query("SELECT account, units FROM transactions WHERE bond_id = ?", (bond_id,))
        if not all_txns.empty:
            account_holdings = all_txns.groupby('account')['units'].sum()
    
    with st.form("record_transaction_form"):
        col1, col2 = st.columns(2)
        with col1:
            account = st.selectbox("Account", ACCOUNTS)
            trade_date = st.date_input("Transaction Date", max_value=date.today())
        
        with col2:
            if transaction_type in ["Buy", "Sell"]:
                units = st.number_input("Units", min_value=1, step=1)
                price = st.number_input("Price (per unit)", min_value=0.0, format="%.4f")
                amount = units * price
                st.markdown(f"**Calculated Amount: {fmt_inr(amount)}**")
                adjust_face_value = False
            
            elif transaction_type == 'Principal_Repayment':
                current_units = account_holdings.get(account, 0.0)
                st.markdown(f"Applies to **{current_units}** units held in **{account}**")
                amount = st.number_input("Total Amount", min_value=0.0, format="%.2f")
                if current_units > 0 and amount > 0:
                    st.markdown(f"**Per Unit: {fmt_inr(amount / current_units)}**")
                adjust_face_value = st.checkbox("Permanently adjust Face Value", value=True)
                units = 0.0
                price = 0.0
            
            else:  # Interest_Receipt
                amount = st.number_input("Amount", min_value=0.0, format="%.2f")
                units = 0.0
                price = 0.0
                adjust_face_value = False

        notes = st.text_area("Notes")
        submit = st.form_submit_button("RECORD TRANSACTION")

        if submit:
            txn_id = str(uuid.uuid4())
            units_to_store = -abs(units) if transaction_type == 'Sell' else abs(units)
            
            if transaction_type == 'Principal_Repayment':
                all_txns = db_query("SELECT units FROM transactions WHERE bond_id = ? AND account = ?", (bond_id, account))
                cur_units = all_txns['units'].sum() if not all_txns.empty else 0.0
                amount_per_unit = amount / cur_units if cur_units > 0 else 0.0
            else:
                amount_per_unit = 0.0

            if transaction_type in ["Buy", "Sell"]:
                final_amount = units * price
            else:
                final_amount = amount

            success = db_execute(
                "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (txn_id, bond_id, account, trade_date.isoformat(), transaction_type,
                 units_to_store, price, final_amount, notes)
            )
            
            if success:
                st.success(f"**{transaction_type}** recorded successfully!")
                logging.info(f"Recorded {transaction_type} for {bond_id}")
                
                if transaction_type == 'Principal_Repayment' and adjust_face_value and amount_per_unit > 0:
                    db_execute("UPDATE securities SET face_value = face_value - ? WHERE bond_id = ?",
                              (amount_per_unit, bond_id))
                    st.success(f"Face value adjusted by {fmt_inr(amount_per_unit)} per unit")
                
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: EDIT TRANSACTION
# ═══════════════════════════════════════════════════════════════════════

def page_edit_transaction():
    st.markdown("""
        <div class='section'>
            <div class='section-header'>
                <h3 class='section-title'>Edit Transaction</h3>
                <p class='section-subtitle'>Correct or delete an existing transaction entry</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    transactions_df = db_query("""
        SELECT t.*, s.issuer, s.isin FROM transactions t
        JOIN securities s ON t.bond_id = s.bond_id
        ORDER BY t.trade_date DESC
    """)
    
    if transactions_df.empty:
        st.warning("No transactions found.")
        return

    transactions_df['trade_date'] = pd.to_datetime(transactions_df['trade_date']).dt.strftime('%Y-%m-%d')
    options = {
        f"{r['trade_date']} | {r['transaction_type']} | {r['issuer']} | {fmt_inr(r['amount'])}": r['transaction_id']
        for _, r in transactions_df.iterrows()
    }
    
    selected = st.selectbox("Select Transaction", options.keys(), index=None, placeholder="Choose a transaction...")
    
    if not selected:
        return
        
    txn_id = options[selected]
    txn = transactions_df[transactions_df['transaction_id'] == txn_id].iloc[0]

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
    with st.form("edit_transaction_form"):
        st.markdown(f"**Editing Transaction:** `{txn_id[:12]}...`")
        st.text_input("Security", value=f"{txn['issuer']} ({txn['isin']})", disabled=True)

        account_list = ACCOUNTS
        type_list = TRANSACTION_TYPES
        
        try: account_idx = account_list.index(txn['account'])
        except ValueError: account_idx = 0
        try: type_idx = type_list.index(txn['transaction_type'])
        except ValueError: type_idx = 0

        col1, col2 = st.columns(2)
        with col1:
            account = st.selectbox("Account", account_list, index=account_idx)
            trade_date = st.date_input("Date", max_value=date.today(),
                                       value=pd.to_datetime(txn['trade_date']).date())
            transaction_type = st.selectbox("Type", type_list, index=type_idx)
        with col2:
            units = st.number_input("Units", min_value=0, step=1, value=int(abs(txn['units'])))
            price = st.number_input("Price", min_value=0.0, format="%.4f", value=txn['price'])
            amount = st.number_input("Amount", min_value=0.0, format="%.2f", value=txn['amount'])
        
        notes = st.text_area("Notes", value=txn['notes'] or '')
        
        col_u, col_d = st.columns([3, 1])
        with col_u:
            update_btn = st.form_submit_button("UPDATE TRANSACTION", use_container_width=True)
        with col_d:
            delete_btn = st.form_submit_button("DELETE", use_container_width=True)

        if update_btn:
            if transaction_type in ["Buy", "Sell"]:
                final_amount = units * price
                final_price = price
                final_units = -abs(units) if transaction_type == 'Sell' else abs(units)
            else:
                final_amount = amount
                final_price = 0.0
                final_units = 0.0
            
            success = db_execute(
                """UPDATE transactions SET account=?, trade_date=?, transaction_type=?,
                   units=?, price=?, amount=?, notes=? WHERE transaction_id=?""",
                (account, trade_date.isoformat(), transaction_type,
                 final_units, final_price, final_amount, notes, txn_id)
            )
            if success:
                st.success("Transaction updated!")
                st.rerun()

        if delete_btn:
            if db_execute("DELETE FROM transactions WHERE transaction_id = ?", (txn_id,)):
                st.success("Transaction deleted!")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# PAGE: TRANSACTION LEDGER
# ═══════════════════════════════════════════════════════════════════════

def page_view_transactions():
    st.markdown("""
        <div class='section'>
            <div class='section-header'>
                <h3 class='section-title'>Transaction Ledger</h3>
                <p class='section-subtitle'>Complete audit trail of all portfolio activity</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Filters
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        f_account = st.selectbox("Account", ['All'] + ACCOUNTS, key="ledger_acct")
    with fcol2:
        f_type = st.selectbox("Type", ['All'] + TRANSACTION_TYPES, key="ledger_type")
    with fcol3:
        f_search = st.text_input("Search Issuer", key="ledger_search")
    
    query = """
        SELECT t.trade_date, s.issuer, s.isin, t.account, t.transaction_type, 
               t.units, t.price, t.amount, t.notes
        FROM transactions t
        JOIN securities s ON t.bond_id = s.bond_id
        WHERE 1=1
    """
    params = []
    if f_account != 'All':
        query += " AND t.account = ?"
        params.append(f_account)
    if f_type != 'All':
        query += " AND t.transaction_type = ?"
        params.append(f_type)
    if f_search:
        query += " AND s.issuer LIKE ?"
        params.append(f"%{f_search}%")
    query += " ORDER BY t.trade_date DESC"
    
    ledger_df = db_query(query, tuple(params))
    
    if ledger_df.empty:
        st.info("No transactions match the filters.")
        return

    ledger_df['trade_date'] = pd.to_datetime(ledger_df['trade_date']).dt.strftime('%d %b %Y')
    
    rows_html = ""
    for _, r in ledger_df.iterrows():
        type_cls = ""
        if r['transaction_type'] == 'Buy':
            type_cls = "positive"
        elif r['transaction_type'] == 'Sell':
            type_cls = "negative"
        elif r['transaction_type'] == 'Interest_Receipt':
            type_cls = "positive"
        
        rows_html += f"""
        <tr>
            <td>{r['trade_date']}</td>
            <td style='font-weight:600;'>{r['issuer']}</td>
            <td style='font-size:0.8rem; color:#888;'>{r['isin']}</td>
            <td>{r['account']}</td>
            <td class='{type_cls}'>{r['transaction_type'].replace('_', ' ')}</td>
            <td style='text-align:right;'>{f"{r['units']:,.0f}" if r['units'] != 0 else '-'}</td>
            <td style='text-align:right;'>{fmt_inr(r['price']) if r['price'] != 0 else '-'}</td>
            <td style='text-align:right; font-weight:600;'>{fmt_inr(r['amount'])}</td>
            <td style='font-size:0.8rem; color:#888;'>{r['notes'] or ''}</td>
        </tr>
        """
    
    st.markdown(f"""
        <div class='table-container'>
            <table class='table'>
                <thead><tr>
                    <th>Date</th><th>Issuer</th><th>ISIN</th><th>Account</th>
                    <th>Type</th><th>Units</th><th>Price</th><th>Amount</th><th>Notes</th>
                </tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
    """, unsafe_allow_html=True)
    
    # Download
    csv = ledger_df.to_csv(index=False)
    st.download_button("EXPORT LEDGER CSV", csv, "nivesh_ledger.csv", "text/csv")


# ═══════════════════════════════════════════════════════════════════════
# PAGE: SECURITIES MASTER
# ═══════════════════════════════════════════════════════════════════════

def page_securities_master():
    st.markdown("""
        <div class='section'>
            <div class='section-header'>
                <h3 class='section-title'>Securities Master</h3>
                <p class='section-subtitle'>Complete registry of all bonds in the system</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    secs = db_query("""
        SELECT s.*, m.bond_type, m.credit_rating, m.sector, m.listing
        FROM securities s
        LEFT JOIN security_metadata m ON s.bond_id = m.bond_id
        ORDER BY s.issuer
    """)
    
    if secs.empty:
        st.info("No securities registered yet.")
        return
    
    rows_html = ""
    for _, s in secs.iterrows():
        days = calc_days_to_maturity(s['maturity_date'])
        mat_str = pd.to_datetime(s['maturity_date']).strftime('%d %b %Y')
        rating = s.get('credit_rating', 'Unrated') or 'Unrated'
        btype = s.get('bond_type', 'NCD') or 'NCD'
        
        rows_html += f"""
        <tr>
            <td style='font-weight:600;'>{s['issuer']}</td>
            <td style='font-size:0.8rem;'>{s['isin']}</td>
            <td>{btype}</td>
            <td>{rating_badge(rating)}</td>
            <td style='text-align:right;'>{fmt_pct(s['coupon_rate'])}</td>
            <td style='text-align:right;'>{fmt_inr(s['face_value'])}</td>
            <td>{s['frequency']}</td>
            <td>{mat_str}</td>
            <td style='text-align:right;'>{days}d</td>
            <td>{s.get('sector', '') or ''}</td>
        </tr>
        """
    
    st.markdown(f"""
        <div class='table-container'>
            <table class='table'>
                <thead><tr>
                    <th>Issuer</th><th>ISIN</th><th>Type</th><th>Rating</th>
                    <th>Coupon</th><th>Face Value</th><th>Frequency</th>
                    <th>Maturity</th><th>Days Left</th><th>Sector</th>
                </tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════

def main():
    # Initialize database
    db_init()
    
    # ─── Sidebar (Swing-family design) ───
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0; margin-bottom: 1rem;">
            <div style="font-size: 1.75rem; font-weight: 800; color: #FFC300;">NIVESH</div>
            <div style="color: #888888; font-size: 0.75rem; margin-top: 0.25rem;">निवेश | Bond Portfolio Ledger</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-title">📊 Navigation</div>', unsafe_allow_html=True)
        page = st.radio(
            "Navigate",
            [
                "📈 Dashboard",
                "📋 Securities Master",
                "➕ Add Security",
                "✏️ Edit Security",
                "💰 Record Transaction",
                "🔧 Edit Transaction",
                "📖 Transaction Ledger",
            ],
            label_visibility="collapsed"
        )
        
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        # Quick stats
        st.markdown('<div class="sidebar-title">💡 Quick Stats</div>', unsafe_allow_html=True)
        sec_count = db_query("SELECT COUNT(*) as c FROM securities")
        txn_count = db_query("SELECT COUNT(*) as c FROM transactions")
        sc = sec_count['c'].iloc[0] if not sec_count.empty else 0
        tc = txn_count['c'].iloc[0] if not txn_count.empty else 0
        st.markdown(f"""
        <div class='info-box'>
            <p style='font-size: 0.8rem; margin: 0; color: var(--text-muted); line-height: 1.8;'>
                <strong>Securities:</strong> {sc}<br>
                <strong>Transactions:</strong> {tc}<br>
                <strong>Date:</strong> {datetime.now().strftime('%d %b %Y')}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class='info-box'>
            <p style='font-size: 0.8rem; margin: 0; color: var(--text-muted); line-height: 1.5;'>
                <strong>Version:</strong> {VERSION}<br>
                <strong>Engine:</strong> SQLite + NumPy<br>
                <strong>Product:</strong> {COMPANY}
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # ─── Premium Header ───
    st.markdown(f"""
        <div class="premium-header">
            <h1>NIVESH : Bond Portfolio Ledger</h1>
            <div class="tagline">Institutional Fixed Income Management · Portfolio Analytics · Cashflow Intelligence</div>
        </div>
    """, unsafe_allow_html=True)
    
    # ─── Page Routing ───
    if "Dashboard" in page:
        page_dashboard()
    elif "Securities Master" in page:
        page_securities_master()
    elif "Add Security" in page:
        page_add_security()
    elif "Edit Security" in page:
        page_edit_security()
    elif "Record Transaction" in page:
        page_record_transaction()
    elif "Edit Transaction" in page:
        page_edit_transaction()
    elif "Transaction Ledger" in page:
        page_view_transactions()


if __name__ == "__main__":
    main()
