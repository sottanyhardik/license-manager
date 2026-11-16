# Backend Audit 02 — Logic Placement and Financial Write Safety

Scope: `backend/apps/*`. Read-only audit, 2026-11-16. No formulas are proposed for change; every
"target" below is a placement suggestion that must preserve current behaviour (characterization tests
first, per `.claude/rules/business-rules.md`). Paths are relative to `backend/apps/`.
Evidence = `file:line` from grep/reads in this session; "not verified" is stated where I only inferred.

Canonical engine: `LicenseBalanceCalculator` / `ItemBalanceCalculator`,
`license/services/balance_calculator.py` (2160 lines; classes at :80 and :1714).

Global facts that frame section 5:
- No `ATOMIC_REQUESTS` setting anywhere in `backend/` (grep returned nothing). Atomicity is opt-in per call site.
- `core/views/master_view.py` (`MasterViewSet.create_viewset`) has no `transaction.atomic`: `perform_create`
  :136, `perform_update` :154, `perform_destroy` :169 (plain `instance.delete()` at :187). It backs the BOE
  (`bill_of_entry/views/boe.py:103`), LicenseTrade (`trade/views.py:32`), TradeLine (`:665`),
  TradePayment (`:694`), Allotment (`allotment/views.py:46`) and LicenseDetails (`license/views/license.py:100`)
  viewsets.
- Request-level `ActivityLog` is written by `core/middleware.py:118-135` from a daemon thread after the
  response (`_start_log_thread`, :98-110). It records method/path/status only, not entity before/after, and is
  disabled under test (`_activity_logging_disabled`, :91). It is not an entity audit trail.

---------------------------------------------------------------------------------------------------

## 1. Business logic in views (ranked by size x risk)

