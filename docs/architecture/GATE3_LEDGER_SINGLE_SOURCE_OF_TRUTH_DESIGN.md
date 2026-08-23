# GATE 3: Ledger Single Source of Truth Design

**Status:** GATE 3 ARCHITECTURE DESIGN — Do NOT implement. For approval only.

**Purpose:** Apply the system-wide Single Source of Truth architecture (GATE3_SINGLE_SOURCE_OF_TRUTH_CALCULATIONS.md) specifically to the License Ledger module to establish authoritative calculations and eliminate P0 duplicate.

---

## Executive Summary

The License Ledger P0 defect (three incompatible running-balance implementations) proves the need for a canonical authoritative backend calculation. This document defines:

1. **Authoritative Ledger Service** — Single calculation owner for running balance
2. **Transaction Classification** — Central definition of business semantics
3. **API Contract** — What the ledger endpoint returns
4. **Consumer Pattern** — How all outputs (screen, PDF, Excel) consume canonical result

---

## PART 1: Authoritative Ledger Service

### Class Definition

**Location (proposed):** `backend/apps/license/services/canonical_ledger.py`

**Responsibility:** Single owner for all ledger calculations

```python
class CanonicalLedgerService:
    """
    Authoritative service for License Ledger calculations.
    
    SINGLE RESPONSIBILITY: Compute the license-wide running balance
    in ledger order (by date, then ID).
    
    No calculation is performed outside this class; all consumers
    read the result, never re-derive.
    """
    
    @staticmethod
    def build_ledger_rows(
        license_id: int,
        include_hidden: bool = False
    ) -> List[LedgerRow]:
        """
        Build canonical ledger rows with running balance.
        
        Args:
            license_id: License to calculate
            include_hidden: Include hidden/previous-owner BOEs (audit view only)
        
        Returns:
            List of LedgerRow(s) with running_balance field
        """
        # Fetch all transactions for license, ordered by date then ID
        transactions = LedgerTransaction.objects.filter(
            license_id=license_id
        ).order_by("transaction_date", "id")
        
        # Calculate running balance
        opening_balance = LicenseBalanceCalculator.calculate_credit(license_id)
        current_balance = opening_balance
        rows = []
        
        for txn in transactions:
            # Apply transaction impact (based on TRANSACTION_RULES)
            impact = TRANSACTION_RULES[txn.type]["balance_impact"](txn)
            current_balance += impact
            
            # Create row with running balance
            row = LedgerRow(
                transaction_id=txn.id,
                transaction_type=txn.type,
                transaction_date=txn.transaction_date,
                company=txn.company,
                amount=txn.amount,
                running_balance=quantize_2dp(current_balance),
                # ... other fields
            )
            rows.append(row)
        
        return rows
    
    @staticmethod
    def get_company_attribution(license_id: int) -> List[CompanyUtilization]:
        """
        Get per-company breakdown of balance utilization.
        
        Returns a list grouping the running balance by company.
        (Derived from canonical running balance, not independent calculation.)
        """
        # Get canonical rows
        rows = CanonicalLedgerService.build_ledger_rows(license_id)
        
        # Group by company and compute company-specific utilization
        company_utilizations = []
        for company, company_rows in groupby(rows, key=lambda r: r.company):
            total_balance = sum(r.amount for r in company_rows)
            company_utilizations.append(CompanyUtilization(
                company=company,
                total_amount=total_balance,
                row_count=len(list(company_rows))
            ))
        
        return company_utilizations
```

### Transaction Semantics (Central Definition)

**Location:** `backend/apps/license/constants.py` (new section)

