# License Ledger Golden Dataset — 14 Test Scenarios

**Purpose:**  
Deterministic, manually-verifiable test scenarios that encode the approved Option C semantics. Each scenario includes explicit calculations, expected results, and business rationale.

**Golden Dataset Version:** 1.0  
**Created:** 2026-08-10  
**Status:** Master reference for all characterization and integration tests

---

## Scenario 1: Single License, Single Company, Simple Flow

### Purpose
Foundational test: verify basic license-wide running balance with single company.

### Input Transactions

| Date | Txn ID | Company | Type | Amount | Notes |
|------|--------|---------|------|--------|-------|
| 2026-01-01 | 1 | - | OPENING | 1000.00 | Initial license balance |
| 2026-01-15 | 2 | Company A | PURCHASE | 500.00 | Purchase transaction |
| 2026-02-01 | 3 | Company A | SALE | 200.00 | Sale transaction |

### Calculations

**License Running Balance (Authoritative):**
```
Opening:                    1000.00
+ PURCHASE (Company A):      +500.00
  → Running Balance:         1500.00
- SALE (Company A):          -200.00
  → Running Balance:         1300.00

FINAL LICENSE BALANCE:       1300.00
```

**Company A Utilization Balance (Secondary):**
```
Company A (reset to 0):       0.00
+ PURCHASE:                  +500.00
  → Company A Balance:        500.00
- SALE:                       -200.00
  → Company A Balance:        300.00

FINAL COMPANY A BALANCE:      300.00
```

### Expected Results

| Metric | Expected Value |
|--------|---|
| License Running Balance | 1300.00 |
| Company A Utilization | 300.00 |
| Number of Transactions | 3 |
| COMMISSION Count | 0 |

### Why This Scenario Matters

- Establishes baseline running balance calculation
- Verifies PURCHASE increments balance
- Verifies SALE decrements balance
- Shows company balance calculation (independent from license balance)
- Baseline for all other scenarios

---

## Scenario 2: Single License, Multiple Companies (A, B, C)

### Purpose
Verify license-wide running balance aggregates correctly across multiple companies.

### Input Transactions

| Date | Txn ID | Company | Type | Amount |
|------|--------|---------|------|--------|
| 2026-01-01 | 1 | - | OPENING | 2000.00 |
| 2026-01-10 | 2 | Company A | PURCHASE | 400.00 |
| 2026-01-20 | 3 | Company A | SALE | 150.00 |
| 2026-02-01 | 4 | Company B | PURCHASE | 600.00 |
| 2026-02-15 | 5 | Company B | SALE | 300.00 |
| 2026-03-01 | 6 | Company C | PURCHASE | 200.00 |
| 2026-03-15 | 7 | Company C | SALE | 100.00 |

### Calculations

**License Running Balance (by date+ID order):**
```
Opening:                        2000.00
+ PURCHASE (Comp A, Txn 2):     +400.00  → 2400.00
- SALE (Comp A, Txn 3):         -150.00  → 2250.00
+ PURCHASE (Comp B, Txn 4):     +600.00  → 2850.00
- SALE (Comp B, Txn 5):         -300.00  → 2550.00
+ PURCHASE (Comp C, Txn 6):     +200.00  → 2750.00
- SALE (Comp C, Txn 7):         -100.00  → 2650.00

FINAL LICENSE BALANCE:          2650.00
```

**Company A Utilization:**
```
PURCHASE:   400.00
SALE:      -150.00
─────────────────
TOTAL:      250.00
```

**Company B Utilization:**
```
PURCHASE:   600.00
SALE:      -300.00
─────────────────
TOTAL:      300.00
```

**Company C Utilization:**
```
PURCHASE:   200.00
SALE:      -100.00
─────────────────
TOTAL:      100.00
```

### Expected Results

| Metric | Value |
|--------|-------|
| License Running Balance | 2650.00 |
| Company A Utilization | 250.00 |
| Company B Utilization | 300.00 |
| Company C Utilization | 100.00 |
| Sum of Company Balances | 650.00 |
| Note: Sum ≠ License Balance | This is correct design |

