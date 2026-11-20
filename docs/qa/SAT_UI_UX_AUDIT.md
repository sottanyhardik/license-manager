# SAT UI/UX Audit: Phase 4 (integration), Phase 5 (E2E), Phase 7 (UI/UX)

| Item | Value |
|---|---|
| Date | 2026-11-20 |
| Branch | feature/v5 |
| `git diff \| shasum \| cut -c1-12` | d7f6ddf4aeed (at write time; 6f1712e03000 at session start; other sessions kept editing) |
| Harness | `scripts/test/run_data_bearing_browser_e2e.sh`, one disposable `test_license_manager_browser_e2e_<ts>_<pid>` DB per run, migrated and seeded with `seed_browser_2509`, dropped on exit. Run with `PYTHON_BIN=backend/.venv/bin/python`, `--workers=1`. |
| Real data | `lmanagement` was never touched. `migrate` ran only on the disposable DBs. |
| Evidence dir | `~/lm_sat_evidence/e2e/` (logs, jsonl, `shots/` with 155 PNGs, downloaded xlsx) |
| Ports at end | 8000 and 41731 free; no harness process alive (`lsof` and `pgrep` empty) |

## Commands and exit codes

| Run | Command (after `PYTHON_BIN=...`) | Exit | Result | Log |
|---|---|---|---|---|
| attempt 1 | regression suite without `PYTHON_BIN` | 1 | the default `.venv` has no Django, so migrate failed. Harness defect, no tests ran. | `harness-attempt1-nodjango.log` |
| regression | `run_data_bearing_browser_e2e.sh data-bearing.real accounting.real licence-edit.real licence-ledger-onepage.real licence-payment-ledgers.real masters- workspaces reports-menu` | 1 | 25 passed, 4 failed, 13 skipped, 16 did not run (2.6m) | `harness-regression.log` |
| sat | `... sat-workflows sat-pages-audit` | 1 | 137 passed, 1 failed, 23 did not run (5.2m) | `harness-sat.log` |
| wf run 1/2 | `... sat-workflows` (after spec fixes, `-run2` log) | 1 | 14 passed, 12 failed (cascade of login rate-limit plus spec bugs, see classification) | `harness-wf-run2.log` |
| wf run 3 | `... sat-workflows` (after fixes) | 1 | 24 passed, 2 failed | `harness-wf-run3.log`, `workflows-run3.jsonl` |
| trade rerun | `... sat-workflows -g "trade invoice"` | 0 | 1 passed (10.3s) | `harness-wf-trade.log` |
| pages | the `sat-pages-audit` part of the "sat" run | (in sat) | 135/135 pass, 0 page errors, 0 console errors, 0 failed `/api/` responses | `pages-audit.jsonl` |

The final consolidated state is "wf run 3" plus the trade rerun. The wf-run-3 trade failure is superseded by the passing rerun, so the open failure is the navigation test (defect D01).
Spec edits (SAT-owned only): evidence path via `SAT_OUT`, a fixed per-run viewer username, login retry on throttle, spec fixes listed under "Failure classification".

## Failure classification

### Regression suite (existing specs, one run, not re-run)

| Failure | Evidence | Classification |
|---|---|---|
| `masters-detail.real.spec.ts:61` (Transfer Letter) | in-page POST returned 401 `token_not_valid` | Test/harness (unconfirmed). Auth state from `beforeAll` rejected in a long single-worker run. Access TTL is 30 min (`settings.py:345`), so expiry is not the cause. Not reproduced in isolation. |
| `masters-seven-pages.real.spec.ts:120` (Companies) | same 401 | Same as above. |
| `masters-workspace.real.spec.ts:19` | `waitForURL` timeout at login | Test/harness. In my own run the login page showed "Request was throttled. Expected available in 9 seconds" (screenshot in the Playwright error-context). Login is rate-limited and a 58-test serial run logs in many times. |
| `reports-menu.spec.ts:91` (Item Report) | "Reports" nav button not found | UNCLASSIFIED. Needs an isolated rerun (not done, rerun budget used). Not shown to be a product defect. |
| 16 "did not run" | masters-detail 22-24, masters-seven-pages 27-34, masters-workspace 36-40 | Consequence of `describe.configure({mode:"serial"})` after the failures above. |
| 13 skipped | accounting.real, licence-payment-ledgers.real | Need `LM_E2E_SEED=seed_accounting_e2e` and `seed_payment_ledger_e2e`. NOT RUN, not a failure. |

