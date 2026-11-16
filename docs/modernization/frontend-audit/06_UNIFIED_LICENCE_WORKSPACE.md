# 06 — Unified Licence Workspace (design note)

Status: DESIGN ONLY (no `frontend/` edits). Author role: react-architect. Date: 2026-11-16.
Branch snapshot: `feature/v5`, including the uncommitted `frontend/src/features/licenses/**` and the
uncommitted `LicensesTable.tsx` diff (+16/−100 vs HEAD).

> **STATUS UPDATE (2026-11-16, re-read of the working tree): sections 0–5 below are a historical snapshot.
> Their `LicensesTable.tsx` and `features/licenses/**` line references are STALE. Do not plan against them.**
>
> - **D2: DONE (uncommitted, implemented by another agent).**
>   - `pages/masters/tables/LicensesTable.tsx` is now a 98-line list. The card lives in
>     `features/licenses/LicenceCard.tsx` (226 LOC), with a single `ActionMenu` (`licenceActionItems.ts`).
>   - The workspace tabs (`features/licenses/LicenseRecordWorkspace.tsx:54-60`) are Overview (new
>     `tabs/OverviewTab.tsx`: financial summary + ledger), Import Items, BOE & Allotment, Invoices, Planning
>     (writer-only), Reconciliation (shown only with trading activity) and History.
>   - The Edit Options tab and the duplicate items-under-Overview are removed.
>   - Owner decisions applied: card CIF format `$` en-US, card status from `deriveStatus`.
> - **B3: DONE (uncommitted).**
>   - `/licenses/:id` redirects to `/overview` under the same `LICENSE_OVERVIEW_ROLES` guard
>     (`routes/AppRoutes.tsx:289-294`).
>   - `SionNormReport.tsx:154`, `MasterForm.tsx:1101` and `ReconciliationIssues.tsx:62` now link to
>     `/overview`.
>   - `/licenses/:id/balance` is kept (`AppRoutes.tsx:296`).
> - **D1: (a) APPROVED.** B7 is cancelled.
> - **Current ownership:** a debugging agent owns `pages/masters/MasterList.tsx` and
>   `features/licenses/LicenseRecordWorkspace.tsx`. No other edits are allowed there until it releases them.
> - **Still OPEN for the owner (checked against the current tree):**
>   - **D3:** `LicenseBalanceModal.tsx` (1062 LOC) is still wired at `MasterForm.tsx:12, 1129` and
>     `MasterList.tsx:13, 1451`.
>   - **D5:** `LicenseOverviewContent.tsx` still passes no `onSaved` to `PlanningEditor`.
>   - **D6:** `BalanceTab.tsx` and `LedgerTab.tsx` still exist. Re-audit the dead-code list against the new
>     card before deciding.
>   - **D7:** `CustomsLedgerSection.tsx:32` header colSpan.
>   - **D8:** formats on surfaces other than the card.
>   - **D9:** only if any label from the former Edit Options tab is still in question.
>   - **D4 quantity:** the client formula `CustomsLedgerSection.tsx:12, 26` is still present. It waits for the
>     Reconciliation Engineer.
> - **Remaining batches to re-plan from the current code:**
>   - B0 (characterisation tests)
>   - B1 / B1b (query-key unification; re-grep `licenseOverviewKeys` usage in the new `features/licenses/*`
>     hooks, for example `useLicenceLedger.ts`)
>   - B2 (shared actions; `useLicenceRowActions.ts` may already cover it)
>   - B5 / B6 (if D3 approves them)
>   - B8 (if D6 approves it)

All paths are relative to `frontend/src/` unless stated. Line numbers come from the working tree as read on
the date above.

Hard constraints from the owner (they apply to every batch):
- Existing data presentation stays the same: labels, values, number/date formatting, columns, order,
  defaults and permissions, per surface.
- No backend API is deleted or changed.
- The separate overview page is removed only after the unified workspace is verified and a
  backward-compatible redirect is in place.
- Frontend-side math is flagged here, not fixed. Any fix is a BUSINESS-RULE item for `cif-balance-auditor`
  and the human owner.

---

## 0. Surfaces in scope

| ID | Surface | Entry | Main files |
|----|---------|-------|------------|
| **P** | Full-page Licence Overview `/licenses/:id/overview` | `routes/AppRoutes.tsx:284-289` (`LICENSE_OVERVIEW_ROLES`) | `pages/license-overview/LicenseOverviewPage.tsx` (6 tabs, `:33-40`), `OverviewTab.tsx`, `LicenseDetailsHeader.tsx`, `LicenseMetricsGrid.tsx`, `StatCard.tsx`, `SionNormCard.tsx`, `CustomsLedgerTable.tsx`, `CustomsLedgerSection.tsx`, `FinancialLedgerTable.tsx`, `FinancialSummarySection.tsx`, `FinalReconciliationSection.tsx`, `BoesTab.tsx`, `AllotmentsTab.tsx`, `ItemsTab.tsx`, `InvoiceLedgerTab.tsx`, `ReplanStatus.tsx`, `components/planning/PlanningEditor.tsx` |
| **C** | Expanded licence card in the register `/licenses` | `routes/AppRoutes.tsx:123-127` (`LICENSE_ROLES` only) → `pages/masters/MasterList.tsx:998-1012` → `pages/masters/tables/LicensesTable.tsx` `LicenseRow` (`:932-1240`) | `features/licenses/LicenseRecordWorkspace.tsx` (8 tabs, `:59-82`), `features/licenses/tabs/*`, `LicenseOverviewContent.tsx` |
| **E** | Licence edit `/licenses/:id/edit` | `AppRoutes.tsx:133-137` | `pages/masters/MasterForm.tsx:1083-1107` ("View Balance" opens the modal; "Balance Workspace" goes to `/licenses/:id/balance`, which redirects to P (`AppRoutes.tsx:69-74, 290`)) |
| **M** | `components/LicenseBalanceModal.tsx` (1059 LOC) | Reachable: `MasterForm.tsx:1088` → `:1129-1133`. **Unreachable**: `MasterList.tsx:1231-1240` (licence `customActions` are passed only to the generic table branch, which excludes `licenses` at `MasterList.tsx:1055`) | — |

Orphans and dead code found during the analysis. None of it is reachable. Removal is decision **D6**.
- `pages/masters/tables/BalanceTab.tsx` (530 LOC) and `LedgerTab.tsx` (1162 LOC): nothing imports them
  any more. `grep -rn "import.*\(LedgerTab\|BalanceTab\)" src` returns nothing. `.claude/index/dependents.tsv`
  still lists `LedgerTab ← LicensesTable`, so that index entry is stale against the uncommitted diff.
- `LicensesTable.tsx:397-666`: the in-file `OverviewTab`, `AllocationTab` and `TransactionsTab` are defined
  but never rendered.
- `LicensesTable.tsx:950-951`: `const [detail] = useState(null)` has no setter. The card's Documents tab is
  therefore never visible (`:1215` `showDocuments={!!detail?.license_documents…}`).
