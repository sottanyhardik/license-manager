# Phase 09 - Inventory Audit Report

Append-only audit log for Phase 9 Inventory work.

## backend/scripts/char_license_list_balance.py

- File Path(s): `backend/scripts/char_license_list_balance.py`
- Module: Inventory / License balance characterization scripts
- Total LOC: 133
- Lines Reviewed: 133 plus repository-wide dependency references
- Functions Reviewed: 4 (`_user`, `_rows_from_list`, `snapshot`, `main`)
- Classes Reviewed: 0
- Validation Improvements: Removed a stale ad hoc script path that accepted `record`/`check` modes, relied on a mutable dev database baseline file, and had no production validation, fixture isolation, or CI contract.
- Package Replacements: None; deletion was safer than refactoring because active deterministic balance coverage already exists in maintained test modules.
- Performance Improvements: Removed a one-off APIRequestFactory probe that executed license list/detail views and query capture against the dev database outside the normal test runner.
- Security Improvements: Removed an import-time `ALLOWED_HOSTS` mutation and unaudited superuser selection from an executable script.
- Dead Code Removed: Deleted the verified-dead characterization probe.
- Duplicate Logic Removed: Removed duplicate balance regression workflow covered by `backend/apps/license/tests/test_balance_calculator.py` and active API/export tests.
- Tests Added: None; no live caller remained. Existing balance regression coverage was run.
- Verification Results:
  - Repository-wide dependency scan excluding audit and legacy indexes found only self-references before deletion; no imports, CI hooks, management commands, docs guide workflow, tests, or runtime callers.
  - Broad `ruff check backend/scripts backend/apps/license/tests/test_balance_calculator.py` remains blocked by pre-existing findings in queued scripts `backend/scripts/test_balance_calc.py`, `backend/scripts/test_crud_balance_updates.py`, and `backend/scripts/verify_e5_plan.py`.
  - Scoped Ruff: `.venv/bin/ruff check backend/apps/license/tests/test_balance_calculator.py backend/apps/license/services/balance_calculator.py backend/scripts/golden_master_balance_exporters.py` -> clean.
  - `.venv/bin/python -m py_compile backend/scripts/golden_master_balance_exporters.py backend/scripts/test_balance_calc.py backend/apps/license/tests/test_balance_calculator.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/scripts` -> passed.
  - `.venv/bin/python -m pytest backend/apps/license/tests/test_balance_calculator.py -q` -> 30 passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations license --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - `git diff --check -- backend/scripts/char_license_list_balance.py` -> clean before source commit.
- Commit SHA: `1d7fb0713b09b25b7375f749c076a43b4734a9f0`
- Commit Timestamp: `2026-07-16T17:40:25+05:30`
- Commit Summary: `cleanup(inventory): remove stale balance probe`
- Blocked Items:
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `pip-audit`, `safety`, or `semgrep` executable.
- Remaining Technical Debt:
  - Adjacent queued inventory/balance items remain: `backend/scripts/test_balance_calc.py`, `docs/architecture/BALANCE_CALCULATION_CONSOLIDATION.md`, and `frontend/src/components/LicenseBalanceModal.tsx`.
- Status: DELETED

## backend/scripts/test_balance_calc.py

- File Path(s): `backend/scripts/test_balance_calc.py`
- Module: Inventory / License balance ad hoc scripts
- Total LOC: 54
- Lines Reviewed: 54 plus repository-wide dependency references
- Functions Reviewed: 1 (`test_balance_calculation`)
- Classes Reviewed: 0
- Validation Improvements: Removed an ad hoc dev database print script with no assertions, fixture isolation, CI contract, or deterministic expected values.
- Package Replacements: None; deletion was preferred because maintained balance tests already cover the logic.
- Performance Improvements: Removed a standalone script that queried the first five licenses and recalculated balance components outside the test runner.
- Security Improvements: Removed import-time Django setup and direct database reads from an unmanaged executable script.
- Dead Code Removed: Deleted verified-dead balance calculation print script.
- Duplicate Logic Removed: Removed duplicate manual balance verification path covered by `backend/apps/license/tests/test_balance_calculator.py`.
- Tests Added: None; existing balance regressions were run.
- Verification Results:
  - Repository-wide dependency scan found no live imports or runtime callers; remaining references are historical planning docs only.
  - `.venv/bin/ruff check backend/apps/license/tests/test_balance_calculator.py backend/apps/license/services/balance_calculator.py` -> clean.
  - `.venv/bin/python -m py_compile backend/apps/license/tests/test_balance_calculator.py backend/apps/license/services/balance_calculator.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/scripts backend/apps/license/tests/test_balance_calculator.py backend/apps/license/services/balance_calculator.py` -> passed.
  - `.venv/bin/python -m pytest backend/apps/license/tests/test_balance_calculator.py -q` -> 30 passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations license --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - `git diff --check -- backend/scripts/test_balance_calc.py` -> clean before source commit.
