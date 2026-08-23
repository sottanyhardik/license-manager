# GATE 3: Master Calculation Registry — Single Source of Truth

**Status:** GATE 3 ARCHITECTURE DESIGN — Do NOT implement. For approval only.

**Purpose:** Establish the authoritative calculation registry for the entire License Manager system such that every important business/financial metric has exactly ONE calculation owner, ONE tested formula, and ONE authoritative consumer pattern.

**Scope:** 50+ business calculations across License, Planning, Allocation, BOE, Invoice, Reconciliation, and Reporting domains.

---

## PART 1: SYSTEM-WIDE CALCULATION INVENTORY

### Balance Calculations (License Domain)

| Calc ID | Metric | Business Meaning | Authoritative Owner | Function | Formula | Inputs | Output Type | Unit | Scope | Precision | Rounding | Status |
|---------|--------|------------------|--------------------|-----------|---------|---------|----|------|-------|-----------|---------|--------|
| **CALC-L-001** | License Running Balance | License balance at point in ledger after each transaction (per transaction date) | `LicenseBalanceCalculator` | `calculate_financial_balance_for_licenses` | Credit - (Debit + Allotment + Trade) floored at 0 | LicenseExportItem.cif_fc, RowDetails.cif_fc, AllotmentItems.cif_fc, LicenseTradeLine.cif_fc | Decimal | USD | License (atomic) | 2 places | ROUND_HALF_UP | AUTHORITATIVE |
| **CALC-L-002** | License Available Balance | Amount available for new allocation/BOE debit | Derived from CALC-L-001 | `calculate_financial_balance_for_licenses` | Running Balance - Pending BOE Utilization | CALC-L-001 result + pending BOE set | Decimal | USD | License | 2 places | ROUND_HALF_UP | DERIVED |
| **CALC-L-003** | License Used Balance | Amount consumed via BOE debits + Allotments + SALE trades | Derived from CALC-L-001 | `calculate_debit`, `calculate_allotment`, `calculate_trade` | Debit + Allotment + Trade | RowDetails.cif_fc, AllotmentItems.cif_fc, LicenseTradeLine.cif_fc | Decimal | USD | License | 2 places | ROUND_HALF_UP | DERIVED |
| **CALC-L-004** | License Remaining Balance | Same as Available (alias) | CALC-L-002 | — | See CALC-L-002 | — | Decimal | USD | License | 2 places | ROUND_HALF_UP | DERIVED |
| **CALC-L-005** | License Planned Balance | Running Balance - Total Planned Quantity (for a given plan type: E1, E5, E132, A3627) | Planning Domain | `services/e1_plan.py`, `e5_plan.py`, etc. | Running Balance - Planned CIF | CALC-L-001 + LicenseItemPlan rows | Decimal | USD | License × Plan Type | 2 places | ROUND_HALF_UP | DERIVED |
| **CALC-L-006** | License Allocated Balance | Running Balance - Total Allocated Quantity (from allotment allocations) | Allocation Domain | `services/allocation_service.py` | Running Balance - Allocated CIF | CALC-L-001 + allocation records | Decimal | USD | License | 2 places | ROUND_HALF_UP | DERIVED |
| **CALC-L-007** | Company Utilization (per-company within license) | Running balance attributed to a specific company/importer | Ledger Domain (Derived) | `build_financial_ledger`, `build_customs_ledger` | License Running Balance grouped by Company | CALC-L-001 by company | Decimal | USD | License × Company | 2 places | ROUND_HALF_UP | DERIVED |
| **CALC-L-008** | License Opening Balance (aka Credit) | Total export CIF for the license | `LicenseBalanceCalculator` | `calculate_credit` | SUM(LicenseExportItem.cif_fc) | LicenseExportItem.cif_fc | Decimal | USD | License | 2 places | ROUND_HALF_UP | AUTHORITATIVE |
| **CALC-L-009** | License Closing Balance | Final balance at end of reporting period | Derived from CALC-L-001 | — (snapshot of final running balance) | Running Balance @ end_date | CALC-L-001 filtered to end_date | Decimal | USD | License × Period | 2 places | ROUND_HALF_UP | DERIVED |

