# 06 - Lint ratchet: unused imports (F401)

Status: enforced. `ruff check .` (config: `backend/ruff.toml`, ruff 0.17.5 pinned in
`backend/requirements-test.txt`) runs in the CI backend job and in
`scripts/dev/quality-gate.sh backend`, right after flake8. Any new unused import fails the gate.

## Config
- `backend/ruff.toml`: `target-version = "py314"`; excludes migrations, .venv/venv, htmlcov, staticfiles, media, node_modules.
- `select = ["F401"]` only. Nothing else is enabled (see "Not yet enforced").
- `[lint.per-file-ignores]` is empty: every remaining intentional unused import is suppressed inline with a reasoned `# noqa: F401`.

## Numbers
| | count |
|---|---|
| Baseline (`ruff --isolated --select F401`, migrations excluded) | 287 |
| Removed (import lines edited only) | 219 |
| Kept, `# noqa: F401  re-export` | 65 |
| Kept, `# noqa: F401  side-effect` (pytest fixtures) | 3 |
| Remaining unsuppressed | 0 |

Removed per area (hits): core 29, accounts 0, tasks 0, trade 6, reconciliation 1, bill_of_entry 1,
allotment 19, license 154 (plus 65 kept in two facades), backend/tests 2, scripts 3, setup 2, shared 4, lmanagement 1.

## Safety protocol
Before removal each hit was checked for consumers: `from <module> import <name>` (AST, relative imports
resolved, both new `api/` path and old shim path), `<module>.<name>` / `<last>.<name>` text and
`mock.patch` strings across backend, master-data-service, mds-client and scripts. Only the names with no
consumer were removed. Verified after each app: `compileall`, `manage.py check`, that app's test suite.
`__init__.py` files and sys.modules shims were not touched (no hits there).

## Explicit keeps
- `apps/license/models/core.py` (46 hits): facade of the license models package; names are re-exported to
  `apps.license.models`. Each import line carries `# noqa: F401  re-export`.
- `apps/license/api/views/item_pivot_report.py` (19 hits): facade module; names re-exported for old
  import paths and patches. Same marker.
- `apps/license/tests/test_item_pivot_totals_and_selection_rule.py`: `pivot_license, pivot_masters,
  superuser_client` are pytest fixtures imported from a sibling test module; they look unused but are
  consumed by pytest (removing them caused 4 test errors, caught by the app suite). `# noqa: F401  side-effect`.

## Not yet enforced (recorded debt, measured with `ruff --select F` after this change)
- F811 redefined-while-unused: 176
- F841 unused-variable: 50
- F541 f-string-missing-placeholders: 38
Ratchet these one rule at a time by adding the code to `select` after clearing it.

## Gotcha for future cleanups
Names imported only to be pytest fixtures, to register models/signals/tasks, or to be re-exported are
invisible to F401; keep them with a `noqa` and a reason rather than deleting.