### Why This Scenario Matters

- Demonstrates license-wide aggregation across multiple companies
- Shows that sum of company balances ≠ license balance (different metrics)
- Tests deterministic ordering (date+ID)
- Critical for multi-company audits
- Reveals if any company's txn is incorrectly affecting license balance

---

## Scenario 3: COMMISSION Exclusion (Not Counted in Balance)

### Purpose
Verify COMMISSION transactions are visible but excluded from running balance calculation.

### Input Transactions

| Date | Txn ID | Company | Type | Amount | Notes |
|------|--------|---------|------|--------|-------|
| 2026-01-01 | 1 | - | OPENING | 500.00 | Opening |
| 2026-01-15 | 2 | Company A | PURCHASE | 300.00 | Purchase for A |
| 2026-02-01 | 3 | Company B | COMMISSION | 100.00 | Commission (internal) |
| 2026-02-15 | 4 | Company A | SALE | 80.00 | Sale by A |

### Calculations

**License Running Balance (COMMISSION excluded):**
```
Opening:                        500.00
+ PURCHASE (Comp A, Txn 2):    +300.00  → 800.00
+ COMMISSION (Comp B, Txn 3):   (NOT COUNTED)
                                  → 800.00  [COMMISSION visible but not added]
- SALE (Comp A, Txn 4):         -80.00  → 720.00

FINAL LICENSE BALANCE:          720.00  [NOT 800.00 + 100.00]
```

**Company A Utilization:**
```
PURCHASE:   300.00
SALE:        -80.00
─────────────────
TOTAL:      220.00
```

**Company B Utilization:**
```
COMMISSION: (NOT COUNTED)
─────────────────
TOTAL:        0.00
```

### Expected Results

| Metric | Value |
|--------|-------|
| License Running Balance | 720.00 |
| Company A Utilization | 220.00 |
| Company B Utilization | 0.00 |
| COMMISSION Visible | YES |
| COMMISSION in Balance | NO |
| COMMISSION Row Display | "Excluded from License Balance" marker |

### Why This Scenario Matters

- **Critical:** COMMISSION exclusion is non-negotiable
- Demonstrates visibility without counting
- Tests that accidental inclusion breaks test
- Original P0 defect: Screen included, PDF/Excel excluded
- Approved semantics: exclude everywhere

---

## Scenario 4: Company-Level Isolation (Independent Calculations)

### Purpose
Verify that company balances are calculated independently and adding Company B doesn't change Company A.

### Input Transactions

| Date | Txn ID | Company | Type | Amount |
|------|--------|---------|------|--------|
| 2026-01-01 | 1 | - | OPENING | 0.00 |
| 2026-01-10 | 2 | Company A | PURCHASE | 500.00 |
| 2026-01-20 | 3 | Company A | SALE | 200.00 |
| 2026-02-10 | 4 | Company B | PURCHASE | 800.00 |
| 2026-02-20 | 5 | Company B | SALE | 300.00 |

### Calculations

**License Running Balance:**
```
Opening:                        0.00
+ PURCHASE (A):                +500.00  → 500.00
- SALE (A):                    -200.00  → 300.00
+ PURCHASE (B):                +800.00  → 1100.00
- SALE (B):                    -300.00  → 800.00

FINAL:                          800.00
```

**Company A (isolated, no effect from B):**
```
PURCHASE (A):    500.00
SALE (A):       -200.00
─────────────────
TOTAL (A):       300.00
```

**Company B (isolated, no effect from A):**
```
PURCHASE (B):    800.00
SALE (B):       -300.00
─────────────────
TOTAL (B):       500.00
```

### Test Assertions

1. **Before adding Company B:** Company A balance = 300.00
2. **After adding Company B:** Company A balance = 300.00 (unchanged)
3. Company B balance = 500.00 (independent)
4. License balance = 800.00 (sum of A+B contributions)