### Quantity Calculations (License Domain)

| Calc ID | Metric | Business Meaning | Authoritative Owner | Function | Formula | Inputs | Output Type | Unit | Scope | Precision | Status |
|---------|--------|------------------|--------------------|-----------|---------|---------|----|------|-------|-----------|--------|
| **CALC-Q-001** | License Available Quantity | Quantity available for allocation (per SION norm/item) | Item Pivot / License Overview | `LicenseImportItemsModel.available_quantity` | Import Quantity - Allocated Quantity (per item, then summed) | LicenseImportItem records | Decimal | KG/MT/LTR/PCS (per SION) | License × Item | 2 places | AUTHORITATIVE |
| **CALC-Q-002** | License Used Quantity | Quantity consumed via BOE + Allotment | Item Pivot | `build_license_row` | BOE Debit Qty + Allotment Qty | RowDetails.quantity, AllotmentItems.quantity | Decimal | Item unit | License × Item | 2 places | DERIVED |
| **CALC-Q-003** | License Remaining Quantity | Same as Available (alias) | — | — | See CALC-Q-001 | — | Decimal | Item unit | License × Item | 2 places | DERIVED |
| **CALC-Q-004** | Item Quantity Allocated | Qty allocated to an allotment (per item) | Allocation Domain | `AllotmentItems.alloted_quantity` | SUM allotted qty for (license, item) | AllotmentItems.quantity | Decimal | Item unit | License × Item | 2 places | AUTHORITATIVE |

### CIF Value Calculations (Transaction Domain)

| Calc ID | Metric | Business Meaning | Authoritative Owner | Function | Formula | Inputs | Output Type | Unit | Scope | Precision | Status |
|---------|--------|------------------|--------------------|-----------|---------|---------|----|------|-------|-----------|--------|
| **CALC-CIF-001** | License Export CIF (Total Opening Value) | Total CIF of export items | `LicenseBalanceCalculator` | `calculate_credit` | SUM(LicenseExportItem.cif_fc) | LicenseExportItem.cif_fc | Decimal | USD | License | 2 places | AUTHORITATIVE |
| **CALC-CIF-002** | BOE Debit CIF | CIF value of BOE debit row | Bill of Entry Domain | — (model field) | Direct field | RowDetails.cif_fc | Decimal | USD | BOE Row | 2 places | AUTHORITATIVE |
| **CALC-CIF-003** | Allotment Item CIF | CIF value of allocated item | Allotment Domain | — (model field) | Direct field or derived from unit price × qty | AllotmentItems.cif_fc | Decimal | USD | Allotment Item | 2 places | AUTHORITATIVE |
| **CALC-CIF-004** | Invoice Item CIF | CIF value of invoice line item | Invoice Domain | — (model field) | Direct field | InvoiceItem.cif | Decimal | USD | Invoice Item | 2 places | AUTHORITATIVE |

### Plan Calculations (Planning Domain)

