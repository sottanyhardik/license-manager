# License Ledger — Architecture & Module Interactions

**Purpose:** Visual and textual architecture documentation showing module boundaries, data flows, and responsibility matrix.  
**Status:** Design specification (Gate 3)  
**Date:** 2026-08-10

---

## HIGH-LEVEL ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Browser)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │  LicenseLedger       │  │  PDF Export  │  │  Excel Export     │   │
│  │  DetailPage          │  │  Utility     │  │  Utility          │   │
│  │  (React Component)   │  │  (ledgerExp) │  │  (ledgerExp)      │   │
│  └──────────┬───────────┘  └──────┬───────┘  └────────┬──────────┘   │
│             │                     │                    │              │
│             └─────────────────────┼────────────────────┘              │
│                                   │                                    │
│                    HTTP GET /api/license/<id>/ledger_detail/          │
│                                   ↓                                    │
│ ┌─────────────────────────────────────────────────────────────────┐  │
│ │ Canonical Dataset (API Response)                                │  │
│ ├─────────────────────────────────────────────────────────────────┤  │
│ │ • license_running_balance                                       │  │
│ │ • company_utilizations: {company_id → balance}                  │  │
│ │ • transactions: [{running_balance, is_commission, ...}]         │  │
│ │ • metadata                                                      │  │
│ └─────────────────────────────────────────────────────────────────┘  │
│             ↑              ↑                      ↑                    │
│             │              │                      │                    │
│             └──────────────┼──────────────────────┘                   │
│                            │                                          │
│     [NO RECALCULATION]     │     All data consumed as-is             │
│                            │     No balance math in frontend          │
│                            │                                          │
└────────────────────────────┼──────────────────────────────────────────┘
                             │ (HTTP)
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                           BACKEND (Django/DRF)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  API Endpoint: LicenseLedgerViewSet.ledger_detail()           │   │
│  ├────────────────────────────────────────────────────────────────┤   │
│  │  • Check authorization (license.view_ledger)                  │   │
│  │  • Call CanonicalLedgerService.build_dfia_ledger_dataset()    │   │
│  │  • Return Response(canonical_dataset)                         │   │
│  └────────────────────────────┬─────────────────────────────────┘   │
│                               │                                      │
│                    build_dfia_ledger_dataset()                       │
│                               ↓                                      │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  CanonicalLedgerService (NEW CLASS)                           │   │
│  ├────────────────────────────────────────────────────────────────┤   │
│  │  Responsibility:                                              │   │
│  │  • Fetch all trades for license (single query)                │   │
│  │  • Calculate license_running_balance (exclude COMMISSION)    │   │
│  │  • Calculate company_utilizations (independent per-company)  │   │
│  │  • Build immutable canonical dataset                          │   │
│  │                                                               │   │
│  │  Public Methods:                                              │   │
│  │  • build_dfia_ledger_dataset(license, company_id=None)       │   │
│  │  • build_incentive_ledger_dataset(license, company_id=None)  │   │
│  └────────┬─────────────────────────────────────────────────┬───┘   │
│           │                                                 │        │
│   (single query pass)                          (result dict)        │
│           ↓                                                 ↓        │
│  ┌────────────────────────┐                  ┌──────────────────┐  │
│  │  Database Query Layer  │                  │ Immutable Result  │  │
│  ├────────────────────────┤                  ├──────────────────┤  │
│  │ LicenseTrade.objects.  │                  │ • license_id     │  │
│  │   filter(...)          │                  │ • running_balance│  │
│  │   .prefetch_related() │                  │ • company_util[] │  │
│  │   .distinct()          │                  │ • transactions[] │  │
│  │   .order_by(...)       │                  │ • metadata       │  │
│  │                        │                  │                  │  │
│  │ RowDetails (debit)     │                  │ Returns: dict    │  │
│  │                        │                  │                  │  │
│  │ Company lookups        │                  │ Used by API      │  │
│  └────────────────────────┘                  │ Consumed by all  │  │
│                                              │ outputs          │  │
│                                              └──────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Supporting Services (Unchanged)                             │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │ • LicenseBalanceCalculator (available_balance calculation)   │  │
│  │ • RowDetails query layer (debit/credit tracking)             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## DATA FLOW DIAGRAM (Transaction Processing)

