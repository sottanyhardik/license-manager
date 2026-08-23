# GATE 3: Calculation Dependency Graph

**Status:** GATE 3 ARCHITECTURE DESIGN — Do NOT implement. For approval only.

**Purpose:** Map all calculation dependencies across the system to identify:
1. Authoritative calculations (no dependencies, pure sources)
2. Derived calculations (depend on authorized metrics)
3. Circular dependencies (if any exist — blockers for migration)
4. Calculation isolation (can failures cascade?)

---

## System-Wide Dependency Graph

```
LAYER 0: SOURCE DATA (Immutable records — no calculation)
════════════════════════════════════════════════════════════════
  LicenseExportItem (cif_fc)  ←─ Field value only, no calc
  LicenseImportItem (quantity, available_quantity)  ←─ Field value
  RowDetails (cif_fc, quantity)  ←─ Field value
  AllotmentItems (quantity, cif_fc)  ←─ Field value
  LicenseTradeLine (cif_fc)  ←─ Field value
  InvoiceItem (cif)  ←─ Field value
  SionNormNote (percentage)  ←─ Field value
  Company (master data)  ←─ Field value


LAYER 1: AUTHORITATIVE CALCULATIONS (Direct from source data)
════════════════════════════════════════════════════════════════

CALC-L-008: License Opening (Credit)
    Owner: LicenseBalanceCalculator.calculate_credit
    Formula: SUM(LicenseExportItem.cif_fc)
    Dependencies: LicenseExportItem (Layer 0)
    Consumers: CALC-L-001, Reports

CALC-L-003: License Debit Component
    Owner: LicenseBalanceCalculator.calculate_debit
    Formula: SUM(RowDetails.cif_fc WHERE NOT in BOE-represented set)
    Dependencies: RowDetails (Layer 0), BOE representation rules
    Consumers: CALC-L-001, Reports

CALC-A-Debit: Allotment Component
    Owner: LicenseBalanceCalculator.calculate_allotment
    Formula: SUM(AllotmentItems.cif_fc WHERE NOT BOE-linked)
    Dependencies: AllotmentItems (Layer 0)
    Consumers: CALC-L-001, Reports

CALC-T-Debit: Trade Component
    Owner: LicenseBalanceCalculator.calculate_trade_debit
    Formula: SUM(LicenseTradeLine.cif_fc FOR SALE trades)
    Dependencies: LicenseTradeLine (Layer 0), Trade direction
    Consumers: CALC-L-001, Reports

CALC-Q-001: Available Quantity (per item)
    Owner: LicenseImportItemsModel.available_quantity (property)
    Formula: Import Qty - Allocated Qty (per item)
    Dependencies: LicenseImportItem.quantity, AllotmentItems aggregation
    Consumers: CALC-P-005, Item Pivot, Allocation validation

CALC-P-001: E1 Planned Quantity
    Owner: e1_plan.py:_calculate_plan
    Formula: License opening qty × norm %
    Dependencies: LicenseImportItem.quantity, SionNormNote.percentage
    Consumers: CALC-P-005, Item Pivot, Plan enforcement

CALC-P-002: E5 Planned Quantity
    Owner: e5_plan.py
    Formula: Similar to E1
    Dependencies: LicenseImportItem.quantity, SionNormNote.percentage
    Consumers: CALC-P-005, Item Pivot, Plan enforcement

CALC-P-003: E132 Planned Quantity
    Owner: e132_plan.py + milk_planner.py (special cases)
    Formula: Norm % + milk split logic
    Dependencies: LicenseImportItem.quantity, SionNormNote, milk_planner rules
    Consumers: CALC-P-005, Item Pivot, Plan enforcement

CALC-P-004: A3627 Auto Plan
    Owner: a3627_auto_plan.py:compute_a3627_auto_plan
    Formula: Fixed-rate allocation + category matching
    Dependencies: License category, SION norms
    Consumers: CALC-P-005, Plan enforcement

CALC-A-001: Allocated Quantity (per item)
    Owner: AllotmentItems.alloted_quantity aggregation
    Formula: SUM(AllotmentItems.quantity) for (license, item)
    Dependencies: AllotmentItems (Layer 0)
    Consumers: CALC-Q-001, Plan enforcement

CALC-CIF-001: License Export CIF
    Owner: LicenseBalanceCalculator.calculate_credit
    Formula: SUM(LicenseExportItem.cif_fc)
    Dependencies: LicenseExportItem (Layer 0)
    Consumers: Reports, License overview

CALC-R-001: BOE-Invoice Difference
    Owner: Reconciliation service (implicit)
    Formula: BOE.cif_fc - Invoice.cif
    Dependencies: RowDetails.cif_fc, InvoiceItem.cif
    Consumers: Reconciliation reports


LAYER 2: PRIMARY DERIVED CALCULATIONS (Depend on Layer 1)
════════════════════════════════════════════════════════════════

CALC-L-001: License Running Balance ⭐ PRIMARY
    Owner: LicenseBalanceCalculator.calculate_financial_balance_for_licenses
    Formula: CALC-L-008 - (CALC-L-003 + CALC-A-Debit + CALC-T-Debit) floored at 0
    Dependencies: CALC-L-008, CALC-L-003, CALC-A-Debit, CALC-T-Debit (Layer 1)
    Consumers: CALC-L-002, CALC-L-006, ALL REPORTS, Ledger detail, PDF/Excel
    Status: THIS IS THE AUTHORITATIVE SOURCE FOR ALL FINANCIAL REPORTING
    Risk: CRITICAL — any change cascades to every report

CALC-P-005: Available for Planning
    Owner: item_pivot_report.py:_build_license_row
    Formula: CALC-Q-001 - SUM(CALC-P-00X for all plan types)
    Dependencies: CALC-Q-001, CALC-P-001, CALC-P-002, CALC-P-003, CALC-P-004
    Consumers: Item Pivot, Available Items filter
    Status: Depends on all plan types, isolated from financial balance

CALC-A-002: Allocated CIF (per item)
    Owner: AllotmentItems aggregation
    Formula: SUM(AllotmentItems.cif_fc) for (license, item)
    Dependencies: AllotmentItems (Layer 0)
    Consumers: CALC-L-003 component (if applicable), reports

CALC-P-006: Plan Cap (Group)
    Owner: plan_enforcement.py + condition_pool.py
    Formula: SUM(group caps from SionNormCondition)
    Dependencies: SionNormCondition (Layer 0), group membership
    Consumers: Plan enforcement validation


LAYER 3: DERIVED DISPLAY CALCULATIONS (Depend on Layer 1 or 2)
════════════════════════════════════════════════════════════════

CALC-L-002: Available Balance
    Owner: Derived from CALC-L-001
    Formula: CALC-L-001 - Pending BOE utilization
    Dependencies: CALC-L-001, pending BOE set
    Consumers: UI display, allocation validation, reports

CALC-L-006: Company Utilization (per-company)
    Owner: build_financial_ledger, build_customs_ledger
    Formula: CALC-L-001 grouped and attributed by Company
    Dependencies: CALC-L-001, Company grouping rules
    Consumers: Ledger detail, Financial ledger report
    ⚠️ CAVEAT: Backend uses license-wide order; frontend regroups by company
              (P0 defect source — see GATE3_DUPLICATE_CALCULATIONS.md)

CALC-L-007: License Planned Balance
    Owner: Planning domain (implicit)
    Formula: CALC-L-001 - CALC-P-005
    Dependencies: CALC-L-001, CALC-P-005
    Consumers: Planning UI, available-for-plan calculations

CALC-L-009: License Closing Balance
    Owner: Report generation
    Formula: CALC-L-001 snapshot at end_date
    Dependencies: CALC-L-001, period boundaries
    Consumers: Financial reconciliation reports, period summaries

CALC-R-LC-001: Report License Balance
    Owner: All reports
    Formula: Use CALC-L-001 directly
    Dependencies: CALC-L-001
    Consumers: All reports (Item Pivot, Financial Ledger, etc.)
    MUST RULE: No report may re-derive this. Consume from API.


LAYER 4: SECONDARY DERIVED / PRESENTATIONAL (Depend on Layer 2 or 3)
════════════════════════════════════════════════════════════════

CALC-R-TS-001: Report Transaction Summary
    Owner: Report generation
    Formula: COUNT(matching rows)
    Dependencies: Row filters (business logic, not calculation)
    Consumers: Report headers, summaries

CALC-R-PT-001: Period Total
    Owner: Report generation
    Formula: SUM(CIF or Qty) filtered to period
    Dependencies: Row selections, aggregation rules
    Consumers: Report footers, summaries

CALC-R-002: BOE-Invoice Match Status
    Owner: reconciliation services
    Formula: EXISTS(InvoiceBOEAllocation OR trade.boes)
    Dependencies: InvoiceBOEAllocation, trade.boes M2M (Layer 0)
    Consumers: Reconciliation reports, ledger status labels

```

