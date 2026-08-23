# Ledger Detail — Forensic Audit & Balance Convention Analysis
**Date:** 2026-08-10  
**Status:** Audit Complete — P0 Defect Documented  
**Scope:** Complete trace of ledger data flow from database to all outputs (UI, PDF, Excel)  
**Finding:** Two legitimate but conflicting running-balance conventions in production

---

## EXECUTIVE SUMMARY

The License Ledger Detail page, PDF export, and Excel export **display different running balances for identical license and transaction data**. This is not a rendering bug—it's a **semantic divergence** caused by two different business conventions being implemented in parallel:

- **Backend (API):** License-wide running balance (PURCHASE→SALE→COMMISSION sequence)
- **Frontend (UI/PDF/Excel):** Per-company running balance (resets per company, excludes COMMISSION)

Neither implementation is technically wrong. They represent two valid but incompatible views of ledger accounting. Resolution requires a **business decision** on which convention is authoritative.

---

## DATA FLOW ARCHITECTURE

```
Database (License + Trade + RowDetails)
        ↓
API Endpoint: LicenseLedgerViewSet.ledger_detail()
        ↓
Backend Builder: build_dfia_ledger_detail() / build_incentive_ledger_detail()
        ├─→ Builds transaction list with BACKEND running balance (license-wide)
        ├─→ Calls LicenseBalanceCalculator.calculate_financial_balance()
        └─→ Returns JSON response
        ↓
Browser (React component receives JSON)
        ├─→ Display: Renders backend-provided data as-is
        ├─→ PDF Export: Recalculates running balance (per-company, COMMISSION excluded)
        └─→ Excel Export: Recalculates running balance (per-company, COMMISSION excluded)
```

**Critical Insight:** The frontend generates its own running balance instead of consuming the backend's, causing divergence.

---

## FILE INVENTORY

### Backend Components

| File | Purpose | Lines | Responsibility |
|------|---------|-------|---|
| `backend/apps/license/views/ledger.py:219` | API endpoint | 42 | Delegates to builders |
| `backend/apps/license/services/exporters/ledger_pdf.py:1025` | DFIA builder | 250 | Builds license-wide running balance |
| `backend/apps/license/services/exporters/ledger_pdf.py:1278` | Incentive builder | ~400 | Builds license-wide running balance |
| `backend/apps/license/services/balance_calculator.py` | Balance calc | 178+ | Authoritative balance computation |

### Frontend Components

| File | Purpose | Lines | Responsibility |
|------|---------|-------|---|
| `frontend/src/pages/LicenseLedgerDetail.tsx:1` | React page | 509 | Displays backend data as-is |
| `frontend/src/utils/ledgerExport.js:103` | groupByCompany | 13 | Groups transactions per company |
| `frontend/src/utils/ledgerExport.js:159` | buildPdfBody | ~500 | PDF generation, recalculates per-company balance |
| `frontend/src/utils/ledgerExport.js:418` | generateExcel | ~500 | Excel generation, recalculates per-company balance |

---

## BACKEND RUNNING BALANCE CONVENTION (License-Wide)

### Implementation Details

**Location:** `backend/apps/license/services/exporters/ledger_pdf.py:1025–1275`

**Transaction Sort Order (Line 1067):**
```python
all_trans.sort(key=lambda x: (x[0] not in ['PURCHASE', 'COMMISSION_PURCHASE'], x[1]))
```
Result: PURCHASE/COMMISSION_PURCHASE first, then others sorted by date.

**Running Balance Calculation:**
```
Line 1126–1181 (PURCHASE/COMMISSION_PURCHASE):
  running_balance += total_cif_usd
  
Line 1183–1223 (SALE/COMMISSION_SALE):
  if COMMISSION_SALE (line 1187):
    running_balance += total_cif_usd  ← adds to balance (treats as debit)
  else (SALE):
    running_balance -= total_cif_usd  ← subtracts from balance
```

**Balance Per Row:**
Each transaction row in the returned `transactions` list includes:
```python
'balance': round(running_balance, 2)  # cumulative running balance
```

**Example Flow:**
```
Opening:    running_balance = 100
PURCHASE:   running_balance = 100 + 50 = 150
SALE:       running_balance = 150 - 30 = 120
COMMISSION: running_balance = 120 + 10 = 130
```