```python
# SINGLE SOURCE OF TRUTH for transaction business semantics
TRANSACTION_RULES = {
    "PURCHASE": {
        "affects_balance": True,
        "balance_direction": "CREDIT",      # Adds to available
        "affects_planning": False,
        "affects_allocation": False,
        "visible_in_ledger": True,
        "commission_excluded": False,
        "balance_impact": lambda txn: txn.amount,
    },
    
    "SALE": {
        "affects_balance": True,
        "balance_direction": "DEBIT",       # Removes from available
        "affects_planning": False,
        "affects_allocation": False,
        "visible_in_ledger": True,
        "commission_excluded": False,
        "balance_impact": lambda txn: -txn.amount,
    },
    
    "COMMISSION_SALE": {
        "affects_balance": True,            # ← GATE 3 B4: Business decision
        "balance_direction": "DEBIT",
        "affects_planning": False,
        "affects_allocation": False,
        "visible_in_ledger": True,
        "commission_excluded": False,       # Will change if B4=NO
        "balance_impact": lambda txn: -txn.amount if COMMISSION_INCLUDED else Decimal("0"),
    },
    
    "BOE_DEBIT": {
        "affects_balance": True,
        "balance_direction": "DEBIT",
        "affects_planning": False,
        "affects_allocation": False,
        "visible_in_ledger": True,
        "commission_excluded": False,
        "balance_impact": lambda txn: -txn.amount,
    },
    
    "ALLOTMENT": {
        "affects_balance": True,
        "balance_direction": "DEBIT",
        "affects_planning": False,
        "affects_allocation": True,
        "visible_in_ledger": True,
        "commission_excluded": False,
        "balance_impact": lambda txn: -txn.amount,
    },
    
    # ... etc for all transaction types
}

# Verification: Every transaction type in the system must be defined here
# If a transaction type is missing, it's a configuration error
def validate_transaction_rules():
    """Ensure all transaction types in DB are defined in TRANSACTION_RULES."""
    defined_types = set(TRANSACTION_RULES.keys())
    db_types = set(
        LedgerTransaction.objects.values_list("type", flat=True).distinct()
    )
    undefined = db_types - defined_types
    if undefined:
        raise ConfigurationError(f"Transaction types undefined: {undefined}")
```

---

## PART 2: API Contract (What Ledger Endpoint Returns)

### Response Structure

**Endpoint:** `GET /license/{id}/ledger_detail/`

**Response Schema:**

```json
{
  "license_id": 123,
  "license_number": "0123456789",
  "opening_balance": "50000.00",
  "closing_balance": "10000.00",
  "company_count": 3,
  
  "ledger_rows": [
    {
      "id": 1001,
      "type": "PURCHASE",
      "transaction_date": "2026-01-15",
      "company": "ABC Importer Inc.",
      "description": "Direct import - Glass containers",
      "quantity": "100.00",
      "quantity_unit": "KG",
      "amount": "50000.00",
      "amount_currency": "USD",
      
      "running_balance": "50000.00",
      "running_balance_currency": "USD",
      "balance_after_transaction": "50000.00",
      
      "status": "POSTED"
    },
    {
      "id": 2001,
      "type": "BOE_DEBIT",
      "transaction_date": "2026-02-10",
      "company": "ABC Importer Inc.",
      "description": "BOE 6756437 - Glass debit",
      "quantity": "50.00",
      "quantity_unit": "KG",
      "amount": "25000.00",
      "amount_currency": "USD",
      
      "running_balance": "25000.00",
      "running_balance_currency": "USD",
      "balance_after_transaction": "25000.00",
      
      "status": "MATCHED"
    }
  ],
  
  "company_utilizations": [
    {
      "company": "ABC Importer Inc.",
      "total_utilized": "25000.00",
      "percentage_of_balance": 50.0,
      "transaction_count": 5
    },
    {
      "company": "XYZ Trader Ltd.",
      "total_utilized": "15000.00",
      "percentage_of_balance": 30.0,
      "transaction_count": 3
    }
  ]
}
```

### Backward Compatibility Note

This response CHANGES from current ledger_pdf.py output. Migration plan includes:
- Feature flag: `LEDGER_CANONICAL_ENGINE`
- 30-day overlap period where both old and new coexist
- Gradual migration of consumers to new response

---

## PART 3: No Duplicate Calculations (Consumption Pattern)

### BEFORE (Current — P0 Defect)

```
Backend:     ledger_pdf.py:1067 calculates running balance
                ↓
API:         Returns balance in response
                ↓
             ┌────────────────────────────────────┐
             │                                    │
          LicensesTable.tsx:616               LicenseLedgerDetail.tsx:339
          (reads backend balance)             (ignores backend, recalculates)
             │                                    │
          Correct ✓                         Wrong ✗ (different convention)
                                               ↓
                                        PDF/Excel also recalculate
```

### AFTER (Proposed)