- `licenseOverviewKeys.planning(id)` (`useLicenseOverviewSummary.ts:17`) is never used as a `queryKey`.
  The five places that invalidate it do nothing: `LicenseOverviewPage.tsx:104`, `SionNormCard.tsx:70`,
  `LicensesTable.tsx:1031`, `IndividualItemCifSwitch.tsx:32`, plus `MasterForm` indirectly.

---

## 1. Duplication matrix

Legend: **=** identical (same component, same endpoint, same query key) · **≈** same endpoint, different
component or format · **≠** different source or calculation · **—** absent.
**FE-MATH** marks arithmetic or derivation done in the browser.

### 1.1 Header / identity

| Element | P (overview page) | C (register card) | M (modal) | Verdict |
|---|---|---|---|---|
| Title | `PageHeader` "License Overview — {license_number}", description = `importer` (`LicenseOverviewPage.tsx:167-171`) | Mono licence number, rendered as a button that opens `merged-documents/` PDF (`LicensesTable.tsx:1106-1121`) | "License Balance Report — {license_number}" (`LicenseBalanceModal.tsx:380-383`) | ≠ three renderings |
| Identity fields | `LicenseDetailsHeader.tsx:52-62`: License Number, File Number, Port Code, License Date (`fmtDate`), Expiry Date (`fmtDate`), **Importer** (`overview-summary/`) | Header `:1124-1149`: license_date / expiry / ledger_date / port_name, all as **raw strings**. Strip `:1180-1183`: Norm Class (`get_norm_class`), **Exporter** (`exporter_name`), IEC, Transfer Status (`latest_transfer`). Source: list endpoint `licenses/` | `:431` License Number, License Date, License Expiry Date, **Exporter Name**, Port Name. `:498` Purchase Status, Balance CIF, Get Norm Class, Latest Transfer. Source: `licenses/:id/` | ≠ different field sets, labels (Importer vs Exporter), date formats and endpoints |
| Status badge | Server `summary.status` + `licenseOverviewStatusVariant` (`LicenseDetailsHeader.tsx:112`) | **FE-MATH** `deriveStatus()` (`LicensesTable.tsx:221-258`): Expired if expiry < client clock, else Exhausted if `Number(get_balance_cif) <= 0`, else Planned if `is_manually_planned`, else Active | — | ≠ client derivation vs server status. These can disagree, for example across timezones or when the balance is `0 < x < 0.005` |
| Purchase status | Editable select, PATCH `licenses/:id/` (`OverviewTab.tsx:59-72`) | Read-only `purchase_status_label` (`:1152-1154`) | Read-only (`:498`) | ≈ |
| SION norm | `SionNormCard` (editable, `licenses/:id/` under key `license-sion-norm`) | Norm Class text (`get_norm_class`) | "Get Norm Class" text | ≈ |

### 1.2 Balance / CIF summaries

| Element | P | C | M | Verdict |
|---|---|---|---|---|
| **Balance CIF value** | `StatCard` "Balance CIF" = `fmtNum(summary.summary.total_balance_cif)`, which uses `formatIndianNumber`, 2 dp, no `$`, and shows "—" for null (`LicenseMetricsGrid.tsx:72-79`) | `$` + `Number(get_balance_cif \|\| 0).toLocaleString("en-US", 2dp)`, red when < 0, null shows `$0.00`. Rendered twice: collapsed (`:1160-1163`) and strip (`:1189-1192`) | `formatFiniteDecimal(balance_cif)`, which is `toFixed(2)` with no grouping and shows `0.00` for null (`:512, :621`; helper `components/licenseBalanceHelpers.ts:13`) | ≠ **three sources** (`overview-summary.summary.total_balance_cif`, list `get_balance_cif`, detail `balance_cif`) and **three formats** (Indian grouping / en-US with `$` / ungrouped) |
| Second balance field on P | `PlanningEditor balanceCif` = `parseFloat(summary.balance_cif)` (`LicenseOverviewPage.tsx:230`), the top-level field, not `summary.summary.total_balance_cif` | Embedded Planning uses `Number(summary.balance_cif)` (`LicenseOverviewContent.tsx:19`) | — | ≈ same field but parsed differently: `""` gives NaN with `parseFloat` and 0 with `Number`, and `"1,234"` gives 1 vs NaN. Low risk, but the two are not identical |
| Ledger balances | `CustomsLedgerTable` `SummaryCard` "Available Balance" (`computed_balance`) and "Balance Engine" (`engine_balance`) from `balance-ledger/` (`CustomsLedgerTable.tsx:328-330`) | — | — | unique to P |
| Over-utilised badge | **absent** in P's metrics | `OverUtilisedBadge balance=get_balance_cif isOverUtilised=is_over_utilised`, twice | `OverUtilisedBadge balance_cif`, twice | ≈ (C/M only) |
| Metric grid (BOEs, Allotments, Planned/Total/Debited/Allotted CIF) | `LicenseMetricsGrid` with 7 `StatCard`s (`pages/license-overview/StatCard.tsx`) | — | Export-item Total/Balance CIF (`:585`) | unique to P |
| `IndividualItemCifSwitch` | Footer of the Balance CIF card (`LicenseMetricsGrid.tsx:79`) | **Twice in the same card**: info strip (`LicensesTable.tsx:1193-1198`) and Edit Options tab (`EditOptionsTab.tsx:37`) | — | = same component. Rendering it twice in C is a duplicate |
| Two `StatCard`s | `pages/license-overview/StatCard.tsx:90` | — | — | Separate from `components/StatCard.tsx:84` (Dashboard, LedgerDetail, Reconciliation, reports). Not a licence-workspace duplicate; out of scope (see 05 spec) |

### 1.3 Item-level tables

| Element | P | C | M | Verdict |
|---|---|---|---|---|
| Items balance table | `ItemsTab` (`overview-items/?include_canonical=1`, key `license-overview-items`), server `balance_qty` / `balance_cif` | Tab "Overview" **and** tab "Import Item" both render `ItemsTab` (`LicenseRecordWorkspace.tsx:61-62`, `ImportItemTab.tsx:5`) | Import Items table (`:716`): Sr No, HS Code, Description, Item, Total Quantity, Allotted Qty, Debited Qty, Available Qty, License Marking, CIF FC, Balance CIF FC | P=C (=, shared key). **C shows the same body under two tabs.** M ≠ |
| Import items utilisation matrix | `CustomsLedgerSection` (`licenses/:id/`, key `license-balance-customs-ledger`). **FE-MATH** `actualAvailableQuantity = quantity − boe_debited_quantity − allotted_quantity − billed_no_boe_qty` overwrites the server's `actual_available_quantity` (`CustomsLedgerSection.tsx:12, 24-27`). **FE-MATH** `status()` (`:13`). This contradicts the component's own docstring "never … recalculates" (`:20`). Header `colSpan={6}` covers 7 quantity and 7 CIF fields (`:32`), so the column groups are misaligned | — | **FE-MATH** usage drill "Balance = quantity − debited_quantity − allotted_quantity" (`:1025-1033`). It uses `debited_quantity`, not `boe_debited_quantity`, and leaves out `billed_no_boe_qty` | ≠ **two different client formulas for "available/balance qty"**, plus the server's `ItemsTab.balance_qty` (a third definition, `ItemsTab.tsx:18-21`). Escalate as a business rule (D4) |
| Per-item usage drill-down | — | — | `item-usage/?item_id&type` (`:163`), with BOE and Allotment usage tables (`:636, :671`) | unique to M |
| Item tags / licence marking / export items | — | — | PATCH `license-items/:id/` `items` (`:232, :276`) and `condition_type` (`:310`); Export Items table (`:578-585`) | unique to M |
| Condition sheet / Notes | — | (dead `LicensesTable.tsx:399`) | Inline edit, PATCH `licenses/:id/` `condition_sheet` / `balance_report_notes` (`:541-565`) | unique to M |

