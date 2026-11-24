# -*- coding: utf-8 -*-
"""
Nivesa — the book's home: a private GitHub repository holding ``portfolio.db``.

Streamlit Community Cloud keeps no files: every redeploy (each push to the code) and every wake from
sleep starts the app on a fresh disk. So the database file on the server is a working copy, and the
book's real home is one file in a PRIVATE repository:

  · ``Replica.pull`` — once per server process, before the database is opened: download the file and
    put it where ``core.db`` reads it. If the download fails the app must not open a stale or empty copy
    (a later save would overwrite the real book with it), so the caller stops and offers a retry.
  · ``Replica.push_if_changed`` — after every script run: if the book's content changed since the last
    pull or push, upload a consistent snapshot as a new commit. Every save is a commit, so the
    repository's history is a backup of every state the book has been in.
  · The upload names the file's sha it last saw. If the stored file changed outside the app (an upload
    by hand), GitHub refuses the commit and nothing is overwritten: the app says so and stops saving
    until the server restarts (which loads the stored copy).

Nothing here imports Streamlit; ``ui.storage`` reads the settings and draws the notices.
"""

from __future__ import annotations

import base64
import hashlib
import os
import sqlite3
import tempfile
import threading
from contextlib import closing
from dataclasses import dataclass, field

import requests

from core.config import logger

API = "https://api.github.com"
_TIMEOUT = 20


class StoreError(Exception):
    """The store could not be read or written."""


class StoreConflict(StoreError):
    """The stored file changed since the app last read it; the upload was refused."""


