# Phase 8 Bills of Entry Audit Report

## backend/apps/bill_of_entry/__init__.py

- File Path(s): `backend/apps/bill_of_entry/__init__.py`
- Module: Bills of Entry / Django app package marker
- Total LOC: 0
- Lines Reviewed: 0-byte file verified with `wc -l` and `xxd`; every possible line/import/symbol/side effect is absent.
- Functions Reviewed: 0
- Classes Reviewed: 0
- Validation Improvements: None required; the package marker has no input handling, serializers, forms, API paths, commands, parsers, uploads, exports, transactions, or database access.
- Package Replacements: None
- Performance Improvements: None required; no executed code exists.
- Security Improvements: None required; no executable code, imports, URL handling, file handling, SQL, template rendering, or request handling exists.
- Dead Code Removed: None
- Duplicate Logic Removed: None
- Tests Added: None; no behavior exists to regress.
- Verification Results:
  - `wc -l backend/apps/bill_of_entry/__init__.py` -> 0 lines.
  - `xxd -g 1 backend/apps/bill_of_entry/__init__.py` -> empty output.
  - `.venv/bin/ruff check backend/apps/bill_of_entry/__init__.py` -> clean.
  - `.venv/bin/python -m py_compile backend/apps/bill_of_entry/__init__.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/apps/bill_of_entry/__init__.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations bill_of_entry --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - `python3 -m json.tool docs/audit/audit-database.json` -> valid JSON.
  - `python3 -m json.tool docs/audit/repository-knowledge-graph.json` -> valid JSON.
- Blocked Items:
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `pip-audit`, `safety`, or `semgrep` executable.
- Remaining Technical Debt:
  - None for this package marker.
- Status: COMPLETED

## backend/apps/bill_of_entry/scripts/__init__.py

- File Path(s): `backend/apps/bill_of_entry/scripts/__init__.py`
- Module: Bills of Entry / Scripts package marker
- Total LOC: 0
- Lines Reviewed: 0-byte file verified with `wc -l` and `xxd`; every possible line/import/symbol/side effect is absent.
- Functions Reviewed: 0
- Classes Reviewed: 0
- Validation Improvements: None required; no script entrypoints, arguments, shell calls, file reads, or runtime validation paths exist.
- Package Replacements: None
- Performance Improvements: None required; no executed code exists.
- Security Improvements: None required; no executable code, imports, subprocess usage, path handling, file handling, or network calls exist.
- Dead Code Removed: None
- Duplicate Logic Removed: None
- Tests Added: None; no behavior exists to regress.
- Verification Results:
  - `wc -l backend/apps/bill_of_entry/scripts/__init__.py` -> 0 lines.
  - `xxd -g 1 backend/apps/bill_of_entry/scripts/__init__.py` -> empty output.
  - `.venv/bin/ruff check backend/apps/bill_of_entry/scripts/__init__.py` -> clean.
  - `.venv/bin/python -m py_compile backend/apps/bill_of_entry/scripts/__init__.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/apps/bill_of_entry/scripts/__init__.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations bill_of_entry --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
- Blocked Items:
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `pip-audit`, `safety`, or `semgrep` executable.
- Remaining Technical Debt:
  - None for this package marker.
- Status: COMPLETED

## backend/apps/bill_of_entry/parsers/__init__.py

