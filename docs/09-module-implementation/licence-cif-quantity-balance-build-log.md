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

## Milestone 18 — Items & Balance: licence-level CIF on every row (Individual Item CIF OFF)

**Change.** The Items & Balance table now has the spec's 16 columns: SR, Item, HS Code, Unit, then Quantity before CIF for Original, Used through BOEs, Reserved for Customers, Invoiced and Available, then CIF Control and Status. The expand control moved into the SR cell, so it no longer takes a column.

- **OFF (`cif_control` LICENCE).** Every row's Available CIF is the licence's canonical available CIF, the same value on every row. The CIF Control column reads "Licence-level CIF control". Nothing is summed across rows.
- **ON (`cif_control` ITEM).** Each row shows its own available CIF, labelled "Individual item CIF".
- **Quantity** is unchanged: each row keeps its own available quantity.
- **Attribution** (Original, Used through BOEs, Reserved for Customers, Invoiced CIF) is unchanged and still shown per item.

**Where the value comes from.** The backend decides it. `serialise_licence_detail` adds `cif_control` and `available_cif_display` to each item row (`_with_cif_display` in `licence_balance_report.py`). The frontend passes the value through and does not choose a source. Existing keys are unchanged.

**Verification.**
- Backend, `test_licence_level_cif_control.py`: 12 of 12 pass. New: OFF rows show the same licence value; ON rows show their own; the display covers both modes.
- Frontend, Vitest over `src/pages/licence-balances` and `src/pages/licenses/workspace`: 216 of 216 pass, including new `ItemBalanceTable.test.tsx` (9 tests: the 16-column structure, the same licence value on every row without summing, the label on every row, quantity per item, ON behaviour, the expand control). `tsc` and ESLint are clean.
- Browser, `e2e/licence-cif-control.spec.ts`: 2 of 2 pass. 0311051362 (OFF): every row's Available CIF equals the licence value read from the page's own detail response, each row is labelled, each quantity matches its item, SR 3 is "Review required", and SR 12's invoiced CIF matches its payload. 2411004858 (ON) keeps the item-level badge.
- Browser, existing `licence-balances.spec.ts` and `licence-workspace.spec.ts`: 24 of 24 pass.

**Not done.**
1. **Reconciliation.** It still compares per-item attribution, not the licence balance.
2. **PDF and Excel exports.** They still use the legacy engine and do not follow the licence-level display.
3. **Individual item available CIF under OFF.** It is no longer shown in the row. It remains in the movement ledger and drill-downs.

## Milestone 19 — Allotment CIF difference ignored

**Rule.** The difference between an allotment's original CIF and its valid, current BOE-linked CIF on the same item is ignored in every financial calculation. Only the BOE-linked CIF counts, and it counts once: through the BOE debit if uncovered, or through the sale that covers it.

**Where it is implemented.** One helper, `allotment_link` (with `AllotmentLink`) in `licence_balance_report.py`. The engine (`_item_inputs`), the item drill-down (`_allotment_section`) and the workspace transactions (`build_licence_transactions`) all use it. The old `original − residue` subtraction no longer exists anywhere.

- **Linked on this item (matched CIF > 0).** Outstanding CIF is zero. BOE-linked CIF is the matched amount, capped at the original. Status is LINKED.
- **Unlinked.** Unchanged: the full allotment is reserved (D-1).
- **Linked only to a BOE on another item or licence.** Unchanged: full amount outstanding, REVIEW REQUIRED.
- **Quantity.** Unchanged. Outstanding quantity still follows the quantity rule.

**Overlap flag, per measure.** `ALLOT_AND_SALE_OVERLAP_UNVERIFIED` was raised by CIF or quantity residue and then applied to both measures. It now applies to each measure only from its own residue, so quantity status no longer depends on CIF.

**Reconciliation.** Same database, before and after. The before state is a counterfactual: the same engine with only the allotment rule reverted (throwaway script, nothing in the repository changed). The earlier snapshot could not be used, because the database had changed since it was taken. Results across 222 licences and 2,377 items:

- Every item's available CIF moved by exactly its old linked residue. Zero mismatches.
- Quantity amounts did not change anywhere.
- Quantity status changed for 26 items (REVIEW REQUIRED to RECONCILED), because the overlap flag came from CIF. See decision 2.
- ON licences: one licence (0811016174) and two items changed. The rule applies in ON mode too.

