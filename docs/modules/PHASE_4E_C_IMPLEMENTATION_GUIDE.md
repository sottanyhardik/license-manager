# Phase 4E-C Implementation Guide
## Frontend PDF Canonical Migration

**Status:** QUEUED (auto-launch after 4E-B PASS)  
**Role:** Frontend Engineer + Implementation Agent  
**Duration:** ~30 minutes  

---

## PHASE OBJECTIVE

Migrate frontend PDF exporter (`frontend/src/utils/ledgerExport.js`) from independent per-company balance calculation to consuming `CanonicalLedgerService` data via API.

**Golden Rule:**
```
Frontend PDF may format and paginate.
Frontend PDF may NOT recalculate financial truth.
Balance, commission, totals = from CanonicalLedgerService.
```

---

## SCOPE

### IN SCOPE
- ✅ frontend/src/utils/ledgerExport.js PDF generation
- ✅ API integration (use existing `/api/license-ledger/{pk}/ledger_detail/`)
- ✅ Data transformation for PDF layout
- ✅ Formatting and presentation

### OUT OF SCOPE
- ❌ Financial calculation
- ❌ Balance recalculation
- ❌ Commission logic
- ❌ Company utilization
- ❌ Running balance tracking
- ❌ Decimal rounding decisions

---

## CURRENT STATE (Before)

File: `frontend/src/utils/ledgerExport.js`

Current logic:
```javascript
// WRONG: Independent per-company balance
let companyBalance = 0;
transactions.forEach(txn => {
  if (txn.direction === 'PURCHASE') {
    companyBalance += txn.amount;
  } else if (txn.direction === 'SALE') {
    companyBalance -= txn.amount;
  }
  // ... PDF generation with companyBalance
});
```

**Problems:**
- Independent calculation (duplicate of backend)
- No commission handling
- No opening balance
- Per-company only (not license-wide)

---

## TARGET STATE (After)

```javascript
// CORRECT: Consume canonical service via API
const { ledgerData } = await fetchCanonicalLedger(licenseId);

// ledgerData contains:
{
  opening_balance: 1000.00,
  transactions: [
    {
      id: 0,
      date: "2026-01-01",
      type: "OPENING",
      amount: 1000.00,
      license_running_balance: 1000.00,  // ← USE THIS
      is_commission: false,
    },
    {
      id: 1,
      date: "2026-01-15",
      type: "PURCHASE",
      amount: 500.00,
      license_running_balance: 1500.00,  // ← USE THIS
      is_commission: false,
      company_id: 2,
      company_name: "Company A",
    },
    // ... more transactions
  ],
  company_utilizations: {
    2: { utilization_balance: 300.00 },  // Company A
  },
  license_running_balance: 1300.00,  // FINAL BALANCE
}

// PDF generation uses CANONICAL DATA
const balances = buildBalanceMap(ledgerData.transactions);
transactions.forEach(txn => {
  // Format, don't calculate
  txn.balance = balances[txn.id];  // ← FROM CANONICAL
});
```

---

## IMPLEMENTATION STEPS

### Step 1: Audit Current State
```bash
# Read the current implementation
cat frontend/src/utils/ledgerExport.js | head -200

# Find all independent balance calculations
grep -n "balance\s*=" frontend/src/utils/ledgerExport.js
grep -n "balance\s*+=" frontend/src/utils/ledgerExport.js
grep -n "balance\s*-=" frontend/src/utils/ledgerExport.js
```

### Step 2: Verify API Contract
```javascript
// Verify API returns what you expect
GET /api/license-ledger/{pk}/ledger_detail/

Expected response structure:
{
  opening_balance: Decimal,
  transactions: [
    {
      id: int,
      date: date,
      type: str,
      amount: Decimal,
      license_running_balance: Decimal,  // ← MUST USE THIS
      is_commission: boolean,
      company_id: int,
      company_name: str,
    },
    ...
  ],
  company_utilizations: {
    company_id: {
      utilization_balance: Decimal,
    },
    ...
  },
  license_running_balance: Decimal,  // ← FINAL BALANCE
}
```

### Step 3: Create Helper Function
```javascript
// frontend/src/utils/canonicalLedgerAdapter.js

export async function fetchCanonicalLedger(licenseId) {
  const response = await axios.get(
    `/api/license-ledger/${licenseId}/ledger_detail/`
  );
  return response.data;
}

export function buildPdfTransactions(canonicalData) {
  // Map canonical transactions to PDF format
  // DO NOT recalculate balance
  // DO NOT filter commission
  // DO NOT reorder transactions
  // DO use canonical.license_running_balance as final balance
  
  return canonicalData.transactions.map(txn => ({
    date: txn.date,
    type: txn.type,
    company: txn.company_name,
    amount: formatDecimal(txn.amount),
    balance: formatDecimal(txn.license_running_balance),
    is_commission: txn.is_commission,
  }));
}
```

