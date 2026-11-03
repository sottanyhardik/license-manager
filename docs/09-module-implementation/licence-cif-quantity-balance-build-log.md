# Licence Item CIF & Quantity Balance — Build Log (Milestones 1–8)

Status: **Milestones 1–7 delivered for the item-balance table, overview, item movements and their verification. Milestone 8 (PDF, Excel, dashboard consistency) is not started.** The legacy "Balance CIF" engine still exists and is shown alongside the new figure with a mismatch flag; reconciling the two needs a business decision (see §6). Nothing historical was changed.

Working tree: uncommitted, alongside other people's work (dashboard files, `views/license.py`, `balance_calculator.py`). None of those files was modified by this build. Only `urls.py` (one import and three routes) and `AppRoutes.tsx` (one lazy route) were touched, each with a targeted edit.

## Milestone 1 — Licence item-balance table (live data)

**Implemented**
- Route `/licence-balances` (lazy, ProtectedRoute, LICENSE_MANAGER / LICENSE_VIEWER).
- Table: Licence number, Importer, Expiry, Original CIF, Used through BOEs (debited), Reserved for customers (allotted), Invoiced, Available CIF, Available qty, Status, Open.
- Column menu for the optional columns (original, debited, allotted and invoiced quantities; legacy balance), persisted in localStorage.
- Search (debounced), expiry filter (All / Active / Expired), rows per page, pagination, URL state, loading, empty and error states.
- Negative values are red, signed, and carry an Over-utilised badge. Quantity shows "Unit unverified" instead of a figure when the unit is not verified.
- Status cell opens the reasons (flag explanations).

**Files**
- Backend: `services/licence_balance_report.py` (new), `views/licence_balance_views.py` (new), `urls.py` (routes), `tests/test_licence_balance_report.py` (new).
- Frontend: `frontend/src/pages/licence-balances/` (29 files, including tests and fixtures), `frontend/src/routes/AppRoutes.tsx` (one route), `frontend/e2e/licence-balances.spec.ts` (new).

**Verified**
- API (`GET /api/licence-balances/`): live JSON checked against the contract the UI uses.
- Browser: licence 2583 row shows Original 6,15,999.98, Reserved 1,62,056.05, Invoiced 5,92,416.60, Available −1,38,472.67, matching the API.

**Limits**
- Sorting is not implemented. Export of the table is not implemented.
- At 1280 px the Open action sits at the right edge and needs horizontal scrolling.
- The Over-utilised label appears three times on an over-utilised row (pill, CIF badge, quantity badge). Redundant, not wrong.

## Milestone 2 — Licence overview with CIF and quantity summaries

**Implemented**: `/licence-balances/:licenceId` with two panels (CIF and quantity), each showing Original, Used through BOEs, Reserved for customers, Invoiced and Remaining. Hidden previous-owner BOEs are a memo line. A legacy mismatch appears as an explicit note.

**Verified**: browser text for 2583 matches `GET /api/licence-balances/2583/` for every CIF and quantity figure.

**Limits**: the existing `/licenses/:id/overview` page is unchanged. Two overview pages now exist for the same licence until the team decides which one to keep.

## Milestone 3 — SION item-wise balance table

**Implemented**: one row per SR item (SION, description, HS code, unit, Original, Debited, Allotted, Invoiced, Available for CIF and quantity, status). Each row expands to its customers (sold, covered by BOE, remaining entitlement).

**Verified**: browser for 2583 shows five item rows, matching the five items in the API. Expanding SR 3 lists customers.

**Limits**: HS code shows as "Unmapped" for 1,052 items (master-data gap).

## Milestone 4 — Item movement ledgers (CIF and quantity)

**Implemented**: `GET /api/licence-balances/<id>/items/<item_id>/` returns `cif_movements` and `qty_movements`. Row kinds: ORIGINAL, SALE, SALE_COVERED_BOE (memo), BOE_DEBIT, OVER_LINKED_EXCESS, ALLOTMENT, HIDDEN_PREVIOUS_OWNER_BOE (memo). Each row carries its source type and id. The UI shows the ledger inline below the item table.

**Verified**
- Browser: the SR 3 CIF ledger for 2583 ends at −1,72,575.97 and the quantity ledger at −1,62,166.480; both are labelled "matches available".
- Population: all 4,754 item ledgers (CIF and quantity) end exactly at their item's available balance (`ledger_invariant.py`, 0 failures).

**Limits**: ledger rows are not yet linked to their source records in the UI. The source type and id are returned, but the UI does not navigate to them.

## Milestone 5 — Verification of actual licences

| Licence | What was checked | Result |
|---|---|---|
| 2583 | Items, sales, BOE links, allotments, ledgers, UI | Allotted 1,62,056.05 is hidden by the legacy engine, which excludes any allotment with a BOE link. One allotment (7208, SR 4) is linked to BOE 27499, which debits licence 2584, so the reservation is cross-licence. Allotment 7246 (SR 3) is linked to BOE 27836, which also sits under sale LGL/0066 for the same customer (118). Both are flagged for review, not resolved. |
| 2406 | Over-linked BOE case | Excess 3,48,905.40 counted as debited; matches the audit to the paisa. |
| 2655, 2656 | Unit ambiguity | Units `mts`. Items are sold in full at their authorised quantity. Quantity reported as unit unverified; CIF reconciles. |
| 2514 | Hidden previous-owner BOEs | 29 of 31 BOE rows are hidden under the engine's rule; memo only, not deducted. |
| 27318 (licence 1843) | Zero-original item with a sale | Original 0, invoiced 7,062.51, flagged for attribution review (O-3). |
| All 222 licences | Service run, read-only | Completed in 3.9 s for the whole batch. Statuses: 149 REVIEW REQUIRED, 62 OVER-UTILISED, 11 RECONCILED (licence level). |
| All 2,348 items | Independent item audit (corrected, see §7) | 0 field differences across debited, allotted, invoiced and available CIF, and available quantity. |