**Example, licence 0311051362, SR 3 (allotments ALLOT-7186 and ALLOT-7297).**

| | Before | After |
|---|---:|---:|
| Original allotment CIF | 14,900.36 | 14,900.36 (reference only) |
| BOE-linked CIF | 14,838.57 | 14,838.57 |
| Outstanding / reserved CIF | 61.79 | 0.00 |
| Item available CIF | −14,900.36 | −14,838.57 |
| Licence available CIF | 1,006.98 | 1,068.77 |
| Item status | REVIEW REQUIRED | RECONCILED |

The drawer's allotment rows are LINKED with no flags, and the reconciliation is RECONCILED.

**Tests.**
- New `test_allotment_cif_difference_ignored.py`: 12 of 12 pass. Covers the exact regression values, the drawer, no reservation or debit, licence available unchanged in both modes, no review, multiple allotments, single counting when the BOE is sold, superseded allocations, cancelled allotments, unlinked (unchanged), elsewhere-linked (unchanged), and agreement between balance, drawer and licence.
- Four existing tests asserted the difference (for example "outstanding 40.00"). They are updated to the new rule and renamed.
- Frontend: 216 of 216 Vitest tests pass in the licence-balance and workspace folders. No frontend source changed.
- Browser, live: 26 of 26 pass across `licence-cif-control`, `licence-balances` and `licence-workspace`. The example-licence spec now reads the reserved CIF and the status from the payload.
- Backend, `apps/license`, `apps/trade`, `apps/bill_of_entry`, `apps/reconciliation`, `apps/allotment`: 2,589 passed, 10 failed. Eight are the pre-existing set in Milestone 16. The other two are in `apps/allotment` (see below).

**The two `apps/allotment` failures.** Neither reaches the code changed here. The allotment app has no import path into the modified modules; I checked the transitive imports. Both are unrelated to the difference:
- `test_16_pair_mismatch_rejected` expects a mismatch at a 0.01 CIF difference. The pair check accepts differences up to and including 0.01, so this is a test and code disagreement that existed before this turn.
- `test_plan_candidate_query_count_is_constant_for_a_paginated_response` reports 17 queries against a ceiling of 16. I haven't traced this to a cause. It is not in a path I changed.

**Decisions to confirm.**
1. **Item 3's review status is gone.** The earlier spec said item 3 should keep its review. Its only trigger was the 61.79 difference, and this spec forbids a review from the difference. If you want it kept, a separate genuine reason must be defined.
2. **26 quantity statuses changed** (REVIEW REQUIRED to RECONCILED), for the reason above.
3. **Unlinked allotments keep the full reservation** under D-1. The spec's wording would drop them.
4. **Elsewhere-linked allotments** stay REVIEW REQUIRED.

**Not done in this milestone.**
- **Legacy stored figures and exports.** The stored `allotted_value`, the Overview summary, the dashboard KPI, the materialised views, and the PDF, Excel and CSV exports still use the legacy `LicenseBalanceCalculator`. That path already excludes BOE-linked allotments, and its per-item outstanding figure agrees with the new canonical figure for 2,365 of 2,377 items. The 12 that differ are the unlinked and elsewhere cases above. I did not change those paths or verify the exported files end to end.
- **Reconciliation** still reflects the canonical engine, so it now agrees with the new allotment figure.

## Milestone 20 — Single source of truth: attempt, revert and what remains

**Outcome: not completed. The single-source migration was attempted, broke 154 tests, and was reverted. The repository is back to the Milestone 19 state (10 pre-existing failures).**

**What was attempted.**
- The legacy `LicenseBalanceCalculator` licence and per-item balance entry points were made to delegate to the canonical engine.
- `update_balance_values` (the stored-field writer) read canonical figures.
- A refresh command wrote the canonical figures into the stored item fields and the licence balance cache.

**Why it was reverted.** Allocation and planning read the stored available CIF, and their test fixtures keep the authorised CIF on the licence balance or export items, not on the import item. The canonical engine reads import items, so those fixtures showed 0.00 available and refused every allocation: 154 failures. A live check found the same convention in only 6 of 222 licences, and none of those has a positive canonical figure, so production allocation is not affected by the data. The conflict is the fixture convention, and it needs a decision before the migration can continue. Changing allocation capacity to canonical is not a decision I should make alone.