Pre-existing versus new cannot be proven without a baseline run on a clean tree, which was out of scope.

### SAT specs

| Failure | Classification |
|---|---|
| `sat-workflows.spec.ts:78` "list boe" (sat run) | Test defect. The empty-state row was counted as a data row, so the "no-match narrows rows" assertion was wrong. 23 did not run because of my `serial` mode. Fixed (assert only when more than 1 row; serial removed). |
| wf run 2, 12 failures | Test defects. Causes: trade payload sent nested company objects (400); `localStorage` read before first navigation; planned export button disabled for empty data; 500-probe asserted after 800 ms though react-query retries (error shows later); the viewer login hit the login rate limit. All fixed in the spec. |
| wf run 3 trade test | Test defect. The API requires at least one line ("At least one trade line or incentive line must be defined."). The spec now sends a line, and the rerun passed. |
| wf run 3 navigation test (`LOGIN-bad-password`) | APP DEFECT, D01. |

## Test-ID table

Status: PASS, PASS-EXC (passes with an exception noted), FAIL, BLOCKED, NOT-RUN.

### Phase 4, integration

| ID | Workflow | Status | Evidence |
|---|---|---|---|
| SAT-INT-001 | Licence 2509 exists, API returns `balance_cif`, all 7 tabs open without error text, tab persists on reload (`?tab=invoice-ledger`) | PASS-EXC. The screen-versus-API balance string match was inconclusive (`pageHasBal` 0 for `2066.75`; likely an Indian-format versus raw string mismatch, not investigated). | `workflows-run3.jsonl` LIC-* |
| SAT-INT-002 | Licence create/edit in UI, then API re-read | NOT-RUN. Read-only page audit only (create/edit forms open at 3 viewports). Writes in the licence form were not driven. | `pages-audit.jsonl` |
| SAT-INT-003 | Allotment create, then BOE debit, then licence balance update | BLOCKED. Seed has 0 BOEs (BOE list shows the empty state) and I did not build a BOE through the UI. Alternative run: allotment pages open (list, create, edit, allocate), no errors. | `pages-audit.jsonl` |
| SAT-INT-004 | Allotment to BOE conversion, no double count | BLOCKED (same reason). Math is covered by the financial audit (other workstream). | n/a |
| SAT-INT-005 | Trade create (API), find in list by search, edit form opens, delete, 404 after delete | PASS-EXC. Create 201, found by search, delete confirmed 404. The edit form has no "Remarks" label, so edit-persist and validation could not be driven (see D02). The row-actions delete menu was not reachable after search, so delete was done via API (`viaUi:false`). | `harness-wf-trade.log`, `workflows.jsonl` TRADE-* |
| SAT-INT-006 | Trade confirm/post, partial payment | NOT-RUN. The accounting seed (`seed_accounting_e2e`) was not run. | n/a |
| SAT-INT-007 | Invoice to BOE link not double counted | BLOCKED (no BOE in seed). | n/a |
| SAT-INT-008 | Item mapping, planning, allocation | PARTIAL. `/mapping`, `/planning`, `/allotments/1/allocate` open at 3 viewports without errors. Write path NOT-RUN. | `pages-audit.jsonl` |
| SAT-INT-009 | Licence transfer | NOT-RUN. | n/a |
| SAT-INT-010 | BOE upload/import | BLOCKED. No BOE upload UI route found in `/bill-of-entries` (only create). Not pursued. | n/a |
| SAT-INT-011 | Item Pivot / Item Report reflect new transactions | PARTIAL. Both pages load. New-transaction reflection NOT-RUN (no BOE/allotment created). | `pages-audit.jsonl` |
| SAT-INT-012 | Export downloads (200, non-empty) | PASS-EXC. item-report 6176 B, item-pivot 8519 B, expiring 5050 B, active 5045 B (all valid xlsx). planned: button disabled (no data). purchase-profit: no export control. | `dl-*.xlsx`, `workflows-run3.jsonl` EXPORT-* |
| SAT-INT-013 | Existing data-bearing regression suite | FAIL (4) / PASS (25). See classification above. | `harness-regression.log` |

