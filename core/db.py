# -*- coding: utf-8 -*-
"""
Nivesa — the SQLite layer: schema/migration, connections, queries, and the ledger-integrity
helpers the write paths use (chronology check, pro-rata face step-down ownership).

Moved byte-for-byte from the 2.8.0 single-file app. The failure paths still speak through
``st.error`` exactly as before (the stylesheet restyles that box into the notice anatomy).
"""

from contextlib import closing
import sqlite3

import pandas as pd
import streamlit as st

from core.config import DB_FILE, logger


def db_init():
    """Initialize / migrate database to current schema."""
    try:
        # closing() releases the handle; `conn` context scopes the txn
        with closing(_connect()) as conn, conn:
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

            # Migration: track which Principal_Repayment transaction "owns" the
            # face-value step-down for its (bond_id, trade_date) group, so a
            # bond redeemed pro-rata across multiple accounts on the same date
            # only decrements face_value once, not once per account. Existing
            # repayments predate this column and already had their real-world
            # effect reflected in face_value (manually, before this feature
            # existed) — flagging them as owners now means editing/deleting one
            # later reverses correctly instead of re-applying a second cut.
            existing_cols = [r[1] for r in c.execute("PRAGMA table_info(transactions)").fetchall()]
            if 'owns_face_adj' not in existing_cols:
                c.execute("ALTER TABLE transactions ADD COLUMN owns_face_adj INTEGER NOT NULL DEFAULT 0")
                c.execute("UPDATE transactions SET owns_face_adj=1 WHERE transaction_type='Principal_Repayment'")

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
        with closing(_connect()) as conn:
            return pd.read_sql_query(query, conn, params=params)
    except sqlite3.Error as e:
        st.error(f"Query failed: {e}")
        logger.error(f"Query failed: {e}")
        return pd.DataFrame()

def db_execute(query, params=()):
    """Run INSERT/UPDATE/DELETE; return success bool."""
    try:
        with closing(_connect()) as conn, conn:
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


def validate_ledger_chronology(bond_id, conn):
    """Ensure running balance of units for all accounts never drops below 0.

    Same-day ties are ordered Buy-before-Sell: transaction_id is a random
    UUID, so ordering by it made same-day Buy→Sell pairs pass or fail at
    random depending on lexical UUID order. Buy-first is the most permissive
    ordering consistent with same-day settlement netting.
    """
    c = conn.cursor()
    c.execute(
        "SELECT account, trade_date, units, transaction_type FROM transactions "
        "WHERE bond_id=? AND transaction_type IN ('Buy', 'Sell') "
        "ORDER BY trade_date, CASE transaction_type WHEN 'Buy' THEN 0 ELSE 1 END, transaction_id",
        (bond_id,)
    )
    txns = c.fetchall()
    
    balances = {}
    for account, tdate, units, ttype in txns:
        balances[account] = balances.get(account, 0.0) + units
        if balances[account] < -1e-5:
            return False, account, tdate
            
    return True, None, None

def face_step_claimed(bond_id, trade_date, exclude_tid=None):
    """Per-unit face step-down already applied to `securities.face_value` by an
    earlier Principal_Repayment in this (bond, date) group.

    Repayment cap checks add this back before comparing against face_value:
    the step-down is claimed once per group (see claim_face_adjustment), so
    every account's share of the same pro-rata redemption must be measured
    against the face as it stood BEFORE that one step-down."""
    q = ("SELECT price FROM transactions WHERE bond_id=? AND trade_date=? AND "
         "transaction_type='Principal_Repayment' AND owns_face_adj=1")
    params = [bond_id, trade_date]
    if exclude_tid is not None:
        q += " AND transaction_id!=?"
        params.append(exclude_tid)
    r = db_query(q, tuple(params))
    return float(r['price'].iloc[0]) if not r.empty and pd.notna(r['price'].iloc[0]) else 0.0

def claim_face_adjustment(c, bond_id, trade_date, tid, price):
    """Apply a Principal_Repayment's per-unit face-value step-down UNLESS
    another transaction already owns the step-down for this (bond, date)
    group — a bond redeemed pro-rata across multiple accounts on the same
    date must only reduce face_value once, not once per account entry."""
    owner = c.execute(
        "SELECT 1 FROM transactions WHERE bond_id=? AND trade_date=? AND "
        "transaction_type='Principal_Repayment' AND owns_face_adj=1 AND transaction_id!=?",
        (bond_id, trade_date, tid),
    ).fetchone()
    if owner is None:
        c.execute("UPDATE securities SET face_value = face_value - ? WHERE bond_id=?", (price, bond_id))
        c.execute("UPDATE transactions SET owns_face_adj=1 WHERE transaction_id=?", (tid,))
    else:
        c.execute("UPDATE transactions SET owns_face_adj=0 WHERE transaction_id=?", (tid,))

def release_face_adjustment(c, bond_id, trade_date, tid, price):
    """Reverse a repayment's face-value step-down (its transaction is being
    edited or deleted) and, if another repayment shares its (bond, date)
    group, promote that one to own the step-down instead — the real-world
    redemption still happened even though this particular row is going away."""
    c.execute("UPDATE securities SET face_value = face_value + ? WHERE bond_id=?", (price, bond_id))
    follower = c.execute(
        "SELECT transaction_id, price FROM transactions WHERE bond_id=? AND trade_date=? AND "
        "transaction_type='Principal_Repayment' AND transaction_id!=? ORDER BY transaction_id LIMIT 1",
        (bond_id, trade_date, tid),
    ).fetchone()
    if follower:
        f_tid, f_price = follower
        c.execute("UPDATE securities SET face_value = face_value - ? WHERE bond_id=?", (f_price, bond_id))
        c.execute("UPDATE transactions SET owns_face_adj=1 WHERE transaction_id=?", (f_tid,))