**Database state (important).**
- The refresh wrote canonical values into the stored item fields and the licence caches of the dev database before the revert. The values those fields held before the refresh were not captured, so I could not restore them byte for byte.
- The stored fields and caches were then recomputed with the restored legacy writer (`update_balance_values` and `update_balance_cif`). They now hold legacy values computed from the current data, which may differ from what they held before this turn where the stored values were stale.
- No transaction, BOE, allotment or invoice was changed.

**Kept.**
- `NO_SION_ITEMS`: licence 0911012569 has no import items and no export items. Its canonical summary is now an explicit exception (0.00, REVIEW REQUIRED, flag `NO_SION_ITEMS`) instead of a missing value.

**Reverted.** `balance_calculator.py`, `calculate_balance.py`, the refresh command, the batched canonical helpers, and the React quantity change in `CustomsLedgerSection.tsx`. The React change displayed the stored quantity, which the legacy writer computes differently from the React formula it replaced, so it was not a verified equivalence. Patches are in `/tmp/migration_backup/`.

**Still legacy (not migrated).**
- Financial, customs and timeline ledgers behind the PDF and Excel exports (`LicenseBalanceLedgerBuilder`). The Excel balance lines show the canonical figure, but the ledger rows above them are legacy.
- Dashboard financial bridge (`dashboard_summary`), which sums legacy components.
- Overview snapshot licence CIF (`balance_snapshot`), which uses the customs formula.
- Reconciliation debit logic (`reconciliation/services/queries.py`, `boe_link_reconciler.py`, `allocation_service.py`).
- Allocation and planning caps (`allocation_service`, `validation_service`, `sion_planning_execution`).
- Restriction and condition pools. The canonical engine has no equivalent, and the stored `available_value` used to apply the pool rule.
- Frontend `CustomsLedgerSection` quantity arithmetic, and the sums in `AllotmentsTab` and `BoesTab`.

**Decision needed before continuing.** Confirm that the authorised CIF for allocation and planning is the import item's CIF (the canonical rule). If yes, the 154 fixtures are updated to match and the migration continues. If not, the canonical engine needs an authorised-CIF source that covers the export and balance records, and that is a rule change, not an implementation detail.

## Milestone 21 — GST/26-27/017: internal transfer pairs

**Root cause.** GST/26-27/017 is a transfer from VISION GURUKRUPA BUILDCON LLP to LABDHI GLOBAL LLP, recorded as a SALE (633) and a PURCHASE copy (634) joined by one persisted COPIED pair (`TradePairAudit` id 2, pair_uuid 8d8b5838-7619-4417-a050-5cb42164af47). Neither side had a classification record, so the SALE counted as external utilisation on four licences (806,565.19 CIF across SR 1 of 0311051322, 0311051531, 0311054696 and 3111005758). The purchase never counted: the canonical engine reads sales only.

**The 68,041.47 on SR 3 of 0311051531 is not this invoice.** It is sale 663 (LGL/2026-27/0092, LABDHI → GOLDEN AGRI), an external sale covered by BOE 28057, counted once. It involves no GST/26-27/017 line.

**Chain established from persisted records.**
- Authorisation: KHYATI GLOBAL VENTURES → VISION purchases of each SR 1 item's authorised CIF (for example 619, 620, 621).
- Internal transfer: VISION → LABDHI GLOBAL, sale 633 and copy 634.
- No external sale of these SR 1 items is recorded anywhere downstream.

**Internal pairs classified (both sides, explicit records, authoriser hardik, pair UUID as evidence).**

| Pair (TradePairAudit) | Sale | Purchase | Companies | Licences affected |
|---|---|---|---|---|
| 2 GST/26-27/017 | 633 | 634 | VISION → LABDHI GLOBAL | 0311051322, 0311051531, 0311054696, 3111005758 |
| 3 SC/2026-27/0001 | 637 | 636 | Sambhav → LABDHI GLOBAL | 5611004885 |
| 4 GST/26-27/021 | 638 | 635 | VISION → Sambhav | 5611004885 |
| 6 04/25-26 | 651 | 639 | NEELKANTH → LABDHI GLOBAL | 3111006003 |
| 8 LGL/2026-27/0101 | 683 | 684 | LABDHI GLOBAL → NEELKANTH | 10 licences (0311049075, 0311049077, 0311054431, 0311054432, 0311054433, 0311054442, 0311054443, 0311054446, 0311054451, 0311055304) |