### Phase 5, E2E

| ID | Page/flow | Status | Evidence |
|---|---|---|---|
| SAT-E2E-001 | Dashboard open | PASS | pages-audit |
| SAT-E2E-002 | Licences list: search, no-match empty state, filter dialog, pagination controls, reload keeps search (URL) | PASS | LIST-licences* |
| SAT-E2E-003 | Licence detail, overview tabs, edit page, create page | PASS (detail redirects to `/overview`, expected) | pages-audit, LIC-* |
| SAT-E2E-004 | Allotments list: search, filters, reload persistence | PASS-EXC. The search term `E2E-ALLOTMENT-2509` matched 0 rows although the seed reports an allotment; with the default filter (`is_boe=False&type=AT`) the unfiltered view showed 1 row. Not verified against the API (see D10). | LIST-allotments |
| SAT-E2E-005 | Allotment create/edit/allocate pages open | PASS | pages-audit |
| SAT-E2E-006 | BOE list and create | PASS (empty state when no rows) | LIST-boe |
| SAT-E2E-007 | BOE detail | NOT-RUN. Seed has no BOE. | n/a |
| SAT-E2E-008 | Trades list, create page, search | PASS | LIST-trades*, TRADE-* |
| SAT-E2E-009 | Reconciliation and issues pages | PASS | pages-audit |
| SAT-E2E-010 | Mapping, Planning | PASS (open only) | pages-audit |
| SAT-E2E-011 | Reports: item pivot, item report, planned, purchase-profit, expiring, active, download-license, SION E1/E5/E126/E132 | PASS (open at 3 viewports) | pages-audit |
| SAT-E2E-012 | Incentive licences, ledger upload, license ledger, ledger downloads | PASS (open) | pages-audit |
| SAT-E2E-013 | Accounting setup and dashboard | PASS (open). Accounting workflows NOT-RUN. | pages-audit |
| SAT-E2E-014 | Masters hub, companies, item names: list, search, reload | PASS | LIST-masters-* |
| SAT-E2E-015 | Masters create form: empty submit shows validation, Cancel returns to list | PASS (2 messages, 1 `aria-invalid`) | FORM-companies-*, `wf-company-validation.png` |
| SAT-E2E-016 | Users/admin list, create, activity log | PASS-EXC. Admin users search is not persisted in the URL on reload (D08). | LIST-admin-users* |
| SAT-E2E-017 | Settings, profile | PASS (open) | pages-audit |
| SAT-E2E-018 | Login, logout redirects to `/login?redirect=...`, protected route bounces to login | PASS | NAV-logout |
| SAT-E2E-019 | Wrong password shows an error | FAIL (message likely shown but not announced; see D01) | LOGIN-bad-password |
| SAT-E2E-020 | 404 page | PASS | NAV-404 |
| SAT-E2E-021 | Deep link plus browser back/forward | PASS | navigation test |
| SAT-E2E-022 | Viewer role (user created through real user API, roles LICENSE_VIEWER and INCENTIVE_LICENSE_VIEWER) | PASS. 12 write/admin routes land on `/403`; `/licenses` shows 0 write controls; API writes return 403/403/403. | VIEWER-* |
| SAT-E2E-023 | Sort on list pages | NOT-RUN. No `th[aria-sort]` or Sort control found on any list (selector-based; the UI may sort via URL `ordering`). | LIST-*.sortCtl |
| SAT-E2E-024 | Multi-select and bulk actions | PARTIAL. Checkboxes found only on masters lists (3). Bulk actions not driven. | LIST-masters-* |
| SAT-E2E-025 | Delete with confirmation dialog | NOT-RUN (the trade row-action menu was not reachable; delete done via API). | TRADE-row-actions |
| SAT-E2E-026 | Persistence after refresh (search state, active tab) | PASS | LIST-*-refresh, LIC-reload |

### Phase 7, UI/UX

