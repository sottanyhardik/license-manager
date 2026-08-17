# FinancialLedgerExportDTO — Complete Package

This directory contains the single immutable input contract for all PDF/Excel rendering from the License Manager ledger system.

---

## What's Inside

### Core Implementation

**`dto.py`** (16 KB, validated syntax)
- `FinancialTransactionDTO` — Single transaction row (frozen dataclass)
- `FinancialSummaryDTO` — Aggregated totals (frozen dataclass)
- `FinancialMetadataDTO` — License header info (frozen dataclass)
- `FinancialLedgerExportDTO` — Top-level contract with factory method (frozen dataclass)
- `_to_decimal()` — Utility to ensure 2dp precision

**Key properties:**
- ✅ Immutable (frozen dataclasses)
- ✅ All decimals pre-rounded to 2dp
- ✅ Zero business logic in data structure
- ✅ All values pre-calculated (from canonical service)
- ✅ Validated in __post_init__()

---

### Documentation

**`USAGE_QUICK_REFERENCE.md`** (11 KB) — START HERE
- Basic usage pattern (3 lines: canonical → DTO → PDF)
- Common patterns (opening display, profit/loss color, currency formatting)
- DO's and DON'Ts
- Debugging tips
- Edge cases
- Cheat sheet

**`MAPPING_GUIDE.md`** (17 KB)
- Field-by-field mapping from canonical to DTO
- Data flow diagram (canonical → DTO → PDF)
- Critical invariants
- Transaction structure details
- Example calling code
- Test verification

**`GAPS_ANALYSIS.md`** (12 KB)
- Assessment: **Zero gaps** (canonical provides everything)
- Field-by-field gap assessment table
- Current renderer logic vs. new path
- Validation checklist
- Pre-rendering verification steps

**`EXAMPLE_LICENSE_FLOW.md`** (20 KB)
- Real-world walkthrough of license 0310833996
- Canonical service output (complete dict)
- DTO structure (with example values)
- PDF rendering output (mock)
- Key observations
- Test verification from test_ledger_reconciliation_smoking_gun.py

**`DTO_DESIGN_SUMMARY.md`** (16 KB)
- Design goals and decisions
- DTO structure (4 dataclasses)
- Data mapping highlights
- Zero-logic principle with before/after code
- Validation layers
- Integration path (steps 1-4)
- Implementation details
- Non-functional properties

**`README.md`** (this file)
- Package overview
- Quick start
- File index

---

## Quick Start

