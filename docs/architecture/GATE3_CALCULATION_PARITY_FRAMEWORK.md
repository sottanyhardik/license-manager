# GATE 3: Calculation Parity Framework

**Status:** GATE 3 ARCHITECTURE DESIGN — Do NOT implement. For approval only.

**Purpose:** Define the standard test methodology for verifying that a new/refactored calculation produces identical results to the old one (within acceptable tolerances).

**Critical Use:** Before activating any new calculation logic (especially CALC-L-001 Running Balance), run dual-calculation parity tests on a golden dataset.

---

## The Three Levels of Parity Testing

```
             Golden Input Data
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
    Old Calc   New Calc    Reference
    (Legacy)   (Candidate) (Expected)
        │          │            │
        └──────────┼────────────┘
                   │
                   ▼
          Comparison Engine
                   │
      ┌────────────┼────────────┐
      ▼            ▼            ▼
   IDENTICAL   EXPECTED       SEMANTIC
   (Good ✓)    CHANGE         DIFFERENCE
              (Review)        (Blocker ✗)
                              
```

---

## Level 1: Parallel Dual-Run Test

### Purpose
Run both old and new calculation on the same input dataset, capture all results.

### Setup

```python
class CalculationParityTest:
    """Test framework for verifying calculation migration."""
    
    def __init__(self, license_id: int):
        self.license_id = license_id
        self.old_results = None
        self.new_results = None
        self.differences = []
    
    def run_old_calculation(self):
        """Run legacy calculation (may be copied code, or service method)."""
        # If old logic is in a service: call the service
        from apps.license.services.balance_calculator_legacy import LegacyBalanceCalculator
        self.old_results = LegacyBalanceCalculator.calculate_balance(self.license_id)
    
    def run_new_calculation(self):
        """Run new/refactored calculation."""
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        self.new_results = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(
            [self.license_id]
        )
    
    def compare(self) -> List[Difference]:
        """Compare results and classify differences."""
        if isinstance(self.old_results, dict) and isinstance(self.new_results, dict):
            # Compare dictionaries (likely per-license results)
            return self._compare_dicts(self.old_results, self.new_results)
        else:
            # Compare scalar values
            return self._compare_scalars(self.old_results, self.new_results)
```

### Golden Dataset

**What it is:** A fixed set of licenses with known transactions, used for all parity tests.

**Where it lives:** `backend/apps/license/tests/golden_data/`

**Example:**

```python
# File: backend/apps/license/tests/golden_data/license_6789_ledger.json
{
  "license_id": 6789,
  "license_number": "0123456789",
  "export_items": [
    {
      "id": 1001,
      "cif_fc": "1000.00",
      "date": "2026-01-15"
    }
  ],
  "boe_debits": [
    {
      "id": 2001,
      "bill_of_entry_id": 5001,
      "cif_fc": "300.00",
      "date": "2026-02-01"
    },
    {
      "id": 2002,
      "bill_of_entry_id": 5001,
      "cif_fc": "200.00",
      "date": "2026-02-05"
    }
  ],
  "commissions": [
    {
      "id": 3001,
      "type": "COMMISSION_SALE",
      "amount": "50.00",
      "date": "2026-02-10"
    }
  ],
  "expected": {
    "opening_balance": "1000.00",
    "final_balance": "450.00",  # 1000 - 300 - 200 - 50
    "running_balances": [
      {"txn_id": 2001, "balance": "700.00"},
      {"txn_id": 2002, "balance": "500.00"},
      {"txn_id": 3001, "balance": "450.00"}
    ]
  }
}
```

### Test Execution

```python
def test_balance_migration_parity():
    """Verify new calculator produces identical results to old."""
    test = CalculationParityTest(license_id=6789)
    
    # Run both
    test.run_old_calculation()
    test.run_new_calculation()
    
    # Compare
    differences = test.compare()
    
    # Assert no unexpected differences
    unexpected = [d for d in differences if d.classification == "SEMANTIC_DIFFERENCE"]
    assert len(unexpected) == 0, f"Semantic differences found: {unexpected}"
```