- File Path(s): `backend/apps/bill_of_entry/parsers/__init__.py`
- Module: Bills of Entry / Parser package marker
- Total LOC: 0
- Lines Reviewed: 0-byte file verified with `wc -l` and `xxd`; every possible line/import/symbol/side effect is absent.
- Functions Reviewed: 0
- Classes Reviewed: 0
- Validation Improvements: None required; no parser functions, file reads, decoding paths, upload handling, or runtime validation paths exist.
- Package Replacements: None
- Performance Improvements: None required; no executed code exists.
- Security Improvements: None required; no executable code, imports, file handling, PDF parsing, path handling, or request handling exists.
- Dead Code Removed: None
- Duplicate Logic Removed: None
- Tests Added: None; no behavior exists to regress.
- Verification Results:
  - `wc -l backend/apps/bill_of_entry/parsers/__init__.py` -> 0 lines.
  - `xxd -g 1 backend/apps/bill_of_entry/parsers/__init__.py` -> empty output.
  - `.venv/bin/ruff check backend/apps/bill_of_entry/parsers/__init__.py` -> clean.
  - `.venv/bin/python -m py_compile backend/apps/bill_of_entry/parsers/__init__.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/apps/bill_of_entry/parsers/__init__.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations bill_of_entry --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
- Blocked Items:
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `pip-audit`, `safety`, or `semgrep` executable.
- Remaining Technical Debt:
  - None for this package marker.
- Status: COMPLETED

## backend/apps/bill_of_entry/migrations/0001_initial.py

- File Path(s): `backend/apps/bill_of_entry/migrations/0001_initial.py`
- Module: Bills of Entry / Initial Django migration
- Total LOC: 75
- Lines Reviewed: 75
- Functions Reviewed: 0
- Classes Reviewed: 1 (`Migration`)
- Validation Improvements: None applied; this historical migration already encodes non-negative decimal validators for exchange rate, CIF INR, CIF FC, and quantity fields.
- Package Replacements: None; standard Django migration primitives, `Decimal`, swappable user dependency, and model field declarations are appropriate.
- Performance Improvements: None applied; follow-up migration `0002_initial.py` intentionally adds lookup indexes after dependent license migration availability.
- Security Improvements: Reviewed file upload path, FK deletion behavior, nullable audit-user FKs, validators, and absence of executable data operations. No migration rewrite was safe or necessary.
- Dead Code Removed: None
- Duplicate Logic Removed: None
- Tests Added: None; no behavior changed.
- Verification Results:
  - Line-by-line review covered imports, dependencies, `BillOfEntryModel` field declarations/options, `RowDetails` field declarations/options, FK/M2M relationships, validators, defaults, and follow-up migration compatibility.
  - `.venv/bin/ruff check backend/apps/bill_of_entry/migrations/0001_initial.py` -> clean.
  - `.venv/bin/python -m py_compile backend/apps/bill_of_entry/migrations/0001_initial.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/apps/bill_of_entry/migrations/0001_initial.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations bill_of_entry --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - Configured migration import verification with `DJANGO_SETTINGS_MODULE=lmanagement.settings` -> `initial=True`, 3 dependencies, 2 operations.
  - `git diff --check -- backend/apps/bill_of_entry/migrations/0001_initial.py` -> clean.
- Blocked Items:
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `pip-audit`, `safety`, or `semgrep` executable.
- Remaining Technical Debt:
  - None for this migration. Semantic model behavior remains queued for the model/service/API files that own runtime validation.
- Status: COMPLETED

## backend/apps/bill_of_entry/migrations/0002_initial.py

