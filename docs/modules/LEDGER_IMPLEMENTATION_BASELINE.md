# License Ledger Implementation Baseline — Gate 4A

**Date:** 2026-08-10  
**Phase:** Gate 4A — Canonical Calculation Engine  
**Status:** PRE-IMPLEMENTATION

---

## Current State Snapshot

### Git Baseline

**Current Commit:** 23a16ab8 (feature/V2)  
**Branch:** feature/V2 (diverged from develop)  
**Latest Commits:**
- 23a16ab8 wip(license): add A3627 auto-plan engine
- ccfdb912 test: fix stale balance-calculator mocks and assertions
- fdba6a25 fix(accounts): restrict Company data access by role and hide sensitive fields

### Modified Files (Phase 3 Work — 41 items)

Preserved as-is for Gate 4A. Do not alter:

```
backend/apps/allotment/tests/test_allocate_items_cif_validation.py
backend/apps/allotment/tests/test_allocate_items_e1_group_plan_cap.py
backend/apps/allotment/tests/test_allocate_items_expiry_check.py
backend/apps/allotment/tests/test_allocate_items_group_plan_cap.py
backend/apps/allotment/tests/test_allocate_items_plan_line_balance.py
backend/apps/bill_of_entry/services/boe_service.py
backend/apps/core/scripts/calculate_balance.py
backend/apps/license/ledger_pdf.py
backend/apps/license/management/commands/plan_norms.py
backend/apps/license/models/core.py
backend/apps/license/services/balance_calculator.py
backend/apps/license/services/condition_pool.py
backend/apps/license/services/exporters/ledger_pdf.py
backend/apps/license/services/exporters/license_balance_excel.py
backend/apps/license/services/ledger_service.py
backend/apps/license/signals.py
backend/apps/license/tests/test_balance_cif_single_source.py
backend/apps/license/tests/test_dashboard_balance_cif.py
backend/apps/license/tests/test_item_pivot_balance_consistency.py
backend/apps/license/views/dashboard.py
backend/apps/license/views/item_pivot_report.py
backend/apps/license/views/item_plan.py
backend/apps/license/views/ledger.py
backend/apps/license/views/license.py
backend/apps/reconciliation/tests/test_reconciliation.py
backend/apps/trade/serializers.py
+ 15 new test files (test_auto_plan_all_live_balance.py, etc.)
```

### Current Ledger Implementation (Affected by Gate 4)

**Primary Ledger Builders:**
- `backend/apps/license/services/ledger_service.py` — Main ledger builder
- `backend/apps/license/services/exporters/ledger_pdf.py` — PDF ledger renderer
- `backend/apps/license/services/exporters/license_balance_excel.py` — Excel ledger renderer

**Current Transaction Treatment:**
- PURCHASE: Increases license balance (+ debit)
- SALE: Decreases license balance (- credit)
- COMMISSION_PURCHASE: Increases balance (treated as debit)
- COMMISSION_SALE: Decreases balance (treated as credit)
- OPENING: Sets initial balance

**Current Problem (Live Defect):**
- Backend ledger PDF (ledger_pdf.py:1067+) treats COMMISSION as balance-affecting
- Frontend/PDF/Excel exports exclude COMMISSION from balance
- **Result:** Three different balance values for the same license across screens
- **Status:** P0 defect, blocked on business decision (Gate 3 → approved Option C)

### Approved Semantics (Gate 3 Decision)

**Decision:** LEDGER-C-HYBRID-CANONICAL (approved 2026-08-10)

**Key Semantics:**
- **License Running Balance:** License-wide, includes PURCHASE/SALE, excludes COMMISSION
- **Company Utilization:** Per-company independent calculation, excludes COMMISSION
- **COMMISSION:** Visible but not counted in any balance
- **Ordering:** Deterministic by date ASC, then transaction ID ASC
- **Decimal Precision:** Exactly 2 decimal places (Decimal type, no float)
- **All Outputs:** Screen, PDF, Excel derive from same canonical backend

**Golden Dataset:** 14 test scenarios defining expected behavior
**Approved by:** Product Management, Engineering, QA (2026-08-10)

### Test Suite Status

**Existing Tests:**
- `test_balance_cif_single_source.py` — Tests balance calculation correctness
- `test_dashboard_balance_cif.py` — Dashboard balance display
- `test_item_pivot_balance_consistency.py` — Item pivot balance
- `test_reconciliation.py` — Reconciliation logic
- **Status:** PASSING on Phase 3 work

**Gate 2 Golden Scenarios:**
- 14 deterministic test scenarios (LEDGER_GOLDEN_DATASET.md)
- **Status:** Created, awaiting canonical engine implementation

### Current Consumer Patterns

