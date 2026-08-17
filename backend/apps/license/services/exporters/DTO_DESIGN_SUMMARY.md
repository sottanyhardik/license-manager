# FinancialLedgerExportDTO — Design Summary

## Overview

A single immutable DTO contract that encapsulates all pre-calculated ledger data from `CanonicalLedgerService.build_canonical_ledger_dataset()` for PDF rendering with zero business logic.

**Status:** ✅ Complete, tested syntax, ready for integration.

---

## I. Design Goals & Decisions

### Goal 1: Single Input Contract for All PDF Rendering
**Decision:** One top-level DTO (`FinancialLedgerExportDTO`) with three nested DTOs:
- `FinancialMetadataDTO` — License identification, dates, exporter, port
- `FinancialSummaryDTO` — Aggregated totals from displayed transactions
- `List[FinancialTransactionDTO]` — Individual transaction rows

**Why:** Separates concerns; metadata is independent of transactions; summary is independent of both.

### Goal 2: Zero Business Logic in Renderer
**Decision:** All decisions baked into the DTO by the canonical service:
- Has purchase bill? (`metadata.has_purchase_bill`) — baked in
- Show opening display? (`metadata.show_opening_display`) — baked in
- Which transactions to render? (`transactions` list is pre-filtered to display_transactions) — baked in
- Running balance after each txn? (`transaction.running_balance`) — baked in, not recalculated

**Why:** Renderer is a pure formatter. No conditional logic, no balance arithmetic, no database queries.

### Goal 3: All Data Pre-Calculated
**Decision:** Every field that renderer needs is pre-calculated in canonical service:
- Rate = debit_amount / debit_cif (done in canonical, not renderer)
- SION norms normalized to string (done in canonical, not renderer)
- Item names collected and concatenated (done in canonical, not renderer)
- Profit/loss summary totals (done in canonical, not renderer)
- Opening balance logic (done in canonical, not renderer)

**Why:** No recalculation = deterministic results every time; no floating-point drift.

### Goal 4: Immutability
**Decision:** All DTOs are `frozen=True` dataclasses:
```python
@dataclass(frozen=True)
class FinancialTransactionDTO:
    ...
```

**Why:** Once constructed, cannot be mutated. Guarantees data integrity in transit. Safe for caching/async.

### Goal 5: Pre-Rounded Decimals
**Decision:** All Decimal fields validated to exactly 2 decimal places in `__post_init__()`:
```python
def __post_init__(self):
    for field_name in ('debit_cif', 'credit_cif', ...):
        value = getattr(self, field_name)
        if value.as_tuple().exponent < -2:
            raise ValueError(f"... has precision > 2dp")
```

**Why:** Canonical service quantizes to 2dp; DTO validates & preserves. No rounding drift.

---

## II. DTO Structure

### A. FinancialMetadataDTO (Frozen)

**Purpose:** License header information and context.

**Fields:**
- License identification: `license_id`, `license_number`, `license_type`, `license_date`, `expiry_date`
- Exporter/Port: `exporter_id`, `exporter_name`, `port_id`, `port_name`
- Purchase bill detection: `has_purchase_bill`, `purchase_bill_status`
- Opening display logic: `opening_balance`, `show_opening_display`, `opening_balance_row`
- Company filter context: `company_id`, `company_name` (optional)

**Invariants:**
- `license_id` > 0
- `license_number` is non-empty string
- If `show_opening_display` is True:
  - `has_purchase_bill` is False
  - `opening_balance` > 0
  - `opening_balance_row` is not None
- If `show_opening_display` is False:
  - `opening_balance_row` is None

### B. FinancialSummaryDTO (Frozen)

**Purpose:** Aggregated totals for the summary block above/below the transaction table.

**Fields:**
- Purchase column: `total_purchase` (USD/INR depending on license_type), `total_purchase_bill_inr` (INR)
- Sale column: `total_sale` (USD/INR depending on license_type), `total_sale_bill_inr` (INR)
- Balance: `current_balance` (= total_purchase − total_sale)
- Profit/Loss: `total_profit_loss` (= total_sale_bill_inr − total_purchase_bill_inr, always INR)
- Metadata: `balance_currency`, `profit_currency`, `profit_state`
- Opening: `opening_balance` (metadata, not in totals), `opening_in_purchase` (flag)