**Caveat on the independent check**: the audit and the service were both written by this team and share the same concepts. Agreement shows the two implementations match each other. Correctness against the source records was checked case by case (the table above), not by the audit alone.

## Milestone 6 — Defects corrected

Corrected in this build:
- The audit script did not exclude previous-owner BOEs, although the audit document said it did. Fixed; the CSV and every figure in the audit document were regenerated.
- The audit script left over-linked excess out of Debited, although the approved rule counts it. Fixed.
- The audit document said licences 2655 and 2656 had no sale activity. Corrected: both are sold in full.
- The service assigned allotments linked to another licence's BOE no flag. Now flagged (ALLOTMENT_LINKED_BOE_NOT_ON_ITEM).

Found, deliberately not changed:
- The legacy engine's allotment rule (any BOE link removes the whole allotment) hides reservations, for example 1,62,056.05 on 2583. Changing the legacy engine changes every balance it produces, so it waits for the decisions in §6.
- The legacy engine and the canonical report disagree for most licences with sales or purchases. The UI shows both with a mismatch flag.

## Milestone 7 — Regression testing

| Suite | Command | Result |
|---|---|---|
| Backend: report (DB) + item + sale + financial + licence list contract | `pytest -o addopts= apps/license/tests/test_licence_balance_report.py apps/license/tests/test_licence_item_balance.py apps/license/tests/test_sale_boe_allocation.py apps/license/tests/test_financial_position.py apps/license/tests/test_license_list_filter_contract.py` (with `TEST_DB_NAME` set) | **153 passed** |
| Frontend: licence balances unit tests | `npx vitest run src/pages/licence-balances` | **71 passed** (5 files) |
| Frontend: typecheck | `npx tsc -p tsconfig.json --noEmit` | exit 0 |
| Frontend: lint | `npx eslint src/pages/licence-balances src/routes/AppRoutes.tsx` | exit 0 |
| Frontend: production build | `npm run build` (run by the UI build; exit 0 reported) | exit 0 (not re-run here) |
| Browser: licence balances spec | `LM_REAL_E2E=1 PLAYWRIGHT_BASE_URL=http://localhost:5173 npx playwright test e2e/licence-balances.spec.ts` | **5 passed** |
| Pyflakes on new backend modules | `pyflakes` | clean |

Not run in this build: the full backend licence suites (existing modules unchanged, but not re-run here), the full frontend suite (run earlier by the UI build: 101 files, 812 tests passed).

## Milestone 8 — PDF, Excel and dashboard consistency

**Not started.** The balance PDF, the bulk balance Excel and the dashboard still use their own figures. They must be moved onto `licence_balance_report` before this milestone can be claimed. Nothing in this build changes them.

## Milestone 9 — Item drill-down (BOE, allotment and invoice drawers)

**Implemented**
- `GET /api/licence-balances/<id>/items/<item_id>/drilldown/` (read-only, `LicensePermission`). Built from the same loader and per-item classification as the item table (`services/licence_item_drilldown.py`).
- Items & Balance: Debited, Allotted and Invoiced CIF and quantity figures open a right-side drawer. Each row expands to three source sections (BOE debits, customer allotments, invoices), each with a summary and View all.
- Drawer: totals from the report, search, date filter, sort, page size and pagination, CSV export, expandable rows with linked sales/BOEs, flags, and source records opened in a new tab. Close returns focus to the figure that opened it.

**Verified**
- Backend 39 tests; population reconciliation 2,377 of 2,377 items, 0 errors.
- Browser: licence 2583 SR 3 drawers (BOE 5 rows, allotment ALLOT-7246 partly linked, invoices 5 rows summing to 5,34,798.15).

**Limits (not built or not tested)**
- Linking and unlinking UI/API: not built, so refresh after a link change has nothing to refresh yet.
- Excel and PDF export of the drawer: not built (CSV only).
- Cancelled-invoice case: the trade model has no cancelled state; not tested.
- Invoice-represented-by-allotment: no allotment-to-invoice link exists; reported as "Not recorded".
- The spec's `FULLY UTILISED` allotment status is not produced, for the same reason. Allotments show `LINKED` when fully covered by BOEs on the item.
- Allotment `RELEASED` shows as CANCELLED. `COMPLETED` and `REACTIVATED` show as excluded from the balance (REACTIVATED is flagged for review).
- Unlike the spec's `UNLINKED`, the existing labels `NOT LINKED` (invoices) and `UNCOVERED` (BOEs) are kept for consistency with the BOEs and Invoices tabs.
- Responsive layout of the drawer at 1024 and 390 px: not checked.

## Milestone 10 — Previous-owner BOEs deducted (decision O-8)

Approved by user instruction ("Additional Business Rule — Previous-Owner BOE Deduction").

**Rule.** A previous-owner BOE is debited like any other BOE, so it reduces Available CIF and Available quantity. Ownership comes only from the BOE hide/restore audit trail (`annotate_and_exclude_hidden`), never from importer name or BOE date. Each debit is counted once:
- A BOE covered by a sale is not deducted again: the sale is already invoiced.
- An allotment's residue is reduced once, by the BOE on the same item (D-1 §3.4).
- Over-linked excess is attributed to previous ownership only when every BOE linked to that sale is previous-owner. Mixed excess stays current-owner and is flagged `OVER_LINKED_MIXED_OWNERSHIP`.

**Statuses.** A previous-owner BOE shows `PREVIOUS OWNER — DEDUCTED` when nothing covers it. The instruction named one status. I added `PREVIOUS OWNER — PARTLY DEDUCTED` and `PREVIOUS OWNER — COVERED BY SALE` because a covered BOE is not deducted, and the single label would be untrue. Please confirm.

**Presentation.** Quantity is shown before CIF for every figure, in the BOE drawer, its totals, expansions and CSV export. The totals include a separate **Previous-owner BOE debit** line. The licence summary shows **Of which previous-owner BOEs (deducted)**. The old memo note is gone.

