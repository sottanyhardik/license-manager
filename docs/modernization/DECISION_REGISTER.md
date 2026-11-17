# Decision Register — Unified Licence Workspace and BOE/Allotment workspace

Status of this document: PROPOSALS ONLY. Nothing in the "Proposed" section is approved. Written 2026-11-16 by the
principal-architect role from current code (feature/v5 working tree). Sources: `frontend-audit/06_UNIFIED_LICENCE_WORKSPACE.md`
(older line refs re-verified here), `backend-audit/05_ALLOCATION_AUDIT.md`. Measured data for OD-BA-a/b/c: see
`backend-audit/07_BOE_ALLOTMENT_MAPPING_AUDIT.md` (not duplicated here; proposals below rest on code evidence only).

## Approved (owner-confirmed 2026-11-16)

- **Overview tab** = licence summary + financial/CIF summary + ledger. Items live under Import Items. No duplicate item table.
- **D3 (card/list)** = BOE and Allotment shown as lists/tables, not oversized cards. All record fields and actions preserved.
  (Note: this is the owner's "D3". In doc 06 it is recorded as OD-BA1. Doc 06's own D3, the balance modal, is still OPEN.)
- **D4 (grouping)** = Supplier → Product Name → individual records.
  - Normalise for grouping only. Never merge different suppliers. Preserve every transaction.
  - Show counts, quantity and CIF. No aggregation across incompatible units.
  - Quantity semantics are NOT approved (doc 06's D4 quantity part stays open; the client formula
    `CustomsLedgerSection.tsx:10` `actualAvailableQuantity` still exists and waits for the Reconciliation Engineer).
- **Earlier:** CIF `$` en-US format on the licence workspace; card status from `deriveStatus`; D1(a) `/overview` stays.

## Owner-reviewed proposals (D5–D9, OD-BA-a/b/c APPROVED 2026-11-17 as recommended)

### D5. Card Planning refresh
- **Decision:** the card's Planning tab passes `onSaved` that calls `invalidateLicence(queryClient, id)`, as the overview page does.
- **Rationale:** after a plan save the card's Overview financial summary, Import Items and ledger show stale planned/balance figures until a manual reload; the page already refreshes them.
- **Verified now:** `LicenseOverviewContent.tsx:16` renders `PlanningEditor` with no `onSaved`; page passes it at `LicenseOverviewPage.tsx:225` (`refreshPlanningDependents` → `invalidateLicence`). `PlanningEditor` already supports `onSaved` (`:206, :841`).
- **API:** none. **DB:** none. **Frontend:** one optional prop on `LicenseOverviewContent` + wiring from `LicenseRecordWorkspace.tsx:58`; refetch behaviour only, no presentation change. **Reporting:** none.
- **Risks:** extra refetches after each row save (the editor saves per row; `onSaved` fires each time). Debounce or invalidate once per batch if noisy. `LicenseRecordWorkspace.tsx` is owned by a debugging agent; coordinate.
- **Options:** (a) add invalidation **[RECOMMENDED]**; (b) leave.
- **Blocks grouped BOE/Allotment endpoint:** no.
- **Status:** APPROVED 2026-11-17 (owner), recommended option.

### D6. Dead and orphan code
- **Decision:** delete `BalanceTab.tsx` and `LedgerTab.tsx` now; defer the balance-modal wiring removal to the D3-modal decision; do not add a Documents tab.
- **Rationale:** dead 1,692 LOC inflates the load-bearing graph and misleads readers; removal is reversible via git.
- **Re-audit against current code (06 list is partly stale):**
  - `pages/masters/tables/BalanceTab.tsx` (530) and `LedgerTab.tsx` (1162): still present, no importer (grep finds only self-references). Safe to delete. The index may still list `LedgerTab ← LicensesTable`; rebuild it.
  - `LicensesTable.tsx` is now 98 lines: the in-file dead `OverviewTab/AllocationTab/TransactionsTab`, the null `detail` state and the Documents gate are **already gone**. Nothing left to delete there.
  - `licenseOverviewKeys.planning` is **no longer dead**: now aliased to `qk.licenses.detail` (`useLicenseOverviewSummary.ts:23`, pinned by `LicenseOverviewPage.queryKeys.test.tsx:106`). Keep.
  - `MasterList.tsx` licence `customActions` "View Balance" (`:1271-1280`) and `LicenseBalanceModal` (`:13, :161, :1451`): licences render through `LicensesTable` (`:1037`), so the actions are unreachable, but the modal import is the same component kept for `MasterForm.tsx:12, :1129`. Remove the MasterList wiring only after D3-modal is settled or as a separate low-risk step.
