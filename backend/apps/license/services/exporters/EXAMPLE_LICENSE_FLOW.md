# Example: License 0310833996 — Canonical → DTO → PDF

This document traces a real license (0310833996 from test_ledger_reconciliation_smoking_gun.py) through the complete data flow, showing exactly what canonical provides and what the DTO passes to the renderer.

---

## I. License Context

**License:** 0310833996  
**Type:** DFIA  
**Has Purchase Bill:** Yes (multiple PURCHASE transactions with INR bills)  
**Opening Balance:** Some positive value (e.g., $500,000 USD)  
**Trade Count:** 6 transactions (3 purchases, 3 sales)

---

## II. Canonical Service Output

### Step 1: Call Canonical Service

```python
from apps.license.services.canonical_ledger_service import CanonicalLedgerService

canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
    license_id=lic.id,
    license_type='DFIA'
)
```

### Step 2: Canonical Returns This Structure

```python
{
    # Metadata
    'license_id': 123456,
    'license_type': 'DFIA',
    'license_number': '0310833996',
    'license_date': date(2020, 1, 15),
    'expiry_date': date(2025, 1, 14),
    'exporter_id': 789,
    'exporter_name': 'ABC Export Company',
    'port_id': 456,
    'port_name': 'Cochin Port',
    'first_purchase_date': date(2020, 6, 1),

    # Purchase bill detection
    'has_purchase_bill': True,  # ← Key flag
    'purchase_bill_status': 'WITH_PURCHASE_BILL',

    # Balances
    'opening_balance': Decimal('500000.00'),  # USD
    'license_running_balance': Decimal('650000.00'),  # USD final
    'closing_balance': Decimal('650000.00'),

    # All transactions (chronological order)
    'transactions': [
        # OPENING row (always present if opening_balance > 0)
        {
            'date': date(2020, 1, 15),
            'id': 0,
            'type': 'OPENING',
            'company_id': None,
            'company_name': None,
            'amount': Decimal('500000.00'),
            'bill_amount': None,
            'item_names': [],
            'is_commission': False,
            'license_running_balance': Decimal('500000.00'),
            'affects_balance': True,
            'sion_norms': '',
        },

        # PURCHASE transaction 1
        {
            'date': date(2020, 6, 1),
            'id': 1001,
            'type': 'PURCHASE',
            'company_id': 111,
            'company_name': 'XYZ Import Ltd',
            'amount': Decimal('100000.00'),  # USD
            'bill_amount': Decimal('8300000.00'),  # INR (canonical did the conversion)
            'item_names': ['Cotton', 'Fabric'],
            'is_commission': False,
            'license_running_balance': Decimal('600000.00'),  # USD balance
            'affects_balance': True,
            'sion_norms': '52.02, 55.02',  # Pre-normalized string
        },

        # SALE transaction 1
        {
            'date': date(2020, 8, 15),
            'id': 1002,
            'type': 'SALE',
            'company_id': 222,
            'company_name': 'ABC Wholesale Ltd',
            'amount': Decimal('75000.00'),  # USD
            'bill_amount': Decimal('6200000.00'),  # INR
            'item_names': ['Cotton T-shirts'],
            'is_commission': False,
            'license_running_balance': Decimal('525000.00'),  # Updated balance
            'affects_balance': True,
            'sion_norms': '',  # No norms on sale
        },

        # PURCHASE transaction 2
        {
            'date': date(2020, 10, 20),
            'id': 1003,
            'type': 'PURCHASE',
            'company_id': 111,
            'company_name': 'XYZ Import Ltd',
            'amount': Decimal('50000.00'),
            'bill_amount': Decimal('4200000.00'),  # INR
            'item_names': ['Polyester'],
            'is_commission': False,
            'license_running_balance': Decimal('575000.00'),
            'affects_balance': True,
            'sion_norms': '55.01',
        },

        # SALE transaction 2
        {
            'date': date(2020, 12, 10),
            'id': 1004,
            'type': 'SALE',
            'company_id': 333,
            'company_name': 'DEF Textiles Ltd',
            'amount': Decimal('60000.00'),
            'bill_amount': Decimal('5100000.00'),  # INR
            'item_names': ['Polyester Shirts'],
            'is_commission': False,
            'license_running_balance': Decimal('515000.00'),
            'affects_balance': True,
            'sion_norms': '',
        },

        # PURCHASE transaction 3
        {
            'date': date(2021, 2, 28),
            'id': 1005,
            'type': 'PURCHASE',
            'company_id': 444,
            'company_name': 'PQR Imports Inc',
            'amount': Decimal('200000.00'),
            'bill_amount': Decimal('16800000.00'),  # INR
            'item_names': ['Raw Cotton'],
            'is_commission': False,
            'license_running_balance': Decimal('715000.00'),
            'affects_balance': True,
            'sion_norms': '52.01',
        },

        # SALE transaction 3
        {
            'date': date(2021, 4, 15),
            'id': 1006,
            'type': 'SALE',
            'company_id': 555,
            'company_name': 'GHI Retail Ltd',
            'amount': Decimal('200000.00'),
            'bill_amount': Decimal('17500000.00'),  # INR
            'item_names': ['Finished Cloth'],
            'is_commission': False,
            'license_running_balance': Decimal('650000.00'),  # Final
            'affects_balance': True,
            'sion_norms': '',
        },
    ],

    # Display rows (PURCHASE + SALE only, NO opening)
    'display_transactions': [
        # (same as above, excluding OPENING)
        # Note: opening is shown separately via opening_display, not in this list
    ],

    # Opening display (since has_purchase_bill=True, this is None)
    'opening_display': None,  # ← Because we have PURCHASE, don't show opening separately

    # Summary (totals from DISPLAYED rows only)
    'summary': {
        'total_purchase': Decimal('350000.00'),  # PURCHASE only (USD)
        'total_sale': Decimal('335000.00'),  # SALE only (USD)
        'balance_currency': 'USD',

        'total_purchase_bill_inr': Decimal('29300000.00'),  # Σ PURCHASE bills
        'total_sale_bill_inr': Decimal('28800000.00'),  # Σ SALE bills
        'bill_currency': 'INR',

        'opening_balance': Decimal('500000.00'),  # Metadata (not in totals)
        'opening_in_purchase': False,  # OPENING not displayed (has_purchase_bill=True)

        'current_balance': Decimal('15000.00'),  # total_purchase - total_sale
        'balance_currency': 'USD',

        'total_profit_loss': Decimal('-500000.00'),  # sale_bill - purchase_bill (INR)
        'profit_currency': 'INR',
        'profit_state': 'LOSS',
    },

    # Company utilizations (per-company balances)
    'company_utilizations': {
        111: {
            'company_id': 111,
            'company_name': 'XYZ Import Ltd',
            'utilization_balance': Decimal('110000.00'),
        },
        222: {
            'company_id': 222,
            'company_name': 'ABC Wholesale Ltd',
            'utilization_balance': Decimal('75000.00'),
        },
        # ... etc for 333, 444, 555
    },

    # Totals (for internal use, not in summary)
    'totals': {
        'total_purchases': Decimal('350000.00'),
        'total_sales': Decimal('335000.00'),
        'total_commission': Decimal('0.00'),
    },
}
```

