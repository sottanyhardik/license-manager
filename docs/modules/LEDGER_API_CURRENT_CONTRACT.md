# LEDGER API CURRENT CONTRACT

**Phase 4C: Current API Response Structure**

Generated: 2026-08-10

---

## Endpoint

| Property | Value |
|----------|-------|
| HTTP Method | GET |
| Path | `/licenses/{id}/ledger_detail/` |
| View | `LicenseLedgerViewSet.ledger_detail()` |
| Permissions | `LicenseLedgerViewPermission` |

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `company` | int | No | None | Filter transactions by company ID (direction-aware) |
| `license_type` | str | No | AUTO | License type: DFIA, INCENTIVE, RODTEP, ROSTL, MEIS, AUTO |

---

## Current Response Structure (DFIA)

**Status Code:** 200 OK

**Content-Type:** `application/json`

```json
{
  "license_id": 123,
  "license_type": "DFIA",
  "license_number": "0311045100",
  "license_date": "2023-01-15",
  "expiry_date": "2024-01-14",
  "exporter": "Exporter Inc.",
  "port": "Port of Mumbai",
  "total_value": 50000.00,
  "available_balance": 45000.00,
  "db_balance": 45000.00,
  "transactions": [
    {
      "date": "2023-01-15",
      "type": "OPENING",
      "particular": "Opening Balance - Original DFIA License",
      "invoice_number": "0311045100",
      "cif_usd": 50000.00,
      "debit_cif": 50000.00,
      "credit_cif": 0,
      "rate": 0,
      "amount": 0,
      "debit_amount": 0,
      "credit_amount": 0,
      "balance": 50000.00,
      "profit_loss": 0,
      "company_id": null,
      "company_name": "N/A",
      "trade_id": null
    },
    {
      "date": "2023-02-01",
      "type": "PURCHASE",
      "particular": "Purchase DFIA - Seller Inc.",
      "invoice_number": "INV-001",
      "items": "Item A, Item B",
      "sion_norms": "NORM-A, NORM-B",
      "qty": 1000.5,
      "cif_usd": 5000.00,
      "debit_cif": 5000.00,
      "credit_cif": 0,
      "rate": 83.50,
      "amount": 417500.00,
      "debit_amount": 417500.00,
      "credit_amount": 0,
      "balance": 55000.00,
      "profit_loss": 0,
      "company_id": 42,
      "company_name": "Buyer Inc.",
      "trade_id": 10
    },
    {
      "date": "2023-03-01",
      "type": "SALE",
      "particular": "DFIA Sale - Final Buyer Inc.",
      "invoice_number": "INV-002",
      "items": "Item A",
      "sion_norms": "NORM-A",
      "qty": 500.0,
      "cif_usd": 2500.00,
      "debit_cif": 0,
      "credit_cif": 2500.00,
      "rate": 83.50,
      "amount": 208750.00,
      "debit_amount": 0,
      "credit_amount": 208750.00,
      "balance": 52500.00,
      "profit_loss": 12345.67,
      "company_id": 43,
      "company_name": "Seller Inc.",
      "trade_id": 11
    },
    {
      "date": "2023-04-01",
      "type": "COMMISSION",
      "particular": "Commission Paid to Commission Agent",
      "invoice_number": "INV-003",
      "items": "N/A",
      "sion_norms": "",
      "qty": 0,
      "cif_usd": 250.00,
      "debit_cif": 250.00,
      "credit_cif": 0,
      "rate": 0,
      "amount": 20000.00,
      "debit_amount": 20000.00,
      "credit_amount": 0,
      "balance": 52750.00,
      "profit_loss": 0,
      "company_id": 44,
      "company_name": "Commission Agent",
      "trade_id": 12
    }
  ]
}
```

---

## Current Response Structure (Incentive)

**Similar to DFIA but:**

```json
{
  "license_id": 456,
  "license_type": "INCENTIVE",
  "license_number": "RODTEP-001",
  ...
  "transactions": [...]
}
```

---

## Field Reference

### Root Level

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `license_id` | int | No | License database ID |
| `license_type` | str | No | DFIA, INCENTIVE, RODTEP, ROSTL, MEIS |
| `license_number` | str | No | License identifier |
| `license_date` | date | No | License issue date |
| `expiry_date` | date | No | License expiry date |
| `exporter` | str | Yes | Exporter name |
| `port` | str | Yes | Port name |
| `total_value` | decimal | No | Total CIF USD (sum of all purchases) |
| `available_balance` | decimal | No | **Current balance after all txns** |
| `db_balance` | decimal | No | Same as `available_balance` (TODO: deprecate) |
| `transactions` | array | No | List of transaction objects |