```
┌─ Start: License with ID 123 ─┐
│                              │
└──────────────┬───────────────┘
               │
               ↓
    ┌──────────────────────┐
    │ Fetch Trades (Step 1)│
    ├──────────────────────┤
    │ LicenseTrade         │
    │  .filter(            │
    │   license_id=123     │
    │  )                   │
    │  .prefetch_related   │
    │   (to_company,       │
    │    from_company)     │
    │  .order_by(          │
    │   invoice_date, id   │
    │  )                   │
    └──────────┬───────────┘
               │
               ↓
    ┌──────────────────────────┐
    │ Sort Transactions        │
    ├──────────────────────────┤
    │ Key: (date, id)          │
    │ Deterministic order      │
    │ Same final balance       │
    │ guaranteed regardless    │
    │ of display order         │
    └──────────┬───────────────┘
               │
               ↓
    ┌──────────────────────────┐
    │ Initialize State         │
    ├──────────────────────────┤
    │ running_balance = 0      │
    │ company_balances = {}    │
    │ result_txns = []         │
    └──────────┬───────────────┘
               │
               ↓
    ┌──────────────────────────┐
    │ Process Each Transaction │
    ├──────────────────────────┤
    │ FOR each trade:          │
    │  1. Compute amounts      │
    │  2. Check if commission  │
    │  3. Update running bal   │
    │     (EXCLUDE COMMISSION) │
    │  4. Update company bal   │
    │  5. Create row object    │
    │  6. Append to results    │
    │                          │
    │ KEY: If is_commission:   │
    │   • Add row (visible)    │
    │   • Don't update balance │
    │   • Mark is_commission=t │
    └──────────┬───────────────┘
               │
               ↓
    ┌──────────────────────────┐
    │ Build Company Utils (Step 2)
    ├──────────────────────────┤
    │ FOR each company_id:     │
    │   balance = SUM(         │
    │     txn.amount           │
    │     WHERE company_id     │
    │     AND NOT commission   │
    │   )                      │
    │                          │
    │ company_utilizations = { │
    │   A: 300.00,             │
    │   B: 250.00              │
    │ }                        │
    └──────────┬───────────────┘
               │
               ↓
    ┌──────────────────────────┐
    │ Build Metadata (Step 3)  │
    ├──────────────────────────┤
    │ Totals, counts, dates    │
    │ for summary section      │
    └──────────┬───────────────┘
               │
               ↓
    ┌──────────────────────────┐
    │ Return Canonical Dataset │
    ├──────────────────────────┤
    │ {                        │
    │   running_balance: X,    │
    │   company_utils: {...},  │
    │   transactions: [...],   │
    │   metadata: {...}        │
    │ }                        │
    └──────────┬───────────────┘
               │
               ↓ (JSON serialization)
               │
    ┌──────────────────────────┐
    │ HTTP Response 200 OK     │
    │ Content-Type: JSON       │
    └──────────────────────────┘
```

---

## MODULE RESPONSIBILITY MATRIX

| Module | Responsibility | Owns | Depends On |
|--------|---|---|---|
| **CanonicalLedgerService** | Calculate license balance (exclude COMMISSION) + company utilizations | Single source of truth | DB query layer, Decimal utils |
| **LicenseLedgerViewSet** | HTTP endpoint, authorization, routing | API contract | CanonicalLedgerService |
| **LicenseLedgerDetail.tsx** | Display ledger in UI | Screen rendering | API response (no recalc) |
| **ledgerExport.js (PDF)** | Format canonical data as PDF | PDF generation | API response (no recalc) |
| **ledgerExport.js (Excel)** | Format canonical data as Excel | Excel generation | API response (no recalc) |
| **LicenseBalanceCalculator** | Calculate available_balance (existing) | Financial position | DB query layer |
| **LicenseTrade** | ORM model (existing) | Database schema | None |
| **RowDetails** | BOE debit tracking (existing) | Debit/credit ledger | None |

---

## DEPENDENCY GRAPH

```
Frontend Layer:
├─ LicenseLedgerDetail.tsx → API (/ledger_detail/)
├─ ledgerExport.js (PDF) → API (/ledger_detail/)
└─ ledgerExport.js (Excel) → API (/ledger_detail/)

Backend Layer (API):
└─ LicenseLedgerViewSet.ledger_detail() 
   └─ CanonicalLedgerService.build_dfia_ledger_dataset()
      ├─ LicenseTrade.objects.filter(...).prefetch_related(...)
      ├─ LicenseBalanceCalculator (for available_balance)
      └─ Company lookup (FK relationships)

Data Layer:
├─ LicenseTrade (ORM model)
├─ LicenseTradeLine (ORM model)
├─ RowDetails (ORM model)
├─ Company (ORM model)
└─ License (ORM model)

Utilities:
├─ Decimal (Python stdlib)
├─ ROUND_HALF_UP (decimal utils)
└─ Date utilities
```