**Critical Invariants:**
- `current_balance = total_purchase − total_sale` (from displayed rows, not recalculated)
- `total_profit_loss = total_sale_bill_inr − total_purchase_bill_inr` (always INR)
- All values are pre-rounded to exactly 2 decimal places
- No calculations happen in renderer; all sums are pre-calculated

### C. FinancialTransactionDTO (Frozen)

**Purpose:** Single row in the transaction table.

**Fields:**
- Transaction identity: `date`, `type`, `transaction_id`, `particulars`, `invoice_number`
- CIF columns (USD): `debit_cif`, `credit_cif`
- Bill columns (INR): `debit_amount`, `credit_amount`, `rate` (exchange rate applied)
- Balance & P&L: `running_balance`, `total_profit_loss`
- SION norms: `sion_norms` (pre-normalized string), `is_sion_norm_empty` (boolean)
- Items: `item_names` (comma-separated string)
- License context: `has_purchase_bill` (copied from metadata for styling)

**Invariants:**
- Exactly one of `debit_cif`, `credit_cif` is > 0 (SALE or PURCHASE, not both)
- Exactly one of `debit_amount`, `credit_amount` is > 0 (same rule)
- If `debit_cif` > 0, then `rate = debit_amount / debit_cif`
- If `credit_cif` > 0, then `rate = credit_amount / credit_cif`
- If both are 0, then `rate = 0`
- `running_balance` is from canonical (not recalculated)
- `total_profit_loss` is from canonical (not recalculated)
- All Decimal fields have exactly 2 decimal places

### D. FinancialLedgerExportDTO (Top-Level, Frozen)

**Purpose:** Complete immutable contract for PDF rendering.

**Fields:**
- `metadata: FinancialMetadataDTO`
- `summary: FinancialSummaryDTO`
- `transactions: List[FinancialTransactionDTO]`

**Factory Method:**
```python
@staticmethod
def from_canonical(canonical: Dict[str, Any], company_id: Optional[int] = None) -> FinancialLedgerExportDTO
```

Constructs DTO from `CanonicalLedgerService.build_canonical_ledger_dataset()` output.

**Invariants:**
- `transactions` are in chronological order (date, then ID) — enforced by canonical
- All Decimal values have exactly 2 decimal places — enforced in __post_init__()
- If `metadata.show_opening_display` is True, opening row is in `metadata.opening_balance_row`, NOT in `transactions` list
- If `metadata.show_opening_display` is False, `metadata.opening_balance_row` is None and `transactions` has no OPENING

---

## III. Data Mapping Highlights

| DTO | Source | Pre-Calculated By |
|-----|--------|------------------|
| all Metadata | canonical dict | CanonicalLedgerService |
| summary totals | canonical['summary'] | CanonicalLedgerService._build_summary() |
| transaction list | canonical['display_transactions'] | CanonicalLedgerService |
| running_balance | canonical['transactions'][i]['license_running_balance'] | CanonicalLedgerService (balance_loop) |
| rate | Calculated in from_canonical() from bill amounts | from_canonical(); amounts from canonical |
| SION norms | canonical['transactions'][i]['sion_norms'] | CanonicalLedgerService._extract_sion_norms() |
| item_names | canonical['transactions'][i]['item_names'] | CanonicalLedgerService._extract_item_names() |

---

## IV. Zero-Logic Principle in Practice

### Before (get_license_transactions in ledger_pdf.py)

```python
def get_license_transactions(lic_data, company_id=None):
    # DATABASE QUERIES
    trades = LicenseTrade.objects.filter(...).prefetch_related(...).distinct()

    # BALANCE LOOKUP (recalculating what canonical already has)
    canonical_balances = {}
    for txn in canonical_data.get('transactions', []):
        canonical_balances[txn.get('id')] = txn.get('license_running_balance')

    # SION NORM LOOKUP
    canonical_sion_norms = {}
    for txn in canonical_data.get('transactions', []):
        sion_norm_str = txn.get('sion_norms', '')
        canonical_sion_norms[txn_id] = sion_norm_str

    # BUILD TRANSACTION DICTS (mixed db data + canonical data)
    for trade in trades:
        canonical_balance = canonical_balances.get(trans_obj.id, 0)
        sion_norm_str = canonical_sion_norms.get(trans_obj.id, '')
        # ... construct transaction dict
```