### Why This Scenario Matters

- Tests isolation: Company A is not affected by Company B
- Prevents accidental cross-company contamination
- Critical for multi-tenant scenarios
- Reveals if balance calculation mixes company data

---

## Scenario 5: Decimal Precision (2 Decimal Places)

### Purpose
Verify all calculations maintain exactly 2 decimal places, no floating-point errors.

### Input Transactions

| Date | Txn ID | Company | Type | Amount |
|------|--------|---------|------|--------|
| 2026-01-01 | 1 | - | OPENING | 1000.00 |
| 2026-01-15 | 2 | Company A | PURCHASE | 123.45 |
| 2026-02-01 | 3 | Company A | SALE | 67.89 |

### Calculations

**License Running Balance:**
```
Opening:          1000.00
+ PURCHASE:      +123.45
                 ─────────
                 1123.45
- SALE:           -67.89
                 ─────────
                 1055.56

Expected: 1055.56 (exactly 2 decimal places)
Not: 1055.5600 (excess precision)
Not: 1055.6 (truncated)
```

**Company A:**
```
PURCHASE:  123.45
SALE:       -67.89
─────────────────
TOTAL:      55.56  (exactly 2 places)
```

### Expected Results

| Metric | Value | Format |
|--------|-------|--------|
| License Balance | 1055.56 | 2 decimal places |
| Company A Balance | 55.56 | 2 decimal places |
| Precision Error | 0.00 | No rounding artifacts |

### Why This Scenario Matters

- Prevents floating-point accumulation errors
- Ensures consistency in financial reporting
- Critical for audit trails (small errors compound)
- Tests Decimal precision implementation

---

## Scenario 6: Same-Date Transaction Ordering (Deterministic)

### Purpose
Verify multiple transactions on same date are ordered deterministically and produce same final balance.

### Input Transactions

| Date | Txn ID | Company | Type | Amount |
|------|--------|---------|------|--------|
| 2026-01-15 | 1 | Company A | PURCHASE | 100.00 |
| 2026-01-15 | 2 | Company A | SALE | 30.00 |
| 2026-01-15 | 3 | Company A | PURCHASE | 50.00 |

### Calculations

**Chronological by Txn ID (authoritative order):**
```
Initial:          0.00
Txn 1 (+100):    +100.00  → 100.00
Txn 2 (-30):      -30.00  → 70.00
Txn 3 (+50):      +50.00  → 120.00

FINAL:            120.00
```

### Test Assertions

1. Final balance = 120.00 (regardless of display order)
2. Running balance sequence is deterministic
3. If displayed in different order, balances still calculated correctly
4. Order is by Txn ID (or timestamp as tiebreaker)

### Why This Scenario Matters

- Prevents ambiguous balance ordering
- Ensures reproducible results
- Tests tiebreaker logic (date+ID)
- Critical for ledger audits

---

## Scenario 7: Zero-Amount Transactions

### Purpose
Verify zero-amount transactions don't affect balance and are handled gracefully.

### Input Transactions

| Date | Txn ID | Company | Type | Amount |
|------|--------|---------|------|--------|
| 2026-01-01 | 1 | - | OPENING | 1000.00 |
| 2026-01-15 | 2 | Company A | PURCHASE | 0.00 |
| 2026-02-01 | 3 | Company A | SALE | 0.00 |
| 2026-03-01 | 4 | Company A | PURCHASE | 100.00 |

### Calculations

**License Running Balance:**
```
Opening:          1000.00
+ PURCHASE (0):     +0.00  → 1000.00
- SALE (0):         -0.00  → 1000.00
+ PURCHASE (100):  +100.00 → 1100.00

FINAL:            1100.00
```

**Company A:**
```
PURCHASE (0):       0.00
SALE (0):           0.00
PURCHASE (100):   +100.00
─────────────────
TOTAL:            100.00
```

### Expected Results

