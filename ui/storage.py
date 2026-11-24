"""
Nivesa — where the book is kept, as the app sees it: the store's settings, the one replica per server
process, and what the notice rail says about it.

Settings (Streamlit secrets, or the environment as ``NIVESA_STORE_REPO`` / ``_TOKEN`` / ``_PATH`` /
``_BRANCH``):

    [storage]
    github_repo  = "owner/nivesa-data"     # a PRIVATE repository
    github_token = "github_pat_…"          # fine-grained: that repository only, Contents read and write
    path         = "portfolio.db"          # optional
    branch       = "main"                  # optional (default: the repository's default branch)

With no settings the book is the file under ``NIVESA_DATA_DIR``, as before — right on your own computer;
on Streamlit Community Cloud the rail warns that edits do not survive a restart.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import streamlit as st

import core.db as _db
from core.store import GitHubStore, Replica
from ui.components import render_header, render_notice_rail

_LOCK = threading.Lock()
_REPLICA: "dict[tuple, Replica]" = {}

#: Streamlit Community Cloud checks repositories out under /mount/src.
ON_STREAMLIT_CLOUD = str(Path(__file__).resolve()).startswith("/mount/src/")


def settings() -> "dict | None":
    env = {k: os.environ.get(f"NIVESA_STORE_{k.upper()}") for k in ("repo", "token", "path", "branch")}
    if env["repo"] and env["token"]:
        cfg = env
    else:
        try:
            sec = dict(st.secrets.get("storage", {}))
        except Exception:  # noqa: BLE001 — no secrets file is the ordinary local case
            sec = {}
        cfg = {"repo": sec.get("github_repo"), "token": sec.get("github_token"),
               "path": sec.get("path"), "branch": sec.get("branch")}
    if not (cfg["repo"] and cfg["token"]):
        return None
    return {"repo": str(cfg["repo"]).strip(), "token": str(cfg["token"]).strip(),
            "path": str(cfg["path"] or "portfolio.db").strip(), "branch": (str(cfg["branch"]).strip() or None)
            if cfg["branch"] else None}


def make_store(cfg: dict) -> GitHubStore:
    return GitHubStore(cfg["repo"], cfg["token"], cfg["path"], cfg["branch"])


def replica() -> "Replica | None":
    """This process's replica for the configured store (None when no store is configured)."""
    cfg = settings()
    if cfg is None:
        return None
    key = (cfg["repo"], cfg["path"], cfg["branch"], _db.DB_FILE)
    with _LOCK:
        if key not in _REPLICA:
            _REPLICA[key] = Replica(make_store(cfg), lambda: _db.DB_FILE)
        return _REPLICA[key]


def load_book() -> bool:
    """Before the database is opened: load the stored book. On failure draw why, with a retry, and
    return False — the caller stops the run, so no empty or stale copy is ever saved over the book."""
    rep = replica()
    if rep is None or rep.pull():
        return True
    render_header("NIVESA", "The book could not be loaded")
    render_notice_rail([{"kind": "danger", "title": "Not loaded",
                         "body": f"The ledger is kept in {rep.store.repo} and could not be read "
                                 f"({rep.pull_error}). Nothing has been opened or changed. Check the "
                                 f"[storage] settings in the app's secrets, then try again."}])
    if st.button("Try again", type="primary"):
        st.rerun()
    return False


def save_book() -> None:
    """After each run: upload the book if it changed. Failures surface in the rail on the next run."""
    rep = replica()
    if rep is not None:
        rep.push_if_changed()


def notices() -> "list[dict]":
    rep = replica()
    if rep is None:
        if ON_STREAMLIT_CLOUD:
            return [{"kind": "warning", "title": "Not kept",
                     "body": "This server keeps no files: edits made here are lost when Streamlit restarts "
                             "the app. Set up [storage] in the app's secrets to keep the ledger in a private "
                             "GitHub repository."}]
        return []
    if rep.created:
        return [{"kind": "warning", "title": "No ledger",
                 "body": f"There is no {rep.store.path} in {rep.store.repo} yet. To bring the existing ledger "
                         f"across, upload it there and reboot the app; otherwise the first entry made here "
                         f"creates it."}]
    if rep.conflict:
        return [{"kind": "danger", "title": "Not saved",
                 "body": f"The ledger in {rep.store.repo} was changed outside the app, so the latest changes "
                         f"made here were NOT saved there (nothing was overwritten). Reboot the app to load "
                         f"the stored ledger; changes made here since then will need entering again."}]
    if rep.push_error:
        return [{"kind": "danger", "title": "Not saved",
                 "body": f"The latest change could not be saved to {rep.store.repo} ({rep.push_error}). "
                         f"It is kept on this server and saving is retried on every action."}]
    return []