- File Path(s): `backend/apps/bill_of_entry/migrations/0002_initial.py`
- Module: Bills of Entry / Secondary initial Django migration
- Total LOC: 58
- Lines Reviewed: 58
- Functions Reviewed: 0
- Classes Reviewed: 1 (`Migration`)
- Validation Improvements: None applied; the migration preserves the historical FK and uniqueness constraints generated by Django.
- Package Replacements: None; Django migration primitives and model index declarations are appropriate.
- Performance Improvements: Reviewed seven explicit `BillOfEntryModel` indexes for BOE number, company/date, port/date, date, invoice/date, fetch status, and product-name lookup paths. No historical migration rewrite was safe or needed.
- Security Improvements: Reviewed cascade behavior on `RowDetails.sr_number`, unique constraints that reduce duplicate BOE/row records, and absence of data operations or raw SQL.
- Dead Code Removed: None
- Duplicate Logic Removed: None
- Tests Added: None; no behavior changed.
- Verification Results:
  - Line-by-line review covered imports, dependencies, `sr_number` FK, all index declarations, both `AlterUniqueTogether` operations, and compatibility with `0003_alter_billofentrymodel_unique_together.py`.
  - `.venv/bin/ruff check backend/apps/bill_of_entry/migrations/0002_initial.py` -> clean.
  - `.venv/bin/python -m py_compile backend/apps/bill_of_entry/migrations/0002_initial.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/apps/bill_of_entry/migrations/0002_initial.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations bill_of_entry --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - Configured migration import verification with `DJANGO_SETTINGS_MODULE=lmanagement.settings` -> `initial=True`, 2 dependencies, 10 operations.
  - `git diff --check -- backend/apps/bill_of_entry/migrations/0002_initial.py` -> clean.
- Blocked Items:
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `pip-audit`, `safety`, or `semgrep` executable.
- Remaining Technical Debt:
  - None for this migration. Runtime validation and duplicate-record behavior remain queued for serializers/services/views.
- Status: COMPLETED

## backend/apps/bill_of_entry/migrations/0003_alter_billofentrymodel_unique_together.py

- File Path(s): `backend/apps/bill_of_entry/migrations/0003_alter_billofentrymodel_unique_together.py`
- Module: Bills of Entry / Unique constraint migration
- Total LOC: 15
- Lines Reviewed: 15
- Functions Reviewed: 0
- Classes Reviewed: 1 (`Migration`)
- Validation Improvements: None applied; the migration intentionally restores the current model-level uniqueness contract for `bill_of_entry_number` and `bill_of_entry_date`.
- Package Replacements: None; the Django `AlterUniqueTogether` operation is the correct historical migration primitive.
- Performance Improvements: None required; no data scan or custom operation exists in this migration file.
- Security Improvements: Reviewed duplicate-record constraint behavior and absence of raw SQL, data operations, request handling, file handling, or executable side effects.
- Dead Code Removed: None
- Duplicate Logic Removed: None
- Tests Added: None; no behavior changed.
- Verification Results:
  - Line-by-line review covered import, dependency on `0002_initial`, `AlterUniqueTogether`, and alignment with `BillOfEntryModel.Meta.unique_together`.
  - `.venv/bin/ruff check backend/apps/bill_of_entry/migrations/0003_alter_billofentrymodel_unique_together.py` -> clean.
  - `.venv/bin/python -m py_compile backend/apps/bill_of_entry/migrations/0003_alter_billofentrymodel_unique_together.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/apps/bill_of_entry/migrations/0003_alter_billofentrymodel_unique_together.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations bill_of_entry --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - Configured migration import verification with `DJANGO_SETTINGS_MODULE=lmanagement.settings` -> 1 dependency, 1 operation.
  - `git diff --check -- backend/apps/bill_of_entry/migrations/0003_alter_billofentrymodel_unique_together.py` -> clean.
- Blocked Items:
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `pip-audit`, `safety`, or `semgrep` executable.
- Remaining Technical Debt:
  - None for this migration.
- Status: COMPLETED

## backend/apps/bill_of_entry/migrations/__init__.py