---

## CURRENT vs TARGET COMPARISON

### Current Architecture (Problem State)

```
Database
  ↓ (query)
  
LicenseTrade → build_dfia_ledger_detail()
  ↓ (calculate license-wide balance, include COMMISSION)
  
API Response
  ├─ balance: [license-wide, COMMISSION included]
  ├─ transactions: [...]
  └─ (NO company_utilizations)
  
Frontend (3 Independent Recalculations)
├─ Screen: Use balance as-is (COMMISSION included)
├─ PDF: Recalculate per-company (COMMISSION excluded)
└─ Excel: Recalculate per-company (COMMISSION excluded)

Result: Three different balances ✗
```

### Target Architecture (Solution State)

```
Database
  ↓ (single query)
  
CanonicalLedgerService.build_dfia_ledger_dataset()
  ├─ Calculate license_running_balance (exclude COMMISSION) ✓
  ├─ Calculate company_utilizations (independent per-company) ✓
  └─ Build immutable dataset
  
API Response (Canonical)
  ├─ license_running_balance: [authoritative]
  ├─ company_utilizations: [{company_id → balance}]
  └─ transactions: [with running_balance, is_commission]
  
Frontend (Zero Recalculation)
├─ Screen: Consume and display (no math)
├─ PDF: Consume and format (no math)
└─ Excel: Consume and format (no math)

Result: Identical balances everywhere ✓
```

---

## CLASS STRUCTURE (Backend)

### CanonicalLedgerService (NEW)

```python
class CanonicalLedgerService:
    """
    Canonical ledger calculation service.
    
    Single source of truth for:
    - License running balance (excludes COMMISSION)
    - Company utilizations (independent per-company)
    - Transaction list with ordering and markers
    """
    
    @staticmethod
    def build_dfia_ledger_dataset(
        license: LicenseDetailsModel,
        company_id: Optional[int] = None
    ) -> dict:
        """
        Build canonical DFIA ledger dataset.
        
        Args:
            license: License instance
            company_id: Optional company filter
        
        Returns:
            Canonical dataset dict (see LEDGER_CANONICAL_DATASET.md)
        """
        # Step 1: Fetch and sort transactions
        trades = self._fetch_and_sort_trades(license, company_id)
        
        # Step 2: Initialize state
        running_balance = Decimal('0.00')
        company_balances = {}
        result_transactions = []
        
        # Step 3: Process each transaction
        for trade in trades:
            balance_updated = self._process_transaction(
                trade, running_balance, company_balances, result_transactions
            )
            running_balance = balance_updated
        
        # Step 4: Build company utilizations
        company_utilizations = self._build_company_utilizations(
            company_balances
        )
        
        # Step 5: Build metadata
        metadata = self._build_metadata(result_transactions)
        
        # Step 6: Return canonical dataset
        return {
            'license_id': license.id,
            'license_running_balance': str(running_balance),
            'company_utilizations': {
                str(k): str(v) for k, v in company_utilizations.items()
            },
            'transactions': result_transactions,
            'metadata': metadata,
        }
    
    @staticmethod
    def _process_transaction(
        trade, running_balance, company_balances, result_transactions
    ) -> Decimal:
        """Process single transaction, return updated running balance."""
        # Compute amounts
        total_cif = trade.total_cif_usd
        is_commission = trade.direction.startswith('COMMISSION')
        
        # Update running balance (EXCLUDE COMMISSION)
        if not is_commission:
            if trade.direction in ['PURCHASE', 'COMMISSION_PURCHASE']:
                running_balance += total_cif
            elif trade.direction in ['SALE', 'COMMISSION_SALE']:
                running_balance -= total_cif
        
        # Update company balance (EXCLUDE COMMISSION)
        if not is_commission:
            company_id = trade.to_company_id if ... else trade.from_company_id
            if company_id:
                company_balances[company_id] = company_balances.get(
                    company_id, Decimal('0.00')
                ) + (total_cif if ... else -total_cif)
        
        # Build transaction row
        result_transactions.append({
            'id': f"trade_{trade.id}",
            'trade_id': trade.id,
            'date': trade.invoice_date.isoformat(),
            'type': 'COMMISSION' if is_commission else trade.direction,
            'is_commission': is_commission,
            'running_balance': str(quantize_2dp(running_balance)),
            # ... other fields
        })
        
        return running_balance
```