| Calc ID | Metric | Business Meaning | Authoritative Owner | Function | Formula | Inputs | Output Type | Unit | Scope | Precision | Status |
|---------|--------|------------------|--------------------|-----------|---------|---------|----|------|-------|-----------|--------|
| **CALC-P-001** | E1 Planned Quantity | Planned quantity per SION E1 norm | Planning Domain | `e1_plan.py:_calculate_plan` | License opening qty × norm percentage | LicenseImportItem.quantity × SionNormNote.percentage | Decimal | Item unit | License × Item | 2 places | AUTHORITATIVE |
| **CALC-P-002** | E5 Planned Quantity | Planned quantity per SION E5 norm | Planning Domain | `e5_plan.py` | Similar to E1 | — | Decimal | Item unit | License × Item | 2 places | AUTHORITATIVE |
| **CALC-P-003** | E132 Planned Quantity | Planned quantity per SION E132 norm + milk split | Planning Domain | `e132_plan.py` | Norm % + milk_planner logic | — | Decimal | Item unit | License × Item | 2 places | AUTHORITATIVE |
| **CALC-P-004** | A3627 Planned Quantity | Auto-plan for category A3627 | Planning Domain | `a3627_auto_plan.py:compute_a3627_auto_plan` | Fixed-rate allocation logic | — | Decimal | Item unit | License × Item | 2 places | AUTHORITATIVE |
| **CALC-P-005** | Available for Planning | Quantity available to plan (not yet planned or allocated) | Planning Domain (Derived) | `item_pivot_report.py:_build_license_row` | Available Qty - Planned Qty | CALC-Q-001, CALC-P-00X | Decimal | Item unit | License × Item | 2 places | DERIVED |
| **CALC-P-006** | Plan Cap (Group) | Maximum allocatable for grouped items | Planning Domain | `plan_enforcement.py` | Sum of group caps from condition pool | SionNormCondition records | Decimal | Item unit | License × Group | 2 places | AUTHORITATIVE |
| **CALC-P-007** | Effective Planned Quantity | Manual override OR norm-derived (per item cell) | Item Pivot Report | `item_pivot_report.py:_effective_planned_quantity` | IF manual > 0 THEN manual ELSE norm | LicenseItemPlan (manual) + Plan rows (norm) | Decimal | Item unit | License × Item | 2 places | DERIVED |

### Allocation Calculations (Allotment Domain)

| Calc ID | Metric | Business Meaning | Authoritative Owner | Function | Formula | Inputs | Output Type | Unit | Scope | Precision | Status |
|---------|--------|------------------|--------------------|-----------|---------|---------|----|------|-------|-----------|--------|
| **CALC-A-001** | Allocated Quantity (per item) | Total allocated on an item | Allotment Domain | `AllotmentItems.alloted_quantity` aggregation | SUM(AllotmentItems.quantity) for (license, item) | AllotmentItems.quantity | Decimal | Item unit | License × Item | 2 places | AUTHORITATIVE |
| **CALC-A-002** | Allocated CIF (per item) | Total CIF allocated on an item | Allotment Domain | `AllotmentItems.alloted_value` aggregation | SUM(AllotmentItems.cif_fc) for (license, item) | AllotmentItems.cif_fc | Decimal | USD | License × Item | 2 places | AUTHORITATIVE |
| **CALC-A-003** | Remaining Allocation (per item) | Qty - Allocated Qty (per item) | Allotment Domain (Derived) | — | Available Qty - Allocated Qty | CALC-Q-001, CALC-A-001 | Decimal | Item unit | License × Item | 2 places | DERIVED |
| **CALC-A-004** | Over-allocation Check | Boolean: is allocated > available? | Allotment Service | `validation_service.py:validate_allocation_within_limits` | Allocated CIF > License Balance | CALC-L-001, CALC-A-002 | Boolean | — | License × Item | — | — | DERIVED |

### Reconciliation Calculations (BOE/Invoice Domain)

| Calc ID | Metric | Business Meaning | Authoritative Owner | Function | Formula | Inputs | Output Type | Unit | Scope | Precision | Status |
|---------|--------|------------------|--------------------|-----------|---------|---------|----|------|-------|-----------|--------|
| **CALC-R-001** | BOE-Invoice Difference | CIF discrepancy between BOE row and matched invoice | Reconciliation Domain | — | BOE.cif_fc - Invoice.cif | RowDetails.cif_fc, InvoiceItem.cif | Decimal | USD | BOE Row × Invoice Item | 2 places | DERIVED |
| **CALC-R-002** | Allotment-Invoice Match Status | Is this BOE debit reconciled to an invoice? | Reconciliation Domain | `resolve_boes_represented_by_invoice` | EXISTS(InvoiceBOEAllocation OR trade.boes) | InvoiceBOEAllocation, trade.boes M2M | String (MATCHED/PENDING/UNMATCHED) | — | BOE | — | — | DERIVED |
| **CALC-R-003** | Expected vs Actual Difference | Summary variance for a license period | Reconciliation Domain | — | SUM(Expected) - SUM(Actual) | All transactions | Decimal | USD | License × Period | 2 places | DERIVED |

