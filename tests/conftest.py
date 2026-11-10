"""Shared test setup.

The suite NEVER touches the tracked ``data/`` (the owner's real book): before anything imports
``core.config`` (which reads ``NIVESA_DATA_DIR`` once, at import), the whole ``data/`` tree is copied
into a throwaway directory and ``NIVESA_DATA_DIR`` is pointed at the copy. Everything runs offline.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
for _p in (str(TESTS / "golden"), str(TESTS), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SCRATCH = Path(tempfile.mkdtemp(prefix="nivesa-test-"))
DATA_COPY = _SCRATCH / "data"
shutil.copytree(REPO / "data", DATA_COPY)
os.environ["NIVESA_DATA_DIR"] = str(DATA_COPY)
assert Path(os.environ["NIVESA_DATA_DIR"]).resolve() != (REPO / "data").resolve()

import logging  # noqa: E402

logging.getLogger().setLevel(logging.ERROR)
