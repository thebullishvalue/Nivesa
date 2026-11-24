"""
The sample book every test runs on: invented issuers and amounts, built fresh for each session.

The real book is never in the repository (it lives in the private store, ``core.store``), so the suite
needs a book of its own. This one is shaped to exercise what the tests ask of a book, and nothing in it
is anyone's holding:

  · live positions in every account, one bond held by several accounts, buys at a discount, at par and
    at a premium, an FD with a large face, a bond maturing within three months;
  · an amortizing bond repaid pro rata across two accounts on two dates (one face step-down owned per
    date, face per unit already stepped down 1000 → 800);
  · interest receipts recorded on one position; a matured security with no holdings; no sales (the
    pages' "no realized P&L" state).

Every maturity falls on day 1–28 of its month, so the 2.8.0 golden values (captured from this book by
``tests/golden/capture_golden.py``) stay valid after 3.1.0's month-end coupon fix; the month-end grid
has tests of its own in ``tests/test_bond_math.py``. Ids are fixed, so the book (and its fingerprint)
is the same on every build.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_SCHEMA = (
    """CREATE TABLE securities (
                bond_id TEXT PRIMARY KEY,
                issuer TEXT NOT NULL,
                isin TEXT NOT NULL UNIQUE,
                maturity_date TEXT NOT NULL,
                frequency TEXT NOT NULL,
                coupon_rate REAL NOT NULL,
                face_value REAL NOT NULL
            )""",
    """CREATE TABLE transactions (
                transaction_id TEXT PRIMARY KEY,
                bond_id TEXT NOT NULL,
                account TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                units REAL NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                notes TEXT, owns_face_adj INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (bond_id) REFERENCES securities (bond_id)
            )""",
    """CREATE TABLE security_metadata (
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
            )""",
)


def _bid(n: int) -> str:
    return f"b{n:07x}-0000-4000-8000-{n:012x}"


def _tid(n: int) -> str:
    # distinct in the first 8 characters (the Edit Transaction picker shows those), and never the
    # write-path harness's own "0000000n-feed-…" ids
    return f"c{n:07x}-0000-4000-8000-{n:012x}"


#: (n, issuer, isin, maturity, frequency, coupon, face now, type, rating, day count, issue, listing, sector)
SECURITIES = (
    (1, "Alder Finance", "INE000A01011", "2028-03-15", "Monthly", 0.105, 1000.0,
     "NCD", "AA", "Actual/365", "2024-03-15", "NSE", "Financials"),
    (2, "Birch Capital", "INE000B01012", "2027-06-20", "Quarterly", 0.0925, 1000.0,
     "Corporate Bond", "AA+", "Actual/365", "2023-06-20", "BSE", "Financials"),
    (3, "Cedar Housing", "INE000C01013", "2028-12-10", "Monthly", 0.11, 800.0,
     "NCD", "A+", "Actual/365", "2024-12-10", "Unlisted", "Housing Finance"),
    (4, "Deodar Infrastructure", "INE000D01014", "2031-09-05", "Annual", 0.079, 1000.0,
     "Tax-Free Bond", "AAA", "Actual/Actual", "2021-09-05", "Both", "Infrastructure"),
    (5, "Elm Micro Credit", "INE000E01015", "2026-12-27", "Monthly", 0.12, 1000.0,
     "NCD", "A", "Actual/365", "2024-12-27", "Unlisted", "Microfinance"),
    (6, "Fir Leasing", "INE000F01016", "2025-09-25", "Quarterly", 0.10, 1000.0,
     "NCD", "BBB+", "30/360", "2022-09-25", "Unlisted", "Financials"),
    (7, "Gingko Bank", "INE000G01017", "2029-02-11", "Annual", 0.075, 100000.0,
     "FD", "AAA", "Actual/365", "2024-02-11", "Unlisted", "Banking"),
)

#: (n, security n, account, date, type, units, price, amount, owns_face_adj, notes)
TRANSACTIONS = (
    (1, 1, "REKHA", "2024-04-10", "Buy", 20, 1000.0, 20000.0, 0, "sample"),
    (2, 1, "HEMANG", "2024-06-05", "Buy", 10, 995.0, 9950.0, 0, None),
    (3, 1, "MANTHAN", "2025-01-20", "Buy", 5, 1002.0, 5010.0, 0, None),
    (4, 2, "REKHA", "2024-02-01", "Buy", 15, 980.0, 14700.0, 0, None),
    (5, 2, "HIMA", "2025-03-03", "Buy", 8, 1010.0, 8080.0, 0, None),
    (6, 3, "MANTHAN", "2025-01-05", "Buy", 10, 1000.0, 10000.0, 0, None),
    (7, 3, "HEMANG", "2025-02-14", "Buy", 6, 1000.0, 6000.0, 0, None),
    (8, 3, "MANTHAN", "2025-06-10", "Principal_Repayment", 0, 100.0, 1000.0, 1, "pro rata"),
    (9, 3, "HEMANG", "2025-06-10", "Principal_Repayment", 0, 100.0, 600.0, 0, "pro rata"),
    (10, 3, "MANTHAN", "2026-06-10", "Principal_Repayment", 0, 100.0, 1000.0, 1, None),
    (11, 3, "HEMANG", "2026-06-10", "Principal_Repayment", 0, 100.0, 600.0, 0, None),
    (12, 4, "REKHA", "2023-10-12", "Buy", 50, 1050.0, 52500.0, 0, "premium"),
    (13, 4, "REKHA", "2024-09-05", "Interest_Receipt", 0, 0.0, 3950.0, 0, None),
    (14, 4, "REKHA", "2025-09-05", "Interest_Receipt", 0, 0.0, 3950.0, 0, None),
    (15, 5, "MANTHAN", "2025-08-01", "Buy", 6, 1000.0, 6000.0, 0, None),
    (16, 5, "HIMA", "2025-08-01", "Buy", 4, 1000.0, 4000.0, 0, None),
    (17, 7, "HIMA", "2024-02-11", "Buy", 3, 100000.0, 300000.0, 0, None),
)


def build(data_dir) -> Path:
    """Write the sample book to ``<data_dir>/db/portfolio.db`` (and an empty ``logs``); return the db path."""
    data_dir = Path(data_dir)
    (data_dir / "db").mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    db = data_dir / "db" / "portfolio.db"
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(f"{db}{suffix}"):
            os.remove(f"{db}{suffix}")
    con = sqlite3.connect(db)
    try:
        for sql in _SCHEMA:
            con.execute(sql)
        for n, issuer, isin, mat, freq, cpn, face, btype, rating, dc, issue, listing, sector in SECURITIES:
            con.execute("INSERT INTO securities VALUES (?,?,?,?,?,?,?)", (_bid(n), issuer, isin, mat, freq, cpn, face))
            con.execute("INSERT INTO security_metadata (bond_id, bond_type, credit_rating, day_count, issue_date, "
                        "listing, sector) VALUES (?,?,?,?,?,?,?)", (_bid(n), btype, rating, dc, issue, listing, sector))
        for n, s, acct, d, tt, units, price, amount, owns, notes in TRANSACTIONS:
            con.execute("INSERT INTO transactions (transaction_id, bond_id, account, trade_date, transaction_type, "
                        "units, price, amount, notes, owns_face_adj) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (_tid(n), _bid(s), acct, d, tt, float(units), price, amount, notes, owns))
        con.commit()
    finally:
        con.close()
    return db