### Report Calculations (Reporting Domain)

| Calc ID | Metric | Business Meaning | Authoritative Owner | Function | Formula | Inputs | Output Type | Unit | Scope | Precision | Status |
|---------|--------|------------------|--------------------|-----------|---------|---------|----|------|-------|-----------|--------|
| **CALC-R-LC-001** | Report License Balance (Item Pivot, License Overview, etc.) | Final balance as displayed in report header | Multiple Reports | Consumed from `LicenseBalanceCalculator` | Use CALC-L-001 | CALC-L-001 | Decimal | USD | License × Report | 2 places | DERIVED (from CALC-L-001) |
| **CALC-R-TS-001** | Report Transaction Summary | Total rows in a transactional report | Report Domain | — | COUNT(matching rows) | Filtered transaction set | Integer | — | Report × Filter | — | — | DERIVED |
| **CALC-R-PT-001** | Period Total (Report) | Sum of all transactions in period | Report Domain | — | SUM(CIF or Qty) filtered to period | Transactions in period | Decimal | USD / Unit | Report × Period | 2 places | DERIVED |

---

## PART 2: CALCULATION CLASSIFICATION

### By Risk Level

**P0 (Critical — used for financial reporting, balance sheet):**
- CALC-L-001: License Running Balance
- CALC-CIF-001: License Export CIF (Opening)
- CALC-L-008: License Opening Balance
- CALC-P-001 through CALC-P-004: All Planned Quantities

**P1 (High — affects user-facing data and decisions):**
- CALC-L-002: Available Balance
- CALC-Q-001: Available Quantity
- CALC-A-001: Allocated Quantity
- CALC-P-006: Plan Cap

**P2 (Medium — reporting/export):**
- CALC-L-007: Company Utilization
- CALC-R-001: BOE-Invoice Difference
- CALC-R-LC-001: Report License Balance

**P3 (Low — administrative/informational):**
- CALC-R-TS-001: Transaction Summary
- CALC-R-PT-001: Period Total

### By Domain Authority

**License Balance Domain:**
- Owner: `LicenseBalanceCalculator` (backend/apps/license/services/balance_calculator.py)
- Metrics: CALC-L-001, CALC-L-008, CALC-L-003
- Consumers: All reports, API, screens, exports

**Planning Domain:**
- Owner: Plan services (e1_plan.py, e5_plan.py, e132_plan.py, a3627_auto_plan.py)
- Metrics: CALC-P-001 through CALC-P-007
- Consumers: Item Pivot Report, Planned Report, Allocation validation

**Allotment Domain:**
- Owner: Allocation Service + Allotment models
- Metrics: CALC-A-001, CALC-A-002, CALC-A-004
- Consumers: Available Items, Allocation validation

**Reconciliation Domain:**
- Owner: Reconciliation services + BOE Invoice Allocation
- Metrics: CALC-R-001, CALC-R-002, CALC-R-003
- Consumers: Financial reconciliation reports

**Reporting Domain:**
- Owner: Report services (item_pivot_report, license_balance_ledger_builder, etc.)
- Metrics: CALC-R-LC-001, CALC-R-TS-001, CALC-R-PT-001
- Consumers: All reports (Item Pivot, License Overview, Financial Ledger, etc.)

---

## PART 3: DUPLICATE DETECTION

### Known Duplicates (P0 Defect)

