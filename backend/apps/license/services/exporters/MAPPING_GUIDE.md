# FinancialLedgerExportDTO — Canonical Mapping Guide

**Purpose:** Document exactly how `CanonicalLedgerService.build_canonical_ledger_dataset()` maps to `FinancialLedgerExportDTO` for PDF rendering.

**Key Principle:** The DTO is a deterministic projection of canonical data. Zero transformation logic. All business decisions are baked in by the canonical service.

---

## I. Top-Level Construction

```python
# In the viewset or exporter calling the PDF renderer:

from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.exporters.dto import FinancialLedgerExportDTO

# Get authoritative ledger data
canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
    license_id=lic.id,
    license_type='DFIA'  # or INCENTIVE, RODTEP, etc.
)

# Convert to DTO (single source of truth)
dto = FinancialLedgerExportDTO.from_canonical(
    canonical=canonical,
    company_id=None  # or int if company-scoped
)

# Pass to renderer
pdf_bytes = generate_detailed_licenses_pdf([dto], query_params={})
```

---

## II. Field-by-Field Mapping

### A. Metadata (FinancialMetadataDTO)

| DTO Field | Source in Canonical | Value | Validation |
|-----------|-------------------|-------|-----------|
| `license_id` | `canonical['license_id']` | int | Required, > 0 |
| `license_number` | `canonical['license_number']` | str | Required, non-empty |
| `license_type` | `canonical['license_type']` | str | DFIA, INCENTIVE, RODTEP, ROSTL, MEIS |
| `license_date` | `canonical['license_date']` | date or None | From LicenseDetailsModel.license_date |
| `expiry_date` | `canonical['expiry_date']` | date or None | From LicenseDetailsModel.license_expiry_date |
| `exporter_id` | `canonical['exporter_id']` | int or None | From LicenseDetailsModel.exporter_id |
| `exporter_name` | `canonical['exporter_name']` | str | "" if unknown (NOT "N/A") |
| `port_id` | `canonical['port_id']` | int or None | From LicenseDetailsModel.port_id |
| `port_name` | `canonical['port_name']` | str | "" if unknown (NOT "N/A") |
| `has_purchase_bill` | `canonical['has_purchase_bill']` | bool | True if ≥1 PURCHASE with non-zero bill |
| `purchase_bill_status` | `canonical['purchase_bill_status']` | str | "WITH_PURCHASE_BILL" or "NO_PURCHASE_BILL" |
| `opening_balance` | `canonical['opening_balance']` | Decimal(2dp) | From LicenseDetailsModel.opening_balance |
| `show_opening_display` | See below | bool | True if opening_display exists |
| `opening_balance_row` | `canonical['opening_display']` | FinancialTransactionDTO or None | See Transaction Mapping |
| `company_id` | Parameter to from_canonical() | int or None | Caller-provided filter context |
| `company_name` | None by default | str or None | Caller must look up if needed |

**Opening Display Logic:**
- `opening_display` exists (non-None) ONLY when:
  1. License has NO purchase (has_purchase_bill = False)
  2. opening_balance > 0
  3. At least one sale exists (or license shows opening as starting state)
- When opening_display is None: show_opening_display = False

### B. Summary (FinancialSummaryDTO)

| DTO Field | Source in Canonical | Derivation | Note |
|-----------|-------------------|-----------|------|
| `total_purchase` | `summary['total_purchase']` | Σ PURCHASE/OPENING rows (displayed) | USD for DFIA |
| `total_sale` | `summary['total_sale']` | Σ SALE rows (displayed) | USD for DFIA |
| `balance_currency` | `summary['balance_currency']` | 'USD' (DFIA) or 'INR' (incentive) | Determines currency of current_balance |
| `total_purchase_bill_inr` | `summary['total_purchase_bill_inr']` | Σ displayed PURCHASE bill amounts | INR, from invoice amounts |
| `total_sale_bill_inr` | `summary['total_sale_bill_inr']` | Σ displayed SALE bill amounts | INR, from invoice amounts |
| `current_balance` | `summary['current_balance']` | total_purchase − total_sale | SINGLE calculation, two labels |
| `total_profit_loss` | `summary['total_profit_loss']` | total_sale_bill_inr − total_purchase_bill_inr | In INR; same number as current_balance conceptually but different currencies |
| `profit_state` | `summary['profit_state']` | PROFIT, LOSS, BREAK_EVEN, or UNAVAILABLE | Derived from total_profit_loss |
| `opening_balance` | `summary['opening_balance']` | License metadata (unchanged) | Not part of total_purchase |
| `opening_in_purchase` | `summary['opening_in_purchase']` | True if opening_display is on screen | Shows whether OPENING is included in total_purchase |

**Critical Invariants:**
1. `current_balance = total_purchase − total_sale` (from displayed rows, not recalculated)
2. `total_profit_loss = total_sale_bill_inr − total_purchase_bill_inr` (always INR)
3. Display rule ensures acquisition counted once:
   - If PURCHASE exists → OPENING suppressed → acquisition via purchase rows
   - If NO PURCHASE → OPENING shown as starting state
4. All values pre-rounded to 2 decimal places by canonical service

