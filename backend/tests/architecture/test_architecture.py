"""Pure-AST architecture guardrails (ADR-003). No Django, no DB, no new deps.

Scans backend/apps/**/*.py excluding tests/ and migrations/. Path-agnostic
within an app (api/, services/, shims, etc. all count as the same app).
"""
import ast
from pathlib import Path

APPS_DIR = Path(__file__).resolve().parents[2] / "apps"
DOMAIN_APPS = {"license", "allotment", "bill_of_entry", "trade", "reconciliation", "tasks", "accounting"}
ALL_APPS = DOMAIN_APPS | {"accounts", "core"}

# Baseline of module-level cross-app import edges (from_app, to_app), 2026-11-16.
# Ratchet: new edges fail. Removing edges is welcome: delete them from this set.
ALLOWED_EDGES = {
    # ADR-004: accounting depends on core + trade one-way; trade must never import accounting.
    ("accounting", "accounts"),
    ("accounting", "core"),
    ("accounting", "license"),  # E2E seed command creates licence fixtures (test_* DB only)
    ("accounting", "trade"),
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


# ---------------------------------------------------------------------------
# Extended rules (shrink-only ratchets). Baselines dated 2026-11-16.
# Keys use (app, module basename), never the full path, so file moves and
# sys.modules shim files (which contain no writes/underscore imports) are safe.
# ---------------------------------------------------------------------------
from collections import Counter  # noqa: E402

WRITE_ATTRS = {
    "save", "delete", "create", "update", "bulk_create", "bulk_update",
    "get_or_create", "update_or_create",
}
FINANCIAL_MODELS = {
    "RowDetails", "AllotmentItems", "AllotmentModel", "LicenseImportItemsModel",
    "LicenseTrade", "LicenseTradeLine", "LicenseTradePayment",
    "BOEAllotmentAllocation", "InvoiceBOEAllocation", "LicenseBalance",
}
DOMAIN_FORBIDDEN = ("django.db", "rest_framework", "requests", "celery", "redis")

# Rule: no new app-level dependency cycle. SCCs (sets of mutually reachable apps)
# that already exist; a new SCC or a larger one fails and prints a cycle path.
CYCLE_BASELINE = {frozenset({'accounts', 'allotment', 'bill_of_entry', 'core', 'license', 'trade'})}
# Rule: cross-app private imports, (src_app, module, name).
PRIVATE_IMPORT_BASELINE = {('trade', 'apps.core.helpers', '_sync_nested'), ('allotment', 'apps.core.utils.exceptions', '_safe_int')}
# Rule: ORM write calls in view modules, (app, module basename) -> count.
VIEW_WRITE_BASELINE = {('accounts', 'password'): 2,
 ('accounts', 'user_management'): 1,
 ('allotment', 'views'): 2,
 ('allotment', 'views_actions'): 6,
 ('allotment', 'views_export'): 1,
 ('bill_of_entry', 'views_parse_pdf'): 1,
 ('bill_of_entry', 'views_export'): 2,
 ('core', 'master_view'): 5,
 ('core', 'throttle_status'): 1,
 ('core', 'views'): 3,
 ('license', 'active_licenses_report'): 2,
 ('license', 'expiring_licenses_report'): 2,
 ('license', 'inventory_balance_report'): 1,
 ('license', 'item_pivot_excel'): 2,
 ('license', 'item_pivot_generate'): 3,
 ('license', 'item_report'): 2,
 ('license', 'ledger'): 11,
 ('license', 'license'): 4,
 ('license', 'license_balance_ledger'): 1,
 ('license', 'license_overview'): 1,
 ('license', 'license_purchase_profit_report'): 1,
 ('license', 'parse_pdf'): 3,
 ('license', 'planned_report'): 1,
 ('license', 'sion_planning_rule'): 13,
 ('license', 'views_actions'): 12,
 ('reconciliation', 'views'): 5,
 ('tasks', 'views'): 3,
 ('trade', 'views'): 2,
 ('trade', 'views_invoice_documents'): 2}
# Rule: direct financial-model writes outside services, (app, basename, Model) -> count.
FINANCIAL_WRITE_BASELINE = {('allotment', 'backfill_allocation_status', 'AllotmentItems'): 1,
 ('bill_of_entry', 'serializers', 'RowDetails'): 4,
 ('core', 'clean_duplicate_rowdetails', 'RowDetails'): 1,
 ('core', 'ledger', 'LicenseImportItemsModel'): 2,
 ('core', 'ledger', 'RowDetails'): 2,
 ('core', 'sync_from_ge_server', 'LicenseBalance'): 1,
 ('license', '_license_write', 'LicenseImportItemsModel'): 2,
 ('license', 'delete_licenses_by_exporter', 'AllotmentItems'): 1,
 ('license', 'delete_licenses_by_exporter', 'RowDetails'): 1,
 ('license', 'header', 'LicenseBalance'): 1,
 ('license', 'parse_existing_license_copies', 'LicenseImportItemsModel'): 1,
 ('accounting', 'seed_accounting_e2e', 'LicenseImportItemsModel'): 1,  # disposable test_* E2E seed
 ('accounting', 'seed_accounting_e2e', 'LicenseTrade'): 1,
 ('accounting', 'seed_accounting_e2e', 'LicenseTradeLine'): 1,
 ('license', 'seed_browser_2509', 'AllotmentItems'): 2,
 ('license', 'seed_browser_2509', 'AllotmentModel'): 2,
 ('license', 'seed_browser_2509', 'LicenseBalance'): 2,
 ('license', 'seed_browser_2509', 'LicenseImportItemsModel'): 2,
 ('license', 'seed_browser_2509', 'LicenseTrade'): 2,
 ('license', 'seed_browser_2509', 'LicenseTradeLine'): 2,
 ('license', 'signals', 'LicenseBalance'): 1,
 ('license', 'signals', 'LicenseImportItemsModel'): 1,
 ('license', 'sync_licenses', 'LicenseBalance'): 1,
 ('license', 'sync_licenses', 'LicenseImportItemsModel'): 1,
 ('license', 'update_balance_cif', 'LicenseBalance'): 1,
 ('trade', 'models', 'LicenseTrade'): 2,
 ('trade', 'serializers', 'LicenseTrade'): 1,
 ('trade', 'serializers', 'LicenseTradeLine'): 1,
 ('trade', 'serializers', 'LicenseTradePayment'): 1}


def _find_cycle_in(nodes, edges):
    """Return one cycle path (list, first==last) inside the node set, or None."""
    adj = {n: sorted(d for s, d in edges if s == n and d in nodes) for n in nodes}
    for start in sorted(nodes):
        stack, seen = [(start, [start])], set()
        while stack:
            cur, path = stack.pop()
            for nxt in adj[cur]:
                if nxt == start:
                    return path + [start]
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append((nxt, path + [nxt]))
    return None


def _sccs(edges):
    nodes = {n for e in edges for n in e}
    reach = {n: {n} for n in nodes}
    changed = True
    while changed:
        changed = False
        for s, d in edges:
            new = reach[d] - reach[s]
            if new:
                reach[s] |= new
                changed = True
    comps = {frozenset(m for m in reach[n] if n in reach[m]) for n in nodes}
    return {c for c in comps if len(c) > 1}


def test_no_new_app_dependency_cycles():
    comps = _sccs(_cross_app_edges())
    edges = _cross_app_edges()
    new = [c for c in comps if not any(c <= b for b in CYCLE_BASELINE)]
    msgs = [f"{sorted(c)} e.g. {' -> '.join(_find_cycle_in(set(c), edges) or [])}" for c in new]
    assert not new, "New app-level dependency cycle(s):\n" + "\n".join(msgs)


def _private_cross_app_imports():
    found = set()
    for rel, tree in _modules():
        src = rel.parts[0]
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                dst = _target_app(node.module)
                if not dst or dst == src:
                    continue
                for a in node.names:
                    if a.name.startswith("_") and not a.name.startswith("__"):
                        found.add((src, node.module, a.name))
    return found


def test_no_new_cross_app_private_imports():
    found = _private_cross_app_imports()
    new, removed = sorted(found - PRIVATE_IMPORT_BASELINE), sorted(PRIVATE_IMPORT_BASELINE - found)
    print(f"\nNEW private imports: {new}\nREMOVED (shrink baseline): {removed}")
    assert not new, f"Importing another app's underscore-prefixed names is forbidden: {new}"


def _is_view_module(rel):
    dirs, name = rel.parts[1:-1], rel.name
    return (
        any(d == "views" or d.startswith("views_") for d in dirs)
        or (dirs and dirs[-1] == "api" and name.startswith("views"))
        or name.startswith("views")
    )


def _write_calls(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in WRITE_ATTRS:
            yield node


def test_views_orm_writes_do_not_grow():
    """Heuristic for 'business logic in views': count ORM write-looking calls
    (.save/.delete/.create/.update/bulk_*/get_or_create/update_or_create) in
    view modules (any */views*/**, */api/views*, views*.py). Receiver is not
    resolved, so serializer.save() is counted too; that is fine for a ratchet.
    Keyed (app, module basename) so moves/shims do not break it. A count may
    only fall; a new view module must start at 0."""
    counts = Counter()
    for rel, tree in _modules():
        if _is_view_module(rel):
            n = sum(1 for _ in _write_calls(tree))
            if n:
                counts[(rel.parts[0], rel.stem)] += n
    grew = {k: (VIEW_WRITE_BASELINE.get(k, 0), v) for k, v in counts.items() if v > VIEW_WRITE_BASELINE.get(k, 0)}
    shrunk = {k: v for k, v in VIEW_WRITE_BASELINE.items() if counts.get(k, 0) < v}
    print(f"\nGREW (baseline, now): {grew}\nSHRUNK (lower baseline): {shrunk}")
    assert not grew, f"ORM writes in views increased; move them to services: {grew}"


def _financial_receiver(call):
    node = call.func.value
    while True:
        if isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Attribute):
            if node.attr == "objects" and isinstance(node.value, ast.Name) and node.value.id in FINANCIAL_MODELS:
                return node.value.id
            node = node.value
        else:
            return None


def test_financial_writes_outside_services_do_not_grow():
    counts = Counter()
    for rel, tree in _modules():
        if "services" in rel.parts:
            continue
        for call in _write_calls(tree):
            model = _financial_receiver(call)
            if model:
                counts[(rel.parts[0], rel.stem, model)] += 1
    grew = {k: (FINANCIAL_WRITE_BASELINE.get(k, 0), v) for k, v in counts.items() if v > FINANCIAL_WRITE_BASELINE.get(k, 0)}
    shrunk = {k: v for k, v in FINANCIAL_WRITE_BASELINE.items() if counts.get(k, 0) < v}
    print(f"\nGREW (baseline, now): {grew}\nSHRUNK (lower baseline): {shrunk}")
    assert not grew, f"Financial-model writes outside services/ increased: {grew}"


def test_domain_packages_are_pure():
    bad = []
    for rel, tree in _modules():
        if "domain" not in rel.parts[1:-1]:
            continue
        for mod in _all_imports(tree):
            if any(mod == f or mod.startswith(f + ".") for f in DOMAIN_FORBIDDEN):
                bad.append(f"{rel}: {mod}")
    assert not bad, "domain/ must stay framework-free:\n" + "\n".join(sorted(set(bad)))
