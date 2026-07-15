# Test Coverage Map

> **Business Rule → Test mapping. Identifies gaps in test coverage.**  
> Status: ✅ Covered | ⚠️ Partial | ❌ Missing | ⏳ Required by pending BD
> Last updated: 2026-07-15 — BD-001, BD-002, BD-003 approved, tests required.

---

## License Balance Business Rules

| Rule | Business Rule | Test File | Test Function | Status |
|---|---|---|---|---|
| LIC-002 | balance = credit - debit - allotment - trade (⏳ BD-003: no floor) | test_license_workflows.py | test_license_balance_after_boe_row_creation | ✅ |
| LIC-003 | ~~balance >= 0~~ **SUPERSEDED** → balance may be negative (BD-003) | test_license_workflows.py | test_over_allotment_rejected | ⚠️ Must update when BD-003 implemented |
| LIC-004 | is_null = True when 0 <= balance < 500 (⏳ BD-003 update required) | test_balance_system.py | test_is_null_flag_set_when_balance_below_threshold | ⚠️ Must update when BD-003 implemented |
| LIC-016 | ⏳ BD-003: is_negative_balance = True when balance < 0 | — | — | ❌ Required, not yet written |
| LIC-017 | ⏳ BD-002: group_import_items_by_name sums correctly | — | — | ❌ Required, not yet written |
| LIC-018 | ⏳ BD-002: grouping preserves raw rows unchanged | — | — | ❌ Required, not yet written |
| LIC-005 | is_expired = True when past expiry | test_balance_system.py | test_is_expired_flag_set_correctly | ✅ |
| LIC-006 | Credit = SUM(export items cif_fc) | test_balance_system.py | test_balance_formula_all_components | ✅ |
| LIC-007 | Debit = SUM(BOE RowDetails cif_fc) | test_balance_system.py | test_boe_scenario_a_no_allotment | ✅ |
| LIC-008 | Allotment component = pending only | test_balance_system.py | test_allotment_with_boe_excluded_from_allotment_component | ✅ |
| LIC-009 | Trade = SALE direction only | test_balance_system.py | test_balance_formula_all_components | ✅ |
| LIC-011 | Item available_qty = total - debited - allotted | test_balance_system.py | test_item_level_balance_formula | ✅ |
| LIC-011 | Item available_qty never negative | test_balance_system.py | test_item_level_balance_never_negative | ✅ |
| LIC-012 | Item-level updated in same transaction | test_license_workflows.py | autouse _patch_item_level_balances | ⚠️ Patched out in most tests |
| LIC-013 | Import items unique per (license, serial_number) | test_license_workflows.py | test_license_number_unique_constraint_declared | ⚠️ Partial (license_number, not serial_number) |
| LIC-014 | Balance recompute triggered by import item CRUD | test_license.py | test_import_item_create_dispatches_balance_task | ✅ |

---

## Planning Business Rules

| Rule | Business Rule | Test File | Test Function | Status |
|---|---|---|---|---|
| PLAN-001 | No restriction when no plan exists | test_balance_system.py | test_create_allotment_allowed_without_plan | ✅ |
| PLAN-002 | Create allotment decrements plan | test_balance_system.py | test_create_allotment_decrements_plan | ✅ |
| PLAN-003 | Delete allotment restores plan | test_balance_system.py | test_delete_allotment_restores_plan, test_delete_allotment_plan_restore_is_exact | ✅ |
| PLAN-004 | Cannot allot more than planned_quantity | test_balance_system.py | test_create_allotment_rejects_over_plan | ✅ |
| PLAN-005 | Cannot allot more than planned_cif_fc | — | — | ❌ Missing |
| PLAN-006 | Plan adjustment uses F() expression | test_balance_system.py | test_validate_plan_uses_select_for_update | ⚠️ Tests select_for_update, not F() |
| PLAN-007 | Plan validation uses select_for_update | test_balance_system.py | test_validate_plan_uses_select_for_update | ✅ |
| PLAN-008 | update_allotment does NOT adjust plan | — | — | ❌ Missing |

---

## Allotment Business Rules

| Rule | Business Rule | Test File | Test Function | Status |
|---|---|---|---|---|
| ALLOT-001 | AT and TR types only | test_allotment.py | test_allotment_type_choices | ✅ |
| ALLOT-002 | Balance recompute after commit | test_allotment.py | test_create_allotment_dispatches_balance_task | ✅ |
| ALLOT-003 | Dispatch resolves license_id from item_id | test_allotment.py | test_create_allotment_dispatches_balance_task | ✅ |
| ALLOT-004 | Cascade delete AllotmentItems | — | — | ❌ Missing |
| ALLOT-005 | unique_together (item, allotment) | — | — | ❌ Missing |
| ALLOT-006 | alloted_quantity property correct | — | — | ❌ Missing |
| ALLOT-007 | balanced_quantity never negative | — | — | ❌ Missing |

---

## BOE Business Rules

| Rule | Business Rule | Test File | Test Function | Status |
|---|---|---|---|---|
| BOE-001 | RowDetails unique per (boe, sr_number, type) | — | — | ❌ Missing |
| BOE-002 | Frozen rows cannot be edited | test_boe.py | TestFrozenRowUpdateRejected, TestFrozenRowDeleteRejected | ✅ |
| BOE-003 | Balance recomputed after RowDetails save | test_boe.py | TestCreateBoeDispatchesBalanceTask | ✅ |
| BOE-003b | Correct license_id dispatched (not item_id) | test_balance_system.py | test_boe_row_save_dispatches_correct_license_id | ✅ |
| BOE-004 | Balance recomputed after RowDetails delete | test_balance_system.py | test_boe_row_delete_dispatches_recompute | ✅ |
| BOE-009 | IDOR prevention: row scoped to BOE | — | — | ❌ Missing |
| BOE-010 | IDOR prevention: update/delete scoped to BOE | — | — | ❌ Missing |

