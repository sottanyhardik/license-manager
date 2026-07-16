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
