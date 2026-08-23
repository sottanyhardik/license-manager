# FinancialLedgerExportDTO — Quick Reference for Developers

**TL;DR:** Use `FinancialLedgerExportDTO.from_canonical()` to build the DTO, pass it to the PDF renderer, and it handles everything else.

---

## I. Basic Usage

```python
# In your viewset, management command, or export handler:

from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.exporters.dto import FinancialLedgerExportDTO
from apps.license.services.exporters.ledger_pdf import generate_detailed_licenses_pdf

# 1. Get canonical data (the single source of truth)
canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
    license_id=lic.id,
    license_type='DFIA'  # or INCENTIVE, RODTEP, etc.
)

# 2. Convert to DTO (deterministic projection, zero queries)
dto = FinancialLedgerExportDTO.from_canonical(canonical)

# 3. Render PDF (pure formatter, zero business logic)
pdf_bytes = generate_detailed_licenses_pdf([dto], query_params={})

# 4. Return to client
return HttpResponse(pdf_bytes, content_type='application/pdf')
```

---

## II. For Multiple Licenses

```python
# Build DTOs for multiple licenses

licenses = LicenseDetailsModel.objects.filter(...)

dtos = []
for lic in licenses:
    canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, lic.license_type)
    dto = FinancialLedgerExportDTO.from_canonical(canonical)
    dtos.append(dto)

pdf_bytes = generate_detailed_licenses_pdf(dtos, query_params={})
```

---

## III. For Company-Scoped Export

```python
# Show license data filtered to a specific company

canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')
dto = FinancialLedgerExportDTO.from_canonical(canonical, company_id=222)

# DTO now has:
# - dto.metadata.company_id = 222
# - dto.metadata.company_name = None (caller must look up if needed)
# - All transactions (filtering is done before from_canonical())
```

---

## IV. Accessing DTO Data in PDF Renderer

### Metadata
```python
# Header information
dto.metadata.license_number  # '0310833996'
dto.metadata.exporter_name   # 'ABC Corp'
dto.metadata.license_date    # date(2020, 1, 15)
dto.metadata.has_purchase_bill  # True or False
```

### Opening Balance (if shown)
```python
if dto.metadata.show_opening_display:
    opening_row = dto.metadata.opening_balance_row
    # opening_row.date, opening_row.credit_cif, opening_row.running_balance, etc.
```

### Summary (totals)
```python
dto.summary.total_purchase          # Decimal('350000.00')  in USD
dto.summary.total_sale              # Decimal('335000.00')  in USD
dto.summary.total_purchase_bill_inr # Decimal('29300000.00') in INR
dto.summary.total_sale_bill_inr     # Decimal('28800000.00') in INR
dto.summary.total_profit_loss       # Decimal('-500000.00') in INR
dto.summary.profit_state            # 'LOSS', 'PROFIT', 'BREAK_EVEN', 'UNAVAILABLE'
```

### Transactions (for table rendering)
```python
for txn in dto.transactions:
    txn.date              # date(2020, 6, 1)
    txn.type              # 'PURCHASE' or 'SALE'
    txn.particulars       # 'Purchase from XYZ Company'
    txn.invoice_number    # 'INV-001' or None
    txn.debit_cif         # Decimal('75000.00')  [SALE]
    txn.credit_cif        # Decimal('100000.00') [PURCHASE]
    txn.debit_amount      # Decimal('6200000.00')  in INR [SALE]
    txn.credit_amount     # Decimal('8300000.00') in INR [PURCHASE]
    txn.rate              # Decimal('83.00')  [exchange rate applied]
    txn.running_balance   # Decimal('600000.00')  [balance after this txn]
    txn.total_profit_loss # Decimal('-500000.00') [P&L to date]
    txn.sion_norms        # '52.02, 55.02' or ''
    txn.is_sion_norm_empty # True or False
    txn.item_names        # 'Cotton, Fabric'
    txn.has_purchase_bill # True [from license-level flag]
```

