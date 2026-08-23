# PHASE A FINDINGS SUMMARY

**Investigation Complete** — Four business decisions analyzed, findings documented.

**Status:** AWAITING AUTHORIZATION before Phase A implementation begins.

---

## KEY FINDINGS

### D1: Company Boundary
**Current state:** AllotmentModel has company field, but **AllotmentItems does NOT**. Any ALLOTMENT_MANAGER can access any allotment (no object-level authorization).

**Gap:** Specification (Req 5) requires manual company selection and splitting across multiple companies. Not possible without adding company field to AllotmentItems.

**Recommendation:** Add company FK to AllotmentItems, migrate existing rows to inherit from allotment, implement manual company selection in allocate_items.

**Business decision needed:** Should users be scoped to a single company, or can they act on behalf of multiple?

---

### D2: CIF Validation
**Current state:** CIF is MIXED:
- AllotmentModel: auto-calculates if unit_value provided, otherwise accepts user input
- LicenseItemPlan: CanonicalPlanningService derives from qty × price
- AllotmentItems: **accepts client CIF without any validation** (F8 defect)

**Gap:** allocate_items endpoint trusts client's cif_fc blindly. No check that cif_fc ≈ qty × unit_price.

**Recommendation:** Implement CIF as DERIVED:
- Derive from qty × unit_price (get unit_price from plan_line or allotment)
- Validate client-provided cif_fc matches (within 0.01 tolerance) or use derived value
- Fixes F8 (client-supplied money unvalidated)

**No change to AllotmentModel or LicenseItemPlan required.**

---

### D3: Approval Gate
**Current state:** is_approved field exists on AllotmentModel, but does **NOT gate allocation**. It's informational/filterable only.

**Gap:** Specification doesn't explicitly require approval gate. Current system doesn't enforce it.

**Recommendation:** Leave as-is (informational). Do NOT implement as a blocking gate in Phase A unless explicitly approved.

**No code changes required.**

---

### D4: Decimal Precision
**Current state:** INCONSISTENT:
- Quantities: 3-dp (0.001)
- Prices: mixed (AllotmentModel is 3-dp, LicenseItemPlan is 2-dp)
- CIF: 2-dp
- Balance: uses float in some places (precision loss)

**Gap:** Unit values have inconsistent precision. Calculate_balance.py uses float (F10 defect).

**Recommendation:** Implement single canonical rule:
- **Quantity × Unit Price = CIF (always)**
- Standardize all prices to 2-dp (migrate AllotmentModel.unit_value_per_unit from 3-dp to 2-dp)
- Use Decimal throughout (replace float in calculate_balance.py)
- ROUND_HALF_UP for normal calcs, ROUND_DOWN for availability ceiling
- Fixes F10 (float arithmetic, silent failures)

---

## ADDITIONAL FINDINGS

### Authorization Gap (F6 — Module 3 defect)
- allocate_items uses bare `get_object_or_404(AllotmentModel, pk=pk)` with no company check
- D1 must be resolved first (add company to AllotmentItems)
- Then implement authorization check: validate caller can allocate to selected company

### Inconsistency: Unit Price Precision
- AllotmentModel.unit_value_per_unit: 3-dp (unusual)
- LicenseItemPlan.unit_price: 2-dp (standard)
- Should be harmonized (both 2-dp) per D4

### Backward Compatibility Risk
- D1 migration: AllotmentItems gains company field (null during migration)
- D4 migration: AllotmentModel.unit_value_per_unit changes from 3-dp to 2-dp
- Both require audit of existing allocations to ensure no corruption

---

## EXACT FILES/MODELS/SERVICES FOR PHASE A

### New Models
```
backend/apps/allotment/models/allocation_version.py
backend/apps/allotment/models/audit_event.py
backend/apps/allotment/models/shortfall.py
```

### Models to Modify
```
backend/apps/allotment/models.py
  - AllotmentItems: Add company FK, status, released_qty, reactivated_qty, version links
  - AllotmentModel: Possibly change unit_value_per_unit precision (D4)

backend/apps/core/models.py
  - No changes needed (CompanyModel already exists)
```

### Migrations Required
```
1. Add fields to AllotmentItems (company, status, released_qty, etc.)
2. Backfill AllotmentItems.company = allotment.company
3. Change AllotmentModel.unit_value_per_unit precision (3-dp → 2-dp)
4. Create AuditEvent, Shortfall, AllocationVersion models
```

### Services to Create
```
backend/apps/allotment/services/eligibility_service.py
backend/apps/allotment/services/automatic_priority_service.py
backend/apps/allotment/services/manual_allocation_service.py
backend/apps/allotment/services/shortfall_fulfillment_service.py
backend/apps/allotment/services/boe_reconciliation_service.py
backend/apps/allotment/services/release_service.py
backend/apps/allotment/services/concurrency_service.py
```

