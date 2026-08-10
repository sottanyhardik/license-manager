# Ledger Export Consumer Inventory — Phase 4E
**Date:** 2026-08-10  
**Status:** PRE-MIGRATION AUDIT  
**Scope:** All Ledger-related PDF and Excel exporters

---

## EXECUTIVE SUMMARY

Three independent Ledger export systems identified:

1. **Frontend Client-Side PDF/Excel** — Uses jsPDF/ExcelJS in browser
2. **Backend Server-Side PDF** — Uses ReportLab, exported via HTTP endpoint
3. **Backend Excel Exports** — Used in reports/dashboard

All three currently recalculate financial values independently. Phase 4E will unify them to use CanonicalLedgerService.

---

## 1. FRONTEND CLIENT-SIDE EXPORTS

### Location
`frontend/src/utils/ledgerExport.js`

### Functions
- `generatePDF(licensesData, filename)` — Generates PDF using jsPDF
- `generateExcel(licensesData, filename)` — Generates Excel using ExcelJS

### Trigger Points
- **LicenseLedgerDetail.tsx** (lines 211-216)
  - User clicks "Download PDF" → `generatePDF([ledger], filename)`
  - User clicks "Download Excel" → `generateExcel([ledger], filename)`
- **LicenseLedger.tsx** (lines 566-569)
  - User selects format and clicks export
  - Fetches `license-ledger/all/` API endpoint
  - Passes results to `generatePDF()` or `generateExcel()`

### Data Source
- **Input:** Ledger object from canonical API (Phase 4C)
- **Data available:** license_running_balance, company_utilizations, totals, transactions
- **Current behavior:** Ignores canonical fields, recalculates per-company running balance

### Financial Calculations
**Lines 103–116: `groupByCompany()`**
```javascript
export function groupByCompany(transactions) {
    const map = {};
    const normalizedTransactions = Array.isArray(transactions)
        ? transactions.map(normalizeTransaction).filter(Boolean)
        : [];
    normalizedTransactions.forEach((txn, index) => {
        const key = txn.company_id != null ? String(txn.company_id) : `unknown-${index}`;
        if (!map[key]) {
            map[key] = { company_id: txn.company_id ?? key, company_name: ..., transactions: [] };
        }
        map[key].transactions.push(txn);
    });
    return Object.values(map);
}
```

**Lines 180–219: PDF per-company balance calculation**
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

**Lines 704–775: Excel per-company balance calculation**
- Identical logic to PDF: per-company reset, commission exclusion

### Violations
- ❌ Independent per-company running balance calculation (PDF)
- ❌ Independent per-company running balance calculation (Excel)
- ❌ Commission transactions excluded (should be visible with "Excluded" status)
- ❌ No use of canonical `company_utilizations` object
- ❌ No use of canonical `license_running_balance` field

### In Scope for Phase 4E
✅ YES — These are Ledger-specific exports with direct financial violations

---

## 2. BACKEND SERVER-SIDE PDF EXPORTS

### Location
`backend/apps/license/services/exporters/ledger_pdf.py`

### Endpoints
**`/license-ledger/export/all/`** (LicenseLedgerViewSet.export_all)
- **Parameters:** license_type, active_only, min_balance, exporter, search, detailed
- **Response:** PDF file (binary)
- **Usage:** Admin export of multiple licenses

**`/license-ledger/company-ledger/export/`** (LicenseLedgerViewSet.company_ledger_export)
- **Parameters:** company, license_type
- **Response:** PDF file (binary)
- **Usage:** Company-specific ledger export

### Functions Called
- `generate_detailed_licenses_pdf(licenses_data, query_params)`
- `generate_all_licenses_pdf(licenses_data, query_params)`
- `get_license_transactions(lic_data, company_id=None)`

### Data Source
- **Input:** License data from `get_queryset()` (list view format)
- **Transactions:** Fetched via `get_license_transactions()` from trade models
- **No canonical data used:** Rebuilds transactions from scratch

