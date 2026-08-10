# License Ledger — Canonical Dataset Specification

**Purpose:** Define the exact structure, fields, types, and precision of the canonical ledger dataset returned by the API.  
**Status:** Design specification (Gate 3)  
**Date:** 2026-08-10

---

## DATASET STRUCTURE (Root Level)

```typescript
interface CanonicalLedgerDataset {
  // License Identification
  license_id: number;
  license_number: string;          // e.g. "0311045100"
  license_type: "DFIA" | "INCENTIVE";
  license_date: string;            // ISO 8601 date
  expiry_date: string;             // ISO 8601 date
  exporter: string;                // Exporter name

  // Authoritative Balances
  license_running_balance: string;        // Decimal(19,2), stringified for JSON
  opening_balance: string;                // Decimal(19,2)
  closing_balance: string;                // Decimal(19,2), = last transaction's running_balance
  available_balance: string;              // Decimal(19,2), from balance_calculator (existing field)

  // Derived Data
  company_utilizations: {
    [company_id: string]: string;        // company_uuid → Decimal(19,2) stringified
  };

  // Transaction History
  transactions: Transaction[];

  // Metadata
  metadata: {
    total_purchase_cif: string;          // Decimal(19,2)
    total_sales_cif: string;             // Decimal(19,2)
    total_purchase_value: string;        // Decimal(19,2) (INR for Incentive)
    total_sales_value: string;           // Decimal(19,2)
    total_commission_amount: string;     // Decimal(19,2)
    transaction_count: number;
    commission_count: number;
    purchase_count: number;
    sale_count: number;
    opening_date: string;                // ISO 8601 date (first transaction date)
    first_purchase_date: string | null;  // ISO 8601 date
    first_sale_date: string | null;      // ISO 8601 date
  };
}
```

---

## TRANSACTION OBJECT STRUCTURE

```typescript
interface Transaction {
  // Identification
  id: string;                      // Unique identifier (e.g., "trade_123" or "txn_1")
  trade_id: number;                // Foreign key to LicenseTrade
  date: string;                    // ISO 8601 date (transaction date)
  type: "OPENING" | "PURCHASE" | "SALE" | "COMMISSION";
  is_commission: boolean;          // true if COMMISSION, false otherwise

  // Company Attribution
  company_id: string | null;       // UUID or ID, null for OPENING
  company_name: string;            // Company name or "N/A"

  // Financial Data (DFIA-specific fields)
  amount_cif: string;              // Decimal(20,2), total CIF USD
  debit_cif: string;               // Decimal(20,2), if PURCHASE/OPENING
  credit_cif: string;              // Decimal(20,2), if SALE

  // Financial Data (Incentive-specific)
  amount_license_value: string;    // Decimal(20,2), license value (INR for Incentive)
  debit_license_value: string;     // Decimal(20,2)
  credit_license_value: string;    // Decimal(20,2)

  // Running Balance (CANONICAL, from backend)
  running_balance: string;         // Decimal(20,2), LICENSE-WIDE running balance (NOT per-company)

  // Invoice & Trade Details
  invoice_number: string;          // E.g., "2026-001", may be empty
  particular: string;              // Description (e.g., "Purchase DFIA - Exporter X")
  items: string;                   // Comma-separated item descriptions
  sion_norms: string;              // SION norm classes (DFIA only)
  qty: string;                     // Quantity in KG
  rate: string;                    // Exchange rate or unit rate

  // Profit/Loss (SALE rows only)
  profit_loss: string | null;      // Decimal(20,2), null for non-SALE rows

  // Status & Markers
  display_status: string;          // "Excluded from License Balance" if is_commission=true
}
```

---

## FIELD DEFINITIONS

### Identification Fields

| Field | Type | Nullable | Example | Notes |
|-------|------|----------|---------|-------|
| `license_id` | number | NO | 123 | Database PK |
| `license_number` | string | NO | "0311045100" | User-facing license ID |
| `license_type` | enum | NO | "DFIA" | "DFIA" or "INCENTIVE" |
| `license_date` | string | NO | "2026-01-01" | ISO 8601 |
| `expiry_date` | string | YES | "2026-12-31" | ISO 8601, may be null if never expires |
| `exporter` | string | NO | "Exporter Corp" | Name of exporting entity |

### Balance Fields (All Decimal, 2 places)

| Field | Type | Nullable | Example | Meaning |
|-------|------|----------|---------|---------|
| `license_running_balance` | string | NO | "1300.00" | **AUTHORITATIVE** license balance (excludes COMMISSION) |
| `opening_balance` | string | NO | "1000.00" | Initial balance at start of ledger |
| `closing_balance` | string | NO | "1300.00" | Final balance = last txn's running_balance |
| `available_balance` | string | NO | "1300.00" | Current available balance (from balance_calculator) |