---

## Level 2: Difference Classification

### Difference Class

```python
class Difference:
    """Represents a single difference between old and new results."""
    
    def __init__(
        self,
        path: str,             # e.g., "licenses[123].balance"
        old_value: Any,
        new_value: Any,
        classification: str,   # See below
        acceptable: bool,
        reason: str = ""
    ):
        self.path = path
        self.old_value = old_value
        self.new_value = new_value
        self.classification = classification
        self.acceptable = acceptable
        self.reason = reason
```

### Classification Types

#### Type 1: IDENTICAL ✓
```python
old_value = Decimal("1000.50")
new_value = Decimal("1000.50")
classification = "IDENTICAL"
acceptable = True
reason = "Perfect match"
```

#### Type 2: ROUNDING_DIFFERENCE ✓ (Acceptable)
```python
old_value = Decimal("1000.501")  # Old system didn't quantize
new_value = Decimal("1000.50")   # New system quantizes to 2dp
classification = "ROUNDING_DIFFERENCE"
acceptable = True
reason = "Rounding to 2dp per FINANCIAL_NUMBER_CONTRACT"
```

**Decision rule:**
```python
def is_rounding_difference(old, new):
    """Check if difference is only rounding."""
    tolerance = Decimal("0.01")  # 1 cent
    return abs(old - new) < tolerance
```

#### Type 3: ORDERING_DIFFERENCE ✓ (Acceptable if final matches)
```python
old_running_balances = [700, 500, 450]  # License-wide order
new_running_balances = [700, 500, 450]  # Per-company order, but same final
classification = "ORDERING_DIFFERENCE"
acceptable = True (if final balance matches)
reason = "Intermediate order differs, but final balance is identical"
```

**Decision rule:**
```python
def is_ordering_difference(old_list, new_list):
    """Check if order differs but content is same."""
    return sorted(old_list) == sorted(new_list)
```

#### Type 4: EXPECTED_CHANGE ✓ (Acceptable if documented)
```python
old_result = "1000.00"  # Commission treated as non-debit (old business rule)
new_result = "950.00"   # Commission treated as debit (new business rule)
classification = "EXPECTED_CHANGE"
acceptable = True (if business approved B4 decision)
reason = "Business rule change: commissions now debits (approval doc: ADR-003)"
```

**Decision rule:**
```python
EXPECTED_CHANGES = {
    "commission_treatment": "Commissions now treated as debits per ADR-003",
    "balance_convention": "License-wide per ADR-004"
}

def is_expected_change(old, new, category):
    return category in EXPECTED_CHANGES
```

#### Type 5: SEMANTIC_DIFFERENCE ✗ (BLOCKER — Investigate!)
```python
old_result = Decimal("1000.50")
new_result = Decimal("900.25")  # Unexplained difference
classification = "SEMANTIC_DIFFERENCE"
acceptable = False
reason = "Unexplained divergence; must investigate logic"
```

**Decision rule:**
```python
def is_semantic_difference(old, new):
    """Difference not explained by rounding, ordering, or known business change."""
    # Not within rounding tolerance
    if abs(old - new) >= Decimal("0.01"):
        # Not an ordering issue (lists don't match when sorted)
        if not isinstance(old, list) or sorted(old) != sorted(new):
            # Not a documented expected change
            return True
    return False
```

### Classification Result Matrix

```
Difference >= 0.01? │ Within Known │ Business  │ Classification │ Acceptable?
                    │ Change?      │ Approved? │                │
────────────────────┼──────────────┼──────────┼────────────────┼─────────────
NO (< 0.01)         │   —          │    —     │ ROUNDING       │ ✓ YES
YES                 │   YES        │   YES    │ EXPECTED_CHANGE│ ✓ YES
YES                 │   YES        │   NO     │ EXPECTED_CHANGE│ ✗ MAYBE
YES                 │   NO         │    —     │ SEMANTIC_DIFF  │ ✗ INVESTIGATE
```

---

