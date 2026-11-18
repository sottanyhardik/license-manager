# Item Pivot Report — current-state audit (2026-11-18)

Read-only audit before the "Licence Utilization & Planning Intelligence" upgrade.
Nothing was changed. File references are to `feature/v5` at the time of writing.

## Flow

- Endpoints (`backend/apps/license/urls.py`): `GET reports/item-pivot/` (`ItemPivotReportView`,
  `api/views/item_pivot_report.py:70`), `GET item-pivot/` (same logic, `ItemPivotViewSet.list`),
  `GET item-pivot/available-norms/`, `POST item-pivot/update-balance/` (Celery `update_all_license_balances`),
  `GET item-pivot/task-status/<id>/`. Permission: `ReportPermission`.
- Params: `format` (json|excel), `days`, `sion_norm`, `company_ids`, `exclude_company_ids`, `min_balance`
  (default 200, against the live financial balance), `license_status`, `expiry_date_from/to`, `purchase_status`.
- JSON is synchronous, cached 300 s per query string + registry version. Excel streams
  (`item_pivot_excel.py:28`).
- `generate_report` (`item_pivot_generate.py`) returns `ItemPivotService.build(valid_licenses)` at ~line 184;
  lines ~186-687 are unreachable legacy code.
- Response: `groups` (per notification / purchase status) → `licenses[]` → `items{key: cell}`, plus `summary`,
  `items`, `item_columns`, `grand_total`, `report_version="canonical-item-pivot-v1"`, optional `c969_entitlement`.

## Product identity today

- Column key = `f"{product_category}:{sion}"` where `product_category = classify_product(hsn, description, norm)`
  (keyword/HSN classifier, first match wins); unmatched → `UNCLASSIFIED:<sion>`.
- `ItemNameModel` (the master canonical item, M2M from import items) is only carried on the cell
  (`canonical_item_id`, `item_name`) — it does not define the column.
- Duplicate / merge risks: unclassified distinct products merge into one column; the same canonical item can
  appear under two categories; unplanned items are named by raw description; `_merge_plan_cell` keeps only the
  first `canonical_item_id`; a stale loop variable (`key`) is reused when registering `item_groups` (~:506-513).

## Financial columns vs canonical rule (`.claude/rules/business-rules.md`)

| Column | Current source | Canonical? |
|---|---|---|
| Licence original CIF | Σ export `cif_fc` inline | equivalent to `calculate_credit` (not called) |
| BOE CIF / qty | `get_item_usage_for_items` (non-hidden DEBIT rows) | raw BOE debit, not allocation-aware `calculate_debit` |
| Allotment CIF / qty | `AllotmentItems` with `allotment.bill_of_entry IS NULL` | **bypasses `BOEAllotmentAllocation` partial netting** |
| Licence balance CIF | `max(total − debited − allotted, 0)` | **diverges**: no billed-without-BOE term, floored at 0 (owner decision 2026-11-16: signed + `is_over_utilised`) |
| Item balance CIF | `max(source_cif × adjusted_qty / source_qty − used, 0)` | proportional estimate |
| Unit price | `balance_cif / balance_qty` | not the rule's maximum unit price |
| Planned qty / CIF | raw active `LicenseItemPlan` | `reconcile_license_plans` not used |

Only the `min_balance` filter uses `LicenseBalanceCalculator.calculate_financial_balance_for_licenses`.

## Reusable building blocks

- `LicenseBalanceCalculator.calculate_financial_balance_for_licenses(license_ids)` — per-licence available CIF.
- `get_item_usage_for_items`, `billed_no_boe_bulk_map`, `billed_no_boe_qty_bulk_map` (`services/item_usage.py`).
- `classify_product` (`services/product_classification.py`), `ItemNameModel` M2M, `plan_grouping.group_ids_of`.
- `reconcile_license_plans` (`services/planning_usage_reconciliation.py`), `compute_condition_pools_bulk`.
- Auto Plan engine `SionPlanningExecutionService.plan_sion(persist=False)` — read-only preview, already capped at
  `min(live balance, SION export CIF − actual debits)` (0 / 1,201 real previews over the cap, 2026-11-18).

## Owner decisions (2026-11-18) and what was implemented

1. **Canonical engine** — classic report licence rows now use `calculate_debit/allotment/trade/financial_balance
   _for_licenses` (signed balance, `is_over_utilised`, billed term); summary `final_balance_cif` is signed and
   `overdrawn_cif` is Σ negative licence balances. Item cells are unchanged (item-level raw basis, labelled as such).
2. **Product identity = `ItemNameModel` × SION** — `services/item_pivot_intelligence.py`. Import items with no
   master link are "Unmapped" (deduped only on identical normalised description + HSN); with several links
   "Ambiguous"; both never merged. Master items spanning HSN chapters are flagged `mapping_review`.
3. **Recommendations** — no competing optimiser: the existing Auto Plan engine is run in read-only preview
   (`transaction.atomic` + `set_rollback`) per licence; ranking = licence expiry, then SION rule priority.

## New endpoints (read-only, `ReportPermission`)

- `GET item-pivot/intelligence/` (same filters as the report; `format=excel` → Products / Licences / Eligibility /
  Exceptions sheets).
- `GET item-pivot/recommendations/?license_ids=…` (≤ 25 licences; `format=excel`).
- Licence selection is shared: `services/item_pivot_selection.select_pivot_licenses` (moved verbatim; the
  unreachable legacy block after `generate_report`'s early return was removed).

## Known limitations

- Item-level quantities are raw records (visible BOE rows, allotments not linked to a BOE, billed-without-BOE);
  invoice representation and `BOEAllotmentAllocation` netting apply only at licence level (shown in the UI).
- Split targets (e.g. E126 PKO / Olive) are shown per licence through the existing entitlement planning report
  ("Show entitlement split"); product rows attribute plans to their source import item.
- In the local DB most E126/E5 import items have no master-item link, so they appear as Unmapped (warning).