**Recorded as REVIEW REQUIRED (no arithmetic change).**
- Pairs 1 (623/624) and 5 (644/645): LABDHI MERCANTILE LLP, whose group membership is not in the approved list.
- Pair 7 (661, LGL/2026-27/0091): external sale to APHRODITE FOODS LLP, with a copy whose counterpart was deleted (`UNPAIRED_DELETED`).

**Group membership is not persisted.** `CompanyModel` has no group field, so the internal test uses the companies named in the approved chain, plus the persisted COPIED pair. Company names and equal amounts alone were not used.

**Canonical effect (before and after, same database, all 222 licences).** Sixteen licences changed. No quantity or CIF changed on any other licence.

| Licence | Available CIF before | After | Status |
|---|---:|---:|---|
| 0311051531 | −225,979.73 | 12,765.98 | REVIEW → RECONCILED |
| 0311051322 | −335,999.92 | 190.35 | REVIEW (unchanged) |
| 0311054696 | −123,535.76 | 147.73 | REVIEW → RECONCILED |
| 3111005758 | −107,945.72 | 0.00 | REVIEW → RECONCILED |
| 3111006003 | −68,498.54 | 35,707.16 | REVIEW → RECONCILED |
| 5611004885 | −338,967.19 | 17.59 | REVIEW → RECONCILED |
| 0311054433 | −52,364.64 | 347,635.36 | REVIEW (unchanged) |
| 0311054442 | 179,216.69 | 719,216.69 | REVIEW (unchanged) |
| 0311055304 | 302,352.23 | 1,442,352.23 | RECONCILED (unchanged) |

Other changed licences: 0311049075, 0311049077, 0311054431, 0311054432, 0311054443, 0311054446, 0311054451.

Negative balances stay negative. 0311054432 remains at −41,437.04 after the change.

**Quantity effect.** Ten items changed quantity. Every change comes from trade 683 (LGL/2026-27/0101), whose lines are the only sales on those items. The internal rule excludes an internal sale from quantity as well as CIF.

**Consequence that needs your decision.** For 11 items, the only sale is internal, and no final external sale is recorded. Their entitlement now shows as available, which is up to 1,140,000 USD on 0311055304. That is right only if the goods are still held in the group. The canonical engine now flags these 11 items `INTERNAL_TRANSFER_NO_EXTERNAL_SALE` and shows REVIEW REQUIRED, so they are not reported as reconciled. Affected items (11): 0311051322 SR 1, 0311051531 SR 1, 0311054696 SR 1, 3111005758 SR 1, 5611004885 SR 1, 3111006003 SR 1, 0311054442 SR 3, 0311054443 SR 3, 0311054446 SR 3, 0311054451 SR 3, 0311055304 SR 3. Confirm each one's final external sale or accept the REVIEW state.

**Files changed.**
- `backend/apps/license/services/licence_balance_report.py`: flag `INTERNAL_TRANSFER_NO_EXTERNAL_SALE`.
- `frontend/src/pages/licence-balances/labels.ts`: label for the new flag.
- `backend/apps/license/tests/test_internal_transfer_pairs.py`: 9 new tests.
- `frontend/e2e/internal-transfer-gst017.spec.ts`: 2 new live browser checks.
- Trade classification records only (15 rows). No trade, line, BOE, allocation or invoice record was edited.

**Tests and checks.**
- Backend, new and related modules (`test_internal_transfer_pairs`, `test_internal_trade_exclusion`, `test_licence_balance_report`, `test_licence_level_cif_control`, `test_allotment_cif_difference_ignored`): 82 of 82 pass.
- Backend, full run (license, trade, bill_of_entry, reconciliation, allotment, core): 3,297 pass, 10 fail. The 10 are the same pre-existing failures as before, and none is new.
- Frontend, Vitest over licence-balances, licence workspace and license-overview: 222 of 222 pass. `tsc` and ESLint are clean.
- Browser, live (0311051531): the Items & Balance figures come from the canonical payload, and the INTERNAL flag appears (2 of 2 pass). Invoices & Sales shows INTERNAL TRADE on both sides of GST/26-27/017.