| Metric | Value |
|--------|-------|
| License Balance | 1100.00 |
| Company A Balance | 100.00 |
| Zero-Amount Txn Visible | YES |
| Zero-Amount in Balance | NO (correctly ignored) |

### Why This Scenario Matters

- Tests edge case: no-op transactions
- Verifies zero doesn't cause errors
- Ensures zero-amount rows are visible but not counted
- Real-world: cancelled/reversed transactions may be recorded as 0

---

## Scenario 8: Large Transaction Count (100+ Transactions)

### Purpose
Verify system handles large datasets correctly without accumulation errors or truncation.

### Input Transactions

- 100+ transactions across 3 companies
- Mix of PURCHASE, SALE, COMMISSION
- Dates spread over 12 months
- Amounts: 10.00 to 999.99

### Calculations

**Pseudo-calculation (example structure):**
```
Opening:                     10000.00
Txn 1-50 (Company A, mixed): +1200.34  → 11200.34
Txn 51-75 (Company B, mixed): +2500.67 → 13700.01
Txn 76-100 (Company C, mixed): -3400.78 → 10299.23
Txn 101+ (various COMMISSION):  (excluded)

FINAL LICENSE BALANCE:       10299.23  [+/- per actual txn amounts]
```

### Test Assertions

1. No truncation of transactions
2. Final balance is correct (sum of all balance-affecting txns)
3. System handles 100+ without error
4. Running balance sequence is complete
5. All company balances calculated correctly

### Why This Scenario Matters

- Performance: system can handle real-world ledgers
- Correctness: no accumulation errors in large sets
- Completeness: all transactions included
- Real-world ledgers: can have 100+ transactions easily

---

## Scenario 9: Empty Ledger (No Transactions)

### Purpose
Verify system handles empty ledger gracefully (no opening, no txns).

### Input Transactions

| Transaction | Count |
|---|---|
| OPENING | 0 |
| PURCHASE | 0 |
| SALE | 0 |
| COMMISSION | 0 |
| Total | 0 |

### Calculations

**License Running Balance:**
```
No opening → Initial balance: 0.00
No transactions
Final balance: 0.00
```

**Company Balances:**
```
All companies: 0.00
```

### Expected Results

| Metric | Value |
|--------|-------|
| License Balance | 0.00 or N/A |
| Company Balances | 0.00 or N/A |
| Transaction Count | 0 |
| Display | "No transactions" message |

### Why This Scenario Matters

- Edge case: new license with no activity
- Tests graceful degradation (no error, clear message)
- UX: users should see clear "empty" indication
- Real-world: happens for new licenses

---

## Scenario 10: COMMISSION-Only Transactions

### Purpose
Verify that if ledger contains ONLY COMMISSION (no PURCHASE/SALE), balance remains unaffected.

### Input Transactions

| Date | Txn ID | Company | Type | Amount |
|------|--------|---------|------|--------|
| 2026-01-01 | 1 | - | OPENING | 1000.00 |
| 2026-01-15 | 2 | Company B | COMMISSION | 100.00 |
| 2026-02-01 | 3 | Company B | COMMISSION | 50.00 |
| 2026-03-01 | 4 | Company C | COMMISSION | 200.00 |

### Calculations

**License Running Balance (COMMISSION excluded):**
```
Opening:                    1000.00
+ COMMISSION (B, 100):      (NOT COUNTED)
                               → 1000.00
+ COMMISSION (B, 50):       (NOT COUNTED)
                               → 1000.00
+ COMMISSION (C, 200):      (NOT COUNTED)
                               → 1000.00

FINAL:                      1000.00  [unchanged]
```

**All Company Balances:**
```
Company B: 0.00 (COMMISSION not counted)
Company C: 0.00 (COMMISSION not counted)
```

### Expected Results

| Metric | Value |
|--------|-------|
| License Balance | 1000.00 |
| Company B Balance | 0.00 |
| Company C Balance | 0.00 |
| COMMISSION Rows Visible | YES (3 rows) |
| COMMISSION in Balance | NO |

### Why This Scenario Matters

