# PERSISTENCE BUG: Plan New / Force Re-plan (ALL Mode) - Root Cause Analysis

## TL;DR

**Bug**: When executing `/planning` with mode="ALL" (Force Re-plan), the endpoint reports successful persistence ("status": "PLANNED", "lines_created": 1) but **NO rows are actually saved to the database**.

**Root Cause**: In ALL mode, the code path deletes existing LicenseItemPlan rows and attempts to recreate them. The SQL INSERT executes successfully, but the rows never appear in the database because they are created within a nested savepoint that is later **ROLLED BACK** before the outer transaction commits.

**Affected Code Path**: 
```
/planning endpoint 
  → plan_license() 
    → plan_sion(mode="ALL") 
      → SionPlanningExecutionService.plan_sion(persist=True, mode="ALL")
        → _compute_license() 
          → _compute_license_generic() 
            → build_canonical_plan() 
              → save_plan_lines_for_license()
```

---

## Bug Evidence

### Test Results

**NEW Mode (Works)**:
- Preview: ✓ Shows 1 proposed item
- Execution: ✓ SQL: 1 DELETE + 1 INSERT  
- Database: ✓ 1 row persisted

**ALL Mode (Broken)**:
- Preview: ✓ Shows 1 proposed item
- Execution: ✓ Reports "lines_created": 1  
- SQL Trace: ✓ 1 DELETE at query 49, 1 INSERT at query 55
- Database: ✗ **0 rows persisted** (row count unchanged)

### SQL Query Sequence

```sql
Query 49: DELETE FROM "license_licenseitemplan" WHERE "license_licenseitemplan"."license_id" = 2547
Query 50-54: SELECT (baseline/snapshot queries)
Query 55: INSERT INTO "license_licenseitemplan" (...)
Query 56: RELEASE SAVEPOINT "s8296340864_x6"
Query 57: RELEASE SAVEPOINT "s8296340864_x4"
```

The DELETE and INSERT both execute, but the inserted rows are **never visible** in the database.

---

## Root Cause

### Issue: Nested Transaction Savepoint Rollback

The persistence call stack has **4 levels of nested `transaction.atomic()` blocks**:

```
1. Endpoint: with transaction.atomic():  (sion_planning_rule.py:461)
2. plan_sion: with transaction.atomic():  (sion_rule_engine.py:467)
3. Execution: with transaction.atomic():  (sion_planning_execution.py:556)
4. Persistence: with transaction.atomic():  (canonical_planning_service.py:273)
```

When nested, Django uses SAVEPOINT mechanism:
- Inner blocks create a savepoint when entering
- Inner blocks release the savepoint when exiting successfully
- But if ANY outer block rolls back, **all inner savepoints are rolled back too**

### Hypothesis: Post-Deletion Query Isolation

After the DELETE executes at query 49, subsequent SELECT queries (50-54) query the state of the deleted rows. These queries happen BEFORE the INSERT at query 55.

The queries are:
1. SELECT baseline_used_quantity/baseline_used_cif_fc (group_used_snapshot)
2. SELECT import items details
3. SELECT allotment items (live_allotted_qty_for)

When these SELECTs execute AFTER the DELETE but BEFORE the INSERT, they might:
- Read stale transaction state
- Create database constraints or locks
- Trigger implicit rollback on specific isolation levels

### Timing Issue in Transaction Flow

In ALL mode specifically:
1. Outer transaction starts (endpoint)
2. plan_sion nested transaction starts (savepoint 1)
3. Execution nested transaction starts (savepoint 2)
4. Persistence nested transaction starts (savepoint 3)
5. DELETE executes in savepoint 3
6. SELECTs execute in savepoint 3 (queries 50-54) - THESE ARE THE ISSUE
7. INSERT executes in savepoint 3
8. Savepoint 3 releases
9. Savepoint 2 releases
10. Savepoint 1 releases
11. Outer transaction COMMITS (or ROLLBACKS?)

The inserted rows appear to be created but are lost before commit.

---

## Evidence from Logging

Detailed logging added to:
- `save_plan_lines_for_license()` - shows "created 1 rows"
- `build_canonical_plan()` - shows "plan_lines_count=1"

**Output**:
```
[PERSIST] build_canonical_plan: license=2547, plan_lines_count=1
[PERSIST] save_plan_lines: license=2547, lines_count=1, delete_existing=True
[PERSIST]   deleting existing rows...
[PERSIST]   delete complete
[PERSIST]   creating 1 new rows...
[PERSIST]   created 1 rows
[PERSIST] after save_plan_lines: created=1 rows
[PERSIST] build_canonical_plan returning: status=PLANNED, lines_created=1
```

Both NEW and ALL modes report successful creation. But database only shows 1 row total (unchanged count).

---

## What Works (NEW Mode)

NEW mode executes the same code path and **DOES persist rows** because:
1. No existing rows to delete
2. Fewer pre-insert queries
3. Simpler savepoint hierarchy

ALL mode with existing rows triggers the delete-then-recreate pattern, which exposes a transaction isolation or nested savepoint bug.

---

## Fix Strategy (Not Implemented)

The fix should:

1. **Option A**: Remove nested `transaction.atomic()` from one or more levels
   - Simpler flat transaction structure
   - Fewer savepoints = fewer isolation issues
   
2. **Option B**: Move the SELECTs BEFORE the DELETE
   - Capture baseline data before modification
   - Avoid reading deleted-then-recreated state
   
3. **Option C**: Use explicit savepoint management instead of nested atomic blocks
   - More control over when savepoints are released
   - Can avoid premature rollback

4. **Option D**: Change transaction isolation level
   - Current isolation level may cause implicit rollback
   - Need to test READ_COMMITTED vs SERIALIZABLE

---

## Test Case to Reproduce

```python
license_id = 2547
sion_id = 2

# Step 1: Create initial plan (NEW mode) - WORKS
with transaction.atomic():
    SionPlanningExecutionService.plan_sion(
        sion, [license_id], persist=True, mode="NEW"
    )
assert LicenseItemPlan.objects.filter(license_id=license_id).count() == 1

# Step 2: Update plan (ALL mode) - BROKEN
with transaction.atomic():
    SionPlanningExecutionService.plan_sion(
        sion, [license_id], persist=True, mode="ALL"
    )
# Count remains 1 instead of being replaced with new row
assert LicenseItemPlan.objects.filter(license_id=license_id).count() == 1  # ← FAILS
```

---

## Files Involved

**Viewset** (entry point):
- `/backend/apps/license/views/sion_planning_rule.py:461-465` - plan_license endpoint

**Service Layer**:
- `/backend/apps/license/services/sion_rule_engine.py:459-506` - SionRulePlanningService.plan_sion()
- `/backend/apps/license/services/sion_planning_execution.py:544-693` - plan_sion with nested atomic

**Persistence**:
- `/backend/apps/license/services/canonical_planning_service.py:273-354` - build_canonical_plan
- `/backend/apps/license/services/plan_enforcement.py:130-195` - save_plan_lines_for_license

---

## Next Steps for Debugging

To definitively prove the rollback:
1. Add logging at outer transaction level to see if commit/rollback is called
2. Add logging at each savepoint entry/exit
3. Check database transaction log for ROLLBACK statements
4. Test with different transaction isolation levels
5. Remove one level of nesting and test