### Financial Calculations
**Line 100+: Running balance calculation**
```python
running_balance = 0
# ... fetch transactions ...
# per transaction:
if type in ['PURCHASE', 'COMMISSION_PURCHASE']:
    running_balance += amount
elif type == 'SALE':
    running_balance -= amount
```

### Current Contract
- Pages: Multi-page PDF with header, transactions, totals
- Columns: Date, Type, Particulars, Qty, CIF, Balance, P/L
- Ordering: By date
- Totals: Per-company and overall
- Commission: Included but not explicitly marked as excluded

### Violations
- ❌ Rebuilds transactions instead of using canonical dataset
- ❌ Independently calculates running balance (not from CanonicalLedgerService)
- ❌ Uses old `build_dfia_ledger_detail` logic (not canonical)

### In Scope for Phase 4E
✅ YES — Backend server-side export with financial violations

---

## 3. BACKEND EXCEL EXPORTS (Dashboard/Reports)

### Location
`backend/apps/license/services/exporters/license_balance_excel.py` (97KB)

### Trigger Points
- Report generation endpoints
- Dashboard excel downloads
- Item reports with balance columns

### Data Source
- **Input:** Query results from license list/detail views
- **Contains:** available_balance field (deprecated)

### Financial Calculations
- Likely includes balance calculations (TBD by code review)

### Current Contract
- Sheet names: License list, transactions, etc.
- Columns: License, Balance, Items, Totals
- Formatting: Currency, dates

### In Scope for Phase 4E
⚠️ POSSIBLY — If it contains ledger-specific data. Needs clarification.

---

## 4. LEGACY LEDGER PDF

### Location
`backend/apps/license/ledger_pdf.py` (standalone)

### Status
- Appears to be older implementation
- May be deprecated in favor of `services/exporters/ledger_pdf.py`

### Action
- Verify if still in use before Phase 4E

---

## PHASE 4E SCOPE DECISION

### Definite In-Scope
1. ✅ **Frontend `ledgerExport.js`**
   - Directly receives canonical API data from LicenseLedgerDetail
   - Recalculates per-company balance unnecessarily
   - Should use API-provided values directly

2. ✅ **Backend PDF export endpoints** (`export_all`, `company_ledger_export`)
   - Server-side PDF generation
   - Should call CanonicalLedgerService instead of rebuilding

### Probable In-Scope
3. ⚠️ **Backend Excel exports** (license_balance_excel.py)
   - If it's for ledger reports, yes
   - If it's for other reports, no
   - Needs code review to determine

### Requires Investigation
4. ❓ **Legacy `ledger_pdf.py`**
   - Is it still used?
   - Is it for ledgers or something else?

---

## INVENTORY SUMMARY

| Export | Type | Location | Financial Calc | Canonical Use | In Scope |
|--------|------|----------|---|---|---|
| LicenseLedgerDetail PDF | Client | ledgerExport.js | ✅ YES | ❌ NO | ✅ YES |
| LicenseLedgerDetail Excel | Client | ledgerExport.js | ✅ YES | ❌ NO | ✅ YES |
| LicenseLedger bulk PDF | Client | ledgerExport.js | ✅ YES | ❌ NO | ✅ YES |
| export/all PDF | Server | ledger_pdf.py | ✅ YES | ❌ NO | ✅ YES |
| company-ledger/export PDF | Server | ledger_pdf.py | ✅ YES | ❌ NO | ✅ YES |
| Balance Excel | Server | license_balance_excel.py | ✅ YES | ❌ NO | ⚠️ TBD |
| Legacy ledger PDF | Server | ledger_pdf.py | ✅ YES | ❌ NO | ⚠️ TBD |

---

## NEXT STEPS

### Phase 4E Priority
1. ✅ **Frontend exports** (ledgerExport.js) — DEFINITE, start here
2. ✅ **Backend PDF exports** (export endpoints) — DEFINITE, follow-up
3. ⚠️ **Other exports** — Investigate and clarify scope

### Before Implementation
- Document current export contracts
- Audit all financial calculations
- Create parity tests baseline
- Verify authorization unchanged

---

**Inventory Status:** COMPLETE  
**Ready for:** Current Export Contract documentation