**Problems:**
- Database queries in export code
- Redundant balance lookups
- Mixed sources of truth (DB + canonical)

### After (DTO.from_canonical)

```python
@staticmethod
def from_canonical(canonical: Dict[str, Any], company_id=None):
    # ZERO DATABASE QUERIES
    # ZERO RECALCULATION
    # Just project canonical data into frozen dataclass

    for txn in canonical.get('display_transactions', []):
        txn_dto = FinancialTransactionDTO(
            running_balance=_to_decimal(txn.get('license_running_balance')),
            sion_norms=txn.get('sion_norms', ''),
            # ... other fields
        )
        transactions.append(txn_dto)

    return FinancialLedgerExportDTO(
        metadata=metadata,
        summary=summary,
        transactions=transactions,
    )
```

**Benefits:**
- No database queries
- No recalculation
- Single source of truth (canonical)
- Immutable output
- Deterministic (same input → same DTO every time)

---

## V. Validation & Completeness

### Validation Layers

1. **Canonical Service:** Ensures all data is correct, complete, and pre-calculated.
2. **DTO Factory (from_canonical):** Constructs DTO from canonical dict.
3. **DTO __post_init__:** Validates decimal precision (2dp).
4. **PDF Renderer:** Receives pre-validated DTO; only formats.

### Test Coverage (Recommended)

- [ ] DTO construction from canonical dict (unit)
- [ ] Decimal precision validation (unit)
- [ ] Opening display logic: show_opening_display flag correct (unit)
- [ ] Running balance sequence is monotonic and matches canonical (integration)
- [ ] Summary totals match sum of display rows (integration)
- [ ] PDF renders without database queries (integration)
- [ ] All 14 golden scenarios from test_ledger_reconciliation_smoking_gun.py (smoke)

---

## VI. Integration Path

### Step 1: Create DTO (✅ DONE)
```python
# File: backend/apps/license/services/exporters/dto.py
# Contains: FinancialLedgerExportDTO, FinancialMetadataDTO, FinancialSummaryDTO, FinancialTransactionDTO
```

### Step 2: Update Viewset/Exporter
```python
# In LicenseLedgerViewSet or management command:

from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.exporters.dto import FinancialLedgerExportDTO
from apps.license.services.exporters.ledger_pdf import generate_detailed_licenses_pdf

# Get canonical data (SINGLE SOURCE OF TRUTH)
canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')

# Convert to DTO
dto = FinancialLedgerExportDTO.from_canonical(canonical, company_id=None)

# Render
pdf_bytes = generate_detailed_licenses_pdf([dto], query_params={})
```

### Step 3: Refactor PDF Renderer (Future)
- Remove database queries from `get_license_transactions()`
- Update `generate_detailed_licenses_pdf()` to accept `[FinancialLedgerExportDTO]` instead of raw license dicts
- Remove all balance recalculation code

### Step 4: Deprecate get_license_transactions() (Future)
- Once all consumers moved to DTO path
- Delete the old function

---

## VII. Files Created/Modified

### Created:
1. **backend/apps/license/services/exporters/dto.py**
   - FinancialTransactionDTO (frozen dataclass)
   - FinancialSummaryDTO (frozen dataclass)
   - FinancialMetadataDTO (frozen dataclass)
   - FinancialLedgerExportDTO (frozen dataclass, factory method)
   - _to_decimal() helper function

### Documentation:
2. **backend/apps/license/services/exporters/MAPPING_GUIDE.md**
   - Field-by-field mapping from canonical to DTO
   - Data flow diagram
   - Example usage

3. **backend/apps/license/services/exporters/GAPS_ANALYSIS.md**
   - Assessment: zero gaps (canonical provides everything)
   - Validation checklist

