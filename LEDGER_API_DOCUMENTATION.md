# Ledger Module API Documentation

## Base URL
All endpoints are prefixed with: `/api/`

## Authentication
All endpoints require authentication. Include the auth token in the request headers:
```
Authorization: Token <your-token-here>
```

---

## Chart of Accounts API

### 1. List All Accounts
**GET** `/api/chart-of-accounts/`

**Query Parameters:**
- `account_type`: Filter by type (ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE)
- `is_active`: Filter by active status (true/false)
- `parent`: Filter by parent account ID
- `search`: Search by code, name, description, or company name

**Response:**
```json
{
  "count": 76,
  "results": [
    {
      "id": 1,
      "code": "1000",
      "name": "Current Assets",
      "account_type": "ASSET",
      "account_type_display": "Asset",
      "parent": null,
      "parent_name": null,
      "linked_company": null,
      "company_name": null,
      "description": "",
      "is_active": true,
      "balance": "0.00",
      "created_on": "2025-01-01T00:00:00Z",
      "modified_on": "2025-01-01T00:00:00Z"
    }
  ]
}
```

### 2. Get Single Account
**GET** `/api/chart-of-accounts/{id}/`

### 3. Create Account
**POST** `/api/chart-of-accounts/`

**Request Body:**
```json
{
  "code": "1011",
  "name": "HDFC Bank",
  "account_type": "ASSET",
  "parent": 1,
  "description": "HDFC Current Account",
  "is_active": true
}
```

### 4. Update Account
**PUT** `/api/chart-of-accounts/{id}/`
**PATCH** `/api/chart-of-accounts/{id}/`

### 5. Delete Account
**DELETE** `/api/chart-of-accounts/{id}/`

### 6. Get Balance Sheet
**GET** `/api/chart-of-accounts/balance_sheet/`

**Response:**
```json
{
  "accounts": {
    "ASSET": [...],
    "LIABILITY": [...],
    "EQUITY": [...]
  },
  "totals": {
    "assets": 1000000.00,
    "liabilities": 500000.00,
    "equity": 500000.00,
    "total_liabilities_equity": 1000000.00
  },
  "date": "2025-01-15"
}
```

### 7. Get Trial Balance
**GET** `/api/chart-of-accounts/trial_balance/`

**Response:**
```json
{
  "accounts": [
    {
      "code": "1000",
      "name": "Current Assets",
      "account_type": "ASSET",
      "debit": 1000000.00,
      "credit": 0.00
    }
  ],
  "totals": {
    "debit": 2000000.00,
    "credit": 2000000.00,
    "difference": 0.00
  },
  "date": "2025-01-15"
}
```

### 8. Get Profit & Loss
**GET** `/api/chart-of-accounts/profit_loss/`

**Query Parameters:**
- `from_date`: Start date (YYYY-MM-DD)
- `to_date`: End date (YYYY-MM-DD)

**Response:**
```json
{
  "revenues": [
    {
      "code": "4000",
      "name": "Sales",
      "amount": 5000000.00
    }
  ],
  "expenses": [
    {
      "code": "5000",
      "name": "Purchase",
      "amount": 3000000.00
    }
  ],
  "totals": {
    "total_revenue": 5000000.00,
    "total_expense": 3000000.00,
    "net_profit_loss": 2000000.00
  },
  "from_date": "2024-04-01",
  "to_date": "2025-03-31"
}
```

---

## Bank Accounts API

### 1. List All Bank Accounts
**GET** `/api/bank-accounts/`

**Query Parameters:**
- `bank_name`: Filter by bank name
- `is_active`: Filter by active status
- `search`: Search by account name, bank name, account number, IFSC