**Impact** (snapshot of every item before and after, real database):
- Available CIF changed on 250 items across 95 licences. Available quantity changed on 247 items across 93 licences.
- The change in Available equals the change in Debited exactly. Allotted and Invoiced did not move.
- The sum of previous-owner debit equals the change in Debited exactly (−50,761,431.15 in total).
- Item status: 176 REVIEW REQUIRED → OVER-UTILISED, 46 REVIEW REQUIRED → RECONCILED. The old memo flag had forced REVIEW REQUIRED.
- Licence status: 16 → OVER-UTILISED and 13 → RECONCILED. Over-utilised licences: 62 → 78.
- Agreement with the legacy engine: 33 → 92 of 222 licences. The legacy engine already deducts previous-owner usage through its opening balance. Licence 2626: canonical available was 1,20,285.51 before this change and is now 10,607.85, which equals the legacy figure. 129 licences still differ, for other reasons (purchases, O-3).
- All 2,377 item drill-downs reconcile.

**Verification.**
- Backend: `test_previous_owner_deduction.py` (19 tests) covers available CIF and quantity, the duplicate cases (sale, allocation and allotment overlap, mixed excess), identification by audit trail only, both values in the BOE summary, the item breakdown, exact reconciliation, the ledger, the transactions endpoint and the API.
- Backend suites: 225 passed, pyflakes clean.
- Frontend: full suite 107 files, 930 tests passed; tsc and ESLint clean on changed files.
- Browser: `e2e/licence-balances.spec.ts` 6 of 6 passed. The BOE drawer on licence 2626 SR 1 was checked at 1440 and 1024 px.

**Found and fixed during this work.**
- The drill-down set row `kind` to the status label, so excess rows were not recognised as excess. Fixed: `kind` is `OVER_LINKED_EXCESS` and the label is in `status`.
- The over-linked excess of one previous-owner BOE (licence 2018, item 30431, 36,118.76) was counted as debit but not as previous-owner. Fixed by the attribution rule above.

**Not changed.**
- Dashboards, PDF and Excel still use the legacy engine (Milestone 8). Their previous-owner line in `FinancialOverview.tsx` still says "pending the business decision DEC-010". DEC-010 is not marked resolved in `V1_DECISION_REGISTER.md`; its question 3 on previous-owner utilisation is answered by this instruction and should be recorded there.
- No historical source record was modified. No bulk reclassification was run.

## Milestone 11 — Workspace navigation and balance details (ECC change)

**Navigation.** The BOEs, Allotments and Ledger tabs are removed from the licence workspace. The visible tabs are Overview, Items & Balance, Invoices & Sales and Reconciliation. No API, model, record or service was removed.
- Retired links `?tab=boes`, `?tab=allotments` and `?tab=ledger` open Items & Balance. A `?item=` value is kept, so `?tab=ledger&item=` still opens that item's movement ledger.
- The three tab modules (`BoesTab`, `AllotmentsTab`, `LedgerTab`) were deleted because nothing referenced them. The backend transactions endpoint they read is unchanged, and Reconciliation now uses it.

**Where the information went.**
- Items & Balance: each debited, allotted and invoiced figure opens its drawer. The expansion has the three source sections.
- Reconciliation: source-level differences (drawer totals against the item figures, per figure), allocation issues (BOEs, invoices and allotments that need review, each with its quantity and CIF), and the bills of entry behind the balance.
- Invoices & Sales: unchanged. It already lists related BOEs and related allotments per invoice.

**Quantity before CIF.** Applied to: the BOE, allotment and invoice drawers (the CIF/Quantity toggle is removed from all three), their totals, expansions and CSV exports; the Items & Balance table; the licence balance panels (Quantity panel first); the movement ledger (quantity ledger first); and the Reconciliation tables. Every quantity shows its unit as recorded. A quantity whose unit is not verified shows "Unit unverified", and the unit is never converted or assumed.

**Previous-owner BOEs** stay deducted (Milestone 10). The BOE drawer summary follows the spec order: Covered by Sale, Uncovered BOE Debit, Over-linked Excess, Debited (Item Figure), Previous-owner BOE Debit.

**Backend (additive, no existing value changed).**
- `GET /api/licence-balances/<id>/source-reconciliation/`: per item, the drill-down reconciliation and the allocation issues (BOE cross-item, over-linked, mixed-owner excess, invoices over-linked or with a linked BOE that debits another item, allotments needing review, sale overlap, recorded releases). Built from the same per-item drill-down as the item view.
- Transactions BOE rows gain `covered_qty`, `uncovered_qty` and `linked_sale_invoices`.
- Invoice drill-down totals gain `covered_by_boe_qty`, `uncovered_qty` and `over_linked_qty`.

**Verification.**
- Backend: 237 passed across the licence suites (new: `test_licence_source_reconciliation.py`, 11 tests; invoice-quantity totals test). pyflakes clean.
- Frontend: full suite 107 files, 941 tests passed. `tsc` clean. ESLint clean on every changed file; eight pre-existing warnings remain in files this change does not touch.
- Browser (`e2e/licence-workspace.spec.ts`, real backend): 6 of 6 pass in each of three runs, and in the final run. Covers the four tabs, the retired-link redirects, the BOE drawer layout and summary, the Reconciliation sections, the previous-owner badge, and the drill-down summary matching the API. Console errors and API errors >= 400 are checked in each flow.
- Existing browser specs: `licence-balances` (6) and `licence-list` pass.

**Known issues.**
- One transient failure: on licence 2626, the Reconciliation "Source-level reconciliation" request showed an error once, during one run. The endpoint returned 200 for 2626 in every direct call and in the next three runs. I did not find the cause. The retry logic is in `retryTransient`.
- `e2e/license-overview.accessibility.spec.ts` has two tests that expect the retired overview page (`License Overview` heading). They fail on the redirect, which has been in place since an earlier milestone. Not changed.
- The Invoices & Sales table is a purchase and sale ledger in CIF and INR. It has no quantity, so the quantity-first rule does not apply to it. Its CSV export is unchanged.
- Dashboard, PDF and Excel exports are on the legacy engine (Milestone 8) and are not covered by this change.