---

## Dependency Adjacency Matrix

```
                          │ L008 │ L003 │ A-Deb│ T-Deb│ Q-001│ P-00X│ A-001│ CIF-1│ R-001│ L-001│ P-005│ A-002│ P-006│ L-002│ L-006│ L-007│ L-009│
──────────────────────────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼──────
L-001 (Running Balance)   │◁─ ↲  │◁─ ↲  │◁─ ↲  │◁─ ↲  │      │      │      │  =   │      │      │      │      │      │      │      │      │
L-002 (Available)         │      │      │      │      │      │      │      │      │      │──→  │      │      │      │      │      │      │
P-005 (Avail for Plan)    │      │      │      │      │◁─ ↲  │◁─ ↲  │      │      │      │      │      │      │      │      │      │      │
L-006 (Company Util)      │      │      │      │      │      │      │      │      │      │──→  │      │      │      │      │      │      │
L-007 (Planned Balance)   │      │      │      │      │      │      │      │      │      │──→  │──→  │      │      │      │      │      │

Legend:
◁─ ↲  = Direct dependency (calculation input)
──→  = Dependent consumer (calculated output)
=    = Same as (alias)
```

---

## Circular Dependencies Check

**Authoritative Pass (Layer 1):** NONE — all Layer 1 calculations depend only on Layer 0 (immutable source data). No cycles.