**Response:**
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "account_name": "ICICI Current Account",
      "bank_name": "ICICI Bank",
      "account_number": "123456789",
      "ifsc_code": "ICIC0001234",
      "branch": "Mumbai",
      "ledger_account": 10,
      "ledger_account_name": "1011 - ICICI Bank",
      "opening_balance": "100000.00",
      "opening_balance_date": "2024-04-01",
      "current_balance": "250000.00",
      "is_active": true,
      "created_on": "2025-01-01T00:00:00Z",
      "modified_on": "2025-01-01T00:00:00Z"
    }
  ]
}
```

### 2. Create Bank Account
**POST** `/api/bank-accounts/`

**Request Body:**
```json
{
  "account_name": "HDFC Current Account",
  "bank_name": "HDFC Bank",
  "account_number": "987654321",
  "ifsc_code": "HDFC0001234",
  "branch": "Delhi",
  "ledger_account": 11,
  "opening_balance": "200000.00",
  "opening_balance_date": "2024-04-01",
  "is_active": true
}
```

### 3. Get Bank Statement
**GET** `/api/bank-accounts/{id}/statement/`

**Query Parameters:**
- `from_date`: Start date (YYYY-MM-DD)
- `to_date`: End date (YYYY-MM-DD)

**Response:**
```json
{
  "bank_account": {...},
  "opening_balance": 100000.00,
  "closing_balance": 250000.00,
  "transactions": [
    {
      "date": "2024-04-05",
      "entry_number": "JE-001",
      "narration": "Payment received from customer",
      "debit": 50000.00,
      "credit": 0.00,
      "balance": 150000.00
    }
  ],
  "from_date": "2024-04-01",
  "to_date": "2024-12-31"
}
```

---

## Journal Entries API

### 1. List All Journal Entries
**GET** `/api/journal-entries/`

**Query Parameters:**
- `entry_type`: Filter by type (GENERAL, SALES, PURCHASE, PAYMENT, RECEIPT, JOURNAL)
- `is_posted`: Filter by posted status (true/false)
- `is_auto_generated`: Filter by auto-generated (true/false)
- `entry_date`: Filter by date
- `search`: Search by entry number, narration, reference

**Response:**
```json
{
  "count": 10,
  "results": [
    {
      "id": 1,
      "entry_number": "JE-2025-001",
      "entry_date": "2025-01-15",
      "entry_type": "GENERAL",
      "entry_type_display": "General Entry",
      "linked_trade": null,
      "linked_trade_invoice": null,
      "linked_payment": null,
      "narration": "Opening balances",
      "reference_number": "",
      "is_posted": true,
      "is_auto_generated": false,
      "total_debit": "1000000.00",
      "total_credit": "1000000.00",
      "is_balanced": true,
      "lines": [
        {
          "id": 1,
          "account": 1,
          "account_name": "1000 - Current Assets",
          "account_code": "1000",
          "debit_amount": "1000000.00",
          "credit_amount": "0.00",
          "description": "Opening balance"
        },
        {
          "id": 2,
          "account": 30,
          "account_name": "3000 - Capital",
          "account_code": "3000",
          "debit_amount": "0.00",
          "credit_amount": "1000000.00",
          "description": "Opening balance"
        }
      ],
      "created_by": 1,
      "created_by_username": "admin",
      "created_on": "2025-01-15T10:00:00Z",
      "modified_on": "2025-01-15T10:00:00Z"
    }
  ]
}
```

### 2. Create Journal Entry
**POST** `/api/journal-entries/`

**Request Body:**
```json
{
  "entry_number": "JE-2025-002",
  "entry_date": "2025-01-16",
  "entry_type": "GENERAL",
  "narration": "Purchase of office supplies",
  "reference_number": "INV-123",
  "lines": [
    {
      "account": 50,
      "debit_amount": "5000.00",
      "credit_amount": "0.00",
      "description": "Office supplies"
    },
    {
      "account": 10,
      "debit_amount": "0.00",
      "credit_amount": "5000.00",
      "description": "Payment from bank"
    }
  ]
}
```

### 3. Post Journal Entry
**POST** `/api/journal-entries/{id}/post/`

Makes the entry immutable (cannot be edited or deleted).

**Response:**
```json
{
  "message": "Journal entry posted successfully",
  "entry": {...}
}
```

### 4. Unpost Journal Entry
**POST** `/api/journal-entries/{id}/unpost/`

Allows editing of the entry (only for non-auto-generated entries).

### 5. Auto-Generate from Trade
**POST** `/api/journal-entries/generate_from_trade/`

**Request Body:**
```json
{
  "trade_id": 123
}
```

**Response:**
```json
{
  "message": "Journal entry generated successfully",
  "entry": {...}
}
```

---

## Ledger Reports API

### 1. Party Ledger (Company-wise)
**GET** `/api/ledger/party/{company_id}/`

Shows all transactions with a specific company.

**Query Parameters:**
- `from_date`: Start date (YYYY-MM-DD)
- `to_date`: End date (YYYY-MM-DD)

**Response:**
```json
{
  "company": {
    "id": 5,
    "name": "ABC Suppliers Pvt Ltd"
  },
  "transactions": [
    {
      "date": "2024-05-01",
      "transaction_type": "PURCHASE",
      "reference_number": "P-ABC/2024-25/0001",
      "narration": "Purchase - P-ABC/2024-25/0001",
      "debit": 0.00,
      "credit": 100000.00,
      "balance": -100000.00
    },
    {
      "date": "2024-05-15",
      "transaction_type": "PAYMENT",
      "reference_number": "PAY-12",
      "narration": "Payment for P-ABC/2024-25/0001",
      "debit": 50000.00,
      "credit": 0.00,
      "balance": -50000.00
    }
  ],
  "summary": {
    "total_debit": 50000.00,
    "total_credit": 100000.00,
    "balance": -50000.00
  },
  "from_date": "2024-04-01",
  "to_date": "2024-12-31"
}
```

**Balance Interpretation:**
- Negative balance = We owe them (Payable)
- Positive balance = They owe us (Receivable)

### 2. Account Ledger
**GET** `/api/ledger/account/{account_id}/`

Shows all journal entries for a specific account.

**Query Parameters:**
- `from_date`: Start date
- `to_date`: End date

**Response:**
```json
{
  "account": {
    "id": 10,
    "code": "1011",
    "name": "ICICI Bank",
    "account_type": "ASSET"
  },
  "transactions": [
    {
      "date": "2024-04-05",
      "entry_number": "JE-001",
      "narration": "Payment received",
      "debit": 50000.00,
      "credit": 0.00,
      "balance": 50000.00
    }
  ],
  "summary": {
    "total_debit": 150000.00,
    "total_credit": 50000.00,
    "balance": 100000.00
  },
  "from_date": "2024-04-01",
  "to_date": "2024-12-31"
}
```

### 3. Outstanding Invoices
**GET** `/api/ledger/reports/outstanding-invoices/`

**Query Parameters:**
- `type`: "receivable" or "payable"

**Response:**
```json
{
  "type": "receivable",
  "invoices": [
    {
      "invoice_number": "LAB/2024-25/0005",
      "invoice_date": "2024-08-15",
      "company": "XYZ Buyers Ltd",
      "company_id": 10,
      "total_amount": 500000.00,
      "paid_amount": 300000.00,
      "outstanding_amount": 200000.00,
      "days_outstanding": 90
    }
  ],
  "total_outstanding": 500000.00,
  "count": 5
}
```

### 4. Aging Analysis
**GET** `/api/ledger/reports/aging-analysis/`

**Query Parameters:**
- `type`: "receivable" or "payable"

**Response:**
```json
{
  "type": "receivable",
  "aging": {
    "0-30": [
      {
        "invoice_number": "LAB/2024-25/0010",
        "invoice_date": "2024-12-20",
        "company": "ABC Ltd",
        "amount": 50000.00,
        "days": 15
      }
    ],
    "31-60": [...],
    "61-90": [...],
    "90+": [...]
  },
  "totals": {
    "0-30": 50000.00,
    "31-60": 100000.00,
    "61-90": 150000.00,
    "90+": 200000.00,
    "total": 500000.00
  }
}
```

---

## Common Use Cases

### Use Case 1: Recording a Purchase
```python
# 1. Create trade (existing flow)
POST /api/trades/
{
  "direction": "PURCHASE",
  "from_company": 5,
  "to_company": 1,
  "invoice_number": "P-ABC/2024-25/0001",
  "invoice_date": "2024-05-01",
  "total_amount": 100000.00
}