### Company Utilization Fields

| Field | Type | Structure | Example |
|-------|------|-----------|---------|
| `company_utilizations` | object | `{company_id: balance_string}` | `{"uuid_A": "300.00", "uuid_B": "250.00"}` |

**Guarantee:** Sum of values does NOT equal `license_running_balance` (different metrics).

### Transaction Fields

#### Identification
| Field | Type | Nullable | Example |
|-------|------|----------|---------|
| `id` | string | NO | "trade_123" or "txn_opening_1" |
| `trade_id` | number | YES | 456 |
| `date` | string | NO | "2026-01-20" |
| `type` | enum | NO | "PURCHASE" |
| `is_commission` | boolean | NO | false |

#### Company
| Field | Type | Nullable | Example |
|-------|------|----------|---------|
| `company_id` | string | YES | "uuid_A" (null for OPENING) |
| `company_name` | string | YES | "Company A" (null for OPENING) |

#### Financial (DFIA)
| Field | Type | Nullable | Example | Meaning |
|-------|------|----------|---------|---------|
| `amount_cif` | string | NO | "500.00" | Total CIF USD for transaction |
| `debit_cif` | string | NO | "500.00" | CIF on debit side (if PURCHASE) |
| `credit_cif` | string | NO | "200.00" | CIF on credit side (if SALE) |

#### Financial (Incentive)
| Field | Type | Nullable | Example | Meaning |
|-------|------|----------|---------|---------|
| `amount_license_value` | string | NO | "1000000.00" | License value (INR) |
| `debit_license_value` | string | NO | "1000000.00" | License value on debit side |
| `credit_license_value` | string | NO | "500000.00" | License value on credit side |

#### Running Balance
| Field | Type | Nullable | Example | Meaning |
|-------|------|----------|---------|---------|
| `running_balance` | string | NO | "1500.00" | **LICENSE-WIDE** cumulative balance (NOT per-company) |

#### Invoice & Details
| Field | Type | Nullable | Example |
|-------|------|----------|---------|
| `invoice_number` | string | YES | "2026-001" |
| `particular` | string | NO | "Purchase DFIA - Supplier X" |
| `items` | string | YES | "Rice, Wheat" |
| `sion_norms` | string | YES | "E1, E5" |
| `qty` | string | YES | "1500.50" |
| `rate` | string | YES | "82.50" |

#### Profit/Loss
| Field | Type | Nullable | Example | When Present |
|-------|------|----------|---------|---|
| `profit_loss` | string | YES | "25.50" | SALE rows only |

#### Status
| Field | Type | Nullable | Example |
|-------|------|----------|---------|
| `display_status` | string | YES | "Excluded from License Balance" |

---

## NUMERIC PRECISION

### Decimal Field Rules

**All monetary fields:**
- **Type:** Python `Decimal` (backend) → stringified JSON (API response)
- **Precision:** Exactly 2 decimal places
- **Minimum:** `Decimal('-999999999.99')`
- **Maximum:** `Decimal('999999999.99')`
- **Rounding:** `ROUND_HALF_UP` (standard commercial)

### Examples

| Value | Stored As | JSON |
|-------|-----------|------|
| 1000 | Decimal('1000.00') | `"1000.00"` |
| 123.456 | Decimal('123.46') | `"123.46"` (ROUNDED) |
| 0.005 | Decimal('0.01') | `"0.01"` (ROUNDED_HALF_UP) |
| -500 | Decimal('-500.00') | `"-500.00"` |
| 0 | Decimal('0.00') | `"0.00"` |

**Why stringify?** JSON `Number` type loses precision for large decimals; string preserves exact 2-place value.

---

## COMPANY_UTILIZATIONS STRUCTURE

### Definition

```json
{
  "company_utilizations": {
    "uuid_company_A": "300.00",
    "uuid_company_B": "250.00"
  }
}
```

### Calculation (Per Company)

```
For each Company:
  balance = 0
  for each transaction where company_id = Company AND is_commission = false:
    if type = PURCHASE:
      balance += amount_cif (or amount_license_value for Incentive)
    elif type = SALE:
      balance -= amount_cif
  company_utilizations[company_id] = balance
```

### Key Properties

- **Independent:** Each company's balance calculated independently
- **No Opening Balance:** Opening transaction doesn't distribute to companies
- **No COMMISSION:** COMMISSION transactions excluded
- **Reset Per Company:** Value starts at 0, accumulates only that company's transactions
- **May Be Zero:** If no transactions, or if purchases = sales

---

## METADATA STRUCTURE

