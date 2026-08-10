# GATE 3: Ledger Implementation Plan (Updated)

**Status:** GATE 3 ARCHITECTURE DESIGN — Do NOT implement until gate 3 is APPROVED and business decision on B2/B4 is recorded.

**This document supersedes:** LEDGER_DETAIL_MIGRATION_PLAN.md (replaced by this comprehensive system-wide plan)

---

## Executive Summary

This plan implements the **License Ledger P0 defect fix** as **Phase 3B** of the overall calculation architecture transformation. It uses the Single Source of Truth framework (GATE 3 documents) to eliminate duplicate balance calculations across backend and frontend.

**Duration:** ~10 working days (assumes B2/B4 business decisions already recorded)

**Risk:** MEDIUM (touches balance calculation — high impact, must use parity framework)

**Gate:** Requires approval of all GATE 3 documents + business decisions on B2 (running balance convention) and B4 (commission treatment)

---

## PART 1: Prerequisites (Before Implementation Starts)

### Must-Have Approvals

- [ ] GATE3_SINGLE_SOURCE_OF_TRUTH_CALCULATIONS.md approved by architecture team
- [ ] GATE3_CALCULATION_DEPENDENCY_GRAPH.md approved
- [ ] GATE3_FINANCIAL_NUMBER_CONTRACT.md approved
- [ ] GATE3_UNIT_AND_CURRENCY_RULES.md approved
- [ ] GATE3_TIME_AND_PERIOD_CALCULATIONS.md approved
- [ ] GATE3_DUPLICATE_CALCULATIONS.md approved
- [ ] GATE3_CALCULATION_PARITY_FRAMEWORK.md approved
- [ ] GATE3_LEDGER_SINGLE_SOURCE_OF_TRUTH_DESIGN.md approved by ledger domain owner
- [ ] GATE3_LEDGER_CALCULATION_INTEGRATION.md approved by all dependent domain leads (Planning, Allocation, BOE, Reconciliation)

### Must-Have Business Decisions

- [ ] **B2: Running Balance Convention** — Approved decision doc (ADR-004?)
  - Option A (Backend current): License-wide, date-ordered, commissions=debit ← Recommended
  - Option B (Frontend current): Per-company, type-ordered, commissions=excluded
  - Implementation assumes chosen option

- [ ] **B4: Commission Treatment** — Approved decision doc
  - YES: COMMISSION_SALE reduces balance (backend current)
  - NO: COMMISSION_SALE has no balance impact (frontend current)
  - Implementation assumes chosen option

### Code State

- [ ] `develop` branch is clean (all pending changes committed or reverted)
- [ ] `feature/V2` branch is up-to-date with `develop`
- [ ] All existing ledger tests pass (baseline)
- [ ] Golden dataset scenarios are prepared (see GATE3_CALCULATION_PARITY_FRAMEWORK.md)

---

## PART 2: High-Level Phases

### Phase 3A: Infrastructure (Days 1-2)

**Deliverables:**
- Golden dataset test framework
- CanonicalLedgerService skeleton
- Feature flag infrastructure

**Activities:**
1. Create `backend/apps/license/services/canonical_ledger.py` (stub)
2. Create `backend/apps/license/tests/golden_data/` directory
3. Create `backend/apps/license/tests/test_parity_framework.py` (framework + 7 scenarios)
4. Add feature flag `LEDGER_CANONICAL_ENGINE` (default OFF)
5. Create `docs/architecture/ADR-004-ledger-running-balance-convention.md` (record business decision B2)

**Owner:** Backend architect + QA

**Tests:** Framework tests only (parity framework itself)

### Phase 3B: Core Implementation (Days 3-6)

**Deliverables:**
- CanonicalLedgerService fully implemented
- Parity tests on golden dataset pass
- API contract updated

**Activities:**
1. Implement `CanonicalLedgerService.build_ledger_rows()` (main calculation)
2. Implement `CanonicalLedgerService.get_company_attribution()` (derived)
3. Update TRANSACTION_RULES in `constants.py` with all transaction types
4. Add validation: `validate_transaction_rules()` (fail fast on misconfiguration)
5. Update `LicenseLedgerViewSet.ledger_detail` action to use new service
6. Update API serializer to return new response schema
7. Run parity tests on all 7 golden scenarios
8. Fix any parity failures (or reclassify as EXPECTED_CHANGE)

