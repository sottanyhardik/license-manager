# License Ledger — API Contract Specification

**Purpose:** Define the HTTP API contract for the ledger detail endpoint, including request/response format, breaking changes, and versioning strategy.  
**Status:** Design specification (Gate 3)  
**Date:** 2026-08-10

---

## ENDPOINT SPECIFICATION

### Current Endpoint

```
GET /api/license/<license_id>/ledger_detail/
```

**Method:** GET (read-only)  
**Authentication:** JWT Bearer token required  
**Permissions:** User must have `license.view_ledger` permission

---

## CURRENT API RESPONSE (Before Gate 3)

```http
GET /api/license/123/ledger_detail/

HTTP/1.1 200 OK
Content-Type: application/json

{
  "license_id": 123,
  "license_number": "0311045100",
  "license_type": "DFIA",
  "available_balance": 1300.00,
  "transactions": [
    {
      "date": "2026-01-15",
      "id": "txn_1",
      "type": "OPENING",
      "company_id": null,
      "company_name": null,
      "amount": 1000.00,
      "balance": 1000.00,
      "is_commission": false,
      "particular": "Opening Balance",
      "invoice_number": "0311045100",
      "cif_usd": 1000.00,
      "debit_cif": 1000.00,
      "credit_cif": 0.00
    },
    {
      "date": "2026-01-20",
      "id": "trade_456",
      "type": "PURCHASE",
      "company_id": "uuid_A",
      "company_name": "Company A",
      "amount": 500.00,
      "balance": 1500.00,
      "is_commission": false,
      "particular": "Purchase DFIA - Supplier X",
      "invoice_number": "2026-001",
      "cif_usd": 500.00,
      "debit_cif": 500.00,
      "credit_cif": 0.00
    },
    {
      "date": "2026-02-01",
      "id": "trade_789",
      "type": "COMMISSION",
      "company_id": "uuid_B",
      "company_name": "Company B",
      "amount": 100.00,
      "balance": 1600.00,
      "is_commission": false,
      "particular": "Commission Paid",
      "invoice_number": "2026-COM-001",
      "cif_usd": 100.00,
      "debit_cif": 100.00,
      "credit_cif": 0.00
    }
  ]
}
```

