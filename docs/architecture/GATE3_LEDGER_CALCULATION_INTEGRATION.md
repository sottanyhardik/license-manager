# GATE 3: Ledger Calculation Integration

**Status:** GATE 3 ARCHITECTURE DESIGN — Do NOT implement. For approval only.

**Purpose:** Define exactly how Ledger calculations integrate with Planning, Allocation, BOE, Reconciliation, and Reporting domains.

---

## Integration Principle

**Ledger is AUTHORITATIVE for:** License Running Balance (CALC-L-001)

**Ledger is DERIVED FROM:** License Balance Calculator (CALC-L-008, CALC-L-003, etc.)

**Ledger integrates with (direction of dependency):**

```
LICENSE BALANCE CALCULATOR (L-008, L-003, L-Debit)
    ↑
    └─→ CANONICAL LEDGER SERVICE (calculates running balance per row)
            ↓↓↓
    ┌───────┼───────┬────────────┬──────────────┐
    ↓       ↓       ↓            ↓              ↓
 PLANNING  ALLOC  BOE-INVOICE  RECONCIL     REPORTING
          
API Response (running_balance in each row)
    ↓
    └─→ LicensesTable.tsx
    └─→ LicenseLedgerDetail.tsx
    └─→ PDF Export (format only)
    └─→ Excel Export (format only)
```

---

## Planning Domain Integration

### What Planning Gets from Ledger

**Dependency:** Planning reads Ledger's License Running Balance (CALC-L-001)

```
CALC-L-001 (License Running Balance) 
    ↓
CALC-P-005 (Available for Planning)
    │
    ├─ Formula: CALC-L-001 - SUM(planned quantities by item)
    │
    └─ Result: Qty available to allocate per item
```

### Contract

| Aspect | Definition | Responsibility |
|--------|---|---|
| **What** | License running balance | Ledger (CanonicalLedgerService) |
| **When** | On demand, real-time | Planning service reads latest |
| **How** | Via service method call | `LicenseBalanceCalculator.calculate_financial_balance_for_licenses` |
| **Frequency** | Every time available qty is calculated | Item Pivot report generation |
| **Cache** | None (fresh calculation) | Ledger can cache if needed |
| **Stale risk** | YES — if balance changes between page load and allocation attempt | Allocation validation rechecks at submission time |

### Implementation

```python
# Planning service (item_pivot_report.py)
def _build_license_row(license_obj):
    """Calculate available qty per item."""
    
    # Get fresh balance from Ledger
    license_balance = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(
        [license_obj.id]
    )[license_obj.id]
    
    # For each item on license
    for item in license_obj.import_items.all():
        # Calculate planned qty from norm
        planned_qty = e1_plan.calculate_planned_qty(item)
        
        # Available = Balance (in item's unit) - Planned
        available_qty = (license_balance / item_unit_price) - planned_qty
        
        row_data = {
            "item_id": item.id,
            "available_qty": available_qty,
            "planned_qty": planned_qty,
            "balance_basis": license_balance  # ← Traceability
        }
        yield row_data
```

### Edge Case: Concurrent Allocation

**Scenario:** User loads Item Pivot (balance = 1000), then starts allocation. Another user allocates 800. First user tries to allocate 700 (thinks 1000 still available).

**Current behavior:** Allotment service rechecks balance at submission time.

**Ledger integration:** No change — Ledger returns fresh balance every time, so allocation always checks latest.

---

## Allocation Domain Integration

### What Allocation Gets from Ledger

**Dependency:** Allocation reads Ledger's License Running Balance

```
CALC-L-001 (License Running Balance) 
    ↓
Allocation Validation Service
    │
    └─ Check: allocation_amount <= CALC-L-001
```

### Contract

| Aspect | Definition | Responsibility |
|--------|---|---|
| **What** | License running balance | Ledger (CanonicalLedgerService) |
| **When** | At allocation submission | Validation service |
| **How** | Via service method call | Same as Planning |
| **Frequency** | Once per allocation attempt | Allotment views |
| **Determinism** | Must be identical if called twice same second | ID-based ordering ensures this |
| **Failure mode** | Reject allocation if balance insufficient | Error message to user |

### Implementation