### 1.4 Ledgers, BOEs, allotments, invoices, planning

| Element | P | C | Verdict |
|---|---|---|---|
| Financial ledger, summary, final reconciliation, missing-purchase warning, no-trade banner | `OverviewTab.tsx:174-240` (`balance-ledger/`) | — | unique to P |
| Customs running-balance ledger + hide/restore BOE (`hide-boe[-bulk]/`, `restore-boe[-bulk]/`) + show-hidden toggle | `CustomsLedgerTable.tsx:194-248` | Reached only through the link "Recalculate / hide-restore BOE (License Overview)" (`EditOptionsTab.tsx:32-35`) | unique to P |
| BOEs | `BoesTab` (`overview-boes/`) | `BoeAllotmentTab` accordion → the same `BoesTab` (`BoeAllotmentTab.tsx:15`) | = |
| Allotments | `AllotmentsTab` (`overview-allotments/`) | same component (`BoeAllotmentTab.tsx:16`) | = |
| Invoice ledger | `InvoiceLedgerTab` (`overview-invoice-ledger/`) | same component (`InvoicesTab.tsx:5`) | = |
| Planning editor | `PlanningEditor … onSaved={refreshPlanningDependents}` (`LicenseOverviewPage.tsx:227-233`) | `PlanningEditor` with **no `onSaved`** (`LicenseOverviewContent.tsx:19`) | ≈ same body. After a save, C does not invalidate summary, items or ledger. This is a behaviour divergence (D5) |
| Replan status banner | `ReplanStatus` (`replan-status/`) | — | unique to P |
| History (ownership) | — | `HistoryTab` (`license-actions/:id/ownership-data/`, `LicensesTable.tsx:974`) | unique to C |

### 1.5 Actions

| Action | P | C | M | Differences |
|---|---|---|---|---|
| Auto Plan | `PermissionGate role=LICENSE_MANAGER` (`:174-179`). Invalidates summary, items, planning (no-op), ledger. On error shows `extractApiError(...)` | `canWrite` ActionRow (`:308`). Invalidates the same keys **plus `["entity-list","licenses"]`** (`:1024-1039`). On error always shows the generic "Failed to auto-plan licence." | — | ≈ different invalidation sets and error text |
| Balance PDF | `balance-pdf/` + `show_hidden` when the toggle is on. Error text "Failed to generate PDF file" (`:132-146`) | `balance-pdf/`, never `show_hidden`. Error text "Failed to generate PDF" (`:1048-1055`) | `balance-pdf/` (`:337`) | ≈ |
| Balance Excel | `openAuthedFile` + `show_hidden` (`:148-163`) | `openAuthedFile`, info toast "Generating Excel file..." first, different error extraction (`:1057-1077`) | `openAuthedFile` (`:355`) | ≈ |
| Licence copy / TL | One button per document via `openDocument`, from `licenses/:id/` `license_documents` (`:180-189`) | Licence-number button → `merged-documents/` (`:992-1012`) | `merged-documents/` (`:455`) | ≠ |
| Recalculate | `recalculate/` (`OverviewTab.tsx:74-87`) | link to P | — | unique to P |
| Edit | — | `navigateToEdit` saves filter state, then `/licenses/:id/edit` (`:1009-1016`) | — | unique to C |
| Fetch from DGFT, Delete | — | ActionPanel (`:310-334`) | — | unique to C |

---

## 2. Inbound links

| Target | Source (file:line) | Notes |
|---|---|---|
| `/licenses/:id/overview` | `pages/masters/tables/LicensesTable.tsx:1019` (ActionPanel "License Overview", Edit Options link) | |
| | `pages/reports/ItemPivotReport.tsx:321` (licence-number `Link`), `:1809` ("Open Licence") | |
| | `pages/LicenseDownloadRequestDetail.tsx:7` (`Link` per item) | |
| | `pages/planning/LicensePlanningWorkspace.tsx:376` → `/overview?tab=planning` | deep link with `?tab=` |
| `/licenses/:id/balance` (legacy, redirects to P while preserving `location.search`) | `pages/masters/MasterForm.tsx:1101` ("Balance Workspace") | extra redirect hop |
| | `pages/ReconciliationIssues.tsx:62` | |
| | (legacy alias `?tab=plan` is normalised to `planning` at `LicenseOverviewPage.tsx:71`) | |
| `/licenses/:id` (**no route, falls through to `NotFound`** at `AppRoutes.tsx:351`) | `pages/reports/SionNormReport.tsx:154` (`<a target=_blank>`) | **existing broken link** |
| `/licenses/:id/edit` | `pages/Dashboard.tsx:558`, `utils/navigationUtils.js:66`, `MasterForm.tsx:417`, `LicensesTable.tsx:1015` | edit stays a separate route (form, not workspace) |
| `/licenses?search=…` / filters | `Dashboard.tsx:267, 412, 466, 478, 641`, `ReconciliationIssues.tsx:62` (fallback) | register, unaffected |
| CommandPalette | `components/CommandPalette.tsx:35, 42`: only `/licenses` and `/licenses/create` | no per-licence entry |
| E2E | `frontend/e2e/license-overview.accessibility.spec.ts` | must keep passing |

### Redirect strategy (additive and reversible)

1. Keep `/licenses/:id/overview` as the **canonical workspace URL** (recommended, D1 default). It already
   carries `?tab=` state and is referenced from 6 places.
2. Keep `/licenses/:id/balance` → `/licenses/:id/overview${search}` unchanged (`AppRoutes.tsx:69-74`).
3. **Add** `/licenses/:id` → `/licenses/:id/overview${search}` with the same `RedirectToLicenseOverview`
   component. This fixes `SionNormReport.tsx:154`. Static `/licenses/create` keeps precedence through
   react-router v7 route ranking. Add a test for it.
4. Point `MasterForm.tsx:1101` and `ReconciliationIssues.tsx:62` directly at `/overview`. The destination is
   the same and one hop is saved. The `/balance` route stays for bookmarks.
