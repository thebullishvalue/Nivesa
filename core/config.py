# -*- coding: utf-8 -*-
"""
Nivesa — application constants, data paths and the logger.
निवेसा · Bond Portfolio Ledger

Moved byte-for-byte from the 2.8.0 single-file app (tests/test_source_identity.py proves it); only
VERSION / BUILD changed. ``NIVESA_DATA_DIR`` is read once, at import.
"""

import logging
import os

VERSION = "3.0.9"
BUILD = "2026.11.GRAPHITE"
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
# Same-day settlement order for the running cost-basis engine: a buy settles
# before a sale of the same units, and a principal repayment reduces the basis
# of units still held before any same-day sale is struck against that basis.
FLOW_ORDER = {'Buy': 0, 'Principal_Repayment': 1, 'Sell': 2}

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