**Ledger Running Balance — CALC-L-001 — THREE INCOMPATIBLE IMPLEMENTATIONS:**

| Location | Convention | Date Order | Commission Treatment | Company Scope | Status | Risk |
|----------|-----------|------------|---------------------|---|--------|------|
| `ledger_pdf.py:1067, 1127, 1188, 1212` (Backend) | License-wide | Purchase first, then date | COMMISSION = DEBIT | License atomic | AUTHORITATIVE | P0 |
| `LicenseLedgerDetail.tsx:339-348` (Frontend) | Per-company | Type order (OPEN→PURCH→SALE) | COMMISSION excluded | Per company | CLIENT DUPLICATE | P0 |
| `ledgerExport.js:185-191` (Frontend PDF) | Per-company | Type order (OPEN→PURCH→SALE) | COMMISSION excluded | Per company | CLIENT DUPLICATE | P0 |
| `ledgerExport.js:730-740` (Frontend Excel) | Per-company | Type order (OPEN→PURCH→SALE) | COMMISSION excluded | Per company | CLIENT DUPLICATE | P0 |

**Impact:** User sees different Balance column values on Licenses table (Transactions tab uses backend) vs. LicenseLedgerDetail page vs. PDF/Excel exports. **This is a live defect**, not a divergence risk.

**Resolution:** Requires Gate 3 business decision: which convention is authoritative? See §10 of LEDGER_DETAIL_DISPLAY_DATASET_DESIGN.md.

### Other High-Risk Duplicates

**License Balance Calculation — Multiple Entry Points (but same owner):**
- `LicenseBalanceCalculator.calculate_financial_balance_for_licenses` — Primary calculation (backend)
- `LicenseDetailsModel.get_balance_cif()` — Delegates to calculator (correct)
- `balance_snapshot.py:get_snapshot` — Bulk calculator wrapper (correct delegation)
- Risk: LOW (all delegate to single calculator)

**Planned Quantity — Item Pivot vs. Available Items:**
- Item Pivot Report: `_build_license_row` + `e1_plan.py`, etc. (authoritative for display)
- Available Items filter: `filter_service.py:apply_quantity_filters` (uses calculated qty correctly)
- Risk: LOW (consistent source)

---

## PART 4: TRANSITION REQUIREMENTS

Every metric in this registry MUST satisfy:

1. **Exactly ONE authoritative calculation function** in ONE module
2. **Exactly ONE test file** covering that function with golden dataset scenarios
3. **Exactly ONE consumer pattern** (all callers use the authoritative result)
4. **Declared scope** (License / Company / Item / BOE / Invoice / etc.)
5. **Declared precision and rounding rules** (matching FINANCIAL_NUMBER_CONTRACT.md)
6. **Documented dependencies** on other authorized metrics
7. **Feature flag for phased rollout** (if replacing a duplicate)

---

## Metrics Requiring Business Clarification (Gates 3→4)

- **B2: Running Balance Convention** — License-wide (backend) or per-company (frontend)? See LEDGER_DETAIL_DISPLAY_DATASET_DESIGN.md §10.
- **B4: Commission Treatment** — Should COMMISSION_SALE reduce the running balance?
- **P6 Cap Enforcement** — Is plan cap group-wide or per-item? Documented but confirm during Phase 3B.

---

## This Registry Grows Incrementally

- **Verified Against Code:** Every row above was traced to current source (HEAD `feature/V2`, 2026-08-10).
- **Add on Verification:** New rows only after reading and tracing the authoritative function to current code.
- **Do Not Speculate:** If a calculation is uncertain, mark as TBD, do not assume.
- **Cross-reference CALCULATION_OWNERSHIP.md:** Extended version of Item Pivot audit, same discipline.

---

## Versioning

- **Version 1.0** — Gate 3 Architecture Design, 2026-08-10
- **Updated by:** Solutions Architect
- **Next Update:** Post-approval, when implementation phase begins (requires business decision on B2, B4)
