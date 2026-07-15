# Change Playbook: Allotment & BOE Modules

> **Developer checklist before/after any allotment or BOE change.**

---

## Before Changing Allotment Code

### Files to Read (in order)
```
1. docs/claude/balance-context.md          ← invariants
2. docs/workflows/allotment-boe-workflow.md ← complete flow
3. backend/apps/allotment/services/allotment_service.py
4. backend/apps/allotment/models.py
5. backend/apps/license/models/license.py   ← LicenseItemPlan model
```

### Invariants to Preserve
1. `_dispatch` must resolve `license_id` from import item IDs (not pass item IDs directly)
2. `_validate_plan_availability` must use `select_for_update()`
3. `_adjust_plan` must use `F()` expression (atomic)
4. Plan adjustment and AllotmentItems save must be in same `transaction.atomic()`
5. Balance dispatch via `on_commit` only (never inline)

### Regression Tests to Run
```bash
.venv/bin/pytest backend/tests/allotment/ -v
.venv/bin/pytest backend/tests/balance/test_balance_system.py::test_create_allotment_decrements_plan -v
.venv/bin/pytest backend/tests/balance/test_balance_system.py::test_delete_allotment_restores_plan -v
.venv/bin/pytest backend/tests/balance/test_balance_system.py::test_create_allotment_rejects_over_plan -v
.venv/bin/pytest backend/tests/balance/test_balance_system.py::test_dispatch_resolves_license_id_from_item_id -v
```

### Common Mistakes
- ❌ Calling `recompute_license_balance_task.delay(item_id)` — must be `license_id`
- ❌ Calling `_adjust_plan` outside `transaction.atomic()` — lost atomicity
- ❌ Collecting item_ids AFTER delete (CASCADE removes them) — collect BEFORE delete
- ❌ Not collecting `cif_fc` value for plan restoration on delete

---

## Before Changing BOE Code

### Files to Read (in order)
```
1. docs/claude/balance-context.md
2. docs/workflows/allotment-boe-workflow.md  ← Scenario A vs B
3. backend/apps/bill_of_entry/models.py      ← signals at bottom
4. backend/apps/bill_of_entry/services/boe_service.py
5. backend/apps/bill_of_entry/serializers.py ← allotment M2M in create/update
```

### Invariants to Preserve
1. `update_stock` and `delete_stock` signals MUST dispatch `_dispatch_balance_recompute(license_id)`
2. `boe.allotment.set()` MUST be called in serializer create/update (enables Scenario B)
3. Row operations MUST scope by `bill_of_entry_id=boe_id` (IDOR prevention)
4. Frozen row check MUST be done before any edit/delete
5. Exchange rate signals MUST remain (BOE.exchange_rate auto-calculation)

### Regression Tests to Run
```bash
.venv/bin/pytest backend/tests/bill_of_entry/ -v
.venv/bin/pytest backend/tests/balance/test_balance_system.py::test_boe_row_save_dispatches_correct_license_id -v
.venv/bin/pytest backend/tests/balance/test_balance_system.py::test_boe_scenario_b_from_allotment -v
.venv/bin/pytest backend/tests/integration/test_license_workflows.py::test_frozen_boe_row_update_rejected -v
```

---

## After Any Change

### Manual QA Scenarios

#### 1. Allotment → Balance updates
```
1. Create license (export item cif_fc=50000)
2. Add import item (qty=1000)
3. Create allotment (qty=100, cif_fc=5000)
4. Wait ~2s for Celery → verify balance_cif = 45000
5. Verify import item allotted_quantity = 100
6. Verify import item available_quantity = 900
```

#### 2. Delete allotment → plan restored
```
1. Create LicenseItemPlan (planned_qty=500, planned_cif_fc=5000)
2. Create allotment (qty=100, cif_fc=1000)
3. Verify plan.planned_qty = 400
4. Delete allotment
5. Verify plan.planned_qty = 500 (restored)
6. Verify balance_cif returned to pre-allotment value
```

#### 3. BOE Scenario B (no double-deduction)
```
1. Create allotment (cif_fc=3000)
2. Verify balance reduces by 3000
3. Create BOE linked to this allotment (RowDetails cif_fc=3000)
4. Verify balance UNCHANGED from step 2 (allotment replaced by debit)
5. Verify allotted_qty = 0, debited_qty = allotment_qty
```

#### 4. Frozen row protection
```
1. Create BOE with frozen row (is_frozen=True)
2. Try to PATCH the row → expect 403
3. Try to DELETE the row → expect 403
```

### Documentation Updates After Change
- [ ] `docs/workflows/allotment-boe-workflow.md` — update affected workflow steps
- [ ] `docs/business-rules/business-rule-index.md` — add/modify rules
- [ ] `docs/test-coverage-map.md` — mark gaps as covered
- [ ] `docs/state-machines/entities.md` — update state diagrams if states change