**Exports are still not canonical.** Across all 222 licences, the Excel "Current Available Balance" agrees with the canonical figure for 52 and differs for 170. Examples: 0311054432 shows +67,984.27 against a canonical −41,437.04, and 3111003827 shows −77,457.95 against 90.35. The export uses the legacy ledger, which is the open item from Milestone 20. I did not run the PDF or CSV checks.

**Not built.** The expandable relationship view and the full classification set (EXTERNAL SALE, EXTERNAL PURCHASE, LINKED/COVERED, CANCELLED/REVERSED) are not in the UI. The ledger still shows only the INTERNAL TRADE badge.

## Milestone 22 — Planning tab restored in the Licence Workspace

**Why it was missing.** The Planning tab belonged to the retired licence overview (`/licenses/:id/overview`, `LicenseOverviewPage`), which hosted the licence planning editor. Commit `34d7b967` replaced that page with the four-tab workspace and its `WORKSPACE_TABS` list, which had no Planning entry. The overview route now redirects to the list. Nothing was deleted: `PlanningEditor` and the planning API were kept.

**What was restored.**
- `workspaceTabs.ts`: `planning` sits directly after Overview, labelled "Planning".
- `LicencePlanningTab.tsx` (new): renders the existing `PlanningEditor` lazily, keyed by licence ID, with the workspace's `canWrite` and the licence number. The loading region is `PlanningTabLoading`.
- `LicenceWorkspace.tsx`: renders the tab after the workspace balance has loaded, so the editor never shows a stale balance.
- `PlanningEditor.tsx`: optional `canonicalBalanceCif` prop. When the parent passes it, the pool balance comes from the canonical engine rather than the stored cache. Other callers are unchanged.
- `OverviewTab.tsx`: Planning removed from the "Not yet available" list.
- Backend `views/license.py`, planning block of the licence detail: `planning_balance_cif.raw_balance_cif` and `operational_reconciliation.actual_balance_cif` are the canonical available CIF. `final_balance_cif` is the canonical balance less only the new planned CIF, so negatives are shown instead of floored, and BOE and allotment are not deducted twice. `cif_balance_basis` is now `CANONICAL_AVAILABLE`.
- Tooltip on "Actual Balance CIF" updated to the canonical definition.

**Reused, not duplicated.** `PlanningEditor`, `licenseApi` (`fetchLicense`, `fetchItemPlans`, `bulkUpsertItemPlans`, `deleteItemPlan`), `planningRuleApi.autoPlanLicense`, the `license-item-plans/` viewset (already filtered by licence and scoped to authorised licences), and the `licenses/<id>/auto-plan/` action. No planning model or endpoint was added.

**Not changed.** The planning engine's own caps (`sion_planning_execution`, `planning_usage_reconciliation`) still read their own figures. This is the same open allocation and planning decision from Milestone 20, not a display issue.

**Tests.**
- Frontend, `LicencePlanningTab.test.tsx` (new, 4 tests): loads the selected licence's records; switching licences shows only the new licence's records; read-only users get the permission message and no write action; the loading region has an accessible name.
- Frontend, updated for five tabs: the tab-order list, the arrow-key path (Overview → Planning → Items & Balance), and the pure tab list.
- Frontend, full Vitest suite: 980 of 980 pass across 112 files. `tsc` and ESLint clean.
- Backend, new `test_planning_balance_is_the_canonical_balance_less_only_new_planned_cif`: the planning balance is canonical, a deficit is shown, and only new plans are deducted. `test_license_detail_plan_utilization` now gives the licence its authorised CIF on the import item, the convention the canonical engine reads.
- Backend, full regression (isolated test database): 3,345 pass, 12 fail. Ten are the known pre-existing set. Two are planning-engine tests affected by concurrent uncommitted work (see below).
- Browser, live (isolated servers, read-only), 3 of 3 pass:
  - Tab order is Overview, Planning, Items & Balance, Invoices & Sales, Reconciliation.
  - Licence 0311054050 (3 plan lines, positive canonical balance): the editor shows each plan record the API returns, and its "Actual Balance CIF" equals the canonical available CIF.
  - Switching between Planning and Items & Balance keeps the same licence.
  - Licence 0311053224 (5 plan lines, negative canonical balance): the "Final Balance CIF" is negative as displayed, not floored.