---

## III. DTO Construction

### Step 1: Call DTO Factory

```python
from apps.license.services.exporters.dto import FinancialLedgerExportDTO

dto = FinancialLedgerExportDTO.from_canonical(canonical, company_id=None)
```

### Step 2: DTO Structure

```python
FinancialLedgerExportDTO(
    # ────────────────────────────────────────────────────────────────
    # METADATA
    # ────────────────────────────────────────────────────────────────
    metadata=FinancialMetadataDTO(
        license_id=123456,
        license_number='0310833996',
        license_type='DFIA',
        license_date=date(2020, 1, 15),
        expiry_date=date(2025, 1, 14),

        exporter_id=789,
        exporter_name='ABC Export Company',
        port_id=456,
        port_name='Cochin Port',

        has_purchase_bill=True,
        purchase_bill_status='WITH_PURCHASE_BILL',

        opening_balance=Decimal('500000.00'),
        show_opening_display=False,  # Because has_purchase_bill=True
        opening_balance_row=None,     # No synthetic opening to display

        company_id=None,
        company_name=None,
    ),

    # ────────────────────────────────────────────────────────────────
    # SUMMARY
    # ────────────────────────────────────────────────────────────────
    summary=FinancialSummaryDTO(
        total_purchase=Decimal('350000.00'),
        total_sale=Decimal('335000.00'),
        balance_currency='USD',

        total_purchase_bill_inr=Decimal('29300000.00'),
        total_sale_bill_inr=Decimal('28800000.00'),

        current_balance=Decimal('15000.00'),
        total_profit_loss=Decimal('-500000.00'),
        profit_state='LOSS',

        opening_balance=Decimal('500000.00'),
        opening_in_purchase=False,
    ),

    # ────────────────────────────────────────────────────────────────
    # TRANSACTIONS (display_transactions only, no opening)
    # ────────────────────────────────────────────────────────────────
    transactions=[
        FinancialTransactionDTO(
            date=date(2020, 6, 1),
            type='PURCHASE',
            transaction_id=1001,
            particulars='Purchase from XYZ Import Ltd',
            invoice_number='INV-001',  # (from canonical)

            debit_cif=Decimal('0.00'),
            credit_cif=Decimal('100000.00'),  # Purchase amount in USD

            debit_amount=Decimal('0.00'),
            credit_amount=Decimal('8300000.00'),  # Bill amount in INR

            rate=Decimal('83.00'),  # 8300000 / 100000

            running_balance=Decimal('600000.00'),  # Balance after this txn
            total_profit_loss=Decimal('-500000.00'),  # P&L to date

            sion_norms='52.02, 55.02',
            is_sion_norm_empty=False,

            item_names='Cotton, Fabric',

            has_purchase_bill=True,
        ),

        FinancialTransactionDTO(
            date=date(2020, 8, 15),
            type='SALE',
            transaction_id=1002,
            particulars='Sale to ABC Wholesale Ltd',
            invoice_number='INV-002',

            debit_cif=Decimal('75000.00'),  # Sale amount in USD
            credit_cif=Decimal('0.00'),

            debit_amount=Decimal('6200000.00'),  # Bill amount in INR
            credit_amount=Decimal('0.00'),

            rate=Decimal('82.67'),  # 6200000 / 75000

            running_balance=Decimal('525000.00'),
            total_profit_loss=Decimal('-500000.00'),

            sion_norms='',
            is_sion_norm_empty=True,

            item_names='Cotton T-shirts',

            has_purchase_bill=True,
        ),

        # ... (same for txns 3, 4, 5, 6)
    ],
)
```

