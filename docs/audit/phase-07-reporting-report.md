# Phase 7 Reporting & Exports Audit Report

## backend/apps/allotment/scripts/pdf_coordinate_finder.py

- File Path: `backend/apps/allotment/scripts/pdf_coordinate_finder.py`
- Module: Reporting & Exports / Allotment PDF helper script
- LOC: 120
- Lines Reviewed: 120
- Functions Reviewed: 4 (`_positive_int`, `create_coordinate_grid`, `parse_args`, `main`)
- Classes Reviewed: 0
- Arguments Reviewed: positional `output`, `--grid-spacing`, `--overwrite`
- Validation Improvements:
  - Added positive-integer validation for grid spacing through `argparse` and the direct helper API.
  - Added output-path validation for existing files, directory targets, and missing parent directories.
  - Added explicit overwrite opt-in to prevent accidental replacement of generated PDFs.
- Package Replacements:
  - Removed unused `pypdf.PdfReader`; retained existing ReportLab dependency because the script's purpose is PDF generation.
  - Replaced ad hoc `sys.argv` behavior with Python standard-library `argparse` and `pathlib`.
- Performance Improvements:
  - No runtime database or API path exists; generation remains bounded to one A4 page with configurable spacing.
  - Avoided unnecessary PDF reads by removing the unused reader import.
- Security Improvements:
  - Prevented unintended file overwrite by default.
  - Explicitly rejects directory targets and missing parent directories before ReportLab writes.
- Dead Code Removed:
  - Removed unused `pypdf.PdfReader` import and stale usage text that advertised an ignored PDF-template input.
- Duplicate Logic Removed:
  - None found; repository-wide search found no duplicate coordinate-grid helper.
- Tests Added:
  - Added `backend/tests/test_pdf_coordinate_finder.py` covering valid PDF generation, existing-output protection, explicit overwrite, directory-output rejection, invalid grid spacing, `argparse` error exit, and `main()` success path.
- Verification Results:
  - Dependency/reference analysis: `rg -n "pdf_coordinate_finder|find_coordinates|fitz|PyMuPDF|coordinate" . -S` found no live runtime references outside this script and audit metadata.
  - Focused pytest: `.venv/bin/python -m pytest backend/tests/test_pdf_coordinate_finder.py -q` -> 7 passed.
  - Ruff: `.venv/bin/ruff check backend/apps/allotment/scripts/pdf_coordinate_finder.py backend/tests/test_pdf_coordinate_finder.py` -> clean.
  - py_compile: `.venv/bin/python -m py_compile backend/apps/allotment/scripts/pdf_coordinate_finder.py backend/tests/test_pdf_coordinate_finder.py` -> passed.
  - compileall: `.venv/bin/python -m compileall -q backend/apps/allotment/scripts/pdf_coordinate_finder.py backend/tests/test_pdf_coordinate_finder.py` -> passed.
  - Django check: `.venv/bin/python backend/manage.py check` -> no issues.
  - makemigrations check: `.venv/bin/python backend/manage.py makemigrations --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - CLI help: `.venv/bin/python backend/apps/allotment/scripts/pdf_coordinate_finder.py --help` -> passed.
  - Import verification: imported `DEFAULT_GRID_SPACING`, `create_coordinate_grid`, and `parse_args`; parsed `--grid-spacing 25 --overwrite` successfully.
- Blocked Items:
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `pip-audit`, `safety`, or `semgrep` executable.
- Remaining Technical Debt:
  - None for this file.
- Status: COMPLETED

### Final State Verification

- Audit Database: `backend/apps/allotment/scripts/pdf_coordinate_finder.py`, `backend/tests/test_pdf_coordinate_finder.py`, and `docs/audit/phase-07-reporting-report.md` marked `COMPLETED`.
- Repository Knowledge Graph / Dashboard / Work Queue: regenerated with `python3 docs/audit/build_audit_state.py`; Phase 7 queue item is active.
- Final scoped Ruff: `.venv/bin/ruff check backend/apps/allotment/scripts/pdf_coordinate_finder.py backend/tests/test_pdf_coordinate_finder.py docs/audit/build_audit_state.py` -> clean.
- Final scoped py_compile: `.venv/bin/python -m py_compile backend/apps/allotment/scripts/pdf_coordinate_finder.py backend/tests/test_pdf_coordinate_finder.py docs/audit/build_audit_state.py` -> passed.
- Final scoped diff check: `git diff --check -- backend/apps/allotment/scripts/pdf_coordinate_finder.py backend/tests/test_pdf_coordinate_finder.py docs/audit/build_audit_state.py docs/audit/phase-07-reporting-report.md docs/audit/audit-database.json docs/audit/repository-knowledge-graph.json docs/audit/dashboard.md docs/audit/work-queue.md` -> clean.