---

## V. Common Patterns

### Check if Opening Should Be Shown
```python
if dto.metadata.show_opening_display:
    opening = dto.metadata.opening_balance_row
    # Render opening row above table
else:
    # Start table with first transaction
```

### Determine Profit/Loss Color
```python
if dto.summary.profit_state == 'LOSS':
    color = RED
elif dto.summary.profit_state == 'PROFIT':
    color = GREEN
elif dto.summary.profit_state == 'BREAK_EVEN':
    color = NEUTRAL
else:
    color = GRAY
```

### Handle Empty Values
```python
# All fields are present (never None unless explicitly optional)
# None values in renderer should display as "-"

if txn.invoice_number:
    display = txn.invoice_number
else:
    display = "-"

# Empty strings also display as "-"
if txn.sion_norms:  # Empty string is falsy
    display = txn.sion_norms
else:
    display = "-" if txn.is_sion_norm_empty else "N/A"
```

### Format Currency
```python
# All Decimals are already 2 decimal places
# Renderer uses format_indian_number() utility for INR
# and formats USD with appropriate symbol

from shared.pdf.builders import format_indian_number

# For INR amounts:
inr_str = format_indian_number(txn.debit_amount, 2)  # "62,00,000.00"

# For USD amounts:
usd_str = format_indian_number(txn.debit_cif, 2)  # "75,000.00"
```

### Format Dates
```python
# Dates are date objects; format as needed
date_str = txn.date.strftime('%d-%b-%y')  # "01-Jun-20"
```

---

## VI. DO's and DON'Ts

