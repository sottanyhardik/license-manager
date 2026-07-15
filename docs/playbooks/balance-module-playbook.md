# Change Playbook: Balance & Planning Module

> **For developers making any change to balance, allotment, or BOE behavior.**  
> Follow this checklist before and after every change.

---

## Before You Change Anything

### 1. Read These Files (in this order)
```
1. docs/claude/balance-context.md          ← start here, 5 min
2. docs/business-rules/balance-calculations.md  ← formula reference
3. docs/business-rules/planning-rules.md   ← if touching planning
4. backend/apps/license/services/balance_service.py  ← THE formula
5. backend/apps/allotment/services/allotment_service.py  ← if touching allotment
6. backend/apps/bill_of_entry/models.py    ← if touching BOE signals
```

### 2. Understand These Invariants (do not break)

| Invariant | Where enforced |
|---|---|
| `balance_cif >= 0` | `max(_DEC_0, raw_balance)` in balance_service.py |
| `planned_quantity` only decremented with select_for_update | `_adjust_plan()` in allotment_service.py |
| Allotment exits formula when linked to BOE | `allotment__bill_of_entry__isnull=True` filter |
| Balance recompute is async (never in-request) | `recompute_license_balance_task.delay()` everywhere |
| No double-deduction in Scenario B | Mutually exclusive allotment/debit components |
| tracker created BEFORE apply_async | Reports views: uuid pre-generation |

### 3. Run Baseline Tests
```bash
cd license-manager
.venv/bin/pytest backend/tests/balance/ -v --tb=short
.venv/bin/pytest backend/tests/integration/test_license_workflows.py -v --tb=short
.venv/bin/pytest backend/tests/allotment/ -v --tb=short
.venv/bin/pytest backend/tests/bill_of_entry/ -v --tb=short
```

Expected: All pass. Record the count before your change.

---

## Making the Change

### Common Scenarios

#### A. Adding a new component to the balance formula
1. Add `_compute_new_component(license_id)` function in `balance_service.py`
2. Add it to `recompute_license_balance()`: `new = _compute_new_component(license_id)`
3. Update the formula: `raw_balance = credit - debit - allotment - trade - new`
4. Update `docs/business-rules/balance-calculations.md` with the new component
5. Update `docs/business-rules/business-rule-index.md` with new rule
6. Add test in `tests/balance/test_balance_system.py`

#### B. Adding a new allotment side effect
1. Add the logic inside `transaction.atomic()` in the relevant service function
2. If it modifies another model: check for circular import
3. Test that the side effect is atomic with the allotment save
4. Update `docs/modules/allotment.md` service section

#### C. Changing when balance recompute is triggered
1. Ensure `transaction.on_commit()` wraps the dispatch (not inline in transaction)
2. Verify the license_id is correctly resolved (not item_id)
3. Add a test verifying the dispatch fires with the correct argument
4. Update `docs/business-rules/balance-calculations.md` triggers section

#### D. Modifying a BOE signal
1. Never remove `_dispatch_balance_recompute(license_id)` from post_save/post_delete
2. Test that the signal fires in `tests/bill_of_entry/test_boe.py`
3. Ensure `transaction.on_commit()` wraps the dispatch

---

## After Making the Change

### 1. Run Full Test Suite
```bash
.venv/bin/pytest backend/tests/ -q --tb=short
# Expected: 161+ passed, 0 failed
```

### 2. Run Linter
```bash
.venv/bin/python -m ruff check backend/ --config backend/pyproject.toml
# Expected: All checks passed!
```

### 3. Manual QA Scenarios

Run these manually against the local dev server:

#### Scenario A: Basic balance flow
1. Create a license with one export item (cif_fc=10000)
2. Add one import item (quantity=100)
3. Verify balance_cif = 10000
4. Create an allotment (qty=20, cif_fc=2000)
5. Verify balance_cif = 8000 (after Celery or direct recompute)
6. Verify allotted_quantity = 20 on the import item

#### Scenario B: BOE from allotment (no double-deduction)
1. Using the allotment from scenario A
2. Create a BOE linked to that allotment, add a RowDetails (cif_fc=2000)
3. Verify balance_cif is still 8000 (allotment exits, debit enters — same value)
4. Verify debited_quantity = 20 on import item
5. Verify allotted_quantity = 0 (allotment consumed)

#### Scenario C: Planning enforcement
1. Create a LicenseItemPlan (planned_quantity=50, planned_cif_fc=5000)
2. Try to create an allotment with qty=60 → should fail with ValidationError
3. Create allotment with qty=30 → should succeed
4. Verify plan.planned_quantity = 20 (50 - 30)
5. Delete the allotment → verify plan.planned_quantity = 50 (restored)

#### Scenario D: Balance never goes negative
1. Create a scenario where debit+allotment > credit
2. Verify balance_cif = 0 (not negative)
3. Verify is_null = True

### 4. Update Documentation

After any behavior change:
- [ ] `docs/business-rules/balance-calculations.md` — update affected formula
- [ ] `docs/business-rules/business-rule-index.md` — update or add rule
- [ ] `docs/modules/license.md` (or allotment.md/bill-of-entry.md) — update section
- [ ] `docs/claude/balance-context.md` — update if a critical pattern changed
- [ ] `docs/knowledge-graph/services.md` — update service inventory

### 5. Commit Checklist
```
[ ] All tests pass (pytest)
[ ] Lint clean (ruff)
[ ] Relevant docs updated
[ ] Commit message describes the business rule change, not just the code change
```

---

## Known Pitfalls (Do Not Repeat)

| Pitfall | What happened | Correct behavior |
|---|---|---|
| Passing item_id as license_id | `_dispatch` called `task.delay(item_id)` where task expected `license_id` | `_dispatch` resolves license_id via `LicenseImportItemsModel.objects.filter(pk__in=item_ids).values_list("license_id")` |
| Importing legacy script from BOE signals | `from apps.core.scripts.calculate_balance import update_balance_values` → ImportError silently swallowed | Use `_dispatch_balance_recompute(license_id)` |
| Using `_safe_get_model` | Returns None on any error, silently zeros balance components | Direct lazy imports in each `_compute_*` function |
| Comparing to string 'DEBIT' | `transaction_type='DEBIT'` → never matches | DB value is single-char `'D'` |
| `q2(pct)` before division | Rounds pct to 2dp before computing → wrong for 3dp rates | `Decimal(str(pct))` preserves 3dp |
| Creating tracker after apply_async | Worker can call `_mark_started()` before tracker row exists | Pre-generate UUID, INSERT tracker, THEN apply_async |
