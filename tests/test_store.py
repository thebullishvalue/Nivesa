"""
The book's home in a private GitHub repository (``core.store`` / ``ui.storage``), against a fake GitHub
that keeps the contents API's rules: a raw GET, a PUT that must name the current blob sha (409 when it
is stale, 422 when it is missing for an existing file). Nothing reaches the network.

  · the requests are the API's (URL, token, accept header, base64 body, branch);
  · the stored book is installed before the database opens, a stale write-ahead log removed first;
  · a run that changes nothing uploads nothing; a change uploads one consistent snapshot, and the next
    change builds on the sha the last one returned;
  · an empty store is created by the first save; a store changed outside the app is never overwritten;
  · a failed load opens nothing (the app shows why, with a retry); a failed save is retried.
"""
from __future__ import annotations

import base64
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest
import requests

import core.db
from core import store as cs
from core.store import GitHubStore, Replica, StoreConflict, blob_sha

import fixture_book
from test_app import apptest  # noqa: F401 — the suite's AppTest fixture (segmented-control shim)

REPO = Path(__file__).resolve().parents[1]


class _Resp:
    def __init__(self, status, content=b"", payload=None):
        self.status_code, self.content, self._payload = status, content, payload

    def json(self):
        return self._payload


class FakeGitHub:
    """One repository's contents API, in memory."""

    def __init__(self, files=None):
        self.files: dict = dict(files or {})
        self.calls: list = []
        self.down = False

    def _path(self, url):
        assert url.startswith("https://api.github.com/repos/fam/nivesa-data/contents/"), url
        return url.rsplit("/contents/", 1)[1]

    def get(self, url, headers, params=None, timeout=None):
        self.calls.append(("GET", url, headers, params))
        if self.down:
            raise requests.ConnectionError("down")
        p = self._path(url)
        return _Resp(200, self.files[p]) if p in self.files else _Resp(404)

    def put(self, url, headers, json, timeout=None):
        self.calls.append(("PUT", url, headers, json))
        if self.down:
            raise requests.ConnectionError("down")
        p = self._path(url)
        if p in self.files:
            if "sha" not in json:
                return _Resp(422)
            if json["sha"] != blob_sha(self.files[p]):
                return _Resp(409)
        data = base64.b64decode(json["content"])
        self.files[p] = data
        return _Resp(201, payload={"content": {"sha": blob_sha(data)}})

    def puts(self):
        return [c for c in self.calls if c[0] == "PUT"]


def _db_bytes(path) -> bytes:
    return Path(path).read_bytes()


def _issuers(db_file) -> set:
    con = sqlite3.connect(db_file)
    try:
        return {r[0] for r in con.execute("SELECT issuer FROM securities")}
    finally:
        con.close()


@pytest.fixture
def stored_book(tmp_path):
    """The sample book as bytes, with one issuer renamed so it is told apart from the local copy."""
    db = fixture_book.build(tmp_path / "stored")
    con = sqlite3.connect(db)
    con.execute("UPDATE securities SET issuer='Stored Copy Ltd' WHERE issuer='Alder Finance'")
    con.commit()
    con.close()
    return _db_bytes(db)


@pytest.fixture
def local(tmp_path):
    """A server's working copy (the sample book), with a stale write-ahead log beside it."""
    db = fixture_book.build(tmp_path / "server")
    Path(f"{db}-wal").write_bytes(b"stale")
    return str(db)


def _replica(gh, db_file, branch=None):
    return Replica(GitHubStore("fam/nivesa-data", "tok", "portfolio.db", branch, http=gh), lambda: db_file)


# ── the API ─────────────────────────────────────────────────────────────────
def test_blob_sha_is_gits(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"\x00nivesa\xff" * 100)
    out = subprocess.run(["git", "hash-object", str(f)], capture_output=True, text=True, check=True).stdout.strip()
    assert blob_sha(f.read_bytes()) == out


