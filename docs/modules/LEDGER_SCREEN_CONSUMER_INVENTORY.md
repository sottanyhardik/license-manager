# Ledger Screen Consumer Inventory — Phase 4D
**Date:** 2026-08-10  
**Status:** INVENTORY COMPLETE  
**Scope:** All Ledger screen consumers and dependencies identified

---

## EXECUTIVE SUMMARY

The Ledger Detail screen (`LicenseLedgerDetail.tsx`) is the primary Ledger consumer. It currently:

1. **Correctly fetches** from the Canonical Ledger API endpoint (`license-ledger/{id}/ledger_detail/`)
2. **Incorrectly recalculates** per-company running balance in React (lines 339–348) — **VIOLATION**
3. **Uses deprecated field** `available_balance` instead of `license_running_balance`
4. **Must migrate to** API-provided canonical values

---

## PRIMARY CONSUMER: LicenseLedgerDetail Screen

**File:** `frontend/src/pages/LicenseLedgerDetail.tsx`  
**Route:** `/license/{id}/ledger`  
**Purpose:** Display complete transaction history for a single license

### Current Behavior

| Aspect | Current | Issue |
|--------|---------|-------|
| **API Endpoint** | `license-ledger/{id}/ledger_detail/` | ✅ Correct (Phase 4C canonical) |
| **Opening Balance Display** | `ledger.available_balance` | ❌ Uses deprecated field |
| **License Running Balance Display** | `ledger.available_balance` | ❌ Uses deprecated field |
| **Company Running Balance** | Recalculated in React (lines 339–348) | ❌ **CRITICAL VIOLATION** |
| **Transaction Running Balance Display** | `companyBalMap` (React-calculated) | ❌ **CRITICAL VIOLATION** |
| **Commission Handling** | Included in table, status not clear | ⚠️ Needs explicit "Excluded" badge |
| **Zero-Amount Transactions** | Rendered if in API response | ✅ Correct |
| **Company Utilization** | Not displayed | ⚠️ Missing canonical data |
| **Transaction Ordering** | Sorted in React (line 335–337) | ⚠️ Should use API ordering |

### Lines with Financial Calculations (VIOLATIONS)

```
Line 71:  Normalize deprecated available_balance field
Line 193: Get currentBalance from deprecated available_balance
Line 339–348: RECALCULATE per-company running balance in React
Line 350–352: RECALCULATE totals/profit-loss in React
Line 403: Use React-calculated rowBal instead of API value
Line 463: Display React-calculated balance (companyBalMap)
```

### Rendering Areas

**Header (lines 262–326):**
- License metadata: ✅ Read-only
- Exporter, dates, type: ✅ Read-only
- **Balance card (lines 312–324):** ❌ Displays `currentBalance` (deprecated field)

**Company-grouped tables (lines 328–506):**
- Company header: ✅ Read-only
- Transaction table (lines 374–501)
  - Columns: Date, Particulars, Items, CIF Dr/Cr, Value Dr/Cr, Rate, INR Debit, INR Credit, **Balance**, P/L
  - **Balance column (line 459–464):** ❌ Displays React-calculated `rowBal` (violation)
  - Company total row (lines 478–499): ❌ Recalculates totals in React

### Export Actions

**Line 211–216:** PDF/Excel download buttons
- Call `generatePDF()` and `generateExcel()` from `ledgerExport.js`
- **Phase 4D scope:** DO NOT MODIFY (handled in Phase 4E)

---

## SECONDARY CONSUMERS

### 2. LicenseLedger List Page

**File:** `frontend/src/pages/LicenseLedger.tsx`  
**Route:** `/ledger/` or `/license/{id}/ledger`  
**Purpose:** Browse ledger by license

**API Call (line 470):**
```typescript
api.get(`license-ledger/${lic.license_id}/ledger_detail/?${params}`)
```

