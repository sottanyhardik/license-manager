# License Ledger — Approved Semantics (Option C — Hybrid with Canonical Backend)

**Decision ID:** LEDGER-C-HYBRID-CANONICAL  
**Approval Date:** 2026-08-10  
**Approved Option:** C (Hybrid with Single Authoritative Backend)  
**Business Authority:** Product Management / Business Stakeholder  
**Implementation Phase:** Gate 3+ (Post-approval)  

---

## EXECUTIVE SUMMARY

The License Ledger Detail module shall implement **Option C — Hybrid with Canonical Backend Architecture**:

- **License Running Balance** is authoritative and calculated once by the backend
- **Company Utilization Balances** are secondary, derived views showing each company's own attribution
- **COMMISSION** transactions are visible for auditability but excluded from running balance calculations
- **All three outputs** (Screen, PDF, Excel) use the same canonical backend dataset

---

## SEMANTIC DEFINITION

### License Running Balance (Authoritative)

**Definition:**  
The cumulative financial position of the entire license across all companies and all balance-affecting transaction types.

**Scope:**  
- License-wide
- Single number per license at any point in the transaction history
- Represents the license's total available position

**Calculation:**  
```
License Running Balance = Opening Balance + SUM(balance-affecting transactions across all companies)

Where balance-affecting transactions are:
- PURCHASE: +amount
- SALE: -amount
- Opening Balance: initialized once

Excluded from calculation:
- COMMISSION (visible, but not counted)
```

**Example:**
```
Opening Balance:        1000.00
+ PURCHASE (Company A):  +500.00  → License Running Balance: 1500.00
- SALE (Company A):      -200.00  → License Running Balance: 1300.00
+ PURCHASE (Company B):  +400.00  → License Running Balance: 1700.00
- SALE (Company B):      -150.00  → License Running Balance: 1550.00
+ COMMISSION (Comp C):   (excluded)
```

**Business Meaning:**  
"At this point in the transaction history, the license has a cumulative financial position of X."

### Company Utilization Balance (Secondary)

**Definition:**  
Each company's own utilization of the license, calculated independently for each company.

**Scope:**  
- Per-company
- Resets to zero for each company
- Shows only that company's contribution to license usage

**Calculation:**  
```
For each Company:
Company Utilization Balance = SUM(balance-affecting transactions for that company ONLY)

Where:
- PURCHASE: +amount
- SALE: -amount

EXCLUDED:
- COMMISSION (never counted, reset to zero for that company)
```

**Example (same data as above, per-company breakdown):**
```
Company A:
  PURCHASE: +500.00
  SALE:     -200.00
  ─────────────────
  Utilization: 300.00

Company B:
  PURCHASE: +400.00
  SALE:     -150.00
  ─────────────────
  Utilization: 250.00

Company C:
  COMMISSION: (excluded, balance = 0)
  ─────────────────
  Utilization: 0.00
```

**Business Meaning:**  
"Company X has used Y of this license (purchase minus sales for that company only)."

**Critical Property:**  
Sum of company balances ≠ License Running Balance (they are different metrics, not decompositions).  
This must be visually clear in all three outputs (Screen, PDF, Excel) to avoid confusion.

### COMMISSION Transaction Treatment

**Definition:**  
COMMISSION transactions are internal/accounting transactions between companies or the exporter and regulatory authorities.

**Visibility:**  
- **Screen:** Visible in transaction list
- **PDF:** Visible in transaction list
- **Excel:** Visible in transaction list

**Balance Impact:**  
- **License Running Balance:** NOT counted (excluded)
- **Company Utilization:** NOT counted (excluded)
- **Display Marker:** Should be clearly marked "Excluded from License Balance" or similar

**Example (Scenario 3 from golden dataset):**
```
Opening:                1000.00
+ PURCHASE (A):         +500.00  → Running Balance: 1500.00
+ COMMISSION (B):       +100.00  → Running Balance: 1500.00 (COMMISSION not added)
                                   [Visible: "COMMISSION - Excluded from Balance"]
- SALE (A):             -200.00  → Running Balance: 1300.00
```

**Why?**  
COMMISSION is an administrative charge, not a true balance-affecting transaction. Including it would conflate regulatory/internal fees with actual import/export activity. The authoritative balance must not include administrative overhead.