def test_requests_are_the_contents_api():
    gh = FakeGitHub({"portfolio.db": b"old"})
    s = GitHubStore("fam/nivesa-data", "tok", "portfolio.db", "main", http=gh)
    data, sha = s.fetch()
    assert (data, sha) == (b"old", blob_sha(b"old"))
    _m, url, h, params = gh.calls[0]
    assert url == "https://api.github.com/repos/fam/nivesa-data/contents/portfolio.db"
    assert h["Authorization"] == "Bearer tok" and h["Accept"] == "application/vnd.github.raw"
    assert params == {"ref": "main"}
    new = s.put(b"new", sha, "msg")
    body = gh.calls[-1][3]
    assert base64.b64decode(body["content"]) == b"new" and body["sha"] == sha and body["branch"] == "main"
    assert new == blob_sha(b"new")
    with pytest.raises(StoreConflict):
        s.put(b"newer", sha, "msg")        # stale sha → 409


# ── the replica ─────────────────────────────────────────────────────────────
def test_pull_installs_the_stored_book(local, stored_book):
    gh = FakeGitHub({"portfolio.db": stored_book})
    rep = _replica(gh, local)
    assert rep.pull() and rep.pull()
    assert len([c for c in gh.calls if c[0] == "GET"]) == 1          # once per process
    assert not Path(f"{local}-wal").exists()
    assert "Stored Copy Ltd" in _issuers(local)


def test_no_change_no_upload_then_each_change_one_commit(local, stored_book):
    gh = FakeGitHub({"portfolio.db": stored_book})
    rep = _replica(gh, local)
    rep.pull()
    core.db.DB_FILE, saved = local, core.db.DB_FILE
    try:
        core.db.db_init()                                          # the app's own start-up writes nothing
    finally:
        core.db.DB_FILE = saved
    assert rep.push_if_changed() and gh.puts() == []

    con = sqlite3.connect(local)
    con.execute("UPDATE securities SET coupon_rate=0.2 WHERE issuer='Stored Copy Ltd'")
    con.commit()                                                    # left in the write-ahead log
    assert rep.push_if_changed() and len(gh.puts()) == 1
    assert rep.push_if_changed() and len(gh.puts()) == 1           # nothing new

    con.execute("UPDATE securities SET coupon_rate=0.3 WHERE issuer='Stored Copy Ltd'")
    con.commit()
    con.close()
    assert rep.push_if_changed() and len(gh.puts()) == 2           # built on the returned sha

    out = Path(local).parent / "out.db"
    out.write_bytes(gh.files["portfolio.db"])
    c2 = sqlite3.connect(out)
    assert c2.execute("SELECT coupon_rate FROM securities WHERE issuer='Stored Copy Ltd'").fetchone() == (0.3,)
    assert c2.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    c2.close()


def test_empty_store_is_created_by_the_first_save(local):
    gh = FakeGitHub()
    rep = _replica(gh, local)
    assert rep.pull() and rep.created
    assert rep.push_if_changed()
    assert "sha" not in gh.puts()[0][3] and "Alder Finance" in _issuers_bytes(gh.files["portfolio.db"], local)


def test_empty_store_and_empty_server_save_nothing(tmp_path):
    db = str(tmp_path / "fresh.db")
    core.db.DB_FILE, saved = db, core.db.DB_FILE
    try:
        core.db.db_init()
    finally:
        core.db.DB_FILE = saved
    gh = FakeGitHub()
    rep = _replica(gh, db)
    assert rep.pull() and rep.created
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE scratch (x)")       # a change, but still no security
    con.commit()
    con.close()
    assert rep.push_if_changed() and gh.puts() == [] and rep.created


def _issuers_bytes(data, near) -> set:
    p = Path(near).parent / "check.db"
    p.write_bytes(data)
    return _issuers(p)


def test_store_changed_outside_the_app_is_never_overwritten(local, stored_book):
    gh = FakeGitHub({"portfolio.db": stored_book})
    rep = _replica(gh, local)
    rep.pull()
    gh.files["portfolio.db"] = b"uploaded by hand"
    con = sqlite3.connect(local)
    con.execute("DELETE FROM transactions WHERE notes='premium'")
    con.commit()
    con.close()
    assert not rep.push_if_changed() and rep.conflict
    assert gh.files["portfolio.db"] == b"uploaded by hand"
    n = len(gh.puts())
    assert not rep.push_if_changed() and len(gh.puts()) == n       # no retries over it


def test_failed_save_is_retried(local, stored_book):
    gh = FakeGitHub({"portfolio.db": stored_book})
    rep = _replica(gh, local)
    rep.pull()
    con = sqlite3.connect(local)
    con.execute("UPDATE securities SET face_value=1 WHERE issuer='Gingko Bank'")
    con.commit()
    con.close()
    gh.down = True
    assert not rep.push_if_changed() and rep.push_error and not rep.conflict
    gh.down = False
    assert rep.push_if_changed() and rep.push_error is None