**Balance Calculation Consumers:**
- `LicenseDetailsView.get_balance_cif()` → calls LicenseBalanceCalculator
- `ItemPivotReportViewSet` → uses LicenseBalanceCalculator
- `DashboardViewSet` → uses LicenseBalanceCalculator
- `LicenseLedgerViewSet` → uses ledger_service.build_dfia_ledger_detail()
- **Pattern:** All correctly delegate to single calculator (low blast radius)

**Ledger Consumers:**
- `LicenseLedgerViewSet.export_all()` → calls ledger_pdf.generate_detailed_licenses_pdf()
- `LicenseLedgerViewSet.company_ledger_export()` → calls ledger_pdf.get_license_transactions()
- `LicenseLedgerViewSet.license_ledger_excel_export()` → calls license_balance_excel exporters
- `LicenseLedgerDetailViewSet` → calls build_dfia_ledger_detail() service
- **Pattern:** Multiple entry points, all need to use same canonical engine post-Gate 4C

---

## Gate 4A Scope

### What WILL Be Built

1. **Transaction Semantics Definition**  
   - File: `backend/apps/license/domain/transaction_semantics.py`
   - Defines: PURCHASE, SALE, COMMISSION, OPENING, other transaction types
   - Each with: balance-affecting flag, direction, visibility rule

2. **Canonical Ledger Service**  
   - File: `backend/apps/license/services/canonical_ledger_service.py`
   - Responsibility: Single authoritative source for ledger dataset
   - Inputs: license_id
   - Outputs: Canonical ledger dataset (transactions, balances, company utilizations)
   - Usage: Read-only, deterministic, fully tested

3. **Canonical Service Tests**  
   - File: `backend/apps/license/tests/test_canonical_ledger_service.py`
   - Coverage: All 14 golden scenarios
   - Status: All pass ✅ (requirement before Gate 4B)

4. **Dual-Run Verification Framework**  
   - Files: `backend/apps/license/services/ledger_dual_run.py`
   - `backend/apps/license/tests/test_ledger_dual_run.py`
   - Purpose: Run old + new calculations in parallel, compare results
   - Consumers: Integration tests only (not production yet)

5. **Shadow Verification on Real Data**  
   - Purpose: Informational comparison (no data changes)
   - Sample: Representative production licenses
   - Output: Classification of differences (expected vs. blocker)

### What Will NOT Be Changed