## Milestone 12 — Workspace inside the licence accordion (ECC correction)

**What changed.**
- `/licenses` is the only licence screen. Clicking a licence row expands it inline, and the licence workspace renders inside the expanded row. Clicking the open row collapses it. Clicking another row collapses the first and expands that one. Only one row is open at a time. The state lives in the URL (`licence`, `tab`, `item`).
- The legacy accordion detail (info strip, Overview, Planning, Documents and History tabs, action panel) is removed. `pages/masters/tables/LicensesTable.tsx` and `LedgerTab.tsx` are deleted. The list is now `pages/licenses/LicenseAccordionList.tsx`.
- One workspace component (`LicenceWorkspace`) serves every licence. It mounts only for the open licence, so no other licence's workspace or queries run.
- Licence operations moved into the workspace header's Actions menu. Balance PDF and Balance Excel are available to all users. Auto plan, Fetch from DGFT and Delete licence need LICENSE_MANAGER. The Individual Item CIF switch, Edit, Refresh and Close stay in the header.
- If the open licence is not on the current page (filters, page or a deep link), its workspace stays open above the list with a notice. The panel appears only once the list has settled, so the workspace mounts once, in its row.
- `/masters/licenses` redirects to `/licenses` and keeps the query string.
- Fix: the Individual Item CIF switch now refreshes the workspace balance and the list's collapsed balance. It previously refreshed only legacy keys, so figures could stay stale after a switch.
- Fix: Enter on the licence-number button no longer also toggles the row. Before, it opened the documents PDF and toggled the row.

**Decisions taken.**
- Delete and Fetch from DGFT stay owned by the list page, because they change the list and the open licence. The menu receives them as callbacks.
- Deleting the open licence closes its workspace.
- The `MasterList` licence branch and its import are removed, and so are the `handleFetchOwnership` and `fetchingOwnershipIds` it alone used.

**Verification (this run).**
- Vitest, full frontend suite: 107 files, 945 tests passed.
- Vitest covers the accordion: expand and collapse, single expansion, the pinned panel, and the Actions menu for a viewer and for a licence manager.
- `tsc --noEmit`: clean. ESLint: clean on every changed file.
- Playwright against the live backend and database (`e2e/licence-workspace.spec.ts`, `LM_REAL_E2E=1`): 12 of 12 pass. The new flows are inline expand and collapse (URL and workspace count checked), a second row collapsing the first, Back closing and Forward reopening, the selected tab surviving reload, the Actions menu, and the pinned panel. Console errors and API errors of 400 or more are checked in every flow except the pinned panel. That flow uses a non-existent licence, so it logs the expected 404s.
- No backend code changed in this milestone, so backend suites were not re-run.

**Not verified.**
- The switch invalidation fix has no automated test. I did not toggle the switch in the browser, because that changes a real licence record.
- Refresh, Auto plan and Delete were not exercised in the browser, because they change data.
- The layout is not compared against "Screenshot 2". The file was not found in Desktop, Downloads or Pictures.

**Regressions to decide.**
1. The legacy Planning (plan editor), History (ownership transfers) and Documents (document list) tabs are no longer reachable from the list. Still available: the merged-documents PDF through the licence number, the current owner in the workspace header, and the ownership fetch in Actions. Decision needed: whether the plan editor and transfer history return as workspace tabs.
2. The workspace has no unsaved-changes state. Edit opens the existing edit page, so there is nothing to warn about inside the accordion.

## Milestone 13 — Workspace layout refinement (presentation only)

**What changed.**
- Accordion row, collapsed: licence number, Active or Expired, purchase status. Expanded: licence number and the collapse indicator only. Details and balances are in the workspace (`LicenseAccordionList.tsx`).
- Workspace header: one place for the licence number, validity, the ten metadata fields (four columns on wide screens, two on tablet, one on mobile), the two available cards side by side, and the operations on the right (`LicenceWorkspaceHeader.tsx`). The "Licence workspace" label is removed to save a line.
- Duplicates removed inside the workspace: the "Remaining" figure at the foot of both balance panels, the reconciliation status row on Overview, the "Available" row of the reconciliation balance table, and the "Reconciled available" line of the legacy comparison. The available figure now appears once, in its card. The standalone balance page keeps its panels unchanged (`BalanceSummaryPanels`, `showAvailable`).
- Over-utilised badge suppressed inside the available cards, where the status pill already says it. It stays in the item table (`BalanceAmount`, `overUtilisedBadge`).
- Item table: descriptions truncate to one line, with the full text in the tooltip and the DOM. Cell padding reduced. The table still scrolls horizontally inside its container.
- Validity pill is shared by the accordion row and the header (`ValidityPill.tsx`).

**Decisions and conflicts.**
- Collapsed Available CIF is not shown. The list's balance field (`get_balance_cif`) is the legacy Financial Ledger figure. Against the canonical available CIF on 25 live licences, it matched for 9 and differed for 16. Some gaps were large, for example licence 2460: 323,386.15 legacy against -461,801.54 canonical. Showing it as "Available CIF" would contradict the expanded card. The brief says the collapsed summary "can" show it, and it also requires the canonical engine, so it was left out. Options: a canonical figure on the list endpoint (a backend change, needs approval), or keep it out.
- The licence number appears twice in the expanded state: once in the row (required by "collapsed header shows only the number") and once as the workspace heading (required by "expanded workspace shows licence number and status"). Both were kept. Pick one if the duplicate is unwanted.
- The collapsed status is Active or Expired, from the licence dates. The earlier Exhausted and Planned labels came from the legacy balance and are removed.

