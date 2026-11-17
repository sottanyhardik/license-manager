# Test and QA report — generic ERP workstream

Real results only (exit codes, counts). Local Postgres 18, isolated `test_*` databases. Nothing pushed or deployed.

## 2026-11-17 — integrated `feature/v5` @ `b099789c` (baseline before this workstream's code)

| Gate | Result |
|---|---|
| `quality-gate.sh backend` (`TEST_DB_NAME=test_lmanagement_e70cgate`) | check PASS · migrations check PASS · flake8 PASS · ruff PASS · **app-level 3546 passed, 1 xfailed** · `tests/` 245 passed, **1 failed** → exit 1 |
| The 1 failure | `tests/test_url_routing.py::test_spa_catchall_resolves_react_entry_template` — `TemplateDoesNotExist: index.html`: the fresh worktree had no `frontend/dist` (CI builds it first). After `vite build`: `tests/test_url_routing.py` **17 passed**. Environment, not a regression. |
| Frontend gate (peer session, same HEAD) | exit 0, vitest 871/871 (recorded in `ERP_AUTONOMOUS_EXECUTION_STATUS.md`) |

## 2026-11-17 — P3 `item-pivot.sticky` (`31061856`)

Root cause: the spec expected tier 2 at `first.top + tier-2 height`; the tiers differ in height (28 px vs 31.375 px)
and abut exactly (measured 129.313 = 129.313). Assertion fixed to `tier2.top ≈ tier1.bottom`; 2 px tolerance and
layout code unchanged. Real backend: before 1 failed (3.375 px), after **1 passed**.

## 2026-11-17 — Masters workspace (`331b9520`)

| Check | Result |
|---|---|
| Backend acceptance `apps/core/tests/test_master_framework_acceptance.py` + `test_master_filter_types`, `test_masterdata_delete_protection`, `test_openapi_schema` | **38 passed** (before the regex fix: 1 failed — slash-coded notification 404) |
| flake8 / ruff on changed Python | exit 0 / all checks passed |
| Frontend gate (`quality-gate.sh frontend`) | lint PASS (0 errors, 20 warnings) · typecheck PASS · build PASS · vitest 883/884 → 1 failed: `TopNav.interaction` link-count pin (8 → 14 Masters links, intended). Pin updated: 17 passed |
| vitest affected after review fixes (masters, navigation, TopNav, CommandPalette) | **127 passed** (17 files); `tsc` exit 0; ESLint 0 errors on changed files |
| Real-backend Playwright (`run_data_bearing_browser_e2e.sh`, fresh `test_*` DB) | `masters-workspace.real` **3/3** + `item-pivot.sticky` 1/1 → **4 passed**, exit 0 |
| Independent review (code-reviewer, Sonnet) | approve-with-nits; fixed: inline-update path for code-keyed masters, empty record-key guard, regex shadowing note |

Acceptance coverage (generic framework, 4 structurally different masters): real DB persistence · create/edit/delete ·
search · boolean filter · ordering · pagination (25/page, page 2) · max-length and required validation · duplicate code ·
delete protection (referenced port → 400) · code-keyed lookup incl. `/` · permissions (reader 403 on write, anonymous 401) ·
UI create → search → edit (encoded URL) → list refresh → delete with confirmation.

Not run for this milestone: the full backend app-level suite after `331b9520` (changes are confined to `core/views/views.py`
config and new tests; affected core suites ran), full Playwright default suite (legacy `responsive.spec.ts` known env failures).

## 2026-11-17 — Masters on the licence UI standard + generic record page

| Check | Result |
|---|---|
| Backend `test_master_framework_acceptance.py` (+3 record-history tests) + `test_activity_log_connections.py` | **21 passed**; flake8 0; ruff all checks passed |
| Frontend gate (`quality-gate.sh frontend`) | lint PASS (0 errors, 20 warnings, count unchanged) · typecheck PASS · **vitest 895/895** · build PASS → exit 0 |
| Snapshot update (`MasterList.licenses.filters`) | 2 updated: `companies` = intended move to the register toolbar; `bill-of-entries` = React `useId` values only (word diff checked) |
| Real-backend Playwright `masters-workspace.real` | **4/4**: hub; create → search → edit (encoded URL) → record page → History shows the real UPDATE → delete; port create/search; 390 px no horizontal overflow (hub, list, record) + desktop comparison screenshots |
| Licence regression, real backend (`data-bearing.real` + `item-pivot.sticky`) | **6 passed**, 1 skipped (`licence-workspace.live`, live-server config only), exit 0 |
| Note | All real specs in one harness run trip the login rate limit (`Request was throttled`) — a security control, left as is; suites run in separate harness runs |

## 2026-11-18 — Generic master bulk actions + live licence UI parity

| Check | Result |
|---|---|
| Live licence UI (`localhost:5173`, user's dev server, read-only, one sign-in) | inspected; measurements in GENERIC_ERP_ARCHITECTURE §5 |
| Backend bulk acceptance (`TestBulkActions`, 12 incl. parametrised) + `test_mds_write_cutover` + `test_masterdata_delete_protection` | **60 passed** |
| `tests/architecture` + acceptance | **39 passed** (first gate run caught an ORM write in `views/master_bulk.py` → moved to `core/services/`) |
| Backend gate app-level (`TEST_DB_NAME=test_lmanagement_e70cgate2`, before the last review fixes) | 3572 passed, 1 xfailed (exit 0); tests/ 246 passed after the services move |
| Frontend gate | lint PASS (0 errors, 20 warnings unchanged) · typecheck PASS · **vitest 903/903** · build PASS → exit 0 |
| Real-backend Playwright `masters-workspace.real` | **5/5**: incl. bulk deactivate (persisted + in record history), bulk delete (licence-referenced port refused by name, unused one deleted), master vs licence row style parity |
| Independent review (Sonnet) | approve-with-nits; fixed: audit row before MDS write, stop batch on MDS outage, bulk off for CIF/planning masters |

## 2026-11-18 — Master rows rebuilt on the licence register anatomy

| Check | Result |
|---|---|
| Column config vs real API rows (local DB, read-only) | every configured field present for all 13 masters (Groups: no local rows) |
| Frontend gate | lint PASS (0 errors, 20 warnings unchanged) · typecheck PASS · **vitest 910/910** · build PASS → exit 0 |
| Real-backend Playwright `masters-workspace.real` | **5/5**; companies / ports / item-names: one toolbar row at the licence toolbar position (±4 px), filters closed by default and open on click, Filters only where configured, Companies identifier = IEC, in-place expand; master rows match licence rows (radius, border, font; height ±6 px) |
| Licence regression, real backend (`data-bearing.real` + `item-pivot.sticky`) | **6 passed**, exit 0 |
| Screenshots | licence list, companies, ports, item names, companies with filters open + expanded row, record page (390 / 1440 px) |