```json
{
  "metadata": {
    "total_purchase_cif": "1500.00",           // Sum of all PURCHASE debit_cif
    "total_sales_cif": "200.00",               // Sum of all SALE credit_cif
    "total_purchase_value": "1200000.00",      // Sum of all PURCHASE amounts (INR for Incentive)
    "total_sales_value": "400000.00",          // Sum of all SALE amounts (INR for Incentive)
    "total_commission_amount": "100.00",       // Sum of all COMMISSION amounts (not in balance)
    "transaction_count": 4,                     // Total transaction count (including COMMISSION)
    "commission_count": 1,                      // Count of COMMISSION-type transactions
    "purchase_count": 1,                        // Count of PURCHASE transactions
    "sale_count": 1,                            // Count of SALE transactions
    "opening_date": "2026-01-15",              // Date of first transaction
    "first_purchase_date": "2026-01-20",       // Date of first PURCHASE (or null)
    "first_sale_date": "2026-02-10"            // Date of first SALE (or null)
  }
}
```

---

## TRANSACTION ORDERING GUARANTEE

**Order by:** `(date ASC, id ASC)`

Example:
```
2026-01-15, txn_1: OPENING
2026-01-20, txn_2: PURCHASE (same date, lower ID)
2026-01-20, txn_3: PURCHASE (same date, higher ID)
2026-02-01, txn_4: COMMISSION
2026-02-10, txn_5: SALE
```

**Guarantee:** Same final `running_balance` regardless of display order (immutable).

---

## SPECIAL CASES

### Empty Ledger (No Transactions)

```json
{
  "license_running_balance": "0.00",
  "opening_balance": "0.00",
  "closing_balance": "0.00",
  "company_utilizations": {},
  "transactions": [],
  "metadata": {
    "transaction_count": 0,
    "commission_count": 0,
    ...
  }
}
```

### COMMISSION-Only Ledger

```json
{
  "license_running_balance": "1000.00",  // Only opening + COMMISSION excluded
  "opening_balance": "1000.00",
  "closing_balance": "1000.00",
  "company_utilizations": {"company_B": "0.00"},  // Company with COMMISSION has 0 util
  "transactions": [
    {
      "type": "OPENING",
      "amount_cif": "1000.00",
      "running_balance": "1000.00",
      "is_commission": false
    },
    {
      "type": "COMMISSION",
      "amount_cif": "100.00",
      "running_balance": "1000.00",  // ← UNCHANGED (excluded)
      "is_commission": true,
      "display_status": "Excluded from License Balance"
    }
  ]
}
```

### Negative Balance (If Allowed)

```json
{
  "license_running_balance": "-500.00",
  "closing_balance": "-500.00",
  "transactions": [
    { "type": "OPENING", "amount_cif": "1000.00", "running_balance": "1000.00" },
    { "type": "SALE", "amount_cif": "1500.00", "running_balance": "-500.00" }
  ]
}
```

---

## VALIDATION CHECKLIST (Before Serialization)

- [ ] All Decimal fields are exactly 2 decimal places
- [ ] All ISO 8601 dates are valid
- [ ] `license_running_balance` excludes all COMMISSION transactions
- [ ] `company_utilizations` values sum equals opening + all non-COMMISSION transactions
- [ ] Each `running_balance` is cumulative (prior balance + current amount, excluding COMMISSION)
- [ ] `is_commission: true` only when type = "COMMISSION"
- [ ] `is_commission: false` for all other types
- [ ] Transactions are sorted deterministically by date+id
- [ ] No null values in required fields
- [ ] `closing_balance` == last transaction's `running_balance`

---

## API RESPONSE EXAMPLE (Complete)

```json
{
  "license_id": 123,
  "license_number": "0311045100",
  "license_type": "DFIA",
  "license_date": "2026-01-01",
  "expiry_date": "2026-12-31",
  "exporter": "Export Corp Ltd",
  "license_running_balance": "1300.00",
  "opening_balance": "1000.00",
  "closing_balance": "1300.00",
  "available_balance": "1300.00",
  
  "company_utilizations": {
    "uuid_A": "300.00",
    "uuid_B": "250.00"
  },
  
  "transactions": [
    {
      "id": "txn_1",
      "trade_id": null,
      "date": "2026-01-01",
      "type": "OPENING",
      "is_commission": false,
      "company_id": null,
      "company_name": null,
      "amount_cif": "1000.00",
      "debit_cif": "1000.00",
      "credit_cif": "0.00",
      "running_balance": "1000.00",
      "invoice_number": "0311045100",
      "particular": "Opening Balance - Original DFIA License",
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
      "invoice_number": "2026-001",
      "particular": "Purchase DFIA - Supplier Inc",
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
      "invoice_number": "2026-COM-001",
      "particular": "Commission Paid to Customs",
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
      "invoice_number": "2026-SALE-001",
      "particular": "Sale to Buyer Corp",
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
    "total_purchase_value": "1200000.00",
    "total_sales_value": "400000.00",
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

**Document Version:** 1.0  
**Date:** 2026-08-10  
**Status:** DESIGN SPECIFICATION