```python
# 1. Get canonical ledger data
from apps.license.services.canonical_ledger_service import CanonicalLedgerService

canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
    license_id=lic.id,
    license_type='DFIA'
)

# 2. Build immutable DTO (zero queries, zero logic)
from apps.license.services.exporters.dto import FinancialLedgerExportDTO

dto = FinancialLedgerExportDTO.from_canonical(canonical, company_id=None)

# 3. Render PDF (pure formatter)
from apps.license.services.exporters.ledger_pdf import generate_detailed_licenses_pdf

pdf_bytes = generate_detailed_licenses_pdf([dto], query_params={})
return HttpResponse(pdf_bytes, content_type='application/pdf')
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ CanonicalLedgerService.build_canonical_ledger_dataset()         │
│ (SINGLE AUTHORITATIVE SOURCE)                                    │
│                                                                   │
│ Returns: {                                                        │
│   'license_id', 'license_number', 'license_type',               │
│   'exporter_name', 'port_name', 'license_date', 'expiry_date',  │
│   'has_purchase_bill', 'purchase_bill_status',                  │
│   'opening_balance', 'opening_display',                         │
│   'display_transactions': [                                      │
│     { 'date', 'type', 'particulars', 'invoice_number',         │
│       'debit_cif', 'credit_cif', 'debit_amount',               │
│       'credit_amount', 'rate', 'license_running_balance',       │
│       'total_profit_loss', 'sion_norms', 'item_names' }        │
│   ],                                                             │
│   'summary': {                                                   │
│     'total_purchase', 'total_sale', 'balance_currency',        │
│     'total_purchase_bill_inr', 'total_sale_bill_inr',          │
│     'current_balance', 'total_profit_loss',                    │
│     'profit_state', 'opening_balance', 'opening_in_purchase'   │
│   }                                                              │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
         ↓
    DTO.from_canonical()
    (deterministic projection, zero business logic)
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ FinancialLedgerExportDTO (frozen, immutable)                     │
│                                                                   │
│ metadata: FinancialMetadataDTO                                   │
│   ├─ license_id, license_number, license_type                  │
│   ├─ exporter_name, port_name                                  │
│   ├─ license_date, expiry_date                                 │
│   ├─ has_purchase_bill, purchase_bill_status                   │
│   ├─ opening_balance, show_opening_display                     │
│   └─ opening_balance_row (FinancialTransactionDTO or None)      │
│                                                                   │
│ summary: FinancialSummaryDTO                                     │
│   ├─ total_purchase, total_sale, balance_currency              │
│   ├─ total_purchase_bill_inr, total_sale_bill_inr              │
│   ├─ current_balance, total_profit_loss, profit_state          │
│   └─ opening_balance, opening_in_purchase                      │
│                                                                   │
│ transactions: List[FinancialTransactionDTO]                    │
│   ├─ [date, type, particulars, invoice_number,                │
│   ├─  debit_cif, credit_cif, debit_amount, credit_amount,     │
│   ├─  rate, running_balance, total_profit_loss,               │
│   ├─  sion_norms, is_sion_norm_empty, item_names,            │
│   └─  has_purchase_bill]                                       │
└─────────────────────────────────────────────────────────────────┘
         ↓
    generate_detailed_licenses_pdf([dto], {})
    (pure formatter, zero business logic, zero queries)
         ↓
    PDF bytes
```

---

## Key Principles

1. **Single Source of Truth:** CanonicalLedgerService only. No recalculation.
2. **Immutability:** Frozen dataclasses. Safe for concurrent reads, caching, etc.
3. **Zero Business Logic in Renderer:** All decisions baked into DTO by canonical service.
4. **Zero Queries:** PDF renderer has zero database access.
5. **Pre-Calculated:** Every field needed by renderer is pre-calculated in canonical service.
6. **Deterministic:** Same input → same DTO → same PDF every time.

---

## Data Completeness

**Canonical service provides everything the DTO needs:**
- ✅ All transaction data (date, type, particulars, invoices, CIF, amounts)
- ✅ All balance data (running balance per transaction)
- ✅ All profit/loss data (P&L to date)
- ✅ All summary totals (purchase, sale, profit/loss)
- ✅ Opening balance logic (opening_display when no purchase)
- ✅ SION norms (pre-normalized strings)
- ✅ Item names (pre-collected)
- ✅ Purchase bill detection (boolean flag)
- ✅ All metadata (license ID, number, type, dates, exporter, port)

**Zero gaps. All required data is present.**

---

## File Index

| File | Purpose | Size | Key Content |
|------|---------|------|-------------|
| `dto.py` | Implementation | 16 KB | 4 frozen dataclasses + factory method |
| `USAGE_QUICK_REFERENCE.md` | Getting started | 11 KB | Examples, patterns, cheat sheet |
| `MAPPING_GUIDE.md` | Field mapping | 17 KB | Canonical → DTO mapping, invariants |
| `GAPS_ANALYSIS.md` | Completeness | 12 KB | Assessment: zero gaps |
| `EXAMPLE_LICENSE_FLOW.md` | Walkthrough | 20 KB | Real license with values |
| `DTO_DESIGN_SUMMARY.md` | Design rationale | 16 KB | Goals, decisions, architecture |
| `README.md` | This file | Overview | Package index |

---

## How to Read the Docs

### If you're implementing the PDF renderer:
1. Start with `USAGE_QUICK_REFERENCE.md` (patterns, DO's/DON'Ts)
2. Reference `MAPPING_GUIDE.md` for field definitions
3. Use `EXAMPLE_LICENSE_FLOW.md` as a concrete example

