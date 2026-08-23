# LEDGER API NEW CONTRACT — Canonical Format

**Phase 4C: API Migration to CanonicalLedgerService**

Generated: 2026-08-10

---

## Requirement

The Ledger API must consume **CanonicalLedgerService** as its single source of truth and expose the canonical dataset unambiguously to consumers (frontend, tests, PDF exporters).

**CRITICAL ARCHITECTURAL RULE:**
> The API must NOT calculate financial values. It is a transparent serialization layer that represents the output of CanonicalLedgerService with no modifications, calculations, or business logic.

---

## New Response Structure

### Endpoint

| Property | Value |
|----------|-------|
| HTTP Method | GET |
| Path | `/licenses/{id}/ledger_detail/` |
| View | `LicenseLedgerViewSet.ledger_detail()` |
| Permissions | `LicenseLedgerViewPermission` (unchanged) |
| Query Parameters | `company` (optional), `license_type` (optional) (unchanged) |

### Response (DFIA License)

**Status Code:** 200 OK

```json
{
  "license_id": 123,
  "license_type": "DFIA",
  "license_number": "0311045100",
  "license_date": "2023-01-15",
  "expiry_date": "2024-01-14",
  "exporter_id": 5,
  "exporter_name": "Exporter Inc.",
  "port_id": 8,
  "port_name": "Port of Mumbai",
  
  "opening_balance": "50000.00",
  "license_running_balance": "45000.00",
  "closing_balance": "45000.00",
  
  "transactions": [
    {
      "date": "2023-01-15",
      "id": 0,
      "type": "OPENING",
      "company_id": null,
      "company_name": null,
      "amount": "50000.00",
      "is_commission": false,
      "affects_balance": true,
      "license_running_balance": "50000.00"
    },
    {
      "date": "2023-02-01",
      "id": 10,
      "type": "PURCHASE",
      "company_id": 42,
      "company_name": "Buyer Inc.",
      "amount": "5000.00",
      "is_commission": false,
      "affects_balance": true,
      "license_running_balance": "55000.00"
    },
    {
      "date": "2023-03-01",
      "id": 11,
      "type": "SALE",
      "company_id": 43,
      "company_name": "Seller Inc.",
      "amount": "2500.00",
      "is_commission": false,
      "affects_balance": true,
      "license_running_balance": "52500.00"
    },
    {
      "date": "2023-04-01",
      "id": 12,
      "type": "COMMISSION_PURCHASE",
      "company_id": 44,
      "company_name": "Commission Agent",
      "amount": "250.00",
      "is_commission": true,
      "affects_balance": false,
      "license_running_balance": "52500.00",
      "display_status": "Excluded from License Balance"
    }
  ],
  
  "company_utilizations": [
    {
      "company_id": 42,
      "company_name": "Buyer Inc.",
      "utilization_balance": "5000.00"
    },
    {
      "company_id": 43,
      "company_name": "Seller Inc.",
      "utilization_balance": "-2500.00"
    }
  ],
  
  "totals": {
    "total_purchases": "5000.00",
    "total_sales": "2500.00",
    "total_commission": "250.00"
  }
}
```

---

## Field Reference

### Root Level

| Field | Type | Nullable | Source | Description |
|-------|------|----------|--------|-------------|
| `license_id` | int | No | License object | License database ID |
| `license_type` | str | No | Constant | DFIA or INCENTIVE |
| `license_number` | str | No | License object | License identifier |
| `license_date` | date (ISO) | No | License object | License issue date |
| `expiry_date` | date (ISO) | No | License object | License expiry date |
| `exporter_id` | int | Yes | License object | Exporter PK **[NEW]** |
| `exporter_name` | str | Yes | License object | Exporter name |
| `port_id` | int | Yes | License object | Port PK **[NEW]** |
| `port_name` | str | Yes | License object | Port name |
| `opening_balance` | decimal (string) | No | CanonicalLedgerService | Opening balance (0.00 if none) |
| `license_running_balance` | decimal (string) | No | CanonicalLedgerService | Final balance after all txns **[NEW CANONICAL NAME]** |
| `closing_balance` | decimal (string) | No | CanonicalLedgerService | Same as `license_running_balance` (alias for clarity) |
| `transactions` | array | No | CanonicalLedgerService | List of transaction objects |
| `company_utilizations` | array | No | CanonicalLedgerService | Per-company balance breakdown **[NEW]** |
| `totals` | object | No | CanonicalLedgerService | Aggregate totals **[NEW]** |