- **API:** none. **DB:** none. **Frontend:** file deletions + (optionally) MasterList cleanup; no visible change. **Reporting:** none.
- **Risks:** hidden importers (dynamic import, tests). Mitigate with `tsc` + full vitest + index rebuild. Do not delete the modal (still reachable from MasterForm).
- **Options:** (a) delete BalanceTab/LedgerTab, MasterList wiring later **[RECOMMENDED]**; (b) keep; (c) also build a Documents tab (a new visible tab = presentation change, needs its own approval).
- **Blocks grouped BOE/Allotment endpoint:** no.
- **Status:** APPROVED 2026-11-17 (owner), recommended option.

### D7. Import Items column-group header misalignment
- **Decision:** set the Quantity and CIF (FC) group headers to `colSpan={7}` so they cover their 7 columns each.
- **Rationale:** the header currently spans 4+6+6+1 = 17 columns over a 19-column body, so groups and Status misalign.
- **Verified now:** `CustomsLedgerSection.tsx:31` (header row); `quantityFields` and `cifFields` each have 7 entries (`:15-16`).
- **API:** none. **DB:** none. **Frontend:** two attributes; header grouping visibly shifts (the intent). **Reporting:** none (Excel/PDF exports are separate).
- **Risks:** `Identity` colSpan 4 over sticky columns is unaffected. Snapshot/aria tests may assert the old spans.
- **Options:** (a) fix to 7 **[RECOMMENDED]**; (b) keep.
- **Blocks grouped BOE/Allotment endpoint:** no.
- **Status:** APPROVED 2026-11-17 (owner), recommended option.

### D8. Per-surface formatting (CIF, dates, toasts)
- **Decision:** keep formats per surface; the licence workspace stays `$` en-US (already approved); do not unify other surfaces now.
- **Rationale:** the owner's constraint is that existing presentation is preserved per surface. Users of the Indian-grouped balance report and the PDF/Excel exports expect their own format, and unification changes every number a user compares across screens.
- **API:** none. **DB:** none. **Frontend:** none. **Reporting:** none (exports keep their own format).
- **Risks:** inconsistency stays visible across surfaces (card/page vs modal vs report). A later unification should go through one `licenceFormat.ts`-style helper (exists at `features/licenses/licenceFormat.ts`) with a per-surface migration.
- **Options:** (a) keep per surface **[RECOMMENDED]**; (b) unify to one format (owner must name it).
- **Blocks grouped BOE/Allotment endpoint:** no. The unified list should simply reuse the licence-workspace format.
- **Status:** APPROVED 2026-11-17 (owner), recommended option.

### D9. Action-menu label for the overview link
- **Decision:** keep the label "Recalculate / hide-restore BOE (License Overview)".
- **Rationale:** it describes a distinct intent for writers (the hide/restore BOE controls live on the overview), and the label is pinned by `LicenceRegister.test.tsx:100, :272`. Both entries navigate to the same place (`licenceActionItems.ts:31, :58`), so the cost of keeping is one redundant menu row.
- **API:** none. **DB:** none. **Frontend:** none. **Reporting:** none.
- **Risks:** duplicate destination may confuse; revisit only if user feedback says so.
- **Options:** (a) keep **[RECOMMENDED]**; (b) merge into "License Overview" (removes a writer-only hint, changes the test).
- **Blocks grouped BOE/Allotment endpoint:** no.
- **Status:** APPROVED 2026-11-17 (owner), recommended option.

### OD-BA-a. Supplier source
- **Decision:** L1 "Supplier" = the transaction's `company_id` for both BOEs and allotments (BOE `company`, allotment `company`); `related_company` is not used for grouping.
- **Rationale:** both are non-optional business party FKs to `core.CompanyModel` with an `iec` unique key (`core/models.py:226-227`); using one field per type keeps "no merging of suppliers" provable. Allotment `company` is today labelled "Customer" in the UI (`AllotmentsTab.tsx:129`), so the label mapping needs owner confirmation: a customer on an allotment is the counterparty on the other side of the BOE supplier.
- **Evidence:** BOE `company` is `null=True` (`bill_of_entry/models.py:188-194`) so BOEs can have no supplier; allotment `company` is required (`allotment/models/core.py:49-53`); `related_company` is optional (`:104-109`) and has a different meaning (related party).
- **API:** the new grouped endpoint exposes `supplier_id`, `supplier_name`, and `supplier_source` (`company` vs none). Existing endpoints unchanged. **DB:** none. **Frontend:** the group header shows the name; a "No supplier" group for null BOE company. **Reporting:** none unless exports adopt the grouping.
- **Risks:** mixing BOE suppliers and allotment customers under one L1 may group unrelated parties together if a company is both. Keep record-type visible on every row. Null-supplier BOEs must show an explicit group. See 07 for measured coverage.
- **Options:** (a) `company` for both **[RECOMMENDED]**; (b) `related_company` for allotments when set, else `company` (inconsistent across records); (c) separate L1 per record type (Suppliers for BOE, Customers for allotments).
- **Blocks grouped BOE/Allotment endpoint:** **yes**.
- **Status:** APPROVED 2026-11-17 (owner), recommended option.

