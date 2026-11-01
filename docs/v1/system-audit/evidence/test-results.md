# Test results evidence — audit session 2026-11-01

Every row is a command actually executed in the session, with its real process exit code and the count from its own output. Logs are under `/tmp/lm-verify/` (not in the repository).

| Command | Environment | Exit | Passed | Failed | Skipped | Did not run | Notes |
|---|---|---|---|---|---|---|---|
| `pytest apps/license/tests/test_license_default_active_filter.py apps/license/tests/test_license_advanced_filters_live_balance.py apps/license/tests/test_license_validity_api.py apps/license/tests/test_license_list_balance_consistency.py -p no:cacheprovider --no-cov -q` (`TESTING=true`, `TEST_DB_NAME=test_filter_contract3_20261101`) | Isolated test database | 0 | 15 | 0 | 0 | 0 | Filter contract, live-balance regression, validity API, list balance consistency. Log `filter-contract3.log`. |
| `pytest apps/license/tests/test_license_default_active_filter.py` (after fixture fix, before dashboard tightening) | Isolated test database | 0 | 8 | 0 | 0 | 0 | First run had 8 fixture errors (wrong helper); fixed by granting the licence role through group membership. |
| `scripts/test/run_data_bearing_browser_e2e.sh e2e/data-bearing.real.spec.ts -g "persisted BOE|seeded populated route is responsive"` | Isolated harness (Redis index 7, harness Celery worker) | 0 | 2 | 0 | 0 | 0 | Previously unrun responsive test now executes and passes. |
| Same harness, `e2e/custom-ledger-download.spec.ts e2e/financial-ledger-invoices.spec.ts e2e/package-download.spec.ts e2e/data-bearing.real.spec.ts -g "custom ledger|Excel|blocks a licence|PLAN allocation debits"` | Isolated harness | 0 | 4 | 0 | 0 | 0 | Custom ledger PDF, Excel export, package readiness negative, PLAN queue. No orphan workers, index 7 empty afterwards. |
| Full isolated suite (`run_data_bearing_browser_e2e.sh --reporter=list`) | Isolated harness | — | — | — | — | — | NOT RUN in this audit. The user interrupted the launch. Last full run (earlier in the session, before the serial-group fix): 129 passed, 1 failed, 1 did not run, exit 1. Superseded. |

## Not re-run since the latest edits

- Frontend `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`: last recorded as passing before the most recent E2E spec edits (`e2e/data-bearing.real.spec.ts`, `e2e/custom-ledger-download.spec.ts`). Re-run required before claiming current frontend health.
- Full backend suite: not run in this audit.

## Known test-suite limitations

- Positive package-generation coverage does not exist yet (fixture with complete purchase documents and final-party invoices not built).
- The sticky-header negative control (intentionally misaligned fixture must fail) has not been run in this session.
- The Playwright default mode skips guarded specs; guarded results must come from the isolated harness.

## Slice 1 — superuser protection (2026-11-01)

Commands run from `backend/` with `TESTING=true`, dedicated `TEST_DB_NAME`, `--no-cov`, `-p no:cacheprovider`. Each exit code is the real process exit.

| Command | Exit | Passed | Failed | Notes |
|---|---|---|---|---|
| `pytest apps/accounts/tests.py tests/test_authorization_permissions.py -q` (baseline, before any change) | 0 | 34 | 0 | `TEST_DB_NAME=test_slice1_superuser_20261101` |
| `pytest apps/accounts/test_superuser_protection.py -q` (before the fix) | 1 | 7 | 8 | Expected failures: superuser detail, reset, delete, deactivate return 200/204; superuser listed and found by search |
| `pytest apps/accounts/test_superuser_protection.py apps/accounts/tests.py tests/test_authorization_permissions.py -q` (after the fix) | 0 | 49 | 0 | 15 new, 34 baseline |
| `flake8 --select=E9,F` on the two changed Python files | 0 | — | — | no findings |
| `py_compile` on the two changed Python files | 0 | — | — | compiles |
| ISS-013 lead probe (`/tmp/lm-audit-probe/test_iss013_recheck.py`, outside repository) | 0 | 1 | 0 | records behaviour; see `iss-011-013-verification.md` |

Not run in this slice: the full backend suite, frontend tests and lint (no frontend file changed), and the browser end-to-end suite.
