# Licence Management — Freeze Checklist

Status: **NOT FROZEN.** Critical items remain FAILED or OPEN. The module must not be frozen until every critical item is VERIFIED or explicitly approved as an open exception.

Legend: **VERIFIED** — tested against real records or the running app. **FAILED** — checked, and does not meet the requirement. **OPEN** — blocked on a business decision or on work not yet done.

## A. Canonical calculation

| # | Requirement | Status | Evidence |
|---|---|---|---|
| A1 | One canonical calculation engine for licence item balances | VERIFIED | `services/licence_balance_report.py` calls `sale_boe_allocation` and `licence_item_balance`. No view or React component computes balances. |
| A2 | Mutually exclusive CIF components (Debited, Allotted, Invoiced, Available) | VERIFIED | Identity checked on every item; 0 identity failures across 2,348 items. |
| A3 | Quantity classified independently from CIF | VERIFIED | Same function, separate inputs; `test_cif_and_quantity_are_independent`. |
| A4 | Sale-covered BOE not deducted twice | VERIFIED | Sale/BOE suite and DB tests (`CoverageTests`, `test_sale_boe_allocation`). |
| A5 | Over-linked excess counted, not dropped | VERIFIED | Licence 2406: 3,48,905.40 excess counted; invoice and BOE status now show it (`OverLinkedBoeStatusTests`). |
| A6 | Negative balances shown, never zero-floored | VERIFIED | Licence 2406 (−1,26,916.21), 2583 (−1,38,472.67) shown with sign in API and UI. |
| A7 | Allotment and invoice overlap prevented | OPEN | Overlap flagged (`ALLOT_AND_SALE_OVERLAP_UNVERIFIED`) on 69 items; not resolved. Decision O-4. |
| A8 | Previous-owner BOEs deducted from Available CIF and quantity, once, identified by the audit trail | VERIFIED | Approved rule (user instruction, decision O-8). Ownership from the BOE hide/restore records only. Each debit counted once; excess attributed only when all linked BOEs are previous-owner, otherwise flagged. Tests: `test_previous_owner_deduction.py` (19). Population: canonical Available moved in 250 items; change in Debited equals the previous-owner debit exactly; all 2,377 items reconcile. Legacy agreement 33 → 92 of 222 licences. |
| A9 | Purchases / transfers count toward entitlement | OPEN | Not in the canonical balance (O-3). Licence 2583 depends on it. |
| A10 | Cross-item BOE links resolved | OPEN | 81 items flagged. Decision O-2. |
| A11 | Zero-original-CIF items attributed correctly | OPEN | 336 negative items. Decision O-3. |
| A12 | Item drill-down totals reconcile to the item table | VERIFIED | `services/licence_item_drilldown.py` checks its BOE, allotment and invoice totals against the item figures. 2,377 of 2,377 items RECONCILED, 0 errors (`/tmp/lm-measure/drill_population.py`). Caveat: both sides use the same classifier, so this shows agreement, not correctness against source records. |

## B. Single source of truth across consumers

