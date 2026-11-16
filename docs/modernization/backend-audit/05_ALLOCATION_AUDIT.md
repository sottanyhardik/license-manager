# Backend Audit 05 — Allocation Logic Inventory (pre-design for a canonical allocation service)

Scope: every allocation path across `backend/apps/*` (allotment, reconciliation, bill_of_entry, trade,
license planning). **Read-only audit, 2026-11-16.** No code changed, no tests run, no DB touched.
Paths are relative to `backend/apps/`. Evidence = `file:line` from reads in this session.
Canonical rule: `.claude/rules/business-rules.md`. Companion: `02_LOGIC_PLACEMENT_AND_FINANCIAL_SAFETY.md`.

> In-flux warning: `allotment/views.py` (destroy/copy) and a new `allotment/services/audit_service.py`
> were uncommitted edits by another task during this audit (git status). Their line refs may shift.
> Doc 02 §5 rank 2 ("allotment delete non-atomic, no audit") is being superseded by that work:
> destroy is now `transaction.atomic` + `record_allotment_deleted` (`allotment/views.py:376-385`).

Terminology used below
- **Allotment allocation** = writing `AllotmentItems` (licence import row → allotment). Reserves "ALLOTMENT CIF".
- **Ledger allocation** = `BOEAllotmentAllocation` (BOE row ↔ allotment item) and `InvoiceBOEAllocation` /
  `ExternalInvoiceLink` (invoice ↔ BOE row). Releases ALLOTMENT CIF / BILLED-without-BOE.
- **Planning allocation** = generating `LicenseItemPlan` targets (licence CIF → plan lines). Not a balance bucket.

---------------------------------------------------------------------------------------------------

## 1. Inventory

### 1(a) Allocation of licence import items to allotments

| # | Implementation | Entry point (URL name / caller) | Reads | Writes | Atomic / lock |
|---|---|---|---|---|---|
| A1 | `allotment/views_actions.py:1072-1568` `_allocate_items_atomic` (public wrapper `allocate_items` :1051-1069 maps any exception → 500) | `POST allotment-actions/{pk}/allocate-items/` (`allotment-actions-allocate-items`); FE `pages/AllotmentAction.tsx:570` (one allocation per request) | `AllotmentModel` (locked), `SUM(AllotmentItems.qty/cif_fc)` all rows of allotment :1101-1106, `LicenseImportItemsModel.available_quantity` (stored cache) :1341, `effective_source_row_cif_available` :1374, `LicenseItemPlan` + `plan_line_status_for` :1230-1270 | `AllotmentItems` create :1460 or merge `existing.qty/cif_fc/cif_inr +=` :1439; item cache via `update_balance_values` :1523; replan request + inline `replan_license_task.run` :1550-1561 | `@transaction.atomic` :1071; `select_for_update` allotment :1098, import item :1192, plan lines :1230; per-row savepoints; `set_rollback(True)` on any row error :1538 (all-or-nothing) |
| A2 | `allotment/views_actions.py:230-454` `available_licenses` (ACTUAL candidates) | `GET allotment-actions/{pk}/available-licenses/` (`allotment-actions-available-licenses`); FE `AllotmentAction.tsx:441` | Allotment requirement from prefetched details :266-275; `available_quantity__gt=0` stored filter :323; `available_value_bulk_map` :501/:549; `effective_source_row_cif_available` :603; `billed_no_boe_*_bulk_map`; `_position_payload` | none | read-only |
| A3 | `allotment/views_actions.py:685-1050` `_available_licenses_plan_mode` (PLAN candidates, `debit_based_on=PLAN`) | same URL | `LicenseItemPlan` + `plan_line_status_for_many` :865; `available_value_bulk_map` :933 (**not** `effective_source_row_cif_available`, :1009) | none | read-only |
| A4 | `allotment/views_actions.py:64-130` `_position_payload` → `allotment/services/allocation_availability.py:27-57` → `allotment/services/paired_allocation_max.py:23-73` | A2/A3 rows | actual/plan/requirement positions | none | pure |
| A5 | `allotment/views_actions.py:169-228` `allocation_initialization` + `_active_target_plan_lines` :132-167 | `GET allotment-actions/{pk}/allocation-initialization/`; FE `AllotmentAction.tsx:329` | active `LicenseItemPlan` for target, `resolve_plan_sion`, `plan_line_status_for_many` | none | read-only |
| A6 | `allotment/services/allocation_service.py:24-307` `AllocationService` (`calculate_max_allocation` :30, `validate_allocation_amount` :112, `allocate_item` :153, `deallocate_item` :206, `update_allocation` :227) | **No production caller** (only re-export `allotment/services/__init__.py:10`; grep) | `ItemBalanceCalculator.calculate_available_quantity` (dynamic) :72, `calculate_item_balance` :73, `LicenseValidationService.validate_allocation` | `AllotmentItems` create/update/delete | atomic :152/:205/:226; **no lock** |
| A7 | `allotment/services/validation_service.py` `AllotmentValidationService` (`validate_allocation_within_limits` :76, `get_remaining_allocation_capacity` :192, `check_allotment_fully_allocated` :163 with 0.99 threshold) | **No production caller** (grep) | `AllotmentItems(is_boe=False)` sums, `balanced_quantity` | none | n/a |
| A8 | `license/services/balance_calculator.py:2116-2160` `ItemBalanceCalculator.calculate_available_value_for_allocation` | **No caller** (grep) | dynamic qty + `calculate_item_balance` | none | pure (unquantized) |
| A9 | `license/services/validation_service.py:120-231` `LicenseValidationService.validate_sufficient_balance/quantity/restriction_limit/validate_allocation` | only A6 + tests | `remaining_for_condition` (% pool), `max(get_balance_cif,0)`, dynamic qty | none | n/a |
| A10 | Frontend dead helpers `frontend/src/services/api/allotmentApi.ts:40,54,65,147` (`allocate-item`, `update-allocation`, `delete-allocation`, `convert-to-boe`) | none of these backend actions exist (`url_path` grep of `allotment/*.py`); no FE importer uses them | — | — | — |
| P1 | Planning allocation primitives: `license/services/planning_allocation.py:31` `allocate_step`; copies `e126_plan.py:200` / `e132_plan.py:244` `_allocate_step` (byte-identical logic); `canonical_planning_service.py:1305` `_allocate_one` (quantizes, ROUND_DOWN price); `split_allocation.py:66` `SplitAllocationService` (e5); `database_driven_sion_planner.py:396`; `split_by_percentage_planner.py:326` | `replan_license_task` (`license/tasks.py:162`), plan views | licence balance (clamped), SION norms | `LicenseItemPlan` | canonical service: atomic + locks (doc 02 §5 rank 24) |