| # | Location | What it does beyond HTTP | Suggested target |
|---|---|---|---|
| 1 | `allotment/views_actions.py:1071-1570` `_allocate_items_atomic` (~500 lines, `@transaction.atomic` :1071) | Locks allotment (:1098), re-aggregates committed qty/CIF (:1101-1106), per-item Decimal math `canonical_cif = qty*unit_price` quantized ROUND_UP (:1192 region), availability/plan-cap checks, `existing.cif_fc += cif_fc` merge (:1441 region), `AllotmentItems` create/save, plan-line ledger link, then `update_balance_values` per touched item (:1510-1516). Whole allocation workflow lives in the view. A parallel, unused-by-views `AllotmentService` exists (`allotment/services/allocation_service.py:24-277`, only re-exported in `allotment/services/__init__.py:10`). | `allotment/services/` (merge with / replace the orphan `AllocationService`); selector for availability |
| 2 | `allotment/views_actions.py:230-684` `available_licenses` (~450 lines) and `:685-1050` `_available_licenses_plan_mode` (~365) | Builds candidate queryset from ~20 query params, inline sums over `allotment_details` (:268-278, seeds `allotment.__dict__` derived totals), remaining-requirement math (:281-283), exhaustion short-circuit | `allotment/selectors.py` (candidate query) + `allotment/services` (requirement/remaining) |
| 3 | `allotment/views_actions.py:64-130` `_position_payload` | Decimal clamps (`max(...,0)`), plan/actual basis ceilings, enable/disable reasons; delegates ceiling math to `allocation_availability.calculate_allocation_availability` | `allotment/services/allocation_availability.py` (already hosts the pure part) |
| 4 | `allotment/views_actions.py:1571-1640` `delete_allotment_item` (`@transaction.atomic`) | Locks parent item, deletes `AllotmentItems`, triggers replan | `allotment/services` |
| 5 | `license/views/item_pivot_report.py` (2400 lines) :679-685, :822-862, :995-1032, :1268, :2377-2390 | Min-balance filter, per-cell qty/CIF accumulation, plan merge, "alloted CIF" re-aggregation (:999-1006), 62 `float(` conversions; :2384 dispatches `update_all_license_balances` | `license/services/item_pivot_service.py` (already exists), selector for the alloted-CIF query |
| 6 | `license/views/license.py:405-470` (retrieve plan summary) | Computes `operational_reconciliation`: `actual_balance_cif = max(gross_cif - actual_boe_cif - actual_allotment_cif, 0)` (:458), `accounted_cif`, `overdrawn_cif` (:467-469), gross CIF from export items (:438) | `license/services/planning_usage_reconciliation.py` (see section 4, SoT #3) |
| 7 | `license/views/license.py:262-282, :985-1010` | `individual_item_cif_override` update + replan marker (atomic + `select_for_update`); SION replan loop (atomic) | `license/services/replan_requests.py` / `sion_rule_engine` (already delegates) |
| 8 | `license/views/license_balance_ledger.py:95-130` | Recalculate action: loops `update_balance_values` per item, then **calls a management-command class** `UpdateBalanceCifCommand().update_license_balance(...)` (:108-112 region), writes `ReconciliationLog`. Not wrapped in `transaction.atomic` (view-level; verified by absence in file grep) | `license/services/balance_snapshot.py` or new `license/services/balance_refresh.py` |
| 9 | `license/views/ledger.py:55-270` | Creates `LicenseLedgerPackageJob` + `bulk_create` items + audit event (:62-64, atomic at :59/:214), retry loop updates item status (:130-134, :268-270) | `license/services/license_ledger_package.py` (exists) / `ledger_package_recovery.py` |
| 10 | `license/views_actions.py:53-180, :185-395` | Licence transfer: `get_or_create` companies, `update_or_create` `LicenseTransferModel`, ownership row saves (:96-99, :139-154, :262-355); only the bulk path is atomic (:240); the single-update path (:53-180) is not | `license/services/dgft_ownership.py` / new transfer service |
| 11 | `license/views/sion_planning_rule.py:288-512` | Versioning of rules (deactivate current + create new + child rows :348-374), profile/action create (:465-511), writes `ActivityLog` explicitly (:301); atomic x5 | `license/services/sion_planning_profile.py` / `sion_rule_engine.py` |
| 12 | `reconciliation/views.py:145-316` (`link`, `merge_boe`, `note`, `recalculate`) | Each write wrapped in `atomic` with `ReconciliationLog` in same txn (:162-168, :198-200, :244-260, :299-304); orchestration is thin but the `ReconciliationLog.objects.create` + before/after snapshots are in the view | `reconciliation/services/` (allocation_service already holds the equivalent for allocations) |
| 13 | `trade/views.py:320-341` `resolve_final_party` | Direct `trade.save(update_fields=[final_party_*])` in view | `trade/services/final_party_classification.py` (exists) |
| 14 | `trade/views.py:405-489` `generate_bill_of_supply` / `generate_purchase_invoice` | Document assembly in view | `trade/services/invoice_document_service.py` |
| 15 | `trade/views_invoice_documents.py:25` | `InvoiceDocumentAuditEvent.objects.create` in view helper | `trade/services/invoice_document_service.py` |
| 16 | `allotment/views.py:321-395` `copy_allotment`, `destroy_allotment` (monkey-patched onto viewset, :370, :395) | `allotment.delete()` (:381) with no `atomic`, no audit, generic `except Exception -> 500` | `allotment/services` |
| 17 | `license/views/active_licenses_report.py:96-120, :166-250, :476-487`; `expiring_licenses_report.py:100-112, :158-242, :467-478` (near-duplicates, 37 Decimal/aggregate lines each) | Per-licence loop calling `license_obj.get_balance_cif` (N queries), norm-level sums of item columns; delegate balance to the engine but total/aggregate in view | selector + report service (`license/services/report_service.py`) |
| 18 | `license/views/active_dfia_report.py:114-247, :322-328` | Delegates balance to `calculate_financial_balance_for_licenses` (:114); computes `cif = qty * unit_price` (:173, :247) and cheese/swp/wpc CIF inline | `license/services/report_service.py` |
| 19 | `license/views/inventory_balance_viewset.py:154-160`, `inventory_balance_report.py:169-174` | Aggregates stored item columns (`available_value`, `debited_quantity` ...) — reads the denormalised item cache | selector |
| 20 | `core/sync/views.py:101-122` | `SyncConflictLog.objects.create`, `SyncPeer ... .update` | `core/sync/service.py` (exists) |
| 21 | `bill_of_entry/views/parse_pdf.py:53`, `license/views/parse_pdf.py:57,109,134` | `CompanyModel/HSCodeModel/NotificationNumber get_or_create` in view | parse service |
| 22 | `license/views/ledger_upload.py:123-260` | Orchestrates upload then calls `core/scripts/ledger.py` bulk writers | upload service |
| 23 | `accounts/views/password.py:109,150`, `user_management.py:73` | `user.save()` | acceptable (non-financial) |

Export views (`bill_of_entry/views_export.py` 901 lines, `allotment/views_export.py` 774,
`license/views/license_purchase_profit_report.py` 763, `item_report.py`, `planned_report.py`) are
workbook-building/IO; they are presentation-heavy but not ORM-writing. They belong in `exporters/` but are
not a financial-integrity risk.

---------------------------------------------------------------------------------------------------

## 2. Business logic in serializers

| Location | Issue |
|---|---|
| `license/serializers/license.py:350-387` `get_billed_no_boe` and `:389-423` `get_billed_no_boe_qty` | Per-object `LicenseTradeLine` aggregate (`trade__direction='SALE', trade__boes__isnull=True`) as the fallback when no batch map is in context. Re-derives billed-CIF-without-BOE using BOE M2M linkage (see SoT #1). Uses `float()` and swallows exceptions (`except Exception: return 0.0`, :388, :423) |
| `license/serializers/license.py:238-437` `get_items_detail`, `get_available_value` (:280), `get_balance_cif_fc` (:424), `get_boe_debited_quantity` (:312-325), `get_planned_quantity` (:334) | Query/calc per row; mostly delegate (`ItemBalanceCalculator.calculate_debited_quantity_for_items` :321, `available_value_calculated`), 18 `float(` |
| `license/serializers/license.py:671-720` `validate`, `:826` `get_get_balance_cif` | Uniqueness queries; balance via model property (delegates) |
| `license/serializers/_license_write.py:337-880` (895 lines) | Nested create/update of export/import items, documents, transfers, purchases; 13 `atomic`/`select_for_update` sites (:337,:353,:461,:747,:835,:865). Writes `LicenseImportItemsModel` value/qty fields (financial). Cohesive but a service-in-serializer |
| `license/serializers/incentive.py` (671 lines, 54 SerializerMethodFields) :149-300 | Arithmetic in serializer methods: `unfilled_target_qty/cif` (:193-196), `effective_unit_price = cif/qty` (:204-206), `remaining_entitlement_qty` (:221-233), `actual_license_balance_cif` reads `obj.license.get_balance_cif` (:252, delegates). Pure Decimal math over plan provenance — good domain candidates |
| `trade/serializers.py:99-165` `get_authoritative_available_cif`, `validate` | Calls `effective_source_row_cif_available` (delegates); ceiling arithmetic `ceiling += self.instance.cif_fc` (:162) |
| `trade/serializers.py:400-470` `create` (atomic :400) | Cumulative qty check with `select_for_update` per item (:432-440) calling `ItemBalanceCalculator.calculate_available_quantity`, then creates `LicenseTrade`, `LicenseTradeLine`, `IncentiveTradeLine`, `LicenseTradePayment` (:451-469), stamps BOE invoice (:483) |
| `trade/serializers.py:501-610` `update` (atomic :501) | Replaces lines/payments, removes BOE links and clears BOE `invoice_no` (:599-603) |
| `bill_of_entry/serializers.py:82-110` `validate` | CIF ceiling via `effective_source_row_cif_available` (delegates); `+ self.instance.cif_fc` add-back (:103) |
| `bill_of_entry/serializers.py:296-370` `create` / `:328-470` `update` | **No atomic.** `update_or_create` BOE header (:306), `allotment.save()` flips `is_boe` (:320, :359, :370), `RowDetails.objects.create` loop (:324), `update_or_create` / delete-missing (:412-460). Multi-row financial write |
| `bill_of_entry/serializers.py:214-240` | Totals/exchange-rate derivation `total/qty` in representation |
| `allotment/serializers.py:317-345` `create`/`update` | `ExchangeRateModel.objects.order_by('-date').first()` default (:332), mapping-only update; `get_planning_target_sion` queries `LicenseItemPlan` (:277); `ListProjectionDecimalField` (:11-25) |
| `license/serializers/ledger.py` | Declared representation-only (docstring :6, :161); no computation found |

---------------------------------------------------------------------------------------------------

## 3. Business logic in models and signals

### 3.1 Models

| Location | What |
|---|---|
| `license/models/core.py:329-349` `get_balance_cif` (property) | Delegates to `calculate_financial_balance` (:348). Fine. `get_total_debit/allotment` (:305-327) delegate. |
| `license/models/core.py:783-860` `get_per_cif` | Restriction budgets from norm class: `credit * 0.03/0.05` etc., `_sum_for_group` aggregates `debited_value`+`allotted_value` columns (:798) — reads stored item cache; norm-specific business rules in a model |
| `license/models/core.py:296-303` `opening_fob`; `:475-520` `get_glass_formers` etc.; ~40 `@cached_property get_*` (:522-780) | Per-norm quantity aggregates (`Sum("qty")` :500, :508) in the model |
| `license/models/core.py:953-958` `LicenseImportItemsModel.save` | Derives `is_restricted` from `condition_type` (side effect, no I/O) |
| `license/models/core.py:961-971` `required_cif` | Hard-coded `>100` qty threshold x `head.unit_rate` |
| `license/models/core.py:973-993` `balance_quantity` | Delegates to `core/scripts/calculate_balance`; **fallback re-derives** `quantity - debited - allotted(un-BOE)` (:984-990) |
| `license/models/core.py:996-1017` `_calculate_item_debit` / `_calculate_item_allotment` | Raw `RowDetails` DEBIT sum (hidden-excluded) and `AllotmentItems` where `allotment__bill_of_entry__isnull=True` — own derivation, not allocation-aware (SoT #4) |
| `license/models/core.py:1019-1100` `balance_cif_fc` family | Delegates to `calculate_financial_balance` with `max(...,0)` CAP clamp (:1086, :1099) and item-attributed path |
| `license/models/core.py:2622` | Post-save `LicenseBalance.objects.get_or_create(license=instance)` |
| `trade/models.py:468-472` `LicenseTrade.save` | Calls `recompute_totals()` after every save (extra writes) |
| `trade/models.py:567-575` `LicenseTradeLine.save` | `amount_inr = compute_amount()` when blank, then `trade.recompute_totals()` |
| `trade/models.py:448-455` | Invoice-number allocation under `atomic` + `select_for_update` (good) |
| `allotment/models/core.py:135-175` `AllotmentModel.save` | Derives `cif_fc`, `unit_value_per_unit`, `cif_inr` (`cif_fc * exchange_rate`) with ROUND_HALF_UP — financial math in `save()` |
| `bill_of_entry/models.py:252, :285-325` | `get_total_inr/fc/quantity/unit_price/exchange_rate` cached_property aggregates |
| `bill_of_entry/models.py:433-440` `RowDetails.save` | **Silently returns** (no save, no exception) if the row is `is_frozen` — callers cannot detect a dropped write (:433-440) |
| `bill_of_entry/models.py:465-559` | `post_save`/`post_delete` receivers on `RowDetails`: `update_stock` (:465), `delete_stock` (:484), `recalc_exchange_rate_on_row_save/delete` (:529,:547), all via `transaction.on_commit` |

### 3.2 Signals doing business writes

| Location | Business write |
|---|---|
| `license/signals.py:205-277` `_update_all_import_items_available_value` | Bulk-`update()`s `LicenseImportItemsModel.available_value` for every item, using `condition_pool.compute_condition_pools` and `min(pool, license_balance)` |
| `license/signals.py:280-333` `update_license_flags` | Reads `license.get_balance_cif` (engine), writes `LicenseBalance.balance_cif` and `LicenseFlags.is_expired/is_null` via queryset `.update()`; `is_null` threshold `< 500` (:316) |
| `license/signals.py:416-570` | Fires `update_license_flags` on `post_save`/`post_delete` of `LicenseExportItemModel`, `LicenseImportItemsModel`, `AllotmentItems` (:517), `RowDetails` (:533), `LicenseTradeLine` (:549; also calls `update_balance_values` :562) |
| `license/signals.py:572-593` | `m2m_changed` on `LicenseTrade.boes` and `post_save` on `InvoiceBOEAllocation` re-run `update_balance_values` for items |
| `license/signals.py:113-198` | Enqueue replan requests on import item / allotment / BOE change |
| `license/signals.py:336-383` `auto_fetch_import_items` | Post-save on licence: auto-links items |
| `allotment/signals.py:8-37` | `AllotmentItems` post_save/post_delete -> `allotment.save(update_fields=['is_allotted'])` |
| `core/cache_signals.py:32-310` | Cache invalidation only (no financial writes); `disable_cache_invalidation` context manager (:385-410) |
| `core/signals_materialized_views.py:51-118` | MV refresh on commit; `AUTO_REFRESH_ENABLED = False` by default (:25), toggled by `enable_auto_refresh` (:120) — **not verified** whether any prod path enables it |
| `core/scripts/calculate_balance.py:165-216` `update_balance_values` | Not a signal but the common sink: writes item `available_quantity, debited/allotted_quantity/value, available_value` (:200-203) then `LicenseFlags.update_or_create(is_null)` at `< 100` (:211). Compares via `float(...) != float(...)` (:184) — comparison only, but is a float on money |

Inconsistent `is_null` thresholds for the same flag: 500 (`license/signals.py:316`,
`validation_service.py:322`, `item_pivot_report.py:2377` doc), 100 (`calculate_balance.py:211`,
`active_licenses_report.py:114`, `expiring_licenses_report.py:106`, `dashboard.py:142`), 200
(`license/views/license.py:219` doc, `active_dfia_report.py:119-124`). Reported, not changed.

---------------------------------------------------------------------------------------------------

## 4. Duplicate calculations (delegates vs re-derives)

Legend: DELEGATES = result comes from the canonical calculator; RE-DERIVES = independent math.

| Component | Verdict | Evidence |
|---|---|---|
| `license/models/core.py:329-349` `get_balance_cif` | DELEGATES | :348 |
| `license/signals.py:280-333` | DELEGATES (writes cache from `get_balance_cif`) | :306 |
| `core/scripts/calculate_balance.py` | Mostly DELEGATES (`get_outstanding_allotment_totals` :59, `calculate_direct_sale_quantity` :60, `calculate_financial_balance` :159) | |
| `license/management/commands/update_balance_cif.py:122-141` | DELEGATES (:132) | |
| `license/services/balance_snapshot.py:157-180` | DELEGATES (all `*_for_licenses` batch calls) | |
| `license/services/license_balance_ledger_builder.py` | DELEGATES for rows/totals (:279-305, :383-515, :663, :814, :951) | |
| Exporters `license_balance_excel.py` (:20, :1672-1673, :1849), `license_balance_pdf.py:645` | DELEGATES (calculator + `CanonicalLedgerService`) | |
| `license/views/dashboard.py:135,250`; `item_pivot_report.py:681,1019`; `item_report.py:376`; `active_dfia_report.py:114`; `license.py:315,332` | DELEGATE (financial batch) | |
| `license/views/active_licenses_report.py:113,197`; `expiring_licenses_report.py:105` | DELEGATE via `get_balance_cif` (per-licence N+1) | |
| `license/services/plan_utilization.py:124` | DELEGATES (item availability) | |
| `license/services/effective_cif_mode.py:75,87` | DELEGATES (`calculate_item_balance`, `get_balance_cif`); explicit "no duplicated formula" docstring | |
| `license/services/condition_pool.py:305-334` | DELEGATES for licence balance/attributed balance | |
| `reconciliation/services/allocation_service.py:68-200` `remaining_for_*` | Separate allocation-remainder arithmetic (invoice/BOE/allotment sides, `_floor0`) — domain-specific, not licence balance; **verify consistency** with calculator's allocation-aware exclusions |
| `reconciliation/services/queries.py:176-200, :330-365` | Read-only comparisons over same tables; mirrors calculator's exclusion condition by hand ("matching `calculate_debit()`'s real exclusion condition") |

### Potential second sources of truth (RE-DERIVE)

1. **Billed-CIF-without-BOE by BOE-link (`trade__boes__isnull=True`)**:
   `license/services/item_usage.py:165-235` (`billed_no_boe_bulk_map`, `billed_no_boe_qty_bulk_map`),
   `license/serializers/license.py:378-420`. The calculator's exclusion was changed to be
   allocation-driven (docs in `reconciliation/services/queries.py:176-190`: "merely having this BOE in the
   trade's `boes` M2M no longer excludes anything"). These item-level figures still key on M2M linkage
   (`boes__isnull`). Drift risk between the item "billed no BOE" column and the licence balance.
2. **`license/services/condition_pool.py:96-130, :168-215`** (pools feed `available_value` via
   `signals.py:205`): own `debited` (raw DEBIT rows, hidden-excluded), `allotted`
   (`allotment__bill_of_entry__isnull=True`, no `min(cif, allocated)` netting) and `traded`
   (all SALE lines, no allocation exclusion). Comment :114 claims to mirror `calculate_trade()` but it
   does not apply the allocation-aware exclusion that `calculate_debit/calculate_trade` do.
3. **`license/views/license.py:430-470` + `license/services/planning_usage_reconciliation.py:81-148, :221-390`**:
   `actual_balance_cif = max(gross_cif - boe - unlinked_allotment, 0)`; no billed term, no allocation
   netting, clamped at 0 (the owner decision of 2026-11-16 says licence-level balances are signed;
   this is a planning pool, so clamp may be intentional — **needs owner confirmation**, flagged not changed).
4. **`license/models/core.py:996-1017, :973-993`** `_calculate_item_debit/_calculate_item_allotment`
   and `balance_quantity` fallback: raw sums (allotment excluded only when `allotment.bill_of_entry` is set).
5. **`license/services/item_pivot_service.py:32-51, :331-335, :441, :539`**: item `balance_qty = total - boe
   - allot - billed`, `balance_cif = max(capacity - used, 0)`, inputs from `item_usage` raw maps (see #1).
6. **`license/services/plan_enforcement.py:25-95, :122-170`**: `_ALLOTTED_FILTER` sums of
   `AllotmentItems.qty/cif_fc` (11 `Sum('cif_fc'|'qty')` hits) for plan residuals.
7. **`license/services/percentage_existing_usage.py:137-205`**, `sion_percentage_capacity.py`,
   `license/services/license_overview_boes.py:52-83`, `license_overview_allotments.py:41-42`,
   `license_overview_summary.py:86-93`: separate BOE/allotment aggregates. `license_overview_*` explicitly
   mirror `get_allotment_rows` ("rather than calling..."), so these are intentional parallel readers; confirm
   parity by test.
8. **`core/materialized_views.py:37-78, :115-153, :194-220`** (SQL): `license_balance_mv.balance_cif =
   total_cif - SUM(rd.cif_inr WHERE DEBIT) - SUM(ai.cif_fc)`. Uses **cif_inr** (not cif_fc) for debits, counts
   all allotment items regardless of BOE linkage, no billed term, no hidden/allocation exclusion. Used by
   `core/tasks_materialized_views.py` and the `refresh_materialized_views` command; I found no `apps/` reader
   outside those files (grep for `license_balance_mv|item_balance_mv|dashboard_stats_mv`), so the practical
   risk is latent — **not verified** for raw-SQL readers outside `backend/apps` (e.g. BI).
9. **`license/services/canonical_ledger_service.py:263-403`**: independent running balance
   (`opening_seed ± amount`, quantize). Zero `Calculator` references in the file. Intentional (Gate 3 spec;
   `ledger_dual_run.py` compares legacy vs new) but it is a second computation of licence balance; reconciled
   to the engine only in `license_balance_ledger_builder.py:663,951` ("engine_balance") for the other builder.
   Confirm a test asserts `closing_balance == calculate_financial_balance`.
10. **LicenseBalance cache** (`LicenseBalance.balance_cif`): writers `license/signals.py:328`,
    `update_balance_cif.py:139-141`, `sync_licenses.py:168`, `core/management/commands/sync_from_ge_server.py:236`,
    `seed_browser_2509.py:279,479`. `license_balance_ledger.py:98-108` documents that reconciliation allocation
    writes never refresh it. Readers of `.balance_cif` (e.g. `license/serializers/license.py:516`
    `balance_cif` field, `inventory_balance_*` item columns) can disagree with live engine.
11. **Item cache columns** (`available_quantity/value`, `debited_*`, `allotted_*` on
    `LicenseImportItemsModel`), written by `calculate_balance.update_balance_values` and signals; read by
    `inventory_balance_viewset.py:154-160`, `inventory_balance_report.py`, `allotment/views_actions.py`
    candidate filter `available_quantity__gt=0` (:~312). Denormalised derived values used as eligibility gate.
12. `license/services/license_profit.py:348-397`, `purchase_profit_report.py:89-95, :400-412`: own SALE/PURCHASE
    sums for profit (not balance). Intentionally separate; module docs state the double-count avoidance.
13. `license/views/active_licenses_report.py:166-170`, `expiring_licenses_report.py:158-161`,
    `active_dfia_report.py:152-154`: export-item `Sum(cif_fc)` = ORIGINAL CIF re-derived in views
    (equals `calculate_credit`, same formula, duplicated).
14. `license/models/core.py:296-303` `opening_fob` and `_calculate_license_credit` vs `calculate_credit`
    (`balance_calculator.py:92`): same export-item sum, duplicated in model.

Float on money paths (Decimal invariant): `item_pivot_report.py` (62 `float(`),
`license/serializers/license.py` (18), `core/scripts/calculate_balance.py` (14); `balance_calculator.py` and
`canonical_ledger_service.py` have 0.

---------------------------------------------------------------------------------------------------

## 5. Financial write safety

Legend: SVC = in a service module; ATOMIC = `transaction.atomic`; LOCK = `select_for_update`;
AUDIT = entity-level audit row (`ReconciliationLog`, `TradePairAudit`, `*AuditEvent`, `*RecoveryAudit`);
"-" = no.

### Ranked by risk (non-atomic or unlocked, multi-row, financial first)

| Rank | Path (file:line) | Rows written | SVC | ATOMIC | LOCK | AUDIT |
|---|---|---|---|---|---|---|
| 1 | BOE create/update — `bill_of_entry/serializers.py:296-470` via `MasterViewSet.perform_create/update` (`core/views/master_view.py:136,154`) | `BillOfEntryModel`, `RowDetails` (create/update/delete-missing :324, :412-460), `AllotmentModel.is_boe` (:320,:359,:370) | No (serializer) | **No** | **No** | - (ActivityLog middleware only) |
| 2 | Allotment delete — `allotment/views.py:374-395` (`allotment.delete()` :381) | `AllotmentModel` + cascaded `AllotmentItems`, fires `update_license_flags` per item via signals | No (view) | **No** | **No** | - |
| 3 | TradeLine / TradePayment generic CRUD — `trade/views.py:665,694` (`MasterViewSet`) | `LicenseTradeLine` (CIF/qty), each save calls `trade.recompute_totals` (`trade/models.py:567-575`) + signals recompute licence flags | No | **No** | **No** | - |
| 4 | Generic LicenseTrade/Allotment/LicenseDetails viewset destroy — `master_view.py:187` | cascades over financial children | No | **No** | **No** | - |
| 5 | `RowDetails.save` silent skip for frozen rows — `bill_of_entry/models.py:433-440` | Dropped write with no error | No | n/a | n/a | - |
| 6 | Recalculate balances — `license/views/license_balance_ledger.py:95-130` | item cache columns (`update_balance_values` loop), `LicenseBalance` (via command class), `LicenseFlags`, `ReconciliationLog` | No (view, calls management command object) | **No** | **No** | `ReconciliationLog` (:114) but written outside txn |
| 7 | `update_balance_values` — `core/scripts/calculate_balance.py:165-216` | item value/qty columns, `LicenseFlags.update_or_create` | Script | No (called from `on_commit` jobs `bill_of_entry/models.py:465-495`, signals, view) | No | - |
| 8 | Signal cascade `update_license_flags` — `license/signals.py:280-333` | `LicenseBalance.balance_cif`, `LicenseFlags`, all items' `available_value` (:205-277) | No (signal) | Runs inside whatever txn the trigger has; `.update()` bypasses `AuditModel.modified_*` | No | - |
| 9 | Ledger upload — `core/scripts/ledger.py:124-327` | `bulk_create/bulk_update` of `LicenseImportItemsModel` (qty/cif :152), `BillOfEntryModel` (:207), `RowDetails` (:326-327); each helper has its own `atomic` (:134,:206,:306) but `create_object` (:221-290) sequence is **not** one transaction | Script | per-step only | No | - |
| 10 | Licence transfer single-update — `license/views_actions.py:53-180` | `LicenseOwnership`, `CompanyModel`, `LicenseTransferModel` (:96-154) | No | **No** (bulk path atomic :240) | No | - |
| 11 | `BOE merge_boe` — `bill_of_entry/services/boe_service.py:203-318` | moves `RowDetails` via `.update(bill_of_entry=target)` (:288), deletes source BOE (:297) | SVC | Yes (:244) | verify (no `select_for_update` in file) | Not seen in `merge_boe`; `ReconciliationLog` only in hide/restore (:406,:459) |
| 12 | `boe_service.resolve_dispute` — `:179-196` | `RowDetails.is_dispute` bulk update | SVC | **No** | No | - |
| 13 | `boe_service.update_invoice_no` — `:321-334`; `update_product_name_for_boe` (:17-47), `bulk_update_product_names` (:55-78) | BOE header fields | SVC | No | No | - |
| 14 | `trade_service.link_trades` — `trade/services/trade_service.py:127-184` | `LicenseTrade.linked_trade` x4 `.update()` on two trades | SVC | **No** (no `atomic` between :127-184) | No | - |
| 15 | Allotment allocate — `allotment/views_actions.py:1071-1570` | `AllotmentItems` create/merge, replan, item cache refresh | **No (view)** | Yes (:1071; inner savepoints :1454,:1459) | Yes (allotment :1098, item :1192, plan lines :1230) | Only middleware `ActivityLog`; replan reason recorded |
| 16 | Allotment item delete — `views_actions.py:1571-1640` | `AllotmentItems` delete | No (view) | Yes | Yes (:1603) | - |
| 17 | Allotment service `AllocationService` — `allotment/services/allocation_service.py:152-272` | `AllotmentItems` create/update/delete | SVC | Yes (:152,:205,:226) | No | - (and unused by the view, see §1 #1) |
| 18 | Invoice<->BOE / BOE<->Allotment allocations, external invoice link — `reconciliation/services/allocation_service.py:224-745` | `InvoiceBOEAllocation`, `BOEAllotmentAllocation`, `ExternalInvoiceLink` (create/edit=supersede/reverse) | SVC | Yes (24 atomic sites) | Yes (:260-261, :331-340, :398, :471-472, :532-541, :593, :683, :726) | `ReconciliationLog` in same txn |
| 19 | Trade copy/unpair/sync — `trade/services/trade_service.py:210-455` | `LicenseTrade`, `LicenseTradeLine`, `IncentiveTradeLine`, `LicenseTradePayment`, deletes | SVC | Yes (:219,:332,:388) | Yes (:220,:333-338,:389) | `TradePairAudit` (:305,:366) |
| 20 | Trade create/update via serializer — `trade/serializers.py:400,501` | Trade + lines + payments + BOE invoice stamp | Serializer | Yes | Yes for item rows on direct SALE (:436) | - (ActivityLog only) |
| 21 | BOE hide/restore — `boe_service.py:377-470` (`_apply_hide/_apply_restore`) | BOE `invoice_no` (hide marker), hidden state | SVC | Yes (:402,:455) | No | `ReconciliationLog` (:406,:459) |
| 22 | Reconciliation views `link/merge/note/recalculate` — `reconciliation/views.py:162,198,244,299` | trade<->BOE link, BOE merge, notes | Partly | Yes | No | `ReconciliationLog` in txn |
| 23 | Licence write serializer — `license/serializers/_license_write.py:337-880` | `LicenseExportItemModel`, `LicenseImportItemsModel` qty/CIF, docs, transfers, purchases | Serializer | Yes | Yes (licence + children) | - |
| 24 | Replan / plan lines — `license/services/plan_enforcement.py:255-273`, `canonical_planning_service.py` (9 atomic), `replan_requests.py:77,92`, `license/tasks.py:136-278` | `LicenseItemPlan` (planned qty/CIF; not a balance bucket) | SVC/tasks | Yes | Yes | replan request rows |
| 25 | Ledger package jobs — `license/views/ledger.py:55-270`, `license/tasks.py:414-540`, `ledger_package_recovery.py:116-168` | package job/items | SVC/tasks | Yes | Yes | `LicensePackageAuditEvent`, recovery audit |
| 26 | Invoice documents — `trade/services/invoice_document_service.py`, `trade/views_invoice_documents.py:25` | `InvoiceDocumentAuditEvent` | SVC (+view write) | Yes (1) | - | Yes |
| 27 | Sale classification — `trade/services/sale_classification_review.py:39-53` | `SaleClassificationDecision` (append-only, `trade/models.py:~487`) | SVC | Yes | Yes | Immutable decision row |
| 28 | `update_balance_cif` command — `license/management/commands/update_balance_cif.py:90-141` | `LicenseBalance` | Command | Yes (:90) | No | - |
| 29 | Other management commands writing `LicenseBalance` — `sync_licenses.py:168`, `sync_from_ge_server.py:236`, `seed_browser_2509.py:279,479` | cache rows | Command | Mostly per-licence/none | No | - |

Notes:
- Audit coverage: entity audit rows exist only for reconciliation allocations, BOE hide/restore, trade
  pairing, sale classification, ledger packages, invoice documents and SION rule versioning
  (`license/views/sion_planning_rule.py:301` writes `ActivityLog` explicitly). There is **no entity
  audit** for: BOE RowDetails edits, AllotmentItems create/delete, `LicenseImportItems` value edits,
  `LicenseTradeLine` edits, `LicenseBalance`, ledger-upload writes. `allotment/models/audit_event.py`
  defines `AuditEvent` but I found no writer outside `allotment/models/__init__.py` (grep).
- `.update()` / `bulk_*` usage bypasses `AuditModel` auto-fields and signals: `signals.py:328,263`,
  `trade_service.py:156-184,354-361`, `boe_service.py:191,288`, `core/scripts/ledger.py:151-152,207,326-327`.
- Concurrency: only the allocation/trade/reconciliation services lock. Signal-driven recomputation
  (`update_license_flags`, `update_balance_values`) reads-then-writes without locks; concurrent BOE and
  allotment writes on the same licence can produce a last-writer-wins cache value (the live engine remains
  correct because it recomputes).
- `on_commit` hooks (`bill_of_entry/models.py:465-495`) run with errors swallowed in `_update_balance_sync`
  (:451-462), so a failed refresh logs but does not surface.

---------------------------------------------------------------------------------------------------

## 6. Existing layering

### 6.1 Apps with `services/`

| App | Modules | Verdict |
|---|---|---|
| `license` | ~70 modules in `services/` (34,038 total service LOC repo-wide). Largest: `balance_calculator.py` 2160, `exporters/license_balance_excel.py` 2006, `sion_planning_execution.py` 1744, `license_balance_ledger_builder.py` 1683, `canonical_planning_service.py` 1449, `canonical_ledger_service.py` 1367, `exporters/license_balance_pdf.py` 1311, `item_pivot_service.py` 819 | Broad; several god-modules (balance calculator = two classes + many batch variants; planning execution; excel exporter). Mixed concerns: calculation, query, persistence and rendering in the same files (e.g. `canonical_planning_service` contains locks + writes + math). Has a `domain/` package, but only `transaction_semantics.py` |
| `reconciliation` | `allocation_service.py` 757, `queries.py` 485, `boe_link_reconciler.py`, `warning_service.py` | Cohesive: write service (atomic + lock + log) separate from read queries |
| `trade` | `trade_service.py` 492, `final_party_classification`, `invoice_document_service`, `invoice_secure_links`, `sale_classification_review` | Cohesive; `trade_service` mixes pure helpers (`parse_date_strict`, `build_trade_summary`) with writes |
| `bill_of_entry` | `boe_service.py` 676 (product-name, dispute, merge, invoice no, hide/restore) | Single grab-bag module; BOE create/update is *not* here (serializer) |
| `allotment` | `allocation_service.py` (orphan), `allocation_availability.py`, `paired_allocation_max.py`, `filter_service.py`, `validation_service.py` | Pure-ish helpers exist, but the main write path is in the view (§1 #1) |
| `core` | `core/sync/service.py`, `mds_write`, `scripts/` (`calculate_balance.py`, `ledger.py`, `calculation.py`, `license_script.py`) | `core/scripts/*` acts as an untyped service layer (and calculation sink for the license domain) — wrong ownership: license/BOE business code living in `core` |
| `accounts`, `tasks` | none | n/a |

No `selectors.py` modules anywhere; read queries live in views, serializers and `*_service.py`.

### 6.2 Pure-function candidates for a `domain/` layer (no ORM needed)

- `license/services/balance_calculator.py`: `quantize_2dp` (:39), `is_over_utilised` (:1349), `available_for_allocation` (:1354) (static, already ORM-free); the combination step of `calculate_balance`/`_calculate_financial_balance` (:1360-1415, :1593-1663) once components are passed in.
- `license/services/planning_tolerances.py` (`effective_planning_balance_cif`), `license/services/effective_cif_mode.py` (`EffectiveCifProjection` assembly, :55-110).
- `allotment/services/allocation_availability.py` (`calculate_allocation_availability`), `allotment/services/paired_allocation_max.py`, `allotment/views_actions.py:64-130` clamp logic.
- `reconciliation/services/allocation_service.py`: `_floor0` (:50), `_validate_non_negative` (:201), `_validate_fits` (:209), snapshot builders (:418, :613, :746).
- `license/services/split_by_percentage_requirement_calculator.py`, `percentage_group_solver.py`, `split_allocation.py`, `sion_percentage_capacity.py`, `planning_usage_reconciliation.reconcile_split_allocation` (:31), `apply_operational_cif_ceiling` (:150).
- `license/serializers/incentive.py:149-300` arithmetic (unfilled target, effective unit price, remaining entitlement) — extract as pure functions.
- `item_pivot_service._add_balance_fields/_unit_price` (:32-51).
- `trade/models.py` `LicenseTradeLine.compute_amount` (QTY vs CIF_INR mode) and `AllotmentModel.save` field derivation (`allotment/models/core.py:135-175`).
- `license/domain/transaction_semantics.py` is the only existing domain module (enum + dict semantics).
- `canonical_ledger_service` running-balance loop (:286-347) once transactions are normalised.

---------------------------------------------------------------------------------------------------

## Not verified / out of scope

- Whether any deployment enables `enable_auto_refresh()` for the materialized views, or has external readers of `*_mv`.
- Exact `select_for_update` coverage in `boe_service.merge_boe` beyond the `atomic` at :244.
- Frontend call sites of the BOE create/update API (to confirm no client-side batching masks non-atomicity).
- No tests were run (read-only audit).