```python
# Allocation service (allocation_service.py)
def validate_allocation_amount(license_id: int, allocation_amount: Decimal) -> bool:
    """Check if license has sufficient balance."""
    
    # Get current balance
    current_balance = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(
        [license_id]
    )[license_id]
    
    # Validate
    if allocation_amount > current_balance:
        raise AllocationError(
            f"Allocation {allocation_amount} exceeds balance {current_balance}"
        )
    return True
```

---

## BOE Integration

### What BOE Gets from Ledger

**Dependency:** BOE reads Transaction Semantics (TRANSACTION_RULES)

```
TRANSACTION_RULES[boe.type]
    ↓
BOE Service
    │
    └─ Use balance_impact rule to affect license balance
```

### Contract

| Aspect | Definition | Responsibility |
|--------|---|---|
| **What** | Transaction type → balance impact mapping | Ledger/Core (TRANSACTION_RULES) |
| **When** | When BOE is created/updated | BOE service uses rules |
| **How** | Via central constants | `from apps.core.constants import TRANSACTION_RULES` |
| **Frequency** | Whenever BOE balance impact is needed | BOE creation, reporting |
| **Source of truth** | TRANSACTION_RULES (single definition) | No hardcoding in BOE service |

### Implementation

```python
# BOE service (boe_service.py)
def update_boe_impact(boe_obj):
    """Update BOE's impact on license balance."""
    
    # Get rules
    rules = TRANSACTION_RULES.get(boe_obj.type)
    if not rules:
        raise ConfigurationError(f"Transaction type {boe_obj.type} not configured")
    
    # Apply rules
    if rules["affects_balance"]:
        # Mark license for balance recalculation
        invalidate_balance_cache(boe_obj.license_id)
```

### Edge Case: Missing Transaction Type

**Scenario:** New transaction type is added to database but TRANSACTION_RULES isn't updated.

**Mitigation:** 
1. Add validation at startup: `validate_transaction_rules()` (see GATE3_LEDGER_SINGLE_SOURCE_OF_TRUTH_DESIGN.md)
2. BOE service raises error if type not in rules (fail fast)
3. Configuration error in monitoring

---

## BOE-Invoice Reconciliation Integration

### What Reconciliation Gets from Ledger

**Dependency:** Reconciliation reads Transaction Classification

```
TRANSACTION_RULES[txn.type]["visible_in_ledger"]
    ↓
Reconciliation Service
    │
    └─ Use to determine if transaction should be included in reconciliation
```

### Contract

| Aspect | Definition | Responsibility |
|--------|---|---|
| **What** | Which transactions participate in BOE-Invoice matching | TRANSACTION_RULES |
| **When** | During reconciliation match logic | Reconciliation service |
| **How** | Check `TRANSACTION_RULES[type]["visible_in_ledger"]` | Filter when building reconciliation view |
| **Frequency** | Every reconciliation report generation | Per-request |

### Implementation

```python
# Reconciliation service
def get_reconciliation_rows(license_id: int):
    """Get rows eligible for BOE-Invoice matching."""
    
    # Get all transactions
    rows = RowDetails.objects.filter(
        sr_number__license_id=license_id
    )
    
    # Filter to reconciliation-eligible types
    eligible = []
    for row in rows:
        rules = TRANSACTION_RULES.get(row.transaction_type)
        if rules and rules.get("visible_in_ledger"):
            eligible.append(row)
    
    return eligible
```

---

## Reporting Integration

### What Reports Get from Ledger

**Dependency:** All reports read Ledger's running balance, NOT separate calculations

```
CALC-L-001 (License Running Balance via CanonicalLedgerService)
    ↓
    ├─→ Item Pivot Report
    │   └─ Uses for "Balance CIF" column header
    │
    ├─→ License Balance Ledger Report
    │   └─ Uses for period-end snapshot
    │
    ├─→ Financial Ledger (PDF/Excel)
    │   └─ Uses for running balance in detail rows
    │
    └─→ Dashboard
        └─ Uses for summary cards
```

### Contract (Universal Rule for All Reports)