### Transaction Fields

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `date` | date | No | Transaction date |
| `type` | str | No | OPENING, PURCHASE, SALE, COMMISSION |
| `particular` | str | No | Human-readable description |
| `invoice_number` | str | Yes | Invoice or document number |
| `items` | str | Yes | Comma-separated item names (max 100 chars) |
| `sion_norms` | str | Yes | SION norm classes |
| `qty` | decimal | No | Quantity in KG |
| `cif_usd` | decimal | No | Transaction CIF USD amount |
| `debit_cif` | decimal | No | Debit CIF (PURCHASE/OPENING) |
| `credit_cif` | decimal | No | Credit CIF (SALE) |
| `rate` | decimal | No | Exchange rate (INR/USD) |
| `amount` | decimal | No | INR amount |
| `debit_amount` | decimal | No | Debit INR amount |
| `credit_amount` | decimal | No | Credit INR amount |
| `balance` | decimal | No | Running balance after this transaction |
| `profit_loss` | decimal | No | P/L for SALE transactions; 0 for others |
| `company_id` | int | Yes | Company involved in transaction |
| `company_name` | str | Yes | Company name |
| `trade_id` | int | Yes | Trade record ID |

---

## Current Implementation Details

### Source Code
- **View:** `backend/apps/license/views/ledger.py`, lines 218-259
- **Builder:** `backend/apps/license/services/exporters/ledger_pdf.py`, lines 1025-1275

### Calculation Logic

1. **Opening Balance:**
   - If no trades and `license.opening_balance > 0`: OPENING transaction

2. **Transaction Ordering:**
   - Purchases before sales (purchases sorted by date first)
   - All sorted by: date ASC, then trade ID ASC

3. **Running Balance:**
   - Starts at opening balance (or 0)
   - PURCHASE/OPENING: add to balance
   - COMMISSION_PURCHASE: add to balance (treated as purchase for balance purposes)
   - SALE: subtract from balance
   - COMMISSION_SALE: add to balance (anomalous; may be bug)
   - Final balance: calls `LicenseBalanceCalculator.calculate_financial_balance(license)`

4. **Profit/Loss Calculation:**
   - SALE: `total_amount - (total_cif_usd * avg_purchase_rate)`
   - Considers company-specific purchase history if available

5. **Commission Handling:**
   - Appears as transaction type "COMMISSION"
   - Increases balance (treated as debit_cif)
   - Anomaly: `balance` field increases, but semantics unclear

6. **Company Filtering:**
   - If `company_id` provided:
     - PURCHASE/COMMISSION_PURCHASE: `to_company_id == company_id`
     - SALE/COMMISSION_SALE: `from_company_id == company_id`

---

## Error Responses

### 404 Not Found

**When:** License not found

```json
{
  "error": "License not found: 999",
  "searched_in": "both DFIA and Incentive"
}
```

### 400 Bad Request

**When:** Invalid query parameters

```json
{
  "error": "Invalid company ID"
}
```

---

## Performance Notes

- **Query count (small ledger, 3 txns):** ~10 queries (from Phase 4B testing)
- **Query count (large ledger, 20 txns):** ~27 queries (baseline acceptable)

---

## Known Issues / Anomalies

1. **`db_balance` field:** Redundant with `available_balance`; should be deprecated

2. **Commission handling:** Semantics unclear:
   - COMMISSION_PURCHASE: increases balance (correct)
   - COMMISSION_SALE: increases balance (may be bug; should it decrease?)

3. **Final balance calculation:** Calls external `LicenseBalanceCalculator` instead of using local `running_balance`
   - This means API returns DB-calculated balance, not transaction-replayed balance
   - Disconnect documented as BL-LEDGER-02

4. **Field presence inconsistency:** Some transactions include `items`, `sion_norms`, `qty`; others set to N/A or empty
   - OPENING transactions: all 0 or N/A
   - COMMISSION transactions: may be N/A

---

## Frontend Assumptions

Based on code review of React consumers:

1. **Response is always a dict** (not a list or paginated)
2. **`transactions` is always an array** (may be empty)
3. **Fields are expected by name** — no aliasing tolerated
4. **Dates are ISO format** (YYYY-MM-DD)
5. **Decimals are numbers** (JSON float)

---

## GATE 4C Requirement

**The API must maintain this exact contract** during Phase 4C migration to CanonicalLedgerService.

Any breaking changes require:
1. Explicit deprecation
2. Backward-compatible aliasing (old field name → new field value)
3. Frontend updates
4. Test updates

**No breaking changes allowed without explicit justification.**
