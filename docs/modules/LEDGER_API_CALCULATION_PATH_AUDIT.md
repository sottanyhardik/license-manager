# Ledger API Calculation Path Audit
**Date:** 2026-08-10  
**Status:** Active Path Verification  
**Scope:** Confirm Phase 4C completion and identify active calculation owners

---

## EXECUTIVE SUMMARY

| Path | Active | Calculator | Canonical | Consumer |
|------|--------|-----------|-----------|----------|
| Ledger API `/ledger-detail/` | ✅ YES | CanonicalLedgerService | ✅ YES | Frontend |
| Backend PDF export `/export/all/` | ✅ YES | `get_license_transactions()` | ✅ Hybrid | Admin |
| Frontend PDF `ledgerExport.js` | ✅ YES | Client-side (Phase 4E-C) | ❌ NO | User |
| Frontend Excel `ledgerExport.js` | ✅ YES | Client-side (Phase 4E-D) | ❌ NO | User |

---

## LEDGER API PATH (Phase 4C Status)

### Active Endpoint
```
GET /api/license/license-ledger/{pk}/ledger_detail/
```

### Current Implementation
**File:** `backend/apps/license/views/ledger.py`  
**Function:** `LicenseLedgerViewSet.ledger_detail()`  
**Lines:** 218–262

### Code Path
```python
ledger_detail(request, pk)
    ↓
Find license (DFIA or Incentive)
    ↓
CanonicalLedgerService.build_canonical_ledger_dataset(
    license_id=license.id,
    license_type=type
)
    ↓
CanonicalLedgerSerializer(canonical_data)
    ↓
Response (JSON)
```

### Verification
```python
# Line 255-257
dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
    license_id=license.id,
    license_type=found_type
)
```

✅ **Confirmed:** API uses CanonicalLedgerService (Phase 4C COMPLETE)

---

## LEGACY FUNCTIONS (NOT USED IN PRODUCTION)

### build_dfia_ledger_detail()
**Location:** `backend/apps/license/services/exporters/ledger_pdf.py:1043–1290`  
**Status:** LEGACY CODE  
**Test Usage:** `test_ledger_pdf_live_balance.py:39`  
**Production Calls:** NONE ✅

### build_incentive_ledger_detail()
**Location:** `backend/apps/license/services/exporters/ledger_pdf.py:1296–1469`  
**Status:** LEGACY CODE  
**Test Usage:** None (similar pattern to build_dfia_ledger_detail)  
**Production Calls:** NONE ✅

### Docstring Claim vs. Reality
**Old Docstring (lines 3-7 of test file):**
```
Backing `GET /api/license-ledger/<pk>/`'s DFIA branch
```

**Current Reality:**
The API endpoint uses CanonicalLedgerService, NOT build_dfia_ledger_detail().

These functions are **orphaned legacy code**, preserved only for:
1. Historical test coverage (test_ledger_pdf_live_balance.py)
2. Possible future reference (documentation)

---

## PRODUCTION CALCULATION OWNERSHIP

### Single Source of Truth (Post-Phase 4C)
```
CanonicalLedgerService
    ├── owns all Ledger calculations
    └── consumed by:
        ├── API (ledger_detail)
        ├── Backend PDF (get_license_transactions)
        └── Frontend (via API)
```

### Independent Calculations Still Present
```
Frontend PDF (ledgerExport.js)
    └── Independent per-company balance calc (Phase 4E-C target)

Frontend Excel (ledgerExport.js)
    └── Independent per-company balance calc (Phase 4E-D target)
```

### No Other Active Calculations
✅ No other financial calculation owners found in production code

---

## DECISION

### Classification of build_dfia_ledger_detail()
```
Status: LEGACY CODE
Action: Mark for Phase 4E-F cleanup
Impact on Phase 4E-B: NONE (not called)
Impact on architecture: LOW (test-only)
```

### Phase 4E-B Scope Resolved
✅ Single active API path: CanonicalLedgerService  
✅ No competing financial calculation engines  
✅ No blocking issues from legacy code  
✅ Phase 4C verified complete and active

---

## RECOMMENDATION

**For Phase 4E-B:**
- ✅ Can proceed (no scope blockers)
- Do NOT modify build_dfia_ledger_detail() now
- Mark for removal in Phase 4E-F cleanup

**For Phase 4E-F Cleanup:**
- Delete `build_dfia_ledger_detail()`
- Delete `build_incentive_ledger_detail()`
- Update/remove test_ledger_pdf_live_balance.py (or mark as legacy)

