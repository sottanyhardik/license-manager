# License Ledger — Current Behavior vs Approved Semantics

**Purpose:**  
Document the gaps between current implementation and approved Option C semantics.

**Date:** 2026-08-10  
**Status:** Used to guide Phase 3 implementation

---

## SUMMARY OF DIFFERENCES

The current implementation shows **divergent running balances** across three outputs:

- **Screen (API):** License-wide running balance
- **PDF:** Per-company running balance (recalculated frontend)
- **Excel:** Per-company running balance (recalculated frontend)

Approved Option C unifies this under a single canonical backend calculation with clear semantic distinction between license-wide and company-utilization metrics.

---

## DETAILED COMPARISON TABLE

| Aspect | Current Screen | Current PDF | Current Excel | Approved (Option C) | Change Required | Owner |
|--------|---|---|---|---|---|---|
| **Running Balance Concept** | License-wide (authoritative) | Per-company (calculated) | Per-company (calculated) | Dual: License-wide (auth) + Company util (secondary) | YES | Backend + Frontend |
| **Balance Formula** | Backend-provided | Frontend recalc (date order) | Frontend recalc (date order) | Single backend source, API-provided to frontend | YES | Backend (ledger builder) |
| **COMMISSION Handling** | Included in balance | Excluded from balance | Excluded from balance | Excluded, but visible, marked "excluded" | YES | Backend (balance calc) |
| **Company Scope** | N/A (no per-company view) | Per-company reset (own balance) | Per-company reset (own balance) | Per-company reset (independent) + License-wide | YES | Backend + Frontend |
| **Authoritative Source** | Backend ✓ | Frontend ✗ (recalc) | Frontend ✗ (recalc) | Backend only ✓ | YES | Backend architecture |
| **Data Consistency** | Single source | Recalculated (diverges) | Recalculated (diverges) | All from same API response | YES | Backend + Frontend |
| **Decimal Precision** | 2 places | 2 places | 2 places | 2 places | NO | Verify in tests |
| **Ordering** | Date+ID (backend) | Date+ID (frontend) | Date+ID (frontend) | Date+ID (backend canonical) | VERIFY | Backend |
| **Opening Balance** | Counted once | Counted once | Counted once | Counted once | NO | Verify in tests |
| **Multiple Companies** | Single balance | Per-company subtotals + overall | Per-company columns + total | License balance + Company breakdown | YES | Frontend display |
| **Visual Clarity** | Ambiguous: COMMISSION in balance, but where? | Clear per-company | Clear per-company | Crystal clear: license vs company |YES | Frontend |
| **P0 Defect Status** | Contrib to P0 (screen shows license, others company) | Contrib to P0 | Contrib to P0 | Fixes P0 completely | YES | Implementation |

---

## DETAILED CHANGE ANALYSIS

### 1. Running Balance Concept

**Current:**
- Screen: Shows license-wide balance on each transaction row
- PDF: Shows per-company balance (resets per company)
- Excel: Shows per-company balance (resets per company)
- **Confusion:** User sees same license number, different balances in different outputs

**Approved:**
- All outputs derive from single backend calculation
- **License Running Balance:** Authoritative, calculated once, shared to all outputs
- **Company Utilization:** Secondary view showing each company's own usage
- **Clarity:** Two distinct metrics, both visible, both correct

