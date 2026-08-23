# PHASE A CONTEXT HANDOFF

**Current Status:** Phase A authorization LOCKED. Phase A.1 plan READY FOR EXECUTION.

**Session Progress:**
1. ✅ Repository reconnaissance complete
2. ✅ D1-D4 business decisions investigated
3. ✅ Findings documents created (4 findings)
4. ✅ Phase A authorization approved by business
5. ✅ Phase A.1 domain foundation plan detailed and committed
6. 🟡 **NEXT:** Phase A.1 implementation (domains, migrations, backfill)

---

## LOCKED DECISIONS (DO NOT RECONSIDER)

### D1: Company Boundary
- Every allocation must have explicit company
- User chooses company per allocation line
- Multi-company support
- Integrated with existing authorization
- No weaker boundaries

### D2: CIF Validation
- CIF is DERIVED: `cif = qty × unit_price`
- Decimal throughout (no float)
- ROUND_HALF_UP rounding
- Server-calculated, not client-authoritative

### D3: Approval Gate
- `is_approved` remains informational
- Does NOT gate allocation
- No code changes for approval logic

### D4: Decimal Precision
- Quantity: existing precision (3-dp)
- Price: 2-dp (standardized)
- CIF: 2-dp
- Rounding: ROUND_HALF_UP
- No float arithmetic

---

## LOCKED BUSINESS RULES

**DO NOT CHANGE THESE:**

1. **Automatic priority:** expiry → issue_date → license_number
2. **Allowed Expiry Date:** inclusive (>=), hard filter before priority
3. **No expiry or license number:** excluded from automatic planning
4. **Manual priority:** overrides automatic
5. **Manual allocation:** cannot exceed live availability
6. **Shortfalls:** FIFO auto-fill when balance increases
7. **Final BOE:** protected, not auto-deleted
8. **Non-final BOE:** user-removable, not auto-removed
9. **BOE usage > allocation:** auto-increase allocation
10. **Atomicity:** all balance mutations atomic
11. **History:** never delete, immutable lifecycle
12. **Reactivation:** uses current limits, not historical

---

## PHASE A.1 — READY FOR EXECUTION

**Plan committed:** `PHASE_A1_DOMAIN_FOUNDATION_PLAN.md`

**Execution steps:**
1. Create migration: Add fields to AllotmentItems
2. Modify AllotmentItems model
3. Create AuditEvent model
4. Create Shortfall model
5. Create AllocationVersion model
6. Update imports
7. Run migrations
8. Backfill existing data
9. Unit tests
10. Verify schema

**Estimated effort:** 4-6 hours

**Critical files:**
- `backend/apps/allotment/models.py` (modify)
- `backend/apps/allotment/migrations/000X_*.py` (create)
- `backend/apps/allotment/models/audit_event.py` (create)
- `backend/apps/allotment/models/shortfall.py` (create)
- `backend/apps/allotment/models/allocation_version.py` (create)

---

## CONTEXT RECOVERY (if compaction occurs)

If context compacts during Phase A.1 implementation:

1. **Verify current state:**
   ```bash
   git log --oneline -10  # Should show authorization + plan commits
   git status             # Check for uncommitted changes
   ```

2. **Resume from last clean point:**
   - If migrations created: run `python manage.py migrate`
   - If models modified: review changes against plan
   - If incomplete: follow Phase A.1 checklist from plan

3. **Do NOT:**
   - Change locked decisions (D1-D4)
   - Deviate from business rules
   - Introduce unrelated refactoring
   - Skip migration backfill

---

## CURRENT GIT STATE

**Branch:** feature/V2 (68 commits ahead of origin/develop)

**Recent commits:**
```
6834eff9 docs: Phase A.1 detailed implementation plan
afee89a6 chore: Phase A authorization locked (D1-D4 decisions approved)
1a365679 docs: Phase A findings for D1-D4 business decisions
cbcd20f9 docs: implementation map for allocation/planning specification
```

**Working tree:** Clean (ready for development)

---

## WHAT NOT TO DO

- ❌ Do not rebuild planning system
- ❌ Do not duplicate CanonicalPlanningService
- ❌ Do not change Phase 4D behavior
- ❌ Do not change unrelated calculations
- ❌ Do not delete history
- ❌ Do not introduce float arithmetic
- ❌ Do not trust client CIF
- ❌ Do not allow manual allocation > availability
- ❌ Do not let automatic planning use expired licenses
- ❌ Do not auto-reduce unrelated allocations

---

## NEXT PHASE (After A.1)

When Phase A.1 is complete with all tests passing:

1. Report: Files changed, models added, migrations, tests passed
2. **Phase A.2:** Canonical domain services (8 services)
   - EligibilityService
   - AutomaticPriorityService
   - ManualAllocationService
   - AutomaticPlanningService
   - ShortfallFulfillmentService
   - BOEReconciliationService
   - ReleaseService
   - ConcurrencyService

Then A.3 (Atomicity), A.4 (Fix F1-F10), A.5 (Tests).

**Do NOT start Phase A.2 until A.1 is complete and verified.**

---

**Status:** Ready to begin Phase A.1 implementation.

**Authorization:** LOCKED (commit afee89a6)

**Plan:** COMMITTED (commit 6834eff9)

**Proceed with Phase A.1.**