## Level 3: Acceptance Criteria

### Acceptance Checklist

```python
class ParityAcceptance:
    """Gate criteria for accepting a new calculation."""
    
    def __init__(self, test_results: List[Difference]):
        self.test_results = test_results
    
    def passes(self) -> bool:
        """Determine if parity test passes all criteria."""
        
        # Criterion 1: No semantic differences
        semantic_diffs = [d for d in self.test_results 
                         if d.classification == "SEMANTIC_DIFFERENCE"]
        if semantic_diffs:
            self.rejection_reason = f"Semantic differences: {semantic_diffs}"
            return False
        
        # Criterion 2: All non-identical differences are classified as acceptable
        for diff in self.test_results:
            if diff.classification not in ["IDENTICAL", "ROUNDING_DIFFERENCE", 
                                          "ORDERING_DIFFERENCE", "EXPECTED_CHANGE"]:
                self.rejection_reason = f"Unknown classification: {diff.classification}"
                return False
            if not diff.acceptable:
                self.rejection_reason = f"Unacceptable difference: {diff}"
                return False
        
        # Criterion 3: All expected changes are business-approved
        expected_changes = [d for d in self.test_results 
                           if d.classification == "EXPECTED_CHANGE"]
        for change in expected_changes:
            if not self._is_business_approved(change):
                self.rejection_reason = f"Expected change not approved: {change}"
                return False
        
        return True
    
    def _is_business_approved(self, diff: Difference) -> bool:
        """Check if difference is referenced in an approved ADR."""
        # Read from APPROVED_CHANGES registry
        return diff.reason in APPROVED_CHANGES.keys()
```

### Gate Signoff Process

```
Step 1: Run parity tests on full golden dataset
        ↓
Step 2: Classify all differences automatically
        ↓
Step 3: Manual review of EXPECTED_CHANGE differences
        ↓
        ┌─ Are they business-approved? ─┐
        │                               │
      NO                              YES
        │                               │
        ↓                               ↓
    REJECT               Continue to Step 4
    (Need approval ADR)
    
Step 4: Run on subset of production data (if feasible)
        ↓
Step 5: Compare with manual spot-checks from domain experts
        ↓
        ┌─ Do domain experts agree? ─┐
        │                            │
      NO                           YES
        │                            │
        ↓                            ↓
    INVESTIGATE        ACCEPT (merge to main, activate via feature flag)
```

---

## Level 4: Golden Dataset Test Scenarios

### Scenario 1: Simple Single License (Zero Complexity)

```python
SCENARIO_SIMPLE = {
    "name": "Single License, Single Export, No Debits",
    "license_id": 1001,
    "exports": [
        {"cif_fc": "1000.00", "date": "2026-01-01"}
    ],
    "debits": [],
    "expected_balance": "1000.00"
}
```

### Scenario 2: Multiple Transactions Same Date

```python
SCENARIO_SAME_DAY = {
    "name": "Multiple Transactions on Same Date (ID-ordered)",
    "license_id": 1002,
    "exports": [
        {"cif_fc": "2000.00", "date": "2026-01-01"}
    ],
    "debits": [
        {"id": 100, "cif_fc": "600.00", "date": "2026-02-15"},
        {"id": 101, "cif_fc": "500.00", "date": "2026-02-15"},  # Same date
    ],
    "expected_running": [
        {"txn_id": 100, "balance": "1400.00"},  # 2000 - 600, ID 100 first
        {"txn_id": 101, "balance": "900.00"}    # 1400 - 500, ID 101 second
    ],
    "expected_final": "900.00"
}
```

### Scenario 3: Commission Handling

```python
SCENARIO_COMMISSION = {
    "name": "Commission Treatment (Depends on B4 Decision)",
    "license_id": 1003,
    "exports": [
        {"cif_fc": "1000.00", "date": "2026-01-01"}
    ],
    "commissions": [
        {"cif_fc": "50.00", "date": "2026-02-01"}
    ],
    "expected_final": "950.00"  # If commission is debit (B4=YES)
                    # OR "1000.00" if commission excluded (B4=NO)
}
```

