"""
Nivesa — the notice rail's plumbing: every message the app has for the reader lands here.

There are no ``st.success`` / ``st.error`` / ``st.info`` boxes and no toasts (rule 133): a form's
outcome, a validation error, a price check and the book's own standing caveats are all rows in the
one notice rail under the command bar.

  · ``set_notification`` — the 2.8.0 call, unchanged: the write paths queue their success message and
    rerun; the next render shows it as a notice (``drain_notifications``).
  · ``open_rail`` — the page shell reserves the rail's slot (an ``st.empty``) under the command bar and
    draws the notices it already has.
  · ``post_notice`` / ``form_error`` / ``form_warning`` — a message raised LATER in the same run (a form
    rejecting its input, then ``st.stop()``) is appended and the slot redrawn in place, so it still
    appears under the command bar, not where the form happened to be.

The run's notice list and slot live in session state, keyed per run, so two sessions never share them.
"""

from __future__ import annotations

import re

import streamlit as st

from ui.components import render_notice_rail

_SLOT = "_notice_slot"
_RUN = "_run_notices"
_BOLD = re.compile(r"\*\*(.+?)\*\*")

#: How a 2.8.0 notification type reads as a notice.
_FROM_TYPE = {"success": ("success", "Saved"), "error": ("danger", "Not saved"),
              "warning": ("warning", "Check"), "info": ("info", "Note")}


def set_notification(message, type="success"):
    """Store notification in session state to persist across rerun."""
    if "notifications" not in st.session_state:
        st.session_state["notifications"] = []
    st.session_state["notifications"].append({"message": message, "type": type})


def plain(message) -> str:
    """A 2.8.0 message as notice text: markdown bold markers dropped (the rail escapes everything)."""
    return _BOLD.sub(r"\1", str(message)).replace("`", "")


def drain_notifications() -> list[dict]:
    """The queued 2.8.0 notifications as notices, cleared once read (shown on exactly one render)."""
    queued = st.session_state.get("notifications") or []
    st.session_state["notifications"] = []
    out = []
    for n in queued:
        kind, title = _FROM_TYPE.get(n.get("type"), ("info", "Note"))
        out.append({"kind": kind, "title": title, "body": plain(n.get("message", ""))})
    return out


def _draw() -> None:
    slot = st.session_state.get(_SLOT)
    notices = st.session_state.get(_RUN) or []
    if slot is None:
        render_notice_rail(notices)
        return
    if notices:
        with slot.container():
            render_notice_rail(notices)


def open_rail(notices: list[dict]) -> None:
    """Reserve the notice rail's slot here (under the command bar) and draw ``notices`` into it."""
    st.session_state[_RUN] = list(notices)
    st.session_state[_SLOT] = st.empty()
    _draw()


def post_notice(kind: str, title: str, body: str) -> None:
    """Add a notice to this run's rail and redraw it in place."""
    st.session_state.setdefault(_RUN, []).append({"kind": kind, "title": title, "body": plain(body)})
    _draw()


def form_error(message) -> None:
    """A rejected entry — the 2.8.0 ``st.error`` text, as a danger notice."""
    post_notice("danger", "Not saved", message)


def form_warning(message) -> None:
    """A check the entry should pass before it is saved — the 2.8.0 ``st.warning`` text (its leading
    "Warning: " is the notice's own title now)."""
    text = str(message)
    post_notice("warning", "Check", text[len("Warning: "):] if text.startswith("Warning: ") else text)