---

## TRANSACTION ORDERING RULES

### Transaction Sequence

Transactions must be ordered by:
1. **Date** (primary): Transaction date (chronological ascending)
2. **ID** (secondary tiebreaker): Transaction ID (numeric ascending) when multiple transactions occur on same date
3. **Company** (tertiary, for display only): Group by company for readability, but order within company must respect date+ID

### Running Balance Calculation Order

Running balance is calculated strictly in transaction date+ID order, regardless of company grouping in the display.

**Example:**
```
Displayed:
Company A:
  2026-01-15 | PURCHASE | +100 | Balance: 100
Company B:
  2026-01-15 | PURCHASE | +200 | Balance: 200

Running Balance (license-wide, by date+ID):
  Txn 1 (2026-01-15, ID 100): PURCHASE +100 → Running: 100
  Txn 2 (2026-01-15, ID 101): PURCHASE +200 → Running: 300

Result:
  Company A balance: 100 (own contribution)
  Company B balance: 200 (own contribution)
  License balance: 300 (both contributions)
```

---

## OPENING BALANCE TREATMENT

### Definition

The opening balance is the license's initial financial position, recorded before any transactions.

### Calculation

Opening balance is a single transaction:
- **Type:** OPENING
- **Amount:** Initial balance amount (e.g., 1000.00)
- **Company:** None (license-level)
- **COMMISSION:** No (not applicable)

### Running Balance Impact

```
Running Balance (start of ledger) = Opening Balance
```

### Company Utilization Impact

Opening balance does NOT distribute to individual company utilizations:
- Each company starts at 0
- Company utilization shows only that company's transactions

### Visual Representation

**Screen:**
```
OPENING | - | 0.00 | Balance: 1000.00
```

**PDF:**
```
Date: [Issue Date]
Opening Balance: 1000.00
```

**Excel:**
```
[Opening Row]
Amount: 1000.00
Running Balance: 1000.00
```

---

## CLOSING BALANCE TREATMENT

### Definition

The closing balance is the final running balance at the end of the ledger report.

### Calculation

```
Closing Balance = Opening Balance + SUM(all balance-affecting transactions)
                = Last row's Running Balance
```

### Representation

**Screen:**
- Footer row or summary panel showing "Closing Balance" or "Final Balance"
- Value: Last transaction's running balance

**PDF:**
- Summary section after transaction table
- Shows license-wide closing balance

**Excel:**
- Final row or summary sheet
- Total row showing closing balance

### Company Closing Balances

Each company also has a "closing utilization balance" = sum of that company's transactions.

---

## DECIMAL PRECISION & ROUNDING

### Precision Standard

All balance calculations use **2 decimal places** (USD cents).

### Rules

1. **Storage:** All balances stored with 2-place precision in database
2. **Calculation:** Intermediate calculations may use higher precision, final results rounded to 2 places
3. **Display:** All outputs (Screen, PDF, Excel) show exactly 2 decimal places
4. **Rounding Method:** Python `Decimal` with ROUND_HALF_UP (standard commercial rounding)

### Example

```
Opening:      1000.00
+ Purchase:   +123.45  → Balance: 1123.45
- Sale:       -67.89   → Balance: 1055.56

NOT: 1055.5600 (excess precision)
NOT: 1055.6 (truncated)
YES: 1055.56 (exactly 2 places)
```

---

## COMPANY SCOPE RULES

### Company Independence

Each company's utilization balance is **calculated independently** from all other companies.

**Rule 1: No Cross-Company Inheritance**
```
Company A's balance is NOT affected by adding Company B transactions.
```

**Example:**
```
Before Company B transaction:
  Company A balance: 300.00

Add Company B transaction:
  Company B PURCHASE: +500.00

After Company B transaction:
  Company A balance: 300.00 (unchanged)
  Company B balance: 500.00
```

**Rule 2: Sum of Company Balances ≠ License Balance**
```
SUM(Company Balances) does NOT necessarily equal License Running Balance.
This is by design, not a bug.

Why?
- License balance includes all companies' transactions
- Company balances are independent projections of each company's usage
- They answer different questions
```

**Example:**
```
Company A: 300.00
Company B: 250.00
Company C: 100.00
─────────────────
Sum:       650.00

License Running Balance: 650.00 (if opening was 0)
```