**Verification (this run).**
- Vitest, full frontend suite: 107 files, 949 tests passed. Four tests were added for the duplicate-figure rules.
- `tsc --noEmit`: clean. ESLint: clean on every changed file.
- Playwright, live backend, real records (`e2e/licence-workspace.spec.ts`): 15 of 15 pass. The new checks are the outer row contents, the ten metadata labels in order, a single "Available CIF (USD)", no "Remaining" or "Balance CIF", the metadata column count (4 at 1440px, 2 at 1024px, 1 at 390px), no page overflow at each width, and the truncated description style. Screenshots were reviewed.
- Existing `e2e/licence-balances.spec.ts`: 6 of 6 pass.
- No calculation, API, record or permission was changed.

## Milestone 14 — Accordion header: the licence summary (final ECC spec)

**What changed.**
- The accordion header is the licence summary, collapsed or expanded. It shows the licence number, status, licence date, expiry date, ledger date (once), Available balance CIF (USD), exporter, current owner and norm class. The workspace opens underneath (`LicenseAccordionList.tsx`).
- Layout: first line is number, status, the three dates, and the available CIF on the right. Second line is exporter, owner and norm class. At mobile width the fields wrap.
- The toggle is a sibling of the summary, not its parent. The licence-number button is therefore no longer nested inside a button.
- Workspace header (`LicenceWorkspaceHeader.tsx`): the title is "Licence workspace". It shows only importer, IEC, port, purchase status, and the Available quantity card. The number, status, dates, owner, exporter, norm class and Available CIF are no longer repeated here. The owner request is removed from the workspace.
- Status badge (`LicenceStatusBadge.tsx`): ACTIVE, EXPIRED, CANCELLED, SUSPENDED, PENDING and INACTIVE have icons and colours. Any other code shows with the server's label in the neutral style.
- `ValidityPill.tsx` and the workspace owner hook (`useLicenceOwner`) are removed. The `LicenceOwnership` type and its test fixture are removed.

**Backend (additive, list endpoint only).**
- `LicenseListSerializer` (a subclass of the detail serializer, used only for `GET licenses/`) adds `current_owner_name`, `licence_status_code`, `licence_status_label` and `available_cif`. The detail, create and update responses are unchanged.
- `available_cif` is the canonical available CIF, batched once per page by `available_cif_by_licence`. It is the same figure the workspace shows. It is not the legacy Financial Ledger balance (`get_balance_cif`), which still feeds other views.
- Status comes from `services/licence_status.py`. It follows the rules `check-validity` already uses. EXPIRED means the licence expiry date is before today. INACTIVE means the stored `flags.is_active` is false. Otherwise ACTIVE. The stored `flags.is_expired` is not used, because it is denormalised and differs from the dates.

**Decisions and open questions.**
- The database has no licence status column. The status set is therefore ACTIVE, EXPIRED and INACTIVE. CANCELLED, SUSPENDED and PENDING have no stored source, so none is produced. The UI supports them when a source exists.
- Two stored flags have unconfirmed meanings. `flags.is_null` is True for 109 of 222 licences, and the default list hides them. `flags.is_active` is False for 108. Which of these means "cancelled" or "suspended" is a business question for you.
- The list's query-count ceiling in `test_license_list_filter_contract` moves from 20 to 24. The canonical batch adds a fixed 4 queries per page, for 21 in total. The count does not grow with page size.
- The licence number appears in both the expanded row and the workspace, as the spec requires in two places. The workspace heading is now "Licence workspace", not the number.

**Verification (this run).**
- Backend, new `test_licence_list_summary.py`: 8 of 8 pass. They cover the summary fields, the owner, status from the expiry date and the active flag, the canonical CIF matching the detail endpoint, and the detail response being unchanged.
- Backend, full `apps/license` suite: 2,298 passed and 11 failed before the fixes below. Eight of those failures also occur without this change: an unchanged copy of the backend, with only the list view reverted, fails the same eight (Excel exports, item pivot, plan utilisation, overview summary). Two were seed-command tests that refuse a database not named `test_*`; they pass with a compliant name. One was the query ceiling above.
- Frontend, full Vitest: 950 of 951 pass. The one failure is in `licenseLedgerPackageDownloads.test.ts`, which I did not touch. It passes when run alone, twice.
- `tsc --noEmit` is clean. ESLint is clean on every changed file.
- Playwright, real backend and records: a full run of `e2e/licence-workspace.spec.ts` passed 15 of 15 once. Other full runs stopped at a different test each time, with blank or slow screens, 429 responses or a click blocked by the fixed bottom bar. Fixes for the click case are in the spec. The 429s come from the API's burst limit (`apps/core/throttling.py`, 180 requests per minute per user). The end-to-end suite makes enough requests to reach it, and the UI does not retry throttled calls. This is an open issue; see below.
- Screenshots reviewed: expanded header at 1440px and 390px. All nine fields are visible in both states. The mobile switch was squeezed, and is fixed with `shrink-0`.

**Open issues.**
- The app does not retry or recover from HTTP 429. A throttled request can leave a section loading or a screen blank. The browser suite triggers the limit on repeat runs.
- The intermittent 2626 reconciliation stall noted in Milestone 12 was not diagnosed. It may be the same throttling.

## Milestone 15 — Accordion state: transient workspace, page-level close rules

**What changed.**
- The open licence, its tab and its item are page state (`workspace/useLicenceWorkspaceState.ts`). They are not in the URL, storage or history. A reload starts with no licence open, and a `?licence=` link no longer opens one.
- The list page closes the workspace when a filter or the search changes. The check runs during render, so the closed workspace never shows beside the new results (`LicenseListPage.tsx`). Page and page size do not count, so paging keeps the licence open.
- The list hook no longer carries workspace keys through its writes (`useLicenseListState.ts`).
- Retired `/licenses/:id/overview` and `/licenses/:id/balance` routes go to the list. They no longer open a licence (`routes/AppRoutes.tsx`).
- Removed: `workspace/licenceWorkspaceUrl.ts`, `workspace/useLicenceWorkspaceUrl.ts` and their tests. Added: `workspace/workspaceTabs.ts`, `workspace/useLicenceWorkspaceState.ts` and its tests.
- The accordion header uses a CSS grid, with no absolute positioning. The toggle is a chevron button in the right column. The header's own click toggles the row only when the click is outside a button or link (`LicenseAccordionList.tsx`).
- The Individual Item CIF switch is not stretched by the app's global 44px mobile button minimum (`IndividualItemCifSwitch.tsx`).

