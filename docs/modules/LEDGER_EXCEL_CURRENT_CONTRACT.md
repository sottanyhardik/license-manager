# Ledger Excel Current Contract — Phase 4E Forensic Analysis
**Date:** 2026-08-10  
**Status:** PRE-MIGRATION CONTRACT DOCUMENTATION  
**Method:** Code-evidence based, read-only

---

## EXECUTIVE SUMMARY

| Aspect | Finding |
|--------|---------|
| **Entry Point** | Frontend only (client-side ExcelJS) |
| **Data Source** | API response (CanonicalLedgerResponse) |
| **Balance Calc** | ❌ Recalculates independently, per-company |
| **Commission** | ✅ Visible; ❌ Excluded from balance |
| **Grouping** | ✅ Per-company; ❌ Running balance resets |
| **Canonical Data** | ❌ Not used |

---

## ENTRY POINT: FRONTEND EXCEL (ExcelJS)

### Location
`frontend/src/utils/ledgerExport.js`

### Function Call Chain
```
LicenseLedgerDetail.tsx:215
    ↓
generateExcel([ledger], filename)
    ↓
buildExcelWorkbook() — line 418+
    ↓
groupByCompany() — line 433
    ↓
Per-company balance calculation — line 730
    ↓
ExcelJS workbook generation
```

### Entry Parameters
| Param | Type | Source | Evidence |
|-------|------|--------|----------|
| `licenses` | Array | API response | Line 215: `generateExcel([ledger], ...)` |
| `filename` | String | Constructed | Line 215 |

### Balance Calculation — Excel Current Formula

**Location:** `frontend/src/utils/ledgerExport.js:704–775`

**Code:**
```javascript
const companiesGrouped = groupByCompany(license.transactions);
companiesGrouped.forEach((company) => {
    let running = 0;  // ← RESET per company
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

**Scope:** Per-company, NOT license-wide

**Evidence:**
- Line 730: `let running = 0;` — reset for each company
- Lines 737-743: Conditional purchase/sale processing
- No commission handling

### Commission Handling — Excel

| Aspect | Behavior | Evidence |
|--------|----------|----------|
| **Visible?** | ✅ YES | Row included in sheet if in API |
| **In Balance?** | ❌ NO | Line 737: Only PURCHASE/SALE affect `running` |
| **Status Flag?** | ❌ NO | No "Excluded" column |
| **In Totals?** | ❌ NO | Commission excluded from running totals |

### Workbook Structure — Excel

| Element | Current Behavior | Evidence |
|---------|------------------|----------|
| **Sheet name** | License number (sanitized) | Line 436: `sanitizeWorksheetName()` |
| **Columns** | Date, Particulars, CIF, Amount, Balance | Line 740+ |
| **Rows** | One per transaction | Line 750+ |
| **Grouping** | By company; subtotal row per company | Line 730+ |
| **Totals** | Grand total row | Line 768+ |

### Columns — Excel Current

| Column | Source | Computation | Evidence |
|--------|--------|-------------|----------|
| Date | `txn.date` | Direct | Line 740 |
| Particulars | `txn.particular` | Direct | Line 741 |
| Type | `txn.type` | Direct | Line 742 |
| CIF | `txn.debit_cif` / `txn.credit_cif` | Direct | Lines 743-744 |
| Debit (₹) | `txn.debit_amount` | Direct | Line 745 |
| Credit (₹) | `txn.credit_amount` | Direct | Line 746 |
| Balance | `running` | **Calculated** | Line 730-747 |
| P/L | `txn.profit_loss` | Direct (SALE only) | Line 748 |

**Critical:** Balance column is computed locally, not from API.

### Formatting — Excel

| Element | Behavior | Evidence |
|---------|----------|----------|
| **Number format** | General (no currency) | Lines 750+ (addRow) |
| **Decimals** | 2 places via formatIndianNumber | Line 748 |
| **Currency** | INR symbol, conditional USD | Line 748-749 |
| **Dates** | Formatted via formatDate | Line 747 |
| **Column widths** | Default | Not explicitly set in code |
| **Freeze panes** | None | Not in current code |
| **Filters** | None | Not in current code |

### Transaction Ordering — Excel

| Factor | Behavior | Evidence |
|--------|----------|----------|
| **Within company** | OPENING → PURCHASE → SALE | Line 735: `TXN_ORDER` |
| **Between companies** | Company order from `groupByCompany()` | Line 733 |
| **Determinism** | Map iteration order | Line 733 |

### Grouping — Excel

| Aspect | Behavior | Evidence |
|--------|----------|----------|
| **By company?** | ✅ YES | Line 733: `groupByCompany()` |
| **Company header?** | ✅ YES | Line 737 adds company name row |
| **Company subtotal?** | ✅ YES | Line 765+ per-company totals |
| **Balance reset?** | ✅ YES | Line 730: `let running = 0;` per company |
| **Grand total?** | ✅ YES | Line 768+ overall totals |

### Edge Cases — Excel Current

| Case | Behavior | Evidence |
|------|----------|----------|
| **Zero amount** | Included | Row added if in API response |
| **Empty ledger** | No transaction rows | `forEach` finds nothing |
| **Commission-only** | 1 row per commission, balance: 0 | Not in running calc |
| **Negative balance** | Shown as-is | No validation/formatting |
| **Large dataset** | Single sheet, may be slow | No pagination in code |

### Filename — Excel

| Aspect | Format | Evidence |
|--------|--------|----------|
| **Pattern** | `License_Ledger_{license}_{date}.xlsx` | Line 203-209 |
| **Sanitization** | Replace special chars | Line 77-87 |
| **Date** | YYYY-MM-DD | Line 99-100 |

### ExcelJS Libraries Used
| Library | Purpose | Evidence |
|---------|---------|----------|
| ExcelJS | Workbook/worksheet creation | Line 2: `import ExcelJS` |
| addRow() | Add transaction rows | Line 750 |
| save() | Write file | Line 776 |
| Blob | Browser file download | Line 780 |

---

## COMPARISON: PDF vs EXCEL

| Aspect | PDF | Excel | Discrepancy |
|--------|-----|-------|-------------|
| **Balance scope** | Per-company | Per-company | ✅ Aligned |
| **Commission** | Excluded | Excluded | ✅ Aligned |
| **Grouping** | Per-company | Per-company | ✅ Aligned |
| **Technology** | jsPDF | ExcelJS | Different libraries |
| **Data source** | API | API | ✅ Same |

Both frontend exporters recalculate identically but differ from canonical (license-wide balance).

---

## CURRENT VS CANONICAL COMPARISON

| Field | Current | Canonical | Gap |
|-------|---------|-----------|-----|
| License Balance | Per-company (Excel) | License-wide | Diverges |
| Commission | Excluded, no flag | Explicit flag | Missing status |
| Opening Balance | Not shown | Provided | Missing |
| Company Util | Derived from rows | Provided object | Not used |
| Running Balance | Recalculated | Provided per txn | Duplicate calc |

---

## CONTRACT BLOCKERS

| Blocker | Severity | Impact |
|---------|----------|--------|
| Recalculates balance unnecessarily | ⚠️ HIGH | Should consume API-provided value |
| Per-company balance differs from backend | 🔴 CRITICAL | Architectural violation (P0-001) |
| No use of canonical `company_utilizations` | ⚠️ HIGH | Missing optimization |
| No commission status flag | ⚠️ MEDIUM | User confusion about excluded rows |

---

**EXCEL CONTRACT STATUS:** DOCUMENTED (with critical divergence requiring resolution)