**Semantic Meaning:** This represents the license's total financial position across all companies and transaction types. COMMISSION_SALE is treated as a debit (increases the balance, not a payment out).

**Data Returned (Lines 1263–1275):**
```python
return {
    'license_id': license.id,
    'license_number': license.license_number,
    # ... metadata ...
    'available_balance': float(LicenseBalanceCalculator.calculate_financial_balance(license)),
    'transactions': transactions,  # ← Each has 'balance' field (license-wide)
}
```

---

## FRONTEND RUNNING BALANCE CONVENTION (Per-Company)

### Implementation Details

**Location:** `frontend/src/utils/ledgerExport.js`

**Company Grouping (Line 103–116):**
```javascript
export function groupByCompany(transactions) {
    const map = {};
    normalizedTransactions.forEach((txn, index) => {
        const key = txn.company_id != null ? String(txn.company_id) : `unknown-${index}`;
        if (!map[key]) {
            map[key] = { company_id, company_name, transactions: [] };
        }
        map[key].transactions.push(txn);
    });
    return Object.values(map);
}
```
Result: Transactions grouped by `company_id`, each group is processed independently.

**Per-Company Running Balance (Lines 185–190, 730–739):**
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

**Key Differences from Backend:**
1. Running balance resets to 0 for each company
2. **COMMISSION transactions are IGNORED** (not processed in balance loop)
3. Uses `debit_cif`/`credit_cif` fields directly (not license-wide like backend)
4. Sort order: OPENING → PURCHASE → SALE (defined at line 118–119)

**Example Flow (for Company A):**
```
Running (Company A): 0
PURCHASE:           0 + 50 = 50
SALE:               50 - 30 = 20
COMMISSION:         (skipped, not processed)

Running (Company B): 0 (reset for new company)
PURCHASE:           0 + 40 = 40
SALE:               40 - 15 = 25
```

**Semantic Meaning:** This represents each company's portion of the license's utilization. COMMISSION is treated as irrelevant to company-level balance tracking.

---

## THREE-WAY DIVERGENCE (Screen vs PDF vs Excel)

### Screen Display

**File:** `frontend/src/pages/LicenseLedgerDetail.tsx`

**Current Behavior:**
- Fetches JSON from backend API
- Renders `transactions` array verbatim
- Uses backend-provided `balance` field on each row
- **Shows BACKEND convention** (license-wide running balance)
- **Includes COMMISSION rows in display**

**Code:**
```typescript
const currentBalance = toFiniteNumber(ledger.available_balance);
// Renders backend transactions with their 'balance' field
```

### PDF Export

**File:** `frontend/src/utils/ledgerExport.js:159`

**Current Behavior:**
- Groups transactions by company (Line 180)
- Resets running balance for each company (Line 185)
- **Excludes COMMISSION rows** (not processed in balance loop)
- **Shows FRONTEND convention** (per-company running balance)

**Code (Lines 180–219):**
```javascript
companiesGrouped.forEach(company => {
    // Header row with company name
    body.push([{ content: company.company_name, colSpan: colCount, styles: chStyle }]);
    
    let running = 0;  // ← per-company reset
    company.transactions.forEach((txn) => {
        if (txn.type === 'PURCHASE') running += ...
        else if (txn.type === 'SALE') running -= ...
        // COMMISSION: skipped
        
        body.push([..., fmtNum(running), ...]); // ← per-company balance
    });
});
```

### Excel Export

**File:** `frontend/src/utils/ledgerExport.js:418`

**Current Behavior:**
- Same as PDF: groups by company, resets per-company balance
- **Excludes COMMISSION rows**
- **Shows FRONTEND convention** (per-company running balance)

**Code (Lines 704–775):**
```javascript
const companiesGrouped = groupByCompany(license.transactions);
companiesGrouped.forEach((company) => {
    let running = 0;  // ← per-company reset
    company.transactions.forEach((txn) => {
        if (txn.type === 'PURCHASE' || txn.type === 'OPENING') running += ...
        else if (txn.type === 'SALE') running -= ...
        
        // Append row with running balance
        ws.addRow([..., fmtNum(running), ...]);
    });
});
```

---

## CONCRETE EXAMPLE (P0 Defect Manifestation)

**Scenario:** License L1 with 2 companies (A, B)