### Step 4: Update PDF Generation
```javascript
// frontend/src/utils/ledgerExport.js

export async function generateLedgerPdf(licenseId) {
  try {
    // Fetch canonical data
    const canonicalData = await fetchCanonicalLedger(licenseId);
    
    // Build PDF format (formatting only, no calculation)
    const pdfTransactions = buildPdfTransactions(canonicalData);
    
    // Generate PDF with canonical data
    const doc = new jsPDF();
    
    // Title
    doc.text('License Ledger', 10, 10);
    doc.text(`Opening Balance: ${canonicalData.opening_balance}`, 10, 20);
    
    // Table
    let y = 40;
    pdfTransactions.forEach(txn => {
      doc.text(
        `${txn.date} | ${txn.type} | ${txn.company} | ${txn.amount} | ${txn.balance}`,
        10,
        y
      );
      y += 10;
    });
    
    // Final balance
    doc.text(
      `Final Balance: ${canonicalData.license_running_balance}`,
      10,
      y + 10
    );
    
    return doc.output('blob');
  } catch (error) {
    // Handle API error
    console.error('Failed to fetch canonical ledger:', error);
    throw new Error('PDF generation failed');
  }
}
```

### Step 5: Remove Old Balance Calculation Code
```javascript
// DELETE:
// - All local balance tracking
// - All `balance +=` operations
// - All `balance -=` operations
// - All commission handling logic
// - All opening balance initialization
// - All per-company balance logic

// KEEP:
// - PDF formatting
// - Table layout
// - Pagination
// - Document styling
// - Export function signature
```

### Step 6: Test Integration
```javascript
// test/ledgerExport.test.js

test('Frontend PDF uses canonical balance (not independent calculation)', async () => {
  // Mock canonical API
  const mockCanonical = {
    opening_balance: 1000.00,
    transactions: [
      {
        id: 1,
        type: 'PURCHASE',
        amount: 500.00,
        license_running_balance: 1500.00,
        is_commission: false,
      },
      {
        id: 2,
        type: 'SALE',
        amount: 200.00,
        license_running_balance: 1300.00,
        is_commission: false,
      },
    ],
    license_running_balance: 1300.00,
  };
  
  // Generate PDF
  const pdfData = await generateLedgerPdf(licenseId);
  
  // Verify PDF contains canonical balance, not independent calc
  expect(pdfData).toContain('1500.00');  // txn 1 balance (from canonical)
  expect(pdfData).toContain('1300.00');  // final balance (from canonical)
  expect(pdfData).toContain('1000.00');  // opening balance (from canonical)
});
```

---

## GOLDEN SCENARIO PARITY TEST

For each of 14 golden scenarios:

```
Scenario N:
  Backend canonical balance: XXXX.XX
  Backend PDF balance: XXXX.XX
  Frontend PDF balance: XXXX.XX
  
  Expected: All three match exactly (zero financial difference)
```

**Gate Criteria:**
- ✅ All 14 scenarios match canonical
- ✅ All balances exactly 2 decimal places
- ✅ Opening balance correct
- ✅ Commission not counted
- ✅ Company utilization correct
- ✅ Final balance correct

---

## RISK ASSESSMENT

### Medium Risk: API Integration
- **Risk:** API endpoint changes break PDF
- **Mitigation:** API is stable (gate 4C), version compatibility

### Low Risk: Presentation Layer
- **Risk:** PDF layout issues
- **Mitigation:** No business logic changes, only formatting

### Zero Risk: Financial Correctness
- **Risk:** Balance mismatch
- **Mitigation:** Using canonical service (proven correct)

---

## SUCCESS CRITERIA

✅ Phase 4E-C PASS requires:
- [ ] No independent balance calculation in frontend
- [ ] All balance data from CanonicalLedgerService API
- [ ] All 14 golden scenarios produce canonical-matching balances
- [ ] API ↔ PDF ↔ Frontend PDF parity (zero financial difference)
- [ ] No commission recalculation
- [ ] No opening balance recalculation
- [ ] Decimal precision: 2 places
- [ ] Deterministic ordering preserved
- [ ] PDF renders without errors
- [ ] Git scope clean

---

## AUTO-EXECUTION CHECKLIST

When this phase auto-launches:

```
[ ] Read this guide
[ ] Audit current frontend PDF implementation
[ ] Verify API contract (already tested in 4B/4C)
[ ] Create canonical ledger adapter
[ ] Update PDF generation to use canonical data
[ ] Remove old balance calculation code
[ ] Run golden scenario parity tests (14/14 must match)
[ ] Run frontend test suite
[ ] Verify git diff shows only frontend changes
[ ] Create PHASE_4E_C_COMPLETION_REPORT.md
[ ] Determine gate: PASS or BLOCKED
[ ] If PASS: auto-launch 4E-D
```

---

**Ready for auto-execution after Phase 4E-B PASS**