### Scenario 4: Rounding Edge Case

```python
SCENARIO_ROUNDING = {
    "name": "Rounding (Should Quantize to 2dp)",
    "license_id": 1004,
    "exports": [
        {"cif_fc": "1000.125", "date": "2026-01-01"}  # 3dp input
    ],
    "expected_final": "1000.13"  # Rounded to 2dp with ROUND_HALF_UP
}
```

### Scenario 5: Zero Balance Edge Case

```python
SCENARIO_ZERO = {
    "name": "Exactly Zero Balance (Fully Consumed)",
    "license_id": 1005,
    "exports": [
        {"cif_fc": "1000.00", "date": "2026-01-01"}
    ],
    "debits": [
        {"cif_fc": "1000.00", "date": "2026-02-01"}
    ],
    "expected_final": "0.00"  # Exactly zero, not negative
}
```

### Scenario 6: Negative Balance Edge Case

```python
SCENARIO_NEGATIVE = {
    "name": "Over-Consumed (Negative Balance)",
    "license_id": 1006,
    "exports": [
        {"cif_fc": "1000.00", "date": "2026-01-01"}
    ],
    "debits": [
        {"cif_fc": "1200.00", "date": "2026-02-01"}
    ],
    "expected_final": "-200.00"  # Allowed (overuse flagged separately)
}
```

### Scenario 7: Production-Like Complexity

```python
SCENARIO_COMPLEX = {
    "name": "Production-Like (Multiple Items, Companies, Transactions)",
    "license_id": 1007,
    "exports": [
        {"cif_fc": "50000.00", "date": "2026-01-05"}
    ],
    "allotments": [
        {"cif_fc": "10000.00", "date": "2026-02-01"},
        {"cif_fc": "5000.00", "date": "2026-02-15"}
    ],
    "boe_debits": [
        {"cif_fc": "12000.00", "date": "2026-02-10"},
        {"cif_fc": "8000.00", "date": "2026-02-20"}
    ],
    "trades": [
        {"cif_fc": "5000.00", "date": "2026-03-01"}
    ],
    "expected_running": [
        # Full calculation chain
    ],
    "expected_final": "10000.00"  # 50000 - 10000 - 5000 - 12000 - 8000 - 5000
}
```

---

## Test Suite Implementation

### File Structure

```
backend/apps/license/tests/
├── test_parity_framework.py        # Framework code
├── test_ledger_balance_parity.py   # Ledger parity tests
├── golden_data/
│   ├── license_1001.json           # Scenario 1
│   ├── license_1002.json           # Scenario 2
│   ├── license_1003.json           # Scenario 3
│   └── ... (all 7 scenarios)
```

### Example Test

```python
import pytest
from apps.license.tests.test_parity_framework import CalculationParityTest

@pytest.mark.parametrize("scenario", [
    SCENARIO_SIMPLE,
    SCENARIO_SAME_DAY,
    SCENARIO_COMMISSION,
    SCENARIO_ROUNDING,
    SCENARIO_ZERO,
    SCENARIO_NEGATIVE,
    SCENARIO_COMPLEX,
])
def test_balance_calculator_parity(scenario):
    """Verify new calculator passes parity test on all golden scenarios."""
    test = CalculationParityTest(scenario["license_id"])
    test.load_scenario(scenario)
    
    # Run both
    test.run_old_calculation()
    test.run_new_calculation()
    
    # Compare and accept
    differences = test.compare()
    acceptance = ParityAcceptance(differences)
    
    assert acceptance.passes(), f"Parity failed: {acceptance.rejection_reason}"
```

---

## Version and Status

- **Version 1.0** — Gate 3 Architecture Design, 2026-08-10
- **Updated by:** Solutions Architect
- **Used for:** Migration acceptance gate (Phase 4+)
- **Critical:** Must pass before activating CALC-L-001 new implementation
- **Test suite:** 7 golden scenarios, all must pass
- **Next:** Phase 4 (implement with this framework)