# 2. Auto-generate journal entry
POST /api/journal-entries/generate_from_trade/
{
  "trade_id": 123
}

# This creates:
# Debit: Purchase Account (5000)
# Credit: Sundry Creditor - ABC Suppliers (2-5)
```

### Use Case 2: Recording a Payment
```python
# 1. Create payment (existing flow)
POST /api/payments/
{
  "trade": 123,
  "date": "2024-05-15",
  "amount": 50000.00,
  "note": "Partial payment"
}

# 2. Create journal entry for payment
POST /api/journal-entries/
{
  "entry_number": "PE-001",
  "entry_date": "2024-05-15",
  "entry_type": "PAYMENT",
  "narration": "Payment to ABC Suppliers",
  "lines": [
    {
      "account": 20,  # Sundry Creditor
      "debit_amount": "50000.00",
      "credit_amount": "0.00"
    },
    {
      "account": 10,  # Bank Account
      "debit_amount": "0.00",
      "credit_amount": "50000.00"
    }
  ]
}
```

### Use Case 3: View Party Ledger
```python
# Get all transactions with a supplier
GET /api/ledger/party/5/?from_date=2024-04-01&to_date=2024-12-31

# Returns all purchases, payments, adjustments with running balance
```

### Use Case 4: Bank Reconciliation
```python
# 1. Get bank statement
GET /api/bank-accounts/1/statement/?from_date=2024-04-01&to_date=2024-12-31