| # | Requirement | Status | Evidence |
|---|---|---|---|
| B1 | Licence list summary uses the canonical engine | VERIFIED | `GET /api/licence-balances/`, 12 queries at any page sizes 10 and 25; legacy comparison only when `?legacy=1`. |
| B2 | Licence detail and item balance use the canonical engine | VERIFIED | Detail and item endpoints; API matches the UI for 2583. |
| B3 | BOE, allotment and invoice tabs use the canonical transactions | VERIFIED | `GET /api/licence-balances/<id>/transactions/`; tie-back to every item balance across 222 licences: 0 failures. |
| B4 | Movement ledgers end at available | VERIFIED | 4,754 ledgers, 0 failures. |
| B5 | Legacy "Balance CIF" removed or reconciled | FAILED | Still displayed beside the canonical figure, flagged MISMATCH for most licences with sales or purchases. Needs decision (which figure is the product's balance). |
| B6 | Dashboard uses the canonical engine | FAILED | Not changed (Milestone 8). |
| B7 | Balance PDF uses the canonical engine | FAILED | Not changed (Milestone 8). Legacy engine. |
| B8 | Balance Excel (single and bulk) uses the canonical engine | FAILED | Not changed (Milestone 8). Bulk path uses the customs formula. |
| B9 | Financial Ledger PDF/Excel uses the canonical engine | FAILED | Not changed (Milestone 8). |

## C. Single-page workspace

| # | Requirement | Status | Evidence |
|---|---|---|---|
| C1 | `/licenses` is the one licence workspace | VERIFIED | Browser: `/licenses?licence=2626` renders the workspace inline above the list; no separate page. |
| C2 | Legacy `/licenses/:id/overview` redirects into the workspace | VERIFIED | Browser: `/licenses/2626/overview` lands on `/licenses?…&licence=2626`. Note: the redirect target requires LICENSE_MANAGER or LICENSE_VIEWER; BOE and TRADE roles that could previously open the overview are now refused (decision needed, see H). |
| C3 | Single overview implementation | OPEN | The overview route is retired (no route serves `pages/license-overview/`). The files remain, unreferenced by routes, until removed in cleanup. |
| C4 | Overview tab (CIF and quantity summaries, warnings) | VERIFIED | Browser on 2626: summaries, hidden-BOE memo, legacy-mismatch flag shown. Headline pill now shows the licence status (was showing 'Reconciled' beside 'Review required'; fixed). |
| C5 | Items & Balance tab with expandable item transactions | OPEN | Drill-down drawers verified in the browser on `/licence-balances/2583` (SR 3: BOE, allotment and invoice drawers, Playwright 6/6). Not yet checked on the workspace `/licenses?licence=2583` tab. |
| C6 | BOE information (formerly the BOEs tab) | VERIFIED | The BOEs tab is removed from navigation (ECC change). Its information is in Items & Balance (BOE Debit Details drawer for each debited figure) and in Reconciliation ("Bills of entry behind the balance", quantity before CIF). Browser: `e2e/licence-workspace.spec.ts`. No API, model or record was removed. |
| C7 | Allotment information (formerly the Allotments tab) | VERIFIED | The Allotments tab is removed from navigation (ECC change). Customer allotments are in Items & Balance (Customer Allotment Details drawer) and allocation issues in Reconciliation. Retired `?tab=allotments` links open Items & Balance. |
| C8 | Invoices & Sales tab | VERIFIED | Browser: 2406 shows OVER-LINKED status on invoices. |
| C9 | Ledger (formerly the Ledger tab) | VERIFIED | The Ledger tab is removed from navigation (ECC change). A movement ledger opens from an item's sources on Items & Balance, and from Reconciliation's item actions. Retired `?tab=ledger&item=` links open that item's ledger. Browser-checked. |
| C10 | Reconciliation tab | VERIFIED | Browser: 2655 shows the unit issue; 2626 shows review status. |
| C11 | Planning tab | FAILED | Not built. The Planning page exists separately at `/planning`. |
| C12 | History tab | FAILED | Not built. |
| C13 | Purchases & Transfers tab | FAILED | Not built; purchases are not in the canonical balance (A9). |
| C14 | Licence actions (Edit, Recalculate, Fetch DGFT, Delete) with permission checks | OPEN | Edit link and Close only. Recalculate, Fetch DGFT and Delete not in the workspace; PDF/Excel not in the workspace. |
| C16 | Workspace navigation: four visible tabs, retired links redirect, no broken routes | VERIFIED | Browser: `e2e/licence-workspace.spec.ts` (6 tests) pass, with no console errors and no API errors >= 400. Unit tests: `licenceWorkspaceUrl.test.ts` (18), `LicenceWorkspace.test.tsx`. Known stale spec, not caused by this change: `e2e/license-overview.accessibility.spec.ts` (2 tests) expect the retired overview page and fail on the redirect. |
| C17 | Licence workspace hosted in the licence accordion (ECC correction) | VERIFIED | Inline expand and collapse, single expansion, Back and Forward, tab survival on reload, the Actions menu and the pinned panel are checked in `e2e/licence-workspace.spec.ts` against the real backend (12 tests pass). The legacy accordion detail is removed. Planning, History and Documents from the legacy accordion are not reachable: open decision (build log, Milestone 12). |
| C15 | Item drill-down: every Debited, Allotted and Invoiced CIF and quantity opens its source rows | VERIFIED | Endpoint `GET /api/licence-balances/<id>/items/<item_id>/drilldown/`. Drawers: BOE Debit Details, Customer Allotment Details, Invoice Details; search, date filter, sort, pagination, CSV export, clickable source records (new tab), close returns focus to the figure. Drawer layout checked at 1440 px. Other widths not checked. Linking and unlinking are not built, so no refresh-after-link path exists yet. |

## D. Data integrity and history

| # | Requirement | Status | Evidence |
|---|---|---|---|
| D1 | No historical record changed by this work | VERIFIED | All work is read-only against the database. Only tests and new modules were added. |
| D2 | No backfill, reclassification or forced balance | VERIFIED | None run. |
| D3 | Uncertain records shown as REVIEW REQUIRED | VERIFIED | Flags on items and licences; 149 licences REVIEW REQUIRED at licence level. |
| D4 | Quantity units verified or explicitly unresolved | OPEN | `mts` on 2655 and 2656 is unresolved (O-1). BOE and allotment quantity units unknown. Totals withheld where unverified. |

## E. Testing

| # | Requirement | Status | Evidence |
|---|---|---|---|
| E1 | Pure calculation tests | VERIFIED | 66 tests across `sale_boe_allocation`, `licence_item_balance`, `financial_position`. |
| E2 | Database-backed report and transaction tests | VERIFIED | 31 tests in `test_licence_balance_report.py`. |
| E3 | API tests (list, detail, item, transactions, permissions, legacy opt-in) | VERIFIED | Included in E2. |
| E4 | Licence list contract still passes | VERIFIED | `test_license_list_filter_contract.py`. |
| E5 | Frontend unit tests for the licence balance screens | VERIFIED | 169 tests across `src/pages/licenses` and `src/pages/licence-balances` (last run). |
| E6 | Frontend tests for the inline workspace | VERIFIED | 23 integration tests in `LicenceWorkspace.test.tsx` plus URL-contract tests (run as part of the 169). |
| E7 | Browser (Playwright) tests for the table and detail | VERIFIED | 5/5 pass against the running app. |
| E8 | Browser tests for the inline workspace and redirects | OPEN | Verified by scripted browser runs (redirect, tabs, 2406/2655/2626/2583 contents, 0 console errors, 0 failed API calls). Not yet committed as a Playwright spec. |
| E9 | Export tests (PDF and Excel match the API) | FAILED | Not built (Milestone 8). |
| E10 | Concurrency tests for allocation writes | FAILED | No write path changed in this work; the existing allocation locks were not re-tested. |
| E11 | Drill-down backend tests (BOE, allotment, invoice, consistency, endpoint) | VERIFIED | `test_licence_item_drilldown.py`: 39 tests pass. Not yet written: cancelled-invoice case (the trade model has no cancelled state) and invoice-represented-by-allotment (no allotment-to-invoice link exists). |
| E12 | Drill-down frontend tests (model, drawer, detail table) | VERIFIED | `drilldownModel.test.ts`, `ItemDrilldownDrawer.test.tsx`, `LicenceBalanceDetail.test.tsx`: 45 pass. Full frontend suite: 107 files, 923 tests pass. |

## F. Security and permissions

| # | Requirement | Status | Evidence |
|---|---|---|---|
| F1 | Licence endpoints require a licence role | VERIFIED | `LicensePermission`; tests for no-role (403) and anonymous (401/403). |
| F2 | Read-only endpoints do not write | VERIFIED | GET only. The report service does not call `save`. |
| F3 | Export and recalculation permissions | OPEN | Not re-audited in this stage. |

## G. Performance

| # | Requirement | Status | Evidence |
|---|---|---|---|
| G1 | List query count does not grow with page size | VERIFIED | 12 queries at page sizes 10 and 25 (was 321 before the legacy comparison was made opt-in). |
| G2 | List latency acceptable | VERIFIED | p50 66.7 ms at 25 rows (was 457.8 ms). |
| G3 | Detail and transactions latency | VERIFIED | Detail 2583 p50 29.8 ms (24 queries); transactions 2583 p50 12.6 ms (11 queries). |
| G4 | Legacy comparison cost | PARTIAL | Default path no longer runs the legacy engine. When `?legacy=1` is requested (the legacy column is visible), it still costs one legacy engine run per licence. |
| G5 | Responsive layout verified at 1920 / 1440 / 1280 / 1024 / 390 px | OPEN | Not yet checked for the workspace. |

## H. Freeze decision

Not frozen. Verification run for the item drill-down stage (exact results):

- Backend: `test_licence_item_drilldown.py` 39 passed; with the other licence suites, 206 passed. pyflakes clean.
- Frontend: full suite 107 files, 923 tests passed; ESLint clean on changed files.
- Browser: `e2e/licence-balances.spec.ts` 6 of 6 passed against the running app (includes the drawer test for SR 3 on licence 2583).
- Population: drill-down reconciled for all 2,377 items (0 mismatches, 0 errors).

Earlier stage (exact results):

- Backend: `test_licence_balance_report.py` 31 passed; with the other licence suites, 160 passed.
- Frontend: `src/pages/licenses` and `src/pages/licence-balances`: 11 files, 169 tests passed; `tsc` exit 0.
- Browser: `e2e/licence-balances.spec.ts` and `e2e/licence-list.spec.ts`: 14 of 14 passed.
- Scripted browser checks (not committed): redirect, tab contents, console errors 0, failed API calls 0.
- Population: transactions tie back to every item balance across 222 licences (0 failures); 0 transaction errors.

Remaining blockers, in priority order:

1. B5 — decide which balance the product shows; retire or reconcile the legacy engine.
2. A9 — purchases and transfers (O-3). Licence 2583 depends on it. A8 (previous-owner usage) is now VERIFIED.
   Also open for the drill-down: credit notes on the sale side are counted as sales (not netted), and purchase-side notes (licence 2525) sit outside the item balance.
3. A7 and C3 — allotment/sale overlap (O-4) and removal of the second overview implementation.
4. B6–B9 — dashboard, PDF and Excel on the canonical engine (Milestone 8).
5. C11–C13 — Planning, History and Purchases tabs.
6. D4 — quantity units.