**Owner:** Backend engineer

**Tests:** 
- Parity framework: 7 scenarios must pass
- Unit tests: CanonicalLedgerService in isolation
- Integration tests: API endpoint returns correct schema

### Phase 3C: Characterization Tests (Days 7-8)

**Deliverables:**
- Comprehensive regression tests
- Edge case coverage

**Activities:**
1. Create `backend/apps/license/tests/test_ledger_characterization.py`
2. Add 20+ characterization tests covering:
   - Different license types (DFIA, Incentive, etc.)
   - Multiple companies
   - Same-day transactions (ordering by ID)
   - Rounding edge cases
   - Zero and negative balances
   - Mixed transaction types
3. Run against production-like data subset
4. Domain expert spot-checks

**Owner:** QA + Backend engineer

**Tests:** 20+ characterization tests, all must pass

### Phase 3D: Consumer Migration (Days 9-10)

**Deliverables:**
- Frontend updated to read from API (not recalculate)
- Feature flag ready for rollout

**Activities:**
1. Update LicenseLedgerDetail.tsx to read `running_balance` from API (remove local calculation)
2. Update ledgerExport.js PDF logic to read from API
3. Update ledgerExport.js Excel logic to read from API
4. Add regression test: PDF balance matches API balance
5. Add regression test: Excel balance matches API balance
6. Feature flag: Enable with 10% rollout
7. Deploy to staging for integration testing

**Owner:** Frontend engineer

**Tests:**
- Page renders correctly
- PDF export matches API
- Excel export matches API

---

## PART 3: Detailed Implementation Steps

### Backend: CanonicalLedgerService

**File:** `backend/apps/license/services/canonical_ledger.py` (NEW, ~400 lines)

**Key Methods:**

```python
class CanonicalLedgerService:
    
    @staticmethod
    def build_ledger_rows(license_id: int, include_hidden: bool = False) -> List[LedgerRow]:
        """
        Build canonical ledger with running balance.
        
        Requirement: Transaction ordering must be deterministic
        (by date ascending, then by id ascending).
        """
        # 1. Fetch opening balance
        # 2. Fetch all transactions
        # 3. Order: date asc, id asc
        # 4. Calculate running balance row-by-row
        # 5. Return rows with running_balance field
        pass
    
    @staticmethod
    def get_company_attribution(license_id: int) -> Dict[str, CompanyBreakdown]:
        """Get per-company balance breakdown."""
        pass
```

**Tests:**
- Unit: Calculation logic in isolation
- Parity: Against golden dataset (7 scenarios)
- Characterization: 20+ edge cases

### Backend: Transaction Semantics

**File:** `backend/apps/core/constants.py` (ADD section)

```python
# TRANSACTION_RULES: Single source of truth for transaction semantics
TRANSACTION_RULES = {
    "PURCHASE": {...},
    "SALE": {...},
    "COMMISSION_SALE": {...},  # ← Decided by B4
    "BOE_DEBIT": {...},
    "ALLOTMENT": {...},
    # ... all other types
}

def validate_transaction_rules():
    """Ensure all DB types are defined."""
    pass
```

### Backend: API Contract

**File:** `backend/apps/license/views/ledger.py` (MODIFY, ~20 lines)

```python
# ledger_detail action now returns new schema
# with running_balance field on each row
# and company_utilizations breakdown
```

**File:** `backend/apps/license/serializers/ledger.py` (NEW/MODIFY, ~100 lines)

```python
# New serializers for LedgerRowSerializer, CompanyUtilizationSerializer
```

### Frontend: Remove Recalculation

**File:** `frontend/src/pages/LicenseLedgerDetail.tsx` (MODIFY, ~50 lines)

**Before:**
```typescript
// Recalculate running balance locally
let balance = 0;
for (const txn of rows) {
    if (txn.type !== "COMMISSION") {
        balance += txn.amount;
    }
}
```