- Extreme case: all-commission ledger
- Tests that COMMISSION is completely excluded
- Demonstrates visibility without impact
- Original defect: some systems counted COMMISSION

---

## Scenario 11: Opening + Company Balances Only (No Mixed Transactions)

### Purpose
Verify ledger with opening and per-company activity (no interleaved companies).

### Input Transactions

| Date | Txn ID | Company | Type | Amount |
|------|--------|---------|------|--------|
| 2026-01-01 | 1 | - | OPENING | 5000.00 |
| 2026-01-15 | 2 | Company A | PURCHASE | 1000.00 |
| 2026-01-20 | 3 | Company A | PURCHASE | 1000.00 |
| 2026-01-25 | 4 | Company A | SALE | 500.00 |
| 2026-02-01 | 5 | Company B | PURCHASE | 2000.00 |
| 2026-02-10 | 6 | Company B | SALE | 1000.00 |

### Calculations

**License Running Balance:**
```
Opening:                     5000.00
+ PURCHASE (A, 1000):       +1000.00 → 6000.00
+ PURCHASE (A, 1000):       +1000.00 → 7000.00
- SALE (A, 500):             -500.00 → 6500.00
+ PURCHASE (B, 2000):       +2000.00 → 8500.00
- SALE (B, 1000):           -1000.00 → 7500.00

FINAL:                      7500.00
```

**Company A:**
```
PURCHASE: 1000 + 1000 = 2000
SALE: 500
─────────────────────────
TOTAL: 1500.00
```

**Company B:**
```
PURCHASE: 2000
SALE: 1000
─────────────────────────
TOTAL: 1000.00
```

### Expected Results

| Metric | Value |
|--------|-------|
| License Balance | 7500.00 |
| Company A Balance | 1500.00 |
| Company B Balance | 1000.00 |
| Sum of Company Balances | 2500.00 |
| Opening | 5000.00 |

### Why This Scenario Matters

- Tests company-grouped activity (transactions per company in sequence)
- Verifies opening is counted once
- Shows realistic ledger structure

---

## Scenario 12: Mixed Company Transactions (Interleaved)

### Purpose
Verify ledger with companies interleaved (A, B, A, C, B, A order) still calculates correctly.

### Input Transactions

| Date | Txn ID | Company | Type | Amount |
|------|--------|---------|------|--------|
| 2026-01-01 | 1 | - | OPENING | 3000.00 |
| 2026-01-10 | 2 | A | PURCHASE | 100.00 |
| 2026-01-15 | 3 | B | PURCHASE | 200.00 |
| 2026-01-20 | 4 | A | SALE | 50.00 |
| 2026-02-01 | 5 | C | PURCHASE | 150.00 |
| 2026-02-15 | 6 | B | SALE | 100.00 |
| 2026-03-01 | 7 | A | PURCHASE | 75.00 |

### Calculations

**License Running Balance (by date+ID):**
```
Opening:        3000.00
A +100:        +100.00 → 3100.00
B +200:        +200.00 → 3300.00
A -50:          -50.00 → 3250.00
C +150:        +150.00 → 3400.00
B -100:        -100.00 → 3300.00
A +75:          +75.00 → 3375.00

FINAL:         3375.00
```

**Company A (sum of A-only txns):**
```
PURCHASE (100):  +100.00
SALE (50):        -50.00
PURCHASE (75):   +75.00
─────────────────
TOTAL:           125.00
```

**Company B:**
```
PURCHASE (200): +200.00
SALE (100):     -100.00
─────────────────
TOTAL:          100.00
```

**Company C:**
```
PURCHASE (150): +150.00
─────────────────
TOTAL:          150.00
```

### Test Assertions

1. License balance = 3375.00
2. Company A balance = 125.00 (independent, despite interleaving)
3. Company B balance = 100.00
4. Company C balance = 150.00
5. Sum of companies = 375.00 (not 3375.00, by design)

### Why This Scenario Matters