def blob_sha(data: bytes) -> str:
    """Git's blob id for ``data`` — what the contents API calls the file's ``sha``."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


@dataclass
class GitHubStore:
    """One file in a GitHub repository, through the REST contents API."""
    repo: str                       # "owner/name" — a PRIVATE repository
    token: str                      # fine-grained token: this repository only, Contents read and write
    path: str = "portfolio.db"
    branch: "str | None" = None     # None = the repository's default branch
    http: object = field(default=requests, repr=False)

    def _url(self) -> str:
        return f"{API}/repos/{self.repo}/contents/{self.path.lstrip('/')}"

    def _headers(self, accept: str) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Accept": accept,
                "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "nivesa"}

    def fetch(self) -> "tuple[bytes | None, str | None]":
        """``(content, sha)``, or ``(None, None)`` when the file does not exist yet."""
        params = {"ref": self.branch} if self.branch else None
        try:
            r = self.http.get(self._url(), headers=self._headers("application/vnd.github.raw"),
                              params=params, timeout=_TIMEOUT)
        except requests.RequestException as e:
            raise StoreError(f"could not reach GitHub: {type(e).__name__}") from e
        if r.status_code == 404:
            # a missing file and a repository the token cannot see both answer 404; the first upload
            # tells them apart (it fails on the second)
            return None, None
        if r.status_code != 200:
            raise StoreError(f"GitHub answered {r.status_code} reading {self.repo}/{self.path}")
        data = r.content
        return data, blob_sha(data)

    def put(self, data: bytes, sha: "str | None", message: str) -> str:
        """Commit ``data`` over the file whose sha is ``sha`` (None: create it). Returns the new sha."""
        body = {"message": message, "content": base64.b64encode(data).decode("ascii")}
        if sha:
            body["sha"] = sha
        if self.branch:
            body["branch"] = self.branch
        try:
            r = self.http.put(self._url(), headers=self._headers("application/vnd.github+json"),
                              json=body, timeout=_TIMEOUT)
        except requests.RequestException as e:
            raise StoreError(f"could not reach GitHub: {type(e).__name__}") from e
        if r.status_code == 409 or (r.status_code == 422 and not sha):
            raise StoreConflict(f"the stored file changed outside the app (GitHub {r.status_code})")
        if r.status_code not in (200, 201):
            raise StoreError(f"GitHub answered {r.status_code} saving {self.repo}/{self.path}")
        return r.json()["content"]["sha"]


def digest(db_file: str) -> "str | None":
    """The book's CONTENT, hashed (the file's bytes move with every harmless commit; this does not)."""
    if not os.path.exists(db_file):
        return None
    with closing(sqlite3.connect(db_file)) as con:
        h = hashlib.sha256()
        # the schema, then every table's rows — not iterdump(), whose sqlite_sequence lines (SQLite's own
        # AUTOINCREMENT bookkeeping) come and go without the book changing
        objs = con.execute("SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' "
                           "ORDER BY type, name").fetchall()
        for typ, name, sql in objs:
            h.update(repr((typ, name, sql)).encode("utf-8"))
            if typ == "table":
                for row in con.execute(f'SELECT * FROM "{name}" ORDER BY rowid'):
                    h.update(repr(row).encode("utf-8"))
        return h.hexdigest()


def _has_securities(db_file: str) -> bool:
    try:
        with closing(sqlite3.connect(db_file)) as con:
            return con.execute("SELECT EXISTS (SELECT 1 FROM securities)").fetchone()[0] == 1
    except sqlite3.Error:
        return False


def snapshot(db_file: str) -> bytes:
    """A consistent copy of the database as one file (the write-ahead log folded in)."""
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "snapshot.db")
        with closing(sqlite3.connect(db_file)) as src, closing(sqlite3.connect(out)) as dst:
            src.backup(dst)
            dst.execute("PRAGMA journal_mode=DELETE")
        with open(out, "rb") as f:
            return f.read()


def install(db_file: str, data: bytes) -> None:
    """Put a downloaded book where ``core.db`` reads it. Only before any connection is open: the old
    write-ahead log and index go first (applied to the new file they would corrupt it)."""
    os.makedirs(os.path.dirname(db_file) or ".", exist_ok=True)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(db_file + suffix):
            os.remove(db_file + suffix)
    tmp = db_file + ".download"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, db_file)


class Replica:
    """The server's working copy of the book and its link to the store. One per process."""

    def __init__(self, store: GitHubStore, db_file_fn):
        self.store = store
        self._db_file = db_file_fn       # read at call time (tests repoint core.db.DB_FILE)
        self.lock = threading.Lock()
        self.pulled = False
        self.sha: "str | None" = None
        self.saved: "str | None" = None  # digest of what the store holds
        self.pull_error: "str | None" = None
        self.push_error: "str | None" = None
        self.conflict = False
        self.created = False             # the store had no file; the first save creates it

    def pull(self) -> bool:
        """Load the stored book (once). False when it could not be loaded — open nothing then."""
        with self.lock:
            if self.pulled:
                return True
            try:
                data, sha = self.store.fetch()
            except StoreError as e:
                self.pull_error = str(e)
                logger.error(f"Store pull failed: {e}")
                return False
            db_file = self._db_file()
            if data is not None:
                install(db_file, data)
                self.saved = digest(db_file)
                logger.info(f"Loaded the book from {self.store.repo}/{self.store.path} ({len(data):,} bytes).")
            else:
                # nothing stored yet: the first save uploads whatever this server holds
                self.created = True
                logger.warning(f"{self.store.repo}/{self.store.path} does not exist yet; the next save creates it.")
            self.sha, self.pulled, self.pull_error = sha, True, None
            return True

    def push_if_changed(self) -> bool:
        """Upload the book if its content changed since the store last saw it. True when in step."""
        with self.lock:
            if not self.pulled or self.conflict:
                return not self.conflict and self.pulled
            db_file = self._db_file()
            now = digest(db_file)
            if now is None or now == self.saved:
                return True
            if self.created and not _has_securities(db_file):
                # Nothing stored yet and nothing here either (a fresh server): saving an empty book
                # would only get in the way of the real one being uploaded. Wait for a first entry.
                return True
            try:
                self.sha = self.store.put(snapshot(db_file), self.sha, "Nivesa: ledger saved")
            except StoreConflict as e:
                self.conflict, self.push_error = True, str(e)
                logger.error(f"Store push refused: {e}")
                return False
            except StoreError as e:
                self.push_error = str(e)          # retried after the next run
                logger.error(f"Store push failed: {e}")
                return False
            self.saved, self.push_error, self.created = now, None, False
            logger.info(f"Saved the book to {self.store.repo}/{self.store.path}.")
            return True