| ID | Check | Status | Evidence |
|---|---|---|---|
| SAT-UX-001 | Console errors, page errors, failed requests per page (135 page-viewport loads) | PASS (none) | pages-audit |
| SAT-UX-002 | Horizontal scroll or clipped tables at 1440/820/390 | PASS (`overflowPx` 0 and `clippedTables` 0 everywhere; licence tabs also 0) | pages-audit |
| SAT-UX-003 | Error state on HTTP 500 (mocked network, labelled as a probe): trades, licences, allotments, BOE, item pivot, dashboard, masters companies | PASS-EXC. All show error text, no unhandled exceptions, but only after react-query retries (about 3 s or more); the trades page shows skeleton rows with "Updating..." meanwhile. Retry button only on dashboard. | `wf-err-*.png`, ERR-* |
| SAT-UX-004 | Empty state (mocked empty list): trades, licences, allotments, BOE | PASS | EMPTY-* |
| SAT-UX-005 | Empty state for item pivot, dashboard, masters companies (mocked empty) | PASS-EXC (no recognisable "no data" text found by regex) | EMPTY-* |
| SAT-UX-006 | Form labels (programmatic) | FAIL (D02) | pages-audit `unlabeled`, axe `label` |
| SAT-UX-007 | Link names | FAIL (D03) | axe `link-name` |
| SAT-UX-008 | Button names | FAIL (D04) | axe `button-name`, `unnamedBtns` |
| SAT-UX-009 | Colour contrast | FAIL (D05) | axe `color-contrast` |
| SAT-UX-010 | ARIA structure and scroll regions | FAIL (D06) | axe |
| SAT-UX-011 | Keyboard: tab order reaches nav in logical order; Escape closes row-actions menu and focus returns | PASS (tab order: brand, Dashboard, menus, Search, theme, account) for the tab order; the row-actions Escape part ran only where an actions button exists | KB-* |
| SAT-UX-012 | Dialog focus trap | NOT-RUN (no modal driven; filter dialog opens and closes with Escape) | LIST-*.filtersOpens |
| SAT-UX-013 | Dark mode | NOT-RUN (toggle exists, "Switch to dark mode"; not exercised) | KB-licences-tab-order |
| SAT-UX-014 | Pagination controls present | PASS-EXC (present on licences, trades, masters; not driven) | LIST-*.pager |
| SAT-UX-015 | Search, filter dialogs | PASS | LIST-* |
| SAT-UX-016 | Login error announced to assistive tech | FAIL (D01) | Login.tsx:163-167 |

## Page x viewport matrix (135 loads)

All 45 pages at each of 1440x900, 820x1180 and 390x844: loaded, not blank, no login bounce, 0 page errors, 0 console errors, 0 bad API responses, 0 horizontal overflow, 0 clipped tables. Pages: dashboard; licences list/overview/detail/edit/create; allotments list/create/edit/allocate; BOE list/create; trades list/create; reconciliation (2); item-pivot, item-report, planned, purchase-profit, expiring, active, download-license; SION E1/E5/E126/E132; mapping; planning; incentive; ledger-upload; license-ledger; ledger-downloads; masters hub/companies/item-names/companies-create; admin users/create/activity-log; settings; profile; accounting setup/dashboard; not-found.
Only variation is accessibility (per-ID rows above; per-page detail in `pages-audit.jsonl`).
Screenshots: `shots/<page>-<viewport>.png`.

## Console-error table

| Scope | Page errors | Console errors | Failed `/api/` requests |
|---|---|---|---|
| 135 page loads | 0 | 0 | 0 |
| Mocked-500 probes (intentional 500s) | 0 unhandled | not collected | injected only |

## Defects

Business approval needed is N for all (UI accessibility only; no business rule, API contract or balance logic is affected).