**Fields Used:**
- List of licenses with summary data
- Not showing detailed balance calculations

**Impact:** NONE (summary only, no calculations removed)

---

### 3. Licenses Table (Masters)

**File:** `frontend/src/pages/masters/tables/LicensesTable.tsx:565`  
**Purpose:** Display available balance in licenses table

**Code:**
```typescript
<div className="font-semibold tabular-nums text-primary">
  ${fmtNum(ledger.available_balance)}
</div>
```

**Issue:** Uses deprecated `available_balance` field  
**Impact:** Will need migration to `license_running_balance`  
**Phase:** 4D (update types)

---

### 4. Item Report Totals Bar

**File:** `frontend/src/pages/reports/itemReport/ItemReportTotalsBar.tsx:32`  
**Purpose:** Sum available balance across licenses

**Code:**
```typescript
uniqueLicenses[item.license_id] = item.available_balance || 0;
```

**Issue:** Uses deprecated `available_balance` field  
**Impact:** Will need migration to `license_running_balance`  
**Phase:** 4D (update types)

---

### 5. Item Report Table

**Files:**
- `frontend/src/pages/reports/itemReport/ItemReportTable.tsx:243, 391`
- `frontend/src/pages/reports/itemReport/ItemReportTable.test.tsx:25, 50, 75`

**Purpose:** Display license balance in item pivot report

**Code:**
```typescript
formatCif(firstItem.available_balance)
```

**Issue:** Uses deprecated `available_balance` field  
**Impact:** Will need migration to `license_running_balance`  
**Phase:** 4D (update types)

---

## EXPORT UTILITIES (DO NOT MODIFY IN PHASE 4D)

**File:** `frontend/src/utils/ledgerExport.ts`  
**Purpose:** Generate PDF and Excel exports

**Current Behavior:**
- Recalculates per-company running balance (legacy approach)
- Uses API transaction data

**Phase 4D Status:** ❌ DO NOT MODIFY (scheduled for Phase 4E)

**Phase 4E Will:**
- Migrate to use API-provided `license_running_balance` per transaction
- Remove duplicate calculation logic
- Use company utilizations from canonical dataset

---

## TEST FILES

**Unit/Integration Tests:**

1. `frontend/src/pages/LicenseLedgerDetail.test.tsx`
   - Tests path building, API calls, normalization
   - Must be updated for new API contract
   
2. `frontend/src/pages/LicenseLedger.test.tsx`
   - Tests ledger list page
   - Must be updated for new field names

3. `frontend/src/utils/ledgerExport.test.ts`
   - Tests export logic
   - DEFER to Phase 4E (export migration)

4. `frontend/src/pages/masters/tables/LicensesTable.tsx` (no dedicated tests found for balance display)

5. `frontend/src/pages/reports/itemReport/ItemReportTable.test.tsx`
   - Tests item report balance display
   - Must be updated for new field names

---

## TYPES AND INTERFACES

**Current Type Definition (LicenseLedgerDetail.tsx:16–26):**
```typescript
type LedgerTransaction = Record<string, unknown> & {
    type?: string;
    company_id?: string | number | null;
    company_name?: string;
};

type LedgerDetail = Record<string, unknown> & {
    license_number: string;
    license_type: string;
    transactions: LedgerTransaction[];
};
```

**Issue:** Overly loose types (Record<string, unknown>), no canonical field names defined

