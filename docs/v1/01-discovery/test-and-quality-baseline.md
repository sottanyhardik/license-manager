# Test and quality baseline

Two kinds of evidence appear below. **Re-run 2026-10-31** means this session ran the command and read its exit code or summary from a log. **Carried forward** means an earlier session recorded the result and this session did not re-run it. Carried-forward results are not re-verified. Logs are in `/tmp/lm-verify/` and are not part of the repository.

## Current baseline (after the 2026-10-31 repair pass)

| Command | Result | Evidence status |
| --- | --- | --- |
| `frontend npm test` (Vitest) | **544 tests passed, 78 files, exit 0** (re-run after the UI changes). | Verified by test (re-run) |
| `frontend npm run lint` | **Exit 0** (re-run after the UI changes). | Verified by test (re-run) |
| `frontend npm run typecheck` | **Exit 0** (re-run after the UI changes). | Verified by test (re-run) |
| `frontend npm run build` | **Exit 0**, `vite build` in 527 ms (re-run after the UI changes). | Verified by test (re-run) |
| `frontend npm run format:check` (`eslint . --max-warnings=0`) | **Exit 0** (run before the UI changes). | Verified by test (re-run, earlier in session) |
| `backend manage.py check` | **Exit 0**: "System check identified no issues (0 silenced)." | Verified by test (re-run) |
| `backend manage.py makemigrations --check --dry-run` | **Exit 0**: "No changes detected." | Verified by test (re-run) |
| `backend pytest tests/ -p no:cacheprovider` (canonical, `TESTING=true`) | **237 passed in 76.31s, exit 0**. Aggregate line coverage 20% (74,228 statements, 59,037 missed). | Verified by test (re-run) |
| `backend pytest apps/license/tests apps/core/tests --import-mode=importlib -p no:cacheprovider --no-cov` (licence/core, `TESTING=true TEST_DB_NAME=test_lmanagement_licence_core_full`) | **2714 passed in 306.75s, exit 0, 0 failures.** 2714 = the original 2,708 plus 6 D2 characterization tests in the same directories. | Verified by test (re-run) |
| `backend pytest apps/license/tests/test_balance_semantics_d2_characterization.py` | **6 passed, exit 0.** Pins current formula values; changes no behaviour. | Verified by test (re-run); characterization only |
| `frontend npm run test:e2e` (Playwright, local Vite on `127.0.0.1:41731`, 130 discovered) | **121 passed, 1 failed, 8 skipped, exit 1, 3.3 min.** The failure is `e2e/item-pivot.sticky.spec.ts:16`, the unguarded seeded-fixture precondition (`E2E2509 Managed browser gate`). | Verified by test (re-run); **1 known failure, not hidden** |
| `frontend npx playwright test e2e/responsive.spec.ts` | **106 passed, exit 0** (was 50 harness `TypeError`s and 1 timeout before the repair). | Verified by test (re-run) |
| `frontend npx playwright test e2e/trades.accessibility.spec.ts e2e/trades.performance.spec.ts` | **5 passed, exit 0** (was 2 serious axe failures before the repair). | Verified by test (re-run) |

## Previous baseline (before the repair pass, for comparison)

| Command | Result | Evidence status |
| --- | --- | --- |
| `frontend npm run test:e2e` (first re-run, same session) | 68 passed, 54 failed, 8 skipped, exit 1. Failures: 50 responsive-screenshot harness `page.path` errors; 2 serious axe `color-contrast` (`#1a2332` on `#155dfc`, ratio 3 vs 4.5) on trades pages; 1 timeout dashboard responsive filter; 1 timeout item-pivot sticky fixture. | Measured failing baseline (superseded) |

## Carried forward (not re-run in this session)

| Command | Result | Evidence status |
| --- | --- | --- |
| `master-data-service manage.py makemigrations --check --dry-run` | "No changes detected" against a disposable PostgreSQL 16 CI-equivalent container on `127.0.0.1:55432`. | Carried forward (earlier session) |
| `master-data-service pytest -p no:cacheprovider` | 25 passed in 0.80s against that container. The earlier default-local-host attempt had 25 setup errors because its database lacked the `master_data` role; no role was added to that database. | Carried forward (earlier session) |
| `mds-client runtests.py` | 32 passed in 0.015s, in-memory Django test database. | Carried forward (earlier session) |
| `backend manage.py spectacular --validate` | 0 errors, 22 warnings (6 unique classes), 246 paths / 354 operations. | Carried forward (earlier session) |

Historical documentation records a 3,203/3,203 backend suite green run, but it is **not a current-worktree result** and must not be treated as one. CI provisions PostgreSQL 16 and Redis 7, runs backend, frontend and MDS unit paths, does not run Playwright/axe E2E, and enforces no coverage floor (**Verified by code**).

## Remaining known failures and gaps

- **E2E `item-pivot.sticky.spec.ts`**: waits for a seeded control that exists only with the seeded browser fixture. It is not guarded behind the isolated harness and uses fallback credentials (see [E2E baseline](../07-quality-and-operations/e2e-baseline.md)). Fix requires a guarded seeded fixture, not a skip.
- **Icon-only links outside `MasterList`**: 8 other files use `hidden sm:inline` labels. Whether they produce an axe `link-name` violation has **not been measured**; no E2E case currently checks them.
- **Accessibility coverage**: axe runs cover only the routes in the E2E suite. No full-route accessibility matrix exists.

## Side effects of these runs on the working tree

- `frontend/test-results/` and `frontend/playwright-report/` are rewritten by every Playwright run, and their earlier contents are replaced. Both are git-ignored.
- `frontend/responsive-screenshots/*.png` is written by the responsive spec into a directory that is **not** git-ignored. The 50 PNGs from this session were deleted. Recommendation: git-ignore the directory (tracked change, needs approval).
- `backend/htmlcov/` and `backend/.coverage` are regenerated by pytest runs without `--no-cov`, because `pytest.ini` sets `--cov=.` and `--cov-report=html`. Both are git-ignored.
- `frontend/dist/` is rebuilt by `npm run build`. Git-ignored.