### DO:
- ✅ Use DTO fields directly (they're pre-calculated and correct)
- ✅ Copy DTO fields into renderer data structures
- ✅ Format and style DTO data for PDF
- ✅ Validate DTO by reading its fields
- ✅ Serialize DTO to dict with `.to_dict()` if needed

### DON'T:
- ❌ Recalculate running balance
- ❌ Recalculate profit/loss
- ❌ Query database for additional data
- ❌ Mutate DTO fields (they're frozen)
- ❌ Assume null/empty fields need special handling (use "-")
- ❌ Derive SION norms from transactions (use pre-normalized string)
- ❌ Filter transactions (use pre-filtered list from DTO)

---

## VII. Debugging Tips

### Verify Canonical Data First
```python
canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic_id, 'DFIA')

# Check expected fields exist
assert canonical['license_number']
assert canonical['opening_display'] is None or canonical['opening_display'] is not None
assert canonical['display_transactions']  # Should have txns
assert canonical['summary']['total_profit_loss']
```

### Inspect DTO Data
```python
dto = FinancialLedgerExportDTO.from_canonical(canonical)

# Print as dict for inspection
import json
dto_dict = dto.to_dict()
print(json.dumps(dto_dict, indent=2, default=str))  # default=str for date serialization
```

### Check Decimal Precision
```python
for txn in dto.transactions:
    # All Decimals should have exactly 2 decimal places
    assert txn.running_balance.as_tuple().exponent >= -2, f"Precision error: {txn.running_balance}"
```

### Verify Opening Display Logic
```python
if dto.metadata.show_opening_display:
    assert not dto.metadata.has_purchase_bill, "Opening shown only when NO purchase"
    assert dto.metadata.opening_balance > 0, "Opening shown only when balance > 0"
    assert dto.metadata.opening_balance_row is not None, "Opening row must exist"
else:
    assert dto.metadata.opening_balance_row is None, "Opening row must be None"
```

---

## VIII. Edge Cases

### No Transactions
```python
if not dto.transactions:
    # License has no trades; render "No transactions" message
    # Opening may still be shown if show_opening_display=True
```

### No Purchase Bill
```python
if not dto.metadata.has_purchase_bill:
    # Mark transactions with "No Purchase Bill" warning
    # Opening balance will be shown (if opening_balance > 0)
```

### Empty SION Norms
```python
if txn.is_sion_norm_empty:
    # Display "N/A" for SION norm column
else:
    # Display txn.sion_norms string
```

### No Opening Balance
```python
if dto.metadata.opening_balance == 0:
    # Opening display is not shown even if no purchase
```

### Multiple Licenses
```python
# Each DTO is independent; render each on separate page or section
for dto in dtos:
    # Render license header
    # Render opening (if applicable)
    # Render transactions
    # Render summary
    # Page break before next license
```

---

## IX. Performance Considerations

- **One DTO per license:** Create DTO only once per license; reuse for multiple renders if needed.
- **No N+1 queries:** Canonical service handles all queries; DTO adds zero queries.
- **Immutable:** Frozen dataclasses are cheap to create and safe to cache.
- **Small memory:** Only data needed for rendering is in DTO.

---

## X. Testing

### Unit Test: DTO Construction
```python
def test_dto_construction_from_canonical():
    canonical = {
        'license_id': 123,
        'license_number': '0310833996',
        'license_type': 'DFIA',
        'exporter_name': 'ABC',
        'port_name': 'Port X',
        'license_date': date(2020, 1, 1),
        'has_purchase_bill': True,
        'opening_balance': Decimal('500000.00'),
        'opening_display': None,
        'display_transactions': [],
        'summary': {
            'total_purchase': Decimal('0.00'),
            'total_sale': Decimal('0.00'),
            'balance_currency': 'USD',
            'total_purchase_bill_inr': Decimal('0.00'),
            'total_sale_bill_inr': Decimal('0.00'),
            'current_balance': Decimal('0.00'),
            'total_profit_loss': Decimal('0.00'),
            'profit_state': 'UNAVAILABLE',
            'opening_balance': Decimal('500000.00'),
            'opening_in_purchase': False,
        }
    }
    
    dto = FinancialLedgerExportDTO.from_canonical(canonical)
    
    assert dto.metadata.license_number == '0310833996'
    assert dto.summary.total_profit_loss == Decimal('0.00')
    assert dto.metadata.show_opening_display == False
```

### Integration Test: Full Flow
```python
def test_full_export_flow():
    lic = LicenseDetailsModel.objects.get(license_number='0310833996')
    
    # Get canonical data
    canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')
    
    # Build DTO
    dto = FinancialLedgerExportDTO.from_canonical(canonical)
    
    # Verify DTO has expected data
    assert dto.metadata.license_id == lic.id
    assert len(dto.transactions) > 0
    assert dto.summary.total_profit_loss is not None
    
    # Render PDF (should not raise)
    pdf_bytes = generate_detailed_licenses_pdf([dto], {})
    assert len(pdf_bytes) > 0
```

---

## Cheat Sheet

| Need | Where | How |
|------|-------|-----|
| License number | `dto.metadata.license_number` | Copy directly |
| Transaction rows | `dto.transactions` | Iterate, format each field |
| Total purchase (USD) | `dto.summary.total_purchase` | Use `format_indian_number()` |
| Total sale (INR) | `dto.summary.total_sale_bill_inr` | Use `format_indian_number()` |
| Running balance | `txn.running_balance` | Copy directly (pre-calculated) |
| Profit/loss color | `dto.summary.profit_state` | Map to color (LOSS→red, PROFIT→green) |
| SION norm display | `txn.sion_norms if not txn.is_sion_norm_empty else "N/A"` | Use flag to decide |
| Opening row | `dto.metadata.opening_balance_row if dto.metadata.show_opening_display else None` | Check flag first |
| Company filter | `dto.metadata.company_id` | Display in report title if present |

---

## Support & Questions

Refer to:
1. **MAPPING_GUIDE.md** — Field-by-field mapping from canonical
2. **GAPS_ANALYSIS.md** — Completeness verification
3. **EXAMPLE_LICENSE_FLOW.md** — Real-world walkthrough
4. **DTO_DESIGN_SUMMARY.md** — Design decisions & architecture