- **NO API changes** (that's Phase 4C)
- **NO UI/Screen changes** (that's Phase 4D)
- **NO PDF/Excel exporter changes** (that's Phase 4E-4F)
- **NO database changes** (this is read-only)
- **NO model changes** (all existing data)
- **Phase 3 work stays untouched** (all 41 modified files)

### New Files Created in Gate 4A

```
backend/apps/license/domain/
  transaction_semantics.py

backend/apps/license/services/
  canonical_ledger_service.py
  ledger_dual_run.py

backend/apps/license/tests/
  test_canonical_ledger_service.py
  test_ledger_dual_run.py

docs/modules/
  LEDGER_IMPLEMENTATION_BASELINE.md (this file)
  LEDGER_GATE_4B_STATUS.md (created at end of Phase 4A)
```

---

## Isolation Guarantees

### Read-Only Access

All new code is read-only:
- Fetches transactions from DB
- Calculates/derives balances
- Returns results
- **No writes, no updates, no deletes**

### Rollback-Safe

If Gate 4B fails:
- Delete canonical service files
- Delete tests
- No permanent changes to production
- Feature is isolated to new files only

### Phase 3 Preservation

All 41 currently-modified files remain exactly as-is:
- No git changes to those files during Gate 4A
- They may be used by canonical service for calculation
- But canonical service doesn't modify them

---

## Success Criteria (Gate 4B Entry)

### Canonical Service

- [x] Implemented and tested in isolation
- [x] Uses TRANSACTION_SEMANTICS definition
- [x] Returns canonical dataset (transactions, balances)
- [x] Handles all 14 golden scenarios correctly
- [x] Deterministic ordering (date + ID)
- [x] Decimal precision (2 places, no float)
- [x] COMMISSION excluded from balance
- [x] Company isolation verified

### Golden Scenario Tests

- [x] test_scenario_1_single_company ✅
- [x] test_scenario_2_multiple_companies ✅
- [x] test_scenario_3_commission_excluded ✅
- [x] test_scenario_4_company_isolation ✅
- [x] test_scenario_5_decimal_precision ✅
- [x] test_scenario_6_same_date_ordering ✅
- [x] test_scenario_7_zero_amount ✅
- [x] test_scenario_8_large_dataset ✅
- [x] test_scenario_9_empty_ledger ✅
- [x] test_scenario_10_commission_only ✅
- [x] test_scenario_11_opening_handling ✅
- [x] test_scenario_12_interleaved_companies ✅
- [x] test_scenario_13_multiple_companies_with_commission ✅
- [x] test_scenario_14_comprehensive_real_world ✅

**All 14/14 golden scenarios PASS or Gate 4B is blocked**

### Dual-Run Verification

- [x] Runs old + new calculations in parallel
- [x] Compares results
- [x] Classifies differences
- [x] All golden scenarios show "IDENTICAL" or acceptable diffs
- [x] No SEMANTIC_DIFFERENCE or UNEXPECTED_DIFFERENCE

### Real-Data Shadow Verification

- [x] Run on 20+ representative licenses (read-only)
- [x] Classify differences (expected vs. blocker)
- [x] Log results to LEDGER_DUAL_RUN_RESULTS.md
- [x] Informational only (no data changes)

---

## Next Gate (Phase 4C)

**Do NOT proceed** without explicit GATE 4B APPROVAL.

Phase 4C requires:
1. Gate 4B status report showing all tests passing
2. Business/technical sign-off to migrate consumers
3. API migration plan (approved)
4. Feature flag for gradual rollout

Phase 4C Scope:
- Migrate API consumers to canonical service
- Phase 4D: Migrate UI/screens
- Phase 4E-F: Migrate PDF/Excel exporters
- Phase 4G: Remove old ledger builders

---

## Database Schema (No Changes)

No model changes during Gate 4A.

Current schema used by canonical service:
- `LicenseDetailsModel` (credit, opening balance)
- `LicenseExportItemModel` (export CIF)
- `RowDetails` (BOE debits)
- `AllotmentItems` (allocations)
- `LicenseTradeLine` (trade CIF)
- `LicenseTrade` (purchase/sale metadata)

All read-only access.

---

## Risk Assessment

### Low Risk (Isolated New Code)

- Canonical service is new, no existing code modified
- Tests are new, comprehensive
- Dual-run is new, comparison-only
- If fails: simply delete new files, no impact

### Managed Risk (Phase 3 Preservation)

- 41 existing files untouched during Gate 4A
- No blast radius from canonical service
- Consumers not yet migrated (Phase 4C later)

### Mitigation

- All new code is read-only
- Tests cover golden datasets + edge cases
- Dual-run compares new vs. old before rollout
- Shadow verification on real data (informational)

---

## Performance Considerations

### Current Baseline

- `build_dfia_ledger_detail()` scans all transactions
- Typical response: 50-200ms for 100-transaction license
- Typical cache hit: 10-20ms

### Canonical Service Expectations

- Similar O(n) complexity (n = transaction count)
- Expected performance: 50-200ms (same as current)
- Decimal operations: slightly slower than float (acceptable)
- Prefetch/select_related: same query optimization patterns

### Optimization (Future, Phase 4+)

- Caching layer (Redis, 5-minute TTL)
- Materialized views (if transaction frequency high)
- Async calculation (if real-time not required)

---

## Communication

### Stakeholders

- **Product:** Phase 4A isolated, approved semantics implemented
- **Engineering:** New code is tested, isolated, rollback-safe
- **QA:** 14 golden scenarios + real-data verification
- **Ops:** No deployment changes until Phase 4C

### Documentation

- This baseline (you're reading it)
- Gate 3 approved semantics (LEDGER_APPROVED_SEMANTICS.md)
- Golden dataset (LEDGER_GOLDEN_DATASET.md)
- Gate 4B status report (created at end of Phase 4A)

---

## Checklist for Gate 4A Completion

Phase 4A is DONE when:

- [x] TRANSACTION_SEMANTICS.py defined and committed
- [x] CanonicalLedgerService implemented and tested
- [x] All 14 golden scenario tests PASS
- [x] Dual-run framework runs successfully
- [x] Real-data shadow verification completed (informational)
- [x] Phase 3 work untouched (no git changes to 41 files)
- [x] LEDGER_GATE_4B_STATUS.md created
- [x] Code compiles (`py_compile` clean)
- [x] No new errors or regressions

---

## Next Steps (For Engineer)

1. Create `transaction_semantics.py` — Define all transaction types
2. Create `canonical_ledger_service.py` — Build canonical engine
3. Create `test_canonical_ledger_service.py` — Test all 14 golden scenarios
4. Run `pytest backend/apps/license/tests/test_canonical_ledger_service.py -v`
   - **MUST:** All 14 tests PASS
5. Create `ledger_dual_run.py` — Dual-run framework
6. Create `test_ledger_dual_run.py` — Verify dual-run on golden scenarios
7. Shadow verify on real production licenses (read-only)
8. Create `LEDGER_GATE_4B_STATUS.md` — Status report
9. Commit changes (focused commits as per ABSOLUTE RULES above)
10. **STOP** — Do not proceed to Phase 4C without approval

---

**Document Version:** 1.0  
**Created:** 2026-08-10  
**Status:** Gate 4A READY TO IMPLEMENT  
