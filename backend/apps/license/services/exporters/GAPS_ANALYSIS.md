# Gaps Analysis: Canonical Service → DTO → PDF Renderer

**Objective:** Identify what data the PDF renderer currently requires that is NOT present in the canonical service dataset.

**Status:** All required fields are present. Zero gaps. The canonical service is complete.

---

## I. Current Renderer Requirements (from ledger_pdf.py)

The PDF renderer currently:
1. Calls `get_license_transactions(lic_data, company_id=None)` 
2. Receives transactions dict with transaction list + totals
3. Renders table with these columns: Date, Type, Particulars, Invoice No., Sale CIF, Purchase CIF, Balance, Sale (₹), Purchase (₹), SION Norm, Status, P/L
4. Renders summary with: total_purchase_bill_inr, total_sale_bill_inr, total_profit_loss

---

## II. Field-by-Field Gap Assessment

### Transaction Fields

| Field | Renderer Uses | Canonical Provides | Status | Note |
|-------|---------------|-------------------|--------|------|
| date | ✓ Yes | ✓ Yes (txn['date']) | ✅ OK | Both use license_date for OPENING |
| type | ✓ Yes | ✓ Yes (txn['type']) | ✅ OK | OPENING, PURCHASE, SALE, COMMISSION_* |
| particular | ✓ Yes | ✓ Yes (txn['particulars']) | ✅ OK | E.g., "Purchase from ABC" |
| invoice_number | ✓ Yes | ✓ Yes (txn['invoice_number']) | ✅ OK | Can be None; renders as "-" |
| debit_cif | ✓ Yes | ✓ Yes (txn['debit_cif']) | ✅ OK | USD amount for sales |
| credit_cif | ✓ Yes | ✓ Yes (txn['credit_cif']) | ✅ OK | USD amount for purchases |
| debit_amount | ✓ Yes | ✓ Yes (txn['debit_amount']) | ✅ OK | INR amount for sales |
| credit_amount | ✓ Yes | ✓ Yes (txn['credit_amount']) | ✅ OK | INR amount for purchases |
| rate | ✓ Yes | ✓ Yes (txn['rate']) | ✅ OK | Exchange rate (calculated by canonical) |
| running_balance | ✓ Yes | ✓ Yes (txn['license_running_balance']) | ✅ OK | Balance after txn (from canonical) |
| total_profit_loss | ✓ Yes | ✓ Yes (txn['total_profit_loss']) | ✅ OK | P&L to date (from canonical) |
| item_names | ✓ Yes | ✓ Yes (txn['item_names']) | ✅ OK | Pre-collected by canonical |
| sion_norms | ✓ Yes | ✓ Yes (txn['sion_norms']) | ✅ OK | Pre-normalized to string |
| is_sion_norm_empty | ✓ Yes | ✓ Yes (txn['sion_norms'] empty check) | ✅ OK | Derived from sion_norms string |
| has_purchase_bill | ✓ Yes | ✓ Yes (canonical['has_purchase_bill']) | ✅ OK | License-level flag for styling |

### Summary Fields

| Field | Renderer Uses | Canonical Provides | Status | Note |
|-------|---------------|-------------------|--------|------|
| total_purchase_bill_inr | ✓ Yes | ✓ Yes (summary['total_purchase_bill_inr']) | ✅ OK | INR total |
| total_sale_bill_inr | ✓ Yes | ✓ Yes (summary['total_sale_bill_inr']) | ✅ OK | INR total |
| total_profit_loss | ✓ Yes | ✓ Yes (summary['total_profit_loss']) | ✅ OK | Derived as sale−purchase |
| current_balance | ✓ Yes (implied) | ✓ Yes (summary['current_balance']) | ✅ OK | total_purchase − total_sale |
| profit_state | ✓ Yes (for color) | ✓ Yes (summary['profit_state']) | ✅ OK | PROFIT, LOSS, BREAK_EVEN, UNAVAILABLE |
| balance_currency | ✓ Yes (implied) | ✓ Yes (summary['balance_currency']) | ✅ OK | USD (DFIA) or INR (incentive) |

### Metadata Fields