- Real-world ledger: companies don't appear in groups
- Tests that company calculation is independent of order
- Prevents bugs where interleaving causes errors
- Critical for realistic stress testing

---

## Scenario 13: Multiple Companies with COMMISSION Mix

### Purpose
Verify that with multiple companies and COMMISSION transactions, everything calculates correctly.

### Input Transactions

| Date | Txn ID | Company | Type | Amount |
|------|--------|---------|------|--------|
| 2026-01-01 | 1 | - | OPENING | 2000.00 |
| 2026-01-10 | 2 | A | PURCHASE | 500.00 |
| 2026-01-15 | 3 | A | COMMISSION | 25.00 |
| 2026-01-20 | 4 | A | SALE | 200.00 |
| 2026-02-01 | 5 | B | PURCHASE | 800.00 |
| 2026-02-15 | 6 | C | COMMISSION | 50.00 |
| 2026-03-01 | 7 | C | PURCHASE | 300.00 |
| 2026-03-15 | 8 | B | SALE | 300.00 |

### Calculations

**License Running Balance (COMMISSION excluded):**
```
Opening:                  2000.00
A PURCHASE (500):        +500.00 → 2500.00
A COMMISSION (25):       (excluded) → 2500.00
A SALE (200):            -200.00 → 2300.00
B PURCHASE (800):        +800.00 → 3100.00
C COMMISSION (50):       (excluded) → 3100.00
C PURCHASE (300):        +300.00 → 3400.00
B SALE (300):            -300.00 → 3100.00

FINAL:                   3100.00  [NOT including COMMISSION amounts]
```

**Company Balances:**
```
Company A:
  PURCHASE (500):  +500.00
  COMMISSION (25): (excluded)
  SALE (200):      -200.00
  ─────────────────
  TOTAL:           300.00

Company B:
  PURCHASE (800):  +800.00
  SALE (300):      -300.00
  ─────────────────
  TOTAL:           500.00

Company C:
  COMMISSION (50): (excluded)
  PURCHASE (300):  +300.00
  ─────────────────
  TOTAL:           300.00
```

### Expected Results

| Metric | Value |
|--------|-------|
| License Balance | 3100.00 |
| Company A Balance | 300.00 |
| Company B Balance | 500.00 |
| Company C Balance | 300.00 |
| COMMISSION Rows Visible | 2 (A and C) |
| COMMISSION in Balance | 0 (excluded) |

### Why This Scenario Matters

- Complex: multiple companies + COMMISSION mix
- Tests COMMISSION exclusion in realistic context
- Shows company balances calculated correctly despite COMMISSION

---

## Scenario 14: Real-World Multi-Company Scenario (Comprehensive)

### Purpose
Comprehensive scenario combining all features: opening, multiple companies, COMMISSION, interleaving, spanning months.

### Input Transactions

| Date | Txn ID | Company | Type | Amount |
|------|--------|---------|------|--------|
| 2026-01-01 | 1 | - | OPENING | 10000.00 |
| 2026-01-15 | 2 | A | PURCHASE | 2500.00 |
| 2026-01-20 | 3 | A | COMMISSION | 125.00 |
| 2026-02-01 | 4 | A | SALE | 1000.00 |
| 2026-02-10 | 5 | B | PURCHASE | 3500.00 |
| 2026-02-15 | 6 | C | PURCHASE | 1500.00 |
| 2026-02-20 | 7 | B | COMMISSION | 175.00 |
| 2026-03-01 | 8 | C | SALE | 800.00 |
| 2026-03-10 | 9 | A | PURCHASE | 1200.00 |
| 2026-03-20 | 10 | B | SALE | 1500.00 |
| 2026-04-01 | 11 | C | COMMISSION | 100.00 |
| 2026-04-15 | 12 | A | SALE | 600.00 |

### Calculations