# 2. Compare with actual bank statement
# 3. Create adjustment entries if needed
POST /api/journal-entries/
```

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Journal entry not balanced: Debit=10000.00, Credit=9000.00"
}
```

### 404 Not Found
```json
{
  "error": "Company not found"
}
```

### 403 Forbidden
```json
{
  "detail": "You do not have permission to perform this action."
}
```

---

## Standard Chart of Accounts (Preloaded)

**Assets (1000-1999)**
- 1000: Current Assets
  - 1001: Cash in Hand
  - 1010: Bank Accounts
  - 1100: Sundry Debtors
  - 1200: Inventory
  - 1400: Input Tax Credit

- 1500: Fixed Assets
  - 1501: Land & Building
  - 1502: Plant & Machinery
  - 1503: Furniture & Fixtures

**Liabilities (2000-2999)**
- 2000: Current Liabilities
  - 2100: Sundry Creditors
  - 2200: Output Tax Liability
  - 2300: TDS Payable

- 2600: Long Term Liabilities
  - 2601: Bank Loan

**Equity (3000-3999)**
- 3000: Capital
- 3100: Reserves & Surplus
- 3200: Current Year Profit/Loss

**Revenue (4000-4999)**
- 4000: Sales
- 4100: Other Income

**Expenses (5000-5999)**
- 5000: Purchase
- 5100: Direct Expenses
- 5200: Operating Expenses
- 5300: Selling Expenses
- 5400: Financial Expenses
- 5500: Administrative Expenses
- 5600: Depreciation

---

## Notes

1. **Posted Entries**: Once posted, journal entries cannot be modified or deleted (immutable for audit trail)
2. **Auto-Generated Entries**: Entries created from trades/payments are marked as auto-generated
3. **Balance Calculation**: Automatic based on account type (debit/credit)
4. **Party Accounts**: Automatically created when generating entries from trades
5. **Date Range**: Most reports support optional from_date and to_date filters

---

## Next Steps

1. Integrate journal entry generation with trade save signals
2. Create frontend components for ledger management
3. Add PDF export for reports
4. Implement user permissions for ledger access