---

## Trade Business Rules

| Rule | Business Rule | Test File | Test Function | Status |
|---|---|---|---|---|
| TRADE-001 | 3dp pct precision (CIF_INR mode) | test_trade.py | test_pct_3dp_precision_cif | ✅ |
| TRADE-001b | 3dp pct precision (FOB_INR mode) | test_trade.py | test_pct_3dp_precision_fob | ✅ |
| TRADE-001c | 3dp rate_pct precision | test_trade.py | test_rate_pct_3dp_precision | ✅ |
| TRADE-002 | amount_inr always recomputed on save | test_trade.py | test_billing_mode_cif_inr | ✅ |
| TRADE-003 | Invoice number format | test_license_workflows.py | test_invoice_number_format | ✅ |
| TRADE-004 | Invoice number race-safe | test_license_workflows.py | test_invoice_number_uniqueness_enforced_by_model | ⚠️ Partial |
| TRADE-011 | PartnerTradeNotFound defined before use | — | — | ❌ Missing (was a NameError bug) |

---

## Authentication Rules

| Rule | Business Rule | Test File | Test Function | Status |
|---|---|---|---|---|
| AUTH-001 | is_active checked before is_superuser | test_permissions.py | test_all_permission_classes_block_unauthenticated | ⚠️ Partial |
| AUTH-002 | Login rate throttled | — | — | ❌ Missing |
| AUTH-003 | Logout blacklists token | test_auth.py | TestLogout::test_logout_blacklists_token | ✅ |
| AUTH-004 | JWT HS256 | — | — | ❌ Missing (config test) |
| AUTH-005 | is_superuser in UserSerializer | — | — | ❌ Missing (regression test) |
| AUTH-006 | RBAC via Django Groups | test_auth.py | TestRBACPermissions | ✅ |

---

## Required Tests from Approved Business Decisions

### BD-001 (Allotment Validation) — Must be written before implementation

| # | Test | Purpose |
|---|---|---|
| 1 | `test_allotment_rejected_when_exceeds_license_cif_balance` | BD-001: total CIF > balance_cif → ValidationError |
| 2 | `test_allotment_rejected_when_item_qty_exceeds_available_qty` | BD-001: qty > available_quantity → ValidationError |
| 3 | `test_allotment_allowed_when_within_balance` | BD-001: positive case (passes) |
| 4 | `test_allotment_concurrent_requests_safe` | BD-001: two simultaneous allotments — only one succeeds |
| 5 | `test_allotment_partial_rejection_no_partial_writes` | BD-001: atomic — all-or-nothing |

### BD-002 (Grouped Import Items) — Must be written before implementation

| # | Test | Purpose |
|---|---|---|
| 6 | `test_group_import_items_by_name_sums_correctly` | BD-002: three "Dietary Fiber" rows sum to correct total |
| 7 | `test_group_preserves_raw_rows_unchanged` | BD-002: raw rows unmodified by grouping |
| 8 | `test_group_handles_items_without_item_name` | BD-002: edge case — no ItemNameModel linked |
| 9 | `test_group_key_is_item_name_id` | BD-002: verifies grouping key is `ItemNameModel.id` |

### BD-003 (Negative Balance) — Must be written before implementation

| # | Test | Purpose |
|---|---|---|
| 10 | `test_balance_can_be_negative` | BD-003: BOE > credit → balance is negative (no floor) |
| 11 | `test_is_negative_balance_flag_set` | BD-003: balance < 0 → is_negative_balance=True |
| 12 | `test_is_null_not_set_when_negative` | BD-003: negative balance doesn't set is_null |
| 13 | `test_item_available_quantity_can_be_negative` | BD-003: item level also allows negative |
| 14 | `test_boe_creation_never_rejected_for_balance` | BD-003: BOE always allowed regardless of balance |
| 15 | `test_activity_log_created_on_negative_balance` | BD-003: ActivityLog entry created |
| 16 | Update `test_balance_never_negative` | **Must change**: was LIC-003, now superseded by BD-003 |

---

## Missing Tests (Pre-existing Gaps, Prioritized)

### HIGH Priority
1. ❌ PLAN-005: `cif_fc > planned_cif_fc` raises ValidationError
2. ❌ PLAN-008: `update_allotment` does not call `_adjust_plan`
3. ❌ BOE-009/010: IDOR prevention on row operations
4. ❌ TRADE-011: `PartnerTradeNotFound` defined before `link_trades()` (regression test)
5. ❌ AUTH-005: `is_superuser` in UserSerializer response (regression)

### MEDIUM Priority
6. ❌ ALLOT-004: Cascade delete behavior
7. ❌ BOE-001: RowDetails unique constraint
8. ❌ AUTH-001: Deactivated superuser blocked
9. ❌ TRADE-004: Invoice number concurrent requests test

### LOW Priority
10. ❌ ALLOT-006/007: AllotmentModel computed properties
11. ❌ AUTH-002: Login throttle rate
