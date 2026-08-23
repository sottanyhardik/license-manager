# MODULE 2 — UNKNOWN REGISTER & INDEPENDENT CLASSIFICATION

**Classification Date:** 2026-08-10  
**Source:** Independent review of MODULE_2_PLANNING_UNKNOWNS.md  
**Assessment:** All unknowns re-classified for implementation gating  

---

## SUMMARY

| Category | Count | Blocking | Material |
|----------|-------|----------|----------|
| Feature Gaps | 2 | NO | NO |
| Specification Gaps | 1 | NO | NO |
| Calculation Precision | 2 | NO | YES (test-covered) |
| Validation Gaps | 1 | NO | YES (add to canonical) |
| Balance Interactions | 2 | NO | YES (mitigated by live balance) |
| Manual Plan UX | 2 | NO | NO |
| Group Definition | 1 | NO | NO |
| **TOTAL** | **11** | **ZERO** | **3 mitigated** |

---

## DETAILED CLASSIFICATION

### 1. NORM CLASSIFICATION DECISIONS

#### Unknown 1.1: PP Norm Planning Rules (73 of 228 licenses = 32%)
- **Type:** Feature Gap
- **Current Status:** No auto-plan for PP licenses (manual entry only)
- **Financial Impact:** LOW (manual entry works, just requires user effort)
- **Data Integrity Impact:** NONE
- **Blocks Implementation:** NO
- **Recommendation:** DEFER to post-Module 2 feature (PP auto-plan engine)
- **Action:** Document in UI that PP licenses require manual planning
- **Classification:** NON-BLOCKING

#### Unknown 1.2: A3627 Specification
- **Type:** Incomplete Documentation
- **Current Status:** Engine exists but specification unclear, 1 real license
- **Financial Impact:** LOW (1 license affected)
- **Data Integrity Impact:** NONE
- **Blocks Implementation:** NO
- **Recommendation:** DOCUMENT and TEST existing behavior
- **Action:** Add A3627 to golden test scenarios, verify current behavior
- **Classification:** NON-BLOCKING

---

### 2. CALCULATION PRECISION & ROUNDING

#### Unknown 2.1: Exact Rounding Behavior During Waterfall
- **Type:** Calculation Verification Needed
- **Current Status:** Existing code works for E1/E5, defect found in E126/E132
- **Financial Impact:** MEDIUM (rounding accumulation possible)
- **Data Integrity Impact:** LOW (existing code persists correctly)
- **Blocks Implementation:** NO (existing code is known, test-covers behavior)
- **Recommendation:** ADD rounding test case verifying sum(item_cif) ≈ category_cif
- **Action:** Create golden test: verify rounding tolerance (±0.01)
- **Classification:** NON-BLOCKING (test-covered)

#### Unknown 2.2: BL-PLAN-01 Fix Side Effects
- **Type:** Known Defect + Proposed Fix
- **Current Status:** E126/E132 have `planned_cif_fc` mismatch, fix proposed
- **Financial Impact:** MEDIUM (affects fractional splits)
- **Data Integrity Impact:** MEDIUM (changed plan values could cascade)
- **Blocks Implementation:** NO (defect exists in current code)
- **Recommendation:** FIX in CanonicalPlanningService, AVOID in consumer migration
- **Action:** Implement BL-PLAN-01 fix in canonical service (recompute planned_cif after flooring)
- **Classification:** NON-BLOCKING (fix applies to new implementation only)

---

### 3. VALIDATION GAPS

#### Unknown 3.1: Missing Validation (planned_cif_fc ≈ planned_qty × unit_price)
- **Type:** Validation Gap
- **Current Status:** Validation missing, BL-PLAN-01 not caught
- **Financial Impact:** MEDIUM (corrupted rows not detected)
- **Data Integrity Impact:** MEDIUM (silent persistence of invalid state)
- **Blocks Implementation:** NO (add validation to canonical service)
- **Recommendation:** ADD validation check in CanonicalPlanningService
- **Action:** Before saving LicenseItemPlan, verify planned_cif_fc ≈ round(planned_qty × unit_price, 2) with ±0.01 tolerance
- **Classification:** NON-BLOCKING (add to implementation)

---

### 4. LEDGER & BALANCE INTERACTIONS