```
CanonicalLedgerService                     (SINGLE source)
            ↓
API Response (canonical running_balance)
            ↓
        ┌───────────────────────────┐
        │                           │
  LicensesTable.tsx          LicenseLedgerDetail.tsx
  (reads backend)            (reads backend)
        │                           │
     Correct ✓                  Correct ✓
                  
  PDF/Excel
  (read from API, format only, NO recalculation)
```

### Frontend Implementation Rule

**CRITICAL:** No screen or export may recalculate running balance.

```typescript
// CORRECT: Read from API
const { running_balance } = ledgerRow;  // ← From backend
displayBalance(running_balance);         // ← Format only

// WRONG: Frontend recalculation
let balance = 0;
for (const row of rows) {
    balance += row.amount;              // ← FORBIDDEN
}
```

---

## PART 4: Integration with Other Domains

### Planning Integration

**Ledger provides:** License Running Balance

**Planning uses for:** Computing Available for Planning

```
CALC-L-001 (License Running Balance) ← CanonicalLedgerService
    ↓
CALC-P-005 (Available for Planning) ← Item Pivot
    ├─ Available Qty - Planned Qty
    └─ Uses CALC-L-001 to ensure fresh balance
```

### Allocation Integration

**Ledger provides:** License Running Balance

**Allocation uses for:** Validation (can allocate if balance > 0)

```
CALC-L-001 (License Running Balance) ← CanonicalLedgerService
    ↓
Allocation validation ← Allotment Service
    └─ Check: allocation_amount <= CALC-L-001
```

### BOE Integration

**Ledger provides:** Transaction classification rules

**BOE uses for:** Determining balance impact

```
TRANSACTION_RULES[txn.type] ← Central definition
    ↓
Used by BOE service when calculating impact
```

---

## PART 5: Business Decision Gate (B2)

### Running Balance Convention (BLOCKING FOR PHASE 3B)

**Decision required:**

- **Option A (Backend current):** License-wide, date-ordered, commissions=debit
- **Option B (Frontend current):** Per-company, type-ordered, commissions=excluded
- **Recommendation:** Option A (backend current) — simpler, deterministic

**This document assumes Option A.** If business chooses Option B, Ledger implementation will differ.

---

## PART 6: Feature Flag Rollout

### Phase 1: Development (Week 1-2)
- Implement CanonicalLedgerService
- Write parity tests (GATE3_CALCULATION_PARITY_FRAMEWORK.md)
- Pass all golden dataset scenarios

### Phase 2: Testing (Week 3)
- Run parity tests on production-like subset
- Domain expert spot-checks
- Acceptance gate

### Phase 3: Shadow Mode (Week 4)
- Deploy with feature flag: `LEDGER_CANONICAL_ENGINE=False` (default)
- New code runs in background, logs differences
- Monitor for divergences

### Phase 4: Gradual Rollout (Week 5-6)
- Feature flag: `LEDGER_CANONICAL_ENGINE=True` (10% of users)
- Monitor for errors
- Ramp up to 50%, then 100%

### Phase 5: Cleanup (Week 7)
- Remove legacy ledger_pdf calculation code
- Remove feature flag
- Finalize new API contract

---

## Transaction Type Classification (Reference)

| Type | Source Module | Balance Impact | Visible | Commission? | Used in Reports |
|------|---|---|---|---|---|
| PURCHASE | Import | CREDIT | YES | NO | YES |
| SALE | Trade | DEBIT | YES | NO | YES |
| COMMISSION_SALE | Trade | DEBIT (B4) | YES | YES | YES |
| BOE_DEBIT | BOE | DEBIT | YES | NO | YES |
| BOE_UTILIZATION_PENDING | BOE | NONE (pending) | YES | NO | YES |
| ALLOTMENT | Allotment | DEBIT | YES | NO | YES |
| OPENING | System | NONE (set) | NO | NO | YES |

---

## Version and Status

- **Version 1.0** — Gate 3 Architecture Design, 2026-08-10
- **Blocking Issue:** B2 (running balance convention) — business decision required
- **Next:** Phase 3B (implement if B2 approved)
- **Test Framework:** GATE3_CALCULATION_PARITY_FRAMEWORK.md (7 golden scenarios)
- **Integration Points:** Planning, Allocation, BOE, Reconciliation