### Existing Services to Extend/Modify
```
backend/apps/license/services/canonical_planning_service.py
  - Extend for automatic planning (use new services)

backend/apps/core/scripts/calculate_balance.py
  - Replace float with Decimal (F10 fix)
  - Harmonize rounding (ROUND_HALF_UP)
```

### Views to Refactor/Extend
```
backend/apps/allotment/views_actions.py
  - allocate_items endpoint (fix F1-F10, add company selection, add validation)
  - May split into multiple endpoints if needed

backend/apps/license/views/item_plan.py
  - Extend auto_plan with allowed_expiry_date
  - Wire to automatic planning logic
```

### Serializers to Update
```
backend/apps/allotment/serializers.py
  - Add company, status, versioning fields
  - Add error mapping for new exceptions
```

---

## CONFLICTS BETWEEN SPEC AND EXISTING IMPLEMENTATION

| Requirement | Current State | Conflict | Resolution |
|---|---|---|---|
| Req 5 (multi-company allocation) | AllotmentItems has no company field | Cannot assign allocation to specific company | Add company FK (D1) |
| Req 8 (partial release) | No lifecycle/version tracking | Cannot record partial releases | Add status, release fields (model change) |
| Req 11 (allowed_expiry_date) | Not implemented | No way to filter licenses by expiry cutoff | Add to automatic planning |
| F1 (concurrent safety) | select_for_update doesn't protect availability | Can over-allocate under concurrency | Refactor allocate_items to use running ledger |
| F8 (CIF validation) | No validation of client CIF | Client can send arbitrary CIF | Add validation/derivation (D2) |
| F10 (float arithmetic) | Uses float in calculate_balance.py | Precision loss | Use Decimal throughout |

---

## RECOMMENDED IMPLEMENTATION SEQUENCE

### Phase A.1 — Data Model
1. Create migrations for new fields/models
   - AllotmentItems: company, status, released_qty, reactivated_qty, version links
   - Create AuditEvent, Shortfall, AllocationVersion models
2. Backfill existing data
3. Change unit_value_per_unit precision (D4)

### Phase A.2 — Core Services (in order)
1. EligibilityService (check license expiry cutoff, license number, issue date)
2. AutomaticPriorityService (fixed priority + FIFO)
3. ManualAllocationService (validate, apply caps, handle concurrency)
4. AutomaticPlanningService (extend CanonicalPlanningService)
5. ShortfallFulfillmentService (FIFO auto-fulfill)
6. BOEReconciliationService (reconcile to actual BOE usage)
7. ReleaseService (release, reversal, reactivation)
8. ConcurrencyService (save-time revalidation, auto-reduction)

### Phase A.3 — Infrastructure Fixes
1. Replace float with Decimal in calculate_balance.py (F10)
2. Implement atomic transaction boundaries for all mutations
3. Create combined audit event logging

### Phase A.4 — API Refactor
1. Refactor allocate_items endpoint
   - Add company selection
   - Implement manual allocation service
   - Add CIF validation/derivation (D2)
   - Fix F1-F10 atomically
2. Extend CanonicalPlanningService for automatic planning
3. Create release/reactivation endpoints
4. Create shortfall endpoints

### Phase A.5 — Testing
- Unit tests for each service
- Integration tests for end-to-end flows
- Concurrency/atomicity tests
- Backward compatibility audit

---

## CRITICAL DECISIONS STILL PENDING

**Before Phase A implementation can begin, approve:**

1. **D1 Answer:** Should users be scoped to specific company(ies), or can ALLOTMENT_MANAGER users access any company's allocations?

2. **D2 Answer:** Confirmed: Implement CIF as DERIVED (qty × unit_price). Correct?

3. **D3 Answer:** Confirmed: Leave is_approved as informational (no gate). Correct?

4. **D4 Answer:** Confirmed: Implement qty × price = cif rule with ROUND_HALF_UP. Correct?

5. **Authorization:** If D1 adds company field, should authorization check be:
   - Option A: Caller's company must match allocation.company
   - Option B: Caller can see all companies (no company isolation)
   - Option C: User has explicit permission list for which companies they can allocate to

---

**DO NOT IMPLEMENT PHASE A UNTIL THESE ARE APPROVED.**

Findings documents:
- D1_COMPANY_BOUNDARY_FINDINGS.md
- D2_CIF_VALIDATION_FINDINGS.md
- D3_APPROVAL_GATE_FINDINGS.md
- D4_DECIMAL_PRECISION_FINDINGS.md
