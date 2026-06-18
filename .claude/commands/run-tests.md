---
description: Run the backend test suite via run-tests.sh (default fast)
argument-hint: "[all|fast|api|unit|coverage]"
---

Run the backend tests using the repo runner. Mode from `$ARGUMENTS` (default `fast`):

- `all` → `./run-tests.sh`
- `fast` → `./run-tests.sh --fast`
- `api` → `./run-tests.sh --api`
- `unit` → `./run-tests.sh --unit`
- `coverage` → `./run-tests.sh --coverage`

Config lives in `backend/pytest.ini` (`DJANGO_SETTINGS_MODULE=lmanagement.settings`). Report
the summary line and any failures with their short traceback. If a test fails, identify the
root cause before changing code — see `.claude/prompts/bugfix.md`.