5. Register deep link into a tab: `navigate(\`/licenses/${id}/overview?tab=${tab}\`)` with existing tab ids
   `boes | allotments | planning | items | invoice-ledger`.
6. If the owner picks D1 option (b), the canonical `/licenses/:id`: move P's element to `/licenses/:id`,
   and turn `/overview` and `/balance` into redirects that preserve `search`. The redirects must keep the
   **`ProtectedRoute requiredAnyRole={LICENSE_OVERVIEW_ROLES}`** gate on the destination. The redirect
   itself is unguarded, as it is today.

Do not redirect `/licenses/:id/overview` to the register. The register is gated by `LICENSE_ROLES`
(`authorizationRoles.ts:36`: LICENSE_MANAGER and LICENSE_VIEWER only). The overview is gated by
`LICENSE_OVERVIEW_ROLES` (`:50-52`), which adds BOE_MANAGER/VIEWER and TRADE_MANAGER/VIEWER. Such a redirect
would lock those roles out, which is a permission change and needs escalation.

---

## 3. Recommended target

**THE workspace = the full page P (`LicenseOverviewPage`, canonical `/licenses/:id/overview`).**
**The register card C becomes a lightweight preview that deep-links into it.**
**The modal M stays until its unique features are ported (D3).**

### Why this direction (least change, keeps every feature)

1. **Feature superset.** P already owns everything balance-critical that C and E lack: recalculate,
   hide/restore BOE and show-hidden, financial and customs ledgers, final reconciliation, purchase status
   and SION norm editing, replan status, show-hidden-aware exports, per-document copy/TL buttons. C reaches
   these only by linking to P (`EditOptionsTab.tsx:32-35`).
2. **The tab bodies are already shared.** C's BOE, Allotment, Invoices, Items and Planning bodies *are* P's
   components (`features/licenses/tabs/*`). Making P the workspace removes nothing from P. The reverse
   direction would mean embedding `OverviewTab` (`balance-ledger/` + two `licenses/:id/` fetches + large
   tables) inside a paginated list, once per expanded row.
3. **Permissions.** P is reachable by 6 roles and C by 2. Making C the workspace would need a route-role
   change, which counts as escalation under CLAUDE.md §2.
4. **URL state.** P is deep-linkable (`?tab=`), and 6 inbound links plus the planning deep link already
   target it. C's state lives in component state on a list page; a licence on page 7 cannot be deep-linked.