- Commit SHA: `8058036a1a16d037cdd27c99ba2a26e81d7ba395`
- Commit Timestamp: `2026-07-16T17:42:58+05:30`
- Commit Summary: `cleanup(inventory): remove stale balance test script`
- Blocked Items:
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `pip-audit`, `safety`, or `semgrep` executable.
- Remaining Technical Debt:
  - Adjacent queued inventory/balance items remain: `docs/architecture/BALANCE_CALCULATION_CONSOLIDATION.md` and `frontend/src/components/LicenseBalanceModal.tsx`.
- Status: DELETED

## docs/architecture/BALANCE_CALCULATION_CONSOLIDATION.md

- File Path(s): `docs/architecture/BALANCE_CALCULATION_CONSOLIDATION.md`
- Module: Inventory / License balance architecture documentation
- Total LOC: 133
- Lines Reviewed: 133 plus referenced balance implementation, command, and test contracts
- Functions Reviewed: 0
- Classes Reviewed: 0
- Validation Improvements: Replaced stale deployment-era checklist content with current validation contracts for `LicenseBalanceCalculator`, materialized `LicenseBalance` rows, CIF updates, migration backfill expectations, and API/export consumers.
- Package Replacements: None; no new dependency was required for a documentation-only architecture update.
- Performance Improvements: Document now records current pre-aggregation and materialized-row responsibilities instead of obsolete manual/probe workflows.
- Security Improvements: Removed stale server host, DuckDNS, old branch/version, old commit, and obsolete path references that could mislead production operators.
- Dead Code Removed: None in this metadata commit; source commit updated the live architecture document.
- Duplicate Logic Removed: Removed duplicate/obsolete balance-operation guidance already superseded by maintained service and management-command tests.
- Tests Added: None; documentation-only source change. Existing balance regression tests were run.
- Verification Results:
  - Dependency scan found the document remains live through `docs/README.md` and historical planning references; it was retained and updated rather than deleted.
  - Stale-marker scan confirmed obsolete `139.59`, `duckdns`, `debug_balance`, old commit IDs, old `backend/license/models.py`, and old branch/version references were removed.
  - `.venv/bin/ruff check backend/apps/license/services/balance_calculator.py backend/apps/license/management/commands/update_balance_cif.py backend/apps/license/tests/test_balance_calculator.py backend/apps/license/tests/test_update_balance_cif_command.py backend/tests/test_api_license.py` -> clean.
  - `.venv/bin/python -m py_compile backend/apps/license/services/balance_calculator.py backend/apps/license/management/commands/update_balance_cif.py backend/apps/license/tests/test_balance_calculator.py backend/apps/license/tests/test_update_balance_cif_command.py backend/tests/test_api_license.py` -> passed.
  - `.venv/bin/python -m compileall -q` scoped to balance service, command, and test files -> passed.
  - `.venv/bin/python -m pytest backend/apps/license/tests/test_balance_calculator.py backend/apps/license/tests/test_update_balance_cif_command.py -q` -> 36 passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations license --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - `git diff --check -- docs/architecture/BALANCE_CALCULATION_CONSOLIDATION.md` -> clean before source commit.
- Commit SHA: `a6246911dab2fcf96053f3e5b87dc6f92a93e74d`
- Commit Timestamp: `2026-07-16T17:50:32+05:30`
- Commit Summary: `docs(inventory): update balance architecture guide`
- Blocked Items:
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `pip-audit`, `safety`, or `semgrep` executable.
- Remaining Technical Debt:
  - Adjacent queued inventory/balance item remains: `frontend/src/components/LicenseBalanceModal.tsx`.
- Status: COMPLETED