### If you're reviewing the design:
1. Read `DTO_DESIGN_SUMMARY.md` (goals, decisions, architecture)
2. Review `MAPPING_GUIDE.md` (field-by-field mapping)
3. Check `GAPS_ANALYSIS.md` (completeness verification)

### If you're integrating with the canonical service:
1. Study `MAPPING_GUIDE.md` (what canonical provides)
2. Review `GAPS_ANALYSIS.md` (data completeness)
3. Follow `USAGE_QUICK_REFERENCE.md` (integration steps)

### If you're debugging:
1. Check `USAGE_QUICK_REFERENCE.md` (common patterns, edge cases)
2. Review `EXAMPLE_LICENSE_FLOW.md` (expected values)
3. Use `GAPS_ANALYSIS.md` (validation checklist)

---

## Implementation Status

**Done:**
- [x] DTO defined (4 frozen dataclasses)
- [x] Factory method (from_canonical)
- [x] Decimal validation (2dp precision)
- [x] Python syntax validated
- [x] Complete documentation (5 guides)

**Next Steps:**
- [ ] Integration test: DTO from real canonical data
- [ ] Update PDF exporter to use DTO
- [ ] Golden scenario validation (14 licenses)
- [ ] Deprecate get_license_transactions()

---

## Examples

### Basic Export
```python
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.exporters.dto import FinancialLedgerExportDTO
from apps.license.services.exporters.ledger_pdf import generate_detailed_licenses_pdf

# Get license
lic = LicenseDetailsModel.objects.get(license_number='0310833996')

# Build DTO
canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')
dto = FinancialLedgerExportDTO.from_canonical(canonical)

# Render
pdf_bytes = generate_detailed_licenses_pdf([dto], {})
return HttpResponse(pdf_bytes, content_type='application/pdf')
```

### Multiple Licenses
```python
licenses = LicenseDetailsModel.objects.filter(...)
dtos = [
    FinancialLedgerExportDTO.from_canonical(
        CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, lic.license_type)
    )
    for lic in licenses
]
pdf_bytes = generate_detailed_licenses_pdf(dtos, {})
```

### Company-Scoped
```python
canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')
dto = FinancialLedgerExportDTO.from_canonical(canonical, company_id=222)
# dto.metadata.company_id = 222 (context for rendering)
```

See `USAGE_QUICK_REFERENCE.md` for more examples.

---

## Validation

Before rendering, verify:

```python
# Metadata
assert dto.metadata.license_id > 0
assert dto.metadata.license_number

# Summary
assert isinstance(dto.summary.total_profit_loss, Decimal)
assert dto.summary.balance_currency in ['USD', 'INR']

# Transactions
assert all(t.date for t in dto.transactions)
assert all(isinstance(t.running_balance, Decimal) for t in dto.transactions)

# Opening display logic
if dto.metadata.show_opening_display:
    assert not dto.metadata.has_purchase_bill
    assert dto.metadata.opening_balance > 0
    assert dto.metadata.opening_balance_row is not None

# Chronological order
dates = [t.date for t in dto.transactions]
assert dates == sorted(dates)
```

See `GAPS_ANALYSIS.md` for complete checklist.

---

## Support

- **Usage questions:** See `USAGE_QUICK_REFERENCE.md`
- **Field definitions:** See `MAPPING_GUIDE.md`
- **Design questions:** See `DTO_DESIGN_SUMMARY.md`
- **Data completeness:** See `GAPS_ANALYSIS.md`
- **Real example:** See `EXAMPLE_LICENSE_FLOW.md`

---

## Version & Date

- **Version:** 1.0
- **Created:** 2026-08-14
- **Status:** Complete, syntactically valid, ready for integration
- **Syntax checked:** ✅ Python 3.8+

---

## Key Takeaway

The DTO is a deterministic, zero-logic projection of canonical ledger data suitable for immutable transmission to a pure PDF renderer with guaranteed correctness, no queries, and no recalculation.

**One canonical source. One immutable DTO. One pure renderer.**