5. **Least code moved.** Most of the work is subtraction (C's duplicate tabs, dead code) plus additive
   redirects and query-key unification.

### What is kept vs removed

| Item | Decision |
|---|---|
| P, all 6 tabs, header, actions | **Kept unchanged** (presentation frozen by B0 tests) |
| `/licenses/:id/overview`, `/licenses/:id/balance` | **Kept**. `/licenses/:id` **added** as a redirect |
| C collapsed header and info strip (list-row data, no extra requests; `$`/en-US Balance CIF; `deriveStatus` badge; OverUtilisedBadge; merged-PDF licence-number button) | **Kept unchanged**. This is the preview. Its formats are different from P's but are already shipped, so they are not unified (presentation must not change) |
| C ActionPanel (Overview link, Auto Plan, Balance PDF/Excel, DGFT fetch, Delete, Edit) | **Kept**. DGFT, Delete and Edit are unique to C. PDF/Excel/AutoPlan move onto a shared hook (B2) and keep C's exact toast texts |
| C History tab (`ownership-data/`) | **Kept** (unique to C) |
| C "Overview" tab (= `ItemsTab`, shipped at HEAD) and "Planning" tab (shipped at HEAD) | **Kept** by default, since they are shipped presentation. Bodies share cache with P after B1 |
| C "Import Item" tab (a second `ItemsTab`, uncommitted) | **Remove** (exact duplicate of C's "Overview" tab). Needs owner confirmation (D2) |
| C "BOE & Allotment", "Invoices" tabs (uncommitted) | **D2**: (a) keep embedded (no duplicate code, cache shared after B1), or (b) replace each with an "Open in workspace" link to `?tab=boes` / `allotments` / `invoice-ledger`. Recommended: **(a) during migration, then (b)** once P is accepted as the workspace |
| C "Edit Options" tab (uncommitted) | **D2**: remove its second `IndividualItemCifSwitch`, since the strip already has one. Its two buttons duplicate ActionPanel Edit and Overview |
| C "Documents" tab | Dead (D6). P's header buttons are the workspace equivalent |
| `LicenseOverviewContent` | Kept as the shared body adapter. Add an optional `onSaved` pass-through (D5) |
| M | **Kept** until D3. Its reachable entry point is `MasterForm.tsx:1088`. The unreachable `MasterList.tsx:13, 139, 1231-1240, 1411-1415` is removed under D6 |
| `BalanceTab.tsx`, `LedgerTab.tsx`, `LicensesTable.tsx:397-666` | Dead. Remove under D6 |
| Backend endpoints | **All kept** |

---

## 4. API request de-duplication

### 4.1 Requests today (default tab, one licence)

| Open | Requests (query key) |
|---|---|
| P, Overview tab | `overview-summary/` (`license-overview-summary`; page and tab share it) · `licenses/:id/` (**`license-balance-customs-ledger`**; page documents and `CustomsLedgerSection` share it) · `licenses/:id/` **again** (**`license-sion-norm`**, `useLicenseSionNorm.ts:42`) · `balance-ledger/` (`license-balance-ledger`) · `replan-status/` |
| P, Planning tab | + `licenses/:id/` **a third time, uncached** (`PlanningEditor` `useEffect` → `fetchLicense`, `PlanningEditor.tsx:562-569`) · `license-item-plans/?license=` (uncached) |
| C expanded, default tab | list row only + `overview-items/` (`license-overview-items`) |
| C BOE & Allotment | `overview-boes/` + `overview-allotments/` (both sections `defaultOpen`) |
| C Planning | `overview-summary/` + `licenses/:id/` (uncached) + `license-item-plans/` |
| C History | `ownership-data/` (component state, refetched for every card instance) |
| M | `licenses/:id/` (uncached `useEffect`, `:142`) + `item-usage/` on each row click |

The same licence open in P, C and M in one session can issue **up to 5 GETs of `licenses/:id/`** under
three cache keys plus two uncached paths. The `overview-*` endpoints are already shared between P and C
because they use the same hooks and keys. With `staleTime: 30_000` (`api/queryClient.ts:6`), C → P
navigation within 30 s reuses them.

### 4.2 Shared query-key plan (`qk.licenses.*`, `lib/queryKeys.ts:20-24`)

All keys live under the prefix `["licenses","detail", String(id)]`, so one prefix invalidation refreshes the
whole workspace. Always pass `String(id)`: today `qk.licenses.detail(id)` keeps the raw type, and `1` and
`"1"` would be different keys.

| Data | Endpoint | New key | Replaces |
|---|---|---|---|
| Licence detail (single fetch; consumers use `select`) | `licenses/:id/` | `qk.licenses.detail(id)` | `["license-balance-customs-ledger",id]`, `licenseSionNormKeys.detail`, `PlanningEditor` `fetchLicense`, M's fetch (later) |
| Summary | `overview-summary/` | `qk.licenses.overview(id,"summary")` | `licenseOverviewKeys.summary` |
| BOEs / Allotments / Items / Invoice ledger | `overview-*` | `qk.licenses.overview(id,"boes" \| "allotments" \| "items" \| "invoice-ledger")` | the corresponding `licenseOverviewKeys.*` |
| Balance ledger | `balance-ledger/` | `qk.licenses.sub(id,"overview","balance-ledger")`, plus `"show-hidden"` as an extra element only when true | `licenseBalanceKeys.ledger`. Prefix matching still invalidates both variants, keeping the guarantee documented at `useLicenseBalanceLedger.ts:13-17` |
| Replan status | `replan-status/` | `qk.licenses.overview(id,"replan-status")` | `["license-replan-status",id]` |
| Item plans | `license-item-plans/` | `qk.licenses.sub(id,"item-plans")` | `PlanningEditor` local fetch |
| Ownership | `ownership-data/` | `qk.licenses.sub(id,"ownership")` | `LicenseRow` local state |
| `planning` | — | **drop** (never a real query). Callers invalidate `item-plans` instead | `licenseOverviewKeys.planning` |

Mechanics:
- **Compatibility shim first.** Keep the exported names `licenseOverviewKeys`, `licenseBalanceKeys` and
  `licenseSionNormKeys`, and re-point their bodies at `qk`. All 20+ call sites (listed by `grep -rn
  licenseOverviewKeys src`) then move in one diff without touching their files.
- **Shared detail hook** `useLicenseDetail(id, { enabled, select })` in `src/hooks/` (or
  `features/licenses/`). `select` slices are `d => d.license_documents`, `d => d.import_license`,
  `d => d.export_license`. One network request for the three P consumers.
- **Single invalidation helper** `invalidateLicenseWorkspace(qc, id)` invalidates
  `["licenses","detail",String(id)]` and `["entity-list","licenses"]`. Recalculate, hide/restore,
  auto-plan, SION and purchase-status writes, the CIF switch and plan saves all use it. Surface-specific
  narrower invalidations can stay where they exist today; the helper is a superset, so nothing is
  refreshed *less*.
- **Risk to note.** `IndividualItemCifSwitch.tsx:35` invalidates `["licenses"]`. After the move this also
  matches every cached licence workspace (all ids). That is correct but broader. It is acceptable, or the
  call can be narrowed to `qk.licenses.lists()` plus the helper.
- `PlanningEditor` → `useQuery` is a separate batch (B1b), because its `load()` also drives local edit
  state. Seed local state from the query data only on `dataUpdatedAt` change.

Expected result: P Overview tab `licenses/:id/` 2 → 1; P Planning tab 3 → 1; C→P within `staleTime` reuses
summary, items, boes, allotments, invoice-ledger and detail.

---

## 5. Incremental plan (small, verifiable batches)

Owner of all `frontend/` files: `frontend-engineer`, one batch per commit on a feature branch. Reviewers:
`code-reviewer` every batch, `a11y-architect` for B4 and B5, `cif-balance-auditor` for D4 (and as a check
that B1 leaves values unchanged). Each batch passes `scripts/dev/quality-gate.sh frontend` (lint, tsc,
vitest, build). Rollback for every batch is `git revert <batch commit>`. Redirects and keys are additive, so
no data or schema is involved.

| Batch | Scope (files) | Equivalence / acceptance tests (vitest + RTL, skill `react-testing`) | Rollback note |
|---|---|---|---|
| **B0. Characterisation (tests only)** | new `pages/license-overview/LicenseOverviewPage.presentation.test.tsx`, `components/LicenseBalanceModal.presentation.test.tsx`, `routes/licenceRedirects.test.tsx`. Extend `features/licenses/LicensesTable.presentation.test.tsx` | Fixture-driven **text snapshots** (not class snapshots) of: P title and description, header fields and order, 7 metric titles and values (including negative, null → "—", Indian grouping), tab labels and order, action buttons per role (LICENSE_MANAGER vs LICENSE_VIEWER vs BOE_VIEWER). C collapsed and strip Balance CIF (`$`, en-US, red when < 0, null → `$0.00`), status label for each `deriveStatus` branch, tab list per `canWrite`. M header tables and Balance CIF `toFixed`. **Request-count spies** per surface/tab (§4.1 numbers as the baseline). Routes: `/licenses/7/balance?tab=boes` → `/licenses/7/overview?tab=boes`, `?tab=plan` renders Planning | n/a (tests only) |
| **B1. Query-key unification** | `lib/queryKeys.ts` (if a helper is needed), `useLicenseOverviewSummary.ts`, `useLicenseBalanceLedger.ts`, `useLicenseSionNorm.ts`, `CustomsLedgerSection.tsx`, `LicenseOverviewPage.tsx` (documents query), `ReplanStatus.tsx`, new `useLicenseDetail` and `invalidateLicenseWorkspace` | B0 snapshots unchanged. Request spy: P Overview `licenses/:id/` == 1. Invalidation tests: recalculate and hide-BOE refetch summary and both ledger variants. CIF switch still refetches items and ledger. C→P within `staleTime` makes 0 new `overview-items/` requests | revert. The shim means call sites are untouched |
| **B1b. PlanningEditor on query cache** | `components/planning/PlanningEditor.tsx`, `api/licenseApi.ts` (no endpoint change) | `PlanningEditor.reconciliation.test.tsx` still green. P Planning `licenses/:id/` == 1 when the Overview tab was visited first. Unsaved edits survive a background refetch | revert |
| **B2. Shared licence actions hook** | new `features/licenses/useLicenceExportActions.ts` (PDF, Excel, auto-plan) used by `LicenseOverviewPage.tsx` and `LicensesTable.tsx` | Per-surface **toast texts unchanged** (P "Failed to generate PDF file" vs C "Failed to generate PDF"; C info toast; P `extractApiError` vs C generic auto-plan message) via an options object. `show_hidden` param sent only from P when toggled. Filenames unchanged | revert |
| **B3. Routes and links** | `routes/AppRoutes.tsx` (add `/licenses/:id` redirect), `MasterForm.tsx:1101`, `ReconciliationIssues.tsx:62` → `/overview` | Redirect test: `/licenses/7` → `/licenses/7/overview`, `search` preserved. `/licenses/create` still renders MasterForm. Destination role gate: BOE_VIEWER allowed, a role outside `LICENSE_OVERVIEW_ROLES` gets the existing denial. Link targets asserted. e2e `license-overview.accessibility.spec.ts` green | revert. Old routes never removed |
| **B4. Card → preview (D2)** | `features/licenses/LicenseRecordWorkspace.tsx`, `features/licenses/tabs/*`, `LicensesTable.tsx` | Remove the duplicate "Import Item" tab and the duplicate CIF switch in Edit Options. If D2(b): BOE & Allotment and Invoices become links to `?tab=…` (assert href). HEAD-shipped tabs (Overview = items, Planning, History) keep their labels and order. Keyboard tab navigation test (existing `LicenseRecordWorkspace.test.tsx:113`). **D5**: pass `onSaved` → `invalidateLicenseWorkspace` (test that a save refetches summary) | revert. Tab ids are unchanged, so persisted state is safe |
| **B5. Modal parity (D3)** | either a new P section ("Item tags & marking", "Condition sheet & notes", "Item usage") reusing M's handlers and endpoints (`license-items/:id/` PATCH, `licenses/:id/` PATCH, `item-usage/`), or no change | Parity tests: each M edit sends the same PATCH payload from P. Usage drill shows the same columns (`:636, :671`). M's FE-MATH balance line is **ported verbatim or dropped only by owner decision** (D4) | revert. M is untouched until B6 |
| **B6. Retire entry points (owner-gated)** | `MasterForm.tsx:1083-1094, 1128-1134` ("View Balance" → navigate to P, or keep), `MasterList.tsx:13, 139, 1231-1240, 1411-1415` (dead), then optionally delete `LicenseBalanceModal.tsx` with its test | Only after B5 parity passes and the owner approves. `MasterForm.smoke.test.tsx:38` mock removed or updated | revert (file restored from git) |
| **B7. Optional canonical URL swap (D1 = b)** | `AppRoutes.tsx` | Swap the element to `/licenses/:id`. `/overview` and `/balance` become redirects. Re-run every B3 test with the roles reversed | revert |
| **B8. Dead-code removal (D6)** | `BalanceTab.tsx`, `LedgerTab.tsx`, `LicensesTable.tsx:397-666, 950-951` + Documents gate, `licenseOverviewKeys.planning` | tsc + full vitest. Rebuild the index (`python3 .claude/index/build_index.py`) and confirm no dependents | revert |

"The overview page is removed" is satisfied by B4 + B7 at the earliest. The separate *duplicate* surfaces
(card workspace tabs, modal) are folded into P. P itself becomes the single workspace, and every legacy URL
redirects to it. Nothing is deleted before B0–B3 are green.

### Owner decisions recorded (2026-11-16)

- **Branch:** `feature/v5` is approved. Verified with `git rev-parse --abbrev-ref HEAD` → `feature/v5` in
  `/Users/drushahardiksottany/PycharmProjects/license-manager`.
- **Ownership:** React Architect owns the licence workspace and `LicensesTable.tsx`. The uncommitted
  `frontend/src/features/licenses/**` and `LicensesTable.tsx` changes stay with their current author until
  the orchestrator records an explicit transfer. Until then, B4 and B8 (the parts touching those files) are
  blocked. B0–B3 do not touch them and may proceed once assigned.
- **D4, CIF: APPROVED as the canonical formula, unchanged.**
  - Utilised = BOE CIF + Outstanding Allotment CIF (excluding BOEs) + Billed CIF Without BOE (excluding
    duplicates).
  - Available = Original CIF − Utilised.
  - Item presentation identity: Total Entitlement = BOE + Outstanding Allotment + Invoiced Without BOE +
    Available.
  - The balance engine is not modified. The browser renders backend values only.
- **D4, quantity: NOT YET APPROVED for implementation.** The Reconciliation Engineer must first audit item
  mappings, units, conversions, partial transactions and duplicates, then document and test the
  definition. Until then the frontend client formulas cited in §1.3 are frozen as they are. They are
  removed only once the replacement backend field exists and has been verified.
- **Out of scope:** allocation and balance consolidation.
- **D1: option (a) APPROVED.** `/licenses/:id/overview` stays canonical. B7 is cancelled. The B3 redirect
  `/licenses/:id` → `/overview` stays additive, and no backend endpoint is deleted.
- **D2: APPROVED, with conditions.** Applied to the card (`LicenseRecordWorkspace.tsx:59-82`). The default
  tab stays `overview` (`LicensesTable.tsx:949`).

  | Tab | Decision | Design consequence |
  |---|---|---|
  | Overview | KEEP (default) | unchanged (`ItemsTab` embedded) |
  | Import Item | REMOVE **only if it duplicates the Overview item table** | Verified as an exact duplicate: `ImportItemTab.tsx:5` renders `<ItemsTab licenseId isActive />`, which is the same component, props, endpoint and query key (`license-overview-items`) as the Overview tab (`LicenseRecordWorkspace.tsx:61` → `LicenseOverviewContent.tsx:22-23`). It has no unique field or action, so it is removable. Test: the Overview tab still renders every `ItemsTab` column, and the `import-item` id is gone from the tablist |
  | BOE & Allotment | KEEP as one combined contextual workspace | Already one tab with two `ModuleAccordion` sections (`BoeAllotmentTab.tsx:10-19`, sessionStorage-persisted under `license:<id>:boe-allotment`). It shows the real `overview-boes/` and `overview-allotments/` rows. No change |
  | Invoices | KEEP | unchanged |
  | Planning | KEEP (writer-only, as today) | unchanged. D5 (missing `onSaved`) is still open |
  | Edit Options | REMOVE the tab. Its actions move into a contextual action menu | It holds 3 controls, and each already exists elsewhere in the same card: (1) "Edit licence" = ActionPanel Edit (`LicensesTable.tsx:340-347`); (2) "Recalculate / hide-restore BOE (License Overview)" = the same `navigateToOverview` as the ActionPanel "License Overview" row (`:306`); (3) `IndividualItemCifSwitch` = the info strip switch (`:1193-1198`). Build the menu from the existing `components/ui/dropdown-menu.tsx`; no new primitive and no `ActionMenu` exists in the index. Menu items keep the same `canWrite` gating (Edit is writer-only, the overview link is visible to all) and the existing label texts. The duplicate CIF switch is dropped, because the strip's switch has identical props and permissions. No empty tab remains |
  | History | KEEP | unchanged (`ownership-data/`) |
  | Documents | (not presented) | Left as is. It is never visible today (§0); this stays part of D6 |

  Tab ids are component state, not URL or storage (`LicensesTable.tsx:949`), so removing `import-item` and
  `edit-options` cannot strand a persisted selection. Only `BoeAllotmentTab`'s accordion persists, and it is
  untouched. Removing those ids from `LicenseRecordTabId` makes tsc flag every reference. Update
  `LicenseRecordWorkspace.test.tsx:87-111` (role gating, and the Edit Options navigation test, which should
  be re-targeted at the action menu items).
  Blocker: these files belong to the current author until the ownership transfer is recorded.

### Owner decisions required (open)

D1, D2 and the CIF part of D4 are resolved (see above). The quantity part of D4 waits for the
Reconciliation Engineer. Still open, each with concrete options. Nothing here has been decided on the
owner's behalf.

- **D3. `LicenseBalanceModal` (reachable only from MasterForm "View Balance", `MasterForm.tsx:1083-1094`).**
  Its unique features are not in any workspace surface: condition sheet and notes inline edit
  (`:541-565`), item-tag edit and licence marking `condition_type` (`:232, :276, :310`), the Export Items
  table (`:578-585`) and per-item usage drill-down (`item-usage/`, `:163`). Options:
  - (a) Keep the modal unchanged. No work.
  - (b) Port these features into the overview workspace (B5, parity-tested), then retire the "View Balance"
    entry point (B6).
  - (c) Port them, but keep the modal entry point as well.

  Note: the modal's usage-drill "Balance" line is client-side math (`:1031-1033`). Under (b) or (c) it is
  ported verbatim or replaced by the backend field, depending on the quantity outcome of D4.
- **D5. Card Planning refresh.** Saving a plan in the card's Planning tab does not invalidate summary, items
  or ledger (`LicenseOverviewContent.tsx:19`, no `onSaved`). The overview page does
  (`LicenseOverviewPage.tsx:232`). Options:
  - (a) Add the same invalidation. This changes refresh behaviour, not presentation.
  - (b) Leave it as is.
- **D6. Dead or orphan code (§0).** `BalanceTab.tsx`, `LedgerTab.tsx`, `LicensesTable.tsx:397-666`, the
  null `detail` state and the never-visible Documents tab (`:950-951, :1215`), the unreachable MasterList
  licence `customActions` and its modal wiring (`MasterList.tsx:13, 139, 1231-1240, 1411-1415`), and the
  unused `licenseOverviewKeys.planning`. Options:
  - (a) Delete (B8).
  - (b) Keep.
  - (c) Delete everything except the Documents tab, and instead wire the tab to the existing
    `licenses/:id/` `license_documents` data. That would make a new tab visible in the card, which is a
    presentation change.
- **D7. Column-group header misalignment.** `CustomsLedgerSection.tsx:32` uses `colSpan={6}` for 7 quantity
  and 7 CIF columns. Options:
  - (a) Fix the colSpan to 7. The visible header grouping changes.
  - (b) Keep it.
- **D8. Per-surface formatting.** Balance CIF formats (Indian grouping vs `$` with en-US vs ungrouped
  `toFixed`), date formats (raw `dd-mm-yyyy` on the card vs `fmtDate` on the overview) and toast texts
  (§1.5). Options:
  - (a) Keep per surface (the plan's default).
  - (b) Unify to one format. Choose which, as a presentation change.
- **D9 (new, from D2).** The action-menu label for the Edit Options overview link. Options:
  - (a) Keep the existing text "Recalculate / hide-restore BOE (License Overview)".
  - (b) Merge it into the ActionPanel's existing "License Overview" entry, which navigates to the same
    place.

  The default under "preserve labels" is (a).

### Accessibility hand-off (`a11y-architect`)
- P `TabsList` is sticky and horizontally scrollable (`LicenseOverviewPage.tsx:205`). Check focus visibility
  when it is scrolled.
- In C, the outer `div role=button` contains a nested `button` (`LicensesTable.tsx:1093-1121`). If C's tabs
  become links (D2(b)), each link needs an accessible name that includes the licence number.
- The redirect must not drop focus to `body` without a page title. `usePageTitle.js` has no pattern for
  `/licenses/:id/overview`; check it before B3.

### Risks
- Stale index: `dependents.tsv` still lists `LedgerTab ← LicensesTable`. Rebuild before B8.
- Broadening `["licenses"]` invalidation (§4.2) may refetch other open licences. This is acceptable but
  should be measured.
- `select`-based detail sharing means one large `licenses/:id/` payload stays cached for 30 s. Today the
  same payload is fetched 2–3 times, so memory use is lower than now.
- The uncommitted `features/licenses/**` is not yet on `develop`. Coordinate with its author before B4 so
  user changes are not overwritten.

---

## 7. BOE & Allotment workspace: unified list with supplier/product grouping (owner decisions, 2026-11-16)

**ID note.** The owner labelled these "D3" and "D4". Those IDs are already used in this doc for the balance
modal (D3) and the quantity definition (D4), so they are recorded here as **OD-BA1** (unified list) and
**OD-BA2** (grouping). **Doc-D3 (modal) and the quantity part of doc-D4 remain OPEN.**

### 7.1 Decisions as given

- **OD-BA1.** BOE and Allotment are shown as one list-based workspace using a shared list/table component,
  with a record-type marker (BOE / Allotment). No per-transaction cards. All records, actions, permissions,
  document numbers and relationships are kept.
- **OD-BA2.** Three levels: Supplier → Product name → individual BOE/Allotment records.
  - Grouping happens in the presentation and query layers only.
  - Underlying transactions are never merged or deleted.
  - Different suppliers are never combined because their products match.
  - Counts, quantity, CIF and status come from the backend.
  - Search, filters, sorting and server-side pagination are supported.
  - Missing supplier or product is shown explicitly.
  - No double counting.

### 7.2 Current state (verified)

| Aspect | BOEs (`overview-boes/`) | Allotments (`overview-allotments/`) |
|---|---|---|
| Selector | `backend/apps/license/services/license_overview_boes.py:41-116` | `license_overview_allotments.py:36-83` |
| Grain | **One row per BOE.** `RowDetails` is aggregated by `bill_of_entry_id` across all licence items (`:56-84`). Previous-owner hidden BOEs are excluded (`annotate_and_exclude_hidden`, `:57-66`) | **One row per allotment.** `AllotmentItems` is aggregated by `allotment_id` across licence items (`:37-44`) |
| "Supplier" source | `boe.company.name` (`:110`), FK `core.CompanyModel` (`bill_of_entry/models.py:188`) | Labelled **"Customer"**: `allotment.company.name` (`:76`), FK `core.CompanyModel` (`allotment/models/core.py:49`). `related_company` (`:104`) also exists |
| Product source | **none in the row.** A BOE can span several licence items (`RowDetails.sr_number`) | `allotment.item_name`, free text with no product FK (`:77`, `types.ts` comment) |
| Quantity | aggregated (`qty`) but **not returned** | `quantity` = sum of `AllotmentItems.qty` across the allotment's licence items. **Units can be mixed if the allotment spans items with different units** |
| Columns (frontend) | BOE No., Date, Port, Supplier, Invoice Number, Invoice Date, CIF, Status (`BoesTab.tsx:163-170`) | Allotment Number, Date, Customer, Product, Quantity, CIF, Status (`AllotmentsTab.tsx:129-135`) |
| Row actions | copy BOE number (`BoesTab.tsx:132`) | copy allotment number (`AllotmentsTab.tsx:94`) |
| Search/sort | client-side (`BoesTab.tsx:53-72`), default sort date desc | client-side |
| Pagination | none (full array). Some licences have 1000+ BOEs (`useLicenseOverviewBoes.ts:9`) | none |
| **FE-MATH** | total CIF `reduce` (`BoesTab.tsx:95`) | total qty and CIF `reduce` (`AllotmentsTab.tsx:78-79`); **the qty total adds across units** |
| Card tab | `features/licenses/tabs/BoeAllotmentTab.tsx`: two `ModuleAccordion` sections | same |

Consequence: OD-BA2 **cannot be built on the existing endpoints**.
- BOE rows have no product.
- One BOE spans several products, so per-product CIF needs line-level (BOE × licence item) data.
- Neither endpoint paginates.
- Group totals would have to be computed in the browser, which OD-BA2 forbids.

### 7.3 Duplication matrix rows (add to §1.4)

| Element | Overview page | Card | Target |
|---|---|---|---|
| BOE list | `BoesTab` (its own tab) | `BoeAllotmentTab` accordion → same `BoesTab` | One `LicenceTransactionsWorkspace` (unified grouped list) used by **both** the page and the card. The page's separate BOEs/Allotments tabs become two pre-filtered views (`record_type=BOE` / `ALLOTMENT`) of the same component, or one tab. That choice is **OD-BA-g** |
| Allotment list | `AllotmentsTab` | same component | as above |
| Totals | client `reduce` (FE-MATH) | same | backend group summaries only |

### 7.4 Target architecture

**Backend (additive; existing endpoints unchanged and kept). API CONTRACT ADDITION.**

`GET licenses/:id/overview-transactions/` is a new endpoint. The selector lives in a new
`backend/apps/license/services/license_overview_transactions.py` and reuses the same querysets and filters
as the two existing selectors, including hidden-BOE exclusion and the M2M linked-allotment check
(`license_overview_allotments.py:56-61`).

- **Line grain (classify each source line exactly once):**
  - **BOE line** = `RowDetails` grouped by (`bill_of_entry_id`, `sr_number_id`).
  - **Allotment line** = `AllotmentItems` row (`allotment_id`, `item_id` → licence import item).
- **Line fields:**
  - `record_type` (BOE / ALLOTMENT), `record_id`, `record_number` (BOE number / `ALT-{id}`), `date`
  - `company_id` and `company_name` (original, unmodified), `supplier_group_key`
  - `product_key` (licence import item id), `product_name` (original licence item name), `allotment_item_name` (original free text, allotments only)
  - `qty`, `unit`, `cif_fc`, `status`, `port`, `invoice_no`, `invoice_date`
  - `linked_boe_numbers` (allotments)
  - `classification` ∈ {`BOE`, `OUTSTANDING_ALLOTMENT`, `LINKED_ALLOTMENT`}
- **Group summaries,** computed in SQL:
  - **Supplier level:** `record_count_by_type`, `boe_cif`, `outstanding_allotment_cif`, `linked_allotment_cif` (shown, **excluded from totals**, because the BOE already represents it under approved D4-CIF).
  - **Product level:** the same, plus `qty` per `unit`.
  - **No supplier-level quantity total across different units.** Show per-unit subtotals or omit.
- **Counting rules:**
  - A BOE spanning 2 products appears under each product with **only that product's line CIF**.
  - The supplier total is the sum of distinct lines, never a BOE-level sum repeated per product.
  - Record counts count distinct `record_id`.
- **Pagination:** page over **supplier groups** (L1, `page`/`page_size`, stable order `company_name`,
  `company_id`). For the suppliers on that page, include their product summaries. Records load lazily per
  product: `?supplier_key=&product_key=&page=`.
- **Query parameters:** `search` (record number, company name, product name, invoice no), `record_type`,
  `status`, `date_from`/`date_to`, `ordering`. Parameter names follow `lib/listContract.ts`.
- **Tests:** query count (constant in the number of suppliers), double-count tests (BOE across 2 products,
  allotment linked to a BOE, duplicate AllotmentItems), hidden-BOE exclusion parity with `overview-boes/`,
  null company or product, and mixed units.

**Frontend.**
- `LicenceTransactionsWorkspace` renders **one table with group header rows** (supplier row, then product
  row, then record rows). These are not nested tables, which satisfies the brief's §8.4 rule "no nested
  expandable tables beyond one level".
- It reuses `components/data-table` (`ExpandableDataTable`) or TanStack grouping. Note that
  `@tanstack/react-table` is a pending, unapproved dependency.
- Record-type badge. Supplier and product rows show backend summaries only, so the FE `reduce` disappears.
- Keeps both copy-number actions. Status badge variants are reused (`overviewBoeStatusVariant` and the
  allotment equivalent).
- Query keys `qk.licenses.overview(id, "transactions", params)` sit under the licence detail prefix, so
  `invalidateLicence` covers them.

**Missing values:**
- `company_id` null → group "No supplier recorded".
- No product mapping → "Unmapped product".
- Original values are never rewritten.

### 7.5 Ownership (proposed; to be confirmed by the orchestrator)

| Work | Owner | Files |
|---|---|---|
| Selector, view, URL, tests | Backend Engineer | new `services/license_overview_transactions.py`, `api/views/…` (new view), license `urls`, new tests |
| Classification and double-count review | Reconciliation Engineer + `cif-balance-auditor` | review only |
| Grouped list component | DataTable owner (Agent D) | `components/data-table/*` (extension) |
| Card tab integration | **current author of `features/licenses/**`** (transfer required) | `features/licenses/tabs/BoeAllotmentTab.tsx` |
| Page tab integration | frontend-engineer | `pages/license-overview/LicenseOverviewPage.tsx`, `BoesTab.tsx`, `AllotmentsTab.tsx` |
| Regression and browser checks | QA | tests |

### 7.6 Open decisions (cannot be inferred; not decided here)

- **OD-BA-a. Supplier source.** For allotments the current UI says "Customer" (`allotment.company`).
  Confirm that L1 "Supplier" = `company` for both BOEs and allotments, or name another field for allotments
  (for example `related_company`).
- **OD-BA-b. "Safe normalisation".** Proposed: group by `company_id`. Different `company_id`s are merged
  only if the names are identical after trim, casefold, whitespace collapse and punctuation strip, and only
  if the owner confirms that rule. No fuzzy matching. Should near-duplicates instead be listed for master-data
  cleanup?
- **OD-BA-c. Product key.** Licence import item (SR / canonical item names) is proposed because both BOE and
  allotment lines link to it. Alternatives are canonical item name, or the allotment free-text `item_name`.
- **OD-BA-d. Column set and labels** of the unified list (union of the BOE and allotment columns, "—" where
  not applicable). Keep both "Supplier" and "Customer" labels?
- **OD-BA-e. Linked allotments.** Show them under their product with "Linked to BOE" status, excluded from
  totals (proposed), or hide them by default.
- **OD-BA-f. Default expansion.** Suppliers collapsed or expanded, and the default sort.
- **OD-BA-g.** Does the overview page keep separate BOEs and Allotments tabs (as filtered views) or merge them
  into one tab like the card?
- **Dependency.** Approval of `@tanstack/react-table` (already in `package.json`, uncommitted, unapproved).

**Blocked until decided:** OD-BA-a, b and c. The backend contract depends on them.