**Decisions and conflicts.**
1. **Reload.** Your brief asks that a browser refresh keeps the selected licence and tab. Milestone 15 made a reload close the open licence, and the existing workspace spec asserts it. I kept the approved behaviour and did not change it. Changing it is a product decision.
2. **Concurrent planning-engine work.** `backend/apps/license/services/sion_planning_execution.py` has uncommitted changes that are not mine (an over-utilisation block and a raw-balance path). `test_planning_tolerances` and `test_seed_browser_2509` failed in the full run and pass when run on their own. They depend on that in-progress work and on test order.
3. **Plan data changed during this session.** Active plan lines went from 73 (44 licences) at the start of the milestone to 58 at the end, and licence 0311045177 went from 3 lines to none. I wrote no plan rows. A `pytest apps/core apps/accounts apps/license` process (PID 32799) was running against the same test database at the same time and collided with my first full run. I could not check which process removed the rows, and this needs your review.

## Milestone 23 — LML/2026-27/0023: group internal transfers, unmatched review, transaction classes

**The regression case.** Licence 0311049585, SR 1 (Polypropylene Granules, HS 39021000). Its invoiced figures were 269,702.32 CIF and 368,353.150 kg, and it was OVER-UTILISED at −47,342.32 CIF and −45,383.000 kg. The item's authorised CIF is 222,360.00 and its quantity is 322,970.150 kg.

**Transaction chain (all persisted).**
- **Authorisation:** purchase NI/2025-26/116, NAVKAR INDUSTRIES → LABDHI MERCANTILE LLP (259), CIF 222,360.00.
- **Sale 197** (LML/2025-26/0125), external, LABDHI MERCANTILE → MALAY EXPORTS: 174,240.00 CIF, 198,000 kg, covered by BOEs 7650222 and 7650224.
- **Sale 614** (LML/2026-27/0023), group → group, LABDHI MERCANTILE → LABDHI GLOBAL: 48,120.00 CIF, 124,970.150 kg, no BOE. Its quantity is exactly the remainder after sale 197 (322,970.150 − 198,000 = 124,970.150).
- **Purchase 615** (same invoice, same date, same parties, identical line): LABDHI GLOBAL's purchase record. It has no `COPIED` audit row, so the match is on persisted record content.
- **Sale 655** (LGL/2026-27/0086), external, LABDHI GLOBAL → MERUSHI: 46,574.32 CIF, 44,783 kg, covered by BOE 4054587.
- **Sale 672** (LGL/2026-27/0097), external, LABDHI GLOBAL → SIGMA: 768.00 CIF, 600 kg, covered by BOE 4457719.

**Classification applied.** Sale 614 and purchase 615 are INTERNAL. Sales 197, 655 and 672 are external, and their utilisation is counted once through their BOEs.

**Before and after (item 37689, licence 0311049585).**

| | Before | After |
|---|---:|---:|
| Invoiced CIF | 269,702.32 | 221,582.32 |
| Invoiced quantity | 368,353.150 kg | 243,383.000 kg |
| Available CIF | −47,342.32 (OVER-UTILISED) | 777.68 (RECONCILED) |
| Available quantity | −45,383.000 kg | 79,587.150 kg |

The 221,582.32 is 174,240.00 + 46,574.32 + 768.00. The 79,587.150 kg is the stock still held by the group, and it is correct only if the goods were not sold externally elsewhere.

**What the engine does now.**
- **Group membership** is by registered company ID (`apps/trade/services/internal_transfers.py`): 881 LABDHI GLOBAL, 766 LABDHI MERCANTILE, 866 NEELKANTH IMPEX, 1037 Sambhav Corporation, 885 VISION GURUKRUPA BUILDCON LLP. Similar names (SAMBHAV PAPERS, VISION VANIJYA, VISION) are excluded. Membership is not stored in the database.
- **Matching** is evidence only, and it uses persisted data: a `COPIED` pair, or the same invoice number, parties, date and identical lines. Equal amounts or names never match.
- **Transaction class** is derived in one function (`transaction_class`): INTERNAL_TRANSFER, INTERNAL_TRANSFER_PURCHASE, EXTERNAL_SALE, EXTERNAL_PURCHASE, UNMATCHED_INTERNAL_TRANSACTION, REVIEW_REQUIRED. The ledger row carries `transaction_class` and the `counterpart` (trade, invoice, seller, buyer, basis).
- **Unmatched rule.** A group-to-group sale with no matched purchase is flagged `UNMATCHED_INTERNAL_TRANSACTION` and stays counted until reviewed. It is not silently external and not discarded. Ten sales are flagged: 79, 84, 85, 157, 215, 373, 389, 534, 547, 569.

