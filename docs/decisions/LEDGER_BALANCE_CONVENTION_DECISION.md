# Ledger Balance Convention — Business Decision Package
**Date:** 2026-08-10  
**Status:** Awaiting Approval  
**Decision Maker:** Business Stakeholder / Product Management  
**Implementation Impact:** 2–3 days (test + code change)

---

## THE DECISION

**Which running-balance convention should the License Ledger use across all outputs (screen, PDF, Excel)?**

- **Option A:** License-wide running balance (current backend implementation)
- **Option B:** Per-company running balance (current frontend implementation)
- **Option C:** Hybrid (dual view showing both)

**Timeline:** Decision needed before Phase 3 implementation.

---

## CONTEXT

The License Ledger (transaction history view) is currently showing **three different running balances** depending on how the user views it:

| View | Current Behavior | Shows | Notes |
|------|---|---|---|
| **Screen** | Backend data | License-wide running balance | Includes COMMISSION rows |
| **PDF Export** | Recalculated | Per-company running balance | Excludes COMMISSION rows |
| **Excel Export** | Recalculated | Per-company running balance | Excludes COMMISSION rows |

**User Impact:** Users see conflicting numbers and cannot trust the data.

**Root Cause:** Two independent implementations of running balance logic:
- Backend: Treats license as a single entity (license-wide)
- Frontend: Groups transactions by company and recalculates per-company

---

## OPTION A: License-Wide Running Balance

**Definition:**
A single running balance for the entire license, accumulating across all companies and transaction types.

**Formula:**
```
Opening Balance
+ PURCHASE (add to balance)
+ COMMISSION_SALE (add to balance, i.e., treat as internal debit)
- SALE (subtract from balance)
= Running Balance
```

**Example Transaction Flow:**

| # | Type | Company | Amount USD | Running Balance |
|---|------|---------|---------|---|
| 1 | OPENING | - | 100.00 | 100.00 |
| 2 | PURCHASE | Company A | +50.00 | 150.00 |
| 3 | SALE | Company A | -30.00 | 120.00 |
| 4 | COMMISSION_SALE | Company B | +20.00 | 140.00 |
| 5 | PURCHASE | Company B | +40.00 | 180.00 |
| 6 | SALE | Company B | -15.00 | 165.00 |

**Closing Balance:** 165.00

**Advantages:**
- ✅ Single authoritative running total
- ✅ Audit-friendly (one number for the entire license)
- ✅ Matches accounting convention for assets
- ✅ Current backend implementation (no refactoring needed)
- ✅ COMMISSION rows are visible and included in calculations

**Disadvantages:**
- ❌ Frontend (PDF/Excel) would need refactoring to use backend balance instead of recalculating
- ❌ COMMISSION rows treated as "debits" (counterintuitive naming)
- ❌ Mixes company-level and license-level concepts in single column
- ❌ Users asking "How much can Company A buy?" must mentally separate their rows

**Business Interpretation:**
"At any point in time, this is the total financial position of this license across all our company interactions."

**Recommendation for:** Auditors, financial teams, regulatory compliance (if license balance must match a master ledger)

---

## OPTION B: Per-Company Running Balance

**Definition:**
Running balance resets to zero for each company. Each company gets its own running total showing that company's utilization of the license.

**Formula per Company:**
```
0 (reset)
+ PURCHASE (add to company's balance)
- SALE (subtract from company's balance)
[COMMISSION: ignored/excluded]
= Company Running Balance
```

**Example Transaction Flow (by Company):**

**Company A:**
| Type | Amount USD | Running Balance |
|------|---------|---|
| PURCHASE | +50.00 | 50.00 |
| SALE | -30.00 | 20.00 |
| **Total** | | **20.00** |

**Company B:**
| Type | Amount USD | Running Balance |
|------|---------|---|
| COMMISSION_SALE | (ignored) | 0.00 |
| PURCHASE | +40.00 | 40.00 |
| SALE | -15.00 | 25.00 |
| **Total** | | **25.00** |

**Overall License Balance:** 20.00 + 25.00 = 45.00 (shown only in totals row, not running)

**Advantages:**
- ✅ Clear per-company view (customers see what they own)
- ✅ Easy for users to answer "How much did Company X buy?"
- ✅ COMMISSION rows cleanly excluded (not confusing)
- ✅ Matches current frontend implementation (no refactoring needed)
- ✅ Frontend exports (PDF, Excel) already work this way

**Disadvantages:**
- ❌ Backend would need refactoring to match (current API returns license-wide)
- ❌ No single "running balance" on each transaction row (only per-company)
- ❌ COMMISSION transactions completely hidden from balance calculations
- ❌ Harder to answer "what's the total license balance at transaction N?" (must sum all companies)
- ❌ Requires grouping/sorting by company (harder for spreadsheet analysis)