**Transactions:**
| Type | Company | Amount | Backend Running | Frontend Running (per-company) |
|------|---------|--------|---|---|
| PURCHASE | A | 100 | 100 | 100 (A) |
| SALE | A | 30 | 70 | 70 (A) |
| COMMISSION | B | 20 | 90 | (skipped) |
| PURCHASE | B | 40 | 130 | 40 (B) |
| SALE | B | 15 | 115 | 25 (B) |

**User Experience:**
1. **Screen:** Shows 115 (backend license-wide balance) with all rows including COMMISSION
2. **PDF:** Shows per-company sections: Company A finishes at 70, Company B finishes at 25
3. **Excel:** Same as PDF

**User Confusion:** "Why does the license balance say 115 on the screen but Company sections show 70 and 25?"

---

## ROOT CAUSE ANALYSIS

### Why Does This Divergence Exist?

**Historical Context:**
- Backend builders (`build_dfia_ledger_detail`) were extracted verbatim from the old ViewSet to follow clean architecture (see docstring line 3–5)
- Frontend export logic (`ledgerExport.js`) was implemented independently for PDF/Excel generation
- Neither side was aware the other was computing running balance
- The two conventions represent legitimate but different accounting models

### Why Wasn't This Caught?

1. **Test Coverage Gap:** Zero unit tests for ledger builders (P0-002)
2. **No Parity Tests:** No tests comparing screen vs PDF vs Excel
3. **Independent Development:** Frontend exports developed separately from backend changes
4. **Silent Divergence:** Both implementations work, neither errors out

---

## BOTH CONVENTIONS ARE LEGITIMATE

### Convention A: License-Wide Running Balance (Backend)

**Definition:** Cumulative balance across all companies and transaction types.

**Formula:**
```
Opening Balance
+ PURCHASE (add)
+ COMMISSION_SALE (add, treats as internal debit)
- SALE (subtract)
```

**Use Case:** Auditing the license's total financial position independent of company interactions.

**Advantage:** Single running total across the entire license lifecycle.

**Disadvantage:** COMMISSION rows are confusing (treated as credits, not payments).

### Convention B: Per-Company Running Balance (Frontend)

**Definition:** Cumulative balance per company, resetting to zero for each company.

**Formula per Company:**
```
0 (reset for new company)
+ PURCHASE (add)
- SALE (subtract)
[COMMISSION: ignored]
```

**Use Case:** Tracking each customer/supplier's consumption separately.

**Advantage:** Clear, separate view of each company's portion.

**Disadvantage:** Loses visibility of COMMISSION transactions (not counted).

---

## THE BUSINESS DECISION GATE

**What needs approval from business stakeholders:**

1. **Which convention is correct?**
   - License-wide (backend)
   - Per-company (frontend)
   - Hybrid (some rows per-company, some license-wide)

2. **How should COMMISSION transactions be handled?**
   - Backend treats as credits (debit the license)
   - Frontend ignores them entirely
   - Should they be separate?

3. **What should the "final" running balance represent?**
   - Total balance available (license-wide)
   - Per-company balance (per-company)
   - Both (dual view)?

**Impact of decision:**
- If license-wide → eliminate per-company grouping in exports
- If per-company → change backend to stop including COMMISSION in balance
- If hybrid → more complex logic but clearest semantically

---

## CURRENT PRODUCTION STATE

**Status:** P0 defect (user-visible, conflicting data)

**Affected Users:** Anyone viewing ledger in multiple formats

**Duration:** Unknown (divergence existed before Phase 3, possibly since PDF/Excel export was implemented)

**Business Impact:** Audit confusion, reconciliation issues, user distrust

---

## NEXT STEPS (To Resolve P0)

1. **Business Decision:** Approve ledger balance convention
2. **Test Suite:** Create characterization tests with golden data (Phase 3D)
3. **Implementation:** Update backend and/or frontend to match approved convention
4. **Verification:** All three outputs (screen, PDF, Excel) produce identical balance
5. **Freeze:** Lock ledger module once tests and parity verified

---

## ARTIFACTS FOR DECISION MAKERS

See accompanying documents:
- `LEDGER_BALANCE_CONVENTIONS.md` — Detailed option analysis with examples
- `LEDGER_BALANCE_CONVENTION_DECISION.md` — Decision package for approval

---

**Forensic Audit Status:** ✅ COMPLETE

All code paths traced, both conventions documented, root cause identified. Ready for business decision.