### Transaction Object

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `date` | date (ISO) | No | Transaction date |
| `id` | int | No | Transaction ID (0 for OPENING; trade ID for others) |
| `type` | str | No | OPENING, PURCHASE, SALE, COMMISSION_PURCHASE, COMMISSION_SALE |
| `company_id` | int | Yes | Company involved (null for OPENING) |
| `company_name` | str | Yes | Company name (null for OPENING) |
| `amount` | decimal (string) | No | Transaction amount (CIF USD or INR, context-dependent) |
| `is_commission` | bool | No | True if type contains COMMISSION |
| `affects_balance` | bool | No | True if PURCHASE/SALE (false if COMMISSION) |
| `license_running_balance` | decimal (string) | No | Running balance AFTER this transaction |
| `display_status` | str | Yes | **[NEW]** "Excluded from License Balance" if `is_commission` |

**Key Differences from Current API:**

1. `type` field now uses canonical names: COMMISSION_PURCHASE, COMMISSION_SALE (not COMMISSION)
2. NEW field: `is_commission` (boolean for easy filtering)
3. NEW field: `affects_balance` (explicit semantic)
4. NEW field: `display_status` (UI-friendly status message)
5. `amount` is the canonical amount; no separate debit/credit fields
6. `id` is explicit (0 for OPENING; trade ID for others)

### Company Utilization Object

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `company_id` | int | No | Company PK |
| `company_name` | str | Yes | Company name |
| `utilization_balance` | decimal (string) | No | Running balance for this company |

### Totals Object

| Field | Type | Description |
|-------|------|-------------|
| `total_purchases` | decimal (string) | Sum of all PURCHASE amounts (excludes COMMISSION) |
| `total_sales` | decimal (string) | Sum of all SALE amounts (excludes COMMISSION) |
| `total_commission` | decimal (string) | Sum of all COMMISSION amounts (excluded from balance) |

---

## Backward Compatibility

### Breaking Changes

1. **Transaction `type` field:**
   - Old API: returns "COMMISSION" for both COMMISSION_PURCHASE and COMMISSION_SALE
   - New API: returns explicit COMMISSION_PURCHASE or COMMISSION_SALE
   - **Impact:** Frontend code that filters by `type === "COMMISSION"` will break

2. **Missing old fields:**
   - Old API included: `particular`, `invoice_number`, `items`, `sion_norms`, `qty`, `cif_usd`, `debit_cif`, `credit_cif`, `rate`, `debit_amount`, `credit_amount`, `balance`, `profit_loss`, `trade_id`
   - New API does NOT include these (reserved for Phase 4D / separate detail endpoint)
   - **Impact:** Frontend code that renders these fields will lose data

3. **Root-level balance field name:**
   - Old API: `available_balance`, `db_balance`
   - New API: `license_running_balance`, `closing_balance`
   - **Impact:** Frontend code referencing `available_balance` will break

### Mitigation Strategy

**Phase 4C:** Add backward-compatible aliasing in the serializer:

```python
class LedgerDetailSerializer(serializers.Serializer):
    # New canonical fields
    license_running_balance = serializers.DecimalField(...)
    closing_balance = serializers.DecimalField(...)
    
    # Old field names (deprecated, alias to new)
    available_balance = serializers.SerializerMethodField()
    db_balance = serializers.SerializerMethodField()
    
    def get_available_balance(self, obj):
        return obj['license_running_balance']
    
    def get_db_balance(self, obj):
        return obj['license_running_balance']
```

**Frontend Migration Path:**
1. Phase 4C: API returns both old and new field names
2. Developers update frontend code to use new field names
3. Phase 4D+: Remove old field names