### OD-BA-b. "Safe normalisation" of supplier identity
- **Decision:** group strictly by `company_id`; no name-based merging in the endpoint; list same-normalised-name different-`company_id` pairs in a master-data cleanup report instead.
- **Rationale:** `CompanyModel.name` is neither unique nor normalised (`core/models.py:245`; `iec` is the unique key), so a name match is not proof of identity and merging would violate "never merge different suppliers". The existing precedent `ItemNameModel.normalize_name` (trim, collapse whitespace, upper, `core/models.py:399-402`) is for items, not companies. Also `normalized_name` has no company equivalent.
- **API:** none beyond the grouping key (`company_id`). **DB:** none (a company `normalized_name` column would be a SCHEMA CHANGE and is not proposed). **Frontend:** none; display name = the company's own name. **Reporting:** optional one-off duplicate-candidate list.
- **Risks:** one real supplier with two company records appears twice (visible, not wrong). Rewiring FKs to merge them is a data operation needing owner approval. Whitespace-only differences in the displayed name do not affect grouping.
- **Options:** (a) `company_id` only + cleanup list **[RECOMMENDED]**; (b) merge identical normalised names (casefold, whitespace, punctuation strip) at group time (cheap but can hide distinct IECs, requires owner rule); (c) fuzzy match (rejected, unsafe).
- **Blocks grouped BOE/Allotment endpoint:** **yes** (defines the L1 key). Recommended option (a) is the simplest contract.
- **Status:** APPROVED 2026-11-17 (owner), recommended option.

### OD-BA-c. Product key (L2)
- **Decision:** L2 = the licence import item (SR number, `serial_number`) the record line is drawn against, displayed as canonical product name(s) via `items_detail`; allotment free-text `item_name` is shown only as a secondary label.
- **Rationale:** BOE lines (`RowDetails.sr_number`) and allotment lines (`AllotmentItems.item`) both reference licence import items, so this is the only key common to both. BOE rows have no product at all today, and one BOE can span several SRs, so per-product CIF requires line-level (BOE × SR) rows, not the current one-row-per-BOE selectors. `AllotmentModel.item_name` is free text (`allotment/models/core.py:91`) with no FK.
- **Evidence:** an import item maps many-to-many to `ItemNameModel` (`license/models/items.py:90`), so one SR may carry several canonical names; the UI already joins them (`CustomsLedgerSection.tsx:12`). Grouping by canonical name would therefore count one SR under multiple groups (double counting, forbidden by the approved D4).
- **API:** the grouped endpoint must be line-level (BOE line / allotment item as the grain), return `sr_number`, product label, unit, and per-group count/qty/CIF; qty not summed across different units (return per-unit subtotals or "mixed units"). **DB:** none (read model over existing tables). **Frontend:** L2 header shows "SR n · product"; "Unmapped product" bucket. **Reporting:** none.
- **Risks:** SR with several canonical names (display only, group key stays SR); SR missing product mapping; mixed units within a group; allotments spanning several SRs get several lines (not double counted if each line carries only its own qty/CIF); linked allotments already netted against BOEs must stay excluded from totals (OD-BA-e). Quantity semantics remain unapproved: the endpoint can return the raw line qty and unit and leave derived "available" qty out. Allocation audit `05` D5/D6 shows BOE-linked allotment items are counted differently by R1/R3/R5, so any totals must state which rule they use. See 07 for measured mapping coverage.
- **Options:** (a) licence import item (SR) **[RECOMMENDED]**; (b) canonical `ItemNameModel` (breaks on many-to-many, double counts); (c) allotment `item_name` (BOE has none).
- **Blocks grouped BOE/Allotment endpoint:** **yes**.
- **Status:** APPROVED 2026-11-17 (owner), recommended option.

## Dependencies and notes

- A grouped BOE/Allotment endpoint is blocked only by OD-BA-a, b and c. D5 to D9 are independent and can ship separately.
- Open items not in this register: OD-BA-d (columns/labels), e (linked allotments), f (default expansion), g (page tabs), the `@tanstack/react-table` approval, doc 06 D3 (balance modal) and D4 quantity.
- Allocation-engine decisions in `05` (O1 to O9) are untouched; they constrain what "available qty/CIF" a new endpoint may expose and are not proposed here.

## Escalated: client-side derived financial values (inventory; no change made)

These predate this work and are kept as-is pending owner review / the quantity proposal (backend-audit/08):