**Change Required:**
- Backend: Ensure balance builder calculates license-wide balance once
- Backend: Calculate company utilizations independently (sum of that company's txns)
- API: Return both `license_running_balance` and `company_utilizations` in response
- Frontend: Use API-provided values, don't recalculate
- Frontend: Display both metrics, clearly labeled

**Owner:** Backend (ledger builder) → API → Frontend (display)

---

### 2. Balance Formula Source

**Current:**
- Screen: Backend-provided (ledger builder output)
- PDF: Frontend recalculates (based on transaction list)
- Excel: Frontend recalculates (based on transaction list)
- **Risk:** Frontend recalculation diverges from backend

**Approved:**
- Single backend source: Ledger builder calculates running balance
- API: Returns pre-calculated balances
- Frontend: Receives and displays, no recalculation
- **Single source of truth**

**Change Required:**
- Backend: Ledger builder must expose `running_balance` for each transaction and `company_utilizations` dict
- API: Return these values in response
- Frontend (PDF exporter): Don't recalculate, use backend values
- Frontend (Excel exporter): Don't recalculate, use backend values
- Tests: Assert that all three outputs produce identical balances

**Owner:** Backend (ledger service) → API → Frontend (exporters)

---

### 3. COMMISSION Transaction Handling

**Current:**
- Screen: Included in running balance ✓ (backend includes it)
- PDF: Excluded from running balance ✓ (frontend explicitly excludes)
- Excel: Excluded from running balance ✓ (frontend explicitly excludes)
- **Divergence:** COMMISSION counted in screen, not in PDF/Excel

**Approved:**
- Excluded from running balance everywhere
- Visible in transaction list (for auditability)
- Marked with "Excluded from License Balance" indicator
- **Consistency:** Same treatment in screen, PDF, Excel

**Change Required:**
- Backend: Modify balance calculator to exclude COMMISSION from `running_balance`
- Backend: Ensure COMMISSION transaction is still present in transaction list
- API: Return `is_commission: true` flag on COMMISSION rows
- Frontend: Display COMMISSION rows with exclusion marker
- PDF/Excel: Apply same exclusion (already do, verify consistency)
- Tests: Assert COMMISSION is visible but not counted in any output

**Owner:** Backend (balance calculator) → Frontend (display)

---

### 4. Company Scope & Isolation

**Current:**
- Screen: No per-company breakdown available
- PDF: Per-company pages, balance resets per company ✓
- Excel: Per-company columns, balance resets per company ✓
- **Gap:** Screen doesn't offer per-company view

**Approved:**
- Screen: Show both license-wide + per-company breakdown (dashboard view)
- PDF: Per-company pages as now, but use backend-calculated balances
- Excel: Per-company columns as now, but use backend-calculated balances
- **All:** Company balances are independent (no cross-contamination)

**Change Required:**
- Backend: Calculate company utilizations: `SUM(company's transactions only)`
- API: Return `company_utilizations: {company_id: balance, ...}`
- Frontend (Screen): New component to display both license + company breakdowns
- Frontend (PDF): Update per-company pages to use backend company balances instead of recalc
- Frontend (Excel): Update columns to use backend company balances instead of recalc
- Tests: Assert Company A balance unchanged when Company B transaction added

**Owner:** Backend (balance calc) → API → Frontend (screen, PDF, Excel)

---

### 5. Authoritative Source

**Current:**
- Backend provides balance for screen
- Frontend recalculates for PDF/Excel
- **Risk:** Divergence possible, has already happened

**Approved:**
- Backend is authoritative for all calculations
- Frontend receives pre-calculated values
- Frontend never recalculates balance
- **Risk eliminated**

**Change Required:**
- Architecture: All balance logic in backend, zero frontend logic
- Backend: Export running_balance and company_utilizations in API
- Frontend: Remove all balance recalculation code
- Tests: Verify frontend never recalculates, only receives

**Owner:** Backend → API → Frontend (audit)

---

### 6. Data Consistency

**Current:**
- Screen: Receives from backend
- PDF: Recalculates (may diverge)
- Excel: Recalculates (may diverge)
- **Inconsistency:** Three independent implementations

**Approved:**
- Single API response feeds all three outputs
- Same input data → same output guarantees
- **Consistency by design**

**Change Required:**
- Backend: Ensure ledger endpoint returns complete, consistent data
- API: Schema includes running_balance, company_utilizations, all metadata
- Frontend: All three outputs consume same API response
- Tests: Golden dataset verification (all three use same input, verify identical output)

**Owner:** Backend (API schema) → Frontend (all exporters)

---

### 7. Multiple Companies Display

**Current:**
- Screen: Single balance (license-wide), no company breakdown
- PDF: Company pages with subtotals, then overall
- Excel: Company columns, then total row
- **Fragmentation:** Different display models per output

**Approved:**
- Screen: Dual dashboard - license balance header + company breakdown table
- PDF: License balance at top, then per-company sections
- Excel: License balance in summary row, per-company columns with util row
- **Unified model:** License + Company, both visible everywhere

**Change Required:**
- Frontend (Screen): Add company breakdown component to ledger detail view
- Frontend (PDF): Ensure license balance header, then per-company sections
- Frontend (Excel): Ensure summary row with license balance + company util rows
- Tests: Verify all three display both license and company metrics

**Owner:** Frontend (components for screen, PDF, Excel templates)

---

### 8. Visual Clarity

**Current:**
- Screen: One balance, unclear scope (license or company?)
- PDF: Per-company, but no license-level summary
- Excel: Per-company, but company-balance semantics unclear
- **User confusion:** What does this balance mean?

**Approved:**
- All outputs clearly distinguish:
  - **License Running Balance:** "Total cumulative position across all companies"
  - **Company Utilization:** "Company X's own usage/attribution" (reset per company)
- **Labels:** Explicit, unambiguous

**Change Required:**
- Frontend: Add labels to distinguish metrics
- Screen: Header "License Balance: X" vs "Company X Utilization: Y"
- PDF: Sections clearly labeled "License Balance" vs "Company A Transactions"
- Excel: Columns labeled "License Running Balance" vs "Company Utilization"
- Tests: Verify labels present and correct

**Owner:** Frontend (UX/design) + Backend (API metadata)

---

## CHANGE OWNER MATRIX

| Component | Current Owner | Change Required | Phase 3 Owner |
|-----------|---|---|---|
| Balance Calculation Logic | Backend (balance_calculator.py) | YES - exclude COMMISSION | Backend |
| Ledger Builder (DFIA/Incentive) | Backend (ledger_pdf.py) | YES - expose balances + company util | Backend |
| API Endpoint | Backend (views) | YES - return both metrics | Backend |
| Screen Display | Frontend (React) | YES - show company breakdown | Frontend |
| PDF Export Logic | Backend + Frontend | YES - use backend balances, not recalc | Backend + Frontend |
| Excel Export Logic | Backend + Frontend | YES - use backend balances, not recalc | Backend + Frontend |
| Tests | QA | YES - comprehensive characterization | QA |

---

## IMPLEMENTATION IMPACT

### Backend

**Files to Change:**
- `apps/license/services/balance_calculator.py` - Exclude COMMISSION
- `apps/license/services/exporters/ledger_pdf.py` - Calculate company utilizations
- `apps/license/views/ledger.py` - API schema and response
- `apps/license/serializers.py` - Ensure balance fields exposed

**Effort:** 2–3 days
**Risk:** Medium (balance logic is critical)

### Frontend

**Files to Change:**
- `frontend/src/components/LedgerDetail.tsx` - Add company breakdown
- `frontend/src/services/ledgerExport.js` - Remove balance recalculation
- `frontend/src/components/PDFExport/` - Use backend balances
- `frontend/src/components/ExcelExport/` - Use backend balances

**Effort:** 2–3 days
**Risk:** Low (display layer)

### Tests

**Files to Create:**
- `backend/apps/license/tests/test_ledger_characterization_option_c.py` - Comprehensive suite
- `backend/apps/license/tests/test_cross_output_parity.py` - Parity verification
- `backend/apps/license/tests/test_p0_defect_regression.py` - P0 defect coverage

**Effort:** 2–3 days
**Risk:** Low (tests only)

---

## TOTAL EFFORT ESTIMATE

- **Phase 2 (Current):** Characterization tests & golden dataset (2–3 days) ✓ In progress
- **Phase 3:** Implementation design (1 day) + Coding (2–3 days) + Verification (1 day) = 4–5 days
- **Phase 4:** Integration testing + UAT (2–3 days)
- **Total:** ~8–10 days from approval to shipping

---

## P0 DEFECT RESOLUTION

**Current P0 Defect:**
```
Screen shows balance: 1300.00
PDF shows balance:    1050.00
Excel shows balance:  1050.00

"Why are three different numbers shown for the same license?"
```

**Root Cause:**
- Screen: Backend-provided (license-wide)
- PDF/Excel: Frontend-recalculated (per-company)

**Approved Resolution:**
- All three use backend-provided balanced
- All three show license balance AND company breakdowns
- **Clear semantics:** Users understand they're different metrics

**Verification Test:**
```python
def test_p0_screen_pdf_excel_balance_agreement():
    """P0 defect: Screen/PDF/Excel show different balances.
    
    After Option C implementation, all three must show same
    license running balance and same company utilizations.
    """
    # Create test license with golden dataset
    # Get screen balance (from API)
    # Get PDF balance (from exporter)
    # Get Excel balance (from exporter)
    
    # All must agree
    assert screen_balance == pdf_balance == excel_balance
    
    # All must exclude COMMISSION
    assert screen_excludes_commission == True
    assert pdf_excludes_commission == True
    assert excel_excludes_commission == True
```

---

## SIGN-OFF

| Role | Current Behavior Confirmed | Approved Behavior Confirmed | Ready for Implementation |
|------|---|---|---|
| QA | ✓ Defect reproduced | ✓ Semantics documented | ✓ Tests ready |
| Backend Engineer | ✓ Code location identified | ✓ Changes scoped | Pending |
| Frontend Engineer | ✓ Code location identified | ✓ Changes scoped | Pending |
| Product Manager | ✓ Issue understood | ✓ Solution approved | ✓ Ready |

---

**Document Version:** 1.0  
**Created:** 2026-08-10  
**Status:** Reference for Phase 3 implementation planning  
**Next Step:** Phase 3 — Implementation Design & Coding