**After:**
```typescript
// Read running_balance from API
const balance = row.running_balance;  // ← From backend
```

**File:** `frontend/src/utils/ledgerExport.js` (MODIFY, ~60 lines)

**Before:**
```javascript
// Recalculate in PDF generation
let balance = 0;
for (const txn of rows) {
    balance += txn.amount;
}
```

**After:**
```javascript
// Read running_balance from API data
const balance = row.running_balance;  // ← From backend
```

### Tests: Parity Framework

**File:** `backend/apps/license/tests/test_parity_framework.py` (NEW, ~600 lines)

```python
# Framework: CalculationParityTest, Difference, ParityAcceptance classes
# 7 scenarios: simple, same-day, commission, rounding, zero, negative, complex
# All scenarios must pass before Phase 3B completes
```

### Tests: Characterization

**File:** `backend/apps/license/tests/test_ledger_characterization.py` (NEW, ~600 lines)

```python
# 20+ characterization tests
# - Different license types
# - Multiple companies
# - Edge cases
# All must pass before Phase 3D
```

### Tests: Regression

**File:** `frontend/src/utils/ledgerExport.test.ts` (MODIFY, +100 lines)

```typescript
// Add regression tests:
// - PDF balance matches API
// - Excel balance matches API
// Both must pass before Phase 3D
```

---

## PART 4: Risk Analysis & Mitigations

### Risk 1: Calculation Logic Error (HIGH IMPACT)
**Severity:** CRITICAL — wrong balance affects all financial reporting

**Mitigation:**
1. Parity framework ensures correctness (7 golden scenarios)
2. Characterization tests (20+ edge cases)
3. Domain expert spot-checks on production-like data
4. Feature flag: Can rollback instantly

**Gate:** 100% parity tests passing before Phase 3B completes

### Risk 2: API Breaking Change (MEDIUM IMPACT)
**Severity:** HIGH — existing consumers of ledger_detail may break

**Mitigation:**
1. New response schema documented in ADR
2. 30-day overlap: old schema still available (feature flag OFF)
3. LicensesTable.tsx (only known consumer) updated before rollout
4. Gradual rollout: 10% → 50% → 100%

**Gate:** LicensesTable.tsx verified before Phase 3D

### Risk 3: Performance Regression (MEDIUM IMPACT)
**Severity:** MEDIUM — ledger_detail endpoint becomes slower

**Mitigation:**
1. Benchmark current performance baseline
2. New calculation must complete in < 2s for typical license
3. If slower, add caching or optimize query
4. Load test before production

**Gate:** Performance test passes before Phase 3D

### Risk 4: Commission Treatment Wrong (HIGH IMPACT)
**Severity:** MEDIUM — if B4 decision is misimplemented

**Mitigation:**
1. B4 decision recorded in ADR before implementation
2. Implementation directly references ADR
3. Parity tests verify behavior (golden dataset must encode both possibilities)
4. If parity fails, reclassify as EXPECTED_CHANGE (not bug)

**Gate:** B4 decision recorded and approved before Phase 3B

---

## PART 5: Rollout Strategy