def test_failed_load_opens_nothing(local):
    gh = FakeGitHub()
    gh.down = True
    rep = _replica(gh, local)
    before = _db_bytes(local)
    assert not rep.pull() and rep.pull_error
    assert not rep.push_if_changed()                               # never saves an unloaded copy
    assert _db_bytes(local) == before and gh.puts() == []


# ── through the app ─────────────────────────────────────────────────────────
@pytest.fixture
def app_with_store(monkeypatch, tmp_path, stored_book):
    import ui.storage as us
    gh = FakeGitHub({"portfolio.db": stored_book})
    data = tmp_path / "data"
    fixture_book.build(data)
    monkeypatch.setattr(core.db, "DB_FILE", str(data / "db" / "portfolio.db"))
    monkeypatch.setenv("NIVESA_STORE_REPO", "fam/nivesa-data")
    monkeypatch.setenv("NIVESA_STORE_TOKEN", "tok")
    monkeypatch.setattr(us, "make_store", lambda cfg: GitHubStore(cfg["repo"], cfg["token"], cfg["path"],
                                                                 cfg["branch"], http=gh))
    us._REPLICA.clear()
    import streamlit as st
    st.cache_data.clear()
    yield gh
    us._REPLICA.clear()
    st.cache_data.clear()


def test_app_reads_the_stored_book_and_saves_changes(app_with_store, apptest):
    gh = app_with_store
    at = apptest().run()
    assert not at.exception
    assert "Stored Copy Ltd" in _issuers(core.db.DB_FILE)
    # the first run adds the audit trail to the stored book: that is a change, saved once
    assert len(gh.puts()) == 1
    at.run()
    assert len(gh.puts()) == 1
    con = sqlite3.connect(core.db.DB_FILE)
    con.execute("UPDATE security_metadata SET credit_rating='AAA'")
    con.commit()
    con.close()
    at.run()
    assert len(gh.puts()) == 2
    assert not any("Not saved" in m.value for m in at.markdown)


def test_app_says_why_when_the_book_cannot_be_loaded(app_with_store, apptest):
    gh = app_with_store
    gh.down = True
    at = apptest().run()
    assert not at.exception
    assert any("could not be read" in m.value for m in at.markdown)
    assert [b.label for b in at.button] == ["Try again"]
    assert gh.puts() == []
    gh.down = False
    at.button[0].click().run()
    assert not at.exception and "Stored Copy Ltd" in _issuers(core.db.DB_FILE)


def test_conflict_shows_in_the_rail(app_with_store, apptest):
    gh = app_with_store
    at = apptest().run()
    gh.files["portfolio.db"] = b"uploaded by hand"
    con = sqlite3.connect(core.db.DB_FILE)
    con.execute("UPDATE security_metadata SET credit_rating='AAA'")
    con.commit()
    con.close()
    at.run()      # this run's save is refused…
    at.run()      # …and the next run says so
    assert any("changed outside the app" in m.value for m in at.markdown)
    assert gh.files["portfolio.db"] == b"uploaded by hand"


def test_streamlit_cloud_without_a_store_warns(monkeypatch):
    import ui.storage as us
    monkeypatch.delenv("NIVESA_STORE_REPO", raising=False)
    monkeypatch.setattr(us, "settings", lambda: None)
    monkeypatch.setattr(us, "ON_STREAMLIT_CLOUD", True)
    assert us.notices()[0]["title"] == "Not kept"
    monkeypatch.setattr(us, "ON_STREAMLIT_CLOUD", False)
    assert us.notices() == []


def test_first_start_with_an_empty_store_copies_the_ledger_there(app_with_store, apptest):
    """The migration path: the store is empty and the server has the ledger — one run puts it there."""
    gh = app_with_store
    gh.files.clear()
    at = apptest().run()
    assert not at.exception
    assert any("being copied there" in m.value for m in at.markdown)
    assert len(gh.puts()) == 1 and "sha" not in gh.puts()[0][3]
    assert "Alder Finance" in _issuers_bytes(gh.files["portfolio.db"], core.db.DB_FILE)
    at.run()
    assert not any("being copied there" in m.value for m in at.markdown) and len(gh.puts()) == 1