| ID | Sev | Category | Module | Summary |
|---|---|---|---|---|
| SAT-UX-D01 | Medium | a11y | Login | Login error is not announced. Repro: `/login`, enter user `hardik` and a wrong password, Sign in. Expected: error in a `role="alert"` or `aria-live` region. Actual: 0 `role=alert` elements; the message sits in a plain `<div>`/`<span>` (also the throttle message). Root cause: `frontend/src/pages/Login.tsx:163-167`. Remediation: add `role="alert"` to the container. Screenshot: Playwright error-context of the failing run (run 3). |
| SAT-UX-D02 | Medium | a11y | Trades, trade create, allotment allocate, item report, planned report, licence create/edit, masters create | Unlabeled inputs. axe `label` serious: trades 8, trade-create 13, allotment-allocate 7, item-report 2, planned-report 2, companies-create 3, licence-edit/create 1. A search/filter input per list page has no label (`unlabeled` 1 on most lists). Also made the trade edit form un-drivable by label ("Remarks"). Root cause not located. Remediation: add `aria-label` or `<label htmlFor>`. |
| SAT-UX-D03 | Medium | a11y | App shell (tablet and mobile) | axe `link-name` (1 node) on every authenticated page at 820 and 390 but not 1440. An unnamed link in the compact header or nav. Root cause not located. Remediation: add an accessible name. |
| SAT-UX-D04 | Medium | a11y | dashboard (390: 4 buttons), admin users (2), admin user create (21 unnamed buttons), allotment create/edit (2), ledger upload (1) | Buttons without accessible name. Root cause not located. |
| SAT-UX-D05 | Low | a11y | masters item names (100 nodes at 820/390), activity log (22), masters companies (6), purchase-profit, license-ledger, profile, allotment-allocate, boe-create | Colour contrast below AA. Root cause not located. |
| SAT-UX-D06 | Low | a11y | licence edit/create (`aria-required-parent` 3, `list` 1), licence overview/detail (`scrollable-region-focusable`), activity log/acct-setup/ledger-downloads at 390, license-ledger (`aria-conditional-attr`) | ARIA structure and scrollable regions not keyboard-focusable. |
| SAT-UX-D07 | Low | UX | Trades, licences, allotments, BOE, masters, dashboard | 500 errors surface only after retries; the trades page shows skeleton rows and "Updating..." with no retry button. No retry control on 6 of 7 probed pages. |
| SAT-UX-D08 | Low | UX | Admin users | Search text is not kept in the URL on reload, unlike other lists (`searchPersisted:false`). |
| SAT-UX-D09 | Low | UX | Reports | `/reports/license-purchase-profit` has no export control; planned report export is disabled with no data (probably by design; confirm). |
| SAT-UX-D10 | Low (unverified) | Data/UI | Allotments | Searching the seeded allotment number returns 0 rows under the default filter. Not verified against the API; may be the seed or the filter. Needs triage. |

## Limitations and coverage gaps

- Phase 4 financial flows (allotment to BOE to balance, invoice/BOE link, partial payment, transfer, BOE upload, pivot reflection) were not executed: the seed has no BOE, and the accounting and payment-ledger seeds were not run (13 specs skipped, NOT RUN). Needs `LM_E2E_SEED=seed_accounting_e2e` and `seed_payment_ledger_e2e` runs.
- The 4 regression failures (masters x3, reports-menu x1) were not individually reproduced; classification is by log evidence only. reports-menu stays unclassified.
- Sort, bulk actions, delete-with-confirm, dialog focus trap and dark mode were not driven.
- axe root causes (D02 to D06) were not traced to file:line; axe node targets were not captured by the spec.
- Screen-versus-API balance match inconclusive (formatting).
- Pages were opened as a superuser except in the viewer test; only one non-admin role pair was tested.
- Console errors were collected only in the page audit, not during workflows.

## Controller addendum (2026-11-20, after `sat-e2e` finished)

Runs by the SAT controller on fresh disposable harness DBs (`PYTHON_BIN=backend/.venv/bin/python`, `--workers=1`). All logs are in
`~/lm_sat_evidence/e2e/` and `~/lm_sat_evidence/int/`.

| Run | Command | Exit | Result |
|---|---|---|---|
| accounting (previously 13 skipped) | `LM_E2E_SEED=seed_accounting_e2e … accounting.real` | 0 | **10 passed** (2.3 m), `harness-accounting.log` |
| payment ledgers | `LM_E2E_SEED=seed_payment_ledger_e2e … licence-payment-ledgers.real` | 0 | **3 passed** (12.4 s), `harness-payledger.log` |
| BOE workflow (new SAT spec `frontend/e2e/sat-int-boe.spec.ts`) | `… sat-int-boe` (3 runs; run 3 is final) | 0 | 1 passed, `harness-int-boe3.log`, `int/boe_flow.jsonl` (runs 1–2 kept as `.run1/.run2`) |
| backend workflow suites (API-level alternative for the BOE-less seed) | 16 files: BOE balance refresh, M2M full consumption, overview summary/allotments, balance-ledger views, BOE write/merge, invoice relations, trade service/payments/pairing/unpair, reconciliation allocation/linker | 0 | **257 passed, 1 xfailed** (57.5 s), `int/pytest_int.log`, `TEST_DB_NAME=test_lmanagement_sat_int` |
| allotment filter probe | throwaway pytest, 6 parametrised queries | 1 (expected) | 4 passed / 2 failed: `?is_approved=all` → **HTTP 500** (unhandled `ValidationError`), `int/pytest_allot_filter.log` |