### Fields to NOT Include in Phase 4C

Reserved for future phases or separate detail endpoints:
- `particular` (too coupled to current view logic)
- `invoice_number` (vendor-specific detail)
- `items`, `sion_norms`, `qty` (commodity details; belongs in item pivot, not ledger)
- `cif_usd`, `debit_cif`, `credit_cif` (currency-specific; belongs in separate detail)
- `rate` (exchange rate; currency-specific detail)
- `debit_amount`, `credit_amount` (duplicates of amount; redundant)
- `balance` (renamed to `license_running_balance`)
- `profit_loss` (computational detail; belongs in separate P/L endpoint)
- `trade_id` (internal ID; not needed for display)

---

## Company Filtering

When `?company={id}` query parameter is provided:

**Current Implementation:**
- Returns only transactions involving that company
- Direction-aware: PURCHASE if buyer, SALE if seller
- Still includes all other transactions

**New Implementation (Phase 4C):**
- **UNCHANGED** — API continues to delegate company filtering to CanonicalLedgerService
- CanonicalLedgerService accepts company_id parameter (Phase 4D planned)
- For now, filtering occurs at the dataset level (CanonicalLedgerService can be extended)

---

## Commission Handling (Critical)

**New Policy (Canonical):**

1. **COMMISSION_PURCHASE and COMMISSION_SALE appear in `transactions`**
2. **They DO NOT affect `license_running_balance`**
3. **`is_commission` = true; `affects_balance` = false**
4. **`display_status` = "Excluded from License Balance"**
5. **They appear in `totals.total_commission` separately**

**Example:**
```json
{
  "type": "COMMISSION_PURCHASE",
  "amount": "250.00",
  "is_commission": true,
  "affects_balance": false,
  "license_running_balance": "50000.00",  // Unchanged from previous txn
  "display_status": "Excluded from License Balance"
}
```

---

## Error Responses (UNCHANGED)

### 404 Not Found
```json
{
  "error": "License not found: 999",
  "searched_in": "both DFIA and Incentive"
}
```

### 400 Bad Request
```json
{
  "error": "Invalid company ID"
}
```

---

## Serializer Implementation

Location: `backend/apps/license/serializers/ledger.py`

```python
class TransactionSerializer(serializers.Serializer):
    date = serializers.DateField()
    id = serializers.IntegerField()
    type = serializers.CharField()
    company_id = serializers.IntegerField(allow_null=True)
    company_name = serializers.CharField(allow_null=True)
    amount = serializers.DecimalField(max_digits=19, decimal_places=2)
    is_commission = serializers.BooleanField()
    affects_balance = serializers.BooleanField()
    license_running_balance = serializers.DecimalField(max_digits=19, decimal_places=2)
    display_status = serializers.CharField(required=False, allow_blank=True)


class CompanyUtilizationSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    company_name = serializers.CharField(allow_null=True)
    utilization_balance = serializers.DecimalField(max_digits=19, decimal_places=2)


class TotalsSerializer(serializers.Serializer):
    total_purchases = serializers.DecimalField(max_digits=19, decimal_places=2)
    total_sales = serializers.DecimalField(max_digits=19, decimal_places=2)
    total_commission = serializers.DecimalField(max_digits=19, decimal_places=2)


class CanonicalLedgerSerializer(serializers.Serializer):
    license_id = serializers.IntegerField()
    license_type = serializers.CharField()
    license_number = serializers.CharField()
    license_date = serializers.DateField()
    expiry_date = serializers.DateField()
    exporter_id = serializers.IntegerField(allow_null=True)
    exporter_name = serializers.CharField(allow_null=True)
    port_id = serializers.IntegerField(allow_null=True)
    port_name = serializers.CharField(allow_null=True)
    opening_balance = serializers.DecimalField(max_digits=19, decimal_places=2)
    license_running_balance = serializers.DecimalField(max_digits=19, decimal_places=2)
    closing_balance = serializers.DecimalField(max_digits=19, decimal_places=2)
    transactions = TransactionSerializer(many=True)
    company_utilizations = CompanyUtilizationSerializer(many=True)
    totals = TotalsSerializer()
    
    # Backward compatibility aliases (Phase 4C only)
    available_balance = serializers.SerializerMethodField()
    db_balance = serializers.SerializerMethodField()
    
    def get_available_balance(self, obj):
        return obj.get('license_running_balance')
    
    def get_db_balance(self, obj):
        return obj.get('license_running_balance')
```