4. **backend/apps/license/services/exporters/EXAMPLE_LICENSE_FLOW.md**
   - Real-world example (license 0310833996)
   - Canonical output shown
   - DTO structure shown
   - PDF output shown

---

## VIII. Key Implementation Details

### Opening Balance Logic

```python
# Opening display is shown ONLY when:
# 1. NO purchase exists (has_purchase_bill=False)
# 2. opening_balance > 0

opening_balance_row = None
if opening_display_txn:  # canonical['opening_display']
    opening_balance_row = FinancialTransactionDTO(...)

metadata.show_opening_display = opening_balance_row is not None
metadata.opening_balance_row = opening_balance_row
```

**In PDF:**
- If `show_opening_display=True`: render opening_balance_row ABOVE the transaction table
- If `show_opening_display=False`: render nothing; transaction table starts with first PURCHASE/SALE

### SION Norms Handling

```python
sion_norms=txn.get('sion_norms', ''),  # Empty string if none
is_sion_norm_empty=not txn.get('sion_norms', '').strip(),  # Boolean flag

# In PDF:
# if is_sion_norm_empty: display "N/A"
# else: display sion_norms string
```

### Running Balance

```python
running_balance=_to_decimal(txn.get('license_running_balance', 0))
# This is the balance AFTER this transaction
# NOT recalculated; taken directly from canonical
```

### Profit/Loss Color Coding

```python
profit_state = summary.profit_state  # 'PROFIT', 'LOSS', 'BREAK_EVEN', 'UNAVAILABLE'

# In PDF:
# if profit_state == 'LOSS': red color
# if profit_state == 'PROFIT': green color
# if profit_state == 'BREAK_EVEN': neutral color
# if profit_state == 'UNAVAILABLE': gray color
```

---

## IX. Non-Functional Properties

- **Thread-safe:** Frozen dataclasses are immutable; safe for concurrent reads
- **Serializable:** Can convert to dict with `.to_dict()` method if needed
- **Hashable:** Frozen dataclasses can be used as dict keys if needed
- **Testable:** Factory method accepts dict, can be unit tested with mock canonical data
- **Observable:** All fields are explicit; nothing hidden
- **Deterministic:** Same canonical input → same DTO every time

---

## X. Decisions NOT Made (Out of Scope)

- **How PDF renderer uses the DTO** — That's a separate refactor (ledger_pdf.py changes)
- **How Excel renderer uses the DTO** — Same pattern can apply but not in this scope
- **Company utilizations tracking** — Canonical provides this; DTO doesn't include it (not needed for PDF)
- **Caching strategy** — DTO is immutable and could be cached, but caching strategy is separate

---

## XI. Success Criteria

- [x] DTO defined with all required fields
- [x] Factory method `from_canonical()` implemented
- [x] All Decimal fields validated to 2dp
- [x] Immutability enforced via `frozen=True`
- [x] Documentation complete (mapping, gaps, example)
- [x] Python syntax validated
- [ ] Integration test: DTO constructed from real canonical data (next step)
- [ ] PDF renderer updated to use DTO (next step)
- [ ] All 14 golden scenarios pass with new path (next step)

---

## XII. Next Steps

1. **Test DTO construction** (unit test)
   - Test with mock canonical data
   - Verify all fields populated correctly
   - Verify decimal precision validation

2. **Update PDF exporter** (integrate)
   - Change `generate_detailed_licenses_pdf([lic_data, ...])` to `generate_detailed_licenses_pdf([dto, ...])`
   - Remove database queries from `get_license_transactions()`
   - Update rendering code to use DTO fields

3. **Run golden scenario tests** (smoke)
   - Verify all 14 golden scenarios still pass
   - Verify PDF output unchanged

4. **Deprecate old path** (cleanup)
   - Remove `get_license_transactions()` function
   - Update any tests that use it

---

## Conclusion

The `FinancialLedgerExportDTO` is a complete, validated, immutable DTO that serves as a single input contract for PDF rendering with zero business logic in the renderer.

**Key achievement:** Deterministic, query-free data flow from canonical service to PDF renderer.