---

## DATA FLOW WALKTHROUGH (Example License)

**Input License:** L1 with 3 trades

```
Trade 1: PURCHASE, Company A, 500 CIF
Trade 2: COMMISSION, Company B, 100 CIF
Trade 3: SALE, Company A, 200 CIF
Opening Balance: 1000 CIF
```

**Processing:**

```
State:  running_balance = 1000 (opening)
        company_balances = {}
        result_txns = []

Trade 1 (PURCHASE, A, 500):
  not is_commission → TRUE, process
  running_balance = 1000 + 500 = 1500
  company_balances[A] = 0 + 500 = 500
  result_txns.append({running_balance: 1500, is_commission: false, ...})

Trade 2 (COMMISSION, B, 100):
  is_commission → TRUE, skip balance update
  running_balance = 1500 (UNCHANGED)
  company_balances[B] = NOT UPDATED
  result_txns.append({running_balance: 1500, is_commission: true, ...})

Trade 3 (SALE, A, 200):
  not is_commission → TRUE, process
  running_balance = 1500 - 200 = 1300
  company_balances[A] = 500 - 200 = 300
  result_txns.append({running_balance: 1300, is_commission: false, ...})

Final State:
  running_balance = 1300 ✓ (COMMISSION excluded)
  company_balances = {A: 300, B: 0}
  company_utilizations = {A: 300, B: 0}
```

**API Response:**

```json
{
  "license_running_balance": "1300.00",
  "company_utilizations": {"A": "300.00", "B": "0.00"},
  "transactions": [
    {running_balance: "1500.00", is_commission: false},
    {running_balance: "1500.00", is_commission: true},
    {running_balance: "1300.00", is_commission: false}
  ]
}
```

**Frontend (Screen):**

```
License Running Balance: $1,300.00 ✓ (from API)
Company A Utilization: $300.00 ✓ (from API)
Company B Utilization: $0.00 ✓ (from API)
```

**Frontend (PDF):**

```
Company A section:
  PURCHASE: $500.00, Balance: $500.00 ✓ (from API, no recalc)
  SALE: $200.00, Balance: $300.00 ✓ (from API, no recalc)
  Subtotal: $300.00 ✓ (from company_utilizations, no recalc)

Company B section:
  COMMISSION: $100.00, Balance: N/A [Excluded] ✓ (from API, marked)
  Subtotal: $0.00 ✓ (from company_utilizations, no recalc)
```

**Verification:**

```
Screen balance: 1300 ✓
PDF license balance: 1300 ✓
PDF Company A: 300 ✓
PDF Company B: 0 ✓
Excel: Same as PDF ✓
All Identical ✓
```

---

## INTEGRATION POINTS

### With LicenseBalanceCalculator

```python
# Current: Available balance calculation (unchanged)
available_balance = LicenseBalanceCalculator.calculate_financial_balance(license)

# Used in: API response to show current license balance
# Note: This is separate from ledger running balance
#       (may differ if there are pending BOE debits, etc.)
```

### With Authorization/Permissions

```python
# Current: Check user has license.view_ledger permission
# Location: LicenseLedgerViewSet.permission_classes
# No changes: Authorization boundary unchanged
```

### With Caching

```python
# Current: available_balance cached via balance_calculator
# New: Canonical dataset NOT cached initially (fresh per request)
# Future: Cache canonical dataset if needed (Phase 4+)
```

---

## FAILURE MODES & RECOVERY

| Failure | Cause | Impact | Recovery |
|---------|-------|--------|----------|
| Database connection timeout | DB unavailable | API returns 500 | Retry, fallback to cache |
| Calculation error | Invalid transaction data | API returns 500 | Log error, fallback to old builder |
| COMMISSION counting error | Bug in is_commission check | Wrong balance | Rollback via feature flag |
| Decimal overflow | Very large amounts | Capped at max Decimal | Log warning, proceed |
| Missing company | Orphaned transaction | Unknown company in utilization | Log warning, include as "unknown" |

---

**Document Version:** 1.0  
**Date:** 2026-08-10  
**Status:** ARCHITECTURE SPECIFICATION