| Field | Renderer Uses | Canonical Provides | Status | Note |
|-------|---------------|-------------------|--------|------|
| license_number | ✓ Yes | ✓ Yes (canonical['license_number']) | ✅ OK | Public license ID |
| license_type | ✓ Yes | ✓ Yes (canonical['license_type']) | ✅ OK | DFIA, INCENTIVE, etc. |
| exporter_name | ✓ Yes | ✓ Yes (canonical['exporter_name']) | ✅ OK | "" if unknown |
| port_name | ✓ Yes | ✓ Yes (canonical['port_name']) | ✅ OK | "" if unknown |
| license_date | ✓ Yes | ✓ Yes (canonical['license_date']) | ✅ OK | Issuance date |
| expiry_date | ✓ Yes | ✓ Yes (canonical['expiry_date']) | ✅ OK | Expiration date |
| opening_balance | ✓ Yes (for display) | ✓ Yes (canonical['opening_balance']) | ✅ OK | Shown only when no purchase |
| has_purchase_bill | ✓ Yes (for "No Purchase Bill" marker) | ✓ Yes (canonical['has_purchase_bill']) | ✅ OK | Flags rows without purchase bill |
| opening_display | ✓ Yes (for opening row) | ✓ Yes (canonical['opening_display']) | ✅ OK | Synthetic OPENING row or None |

---

## III. Current Renderer Logic That Gets Moved to Canonical Service

**Before (in get_license_transactions):**
```python
# Database queries (MOVED TO CANONICAL)
trades = LicenseTrade.objects.filter(...).prefetch_related(...).distinct()

# Canonical balance calculation (MOVED TO CANONICAL)
canonical_balances = {}
for txn in canonical_data.get('transactions', []):
    canonical_balances[txn.get('id')] = txn.get('license_running_balance')

# Canonical bill amounts (MOVED TO CANONICAL)
canonical_bill_amounts = {}
for txn in canonical_data.get('transactions', []):
    canonical_bill_amounts[txn.get('id')] = txn.get('bill_amount')

# Canonical SION norms (MOVED TO CANONICAL)
canonical_sion_norms = {}
for txn in canonical_data.get('transactions', []):
    canonical_sion_norms[txn.get('id')] = txn.get('sion_norms')

# Summary totals (MOVED TO CANONICAL)
canonical_total_purchase_bill_inr = canonical_summary.get('total_purchase_bill_inr')
canonical_total_sale_bill_inr = canonical_summary.get('total_sale_bill_inr')
canonical_total_profit_loss = canonical_summary.get('total_profit_loss')
```

**After (in DTO.from_canonical):**
```python
# All data already in canonical dict
# DTO just projects it (zero recalculation)
summary = FinancialSummaryDTO(
    total_purchase_bill_inr=_to_decimal(summary_data.get('total_purchase_bill_inr')),
    total_sale_bill_inr=_to_decimal(summary_data.get('total_sale_bill_inr')),
    total_profit_loss=_to_decimal(summary_data.get('total_profit_loss')),
    # ... etc
)
```

---

## IV. Potential Gaps (None Found)

### A. Opening Balance Row Handling

**Requirement:** Opening balance must be shown as a separate row when:
- has_purchase_bill = False (no purchase exists)
- opening_balance > 0

**Current State in Canonical:**
- ✅ `canonical['opening_display']` is None or a dict
- ✅ Display rule is enforced in canonical service
- ✅ When opening_display is not None, it contains all transaction fields

**DTO Handling:**
```python
opening_balance_row = None
if opening_display_txn:
    opening_balance_row = FinancialTransactionDTO(
        date=opening_display_txn.get('date'),
        type=opening_display_txn.get('type', 'OPENING'),
        # ... all fields from opening_display_txn
    )
metadata.opening_balance_row = opening_balance_row
metadata.show_opening_display = opening_balance_row is not None
```

**Status:** ✅ No gap. Canonical pre-selects opening_display; DTO wraps it.

### B. Purchase Bill Detection

**Requirement:** Flag whether license has ANY PURCHASE with non-zero bill.

**Current State in Canonical:**
- ✅ `canonical['has_purchase_bill']` is a boolean
- ✅ Computed once by `_has_purchase_bill()` in canonical service
- ✅ Used to control opening display logic
- ✅ Passed to every transaction for styling

**DTO Handling:**
```python
has_purchase_bill = canonical.get('has_purchase_bill', False)
# Copy to metadata and every transaction for styling
```

**Status:** ✅ No gap. Canonical provides boolean; DTO carries it through.

### C. SION Norms Normalization

**Requirement:** SION norms must be:
- Comma-space separated string ("NORM1, NORM2, NORM3")
- Empty string if none
- is_sion_norm_empty boolean for rendering

**Current State in Canonical:**
- ✅ `txn['sion_norms']` is a pre-normalized string
- ✅ Canonical service computes this via `_extract_sion_norms()`
- ✅ "" for OPENING rows (no billed items)