**License Running Balance (step-by-step):**
```
Opening:                           10000.00
A PURCHASE (2500):                +2500.00 → 12500.00
A COMMISSION (125):               (excluded) → 12500.00
A SALE (1000):                    -1000.00 → 11500.00
B PURCHASE (3500):                +3500.00 → 15000.00
C PURCHASE (1500):                +1500.00 → 16500.00
B COMMISSION (175):               (excluded) → 16500.00
C SALE (800):                      -800.00 → 15700.00
A PURCHASE (1200):                +1200.00 → 16900.00
B SALE (1500):                    -1500.00 → 15400.00
C COMMISSION (100):               (excluded) → 15400.00
A SALE (600):                      -600.00 → 14800.00

FINAL:                            14800.00
```

**Company A (all A transactions):**
```
PURCHASE (2500):                  +2500.00
COMMISSION (125):                 (excluded)
SALE (1000):                      -1000.00
PURCHASE (1200):                  +1200.00
SALE (600):                        -600.00
──────────────────────────────────────────
TOTAL:                            2100.00
```

**Company B:**
```
PURCHASE (3500):                  +3500.00
COMMISSION (175):                 (excluded)
SALE (1500):                      -1500.00
──────────────────────────────────────────
TOTAL:                            2000.00
```

**Company C:**
```
PURCHASE (1500):                  +1500.00
SALE (800):                        -800.00
COMMISSION (100):                 (excluded)
──────────────────────────────────────────
TOTAL:                             700.00
```

### Expected Results

| Metric | Value |
|--------|-------|
| License Running Balance | 14800.00 |
| Company A Utilization | 2100.00 |
| Company B Utilization | 2000.00 |
| Company C Utilization | 700.00 |
| Opening Balance | 10000.00 |
| Total Purchased (all companies) | 2500 + 3500 + 1500 + 1200 = 8700 |
| Total Sold (all companies) | 1000 + 800 + 1500 + 600 = 3900 |
| Net from transactions | 8700 - 3900 = 4800 |
| Closing Balance | 10000 + 4800 = 14800 ✓ |
| COMMISSION Rows Visible | 3 (A, B, C) |
| COMMISSION in Balance | 0 (all excluded) |

### Test Assertions

1. License balance = 14800.00 (exactly)
2. Company A = 2100.00 (independent)
3. Company B = 2000.00 (independent)
4. Company C = 700.00 (independent)
5. All COMMISSION rows visible but not counted
6. Running balance sequence is correct
7. Decimal precision maintained (2 places)
8. Opening is counted once

### Why This Scenario Matters

- **Most comprehensive:** real-world complexity
- Tests all features together: opening, companies, COMMISSION, interleaving
- Realistic date span (4 months)
- Verifiable: opening + net = closing
- Serves as master golden dataset for integration testing

---

## GOLDEN DATASET VALIDATION CHECKLIST

For each scenario before committing to tests:

- [ ] Transactions listed with explicit dates and IDs
- [ ] Opening balance documented
- [ ] License running balance calculated step-by-step
- [ ] Company balances calculated independently
- [ ] COMMISSION exclusion clear and correct
- [ ] Expected results match calculations
- [ ] Business rationale documented ("Why This Scenario Matters")
- [ ] Test assertions are testable/verifiable

---

## USAGE IN TESTS

Each scenario becomes a test case in `test_ledger_characterization_option_c.py`:

```python
def test_scenario_1_single_company():
    """Scenario 1: Single License, Single Company, Simple Flow"""
    # Setup from Scenario 1 data
    license = create_test_license_from_golden_data(scenario_1)
    
    # Execute ledger builder
    result = build_dfia_ledger_detail(license)
    
    # Assert
    assert result['license_running_balance'] == Decimal('1300.00')
    assert result['company_utilizations']['company_a'] == Decimal('300.00')
    assert len(result['transactions']) == 3
```

Each golden dataset scenario is deterministic, manually-verifiable, and serves as the contract between business rules and implementation.

---

**Golden Dataset Version:** 1.0  
**Created:** 2026-08-10  
**Status:** Master reference for characterization tests  
**Last Updated:** 2026-08-10