In this case, SUM = License, but that's coincidental, not required.

**Rule 3: Company-Scoped Fields Must Reset**

When displaying company-level data (PDF per-company pages, Excel company columns), any running or accumulated balance must reset to 0 for that company.

```
PDF Page: Company A
Opening:      0.00 (not 1000.00, not inherited)
+ Purchase:   +300.00
- Sale:       -50.00
Closing:      250.00
```

---

## EDGE CASES & CLARIFICATIONS

### Empty Ledger (No Transactions)

```
Opening Balance: [0.00 or N/A, if no opening transaction]
Transactions: [None]
Closing Balance: [0.00 or Opening, depending on policy]

Display:
Screen: "No transactions" message, show opening if available
PDF:    "No transactions to display"
Excel:  [Opening row, if available] + [Empty rows message]
```

### Zero-Amount Transactions

```
Type: PURCHASE
Amount: 0.00

Impact: No change to running balance
Display: Visible in transaction list, shows 0 amount
Running Balance: Unchanged from previous transaction
```

### Negative Balance (if permitted by business rules)

```
If allowed:
Opening:       500.00
- Sale:       -1000.00
Closing:      -500.00

Display: Negative balance clearly marked (may show in red, with warning)
```

**Note:** Document business rule on whether negative balances are permitted.

### Large Transaction Count (100+ transactions)

```
System must handle without error.
All calculations must be correct and complete.
No truncation or pagination of balance calculation.
(Pagination in UI is allowed; balance calculation is not.)
```

### Same-Date Transactions

```
All transactions on same date must be ordered deterministically.
Use transaction ID (or timestamp) as tiebreaker.
Final balance must be identical regardless of display order.

Example:
  2026-01-15 Transaction 1: +100
  2026-01-15 Transaction 2: -30
  
Always calculate in ID order (1 then 2), even if displayed differently.
Final balance: always 70, never 70.
```

### Only COMMISSION Transactions

```
Example:
Opening:          500.00
+ COMMISSION:     +100.00
+ COMMISSION:     +200.00
+ COMMISSION:     +300.00

Running Balance (excluding COMMISSION):
Initial:          500.00
Final:            500.00 (unchanged, COMMISSION not added)

Display:
All COMMISSION rows visible with "Excluded from Balance" marker.
Final balance: 500.00 (not 1100.00).
```

---

## CROSS-OUTPUT CONSISTENCY CONTRACT

### Golden Rule

**All three outputs (Screen, PDF, Excel) must derive from the same canonical backend dataset and produce identical semantic results.**

### What Must Match

| Aspect | Screen | PDF | Excel | Rule |
|--------|--------|-----|-------|------|
| License Running Balance | YES | YES | YES | Identical value |
| COMMISSION Excluded | YES | YES | YES | All exclude from balance |
| Company Utilization Balances | YES | YES | YES | Identical per-company values |
| Transaction Order | YES | YES | YES | Deterministic by date+ID |
| Decimal Precision | 2 places | 2 places | 2 places | Never diverge |
| Canonical Source | API backend | API backend | API backend | Single source of truth |

### What May Differ (Presentation Only)

| Aspect | Screen | PDF | Excel |
|--------|--------|-----|-------|
| Layout/Formatting | Responsive table | Formatted document | Spreadsheet columns |
| Company Grouping | Sortable, filterable | By page breaks | By columns |
| Navigation | Scroll, pagination | Page numbers | Sheet tabs |
| Styling | Light/dark mode | Branding | Cell formatting |

The underlying **numbers must never differ**.

---

## CONFIGURATION & VALIDATION

### Backend Ledger Builder Canonical Functions

These functions are **THE** authoritative source of truth:

- `build_dfia_ledger_detail()` → Primary DFIA ledger
- `build_incentive_ledger_detail()` → Incentive scheme ledger

All outputs (API, PDF, Excel) must call these or receive pre-calculated results from these.

### API Response Structure

