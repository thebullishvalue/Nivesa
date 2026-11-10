"""
The 3.0 refactor moved Nivesa's business logic out of the 2.8.0 single file WITHOUT editing it.

  · every moved function's source is character-for-character the original's (only the module moved);
  · every moved constant's assignment is the original's (VERSION / BUILD are the only new values);
  · every original top-level function is accounted for — moved, or retired with the UI it drew;
  · the dashboard aggregates lifted into ``core.views`` keep the original statements verbatim (every
    code line not marked ``# seam`` appears in the original);
  · the four forms' submit handlers (validation, writes, face adjustments, chronology rollback) are the
    original handlers, modulo the listed presentation substitutions (``st.error`` → the notice rail,
    button labels).

The original is ``tests/golden/app_2_8_0.py`` = ``git show 8090864:app.py``.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ORIGINAL = REPO / "tests" / "golden" / "app_2_8_0.py"
ORIG_SRC = ORIGINAL.read_text(encoding="utf-8")
ORIG_TREE = ast.parse(ORIG_SRC)

MOVED = {
    "core/db.py": ["db_init", "_connect", "db_query", "db_execute", "ensure_metadata", "validate_ledger_chronology",
                   "face_step_claimed", "claim_face_adjustment", "release_face_adjustment"],
    "core/formatting.py": ["esc", "fmt_inr", "fmt_inr_short", "fmt_pct"],
    "core/bonds.py": ["day_count_fraction", "prev_coupon_date", "accrued_at", "calc_accrued_interest",
                      "calc_macaulay_duration", "calc_modified_duration", "calc_yield_to_cost", "_xirr",
                      "calc_position_yield_to_cost", "generate_amortizing_schedule", "calc_days_to_maturity",
                      "generate_cashflow_schedule"],
    "core/book.py": ["get_positions_dataframe", "get_transaction_ledger_dataframe", "_maturity_bucket"],
    "ui/notices.py": ["set_notification"],
    "ui/pages/_forms.py": ["_safe_index"],
}
#: Original functions that drew the 2.8.0 UI and are replaced by the Graphite shell and components.
RETIRED = {"load_css", "show_notifications", "rating_badge", "_render_metric", "_render_html_table", "page_dashboard",
           "get_icon", "_render_section_header", "page_add_security", "page_edit_security",
           "page_record_transaction", "page_edit_transaction", "page_view_transactions", "page_securities_master",
           "_render_footer", "main"}
CONSTANTS = {
    "core/config.py": ["PRODUCT_NAME", "PRODUCT_DEVANAGARI", "COMPANY", "TAGLINE", "ACCOUNTS", "FREQUENCIES",
                       "FREQ_MAP", "BOND_TYPES", "CREDIT_RATINGS", "DAY_COUNT_CONVENTIONS", "TRANSACTION_TYPES",
                       "FLOW_ORDER", "DATA_DIR", "LOG_DIR", "DB_DIR", "DB_FILE", "LOG_FILE", "logger"],
    "core/book.py": ["MATURITY_BUCKET_ORDER"],
}


def _functions(src: str, tree: ast.Module) -> dict[str, str]:
    """Each top-level function as its WHOLE source lines (decorators excluded; none are used) — whole
    lines, so a trailing comment on the last statement is compared too."""
    lines = src.splitlines()
    return {n.name: "\n".join(lines[n.lineno - 1:n.end_lineno]) for n in tree.body if isinstance(n, ast.FunctionDef)}


def _assigns(src: str, tree: ast.Module) -> dict[str, str]:
    out = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            out[n.targets[0].id] = ast.get_source_segment(src, n)
    return out


def _module(rel: str) -> tuple[str, ast.Module]:
    src = (REPO / rel).read_text(encoding="utf-8")
    return src, ast.parse(src)


ORIG_FUNCS = _functions(ORIG_SRC, ORIG_TREE)


@pytest.mark.parametrize("rel,name", [(rel, n) for rel, names in MOVED.items() for n in names])
def test_moved_function_is_byte_identical(rel, name):
    src, tree = _module(rel)
    new = _functions(src, tree)
    assert name in new, f"{name} missing from {rel}"
    assert new[name] == ORIG_FUNCS[name], f"{rel}:{name} differs from the 2.8.0 original"


def test_every_original_function_is_moved_or_retired():
    moved = {n for names in MOVED.values() for n in names}
    assert moved.isdisjoint(RETIRED)
    assert set(ORIG_FUNCS) == moved | RETIRED, sorted(set(ORIG_FUNCS) ^ (moved | RETIRED))


@pytest.mark.parametrize("rel,name", [(rel, n) for rel, names in CONSTANTS.items() for n in names])
def test_moved_constant_is_identical(rel, name):
    src, tree = _module(rel)
    assert _assigns(src, tree)[name] == _assigns(ORIG_SRC, ORIG_TREE)[name]


def test_config_side_effects_are_the_originals():
    """The data directories and the log file are created and configured exactly as before."""
    src = (REPO / "core/config.py").read_text(encoding="utf-8")
    for n in ORIG_TREE.body:
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
            seg = ast.get_source_segment(ORIG_SRC, n)
            if seg.startswith(("os.makedirs", "logging.basicConfig")):
                assert seg in src, seg


def test_version_is_3():
    from core.config import BUILD, VERSION
    assert VERSION.startswith("3.") and BUILD == "2026.11.GRAPHITE"


# ── core.views: the lifted dashboard aggregates ──────────────────────────────
LIFTED = ["add_weight_columns", "account_options", "capital_allocation", "issuer_concentration", "positions_table",
          "positions_export", "maturity_ladder", "maturity_rows", "cashflow_projection", "cashflow_totals",
          "nearterm_cashflows", "issuer_detail", "ledger_tab", "ledger_page", "securities_master"]


@pytest.mark.parametrize("name", LIFTED)
def test_lifted_view_statements_are_verbatim(name):
    src, tree = _module("core/views.py")
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    orig_lines = {ln.strip() for ln in ORIG_SRC.splitlines()}
    # whole lines (a source segment would cut the trailing "# seam" off the last statement)
    body = src.splitlines()[fn.lineno:fn.end_lineno]                 # drop the def line
    doc = fn.body[0]
    skip = set()
    if isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant) and isinstance(doc.value.value, str):
        skip = set(range(doc.lineno - fn.lineno - 1, doc.end_lineno - fn.lineno))
    checked = 0
    for i, ln in enumerate(body):
        s = ln.strip()
        if i in skip or not s or s.startswith("#") or s.endswith("# seam"):
            continue
        assert s in orig_lines, f"core.views.{name}: not in the 2.8.0 source: {s!r}"
        checked += 1
    assert checked > 0 or name in ("account_options",)


# ── the forms' submit handlers ───────────────────────────────────────────────
#: The ONLY substitutions allowed between a 2.8.0 handler and its 3.0 port (presentation, not logic).
SUBS = (
    ("st.error(", "form_error("),
    ("st.warning(", "form_warning("),
    ('st.form_submit_button("ADD SECURITY")', 'st.form_submit_button("Add security", type="primary")'),
    ('st.form_submit_button("UPDATE SECURITY")', 'st.form_submit_button("Update security", type="primary")'),
    ('st.form_submit_button("RECORD TRANSACTION")', 'st.form_submit_button("Record transaction", type="primary")'),
)
HANDLERS = (
    # (original function, new module, new function, first line of the handler block in the original)
    ("page_add_security", "ui/pages/page_add_security.py", "render_add_security_page",
     '        submitted = st.form_submit_button("ADD SECURITY")'),
    ("page_edit_security", "ui/pages/page_edit_security.py", "render_edit_security_page",
     '        if st.form_submit_button("UPDATE SECURITY"):'),
    ("page_record_transaction", "ui/pages/page_record_transaction.py", "render_record_transaction_page",
     '        if st.form_submit_button("RECORD TRANSACTION"):'),
    ("page_edit_transaction", "ui/pages/page_edit_transaction.py", "render_edit_transaction_page",
     "        if update_btn:"),
)


def _sub(text: str) -> str:
    for a, b in SUBS:
        text = text.replace(a, b)
    return text


@pytest.mark.parametrize("orig,rel,new,marker", HANDLERS)
def test_form_handler_is_the_original(orig, rel, new, marker):
    o = ORIG_FUNCS[orig]
    assert o.count(marker) == 1
    want = _sub(o[o.index(marker):])
    src, tree = _module(rel)
    n = _functions(src, tree)[new]
    start = _sub(marker)
    assert n.count(start) == 1, f"{rel}: handler start not found"
    assert n[n.index(start):] == want, f"{rel}: the submit handler differs from 2.8.0's"
    # and the write path really is in it
    assert any(k in want for k in ("db_execute(", "c.execute("))