### Shadow Mode (Week 1 of production)
- Feature flag: `LEDGER_CANONICAL_ENGINE=False` (new service runs, doesn't affect API)
- Log differences between old and new calculation
- Monitor for divergences

### Gradual Activation (Weeks 2-3)
- Week 2: 10% of users see new balance
- Monitor error rates, user feedback
- If issues: rollback (feature flag OFF)
- If OK: Ramp to 50%
- Week 3: 50% of users
- Final: 100%

### Cleanup (Week 4)
- Remove legacy ledger_pdf balance calculation code
- Remove feature flag
- Finalize API contract
- Archive legacy calculation functions

---

## PART 6: Success Criteria

**Phase 3A (Infrastructure):** PASS
- [ ] Golden dataset framework created
- [ ] Feature flag infrastructure deployed
- [ ] ADR-004 (B2 decision) recorded
- [ ] ADR-005 (B4 decision) recorded

**Phase 3B (Core Implementation):** PASS
- [ ] CanonicalLedgerService implemented
- [ ] All 7 parity tests pass
- [ ] 0 semantic differences
- [ ] API schema updated
- [ ] LicenseLedgerViewSet.ledger_detail uses new service

**Phase 3C (Characterization):** PASS
- [ ] 20+ characterization tests added
- [ ] All pass on golden dataset
- [ ] All pass on production-like subset
- [ ] Domain expert spot-checks passed

**Phase 3D (Consumer Migration):** PASS
- [ ] Frontend removes all balance recalculations
- [ ] LicenseLedgerDetail.tsx reads from API
- [ ] ledgerExport.js (PDF/Excel) reads from API
- [ ] Regression tests: PDF/Excel balance match API
- [ ] Performance test: <2s for typical license
- [ ] Feature flag ready for rollout

**Go-Live:** PASS
- [ ] All criteria above met
- [ ] Shadow mode data logged
- [ ] Gradual rollout executed (10% → 50% → 100%)
- [ ] Zero customer-reported balance discrepancies

---

## PART 7: Rollback Plan (If Problems)

**If at any phase, parity tests fail:**

1. Halt Phase immediately
2. Investigate failure (is it a bug or EXPECTED_CHANGE?)
3. If bug:
   - Fix logic
   - Re-run parity tests
   - Document in incident log
4. If EXPECTED_CHANGE:
   - Reclassify in framework
   - Get business approval (via ADR)
   - Re-run parity tests
   - Continue

**If production rollout shows issues:**

1. Feature flag OFF (instant rollback)
2. New implementation stays on `feature/V2`
3. Investigate root cause
4. Fix and re-test on staging
5. Retry rollout from Phase 3D

---

## PART 8: Phase 3 → Phase 4 Handoff

### Deliverables to Phase 4 (Refactor Team)

Once Phase 3 completes, the Ledger refactoring is done. Next phases (Planning, Allocation, BOE) use same framework:

1. **CanonicalLedgerService** — Template for how other services should work (single authority)
2. **TRANSACTION_RULES** — Template for central semantic definitions
3. **Parity Framework** — Reusable for Planning/Allocation/BOE refactoring
4. **Golden Dataset** — Seed for larger comprehensive test suite

### Lessons Learned (Feedback Loop)

1. Document what went well
2. Document what was harder than expected
3. Update GATE 3 documents with real experience
4. Prepare Phase 4 with lessons applied

---

## PART 9: Timeline

```
Day 1-2:    Phase 3A (Infrastructure)
            ├─ Golden dataset framework
            ├─ Feature flag setup
            └─ ADR records (B2, B4)

Day 3-6:    Phase 3B (Core Implementation)
            ├─ CanonicalLedgerService
            ├─ Parity tests (must pass)
            └─ API update

Day 7-8:    Phase 3C (Characterization)
            ├─ Characterization tests
            └─ Domain expert review

Day 9-10:   Phase 3D (Consumer Migration)
            ├─ Frontend updates
            ├─ Regression tests
            └─ Feature flag ready

Week 2-4:   Production Rollout
            ├─ Shadow mode (Week 1)
            ├─ Gradual activation (Week 2-3)
            └─ Cleanup (Week 4)
```

---

## PART 10: Team Assignments

| Phase | Owner | Contributors | Duration |
|-------|-------|---|---|
| 3A | Architect | DevOps (feature flag), QA (framework) | 2 days |
| 3B | Backend Engineer | QA (parity tests) | 4 days |
| 3C | QA | Backend (spot-check support) | 2 days |
| 3D | Frontend Engineer | QA (regression tests) | 2 days |
| Rollout | DevOps | Backend (monitoring) | 4 weeks |

---

## Version and Status

- **Version 2.0** — Gate 3 Updated Plan, 2026-08-10
- **Status:** AWAITING APPROVAL + BUSINESS DECISIONS (B2, B4)
- **Replaces:** LEDGER_DETAIL_MIGRATION_PLAN.md
- **Framework:** All GATE 3 documents must be approved before Day 1
- **Next:** Gate 4 (Approve this plan, record B2/B4 decisions, schedule timeline)
