# Rule — Testing

Backend config: `backend/pytest.ini` (`DJANGO_SETTINGS_MODULE=lmanagement.settings`, tests in
`tests/`). Runner: `run-tests.sh` (root). Guides: `docs/guides/TESTING_GUIDE.md`,
`docs/guides/README_TESTING.md`.

## Must

- **Every bug fix ships a regression test** that fails before the fix and passes after.
- **Mark tests** with the right marker so suites can be sliced:
  `slow`, `integration`, `unit`, `api`, `database` (declared in `pytest.ini`).
- **Cover business logic**: balance debits/credits, ledger parsing, OCR extraction,
  allotment reservation, transfer documentation, role permission boundaries.
- **Cover edge cases**: zero/negative/over-draw balances, `frozen` BOE rows, partial
  allotments, expired/blacklisted JWTs, unauthorized roles → 403.
- Name files `test_*.py`, classes `Test*`, functions `test_*` (pytest config enforces).

## Commands

| Goal | Command |
|---|---|
| Everything | `./run-tests.sh` |
| Fast (skip `slow`) | `./run-tests.sh --fast` |
| API only | `./run-tests.sh --api` |
| Unit only | `./run-tests.sh --unit` |
| Detailed coverage | `./run-tests.sh --coverage` |
| Clean artifacts first | `./run-tests.sh --clean` |
| Direct pytest | `cd backend && pytest -m "not slow"` |

## Frontend

No JS test runner is configured. The frontend gate is `lint` → `typecheck` → `build`
(see `.claude/rules/frontend-ui.md`). Don't introduce a test framework without discussing it.