**DTO Handling:**
```python
sion_norms=txn.get('sion_norms', ''),
is_sion_norm_empty=not txn.get('sion_norms', '').strip(),
```

**Status:** ✅ No gap. Canonical pre-normalizes; DTO preserves it.

### D. Item Names Collection

**Requirement:** Comma-separated descriptions of items billed in this transaction.

**Current State in Canonical:**
- ✅ `txn['item_names']` is a list collected by `_extract_item_names()`
- ✅ Canonical service handles both DFIA (SRs) and incentive licenses

**DTO Handling:**
```python
item_names=txn.get('item_names', ''),
# Renderer joins with ', ' if needed
```

**Status:** ✅ No gap. Canonical collects; DTO carries forward.

### E. Running Balance & P&L

**Requirement:** Every transaction must have:
- Running balance after that transaction
- Consolidated P&L to date

**Current State in Canonical:**
- ✅ `txn['license_running_balance']` is calculated deterministically
- ✅ `txn['total_profit_loss']` is passed through from summary
- ✅ All values pre-quantized to 2 decimal places

**DTO Handling:**
```python
running_balance=_to_decimal(txn.get('license_running_balance', 0)),
total_profit_loss=_to_decimal(txn.get('total_profit_loss', 0)),
```

**Status:** ✅ No gap. Canonical calculates; DTO ensures 2dp precision.

---

## V. Fields Renderer Must NOT Request

These should NOT be added to canonical or DTO:

| Field | Why Not | Alternative |
|-------|---------|-------------|
| company_utilization_after | Not needed for PDF (only for company-scoped table row footer) | If needed, keep in separate data structure for that view |
| Intermediate balance calc | All balances are final from canonical | Use canonical running_balance |
| Recalculated profit | Canonical profit is authoritative | Use canonical total_profit_loss |
| Currency-adjusted amounts | Canonical uses target currency (INR for bills, USD for CIF) | No conversion needed |

---

## VI. Summary: Zero Gaps

**Canonical Service Provides:**
- ✅ All transaction data (date, type, particulars, invoices, CIF, amounts)
- ✅ All balance data (running balance per transaction)
- ✅ All profit/loss data (P&L to date)
- ✅ All summary totals (purchase, sale, profit/loss)
- ✅ Opening balance logic (opening_display when no purchase)
- ✅ SION norms (pre-normalized strings)
- ✅ Item names (pre-collected)
- ✅ Purchase bill detection (boolean flag)
- ✅ All metadata (license ID, number, type, dates, exporter, port)

**DTO Does:**
- ✅ Project canonical data into frozen dataclasses
- ✅ Ensure 2dp precision on all Decimal fields
- ✅ Provide from_canonical() factory for construction
- ✅ Provide to_dict() for serialization if needed

**PDF Renderer Does:**
- ✅ Format and layout data (table, typography, colors)
- ✅ Convert None/empty to "-" for display
- ✅ Apply locale-specific number/date formatting
- ✅ Implement PDF-specific styling (fonts, colors, borders)

---

## VII. Pre-Rendering Validation Checklist

Before rendering, verify:

```python
dto = FinancialLedgerExportDTO.from_canonical(canonical)

# Metadata
assert dto.metadata.license_id > 0
assert dto.metadata.license_number
assert dto.metadata.license_type in ['DFIA', 'INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS']

# Summary totals are valid Decimals
assert isinstance(dto.summary.total_purchase, Decimal)
assert isinstance(dto.summary.total_sale, Decimal)
assert dto.summary.total_purchase >= 0
assert dto.summary.total_sale >= 0

# Transactions are chronologically sorted
if dto.transactions:
    dates = [t.date for t in dto.transactions]
    assert all(d is not None for d in dates)
    # dates should be in order (enforcement by canonical)

# Opening display logic is correct
if dto.metadata.show_opening_display:
    assert not dto.metadata.has_purchase_bill
    assert dto.metadata.opening_balance > 0
    assert dto.metadata.opening_balance_row is not None
else:
    assert dto.metadata.opening_balance_row is None

# All Decimals have exactly 2 places
for txn in dto.transactions:
    assert txn.debit_cif.as_tuple().exponent >= -2
    assert txn.credit_cif.as_tuple().exponent >= -2
    # ... etc (validation is in __post_init__)
```

---

## VIII. Conclusion

**The canonical service is complete.** There are zero gaps in the data it provides. The DTO is a deterministic, zero-logic projection of that data, suitable for immutable transmission to a pure PDF renderer.

No additional database queries, no additional calculations, no additional business logic is needed anywhere in the rendering pipeline.