**Derived Pass (Layer 2+):** NONE — dependency direction is strictly acyclic:
- CALC-L-001 depends on Layer 1, fed by Layer 2
- CALC-L-002 depends on CALC-L-001 (Layer 2 → Layer 3)
- CALC-L-006 depends on CALC-L-001 (Layer 2 → Layer 3)

**RESULT:** No circular dependencies. Safe to migrate any layer without deadlock risk.

---

## Calculation Isolation Analysis

**Critical Chain (Monolithic — cannot fail independently):**
```
Layer 0 → CALC-L-008, CALC-L-003, CALC-A-Debit, CALC-T-Debit
    ↓↓↓↓↓
CALC-L-001 (Running Balance)
    ↓↓↓↓↓
L-002, L-006, L-007, ALL REPORTS
```

**Implication:** If CALC-L-001 is wrong, every report using it is wrong. No isolation. This justifies the P0 priority and the need for a *golden dataset* test suite before activation.

**Isolated Chain (Can fail independently):**
```
Layer 0 → CALC-Q-001, CALC-P-001...004, CALC-A-001
    ↓↓↓
CALC-P-005 (Available for Planning)
    ↓↓↓
Item Pivot, Available Items
```

**Implication:** If CALC-P-005 is wrong, planning is affected but financial balance is unaffected. Can be tested independently. Same for allocation chain.

**Recommendation for Migration:**
- Migrate CALC-L-001 first (high blast radius, critical path)
- Validate with golden dataset before activating
- Plan phase separately depends only on this, can follow immediately
- Allocation phase follows the same rule

---

## Dependency Validation Rules (for Gate 4 Implementation)

**Before changing any Layer 1 calculation:**
1. Verify Layer 0 data exists and is immutable
2. Add test for each edge case (zero, negative, missing, NULL)
3. Validate precision/rounding at calculation boundary

**Before activating any Layer 2 calculation:**
1. Verify all Layer 1 dependencies are stable
2. Run parity tests (old vs. new CALC-L-001 on golden dataset)
3. Validate all Layer 3+ consumers read result, not recalculate

**Before any Layer 3 consumer goes live:**
1. Verify it reads from Layer 2, does not re-derive
2. Validate precision is preserved at serialization boundary
3. Verify API contract is stable (no field renames mid-migration)

---

## Cross-Domain Integration Points

### License → Planning Integration
- **Boundary:** CALC-L-001 → CALC-P-005
- **Contract:** License provides running balance; Planning derives available qty
- **Risk:** If Planning assumes a different balance convention, CALC-P-005 is wrong
- **Mitigation:** Explicit dependency documented here; tested before Phase 3B

### License → Allocation Integration
- **Boundary:** CALC-L-001 → Allocation validation
- **Contract:** Allocation checks CALC-L-001 >= allocation amount
- **Risk:** If allocation uses stale balance, over-allocates
- **Mitigation:** Allocation reads live CALC-L-001, not cache

### License → Reconciliation Integration
- **Boundary:** CALC-L-001 ← CALC-R-001 feedback
- **Contract:** BOE-Invoice matches feed back into CALC-L-003 (debit component)
- **Risk:** If reconciliation changes debit rules, CALC-L-001 changes
- **Mitigation:** Clear rule: BOE representation rules are calculated once, centralized

---

## This Graph as Test Specification

Each edge (→) in the graph becomes a test:
- **Source-to-Layer-1 tests:** Verify calculation against source data
- **Layer-1-to-Layer-2 tests:** Verify dependency contract
- **Layer-2-to-Layer-3 tests:** Verify derived logic (parity tests)
- **Layer-3-to-Consumer tests:** Verify consumption pattern (golden dataset)

Total estimated test coverage: **50+ characterization tests, 20+ integration tests**.

---

## Version and Status

- **Version 1.0** — Gate 3 Architecture Design, 2026-08-10
- **Updated by:** Solutions Architect
- **Next Update:** Post-approval, Phase 3A (golden dataset design)
