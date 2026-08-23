# GATE 3: Duplicate Calculation Audit

**Status:** GATE 3 ARCHITECTURE DESIGN — Do NOT implement. For approval only.

**Purpose:** Comprehensive audit of duplicate financial calculations across the codebase to identify migration targets.

---

## P0 DEFECT: License Ledger Running Balance (THREE INCOMPATIBLE IMPLEMENTATIONS)

### Summary
**Same metric, three different formulas, two different conventions.** User sees different Balance values on different screens.

### Duplicate Instances

#### Instance 1: Backend (AUTHORITATIVE)
- **Location:** `backend/apps/license/services/exporters/ledger_pdf.py:1067, 1127, 1188, 1212`
- **Function:** `build_dfia_ledger_detail`, `build_incentive_ledger_detail`
- **Convention:** License-wide, purchase-first-then-date order
- **Commission Treatment:** COMMISSION_SALE is a DEBIT (reduces balance)
- **Per-Company:** No (atomic license balance)
- **Precision:** 2dp
- **Status:** Backend returns this in API; LicensesTable.tsx:616 (Transactions tab) reads it

**Code Pattern:**
```python
balance = opening_balance
for txn in transactions_by_purchase_then_date:
    if txn.type in ("PURCHASE", "COMMISSION_SALE"):
        balance -= txn.amount  # ← Commissions are debits
    elif txn.type == "SALE":
        balance -= txn.amount
    running_balances.append(balance)
```

#### Instance 2: Frontend — LicenseLedgerDetail Page
- **Location:** `frontend/src/pages/LicenseLedgerDetail.tsx:339-348`
- **Convention:** Per-company (restarts at zero), type-ordered (OPENING→PURCHASE→SALE)
- **Commission Treatment:** COMMISSION_SALE is EXCLUDED (does not affect balance)
- **Per-Company:** Yes (restarts for each company)
- **Precision:** 2dp displayed
- **Status:** This screen shows different Balance column than Transactions tab

**Code Pattern:**
```javascript
let balance = 0;
for (const company of groupedByCompany) {
    balance = 0;  // ← Restart per company
    for (const txn of company.transactions) {  // ← Type-ordered, not date-ordered
        if (txn.type !== "COMMISSION_SALE") {  // ← Commission excluded
            if (txn.type === "PURCHASE") balance += txn.amount;
            else if (txn.type === "SALE") balance -= txn.amount;
        }
        result.push({ ...txn, balance });
    }
}
```

#### Instance 3: Frontend — PDF Export
- **Location:** `frontend/src/utils/ledgerExport.js:185-191`
- **Convention:** Per-company (restarts at zero), type-ordered
- **Commission Treatment:** COMMISSION_SALE is EXCLUDED
- **Per-Company:** Yes (identical to Instance 2)
- **Precision:** 2dp
- **Status:** PDF file downloaded from LicenseLedgerDetail page

**Code Pattern:** Identical to Instance 2

#### Instance 4: Frontend — Excel Export
- **Location:** `frontend/src/utils/ledgerExport.js:730-740`
- **Convention:** Per-company (restarts at zero), type-ordered
- **Commission Treatment:** COMMISSION_SALE is EXCLUDED
- **Per-Company:** Yes (identical to Instances 2 and 3)
- **Precision:** 2dp
- **Status:** Excel file downloaded from LicenseLedgerDetail page

**Code Pattern:** Identical to Instances 2 and 3

### Impact Analysis

| Screen/Export | Uses | Running Balance Convention | Commission Treated As | Issue |
|---|---|---|---|---|
| Licenses table (Transactions tab) | Backend API | License-wide, date-ordered | DEBIT | GOLD STANDARD |
| LicenseLedgerDetail page | Frontend recalc | Per-company, type-ordered | EXCLUDED | P0 DEFECT — differs from tab |
| PDF export from Ledger Detail | Frontend recalc | Per-company, type-ordered | EXCLUDED | P0 DEFECT — identical to page |
| Excel export from Ledger Detail | Frontend recalc | Per-company, type-ordered | EXCLUDED | P0 DEFECT — identical to page |

### Verification Evidence

**Filename → Line Mapping (verified by reading code 2026-08-10):**

```
Backend:
  ledger_pdf.py:1067 → build_dfia_ledger_detail() start
  ledger_pdf.py:1127 → balance = opening; for-loop balance calc
  ledger_pdf.py:1188 → build_incentive_ledger_detail() parallel logic
  
Frontend:
  LicenseLedgerDetail.tsx:339-348 → groupedByCompany loop, per-company restart
  ledgerExport.js:118-119 → Type order comment (OPENING→PURCHASE→SALE)
  ledgerExport.js:185-191 → PDF balance loop, commission exclusion
  ledgerExport.js:730-740 → Excel balance loop, commission exclusion
```

### Business Context (From LEDGER_DETAIL_DISPLAY_DATASET_DESIGN.md)

**B2: Running Balance Convention** (blocking gate for Phase 3B)

- **Option A (Backend current):** License-wide, date-ordered, commissions=debit
- **Option B (Frontend current):** Per-company, type-ordered, commissions=excluded
- **Status:** Unresolved; requires business decision

---

## P1 DUPLICATES: License Balance Calculation (SAME OWNER, MULTIPLE ENTRY POINTS)

### Risk Assessment: LOW (all delegate to single calculator)

#### Locations
1. `LicenseBalanceCalculator.calculate_financial_balance_for_licenses` — Primary
2. `LicenseDetailsModel.get_balance_cif()` — Delegates to calculator
3. `balance_snapshot.py:get_snapshot` — Bulk wrapper, delegates
4. `license_balance_ledger_builder.py` — Uses calculator result
5. `item_pivot_report.py` — Uses calculator result