```json
{
  "license_running_balance": 1300.00,
  "company_utilizations": {
    "company_uuid_A": 300.00,
    "company_uuid_B": 250.00,
    "company_uuid_C": 100.00
  },
  "transactions": [
    {
      "id": "txn_1",
      "date": "2026-01-15",
      "type": "OPENING",
      "company": null,
      "amount": 1000.00,
      "running_balance": 1000.00,
      "is_commission": false
    },
    {
      "id": "txn_2",
      "date": "2026-01-20",
      "type": "PURCHASE",
      "company": "uuid_A",
      "amount": 500.00,
      "running_balance": 1500.00,
      "is_commission": false
    },
    {
      "id": "txn_3",
      "date": "2026-02-01",
      "type": "COMMISSION",
      "company": "uuid_B",
      "amount": 100.00,
      "running_balance": 1500.00,
      "is_commission": true
    }
  ]
}
```

### Validation Checklist

Before shipping any implementation:

- [ ] License running balance matches backend calculation exactly
- [ ] Company utilizations match per-company sums exactly
- [ ] COMMISSION transactions are marked `is_commission: true`
- [ ] COMMISSION not included in running balance calculation
- [ ] Transaction order is deterministic (date+ID)
- [ ] All decimal values are exactly 2 places
- [ ] API, PDF, and Excel all produce identical balances
- [ ] Edge cases (empty, zero, negative) are handled
- [ ] Large datasets (100+) calculated without error

---

## BUSINESS RULES & CONSTRAINTS

### Rule 1: No Backend Recalculation by Frontend

**Forbidden:**
```javascript
// Frontend recalculates balance ❌
let balance = 0;
transactions.forEach(t => {
  if (t.type === 'PURCHASE') balance += t.amount;
  if (t.type === 'SALE') balance -= t.amount;
});
```

**Required:**
```javascript
// Frontend receives from backend ✅
let balance = response.license_running_balance;
let companyBalance = response.company_utilizations[companyId];
```

### Rule 2: COMMISSION Exclusion is Non-Negotiable

COMMISSION transactions must **never** be included in any balance calculation, regardless of:
- Report type (screen/PDF/Excel)
- Scope (license/company)
- Business request

They are visible for auditability only.

### Rule 3: Single Source of Truth

Backend ledger builders (`build_dfia_ledger_detail`, etc.) are THE canonical source.

All exports (API, PDF, Excel) must receive pre-calculated balances from the backend, not recalculate.

### Rule 4: Company Isolation is Strict

No company's balance calculation may reference or depend on:
- Another company's transactions
- Another company's balance
- Aggregate/global state

Each company is independent.

---

## TESTING STRATEGY

### Phase 2 (Current): Characterization Tests

Create comprehensive test suite covering:

1. **Balance Formula Tests**
   - Single company, single license
   - Multiple companies
   - COMMISSION exclusion
   - Large transaction counts

2. **Company Isolation Tests**
   - Companies calculated independently
   - Adding Company B doesn't change Company A balance

3. **Edge Case Tests**
   - Empty ledger
   - Zero-amount transactions
   - Negative balances
   - Same-date ordering

4. **Decimal & Rounding Tests**
   - 2-place precision
   - No floating-point errors

5. **Cross-Output Parity Tests**
   - Screen, PDF, Excel produce same balances
   - Using same canonical dataset

6. **P0 Defect Regression Tests**
   - Screen/PDF/Excel agreement
   - No divergence between outputs

### Phase 3 (Implementation): Implementation Design

Detailed implementation plan (separate document).

### Phase 4 (Verification): Live Testing

Run characterization tests against implementation to verify compliance.

---

## APPROVAL SIGN-OFF

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product Manager | [Name] | 2026-08-10 | [Approved] |
| Engineering Lead | [Name] | 2026-08-10 | [Approved] |
| QA Lead | [Name] | 2026-08-10 | [Approved] |

---

## DOCUMENT REFERENCES

- **Original Decision:** `docs/decisions/LEDGER_BALANCE_CONVENTION_DECISION.md`
- **Golden Dataset:** `docs/modules/LEDGER_GOLDEN_DATASET.md`
- **Current vs Approved:** `docs/modules/LEDGER_CURRENT_VS_APPROVED.md`
- **Characterization Tests:** `backend/apps/license/tests/test_ledger_characterization_option_c.py`
- **Implementation Plan:** `docs/modules/LEDGER_IMPLEMENTATION_PLAN.md` (Phase 3+)

---

**Document Version:** 1.0  
**Last Updated:** 2026-08-10  
**Status:** APPROVED
