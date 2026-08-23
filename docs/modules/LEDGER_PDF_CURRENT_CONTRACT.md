# Ledger PDF Current Contract — Phase 4E Forensic Analysis
**Date:** 2026-08-10  
**Status:** PRE-MIGRATION CONTRACT DOCUMENTATION  
**Method:** Code-evidence based, read-only

---

## EXECUTIVE SUMMARY

| Aspect | Finding |
|--------|---------|
| **Entry Points** | 2 paths (client-side jsPDF, server-side ReportLab) |
| **Data Source** | Frontend: API response; Backend: Direct DB queries |
| **Balance Calc** | ❌ Both recalculate independently |
| **Commission** | ✅ Visible; ❌ Excluded from balance |
| **Company Group** | ✅ Yes; ❌ Running balance resets per company |
| **Canonical Data** | ❌ Not used |

---

## ENTRY POINT 1: FRONTEND PDF (jsPDF)

### Location
`frontend/src/utils/ledgerExport.js`

### Function Call Chain
```
LicenseLedgerDetail.tsx:211
    ↓
generatePDF([ledger], filename)
    ↓
buildPdfBody() — line 159
    ↓
groupByCompany() — line 180
    ↓
Per-company balance calculation — line 185
    ↓
jsPDF table generation
```

### Entry Parameters
| Param | Type | Source | Evidence |
|-------|------|--------|----------|
| `licenses` | Array | API response (CanonicalLedgerResponse) | Line 211: `generatePDF([ledger], ...)` |
| `filename` | String | Constructed from license metadata | Line 211 |

### Data Transformation Before PDF Calculation

| Step | File | Function | Purpose | Lines |
|------|------|----------|---------|-------|
| 1 | ledgerExport.js | `normalizeLedgerLicensesData()` | Normalize API response | 46-68 |
| 2 | ledgerExport.js | `normalizeTransaction()` | Convert txn fields | 23-44 |
| 3 | ledgerExport.js | `groupByCompany()` | Group by company_id | 103-116 |

### Balance Calculation — PDF Current Formula

**Location:** `frontend/src/utils/ledgerExport.js:180–219`

**Code:**
```javascript
companiesGrouped.forEach(company => {
    let running = 0;  // ← RESET for each company
    company.transactions.forEach((txn) => {
        if (txn.type === 'PURCHASE' || txn.type === 'OPENING') {
            running += isDFIA ? (txn.debit_cif || 0) : (txn.debit_license_value || 0);
        } else if (txn.type === 'SALE') {
            running -= isDFIA ? (txn.credit_cif || 0) : (txn.credit_license_value || 0);
        }
        // ← NO COMMISSION PROCESSING
    });
});
```

**Formula (per company):**
```
Company Running Balance = 0 (reset)
  + PURCHASE amounts
  - SALE amounts
  [COMMISSION excluded]
```

**Scope:** Per-company, not license-wide

**Evidence:**
- Line 185: `let running = 0;` — reset for each company group
- Lines 191-197: `if (txn.type === 'PURCHASE'...)` — conditional logic
- Lines 198-201: `else if (txn.type === 'SALE'...)` — conditional logic
- No commission processing in balance loop

### Commission Handling — PDF

| Aspect | Current Behavior | Evidence |
|--------|------------------|----------|
| **Visible?** | ✅ YES | Line 169: Commission txn renders as table row |
| **In Balance?** | ❌ NO | Line 193: Only PURCHASE/SALE affect `running` |
| **Status Flag?** | ❌ NO | No "Excluded" badge or status display |
| **In Totals?** | ❌ NO | Totals exclude commission (line 233-239) |

### Company Grouping — PDF

| Behavior | Evidence |
|----------|----------|
| **Grouped?** | ✅ YES — `groupByCompany()` line 180 |
| **Reset per company?** | ✅ YES — `let running = 0;` line 185 |
| **Company header?** | ✅ YES — Table header per company group |
| **Company subtotal?** | ✅ YES — Per-company P/L row (line 208-210) |

### Columns — PDF Current

| Column | Source | Computation | Evidence |
|--------|--------|-------------|----------|
| Date | `txn.date` | Direct | Line 172 |
| Particulars | `txn.particular` | Direct | Line 173 |
| CIF Dr | `txn.debit_cif` | Direct | Line 174 |
| CIF Cr | `txn.credit_cif` | Direct | Line 175 |
| Debit (₹) | `txn.debit_amount` | Direct | Line 177 |
| Credit (₹) | `txn.credit_amount` | Direct | Line 178 |
| Balance | `running` | **Calculated** | Line 185-201 |
| P/L | `txn.profit_loss` | Direct (SALE only) | Line 209 |

**Critical:** Balance column is computed locally, not from API.

### Formatting — PDF

| Element | Current Behavior | Evidence |
|---------|------------------|----------|
| **Currency** | ₹ for INR, $ for USD | Line 154-157 |
| **Decimals** | 2 places | `formatIndianNumber(..., 2)` |
| **Negative** | Color: destructive (red) | Line 461 |
| **Headers** | Company-grouped | Line 208 |
| **Totals** | Per-company P/L row | Line 208-210 |
| **Dates** | `formatDate()` | Line 149 |