**Business Interpretation:**
"For each company interaction with this license, here's how much that company has used. The final numbers per company show that company's net position."

**Recommendation for:** Multi-customer scenarios, company-focused accounting, simplicity-first UX

---

## OPTION C: Hybrid (Dual View)

**Definition:**
Show both conventions simultaneously.

**Implementation:**
- Main table: Per-company grouping (Option B)
- Subtotal rows: Per-company balance (Option B)
- Grand total: License-wide running balance (Option A)
- Footer: License-wide analytics

**Example Display:**

```
COMPANY A
  PURCHASE   +50.00  [Company A Balance: 50.00]
  SALE       -30.00  [Company A Balance: 20.00]
SUBTOTAL              [Company A Total: 20.00]

COMPANY B
  PURCHASE   +40.00  [Company B Balance: 40.00]
  SALE       -15.00  [Company B Balance: 25.00]
SUBTOTAL              [Company B Total: 25.00]

OVERALL LICENSE BALANCE: 45.00
```

**Advantages:**
- ✅ Serves both use cases (company view + license view)
- ✅ No hidden data (COMMISSION visible even if excluded from balance)
- ✅ Both perspectives available for different analyses
- ✅ Most comprehensive (answers most questions)

**Disadvantages:**
- ❌ Most complex to implement and test
- ❌ Requires non-trivial refactoring of both backend and frontend
- ❌ Risk of introducing more confusion (two balance columns?)
- ❌ Largest implementation effort (3+ days)
- ❌ Takes 7+ days to fully test and verify parity

**Recommendation for:** Enterprise customers with complex reporting needs; highest cost but also highest completeness

---

## DECISION MATRIX

| Criterion | Option A | Option B | Option C |
|-----------|----------|----------|----------|
| **User Clarity** | Medium | High | Highest |
| **Implementation Effort** | Low (backend works) | Low (frontend works) | High (full refactor) |
| **Testing Effort** | Medium | Medium | High |
| **Audit Friendliness** | High | Medium | High |
| **Code Complexity** | Low | Low | High |
| **Serves Company View** | No | Yes | Yes |
| **Serves License View** | Yes | No | Yes |
| **Risk of Confusion** | Medium (COMMISSION weird) | Medium (hidden data) | Low (explicit) |
| **Days to Ship** | 1–2 | 1–2 | 5–7 |

---

## RECOMMENDATION

**For most business scenarios: Option B (Per-Company Running Balance)**

**Reasoning:**
1. **Matches User Workflow:** "I want to see how much Company X used this license"
2. **Frontend Already Works:** PDF and Excel use this convention, only need to update backend
3. **Simplest Implementation:** 1–2 days including tests
4. **Cleaner UX:** COMMISSION rows explicitly excluded, not confusingly included
5. **Spreadsheet Friendly:** Grouping by company is natural for Excel analysis

**If audit/compliance is critical:** Option A (License-Wide)
- Single authoritative line per transaction
- Matches accounting system conventions
- Backend already implements this
- Only frontend needs updates

**If serving both audiences is mandatory:** Option C (Hybrid)
- Most complete solution
- Highest cost (3+ days per phase)
- Significant test burden
- Only recommend if multiple use cases are equally important

---

## DECISION FORM

**To approve, answer these questions:**

1. **Running Balance Convention:**
   - [ ] Option A: License-wide
   - [ ] Option B: Per-company
   - [ ] Option C: Hybrid (dual view)

2. **COMMISSION Transaction Handling:**
   - [ ] Include in balance (Option A)
   - [ ] Exclude from balance (Option B)
   - [ ] Show separately but excluded (Option C)

3. **Timeline Acceptable?**
   - [ ] Option A/B: 1–2 days to ship
   - [ ] Option C: 5–7 days to ship

4. **Sign-Off:**
   - [ ] Approved by: ________________
   - [ ] Date: ________________
   - [ ] Notes: ________________

---

## NEXT STEPS AFTER APPROVAL

1. **Code Phase 3D Tests** (2–3 days)
   - Characterization tests with golden data
   - UI/PDF/Excel parity tests
   - Regression tests for balance calculation

2. **Implementation** (1–2 days, or 5–7 for Option C)
   - Backend: Update `build_dfia_ledger_detail()` and/or `build_incentive_ledger_detail()`
   - Frontend: Update `ledgerExport.js` to match convention
   - Verify parity across all three outputs

3. **Verification** (1 day)
   - Run characterization tests
   - Manual audit with golden data
   - Confirm UI/PDF/Excel agreement

4. **Module Freeze**
   - Lock ledger module
   - Move to next priority module

---

**Status:** Awaiting approval before Phase 3 implementation

**Questions?** Contact: [Business Product Manager]

---

**Timeline Sensitivity:** Each day of delay pushes Phase 3 completion back 1 day. Recommend approval within 48 hours of this document.
