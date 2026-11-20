# Item Pivot — transaction attribution: implemented rules and OPEN owner decisions (2026-11-20)

Status: implemented (uncommitted, feature/v5) · open items below need the owner. Existing behaviour is preserved for
every open item. Licence-level CIF is unchanged (canonical `LicenseBalanceCalculator`, `business-rules.md`).

## Implemented (item-level projection only — `backend/apps/license/services/item_pivot_service.py`)

1. **Transaction-level attribution.** Every BOE `RowDetails` row, `AllotmentItems` row and billed-without-BOE import
   item of a licence is carried by at most one item cell (`carried_rows` / `carried_billed`). Overlapping plan sources
   no longer count a transaction twice; `_merge_plan_cell` adds the (already deduplicated) usage of every candidate.
2. **NOT ATTRIBUTED (TARGET MISSING).** Usage no cell carries is one row per licence with per-transaction records and a
   reason: `no_target`, `target_not_planned` (target has no plan on that source), `target_not_carried`,
   `split_source_billed`. No entitlement, plan, capacity or over-use exception.
3. **Licence scope.** A plan reads only its own licence's import items (stale provenance ids are ignored).
4. **Per-licence reconciliation.** `group.reconciliation.reconciled` is true only when every licence matches on
   allotted / debited / billed / planned CIF (tolerance < 0.01) and on BOE / allotment / billed quantity
   (< 0.001); group totals are informational, licence differences never cancel.
5. Excel Item Summary: calculated zero → numeric 0; missing value (e.g. unit price) → empty cell; never text.

Real local data (read-only, 2026-11-20): 20/20 notification groups (E126, E5, E1, A3627) reconcile per licence;
91 NOT ATTRIBUTED records. Before: E5 025/2023 GLOBAL EXIM item side short by 8,435,181.79 debited CIF.

## OPEN — owner decisions (current behaviour kept)

| # | Question | Current behaviour (kept) | Impact |
|---|---|---|---|
| D1 | Two STANDARD plans on the same source both fall back (no usage mapped to either target): who gets the **unmapped** BOE / allotment rows? | First plan in plan order takes them (counted once). | Which item column shows the usage is arbitrary; totals correct. Options: NOT ATTRIBUTED, proportional, priority rule. |
| D2 | A row mapped to Item Name X on a source where X has **no plan**, and the source's plan has no usage mapped to its own target. | Legacy fallback: the plan's cell takes it. | Usage shown on a different item than its mapped target. Option: always NOT ATTRIBUTED (`target_not_planned`). |
| D3 | Billed-without-BOE on a **percentage-split** source (no planning target on trade lines). | Shown once in NOT ATTRIBUTED; not deducted from any split target's balance; each target shows `shared_source_billed_cif`. | Split-target item balance CIF is higher than if billed were apportioned. Option: apportion by split %. |
| D4 | Reconciliation compares canonical licence CIF (allocation-aware debit, BOE-netted allotment) with raw item rows. | Reported as is; `definitions` text explains. | A licence with invoice-represented BOEs or allocation netting can show "does not reconcile" while correct. Option: compare item cells to raw-row licence totals, show canonical separately. |

## E1 Total Summary ↔ detail (2026-11-20, later) — implemented

Approved scope: the Total Summary aggregates every notification/company group of the report (E1 active: 019/2015
GLOBAL EXIM 3 + 025/2023 GLOBAL EXIM 63 + 025/2023 MITC 14 = 80 distinct licences); each notification tab stays scoped.

Root causes fixed:
1. **API default dropped MITC.** `item_pivot_selection` defaulted to `[GE, MI, CO]` with `constants.MI == "NP"`; MITC's
   code is `MI`. The default now accepts both (`MITC_CODE`). The UI already sent every code. `constants.MI` is unchanged
   (also used by the active / expiring licence reports — not in scope; same mismatch there, flagged for the owner).
2. **Two row identities.** Notification Item Summaries were built from matrix category columns, the Total Summary from
   the canonical projection. Screen and Excel now use one projection (Item Name × SION) for both.
3. **Identity lost in merged category cells.** Cells carry `identity_parts`; the projection aggregates them, so an item
   is never credited with another item's rows and sources without one Item Name are listed in
   `NOT ATTRIBUTED (NO ITEM NAME)` (reasons: `no_item_name`, `ambiguous_item_name`, `item_name_not_valid_for_norm`)
   — distinct from `NOT ATTRIBUTED (TARGET MISSING)` (mapped usage whose target is not planned / missing).
4. **Valid mappings read as unmapped.** The canonical report now accepts an Item Name valid for the norm through
   `ItemNameModel.norms` (as the intelligence views already do), not only the legacy single-norm FK.

Real local data (read-only), E1 active, min balance 200: 80 licences; 21 products; Total Summary = licence detail =
Σ notifications on every metric (total qty 49,892,536.054; debited CIF 12,776,002.35; allotted CIF 1,420,272.70; planned
CIF 13,839,636.66; balance qty 43,940,798.868); NO ITEM NAME 82 source rows; all units KG; Excel = screen.

| # | Open question | Current behaviour (kept) |
|---|---|---|
| D5 | Active / expiring licence reports also filter `[GE, MI, …]` with `MI == "NP"` → MITC excluded there too. | Unchanged (out of scope). |
| D6 | An import item linked to several Item Names (10 E1 source rows). | NOT ATTRIBUTED (`ambiguous_item_name`); the matrix column keeps its display label. |

## Review round (2026-11-20, later) — fixed and follow-ups

Fixed: TARGET MISSING summary rows now carry `source_records` (licence, BOE/allotment/billed id, serial, HSN, description,
unit, reason) — display only. **F1:** a SPLIT_BY_PERCENT plan whose Item Name is NULL (`SET_NULL`) took every row on its
source, including rows mapped to another target; it now carries none. **F3:** `summary_check.consistent` allows only output
rounding (½ unit × summed rows). Opus cif-balance-auditor: APPROVED. No business-rule change.

Non-blocking follow-ups (current behaviour kept; owner to prioritise):
- Mixed quantity units are summed without a visible marker (`mixed_units` is JSON only); TARGET MISSING rows collect no units. Real E1: all KG.
- Item Summary has no BILLED columns; a TARGET MISSING row holding only `split_source_billed` shows zeros (amount in `source_records`). Reason label `split_source_billed` is also used for non-split billed.
- A plan's secondary source in another category can repeat its entitlement (`planned_import_item_ids` holds only `plan.import_item_id`).
- MITC default also widens `item_pivot_intelligence` and `product_matching_semantic` defaults (consistent with NP→MI history).
- Excel/screen: calculated zero shown as 0 (was blank); rows named by canonical Item Name; tab labels "Notification N · status (count)".
- Reconciliation banner can be a definition difference (D4), shown in destructive style.
- RUTILE unit price on a merged multi-part cell drops balance (no such cells in local data).
- Performance/size: `linked_name_counts` IN-list over all import items; NOT ATTRIBUTED records repeated in several payload places.
- Frontend: tab buttons lack `aria-pressed`; tab id collides if two groups share a notification with no status; float subtotal (display-rounded).
