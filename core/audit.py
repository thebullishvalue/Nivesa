# -*- coding: utf-8 -*-
"""
Nivesa — the audit trail: every insert, update and delete on the book, kept in an append-only table.

The record is written by SQLite triggers, not by the app, so no write path can skip it: a form, a
face-value step-down, a script run against the file by hand — every change to ``securities``,
``transactions`` and ``security_metadata`` leaves one row holding the row as it was and as it became
(JSON), with the time in UTC. Two more triggers refuse any UPDATE or DELETE on the trail itself.

The write paths are untouched (``tests/test_source_identity.py``): ``audit_init`` runs after
``db_init`` and (re)creates the table and its triggers, so a column added to a tracked table later is
picked up on the next start.
"""

from __future__ import annotations

from contextlib import closing
import sqlite3

import pandas as pd

from core.db import _connect
from core.config import logger

#: The tables whose every change is recorded, and the column that names a row.
TRACKED = {"securities": "bond_id", "transactions": "transaction_id", "security_metadata": "bond_id"}

_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    changed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    table_name TEXT NOT NULL,
    action     TEXT NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    row_id     TEXT NOT NULL,
    old_row    TEXT,
    new_row    TEXT
)"""

_GUARDS = (
    "CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log "
    "BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END",
    "CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log "
    "BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END",
)


def _json(alias: str, cols: "list[str]") -> str:
    return "json_object(" + ", ".join(f"'{c}', {alias}.\"{c}\"" for c in cols) + ")"


def _triggers(c: sqlite3.Cursor) -> "list[tuple[str, str]]":
    out = []
    for table, key in TRACKED.items():
        cols = [r[1] for r in c.execute(f'PRAGMA table_info("{table}")').fetchall()]
        if not cols:
            continue
        old, new = _json("OLD", cols), _json("NEW", cols)
        out += [
            (f"audit_{table}_insert",
             f"CREATE TRIGGER audit_{table}_insert AFTER INSERT ON {table} BEGIN "
             f"INSERT INTO audit_log (table_name, action, row_id, new_row) "
             f"VALUES ('{table}', 'INSERT', NEW.\"{key}\", {new}); END"),
            # an UPDATE that changes nothing (a re-save of the same form) is not a change
            (f"audit_{table}_update",
             f"CREATE TRIGGER audit_{table}_update AFTER UPDATE ON {table} WHEN {old} IS NOT {new} BEGIN "
             f"INSERT INTO audit_log (table_name, action, row_id, old_row, new_row) "
             f"VALUES ('{table}', 'UPDATE', NEW.\"{key}\", {old}, {new}); END"),
            (f"audit_{table}_delete",
             f"CREATE TRIGGER audit_{table}_delete AFTER DELETE ON {table} BEGIN "
             f"INSERT INTO audit_log (table_name, action, row_id, old_row) "
             f"VALUES ('{table}', 'DELETE', OLD.\"{key}\", {old}); END"),
        ]
    return out


def audit_init() -> bool:
    """Create the trail and (re)create its triggers in one transaction. Returns False (and logs) on
    failure: the book stays usable, but the caller should say the trail is not being kept."""
    try:
        with closing(_connect()) as conn, conn:
            c = conn.cursor()
            c.execute(_TABLE)
            existing = {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'audit_%'").fetchall()}
            want = _triggers(c)
            # rebuild only when the set or a definition changed, so an ordinary run writes nothing
            current = dict(c.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'audit_%'").fetchall())
            target = dict(want) | {g.split()[2]: g for g in _GUARDS}
            if current != target:
                for name in existing:
                    c.execute(f'DROP TRIGGER IF EXISTS "{name}"')
                for sql in target.values():
                    c.execute(sql)
            return True
    except sqlite3.Error as e:
        logger.error(f"Audit trail init failed: {e}")
        return False


def audit_entries(limit: int = 500) -> pd.DataFrame:
    """The newest ``limit`` entries of the trail, newest first (empty frame when there are none)."""
    try:
        with closing(_connect()) as conn:
            return pd.read_sql_query(
                "SELECT audit_id, changed_at, table_name, action, row_id, old_row, new_row "
                "FROM audit_log ORDER BY audit_id DESC LIMIT ?", conn, params=(int(limit),))
    except (sqlite3.Error, pd.errors.DatabaseError) as e:
        logger.error(f"Audit trail read failed: {e}")
        return pd.DataFrame()