#### Result
All consumers correctly delegate to single authoritative source. **No risk.**

**Maintenance rule:** Any new consumer must use `LicenseBalanceCalculator`, never re-derive.

---

## P2 DUPLICATES: Planned Quantity (Item Pivot + Plan Enforcement)

### Risk Assessment: LOW (same source)

#### Item Pivot Report (`item_pivot_report.py`)
- **Function:** `_build_license_row`
- **Source:** `e1_plan.py`, `e5_plan.py`, `e132_plan.py`, `a3627_auto_plan.py`
- **Output:** Planned quantity per item × plan type

#### Plan Enforcement (`plan_enforcement.py`)
- **Function:** `validate_plan_line_cap`
- **Source:** Same services (e1_plan, etc.) + condition_pool
- **Output:** Check if planned qty exceeds cap

#### Status
Both use identical source (plan services). Plan enforcement correctly reads Item Pivot output, not recalculating. **No duplication risk.**

---

## P3 DUPLICATES: BOE Debit Matching (Multiple Status Labels)

### Risk Assessment: MEDIUM (semantic drift possible)

#### Instance 1: Backend Reconciliation
- **Location:** `reconciliation/models.py` — `InvoiceBOEAllocation`
- **Status values:** ACTIVE, PARTIAL, CANCELLED
- **Logic:** Formal allocation records determine match status

#### Instance 2: Frontend Ledger Detail
- **Location:** `ledgerExport.js:200-230` — `BOE_STATUS` labels
- **Status values:** "MATCHED", "PENDING", "UNMATCHED"
- **Logic:** Heuristic based on transaction type

#### Risk
If backend adds new reconciliation rule (e.g., partial match threshold), frontend's heuristic will not auto-sync. **Maintenance burden.**

**Migration plan:** Centralize status logic in backend; frontend reads from API, not heuristic.

---

## Consolidated Duplicate Summary Table

| Metric | Location A | Location B | Location C | Same Formula? | Risk | Action |
|--------|-----------|-----------|-----------|---|---|---|
| **Ledger Running Balance** | ledger_pdf.py:1067 | LicenseLedgerDetail.tsx:339 | ledgerExport.js:185 | NO ✗ | P0 | **GATE 3 TARGET** |
| **License Balance CIF** | LicenseBalanceCalculator | LicenseDetailsModel.get_balance_cif | balance_snapshot.py | YES ✓ | LOW | No action (delegates correctly) |
| **Planned Quantity** | item_pivot_report.py | plan_enforcement.py | — | YES ✓ | LOW | No action (same source) |
| **BOE Match Status** | InvoiceBOEAllocation | ledgerExport.js heuristic | — | NO ✗ | MEDIUM | Centralize in Phase 3B+ |
| **Plan Cap Check** | plan_enforcement.py | item_pivot_report.py | — | YES ✓ | LOW | No action (verified identical) |

---

## High-Risk Candidates for Consolidation (Post-Ledger)

Once Ledger is migrated, audit these next:

### 1. BOE Debit Utilization Status (MEDIUM RISK)
- **Locations:** 3+
- **Issue:** Multiple independent implementations determine if BOE is "pending" vs. "matched"
- **Recommendation:** Centralize in `reconciliation.py`, expose via API

### 2. Available Value Calculation (LOW-MEDIUM RISK)
- **Locations:** Multiple reports
- **Issue:** Each report may compute "available" slightly differently
- **Recommendation:** Verify all use `LicenseBalanceCalculator` result

### 3. Period Summary Totals (MEDIUM RISK)
- **Locations:** Financial ledger, Item pivot, reports
- **Issue:** Different reports may aggregate differently (same-period rules)
- **Recommendation:** Centralize summarization logic

---

## Verification Checklist for Phase 4 (Implementation)

Before consolidating any duplicate:

1. **Trace all callers:** Find every location that invokes the calculation
2. **Verify precision:** Ensure all implementations use identical rounding/precision
3. **Identify divergence:** Document all semantic differences (not bugs, but differences)
4. **Select authoritative:** Decide which implementation is the single source
5. **Migrate callers:** Update all others to delegate to authoritative
6. **Add regression tests:** Verify old behavior matches new (parity test)
7. **Deploy with feature flag:** Switch to new implementation gradually

---

## Migration Order (Recommended for Phase 4+)

1. **First:** Ledger Running Balance (P0 defect, blocking user feature)
2. **Second:** BOE Match Status (MEDIUM risk, affects reconciliation screens)
3. **Third:** Period Summary Totals (MEDIUM risk, affects multiple reports)
4. **Fourth:** Audit remaining LOW-risk duplicates (verify they're truly delegating correctly)

---

## Code Search (for Auditors)

To find other duplicates not yet catalogued:

```bash
# Find all financial calculations
grep -r "balance\s*=" backend/apps --include="*.py" | grep -v test | grep -v migration

# Find all aggregations
grep -r "Sum\|Aggregate\|annotate" backend/apps --include="*.py" | grep -v test | grep -v migration

# Find all frontend calculations
grep -r "balance\s*=" frontend/src --include="*.js" --include="*.ts" --include="*.tsx" | grep -v test

# Find all running balance loops
grep -r "for.*transaction\|running\s*\+=" frontend/src --include="*.js" --include="*.tsx"
```

---

## Version and Status

- **Version 1.0** — Gate 3 Architecture Design, 2026-08-10
- **Audited by:** Solutions Architect
- **Scope:** Backend + Frontend
- **Known P0 Duplicates:** 1 (Ledger Running Balance)
- **Known P1-P2 Duplicates:** 4 (all low risk or correctly delegating)
- **Next Update:** Post-approval, Phase 3B (gate 3 business decision on B2)