### Transaction Ordering — PDF

| Factor | Current Behavior | Evidence |
|--------|------------------|----------|
| **Within company** | OPENING → PURCHASE → SALE | Line 118-119: `TXN_ORDER` |
| **Between companies** | Company order from `groupByCompany()` | Line 180 |
| **Determinism** | Map iteration order (unstable in old JS) | Line 180 |

### Edge Cases — PDF Current

| Case | Current Behavior | Evidence |
|------|------------------|----------|
| **Zero amount** | Visible | Line 169 renders all txns |
| **Empty ledger** | Empty table | Line 159 produces empty PDF |
| **Commission-only** | 1 row, balance: 0 | Balance not affected (line 193) |
| **Negative balance** | Red color, allowed | Line 461 |
| **Large dataset** | No pagination | Single table (line 159) |

### Filename — PDF

| Aspect | Format | Evidence |
|--------|--------|----------|
| **Pattern** | `License_Ledger_{license}_{date}.pdf` | Line 203-209 |
| **Sanitization** | Replace special chars | Line 77-87 (`sanitizeExportFilename`) |
| **Date** | YYYY-MM-DD | Line 99-100 |

---

## ENTRY POINT 2: BACKEND PDF (ReportLab)

### Location
`backend/apps/license/services/exporters/ledger_pdf.py`

### Endpoints
| Endpoint | Function | Lines |
|----------|----------|-------|
| `/license-ledger/export/all/` | `export_all()` → `_generate_detailed_licenses_pdf()` | backend/apps/license/views/ledger.py:311 |
| `/license-ledger/company-ledger/export/` | `company_ledger_export()` → `generate_detailed_licenses_pdf()` | backend/apps/license/views/ledger.py:435 |

### Data Flow
```
ViewSet.export_all()
    ↓
_generate_detailed_licenses_pdf(licenses_data, query_params)
    ↓
ledger_pdf.generate_detailed_licenses_pdf()
    ↓
build_dfia_ledger_detail() or build_incentive_ledger_detail()
    ↓
get_license_transactions()
    ↓
Per-transaction balance calculation
    ↓
ReportLab PDF generation
```

### Balance Calculation — Backend PDF Current

**Location:** `backend/apps/license/services/exporters/ledger_pdf.py:100+`

**Formula:**
```python
running_balance = 0
for transaction in transactions:
    if type in ['PURCHASE', 'COMMISSION_PURCHASE']:
        running_balance += amount
    elif type == 'SALE':
        running_balance -= amount
    elif type == 'COMMISSION_SALE':
        running_balance += amount  # ← Treats as debit
```

**Scope:** License-wide, NOT per-company

**Evidence:**
- Line 100: Initial `running_balance = 0`
- Lines 126-181: Transaction loop with conditional additions/subtractions
- Lines 1187-1223: COMMISSION_SALE treated as credit (adds to balance)

### Commission Handling — Backend PDF

| Aspect | Behavior | Evidence |
|--------|----------|----------|
| **Visible?** | ✅ YES | Included in transaction list |
| **In Balance?** | ✅ YES (treated as debit) | Line 1187: COMMISSION_SALE adds |
| **Status Flag?** | ❌ NO | No "Excluded" marker |

### Key Difference from Frontend
```
Frontend:  Per-company, COMMISSION excluded
Backend:   License-wide, COMMISSION included as debit
```

This is a **SEMANTIC DIVERGENCE** (same as P0-001).

---

## SUMMARY TABLE: PDF VARIANTS

| Aspect | Frontend PDF | Backend PDF | Canonical |
|--------|--------------|-------------|-----------|
| **Balance scope** | Per-company | License-wide | License-wide |
| **Commission in balance** | ❌ Excluded | ✅ Included | ✅ Included, explicit flag |
| **Company reset** | ✅ YES | ❌ NO | ✅ Separate field |
| **Data source** | API response | Database queries | CanonicalLedgerService |
| **Active?** | ✅ YES (LicenseLedgerDetail) | ✅ YES (admin export) |

---

## CURRENT VS CANONICAL COMPARISON

| Field | Current Frontend | Current Backend | Canonical | Gap |
|-------|------------------|-----------------|-----------|-----|
| License Balance | Per-company | License-wide | License-wide | Frontend disagrees |
| Commission | Excluded | Included | Explicit flag | Different handling |
| Opening Balance | Not shown | Not shown | Provided | Missing |
| Company Util | Not extracted | Not calculated | Provided object | Not used |
| Running Balance | Recalculated | Recalculated | Provided per txn | Duplicate calc |

---

## CONTRACT BLOCKERS

| Blocker | Severity | Impact |
|---------|----------|--------|
| Frontend/Backend divergence | ⚠️ HIGH | Must reconcile before unified migration |
| API provides canonical; PDF ignores | 🔴 CRITICAL | Fundamental architecture violation |
| Backend rebuilds from DB | ⚠️ HIGH | Should use canonical service |

---

**PDF CONTRACT STATUS:** DOCUMENTED (with blockers requiring Gate 4E design decision)