| Site | What it computes | Status |
|---|---|---|
| `license-overview/CustomsLedgerSection.tsx:12,26` | Available quantity, overriding the server value | escalated (D4 quantity) |
| `components/LicenseBalanceModal.tsx:1031-1033` | A different available-quantity formula | escalated (D4 quantity) |
| `license-overview/BoesTab.tsx:95` | Client CIF total | escalated |
| `license-overview/AllotmentsTab.tsx:78-79` | Client CIF + quantity totals (quantity mixes units) | escalated |
| `license-overview/AllotmentsTab.tsx` Rate column | `cif_fc / quantity` (moved from the old card into the table under D3, so no information is lost) | escalated. **Owner option:** keep it, or drop it until a server field exists |

## Added 2026-11-16 (later session): new open decisions and escalations

All PROPOSED / awaiting owner. Full definitions live in the cited docs; they are indexed here so the owner has one list.

### From backend-audit/07 (mapping) and 08 (quantity)
- **OD-MAP-1..6** (`07` §decisions): BOE CREDIT rows in totals (= OD-QTY-6), cross-licence / no-shared-SR BOE↔allotment links,
  same-SR rule for manual allocations, AR allotments in the workspace, unit-string equality, PLAN rows as separate records.
- **OD-QTY-1..14** (`08` decision table): Available Quantity definition, "Billed (No BOE)" source, floor vs signed qty,
  allotment line qty, per-unit group subtotals, ledger allotment-row qty, Rate column (resolves the escalated Rate item above),
  client grand totals, stored-vs-live drift, orphan `allocationMath.ts`. OD-QTY-4/11/12 defer to doc 05 O2/O3/O4 (decide once).
- Measurements M1–M14 (`07` §5) are written but **not run** (no DB operations authorised). Running them is read-only; approval needed.

### Escalated rule/code conflicts (verified by an independent boe-reconciliation-auditor; nothing changed)
| Finding | Severity | Evidence |
|---|---|---|
| Allotment overview "Total Allotted" sums every row with no netting, so CIF of BOE-linked allotments is also counted under BOEs and disagrees with the engine ALLOTMENT CIF; qty mixes units | **HIGH (user-visible)** | `license_overview_allotments.py:37-44`, `AllotmentsTab.tsx:71-72` |
| BOE overview sums C+D rows; engine uses D only | LOW / latent (no current writer attaches C rows to a BOE) | `license_overview_boes.py:58`, `balance_calculator.py:581` |
| Stored available/debited qty does not exclude hidden BOEs; engine does | MEDIUM | `core/scripts/calculate_balance.py:41-45` vs `balance_calculator.py:1996,2033` |
| Ledger re-import bulk-creates duplicate CREDIT rows (lookup filters DEBIT only) | MEDIUM (data integrity, untested) | `core/scripts/ledger.py:308-311` |

### From frontend-audit/07 (routes, filters, reuse)
- **B8** 429 handling: needs owner OK for the new toast text. **B9b** first `useListQuery` consumer: needs the list-URL shape agreed.
  **B13** nav links for 9 unlinked routes. **B14** ledger page per-licence fan-out (throttle risk) needs backend confirmation.
- **D6 addendum:** `pages/ServerError.tsx` is also dead (no route, no importer).
- Done (no decision needed, committed aa0922c0): B0–B6, B9a.

### From backend-audit/09 (licence workspace performance)
- Ranked fixes 1–6 are proposals. #1 (documents-only endpoint) is an **API CONTRACT** addition. #2, #4, #5, #6 touch CIF
  computation paths and need cif-balance-auditor review before implementation.

## Owner decisions 2026-11-17

- **APPROVED as recommended:** D5, D6 (incl. `ServerError.tsx`), D7, D8, D9, OD-BA-a, OD-BA-b, OD-BA-c.
- **Packages:** `@tanstack/react-table` 8.21.3 APPROVED. `react-hook-form`, `zod`, `@hookform/resolvers` NOT approved (removed).
- **Doc-07 follow-ups APPROVED:** B8 (429 handling), B9b (first `useListQuery` consumer, list page in URL), B13 (nav links), B14 (ledger fan-out).
- **Balance modal ("complete"):** implemented as doc 06 D3 option (c): unique modal features ported into the workspace, modal and its
  MasterForm entry kept unchanged. The modal's client-side usage "Balance" line was not ported (quantity semantics still open).
  If the owner intended (b) (retire the modal entry point), that is a follow-up step (B6).
- **Still open:** OD-BA-d (columns/labels), e (linked allotments display), f (default expansion), g (page tabs) — these gate the
  grouped list's UI placement only; the backend endpoint and client are implemented. Quantity semantics (OD-QTY, OD-MAP),
  measurements M1–M14, and the escalated rule/code conflicts above.