**Classification applied across the group.** I applied the same matching standard to every group-to-group pair that matches on persisted records. These are the pairs where the sale and its purchase share invoice number, parties, date and identical lines, plus the pairs that have a `COPIED` audit row:

- New INTERNAL: 614/615 (LML/2026-27/0023), 608/609 (LML/2026-27/0022), 350/390 (LGL/2026-27/0001), 365/366 (012/25-26), 367/211 (GST/25-26/005), 384/385 (LML/2026-27/0003).
- REVIEW → INTERNAL, after your confirmation that LABDHI MERCANTILE LLP is a group company: 623/624 (LML/2026-27/0024) and 644/645 (LML/2026-27/0026).
- Already INTERNAL from Milestone 21: 633/634, 635/638, 636/637, 639/651, 683/684.
- REVIEW unchanged: 661 (APHRODITE copy with a deleted counterpart).

**The classification table was empty again.** When I started this work, all 15 classification rows from Milestone 21 were gone. The table's sequence had never advanced. Migration `0011_trade_utilisation_classification` had been applied again at 15:14:49 UTC, which recreates the table. The database also holds a migration `0011_tradepairaudit_survive_trade_delete` that is not in this checkout, so another checkout is migrating the same database. I did not find which process did it. I re-recorded every decision from Milestones 21 and 23 with the same reasons and evidence, and I recorded the 614/615 pair as a new decision. The table now holds 27 rows. Until the database is isolated, these records can be lost again.

**Effect on licences (28 licences changed; none of them had their quantity or CIF changed by anything else).** Largest changes: 0311054442 +540,000, 0311055304 +1,140,000, 0311054433 +400,000, 0811016790 OVER-UTILISED → REVIEW REQUIRED (−451,031.88 → 362,968.11), 0811016774 −461,464.94 → 273,390.55. The rest are listed in `/tmp/lml0023_before.json` and `/tmp/lml0023_after.json`. These movements are the internal rule applied to each pair. Most of them leave the item in REVIEW REQUIRED, because the receiving company has no recorded external sale for those goods (`INTERNAL_TRANSFER_NO_EXTERNAL_SALE`).

**Accounting integrity.** The only database writes were 27 `TradeUtilisationClassification` rows. No trade, trade line, BOE, allocation, allotment or invoice was edited, and the historical values are unchanged. Internal rows stay in every company ledger with their amounts, and they are excluded from the external totals. The company external totals therefore change by the transferred amounts. I did not check the company-level summary numbers before and after, so that is a verification gap.

**Exports.** The Excel "Current Available Balance" for 0311049585 is 777.68, which matches the canonical figure. Across all 222 licences, Excel agrees with the canonical figure for 57 and differs for 165. The export still uses the legacy ledger, which is the open item from Milestone 20. I did not run the PDF or CSV checks.

**Tests and checks.**
- Backend: `test_group_internal_transfers.py` (17 tests) plus the internal-transfer, ledger and balance modules: 82 of 82 pass. The full backend run passes 3,412, with 10 failures in the known pre-existing set.
- Frontend: full Vitest run 980 of 980; TypeScript clean; ESLint clean on the changed files.
- Browser, live (0311049585): Items & Balance shows the canonical available CIF in the SR 1 row. Invoices & Sales labels both sides of LML/2026-27/0023 as INTERNAL TRADE, with the counterpart and trade IDs.

**Not built.** The full five-way transaction classification in the UI (EXTERNAL SALE, EXTERNAL PURCHASE, LINKED/COVERED, CANCELLED/REVERSED) and the expandable relationship view are not done. The drawer does not yet show the counterpart.

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