**Phase 4D Will Create:**
```typescript
interface CanonicalLedgerResponse {
  license_id: number;
  license_type: string;
  license_number: string;
  license_date: string;
  expiry_date: string;
  exporter_id: number | null;
  exporter_name: string | null;
  port_id: number | null;
  port_name: string | null;
  opening_balance: string;
  license_running_balance: string;
  closing_balance: string;
  transactions: CanonicalTransaction[];
  company_utilizations: Record<string, CompanyUtilization>;
  totals: LedgerTotals;
  // Deprecated (backward compat only)
  available_balance: string;
  db_balance: string;
}

interface CanonicalTransaction {
  date: string;
  id: number;
  type: string;
  company_id: number | null;
  company_name: string | null;
  amount: string;
  is_commission: boolean;
  affects_balance: boolean;
  license_running_balance: string;
  company_utilization_after: string | null;
  display_status: string;
}

interface CompanyUtilization {
  company_id: number;
  company_name: string | null;
  utilization_balance: string;
}

interface LedgerTotals {
  total_purchases: string;
  total_sales: string;
  total_commission: string;
}
```

---

## DEPENDENCIES ANALYSIS

```
LicenseLedgerDetail.tsx
  ├─ API: license-ledger/{id}/ledger_detail/
  │   ├─ Backend: views/ledger.py:ledger_detail()
  │   ├─ Service: CanonicalLedgerService
  │   └─ Serializer: CanonicalLedgerSerializer (Phase 4C)
  │
  ├─ Utils:
  │   ├─ ledgerExport.js (generatePDF, generateExcel)
  │   ├─ numberFormatter.js (formatIndianNumber)
  │   ├─ dateFormatter.js (formatDate)
  │   └─ utils/lib (cn, Button, Badge, Icons)
  │
  └─ Components: UI primitives (Button, Badge, Icons)

Consumers of deprecated available_balance:
  ├─ LicenseLedgerDetail.tsx
  ├─ LicensesTable.tsx
  ├─ ItemReportTotalsBar.tsx
  ├─ ItemReportTable.tsx (2 locations)
  └─ Tests: 4 test files
```

---

## PHASE 4D MIGRATION SCOPE

### MUST MODIFY

1. **LicenseLedgerDetail.tsx**
   - Remove React-based balance calculation (lines 339–348)
   - Use API-provided `license_running_balance` for each transaction
   - Use API-provided `company_utilizations` for company balances
   - Update types to use canonical fields
   - Add "Excluded from License Balance" badge for commission rows

2. **TypeScript Types**
   - Create `CanonicalLedgerResponse` interface
   - Update `LedgerDetail` and `LedgerTransaction` to match API contract
   - Update all type references

3. **LicenseLedgerDetail.test.tsx**
   - Update mock data to use canonical field names
   - Update assertions for new API contract
   - Add parity test (API values == displayed values)

### OPTIONAL (Out of scope for 4D, but recommended for consistency)

4. **LicensesTable.tsx**
   - Update `available_balance` → `license_running_balance`
   - Update type definitions

5. **ItemReportTable.tsx** and **ItemReportTotalsBar.tsx**
   - Update `available_balance` → `license_running_balance`
   - Update test data

### DO NOT MODIFY

- `ledgerExport.ts` (Phase 4E)
- Backend code
- Database
- PDF/Excel generation logic

---

## HARD STOP CONDITIONS FOR PHASE 4D

STOP immediately if:

1. ✋ UI requires independent financial calculations
2. ✋ API does not provide `license_running_balance` on each transaction
3. ✋ API does not provide `company_utilizations` breakdown
4. ✋ `affects_balance` field missing from transaction
5. ✋ Commission `display_status` field missing
6. ✋ Balance parity test fails (API value != displayed value)
7. ✋ Existing tests fail due to schema changes
8. ✋ Authorization behavior changes
9. ✋ Duplicate API requests occur
10. ✋ Scope violation (modifying exports, backend, database)

---

## STATUS

**CONSUMER INVENTORY:** ✅ COMPLETE

**Key Findings:**
- ✅ All Ledger consumers identified
- ❌ Primary consumer (LicenseLedgerDetail.tsx) has critical violations (independent balance calculation)
- ❌ Deprecated field names in use across UI
- ⚠️ Secondary consumers need type migration only

**Ready for:** Phase 4D Implementation

---

**Next Step:** Inspect current Ledger screen and remove independent financial calculations