**Problems:**
- `balance: 1600.00` includes COMMISSION (should be 1500.00)
- No `license_running_balance` field (ambiguous which is authoritative)
- No `company_utilizations` field (exporters can't display breakdown from API)
- `is_commission` always false (should be true for COMMISSION rows)

---

## TARGET API RESPONSE (After Gate 3)

```http
GET /api/license/123/ledger_detail/

HTTP/1.1 200 OK
Content-Type: application/json
Deprecation: true
Sunset: Sun, 01 Sep 2026 00:00:00 GMT

{
  "license_id": 123,
  "license_number": "0311045100",
  "license_type": "DFIA",
  "license_date": "2026-01-01",
  "expiry_date": "2026-12-31",
  "exporter": "Export Corp Ltd",
  
  "available_balance": "1300.00",
  "license_running_balance": "1300.00",
  "opening_balance": "1000.00",
  "closing_balance": "1300.00",
  
  "company_utilizations": {
    "uuid_A": "300.00",
    "uuid_B": "250.00"
  },
  
  "transactions": [
    {
      "id": "txn_1",
      "trade_id": null,
      "date": "2026-01-15",
      "type": "OPENING",
      "is_commission": false,
      "company_id": null,
      "company_name": null,
      "amount_cif": "1000.00",
      "debit_cif": "1000.00",
      "credit_cif": "0.00",
      "running_balance": "1000.00",
      "particular": "Opening Balance",
      "invoice_number": "0311045100",
      "items": null,
      "sion_norms": null,
      "qty": null,
      "rate": "0.00",
      "profit_loss": null,
      "display_status": null
    },
    {
      "id": "trade_456",
      "trade_id": 456,
      "date": "2026-01-20",
      "type": "PURCHASE",
      "is_commission": false,
      "company_id": "uuid_A",
      "company_name": "Company A",
      "amount_cif": "500.00",
      "debit_cif": "500.00",
      "credit_cif": "0.00",
      "running_balance": "1500.00",
      "particular": "Purchase DFIA - Supplier Inc",
      "invoice_number": "2026-001",
      "items": "Rice, Wheat",
      "sion_norms": "E1, E5",
      "qty": "1500.50",
      "rate": "82.50",
      "profit_loss": null,
      "display_status": null
    },
    {
      "id": "trade_789",
      "trade_id": 789,
      "date": "2026-02-01",
      "type": "COMMISSION",
      "is_commission": true,
      "company_id": "uuid_B",
      "company_name": "Company B",
      "amount_cif": "100.00",
      "debit_cif": "100.00",
      "credit_cif": "0.00",
      "running_balance": "1500.00",
      "particular": "Commission Paid to Customs",
      "invoice_number": "2026-COM-001",
      "items": null,
      "sion_norms": null,
      "qty": null,
      "rate": "0.00",
      "profit_loss": null,
      "display_status": "Excluded from License Balance"
    },
    {
      "id": "trade_101",
      "trade_id": 101,
      "date": "2026-02-10",
      "type": "SALE",
      "is_commission": false,
      "company_id": "uuid_A",
      "company_name": "Company A",
      "amount_cif": "200.00",
      "debit_cif": "0.00",
      "credit_cif": "200.00",
      "running_balance": "1300.00",
      "particular": "Sale to Buyer Corp",
      "invoice_number": "2026-SALE-001",
      "items": "Rice",
      "sion_norms": "E1",
      "qty": "500.00",
      "rate": "82.50",
      "profit_loss": "50.00",
      "display_status": null
    }
  ],
  
  "metadata": {
    "total_purchase_cif": "500.00",
    "total_sales_cif": "200.00",
    "total_commission_amount": "100.00",
    "transaction_count": 4,
    "commission_count": 1,
    "purchase_count": 1,
    "sale_count": 1,
    "opening_date": "2026-01-01",
    "first_purchase_date": "2026-01-20",
    "first_sale_date": "2026-02-10"
  }
}
```

---

## BREAKING CHANGES ANALYSIS

| Field | Current | Target | Breaking | Mitigation |
|-------|---------|--------|----------|---|
| `balance` (txn field) | ✓ Present (includes COMMISSION) | ✗ REMOVED | YES | Keep for 30 days (deprecation notice), then remove |
| `license_running_balance` | ✗ Missing | ✓ Added | NO | New field, clients ignore if not needed |
| `company_utilizations` | ✗ Missing | ✓ Added | NO | New field, optional |
| `running_balance` (txn field) | ✗ Missing | ✓ Added (replaces `balance`) | PARTIAL | Clients using `balance` will break; must migrate to `running_balance` |
| `is_commission` (txn field) | ✓ Always false | ✓ Can be true | MAYBE | Clients should check; backward compatible if ignored |
| `display_status` (txn field) | ✗ Missing | ✓ Added | NO | Optional field |
| `opening_balance` | ✗ Missing | ✓ Added | NO | New field |
| `closing_balance` | ✗ Missing | ✓ Added | NO | New field |
| `metadata` | ✗ Missing | ✓ Added | NO | New field |

### Summary

- **Breaking:** Removal of `balance` field and changes to transaction semantics (COMMISSION exclusion)
- **Non-Breaking:** All additions
- **Partial Breaking:** Clients depending on `balance` field must migrate to `running_balance`

---

## MIGRATION STRATEGY FOR CLIENTS

### Phase 1: Additive (Days 1–30)

**API Response:** Contains BOTH old and new fields

```json
{
  "transactions": [
    {
      "balance": 1500.00,           // OLD (deprecated, still included)
      "running_balance": "1500.00", // NEW (authoritative)
      "is_commission": false        // NEW (may be true)
    }
  ],
  "license_running_balance": "1300.00",  // NEW
  "company_utilizations": {...}         // NEW
}
```

**Client Action:** Migrate to `running_balance` and `license_running_balance`.

### Phase 2: Deprecation Notice (Days 25–31)

**API Response Headers:**
```
Deprecation: true
Sunset: Sun, 01 Sep 2026 00:00:00 GMT
Link: <https://api.example.com/docs/migration/ledger>; rel="deprecation"
```

**API Documentation:** Updated with migration guide.

### Phase 3: Removal (After Day 31)

**API Response:** `balance` field removed.

**Major Version Bump:** API v2.0 (if using semantic versioning).

---

## HTTP STATUS CODES

| Status | Meaning | When |
|--------|---------|------|
| 200 OK | Success | Valid request, license found |
| 400 Bad Request | Invalid request | Malformed query params |
| 401 Unauthorized | No auth | Missing JWT token |
| 403 Forbidden | Not authorized | User lacks `license.view_ledger` permission |
| 404 Not Found | License not found | `license_id` doesn't exist |
| 500 Internal Server Error | Server error | Database error, calculation error |

---

## ERROR RESPONSE EXAMPLES

### License Not Found

```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{
  "detail": "License with id 999 not found"
}
```

### Authorization Denied

```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "detail": "You do not have permission to view this license ledger"
}
```

### Server Error

```http
HTTP/1.1 500 Internal Server Error
Content-Type: application/json

{
  "detail": "Error calculating ledger: database connection failed"
}
```

---

## QUERY PARAMETERS

### Existing Parameters

| Parameter | Type | Optional | Default | Purpose |
|-----------|------|----------|---------|---------|
| `company_id` | integer | YES | null | Filter ledger by company (PURCHASE buyer or SALE seller) |
| `format` | string | YES | "json" | Output format (json, csv, xlsx — not ledger detail specific) |

### New Parameters (Future Enhancement)

Reserved for future use:
- `start_date`: Filter transactions after date
- `end_date`: Filter transactions before date
- `exclude_commission`: Boolean to exclude COMMISSION rows
- `include_metadata`: Boolean to include metadata section

---

## CONTENT NEGOTIATION

### Response Format

**Current:** JSON only

**Accept Header:**
```
Accept: application/json
```

**Response:**
```
Content-Type: application/json
```

**Charset:** UTF-8 (always)

---

## CACHING HEADERS

### Current Implementation

```http
Cache-Control: private, max-age=3600
```

**Rationale:**
- `private`: Each user has their own balance data
- `max-age=3600`: Cache for 1 hour (balance changes infrequently)

### Recommended (After Gate 3)

```http
Cache-Control: private, max-age=600, must-revalidate
ETag: "abc123def456"
Last-Modified: 2026-08-10T12:34:56Z
Vary: Accept, Accept-Encoding
```

**Rationale:**
- Shorter TTL (10 minutes) for more fresh data
- ETags for client-side caching validation
- Vary header for compression variants

---

## RATE LIMITING

### Current Rate Limits

| User Role | Limit | Window |
|-----------|-------|--------|
| Anonymous | 10 req/hour | Per IP |
| Authenticated | 100 req/hour | Per user |
| Staff | 500 req/hour | Per user |

### Recommended (After Gate 3)

No changes; use existing rate limits.

---

## VERSIONING STRATEGY

### Option A: URL Versioning (Recommended)

**Current:** `/api/license/<id>/ledger_detail/` (implicit v1)

**Future:** 
- `/api/v1/license/<id>/ledger_detail/` (current)
- `/api/v2/license/<id>/ledger_detail/` (after breaking change)

**Pros:** Clear in URL, easy to maintain multiple versions

**Cons:** More endpoints to maintain

### Option B: Header Versioning

**Request:**
```
GET /api/license/123/ledger_detail/
Accept: application/vnd.example.ledger+json; version=2
```

**Response:**
```
Content-Type: application/vnd.example.ledger+json; version=2
```

**Pros:** Single endpoint, clean API

**Cons:** Less discoverable

### Recommendation

Use **Option A (URL Versioning)** for clarity and discoverability.

---

## DOCUMENTATION

### Current API Docs

Location: `/api/docs/` (OpenAPI/Swagger)

### Required Updates (After Gate 3)

1. Add `license_running_balance` field to schema
2. Add `company_utilizations` field to schema
3. Document COMMISSION exclusion behavior
4. Add deprecation notice for `balance` field
5. Add Sunset header example
6. Add migration guide

### Example OpenAPI Schema (Updated)

```yaml
/license/{license_id}/ledger_detail/:
  get:
    summary: Get License Ledger Detail (Canonical)
    description: |
      Returns the canonical ledger dataset for a license.
      
      **Breaking Changes (2026-08-10):**
      - Field `balance` deprecated (use `running_balance` instead)
      - COMMISSION transactions now excluded from `running_balance`
      - New fields: `license_running_balance`, `company_utilizations`
      
      **Migration:** See https://...docs/ledger_migration.md
    parameters:
      - name: license_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      '200':
        description: Success
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CanonicalLedgerDataset'
      '404':
        description: License not found
      '403':
        description: Permission denied
```

---

## BACKWARD COMPATIBILITY

### Guarantees

- ✅ Old `available_balance` field remains unchanged
- ✅ New fields are additive (don't break old clients)
- ✅ Transaction array structure preserved (new fields added)
- ✅ Existing query parameters (`company_id`) still work

### Breaking Points

- ❌ `balance` field in transactions will be removed (after deprecation)
- ❌ `is_commission` will sometimes be true (clients expecting false may error)
- ❌ COMMISSION transactions no longer counted in running balance

---

## TESTING CHECKLIST

- [ ] Response includes `license_running_balance` (authoritative)
- [ ] Response includes `company_utilizations` (derived)
- [ ] COMMISSION transactions marked `is_commission: true`
- [ ] COMMISSION transactions NOT added to `running_balance`
- [ ] Transaction `running_balance` field matches canonical calculation
- [ ] Company utilization sums equal expected values
- [ ] Response is valid JSON schema
- [ ] All decimal fields are stringified (not floats)
- [ ] All decimal fields are exactly 2 places
- [ ] Transactions ordered deterministically (date+ID)
- [ ] Metadata counts are correct
- [ ] Error cases (404, 403) return correct status + message
- [ ] Caching headers present
- [ ] Deprecation headers present (during Phase 2)

---

## MIGRATION GUIDE (For Frontend/API Clients)

### Old Code (Broken After Migration)

```python
# OLD: Using `balance` field
for txn in response['transactions']:
    print(f"Balance: {txn['balance']}")  # ❌ WILL FAIL (removed after 30 days)
```

### New Code (Required After Migration)

```python
# NEW: Using `running_balance` field
for txn in response['transactions']:
    print(f"License Balance: {response['license_running_balance']}")  # ✅ Use this
    print(f"Transaction Balance: {txn['running_balance']}")  # ✅ Use this instead
    
    # Handle COMMISSION explicitly
    if txn['is_commission']:
        print(f"  (Transaction is COMMISSION, excluded from balance)")
```

### Old Code (Company Breakdown)

```python
# OLD: PDF/Excel calculated per-company balance
running = 0
for txn in group_by_company(response['transactions']):
    if txn['type'] == 'PURCHASE':
        running += txn['amount']
    # ❌ Error-prone, diverges from backend
```

### New Code (Company Breakdown)

```python
# NEW: Use API-provided company utilizations
company_balances = response['company_utilizations']  # ✅ Use this (canonical)

# If you still need to group for display:
for company_id, balance in company_balances.items():
    print(f"Company {company_id}: {balance}")  # No recalculation needed
```

---

**Document Version:** 1.0  
**Date:** 2026-08-10  
**Status:** API CONTRACT SPECIFICATION
