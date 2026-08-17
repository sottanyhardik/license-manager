# FORCE ALL BUG REPORT

## Critical Issue: Wrong Scope for Deletion

### Current Behavior (WRONG)

In `plan_enforcement.py:171`:
```python
if delete_existing:
    LicenseItemPlan.objects.filter(license=license_obj).delete()
```

This deletes **ALL LicenseItemPlan rows for the entire license**, regardless of SION.

### Problem Scenario

License 100 has plans from multiple SIONs:
```
LicenseItemPlan rows:
  [1] SION: E1, Item: Rubber
  [2] SION: E1, Item: Steel
  [3] SION: A3627, Item: RUTILE - A3627
```

User clicks "Force All" for **SION A3627** only.

Current behavior:
```
DELETE FROM license_licenseitemplan WHERE license_id=100
→ Deletes rows [1], [2], [3] ❌ WRONG

E1 rows are deleted even though user only requested A3627!
```

Expected behavior:
```
DELETE FROM license_licenseitemplan 
WHERE license_id=100 
  AND planning_rule_id IN (
    SELECT id FROM sion_planning_rule WHERE sion_id=17
  )
→ Deletes only row [3] ✅ CORRECT

E1 rows remain untouched
```

## Architecture Issue

LicenseItemPlan model:
```python
class LicenseItemPlan(AuditModel):
    license = ForeignKey(LicenseDetailsModel)  ← Indexed
    planning_rule = ForeignKey(SionPlanningRule)  ← Contains SION reference
    # NO direct SION field ❌
```

To delete by SION scope, must join through planning_rule:
```python
planning_rule__sion_id = sion_id
```

## Required Fix

### 1. Update save_plan_lines_for_license signature

```python
def save_plan_lines_for_license(
    license_obj, 
    lines, 
    *, 
    delete_existing=True,
    sion_id=None,  # ← NEW: Scope deletion to SION
) -> list:
```

### 2. Update deletion logic

```python
if delete_existing:
    query = LicenseItemPlan.objects.filter(license=license_obj)
    
    # Scope by SION if provided
    if sion_id is not None:
        query = query.filter(planning_rule__sion_id=sion_id)
    
    query.delete()
```

### 3. Update call site in canonical_planning_service.py

```python
# Line 334-336
created = save_plan_lines_for_license(
    license_obj, 
    plan_lines, 
    delete_existing=True,
    sion_id=sion.pk,  # ← PASS SION
)
```

### 4. Verify caller provides SION

In sion_planning_execution.py:
```python
# Line 637-640
result = CanonicalPlanningService.build_canonical_plan(
    license_id=license_obj.pk,
    norm_class=sion.norm_class,
    items=canonical_lines,
    force_replan=mode == PLAN_MODE_ALL,
    sion_id=sion.pk,  # ← ADD THIS
)
```

## Test Case: Demonstrate the Bug

### Before Fix

```python
def test_force_all_deletes_wrong_sion_rows():
    # Create E1 and A3627 plans for same license
    license = LicenseDetailsModel.objects.create(...)
    
    e1_rule = SionPlanningRule.objects.create(sion_id=1, name="E1 Rule")
    a3627_rule = SionPlanningRule.objects.create(sion_id=17, name="A3627 Rule")
    
    # Both have plans
    e1_plan = LicenseItemPlan.objects.create(
        license=license, planning_rule=e1_rule
    )
    a3627_plan = LicenseItemPlan.objects.create(
        license=license, planning_rule=a3627_rule
    )
    
    assert LicenseItemPlan.objects.filter(license=license).count() == 2
    
    # Force All for A3627 only
    result = SionRulePlanningService.plan_sion(
        sion_id=17,  # A3627
        license_ids=[license.pk],
        mode="ALL"
    )
    
    # Current behavior (BUG):
    assert LicenseItemPlan.objects.filter(license=license).count() == 1
    assert LicenseItemPlan.objects.filter(planning_rule=e1_rule).count() == 0
    # E1 plan was DELETED! ❌
    
    # Expected behavior (FIXED):
    assert LicenseItemPlan.objects.filter(license=license).count() > 0
    assert LicenseItemPlan.objects.filter(planning_rule=e1_rule).exists()
    # E1 plan still exists ✅
```

## Files Requiring Changes

| File | Line | Change |
|------|------|--------|
| plan_enforcement.py | 130 | Add `sion_id=None` parameter |
| plan_enforcement.py | 170-171 | Add SION scope to deletion query |
| canonical_planning_service.py | 200 | Add `sion_id` parameter to build_canonical_plan |
| canonical_planning_service.py | 334-336 | Pass sion_id to save_plan_lines_for_license |
| sion_planning_execution.py | 550 | Add `sion` to _compute_license return |
| sion_planning_execution.py | 637-640 | Pass sion_id to build_canonical_plan |

## Backward Compatibility

- Default `sion_id=None` means delete ALL (current behavior)
- Existing callers not specifying sion_id continue to work
- No migration needed (behavior change only)
- No model changes required

## Impact Assessment

- **Severity**: CRITICAL
- **Scope**: Multi-SION licenses
- **User Impact**: Force All on SION A3627 might delete E1 plans
- **Likelihood**: HIGH for licenses with multiple SION plans
- **Test Coverage**: Currently missing

## Acceptance Criteria

✅ After fix:
- [ ] Force All SION A3627 leaves E1 plans untouched
- [ ] Force All SION E1 leaves A3627 plans untouched
- [ ] Delete is scoped correctly by SION
- [ ] Multi-SION license test passes
- [ ] Rollback restores ALL old plans
- [ ] No model migrations
- [ ] Backward compatible

---

**Status**: REQUIRES IMMEDIATE FIX BEFORE PRODUCTION USE