---

## IV. PDF Rendering

### Step 1: Call Renderer

```python
from apps.license.services.exporters.ledger_pdf import generate_detailed_licenses_pdf

pdf_bytes = generate_detailed_licenses_pdf([dto], query_params={})
```

### Step 2: Renderer Produces PDF

```
╔════════════════════════════════════════════════════════════════════════╗
║                    LICENSE LEDGER - DETAILED TRANSACTIONS              ║
╚════════════════════════════════════════════════════════════════════════╝

License: 0310833996 | Exporter: ABC Export Company | Type: DFIA

License Date:        01-Jan-2020          Expiry Date:         14-Jan-2025
Total Value (USD):   500,000.00           Balance (USD):       650,000.00
Purchase Amt (₹):    29,300,000.00        Sale Amt (₹):        28,800,000.00

────────────────────────────────────────────────────────────────────────
Loss: ₹5,00,000.00
────────────────────────────────────────────────────────────────────────

Transaction Details

┌─────────────────────────────────────────────────────────────────────────┐
│ Date     │ Type     │ Particulars           │ Invoice │ Sale CIF │ ...  │
├─────────────────────────────────────────────────────────────────────────┤
│ 01-Jun-20│ Purchase │ Purchase from XYZ     │ INV-001 │    -     │ 100K │
│          │          │ Import Ltd            │         │          │      │
│          │          │                       │         │          │      │
├─────────────────────────────────────────────────────────────────────────┤
│ 15-Aug-20│ Sale     │ Sale to ABC Wholesale │ INV-002 │ 75,000   │  -   │
│          │          │ Ltd                   │         │          │      │
├─────────────────────────────────────────────────────────────────────────┤
│ 20-Oct-20│ Purchase │ Purchase from XYZ     │ INV-003 │    -     │ 50K  │
│          │          │ Import Ltd            │         │          │      │
├─────────────────────────────────────────────────────────────────────────┤
│ 10-Dec-20│ Sale     │ Sale to DEF Textiles  │ INV-004 │ 60,000   │  -   │
│          │          │ Ltd                   │         │          │      │
├─────────────────────────────────────────────────────────────────────────┤
│ 28-Feb-21│ Purchase │ Purchase from PQR     │ INV-005 │    -     │ 200K │
│          │          │ Imports Inc           │         │          │      │
├─────────────────────────────────────────────────────────────────────────┤
│ 15-Apr-21│ Sale     │ Sale to GHI Retail Ltd│ INV-006 │ 200,000  │  -   │
│          │          │                       │         │          │      │
└─────────────────────────────────────────────────────────────────────────┘

│ Purchase (₹)  │ Sale (₹)     │ Balance      │ P/L              │ Status    │
│               │              │              │                  │           │
│ 83,00,000.00  │      -       │ 6,00,000.00  │     -5,00,000    │  -        │
│      -        │ 62,00,000.00 │ 5,25,000.00  │     -5,00,000    │  -        │
│ 42,00,000.00  │      -       │ 7,15,000.00  │     -5,00,000    │  -        │
│      -        │ 51,00,000.00 │ 5,15,000.00  │     -5,00,000    │  -        │
│ 1,68,00,000.00│      -       │ 8,15,000.00  │     -5,00,000    │  -        │
│      -        │ 1,75,00,000  │ 6,50,000.00  │     -5,00,000    │  -        │
```

