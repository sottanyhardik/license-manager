"""Pure-AST architecture guardrails (ADR-003). No Django, no DB, no new deps.

Scans backend/apps/**/*.py excluding tests/ and migrations/. Path-agnostic
within an app (api/, services/, shims, etc. all count as the same app).
"""
import ast
from pathlib import Path

APPS_DIR = Path(__file__).resolve().parents[2] / "apps"
DOMAIN_APPS = {"license", "allotment", "bill_of_entry", "trade", "reconciliation", "tasks"}
ALL_APPS = DOMAIN_APPS | {"accounts", "core"}

# Baseline of module-level cross-app import edges (from_app, to_app), 2026-11-16.
# Ratchet: new edges fail. Removing edges is welcome: delete them from this set.
ALLOWED_EDGES = {
    ("accounts", "core"),
    ("allotment", "accounts"),
    ("allotment", "bill_of_entry"),
    ("allotment", "core"),
    ("allotment", "license"),
    ("bill_of_entry", "accounts"),
    ("bill_of_entry", "allotment"),
    ("bill_of_entry", "core"),
    ("bill_of_entry", "license"),
    ("core", "accounts"),
    ("core", "allotment"),
    ("core", "bill_of_entry"),
    ("core", "license"),
    ("license", "accounts"),
    ("license", "allotment"),
    ("license", "bill_of_entry"),
    ("license", "core"),
    ("license", "trade"),
    ("reconciliation", "accounts"),
    ("reconciliation", "bill_of_entry"),
    ("reconciliation", "core"),
    ("reconciliation", "license"),
    ("reconciliation", "trade"),
    ("tasks", "core"),
    ("trade", "accounts"),
    ("trade", "bill_of_entry"),
    ("trade", "core"),
    ("trade", "license"),
}

# Known module-level core -> domain imports on the baseline date (rule 5 debt).
# Keyed by (path relative to apps/, imported module). Must only shrink.
CORE_DOMAIN_IMPORT_BASELINE = {
    ("core/management/commands/_item_linking.py", "apps.license.models"),
    ("core/management/commands/clean_duplicate_rowdetails.py", "apps.bill_of_entry.models"),
    ("core/management/commands/convert_docx_to_pdf.py", "apps.allotment.scripts.aro"),
    ("core/management/commands/fetch_detail_bisc.py", "apps.license.models"),
    ("core/management/commands/merge_cardamom_item_names.py", "apps.license.models"),
    ("core/management/commands/merge_item_name_duplicates.py", "apps.allotment.models"),
    ("core/management/commands/merge_item_name_duplicates.py", "apps.bill_of_entry.models"),
    ("core/management/commands/merge_item_name_duplicates.py", "apps.license.models"),
    ("core/management/commands/merge_norm_suffixed_item_names.py", "apps.license.models"),
    ("core/management/commands/report_fetch.py", "apps.license.models"),
    ("core/management/commands/seed_e132_plan_items.py", "apps.license.services.e132_plan"),
    ("core/management/commands/verify_item_name_merge.py", "apps.allotment.models"),
    ("core/management/commands/verify_item_name_merge.py", "apps.bill_of_entry.models"),
    ("core/management/commands/verify_item_name_merge.py", "apps.license.models"),
}

BALANCE_NAMES = {"calculate_balance", "calculate_financial_balance", "_calculate_financial_balance"}


def _modules():
    for path in sorted(APPS_DIR.rglob("*.py")):
        rel = path.relative_to(APPS_DIR)
        if "tests" in rel.parts or "migrations" in rel.parts or rel.name.startswith("test_"):
            continue
        yield rel, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _module_level_imports(tree):
    """Imported module names from top-level statements (incl. top-level
    if/try/with blocks), excluding def/class bodies."""
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module
        else:
            for field in ("body", "orelse", "finalbody", "handlers"):
                stack.extend(getattr(node, field, []) or [])


def _target_app(module):
    parts = module.split(".")
    if len(parts) >= 2 and parts[0] == "apps" and parts[1] in ALL_APPS:
        return parts[1]
    return None


def _all_imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module
            for a in node.names:  # `from apps.x import views`
                yield f"{node.module}.{a.name}"


def _cross_app_edges():
    edges = set()
    for rel, tree in _modules():
        src = rel.parts[0]
        if src not in ALL_APPS:
            continue
        for mod in _module_level_imports(tree):
            dst = _target_app(mod)
            if dst and dst != src:
                edges.add((src, dst))
    return edges


def _core_domain_imports():
    found = set()
    for rel, tree in _modules():
        if rel.parts[0] != "core":
            continue
        for mod in _module_level_imports(tree):
            if _target_app(mod) in DOMAIN_APPS:
                found.add((rel.as_posix(), mod))
    return found


def test_core_has_no_new_module_level_domain_imports():
    found = _core_domain_imports()
    new, removed = sorted(found - CORE_DOMAIN_IMPORT_BASELINE), sorted(CORE_DOMAIN_IMPORT_BASELINE - found)
    print(f"\nNEW core->domain imports: {new}\nREMOVED (shrink baseline): {removed}")
    assert not new, f"core must not import domain apps at module level: {new}"


def test_cross_app_import_edges_ratchet():
    edges = _cross_app_edges()
    new, removed = sorted(edges - ALLOWED_EDGES), sorted(ALLOWED_EDGES - edges)
    print(f"\nNEW edges (not allowed): {new}\nREMOVED edges (shrink baseline): {removed}")
    assert not new, f"New cross-app module-level import edges: {new}. Use services/selectors or a reviewed function-level import."


def test_no_cross_app_views_imports():
    # core.views hosts the shared MasterViewSet kernel and is allowed as a target;
    # views of the domain apps must never be imported from another app.
    bad = set()
    for rel, tree in _modules():
        src = rel.parts[0]
        for mod in _all_imports(tree):
            dst = _target_app(mod)
            if dst and dst not in (src, "core") and any(p == "views" or p.startswith("views_") for p in mod.split(".")[2:]):
                bad.add(f"{rel}: {mod}")
    assert not bad, "Importing another app's views is forbidden:\n" + "\n".join(sorted(bad))


def test_single_balance_engine():
    bad = []
    for rel, tree in _modules():
        if rel.parts[0] == "license" and len(rel.parts) > 1 and rel.parts[1] == "services":
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in BALANCE_NAMES:
                bad.append(f"{rel}:{node.lineno} {node.name}")
    assert not bad, "Balance math must live in apps/license/services/:\n" + "\n".join(bad)