**Decisions.**
- Sorting: the licence list has no sort control, so the sort rule has nothing to apply to. If a sort is added, it should close the workspace.
- Deep links and browser history no longer restore the workspace. That is what the reload rule requires.
- The workspace remounts only when a page change moves its licence between the row and the pinned panel. Tab changes, Refresh and drawers do not remount it.

**Verification (this run).**
- Vitest, full frontend suite: 107 files, 944 tests pass. The 18 URL-contract tests were removed with the URL contract. The new hook tests (9) were added.
- `tsc --noEmit` is clean. ESLint is clean on every changed file.
- Browser (`e2e/licence-workspace.spec.ts`, real backend and records): 18 of 18 pass in each of the last two full runs. The checks cover the header fields, Ledger Date once, positive, negative and zero CIF, a missing owner, layout at 1440, 1024 and 390px (no overflow, no clipping, CIF and toggle position), paging with the notice, filter and search closing the licence, reload closing it, Refresh and tab changes keeping it open, Close, and opening another licence. The existing drawer, reconciliation, previous-owner and drill-down checks still pass.
- Browser (`e2e/licence-list.spec.ts`, existing): 9 of 9 pass.
- Screenshots of the header were reviewed at 1440, 1024 and 390px.

**Not verified.**
- Statuses other than ACTIVE and EXPIRED. The database has no INACTIVE, CANCELLED, SUSPENDED or PENDING licence, so no real record exercises them. A unit test covers the unknown-code path with CANCELLED. INACTIVE has no test.
- Licence numbers longer than 10 characters. None exist in the database.
- PDF and Excel downloads were not clicked in this run.

## Milestone 16 — Internal trades excluded from external utilisation (licence 5611004885)

**What changed.**
- New audited record `TradeUtilisationClassification` (one per trade: INTERNAL, EXTERNAL or REVIEW, with reason, evidence, authoriser and time). Migration `trade.0011`, table only. Protected from deletion while it exists.
- No record means EXTERNAL, which is how every trade was treated before. Only an INTERNAL record changes arithmetic. REVIEW is a flag and changes nothing.
- Canonical engine (`licence_balance_report.py`): INTERNAL sale trades are removed from the utilisation inputs, so they cannot be matched to a BOE, reduce the balance or be over-linked. Their own BOE debits still count as ordinary, unlinked debits. Internal sales appear in the item ledger as memo rows that the running balance skips.
- Drill-down (`licence_item_drilldown.py`): INTERNAL invoices are listed with their reason and authoriser. Totals add `internal_sold_cif`, `internal_sold_qty` and `gross_sold_cif`. `sold_cif`, `uncovered_cif` and `current_balance_cif` stay external-only.
- Invoices & Sales ledger (`invoice_ledger.py`): rows carry their classification. Summary adds `gross_internal_sale_cif`, `gross_sale_all_cif` and `internal_row_count`. `gross_sale_cif` and the company balances are external-only.
- Command `set_trade_utilisation_classification`: dry run by default, `--apply` to write, `--reason` required, names the authoriser. It writes only the classification row.
- UI: Invoice Details shows separate internal and external figures, an INTERNAL TRADE label on the invoice, and its reason. The ledger shows the badge and the internal total beside the external sale.

**Data written (approved by the business owner, 2026-11-03).** Trades 637 (SC/2026-27/0001) and 638 (GST/26-27/021), both INTERNAL, authorised by `hardik`. No other row or licence changed.

**Evidence and reconciliation.** Snapshots were taken before the write (production path, and an evidence override that writes nothing). After the write, the production output matched the override output with zero differences across every item, drill-down row, ledger memo row and reconciliation field.

| Figure (licence 5611004885) | Before | After |
|---|---:|---:|
| SR 1 invoiced CIF | 338,984.78 | 0.00 |
| SR 1 uncovered CIF | 338,984.78 | 0.00 |
| SR 1 internal CIF (display only) | 0.00 | 338,984.78 |
| SR 1 available CIF | −169,492.39 | +169,492.39 |
| SR 1 status | OVER-UTILISED | RECONCILED |
| SR 1 available quantity | 61,321.800 | 61,321.800 |
| SR 20 (all figures) | unchanged | unchanged |
| Licence invoiced CIF | 508,459.58 | 169,474.80 |
| Licence available CIF (sum of items) | −338,967.19 | +17.59 |
| Stored `LicenseBalance` and legacy ledger | 169,492.39 | unchanged |
| Invoice ledger gross sale (external) | 508,459.58 | 169,474.80 |
| Invoice ledger gross internal sale | 0.00 | 338,984.78 |
| Invoice ledger current balance (purchases − external sales) | 169,492.39 | 508,477.17 |
| Company balance: Sambhav | 0.00 | 169,492.39 |
| Company balance: VISION | 0.00 | 169,492.39 |

**Verification.**
- Backend, new `test_internal_trade_exclusion.py`: 16 of 16 pass. Covers internal and external sales, a BOE on an internal sale (counted once), REVIEW changing nothing, cross-item isolation, internal purchases, drill-down labelling, workspace transactions, the ledger split, the company balance, dry run, apply, required reason, unknown trade or user, and PROTECT on delete.
- Backend, full `apps/license` and `apps/trade`: 2,371 passed. The 8 failures are the same pre-existing set (Excel exports, item pivot, plan utilisation, overview summary), unchanged by this milestone.
- Frontend, `tsc --noEmit` clean. Full Vitest 946 of 946. ESLint clean on changed files.
- Browser, new `e2e/internal-trades.spec.ts`: 4 of 4 pass on the live record. Existing `licence-workspace` 18 of 18, `licence-list` 9 of 9, `licence-balances` 6 of 6.