---

## API Implementation (View Layer)

Location: `backend/apps/license/views/ledger.py`, `ledger_detail()` action

```python
@action(detail=True, methods=['get'])
def ledger_detail(self, request, pk=None):
    """
    Get detailed ledger view for a specific license showing all transactions.
    
    Endpoint: GET /licenses/{id}/ledger_detail/
    
    Query Parameters:
    - company: Optional company ID for filtering
    - license_type: Optional license type (DFIA, INCENTIVE, etc.)
    
    Returns:
    - 200: Canonical ledger dataset
    - 404: License not found
    - 400: Invalid parameters
    """
    # Authorization
    license_type = request.query_params.get('license_type', 'AUTO')
    
    # Lookup license
    found_type, license = self._find_license_by_id_or_number(pk, ...)
    if not license:
        return Response({'error': f'License not found: {pk}'}, status=404)
    
    # Delegate calculation to CanonicalLedgerService (no business logic here)
    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
        license_id=license.id,
        license_type=found_type
    )
    
    # Serialize for response (representation only, no calculations)
    serializer = CanonicalLedgerSerializer(dataset)
    return Response(serializer.data)
```

---

## Testing Requirements

### Test 1: Balance Parity
```python
def test_api_license_running_balance_equals_canonical():
    canonical = CanonicalLedgerService.build_canonical_ledger_dataset(license.id, 'DFIA')
    response = self.client.get(f'/api/licenses/{license.id}/ledger_detail/')
    
    assert response.data['license_running_balance'] == str(canonical['license_running_balance'])
```

### Test 2: Transactions Parity
```python
def test_api_transactions_match_canonical():
    canonical = CanonicalLedgerService.build_canonical_ledger_dataset(license.id, 'DFIA')
    response = self.client.get(f'/api/licenses/{license.id}/ledger_detail/')
    
    assert len(response.data['transactions']) == len(canonical['transactions'])
    for api_txn, canonical_txn in zip(response.data['transactions'], canonical['transactions']):
        assert api_txn['type'] == canonical_txn['type']
        assert api_txn['amount'] == str(canonical_txn['amount'])
```

### Test 3: Commission Handling
```python
def test_api_commission_excluded_from_balance():
    response = self.client.get(f'/api/licenses/{license.id}/ledger_detail/')
    
    commission_txns = [t for t in response.data['transactions'] if t['is_commission']]
    for txn in commission_txns:
        assert txn['affects_balance'] is False
        assert txn['display_status'] == 'Excluded from License Balance'
```

### Test 4: Backward Compatibility
```python
def test_api_includes_deprecated_fields_for_backward_compat():
    response = self.client.get(f'/api/licenses/{license.id}/ledger_detail/')
    
    # Old field names should exist (for compatibility)
    assert 'available_balance' in response.data
    assert 'db_balance' in response.data
    assert response.data['available_balance'] == response.data['license_running_balance']
```

---

## GATE 4C Contract Checklist

- [ ] Serializer created and tested
- [ ] View migrated to CanonicalLedgerService
- [ ] No financial calculations in API layer
- [ ] Commission handling verified
- [ ] Backward compatibility fields aliased
- [ ] Parity tests PASS
- [ ] All existing tests PASS
- [ ] No breaking changes in response structure

---

## Phase 4D Readiness

Once Phase 4C is complete, Phase 4D (UI/PDF/Excel migration) can:
1. Consume the canonical API response directly
2. Map canonical fields to UI display names
3. Cache canonical response for performance
4. Add new fields as needed (inventory details, tax, etc.)

**No Phase 4D work begins until Phase 4C PASS gate is confirmed.**