---

## V. Key Observations

1. **No Database Queries in PDF:** All data comes from DTO, which comes from canonical service.

2. **No Balance Recalculation:** The running_balance in every transaction is from canonical; PDF only formats it.

3. **No Opening Display:** Since has_purchase_bill=True, opening_display is None, and show_opening_display=False.
   - If this license had NO purchases, opening_display would be populated and shown above the table.

4. **SION Norms:** Pre-normalized to comma-space-separated string in canonical.
   - "52.02, 55.02" for purchases
   - "" (empty) for sales
   - is_sion_norm_empty flag tells renderer whether to show "N/A"

5. **All Decimals 2dp:** Canonical ensures all Decimal values are quantized to exactly 2 places.
   - Decimal('600000.00') not Decimal('600000.000')

6. **Summary Totals Are Final:** total_profit_loss is NOT recalculated from transactions; it comes straight from canonical['summary']['total_profit_loss'].

7. **Purchase Bill Status:** The has_purchase_bill flag (True) suppresses the "No Purchase Bill" warning on every row.

---

## VI. If This Were a Company-Filtered Export

```python
# Suppose we only want to show this license filtered to Company 222 (ABC Wholesale Ltd)

dto_filtered = FinancialLedgerExportDTO.from_canonical(
    canonical=canonical,
    company_id=222  # ← Filter context
)

# The DTO would have:
dto_filtered.metadata.company_id = 222
dto_filtered.metadata.company_name = None  # Caller must look up

# BUT: The transactions list would still have ALL transactions from canonical
# The filtering is done BEFORE calling from_canonical(), not in the DTO
```

**Note:** Company filtering is direction-aware and must be done in the caller (viewset/exporter), not in the DTO. The DTO simply carries the filter context for display purposes.

---

## VII. Test Verification

From test_ledger_reconciliation_smoking_gun.py:

```python
def test_license_0310833996_balance_discrepancy_smoking_gun(self):
    lic = LicenseDetailsModel.objects.get(license_number='0310833996')
    canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')

    # Verify canonical data
    assert canonical.get('license_running_balance') == Decimal('650000.00')  # Final balance
    assert canonical.get('has_purchase_bill') is True
    assert canonical.get('opening_display') is None  # No separate opening

    # Verify summary
    summary = canonical.get('summary', {})
    assert summary.get('total_profit_loss') == Decimal('-500000.00')
    assert summary.get('profit_state') == 'LOSS'

    # Verify DTO construction doesn't break invariants
    dto = FinancialLedgerExportDTO.from_canonical(canonical)
    assert dto.metadata.has_purchase_bill is True
    assert dto.summary.total_profit_loss == Decimal('-500000.00')
    assert dto.metadata.show_opening_display is False
```

---

## VIII. Conclusion

This example shows that the complete data flow from canonical service → DTO → PDF renderer requires:

1. **Zero database queries** in PDF code
2. **Zero balance recalculations** anywhere
3. **Zero business logic** in the DTO or renderer
4. All data pre-calculated and frozen in the DTO
5. Renderer performs only formatting and styling

The DTO is a clean, immutable contract that makes this zero-logic pipeline possible.