**Open decisions (not changed here).**
1. **Purchase counterparts.** Trades 635 (GST/26-27/021, purchase by Sambhav) and 636 (P-LGL/2026-27/0001, purchase by LABDHI) are still EXTERNAL. They do not affect utilisation, because purchases never add entitlement. They do move the company balances above (Sambhav and VISION show 169,492.39 each). Classify them as INTERNAL too, or leave them?
2. **Licence headline.** The licence summary adds item values, so item 1 (+169,492.39) and item 20 (−169,474.80) net to +17.59. Your rule forbids this offset. The old −338,967.19 was also a sum, but of two negatives. Changing the summary changes every licence with mixed items. Decide the headline convention.
3. **BOE 27894 (item 20).** Still REVIEW. Filer APHRODITE FOODS LLP has no documented entitlement.
4. **Legacy PDF and Excel.** Still use the legacy engine (169,492.39 and 17.59). Not changed in this milestone.
5. **Invoice 661.** Five generated invoice versions with unrelated sale bill values. Not changed.

## Milestone 17 — Licence-level CIF control when Individual Item CIF is OFF

**Rule.** The persisted `individual_item_cif_override` decides the mode. Only a literal `True` enforces CIF per item. `NULL` and `False` are licence-level control.

- **OFF (NULL or False).** The licence's pooled CIF decides over-utilisation. Licence available CIF = authorised licence CIF − verified net CIF utilisation (the pooled figure from the canonical engine). An item's negative CIF is attribution only: it keeps its figures, shows the status `LICENCE-LEVEL CONTROL` ("Licence-level CIF control"), and is not OVER-UTILISED by its own sign. Item CIF is REVIEW REQUIRED only when its attribution is unverified (existing flags `CROSS_ITEM`, `ALLOT_AND_SALE_OVERLAP_UNVERIFIED`, `ALLOTMENT_LINKED_BOE_NOT_ON_ITEM`, `OVER_LINKED_MIXED_OWNERSHIP`, or a raw REVIEW status).
- **ON (True).** Unchanged. Each item's CIF is enforced on its own. No cross-item netting enters the item status.
- **Quantity.** Unchanged in both modes. An item can be quantity OVER-UTILISED while its CIF is not.
- **Unverified sales.** A sale with no classification record counts as external (the base). If the base licence total is negative and that result depends on an unverified sale, the engine also re-runs the licence with those sales treated as internal:
  - base not negative → no CIF over-utilisation;
  - base negative, no unverified sale → OVER-UTILISED;
  - base negative, alternative also negative → OVER-UTILISED, flagged `LICENCE_CIF_DEPENDS_ON_UNVERIFIED_SALE`;
  - base negative, alternative not negative → REVIEW REQUIRED, flagged the same way.

**Where it is implemented (one canonical calculation).** `backend/apps/license/services/licence_balance_report.py`: `_attribute_item_cif`, `_apply_cif_control_scenarios`, `_apply_licence_cif_control`, `_licence_status`, `_unverified_sale_trade_ids`. The serialised summary gains `cif_control` and `cif_scenarios`. The serialised item CIF block gains `cif_control` and, under OFF, `raw_status`. Existing keys are unchanged. The persisted toggle, the original licence CIF, invoices, trades, BOEs, allotments and historical balances are not written.

**Frontend.** `BalanceAmount` now takes over-utilisation from the backend flag only. The sign-based fallback is removed. Under licence-level control the available figure is neutral, with a "Licence-level CIF control" label, and never red or badged. `labels.ts` gains the status label and the scenario flag text. The CIF card on the licence summary states which control applies. No status is computed in React.

**Reconciliation (before and after, read-only).** Captured with `/tmp/cif_full_snap.py` and compared by `/tmp/cif_diff.py` across all 222 licences and 2,377 items. The before snapshot was taken before the code change, and the after snapshot after it, on the same database state.

| Measure | Result |
|---|---|
| ON licences (3) | No change in any figure or status |
| Item CIF amounts, all licences | No change |
| Quantity amounts and statuses, all licences | No change |
| OFF licences (219): licence CIF over-utilisation | 65 change from OVER-UTILISED to REVIEW REQUIRED (base negative, alternative not negative). None change the other way |
| OFF licences: licence CIF status | 110 REVIEW REQUIRED → RECONCILED; 65 OVER-UTILISED → REVIEW REQUIRED |
| OFF licences: item CIF OVER-UTILISED | 542 items: 437 → LICENCE-LEVEL CONTROL, 105 → REVIEW REQUIRED |
| OFF licences: item CIF RECONCILED | 1,809 items → LICENCE-LEVEL CONTROL (label only; amounts unchanged) |
| OFF items: item status | 339 OVER-UTILISED → RECONCILED; 180 OVER-UTILISED → REVIEW REQUIRED |

Evidence licences:

| Licence | Mode | Before (licence CIF) | After (licence CIF) | Item SR 3 CIF | Quantity |
|---|---|---|---|---|---|
| 0311051322 | OFF | −336,194.69 OVER-UTILISED | −336,194.69 OVER-UTILISED (flag: depends on unverified sale; alternative −4.42, still negative) | −59,388.22 OVER-UTILISED → LICENCE-LEVEL CONTROL | 17,064.530 unchanged |
| 5611004885 | OFF | −338,967.19 OVER-UTILISED | −338,967.19 REVIEW REQUIRED (alternative +17.59) | item SR 1 −169,492.39 → LICENCE-LEVEL CONTROL | unchanged |
| 2411004858 | ON | −126,916.21 OVER-UTILISED | unchanged | enforced | unchanged |
| 0811016174 | ON | 36,654.61 REVIEW REQUIRED | unchanged | enforced | unchanged |
| 0811016790 | ON | −451,031.88 OVER-UTILISED | unchanged | enforced | unchanged |