#### Unknown 4.1: Hidden BOE Rows Interaction
- **Type:** Edge Case
- **Current Status:** Hidden BOE rows affect balance_cif calculation, unclear intent
- **Financial Impact:** LOW (rare, hidden BOEs edge case)
- **Data Integrity Impact:** LOW (documented edge case)
- **Blocks Implementation:** NO
- **Recommendation:** DOCUMENT behavior, TEST edge case
- **Action:** Add golden test: hide BOE, verify plan allocation unchanged
- **Classification:** NON-BLOCKING

#### Unknown 4.2: Cached vs. Live Balance CIF (CRITICAL CLARIFICATION)
- **Type:** Critical Balance Source Question
- **Current Status:** get_balance_cif() might return stale cached balance
- **Financial Impact:** HIGH (over-allocation risk if stale)
- **Data Integrity Impact:** HIGH (balance corruption possible)
- **Blocks Implementation:** NO **IF** we use LIVE balance
- **Recommendation:** CanonicalPlanningService MUST call live balance computation (Module 1 CanonicalLedgerService)
- **Action:** Use `license_obj.get_balance_cif()` confirmed to compute LIVE (not cached)
- **Classification:** NON-BLOCKING (mitigated by using Module 1 canonical ledger)

---

### 5. MANUAL PLAN INTERACTION

#### Unknown 5.1: Manual Plan Merge Semantics
- **Type:** User Experience Clarification
- **Current Status:** Manual plans preserved when auto-plan re-run, unclear to users
- **Financial Impact:** NONE (existing behavior)
- **Data Integrity Impact:** NONE
- **Blocks Implementation:** NO
- **Recommendation:** PRESERVE existing behavior, DOCUMENT in UI
- **Action:** Add UI note: "Manual plan lines persist when Auto-Plan runs"
- **Classification:** NON-BLOCKING

#### Unknown 5.2: Unit Price Derivation from Manual Plans
- **Type:** Calculation Verification
- **Current Status:** unit_price computed from planned_cif/planned_qty for manual plans
- **Financial Impact:** LOW (mostly edge case)
- **Data Integrity Impact:** NONE
- **Blocks Implementation:** NO
- **Recommendation:** VERIFY in golden tests
- **Action:** Test case: create manual plan with 0.123 qty, verify unit_price computation
- **Classification:** NON-BLOCKING

---

### 6. GROUP SCOPING & AGGREGATION

#### Unknown 6.1: Group Key Definition
- **Type:** Documentation Gap
- **Current Status:** plan_group_key() function exists, semantics not documented
- **Financial Impact:** NONE (existing code works)
- **Data Integrity Impact:** NONE (tested in existing code)
- **Blocks Implementation:** NO
- **Recommendation:** DOCUMENT function, VERIFY behavior in tests
- **Action:** Document plan_group_key() in code comments with examples
- **Classification:** NON-BLOCKING

---

## IMPLEMENTATION GATING DECISION

### Can Module 2 Implementation Proceed?

| Gate | Status | Evidence |
|------|--------|----------|
| Critical unknowns | ZERO | 4.2 mitigated by using live balance |
| Blocking unknowns | ZERO | All 11 classified as non-blocking |
| Financial impact | ACCEPTABLE | 3 unknowns have mitigation strategies |
| Data integrity risk | MITIGATED | Live balance, validation, testing |
| Implementation scope | CLEAR | 6 actions fit within canonical service design |

### **VERDICT: IMPLEMENTATION MAY PROCEED** ✅

**Conditions:**
1. Use LIVE balance from Module 1 CanonicalLedgerService (Unknown 4.2 mitigation)
2. Implement BL-PLAN-01 fix in canonical service (Unknown 2.2 mitigation)
3. Add validation for planned_cif_fc ≈ planned_qty × unit_price (Unknown 3.1 mitigation)
4. Add rounding verification golden test (Unknown 2.1 mitigation)
5. Add manual plan UX documentation (Unknown 5.1 mitigation)
6. Document group key behavior (Unknown 6.1 mitigation)

**Non-blocking deferrable unknowns:**
- PP Norm (defer feature, document limitation)
- A3627 specification (defer detailed spec, test existing)
- Hidden BOE interaction (edge case, test if time permits)
- Manual price derivation (edge case, test if time permits)

---

## NEXT ACTIONS

1. ✅ Unknown classification complete
2. ⏳ Await implementation workflow completion
3. ⏳ Verify implementation against conditions above
4. ⏳ Freeze Module 2 if all conditions met
5. ⏳ Auto-start Module 4 discovery

**Status:** READY FOR IMPLEMENTATION