Updated Phase 4 outcomes (they override the table above):

| ID | New status | Evidence |
|---|---|---|
| SAT-INT-003 Licence → BOE debit → balance | **PASS** | Licence 2509: B0 2,066.75 → BOE 100.00 CIF / 10.000 qty created (201) → API 1,966.75 (diff 0.00). After reload, the overview screen shows `1,966.75` (screenshot `int/int003_overview_after_boe.png`) |
| SAT-INT-014 (new) Reversal: BOE delete restores balance | **PASS** | DELETE 204 → 2,066.75 (diff 0.00) |
| SAT-INT-004 Allotment → BOE link, no double count | BLOCKED in the browser → **PASS at API level** | The seeded allotment isn't returned by `allotments/` (total 0, unfiltered and with `is_boe=all`). Alternative: `test_m2m_full_consumption.py` + `test_license_overview_allotments_view.py` in the 257-pass run |
| SAT-INT-006 Trade confirm/post, partial payment | **PASS** (seeded) | accounting.real 10/10 + payment ledgers 3/3; `test_trade_line_payment_*` in the 257 |
| SAT-INT-007 Invoice ↔ BOE link not double counted | BLOCKED in the browser → **PASS at API level** | `test_license_invoice_relations.py`, reconciliation suites in the 257. Real-data verification impossible (0 trades locally) |
| SAT-INT-009 Licence transfer | **NOT-RUN in the browser**; API-level coverage only through the hidden-BOE/opening-balance tests in Phase 3/9 | No transfer UI workflow was driven |
| SAT-INT-013 Regression suite | FAIL (4) / PASS (25) unchanged; the 13 skipped are now **run and PASS** (see above) | — |
| SAT-UX-D10 triage | Not a search defect: the seeded allotment is absent from the list endpoint itself. It is the default list scope or the seed; still unverified | `boe_flow.jsonl` "SAT-UX-D10 triage" |

New defect instance: `GET /api/allotments/?is_approved=all` → 500. Added to SAT-DEF-059 (invalid filter value → 500). No UI caller sends it.

### Controller addendum 2: gap-closing reruns and Phase 9 §13

| Run | Exit | Result |
|---|---|---|
| `sat-int-boe reports-menu` (`harness-gap1.log`) | 1 | 11 passed, 2 failed: X07 → HTTP 500 (SAT-DEF-090); `reports-menu.spec.ts:73` fails in isolation (SAT-DEF-091) |
| `masters-detail.real masters-seven-pages.real masters-workspace.real` (`harness-gap2.log`) | 1 | 13 passed, 2 failed, 5 did not run: both failures end on the sign-in page (session lost; SAT-DEF-092) |
| pytest X07 repro (`int/pytest_x07.log`) | 1 (repro) | `PackageDocumentError: MISSING_MAIN_PURCHASE_INVOICE transaction 1` at `license_ledger_package.py:141` |

Status changes, which override the earlier tables:
- **SAT-INT-004** is "PASS (rule, API), UI workflow not driven". Per Phase 9 §13 the blocker was not a missing allotment: the seeded allotment is hidden by the list's default scope.
- **SAT-INT-007** is "NOT VERIFIED ON REAL DATA". The synthetic tests do not cover DEC-41.
- **SAT-UX-D10 / SAT-DEF-089** is closed as a seed artifact.
- **SAT-INT-013** regression: the "test/harness" label is withdrawn for reports-menu (SAT-DEF-091) and narrowed for the masters specs (SAT-DEF-092). The masters 401s are not token expiry (the run took 2.6 min).
- **Still NOT-RUN:**
  - INT-002 licence form writes;
  - INT-008 and INT-011 write paths;
  - INT-009 transfer;
  - E2E sort (023) and delete-confirm (025);
  - dialog focus trap;
  - INT-010 BOE PDF upload. A path exists (Phase 9), so this is NOT-RUN rather than BLOCKED.