**Important: the two INTERNAL records for 5611004885 are not in the database.** Milestone 16 recorded trades 637 and 638 as INTERNAL, but `trade_tradeutilisationclassification` is empty. Its sequence has never advanced, and its insert counter is zero. Migration 0011 was applied at 07:14 UTC on 3 November 2026. Without those records, 637 and 638 are unverified, so 5611004885 shows REVIEW REQUIRED. With them, its base figure would be +17.59 and it would be RECONCILED. The records were not recreated here, because they carry the authoriser's name. The browser spec `internal-trades` shows the same cause: the "INTERNAL TRADE" label on GST/26-27/021 is absent.

**Tests.**
- Backend, new `test_licence_level_cif_control.py`: 11 tests. They cover OFF item attribution, OFF pooled status, quantity independence, verified negative pool, the unverified-sale scenario (REVIEW and OVER), attribution REVIEW, ON item enforcement with no netting, ON and OFF quantity parity, and the serialised contract.
- Backend, `test_licence_balance_report.py`: `test_negative_licence_balance_is_reported_not_floored` now records its sale as verified EXTERNAL. Its sale has no record, so under the new rule the negative balance is REVIEW REQUIRED. The test's intent is unchanged.
- Backend, `apps/license`, `apps/trade`, `apps/bill_of_entry`, `apps/reconciliation` (excluding the pre-existing `test_parse_pdf_hs_autocreate.py` collection error): 2,466 passed, 8 failed, 1 skipped, 2 xfailed. The 8 failures are the pre-existing set recorded in Milestone 16: Excel export ordering and HSN categories (`test_a3627_item_pivot_e2e`, `test_e132_display_sequence`, `test_e1_classification_sequence`), item pivot sources (`test_item_pivot_planned_import_item`), plan utilisation description (`test_plan_utilization`), and one query-count ceiling on the Overview summary (`test_license_overview_summary_view`, 49 queries against 47). None of their captured queries touch the balance engine. I did not re-run them on pre-change code, so this rests on the Milestone 16 record.
- Frontend, Vitest over `src/pages/licence-balances` and `src/pages/licenses/workspace` (12 files): 208 of 208 pass, including new `BalanceAmount.test.tsx` (4 tests and the label mapping). `tsc --noEmit` clean. ESLint clean on changed files.
- Browser, new `e2e/licence-cif-control.spec.ts`: 2 of 2 pass. 0311051322 (OFF) shows the label and no badge on SR 3. 2411004858 (ON) keeps the item-level badge and no label.
- Browser, existing `e2e/licence-balances.spec.ts`: 6 of 6 pass. `e2e/internal-trades.spec.ts`: 1 failed (the missing INTERNAL badge above, caused by the empty table), 3 did not run after it in that file.

**Not done in this milestone.**
1. **Overview licence control card.** Not built. The licence summary card states the control and shows the canonical figures. The card with gross purchases, gross sales, verified internal transfers and BOE utilisation needs the invoice-ledger figures placed alongside it, which is a separate change.
2. **PDF, Excel and the legacy list `get_balance_cif`.** Still use the legacy engine, as before. They are not aligned with the canonical licence-level figures. Changing them changes exported numbers, so it needs approval.
3. **Scenario rule.** The base-and-alternative rule above is my design. The user's full status table was not available to me in this session. Confirm it before relying on the REVIEW outcome.

**Open decisions.**
1. Re-apply the two INTERNAL records for 637 and 638 (5611004885), with the authoriser, if the earlier confirmation still stands.
2. Trade 633 (0311051322). Unclassified. Classifying it changes the figure but not the OVER-UTILISED result, which holds in both scenarios.
3. Confirm the base-and-alternative scenario rule and the REVIEW outcome for licences whose result depends on an unverified sale.

## 6. Unresolved issues and decisions

1. **Legacy engine versus canonical report.** For most licences with sales or purchases the two figures differ. Decision needed: which one the product shows for "balance", and whether the legacy engine's allotment and purchase rules are retired.
2. **Purchases (O-3).** The canonical report does not count purchase credit. Licence 2583 is over-utilised under the approved rule largely for this reason and because of the allotment overlap below.
3. **Allotment and sale overlap (O-4).** Customer 118 has allotments and sales on the same items of 2583, linked to the same BOE 27836. Whether they are the same entitlement is unknown.
4. **Cross-licence allotment.** Allotment 7208 (2583 SR 4) is fulfilled by BOE 27499 on licence 2584.
5. **Units (O-1).** `mts` on two items; BOE and allotment quantities have no unit field. Quantity totals are withheld for licences containing unverified units.
6. **Previous-owner BOEs (O-8).** Resolved in Milestone 10: deducted once, shown separately.
7. **Zero-original items (O-3).** 336 items have negative available CIF because sales or BOE debits sit on items with no authorised CIF.
8. **Cross-item links (O-2).** 81 items.
9. **Performance.** The legacy comparison runs the old engine once per licence; the query count grows with page size. The canonical part is fixed-cost per batch.
10. **UI polish.** Sorting, table export, the Actions column at narrow widths, the floating action bar covering rows, and repeated status labels.

## 7. Audit corrections made in this build

- Hidden BOEs: now excluded with the engine's audit-trail rule in the item audit. The raw `OTH` marker was not used.
- Over-linked excess: now counted as Debited in the item audit.
- Item audit figures regenerated: 902 reconciled, 229 review required, 165 over-utilised, 1,052 unmapped HS (of 2,348 items); CIF debited 23,210,485.42, down from 73,288,693.77 before the hidden-row fix.
- Item audit document updated to the corrected figures.
- Data-model statement about 2655 and 2656 corrected.
