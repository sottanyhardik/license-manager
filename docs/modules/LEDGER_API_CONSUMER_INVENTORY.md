# LEDGER API CONSUMER INVENTORY

**Phase 4C: API Migration to CanonicalLedgerService**

Generated: 2026-08-10

---

## Summary

The ledger API endpoint (`/licenses/{id}/ledger_detail/`) is consumed by:
- **2 Frontend consumers** (React pages)
- **1 Test consumer** (API integration test)
- **2 Internal Python functions** (PDF exporters)

**CRITICAL:** Frontend consumers hit the HTTP endpoint only; they do NOT directly call Python functions. PDF exporters call Python functions directly, bypassing HTTP.

---

## Consumer Table

| Consumer | File | Function/Component | Endpoint Used | Fields Consumed | Risk | Scope 4C |
|----------|------|-------------------|----------------|------------------|------|----------|
| LicenseLedger React | `frontend/src/pages/LicenseLedger.tsx` | `LicenseLedger` component | `GET /licenses/{id}/ledger_detail/?company=...` | Full response object | HTTP contract breakage | YES |
| LicenseLedgerDetail React | `frontend/src/pages/LicenseLedgerDetail.tsx` | `LicenseLedgerDetail` component | `GET /licenses/{id}/ledger_detail/?company=...` | Full response object | HTTP contract breakage | YES |
| LicensesTable React | `frontend/src/pages/masters/tables/LicensesTable.tsx` | `LicensesTable` component | `GET /licenses/{id}/ledger_detail/` | Full response object (for modal/detail view) | HTTP contract breakage | YES |
| API Integration Test (Trade) | `backend/tests/test_api_trade.py` | `test_license_ledger_detail()` | `GET /licenses/{id}/ledger_detail/` | Validates response structure | Test breakage | YES |
| PDF Exporter | `backend/apps/license/services/exporters/ledger_pdf.py` | `build_dfia_ledger_detail()` | Python function (NOT HTTP) | Returns dict with transaction details | Internal logic, not HTTP | NO |
| PDF Exporter | `backend/apps/license/services/exporters/ledger_pdf.py` | `build_incentive_ledger_detail()` | Python function (NOT HTTP) | Returns dict with transaction details | Internal logic, not HTTP | NO |

---

## Detailed Consumer Analysis

### 1. Frontend: LicenseLedger Component

**File:** `frontend/src/pages/LicenseLedger.tsx`

**HTTP Call:**
```typescript
api.get(`license-ledger/${lic.license_id}/ledger_detail/?${params}`)
```

**Fields Consumed:**
- Full response object (passed to child components)
- Used for display in a table/detail view

**Risk:**
- **HIGH if response structure changes** — component expects specific field names
- Response must maintain backward compatibility

**In Scope 4C:** YES (API response contract must be maintained)

---

### 2. Frontend: LicenseLedgerDetail Component

**File:** `frontend/src/pages/LicenseLedgerDetail.tsx`

**HTTP Call:**
```typescript
api.get(`license-ledger/${safeId}/ledger_detail/?${queryString}`)
```

**Fields Consumed:**
- Full response object
- Renders transactions, balances, company details

**Risk:**
- **HIGH if response structure changes** — depends on exact field names and structure

**In Scope 4C:** YES (API response contract must be maintained)

---

### 3. Frontend: LicensesTable Component

**File:** `frontend/src/pages/masters/tables/LicensesTable.tsx`

**HTTP Call:**
```typescript
api.get(`license-ledger/${item.id}/ledger_detail/`)
```

**Fields Consumed:**
- Full response object (likely for modal or tooltip display)

**Risk:**
- **MEDIUM** — used for supplementary details; less critical than primary pages

**In Scope 4C:** YES (API response contract must be maintained)

---

### 4. Backend: API Test

**File:** `backend/tests/test_api_trade.py`

**Test Function:** `test_license_ledger_detail()`

**HTTP Call:**
```python
response = self.client.get(f'/api/licenses/{license.id}/ledger_detail/')
```

**Fields Consumed:**
- Response structure validation
- Validates status code and JSON structure

**Risk:**
- **MEDIUM** — test may fail if response structure changes
- Test must be updated if API response schema changes

**In Scope 4C:** YES (tests must pass)

---

### 5. Python: PDF Exporter (DFIA)

**File:** `backend/apps/license/services/exporters/ledger_pdf.py`

**Function:** `build_dfia_ledger_detail(license, company_id=None)`

**Returns:** Dict (NOT consumed via HTTP)

```python
return {
    'license_id': license.id,
    'license_type': 'DFIA',
    'license_number': license.license_number,
    'license_date': license.license_date,
    'expiry_date': license.license_expiry_date,
    'exporter': license.exporter.name if license.exporter else '',
    'port': license.port.name if license.port else '',
    'total_value': total_purchase_cif,
    'available_balance': real_balance,
    'db_balance': real_balance,
    'transactions': transactions,
}
```

**Risk:**
- **LOW for Phase 4C** — this is NOT called by the API view; it's a separate code path
- PDF exporters are OUT OF SCOPE for Phase 4C (they should continue using their own logic)

**In Scope 4C:** NO (Phase 4C API only; PDF is Phase 4D)

---

### 6. Python: PDF Exporter (Incentive)

**File:** `backend/apps/license/services/exporters/ledger_pdf.py`

**Function:** `build_incentive_ledger_detail(license, company_id=None)`

**Risk:**
- **LOW for Phase 4C** — NOT called by the API view
- OUT OF SCOPE for Phase 4C

**In Scope 4C:** NO (Phase 4C API only; PDF is Phase 4D)

---

## Current API Endpoint

**HTTP Method:** GET

**Path:** `/licenses/{id}/ledger_detail/`

**Query Parameters:**
- `company` (optional): Filter by company ID
- `license_type` (optional): DFIA, INCENTIVE, etc.

**Current Implementation:**
- Called via `LicenseLedgerViewSet.ledger_detail()` action
- Delegates to `build_dfia_ledger_detail()` or `build_incentive_ledger_detail()`
- Returns transaction list with balances

---

## Backward Compatibility Concerns

### MUST MAINTAIN:
1. **HTTP status codes** (200 for success, 404 for not found, 400 for bad request)
2. **Response structure** (JSON object with transaction list)
3. **Field names** (frontend code hardcodes field access)
4. **Pagination/filtering** (if implemented)
5. **Permission checks** (LicenseLedgerViewPermission must remain enforced)

### ALLOWED TO CHANGE (with deprecation notice):
1. Add new fields (must be optional/nullable for old clients)
2. Mark old fields as deprecated (keep them for backward compat)
3. Rename fields (only if old names aliased to new values)

---

## Phase 4C Action Items

- [ ] Document current API response contract (LEDGER_API_CURRENT_CONTRACT.md)
- [ ] Define canonical API response (LEDGER_API_NEW_CONTRACT.md)
- [ ] Create CanonicalLedgerSerializer (representing only; no business logic)
- [ ] Migrate LicenseLedgerViewSet.ledger_detail() to use CanonicalLedgerService
- [ ] Verify API response matches CanonicalLedgerService output
- [ ] Run consumer tests (frontend + backend)
- [ ] Verify no financial logic in API layer (search for "balance", "running_balance", etc.)

---

## GATE 4C Consumer Inventory: PASS

All consumers identified. No breaking changes detected as long as response structure remains compatible.

**Next Step:** Document current API contract