---

## III. Transactions (List[FinancialTransactionDTO])

Source: `canonical['display_transactions']` (EXCLUDES opening, unless opening_display exists)

### A. Transaction Structure

| DTO Field | Source | Value | Validation |
|-----------|--------|-------|-----------|
| `date` | `txn['date']` | date | Required; OPENING uses license_date |
| `type` | `txn['type']` | str | OPENING, PURCHASE, SALE, COMMISSION_PURCHASE, COMMISSION_SALE |
| `transaction_id` | `txn['id']` | int | 0 for synthetic OPENING, otherwise trade ID |
| `particulars` | `txn['particulars']` | str | Description (e.g., "Purchase from XYZ Company") |
| `invoice_number` | `txn['invoice_number']` | str or None | Invoice/bill number (null renders as "-") |
| `debit_cif` | `txn['debit_cif']` | Decimal(2dp) | USD; sale CIF (for SALE transactions) |
| `credit_cif` | `txn['credit_cif']` | Decimal(2dp) | USD; purchase CIF (for PURCHASE transactions) |
| `debit_amount` | `txn['debit_amount']` | Decimal(2dp) | INR; sale bill amount (for SALE transactions) |
| `credit_amount` | `txn['credit_amount']` | Decimal(2dp) | INR; purchase bill amount (for PURCHASE transactions) |
| `rate` | `txn['rate']` | Decimal(2dp) | Exchange rate (INR/USD); calculated as debit_amount / debit_cif if debit_cif > 0 |
| `running_balance` | `txn['license_running_balance']` | Decimal(2dp) | Balance after this transaction (from canonical) |
| `total_profit_loss` | `txn['total_profit_loss']` | Decimal(2dp) | Consolidated P&L to date (in INR) |
| `sion_norms` | `txn['sion_norms']` | str | Comma-space-separated norms; "" if none |
| `is_sion_norm_empty` | Derived | bool | True if sion_norms is empty or all-whitespace |
| `item_names` | `txn['item_names']` | str | Comma-separated descriptions; "" if none |
| `has_purchase_bill` | `canonical['has_purchase_bill']` | bool | License-level flag, copied to every transaction for styling |

### B. Opening Balance Transaction

When `canonical['opening_display']` exists, construct a FinancialTransactionDTO with:
```python
FinancialTransactionDTO(
    date=opening_display['date'],  # Usually license_date
    type='OPENING',
    transaction_id=0,
    particulars=opening_display.get('particulars', 'Opening Balance'),
    invoice_number=opening_display.get('invoice_number'),
    credit_cif=opening_display['credit_cif'],  # The opening CIF value
    running_balance=opening_display['license_running_balance'],  # The opening balance
    # ... other fields from canonical
)
```

This becomes `metadata.opening_balance_row` and is rendered separately from the transaction table.

---

## IV. Data Flow: Canonical → DTO → PDF

```
┌─────────────────────────────────────────────────────────────────┐
│ CanonicalLedgerService.build_canonical_ledger_dataset()         │
│ (SINGLE AUTHORITATIVE SOURCE)                                    │
│                                                                   │
│ Returns:                                                          │
│  - metadata (license_id, license_number, exporter, port, dates)  │
│  - opening_display (synthetic OPENING if no purchase)            │
│  - transactions (raw list, all types)                            │
│  - display_transactions (PURCHASE + SALE only, OPENING separate) │
│  - summary (totals from displayed rows)                          │
│  - company_utilizations (per-company balances)                   │
│  - has_purchase_bill, purchase_bill_status                       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
        DTO.from_canonical() — deterministic projection
        (zero business logic, zero queries)
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ FinancialLedgerExportDTO                                         │
│                                                                   │
│ metadata (immutable FinancialMetadataDTO)                        │
│   ├─ license_id, license_number, license_type, dates            │
│   ├─ exporter_name, port_name                                   │
│   ├─ has_purchase_bill, purchase_bill_status                    │
│   ├─ opening_balance, show_opening_display                      │
│   └─ opening_balance_row (FinancialTransactionDTO or None)       │
│                                                                   │
│ summary (immutable FinancialSummaryDTO)                          │
│   ├─ total_purchase, total_sale                                 │
│   ├─ balance_currency, current_balance                          │
│   ├─ total_purchase_bill_inr, total_sale_bill_inr               │
│   └─ total_profit_loss, profit_state                            │
│                                                                   │
│ transactions (List[FinancialTransactionDTO])                    │
│   └─ [date, type, particulars, invoice, CIF, amounts,           │
│       rate, running_balance, P&L, SION, item_names]             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
    PDF Renderer (generate_detailed_licenses_pdf)
    (ZERO BUSINESS LOGIC — FORMAT ONLY)
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ PDF Output                                                        │
│                                                                   │
│ [License Header]                                                 │
│ License: 0310833996 | Exporter: ABC Corp | Type: DFIA           │
│                                                                   │
│ [Opening Balance] (if show_opening_display=True)                 │
│ Opening Balance - Original DFIA License    USD 500,000.00        │
│                                                                   │
│ [Transaction Table]                                              │
│ Date | Type | Particulars | ... | Sale CIF | Balance | P/L      │
│ ──────────────────────────────────────────────────────────────  │
│ [display_transactions rendered row by row]                       │
│                                                                   │
│ [Summary Footer]                                                 │
│ Total Purchase (₹): 100,000.00                                   │
│ Total Sale (₹): 75,000.00                                        │
│ Profit/Loss (₹): -25,000.00  [LOSS]                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## V. Data Gaps: What Must Be Filled Before Rendering

### A. Gaps in Canonical Data (None — All Required Fields Present)

The canonical service provides everything the DTO needs:
- ✅ Metadata (license_id, number, type, dates, exporter, port)
- ✅ has_purchase_bill (boolean flag)
- ✅ opening_display (pre-selected for display)
- ✅ display_transactions (pre-filtered PURCHASE + SALE only)
- ✅ summary (pre-calculated totals)
- ✅ All monetary values in target currency (USD for CIF, INR for bills)
- ✅ All decimals pre-rounded to 2 places
- ✅ Running balances from canonical calculation
- ✅ Profit/loss from canonical calculation
- ✅ SION norms pre-normalized to strings

### B. Gaps in DTO (Filled by Caller if Needed)

| Field | Default | Filled By | When |
|-------|---------|-----------|------|
| `company_id` | None | Caller (viewset/exporter) | When company-scoped export |
| `company_name` | None | Caller lookup (or left empty) | When company_id is set |

These are optional and used only for company-filtered views.

### C. Gaps in PDF Rendering (Handled by Renderer)

The PDF renderer must handle these formatting/styling tasks:
- Date formatting (locale, format: "dd-MMM-yyyy")
- Number formatting (Indian lakhs/crores: "12,34,567.89")
- Currency symbols and alignment
- Color-coding (green for profit, red for loss)
- Font styling (bold, italic, size)
- Table layout (column widths, borders, shading)
- Paragraph wrapping (particulars, item names)
- Null value rendering (None → "-", empty string → "-")

---

## VI. Example: Calling the Exporter

```python
# In a Django viewset or management command:

from apps.license.models import LicenseDetailsModel
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.exporters.dto import FinancialLedgerExportDTO
from apps.license.services.exporters.ledger_pdf import generate_detailed_licenses_pdf

# Get license(s)
licenses = LicenseDetailsModel.objects.filter(
    license_number__in=['0310833996', '0310834296']
)

# Build DTOs
dtos = []
for lic in licenses:
    canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
        license_id=lic.id,
        license_type='DFIA'
    )
    dto = FinancialLedgerExportDTO.from_canonical(canonical)
    dtos.append(dto)

# Render PDF (zero business logic in the renderer)
pdf_bytes = generate_detailed_licenses_pdf(dtos, query_params={})

# Return to client
return HttpResponse(pdf_bytes, content_type='application/pdf')
```

---

## VII. Validation & Testing

### A. DTO Invariants (Checked in __post_init__)

```python
# All Decimal fields must have exactly 2 decimal places
assert all_decimals.as_tuple().exponent >= -2
```

### B. Canonical Invariants (From test_ledger_reconciliation_smoking_gun.py)

```python
# Opening display shown only when no purchase and opening_balance > 0
if opening_display:
    assert not has_purchase_bill
    assert opening_balance > 0

# Running balances are deterministic and monotonic (within the same direction)
assert all(txn.running_balance is not None for txn in transactions)

# Transactions in chronological order (date, then ID)
assert (dates, ids) == sorted((dates, ids))

# Summary totals equal sum of display rows
assert summary.total_purchase == sum(t.amount for t in display_txns if t.type in ['PURCHASE', 'OPENING'])
assert summary.total_sale == sum(t.amount for t in display_txns if t.type == 'SALE')
```

### C. Test Coverage

- [ ] DTO construction from canonical dataset (unit)
- [ ] Decimal precision validation (unit)
- [ ] Opening display logic (unit)
- [ ] Summary totals accuracy (integration)
- [ ] PDF rendering without database queries (integration)
- [ ] Company-scoped filter (integration)
- [ ] All 14 golden scenarios (smoke)

---

## VIII. Migration Path (If Replacing get_license_transactions)

**Current:** `get_license_transactions()` is called by the PDF renderer and does database queries + balance recalculation.

**Target:** PDF renderer receives pre-built DTO with zero queries.

**Steps:**
1. ✅ Define FinancialLedgerExportDTO (DONE)
2. Add DTO.from_canonical() factory (DONE)
3. Update viewset to call: canonical → DTO → renderer
4. Delete get_license_transactions() (deprecated)
5. Verify all 14 golden scenarios pass with new path

---

## IX. Key Principles (Do Not Violate)

1. **Single Source of Truth:** CanonicalLedgerService only. No balance recalculation in PDF.
2. **Immutability:** DTOs are frozen dataclasses. No mutation after construction.
3. **Zero Queries:** PDF renderer has zero database access. All data in DTO.
4. **Deterministic:** Same canonical input → same DTO → same PDF every time.
5. **No Business Logic in Renderer:** Renderer is a pure formatter. All decisions baked into DTO.