- File Path(s): `backend/apps/bill_of_entry/migrations/__init__.py`
- Module: Bills of Entry / Django migrations package marker
- Total LOC: 0
- Lines Reviewed: 0-byte file verified with `wc -l` and `xxd`; every possible line/import/symbol/side effect is absent.
- Functions Reviewed: 0
- Classes Reviewed: 0
- Validation Improvements: None required; no migration operations or runtime validation paths exist.
- Package Replacements: None
- Performance Improvements: None required; no executed code exists.
- Security Improvements: None required; no executable code, imports, database operations, raw SQL, file handling, or request handling exists.
- Dead Code Removed: None
- Duplicate Logic Removed: None
- Tests Added: None; no behavior exists to regress.
- Verification Results:
  - `wc -l backend/apps/bill_of_entry/migrations/__init__.py` -> 0 lines.
  - `xxd -g 1 backend/apps/bill_of_entry/migrations/__init__.py` -> empty output.
  - `.venv/bin/ruff check backend/apps/bill_of_entry/migrations/__init__.py` -> clean.
  - `.venv/bin/python -m py_compile backend/apps/bill_of_entry/migrations/__init__.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/apps/bill_of_entry/migrations/__init__.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations bill_of_entry --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
- Blocked Items:
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `pip-audit`, `safety`, or `semgrep` executable.
- Remaining Technical Debt:
  - None for this package marker.
- Status: COMPLETED

## backend/apps/bill_of_entry/scripts/boe.py

- File Path(s): `backend/apps/bill_of_entry/scripts/boe.py`; `backend/tests/test_boe_script_helpers.py`
- Module: Bills of Entry / ICEGATE helper script
- Total LOC: 333 source lines; 142 focused test lines
- Lines Reviewed: 333 source lines plus 142 regression-test lines
- Functions Reviewed: 18 helper/parser methods and test helpers
- Classes Reviewed: 1 (`_InputValueParser`) plus 3 focused test doubles
- Validation Improvements: Trimmed and normalized submitted BE form values, rejected incomplete BE payloads before network calls, normalized cookie/form value extraction, rejected non-image captcha payloads, handled `requests.RequestException` paths, and preserved the existing helper return contracts for callers.
- Package Replacements: Replaced missing `bs4`/BeautifulSoup usage with Python standard-library `html.parser`; no new dependency introduced.
- Performance Improvements: Added bounded `DEFAULT_TIMEOUT = 15` request timeouts to avoid unbounded external ICEGATE calls; bounded response snippets logged from failed submissions.
- Security Improvements: Removed global `urllib3.disable_warnings`, constrained logging of remote response bodies, avoided implicit network calls for incomplete input, and covered network error paths without leaking full response content.
- Dead Code Removed: Removed dependency on unavailable BeautifulSoup import path.
- Duplicate Logic Removed: None; parser extraction keeps behavior local to this helper until adjacent BOE script files are audited.
- Tests Added: `backend/tests/test_boe_script_helpers.py` with 6 focused tests for CSRF extraction, non-image captcha rejection, network exceptions, timeout propagation, cookie coercion, BE form normalization, incomplete payload short-circuiting, and detail/current-status parsing.
- Verification Results:
  - `.venv/bin/python -m pytest backend/tests/test_boe_script_helpers.py -q` -> 6 passed.
  - `.venv/bin/ruff check backend/apps/bill_of_entry/scripts/boe.py backend/tests/test_boe_script_helpers.py` -> clean.
  - `.venv/bin/python -m py_compile backend/apps/bill_of_entry/scripts/boe.py backend/tests/test_boe_script_helpers.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/apps/bill_of_entry/scripts/boe.py backend/tests/test_boe_script_helpers.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations bill_of_entry --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - Configured import verification from `backend/` -> `DEFAULT_TIMEOUT=15` and `_input_value(...) == "abc"`.
  - `git diff --check -- backend/apps/bill_of_entry/scripts/boe.py backend/tests/test_boe_script_helpers.py` -> clean before code commit.
  - `python3 -m json.tool docs/audit/audit-database.json` -> valid JSON after audit database update.
- Commit SHA: `e912f2242b1202cf87524998e4cdd1c2ca2d5230`
- Commit Timestamp: `2026-07-16T16:57:31+05:30`
- Commit Summary: `fix(bill_of_entry): harden icegate helpers`
- Blocked Items:
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `pip-audit`, `safety`, or `semgrep` executable.
- Remaining Technical Debt:
  - Adjacent BOE scripts remain queued and must be audited separately; no additional helper extraction was safe until their call contracts are reviewed.
- Status: COMPLETED