### 1(b) Entitlement reservation (outstanding ALLOTMENT CIF)

| # | Implementation | Formula | Used by |
|---|---|---|---|
| R1 | `license/services/balance_calculator.py:970-1000` `calculate_allotment` via `_annotate_allotment_contribution` :~700-835, `get_allotment_rows` :845 | per `AllotmentItems` (all types): `contributed = 0 if Exists(BOE.allotment = parent) else max(cif_fc − min(cif_fc, Σ active current BOEAllotmentAllocation.allocated_cif_fc), 0)` | licence balance (customs + financial), ledgers |
| R2 | `balance_calculator.py:895-927` `get_outstanding_allotment_totals` (+ `_for_items` :928) | same annotation, **filtered `allotment__type='AT'`** | item available qty (stored + dynamic), `update_balance_values` |
| R3 | `license/services/plan_enforcement.py:25-28,98-139` `plan_line_status_for` | `used = Σ AllotmentItems.cif_fc/qty WHERE allotment.bill_of_entry IS NULL AND type='AT' AND basis='PLAN' AND target=line.item_name AND item ∈ plan group`; residual `max(planned − used, 0)` — **no BOEAllotmentAllocation netting** | PLAN caps (A1, A3, A5) |
| R4 | Allotment-level requirement: `allotment/models/core.py:162-208` (`required_value` = qty × unit HALF_UP; `alloted_quantity`/`allotted_value`/`balanced_quantity` all `@cached_property` sums over **all** details) ; A1 re-aggregates under lock :1101 | `required − Σ` | A1, A2, serializer |
| R5 | `reconciliation/services/allocation_service.py:173-198` `remaining_for_allotment_item` | `max(item.{qty,cif_fc,cif_inr} − Σ active current BOEAllotmentAllocation, 0)` — ignores M2M BOE link | `create/edit_boe_allotment_allocation` |
| R6 | Re-derivations listed in doc 02 §4 (#2 `condition_pool` allotted, #4 `models` `_calculate_item_allotment`, #6 plan_enforcement, #8 MV) — still present, not repeated here | raw `allotment__bill_of_entry__isnull=True` sums | `available_value` cache, % pools |

### 1(c) CIF calculations during allocation

| Concern | Where | Rule |
|---|---|---|
| Canonical line CIF | `views_actions.py:1186-1187` | `canonical_cif = (qty × allotment.unit_value_per_unit).quantize(0.01, ROUND_UP)` |
| Pair tolerance (d89d9d91, 2026-10-08) | `views_actions.py:1321-1332` | reject if `unit_price>0 and |cif_fc − canonical| > 0.01 and not final_settlement` → `ALLOCATION_PAIR_MISMATCH`. Unit price 0 ⇒ no pair check (legacy) |
| Final settlement ($20 buffer) | `views_actions.py:1169-1172` (pre-check, decremented requirement) and `:1303-1320` (pair check, uses cached props); `paired_allocation_max.py:7,38-57` | last whole-unit qty may carry CIF up to residual + 20.00, or ±0.01 of residual |
| Max pair suggestion | `paired_allocation_max.py:58-73` | step-floored qty, `cif = qty × price` ROUND_UP, step down while `cif > ceiling`; step 1.000 in A4, 0.001 in A6 |
| Allotment header | `allotment/models/core.py:135-160` `AllotmentModel.save` | cif_fc = unit × qty HALF_UP; or unit = cif/qty **ROUND_UP 3dp**; cif_inr = cif_fc × exchange_rate HALF_UP |
| INR on allotment items | `views_actions.py:1160` | `cif_inr` taken from request, default 0, **never derived**; UI payload (`AllotmentAction.tsx:571-582`) sends no `cif_inr` ⇒ every UI-created `AllotmentItems.cif_inr = 0` |
| BOE rows | `bill_of_entry/serializers.py:61-77` | cif_fc/cif_inr HALF_UP 2dp, qty HALF_UP 3dp |
| Ledger allocations | `reconciliation/services/allocation_service.py:201-221` | three independent components (qty, cif_fc, cif_inr) each ≤ remaining; no unit-price pairing, no tolerance |
| Auto-match tolerance | `boe_link_reconciler.py:~102-118`; `settings.py:581-582` | `RECONCILIATION_CIF_TOLERANCE=1.00`, `QTY=1.000`; amounts = per-component `min()` |
| Planning | `planning_allocation.py:31-49` (raw `balance/qty`, unquantized); `canonical_planning_service.py:1332-1350` (2dp, price ROUND_DOWN) | |

### 1(d) Allocation validation

| Check | A1 (live write) | A2/A3 (candidates) | A6/A9 (orphan) | Ledger (R5 etc.) |
|---|---|---|---|---|
| Pair mismatch | ±0.01 / settlement :1321 | n/a (UI uses `basis_options` pair) | none | none |
| Quantity cap | stored `available_quantity` (int-truncated float cache) :1341 | stored `available_quantity__gt=0` | dynamic `calculate_available_quantity` (3dp Decimal) | `remaining_for_*` qty |
| CIF cap | `effective_source_row_cif_available` :1374 → **legacy mode = `max(licence.get_balance_cif,0)`** (`effective_cif_mode.py:96-101`); individual mode = `calculate_item_balance` | ACTUAL: same as A1 :603; PLAN: `available_value_bulk_map` (% pool aware) :1009 | `calculate_item_balance`; A9 pool / licence balance | `remaining_for_*` cif |
| Requirement cap | locked aggregate :1101-1110 + cached props :1390, :1404 | prefetched sums :266-275 | `balanced_quantity` + 20 buffer | n/a |
| Plan cap | `plan_line_status_for` under lock :1266-1300 | `plan_line_status_for_many` | none | n/a |
| Restriction % / `available_value` | **not enforced** in legacy mode (see D1) | PLAN rows only | A9 `remaining_for_condition` | n/a |
| Item-name / norm | `actual_item_id ∈ license_item.items` :1199-1210 (only if supplied); plan group membership `group_ids_of` :1238-1253; target match :1254 | `items__id__in` filter | none | same-licence check only |
| Expiry | none (`test_allows_allocation_against_an_expired_license`) | `license_status` filter | none | none |
| Duplicate identity | merge into existing row :1422-1450; DB unique constraints `allotment/models/core.py:338-347` | — | none | app-level "one active current pair" check under lock :~262; **no DB unique constraint** |
| BOE BOE-row CIF cap | — | — | — | `bill_of_entry/serializers.py:80-110` only in INDIVIDUAL mode; trades `trade/api/serializers.py:125-167` only INDIVIDUAL mode |

### 1(e) Lifecycle transitions

| Transition | Implementation | Atomic / lock | Audit |
|---|---|---|---|
| Allot (create/merge) | A1 | yes / yes | middleware ActivityLog only; `AllotmentItems.allocation_basis/search_mode` as facts |
| Deallocate item | `views_actions.py:1570-1636` `delete_allotment_item` (`DELETE allotment-actions/{pk}/delete-item/{id}/`, FE `AllotmentAction.tsx:651`) | yes / locks import item :1603 (**not** allotment) | none (hard delete); `ProtectedError` if any `BOEAllotmentAllocation` (PROTECT, `reconciliation/models.py:~374-378`) → caught → 400 |
| Delete allotment | `allotment/views.py:376-385` (in flux) | atomic, no lock | `AuditEvent` via `audit_service.record_allotment_deleted` (new); ProtectedError → 500 |
| Copy allotment | `allotment/views.py:323-370` | no | none; copies header only |
| Allotment ↔ BOE link (coarse) | `bill_of_entry/serializers.py:296-375` `boe.allotment.set(...)`, `allotment.is_boe` flag | **no atomic** (doc 02 §5 rank 1) | none |
| BOE ↔ allotment item (fine) | `reconciliation/services/allocation_service.py:437-631` create/edit(supersede)/reverse | yes / yes | `ReconciliationLog` same txn |
| Invoice ↔ BOE | same module :224-436; auto via `boe_link_reconciler.reconcile_trade_boe_links` :71 | yes / yes | `ReconciliationLog` |
| External invoice mark | same module :656-745 | yes / yes | `ReconciliationLog` |
| Release / reactivate | fields only: `AllotmentItems.status/released_quantity/reactivated_quantity` (`allotment/models/core.py:285-330`), `AllocationVersion` model; **no writer anywhere** (grep); `backfill_allocation_status` sets CREATED only | — | — |
| Trade unpair/delete | `trade/services/trade_service.py:318-378` | yes / yes | `TradePairAudit`; trade lines with `InvoiceBOEAllocation` → ProtectedError (PROTECT) |
| Recovery | none for allotment allocations; reconciliation uses reverse+recreate; `check_allocation_health` / `backfill_boe_allocations` commands | — | — |

**Production writers of `BOEAllotmentAllocation`: none.** `create_boe_allotment_allocation` has no API,
view, task or command caller (grep: only tests). No `reconciliation` endpoint writes ledger allocations
(`reconciliation/api/views.py` actions: link/merge-boe/note/recalculate + read queries). `InvoiceBOEAllocation`
is written only by `boe_link_reconciler` via `backfill_boe_allocations --apply`. Consequently in production
R1's partial-netting branch is inert and ALLOTMENT CIF is effectively "full cif_fc unless the parent allotment
has any BOE in the M2M" (unverified against prod data — **not verified**).

---------------------------------------------------------------------------------------------------

## 2. Duplication matrix

Legend: **D** delegates to canonical engine/helper · **R** re-derives · **—** absent.

| Concept | A1 write | A2 ACTUAL cand. | A3 PLAN cand. | A6/A7/A8 orphan | Trade SALE create | BOE row | Ledger svc | Engine |
|---|---|---|---|---|---|---|---|---|
| Item available qty | R (stored cache, int-truncated, float) | R (stored) | R (stored, `row_max`) | D dynamic | D dynamic (`trade/api/serializers.py:438`) | — | R5 | `calculate_available_quantity` |
| Item/row CIF cap | D `effective_source_row_cif_available` | D same | **R** `available_value_bulk_map` | R `calculate_item_balance` | D (INDIVIDUAL only) | D (INDIVIDUAL only) | R5 | `effective_source_row_cif_available` |
| ALLOTMENT CIF outstanding | — | — | — | — | — | — | R5 | R1 |
| Plan used | R3 | R3 | R3 | — | — | — | — | R3 is the only one |
| Requirement remaining | R (locked agg + cached props, mixed) | R (prefetch) | R (prefetch) | R (**double-subtract bug**, D4) | — | — | — | `AllotmentModel` props |
| Max pair | A4 D | A4 D | A4 D | D paired_max (step 0.001) / A8 R | — | — | — | `calculate_paired_allocation_max` |
| Tolerance | 0.01 + $20 | via A4 | via A4 | $20 buffer only | none | none | none / 1.00 auto | — |

### Concrete divergences (from reading the code; none executed)

| ID | Divergence | Inputs → different numbers |
|---|---|---|
| D1 | `%`-condition pool not enforced on write in legacy mode; PLAN candidate grid does enforce it | Licence override NULL, credit 100 000, financial balance 80 000, item `condition_type='10%'` pool remaining 2 000, allotment requirement 5 000 @ unit 10. ACTUAL candidate max CIF = 5 000 (licence 80 000); A1 write cap = 80 000 → 500 kg/5 000 accepted. PLAN candidate (`:1009`) shows actual CIF 2 000, `row_max_allotment_cif` ≤ 2 000. `views_actions.py:1352-1373` comment claims the pool is applied; `effective_cif_mode.py:96-101` (hotfix 7bcbbf38) discards `legacy_available`. **Owner decision.** |
| D2 | Stored vs dynamic available qty | Item `quantity=1000.500`, no debits: stored `available_quantity=1000` (`calculate_balance.py:98`, `round_down(...,0)`), dynamic `1000.500`. Allotment of 1000.5 kg rejected (`ALLOTMENT_QTY_EXCEEDS_ACTUAL`); SALE trade of 1000.5 kg accepted. Also stale cache: any write path that skips `update_balance_values` leaves A1 gating on stale data. |
| D3 | ARO (`type='AR'`) allotments | `core/constants.py:22` `ARO="AR"`, but `calculate_balance.py:56-57` filters `type='ARO'` (never matches, field max_length 2) and R2/R3 filter `type='AT'`. An AR allotment item 100 kg/$1 000: licence ALLOTMENT CIF +1 000 (R1, no type filter), item available qty unchanged (stored + dynamic), plan used unchanged. |
| D4 | `AllotmentValidationService` double-subtracts (orphan) | required 100 kg, allocated 40 kg: `balanced_quantity=60`; `get_remaining_allocation_capacity` returns `60−40=20` (:229); `validate_allocation_within_limits(+30)` compares `70 > 60` → rejects a valid 30 kg (:108-114). Also filters `is_boe=False` while `balanced_quantity` sums all rows. |
| D5 | BOE-linked allotment item: engine vs ledger remaining | AllotmentItem cif 1 000, parent allotment in a BOE's M2M, no `BOEAllotmentAllocation`: R1 contributes 0; R3 plan used 0 (capacity restored); R5 `remaining_for_allotment_item` = 1 000 (still matchable). |
| D6 | Plan residual ignores partial BOE netting | Same item with `BOEAllotmentAllocation` of 600 and no M2M link: R1 contributes 400; R3 still counts 1 000 used. |
| D7 | `cif_inr` on UI allotment items is 0 | UI-created item cif_fc 1 000, cif_inr 0 (`:1160`). `create_boe_allotment_allocation(..., cif_inr=83 000)` fails `_validate_fits` (remaining cif_inr 0); only `cif_inr=0` succeeds, so INR side of the ledger is structurally empty. |
| D8 | **Suspected defect** — ACTUAL merge can absorb a PLAN row | `existing_query` for ACTUAL filters only `plan_line__isnull=True` (`:1434`), but A1 never sets `plan_line` on PLAN rows (`:1446`, `:1460`). Sequence: PLAN 10 kg target T on item I, then ACTUAL 5 kg on I in the same allotment → `.first()` (Meta ordering `qty`) returns the PLAN row; it becomes 15 kg, `allocation_basis='ACTUAL'`, `planning_target_item=None` (`:1439-1446`). R3 used for T drops by 10 (plan capacity revived, audit fact rewritten). If an ACTUAL row also exists, unique constraint → IntegrityError → 500. No test covers PLAN-then-ACTUAL (test_10 is ACTUAL→ACTUAL). Needs a characterization test to confirm. |
| D9 | Batch requirement checks use two sources | Batch of two rows (50 + 50 kg of remaining 100): pre-check (`:1169`) uses decremented requirement (second row is final settlement); pair check (`:1303-1320`) and `:1390/:1404` use `@cached_property` pre-batch values (final_settlement false). Effect: $20 buffer unavailable for the last row of a multi-row batch. Conservative, UI never batches. |
| D10 | Allotment header unit-price drift | `cif_fc=1000`, `required_quantity=3000`, unit 0: first save sets unit `0.334` (ROUND_UP 3dp), keeps cif 1000; `required_value=1002.00`; next save rewrites `cif_fc=1002.00` (`models/core.py:147-153`). Requirement cap and canonical CIF both inflate by 0.2 %. |
| D11 | Availability bulk vs property ordering | Item with no licence and `cif_fc=0.01`: property returns 0 (`license/models/items.py:250-255`), bulk resolver returns 0.01 (`condition_pool.py:258-262`). Edge only. |
| D12 | Max formula variants | A4 step 1.000, A6 step 0.001, A8 unquantized fractional (`balance_calculator.py:2140-2158`). E.g. unit 8.821, CIF ceiling 2066.75: A4 → 234 kg / 2064.12; A8 → 234.299… kg / 2066.75. |

---------------------------------------------------------------------------------------------------

## 3. Test coverage map

| Implementation | Tests (file :: notable functions) | Gaps |
|---|---|---|
| A1 write | `allotment/tests/test_module3_allocation_scenarios.py` (26: test_01..23, `test_12b_concurrent_final_confirms_serialize_on_locked_allotment`, `test_14_invalid_batch_rolls_back_valid_sibling`, `test_16_pair_mismatch_rejected`, `test_final_whole_kg_uses_twenty_dollar_settlement_buffer`, `test_23_cif_requirement_cap_blocks_later_debit`); `test_allocate_items_cif_validation.py` (6, live vs stale balance); `test_allocate_items_plan_line_balance.py` (14); `test_allocate_items_group_plan_cap.py` (4); `test_allocate_items_e1_group_plan_cap.py` (4); `test_allocate_items_expiry_check.py` (1) | D1 (%-pool, legacy mode), D2 fractional qty, D3 AR type, D8 PLAN→ACTUAL merge, D9 batch settlement, `cif_inr` |
| A2/A3 candidates | `test_available_licenses_filters.py` (12); `test_available_licenses_plan_mode.py` (13, incl. query-count contract); `core/tests/test_openapi_schema.py` | ACTUAL vs PLAN `actual_cif` parity (D1) |
| A4 availability/max | `test_module3_allocation_scenarios.py::test_18_max_intersects_cif_and_quantity_caps`, settlement tests; `license/tests/test_seed_browser_2509_command.py` | `calculate_allocation_availability` has no direct test |
| A5 init | `test_allocation_initialization.py` (5) | — |
| A6/A7/A8 orphans | none (A9 via `license/tests/test_validation_service.py`, `test_negative_balance.py`) | all — delete-or-adopt decision first |
| R1/R2 engine | `license/tests/test_balance_calculator.py` (`test_calculate_allotment_with_items`, `test_boe_linked_allotment_quantity_excluded_even_when_not_formally_allocated`, `test_partially_allocated_allotment_only_leaves_remainder_quantity`, …); `test_negative_balance.py`; `reconciliation/tests/test_allocation_service.py` | type `AR` |
| R3 plan residual | `test_allocate_items_plan_line_balance.py`, `test_allocate_items_group_plan_cap.py` | BOE-linked/partially allocated PLAN items (D5/D6) |
| Ledger service | `reconciliation/tests/test_allocation_service.py` (24: split/many-to-many, over-allocation, cross-licence, duplicate, reversal never deletes, edit supersedes); `test_external_invoice_service.py`; `test_boe_link_reconciler.py`; `test_backfill_boe_allocations_command.py`; `test_check_allocation_health_command.py` | concurrent create race; `cif_inr=0` allotment items (D7) |
| Item cache writer | `license/tests/test_balance_cif_single_source.py` | int truncation, ARO filter |
| Effective CIF mode | `license/tests/test_effective_cif_mode.py` (6) | — |
| Delete item / destroy | `test_module3…::test_11_delete_releases`, `test_allocate_items_plan_line_balance.py::test_deleting_*`; `test_destroy_allotment_atomic.py`, `test_destroy_allotment_audit.py` (new, uncommitted) | ProtectedError path when ledger rows exist |
| Trade unpair | `trade/tests/test_unpair_and_delete.py` | — |

---------------------------------------------------------------------------------------------------

## 4. Dependencies and blast radius for consolidation

| Surface | Callers / consumers | Frontend (URL name) | Concurrency / atomicity today |
|---|---|---|---|
| A1 `_allocate_items_atomic` | view only | `allotment-actions-allocate-items` ← `pages/AllotmentAction.tsx:570` | atomic; locks allotment → import item → plan lines (fixed order per row); inline replan locks licence (`replan_requests`) |
| A2/A3/A5 | view only | `allotment-actions-available-licenses`, `allotment-actions-allocation-initialization` ← `AllotmentAction.tsx:329,441` | read-only; response shape (`basis_options`, `allocation_limit`, `row_max_*`, `code`) is an API contract |
| `delete_allotment_item` | view only | `allotment-actions-delete-item` ← `AllotmentAction.tsx:651` | atomic; locks import item only (allocation on another item of same allotment can interleave — requirement cap still safe because A1 re-reads under allotment lock) |
| `AllotmentModel` derived props | `AllotmentSerializer`, A1/A2, exports, PDFs | allotment list/detail | `@cached_property` — stale within an instance |
| `update_balance_values` | A1, delete, BOE `on_commit` jobs, signals, recalc view, `license_balance_ledger.py:95-130` | indirect (all grids reading `available_quantity`) | no lock; last-writer-wins (doc 02 §5) |
| `effective_source_row_cif_available` | A1, A2, `bill_of_entry/serializers.py:51,96`, `trade/api/serializers.py:114,155`, `license_overview_items.py` | BOE/trade forms (`authoritative_available_cif`) | pure + engine reads |
| `plan_enforcement` | A1/A2/A3/A5, planning views, `canonical_planning_service` | plan grids | read |
| `reconciliation/services/allocation_service.py` | `boe_link_reconciler.py:56,92`, `license_balance_ledger_builder.py:267,1029,1173`, commands; tests | none write; ledger pages read via builder | 24 atomic sites, locks on both sides, `ReconciliationLog` in txn |
| Engine R1/R2 | everything balance-related (doc 02 §4) | all balance UIs | read |
| Signals | `allotment/signals.py:8-37`, `license/signals.py:517,572-593`, `allotment/models/core.py:445-495` | — | `on_commit`, errors swallowed |

Consolidation must preserve: lock order (allotment → import item → plan line), all-or-nothing batch
semantics, error `code` values consumed by `getAllocationErrorMessage` in the FE, inline replan before commit,
and the PROTECT FKs on ledger rows.

---------------------------------------------------------------------------------------------------

## 5. Recommended canonical-service boundary (sketch only — not implemented)

Proposed module: `allotment/services/allocation/` (writes) + reuse `reconciliation/services/allocation_service.py`
as-is for ledger allocations (already the best-shaped code: atomic, locked, audited). Engine
(`LicenseBalanceCalculator`) remains the only source of balance math; the service composes, never re-derives.

```
# Read side (pure / selector, no writes)
allocation_position(allotment_id, source_item_id, basis, planning_target_item_id=None)
    -> Position{actual_qty, actual_cif, plan_qty, plan_cif, requirement_qty, requirement_cif,
                unit_price, max_pair: PairedAllocationMaximum, enabled, reason_code}
candidate_positions(allotment_id, basis, filters, page) -> Page[Position]   # A2/A3 backend
requirement_remaining(allotment_id, *, lock=False) -> (qty, cif)            # single R4 implementation
validate_allocation(position, qty, cif_fc) -> list[AllocationError(code, message, max_qty, max_cif)]

# Write side (atomic, locked, audited)
allocate(allotment_id, lines: list[AllocationRequest], actor) -> AllocationResult  # replaces A1 body
deallocate(allotment_item_id, actor, reason) -> DeallocationResult                 # replaces delete_allotment_item
# Ledger side: keep create/edit/reverse_* in reconciliation.allocation_service; expose them via one facade
link_boe_to_allotment_item(row_details_id, allotment_item_id, qty, cif_fc, cif_inr, actor)
link_invoice_to_boe(trade_line_id, row_details_id, qty, cif_fc, cif_inr, actor)
reverse_link(kind, allocation_id, actor, reason)
```

### Migration order

1. Characterization tests (below) against current behaviour, including the suspected defects (pin as-is, mark xfail where owner wants a change).
2. Extract `requirement_remaining` + `validate_allocation` from A1 as pure functions; A1 calls them (no behaviour change).
3. Extract `allocate`/`deallocate` bodies into the service; views become thin (same URLs, same response).
4. Move A2/A3 candidate assembly to `candidate_positions`; unify ACTUAL/PLAN `actual_cif` source **only after D1 decision**.
5. Delete orphans A6/A7/A8 and FE dead helpers A10 (after decision) — 0 production callers today.
6. Owner-gated: decide R3 netting (D5/D6), item-qty source (D2), AR type (D3), INR derivation (D7); then wire a BOE→allotment ledger writer if wanted.

### Characterization tests needed first

- A1: PLAN-then-ACTUAL on same item/allotment (D8) — assert basis/target/plan residual after.
- A1: legacy-mode `%` item where pool < licence balance (D1) — pin accepted amount; same fixture through A2 and A3 to pin `effective_cif_limit`.
- A1 vs trade SALE: fractional `quantity` (D2).
- AR-type allotment: licence ALLOTMENT CIF vs item `available_quantity` vs plan residual (D3).
- BOE M2M-linked and partially `BOEAllotmentAllocation`-netted items: R1 vs R3 vs R5 (D5/D6).
- Multi-row batch reaching final settlement (D9); `AllotmentModel.save` cif/unit round-trip (D10).
- `delete_allotment_item` when a (reversed) `BOEAllotmentAllocation` exists → current 400 + ProtectedError.
- Response-shape snapshot tests for `available-licenses` (ACTUAL + PLAN) and `allocate-items` error codes.
- Run existing: `allotment/tests/test_*allocat*`, `test_available_licenses_*`, `license/tests/test_balance_*`, `reconciliation/tests/*`.

### Owner decisions required (flagged, not changed)

| # | Question |
|---|---|
| O1 | D1: must the `%`-condition pool (`available_value_calculated`) cap allotment writes in legacy (override NULL/False) mode? Code comment says yes; hotfix 7bcbbf38 makes it licence-wide. |
| O2 | D2: authoritative item qty for allocation gates — stored integer-truncated cache or dynamic Decimal engine? Trade and allotment currently disagree. |
| O3 | D3: should `AR` allotments reduce item available qty / plan residual (they already reduce licence ALLOTMENT CIF)? Fix of the `'ARO'` vs `'AR'` literal changes numbers. |
| O4 | D5/D6: should plan residual (R3) follow the engine's netting (M2M-zero + partial `BOEAllotmentAllocation`), or keep "BOE-linked ⇒ plan capacity released"? |
| O5 | D7: derive `AllotmentItems.cif_inr` (from allotment exchange rate) or keep INR out of allotment-side ledger? |
| O6 | Is a production writer for `BOEAllotmentAllocation` intended (UI/command), or is the M2M link the permanent mechanism? |
| O7 | Release/reactivate (`status`, `released_quantity`, `AllocationVersion`) — build or drop the dormant schema? |
| O8 | Delete orphans A6/A7/A8 and FE helpers A10? |
| O9 | D8: confirm it is a defect (expected: separate ACTUAL row) before any fix — it is a BUSINESS-RULE-adjacent ledger-identity change. |
| O10 | D10: should `AllotmentModel.save` stop rewriting `cif_fc` after deriving `unit_value_per_unit`? Changes requirement caps of existing allotments on next save. |

## Not verified

- Production data shape (whether any `BOEAllotmentAllocation`/`InvoiceBOEAllocation` rows exist; count of AR allotments; PLAN+ACTUAL rows on same item).
- D8 and D9 are derived from reading only; no test executed.
- `calculate_item_attributed_balances_for_items` parity with `calculate_item_attributed_balance` (assumed per docstring).
- No tests, gates or linters were run (read-only audit).