| Aspect | Definition | Responsibility |
|--------|---|---|
| **What** | License running balance | Ledger (CanonicalLedgerService) |
| **When** | At report generation | Report service fetches via API |
| **How** | Call CanonicalLedgerService, NOT recalculate | Service layer only |
| **Frequency** | Once per report, unless filtered by date/time | Per-request |
| **Derivation** | Reports may group/aggregate, NOT recalculate balance | Only formatting and grouping allowed |
| **Verification** | Golden dataset test: report balance matches API balance | Regression test per report |

### Implementation Rule

**For every report:**

```python
# CORRECT
def generate_license_report(license_id):
    # Get canonical balance from ledger
    ledger_rows = CanonicalLedgerService.build_ledger_rows(license_id)
    
    # Use balance from ledger (no recalculation)
    for row in ledger_rows:
        report.append({
            "transaction": row.description,
            "balance": row.running_balance,  # ← Read, don't calculate
        })
    
    return report

# WRONG
def generate_license_report(license_id):
    # DON'T recalculate
    balance = 0
    for txn in get_transactions(license_id):
        balance += calculate_impact(txn)  # ← FORBIDDEN
    
    # This might differ from ledger!
```

---

## Cross-Domain Consistency Rules

### Rule 1: Single Balance Source
Every screen, API response, PDF, Excel file must show the same License Running Balance for the same license on the same date.

**Enforcement:** All read from CanonicalLedgerService.

### Rule 2: Transaction Type Authority
Every module using transaction type rules must reference TRANSACTION_RULES, never hardcode.

**Enforcement:** Code review, linter rule.

### Rule 3: No Independent Balance Recalculation
No module may independently recalculate License Running Balance (CALC-L-001).

**Exception:** Only the one CanonicalLedgerService method.

**Enforcement:** Grep for "running" or "balance" + "for ... in", flags as potential violation.

### Rule 4: Deterministic Ordering
All calculations of running balance across modules must order transactions identically (by date, then ID).

**Enforcement:** Shared code (CanonicalLedgerService) enforces this once.

---

## Integration Testing Strategy

### Parity Tests (Per GATE3_CALCULATION_PARITY_FRAMEWORK.md)

Every integration must pass parity tests on golden dataset:

```python
def test_planning_reads_fresh_balance():
    """Planning gets fresh balance from Ledger, not stale."""
    # Setup: Create license, add purchase, generate Item Pivot
    license = create_license_with_purchase(cif=1000)
    
    # Get available qty (uses balance from ledger)
    available1 = get_available_qty(license)
    
    # Add another purchase (increases balance)
    add_purchase(license, cif=500)
    
    # Get available qty again
    available2 = get_available_qty(license)
    
    # Must reflect new balance
    assert available2 > available1

def test_allocation_uses_fresh_balance():
    """Allocation validation uses fresh balance."""
    license = create_license(balance=1000)
    
    # Allocation should succeed
    assert allocate(license, amount=500) == OK
    
    # Allocation should fail if exceeds balance
    assert allocate(license, amount=1500) == ERROR

def test_report_balance_matches_api():
    """Report balance column matches API running_balance field."""
    license = create_license_with_transactions()
    
    # Get API response
    api_response = client.get(f"/license/{license.id}/ledger_detail/")
    api_balance = api_response.json()["ledger_rows"][0]["running_balance"]
    
    # Generate report
    report = generate_license_report(license.id)
    report_balance = report["rows"][0]["balance"]
    
    # Must match
    assert api_balance == report_balance
```

### Integration Regression Tests

For each domain integration, add regression test:

```python
# In each domain's test file

def test_planning_avail_qty_uses_ledger_balance():
    """Verify Item Pivot uses Ledger's balance."""
    # Setup
    license = create_license(purchase=1000)
    
    # Generate report
    report = item_pivot_report.generate_report(license_id=license.id)
    
    # Get balance from ledger (separate call)
    ledger_balance = CanonicalLedgerService.get_balance(license.id)
    
    # Verify report used ledger balance
    assert report["balance_basis"] == ledger_balance
```

---

## Version and Status

- **Version 1.0** — Gate 3 Architecture Design, 2026-08-10
- **Updated by:** Solutions Architect
- **Integration Points:** Planning, Allocation, BOE, Reconciliation, Reporting
- **Key Rule:** All read from CanonicalLedgerService, none recalculate
- **Test Framework:** Parity tests + integration regression tests
- **Next:** Phase 4 (implement with integration tests)
