# Backend PDF Canonical Migration Baseline — Phase 4E-B
**Date:** 2026-08-10  
**Status:** PRE-IMPLEMENTATION BASELINE  
**Phase:** 4E-B — Backend PDF Migration

---

## CURRENT STATE

### File Under Migration
**Location:** `backend/apps/license/services/exporters/ledger_pdf.py`

### Entry Points (Backend Only)
1. `/license-ledger/export/all/` → `export_all()` → `_generate_detailed_licenses_pdf()`
2. `/license-ledger/company-ledger/export/` → `company_ledger_export()` → `generate_detailed_licenses_pdf()`

### Current Architecture
```
View endpoint
    ↓
generate_detailed_licenses_pdf() [lines 237–551]
    ↓
get_license_transactions(lic_data, company_id) [lines 43–233]
    ↓
LicenseTrade.objects.filter() → Raw transaction rebuild
    ↓
Independent balance calculation [lines 100–227]
    ↓
Transaction dict with pre-calculated `balance` field
    ↓
ReportLab PDF generation with formatted `balance` column
```

### Independent Balance Calculation
**Location:** `ledger_pdf.py:100–227` in `get_license_transactions()`

**Code Pattern:**
```python
running_balance = 0  # Line 100
# ... transaction processing ...
if trans_type in ['PURCHASE', 'COMMISSION_PURCHASE']:
    running_balance += total_cif_usd  # Line 187
elif trans_type in ['SALE', 'COMMISSION_SALE']:
    running_balance -= total_cif_usd  # Line 193
# ... transaction appended with balance field
```

**Scope:** License-wide (correct, matches canonical)
**Semantics:** Includes COMMISSION in balance calculation (lines 184–194)

### Transaction Fields Generated
| Field | Source | Type | Example |
|-------|--------|------|---------|
| date | trans_date | date | 2026-01-15 |
| type | trans_type | enum | PURCHASE, SALE, COMMISSION |
| particular | f-string | str | "Purchase from Supplier A" |
| invoice_number | trans.invoice_number | str | "INV-001" |
| cif_usd | Calculated | float | 1000.00 |
| debit_cif | Conditional | float | 1000.00 or 0 |
| credit_cif | Conditional | float | 0 or 500.00 |
| rate | total_amount / cif_usd | float | 85.50 |
| amount | trans_line.amount_inr | float | 85500.00 |
| debit_amount | Conditional | float | 85500.00 or 0 |
| credit_amount | Conditional | float | 0 or 42750.00 |
| **balance** | **CALCULATED** | **float** | **42750.00** |
| profit_loss | SALE only | float | 500.00 |

### PDF Presentation Layer
**Functions:** `generate_detailed_licenses_pdf()`, `generate_all_licenses_pdf()`, `generate_company_ledger_pdf()`

**Key Formatting:**
- Lines 344–381: Transaction table columns (Date, Type, Particulars, Invoice No., CIF, Balance, P/L)
- Line 359: `balance = txn.get('balance', 0)` — consumes pre-calculated balance
- Line 378: `Paragraph(format_indian_number(balance, 2), wrap_style)` — formats for display
- Lines 350–382: No independent calculations, purely formatting

**Preserved Elements:**
- PDF layout and pagination
- Table structure and styling
- Currency formatting (₹ INR, $ USD)
- Profit/loss color coding
- Company grouping structure (if present in transaction list)

---

## CANONICAL DATA CONTRACT

### CanonicalLedgerService Output
**Source:** `backend/apps/license/services/canonical_ledger_service.py`

**Returned Structure:**
```python
{
    'opening_balance': Decimal('1000.00'),
    'closing_balance': Decimal('500.00'),
    'license_running_balance': Decimal('500.00'),
    'transactions': [
        {
            'date': datetime.date(2026-01-15),
            'type': 'PURCHASE',
            'company_id': 123,
            'company_name': 'Supplier A',
            'debit_cif': Decimal('1000.00'),
            'credit_cif': Decimal('0.00'),
            'debit_amount_inr': Decimal('85500.00'),
            'credit_amount_inr': Decimal('0.00'),
            'license_running_balance': Decimal('1000.00'),
            'affects_balance': True,
            'profit_loss': Decimal('0.00'),
            'invoice_number': 'INV-001',
            'particular': 'Purchase from Supplier A',
        },
        # ... more transactions
    ],
    'company_utilizations': {
        123: {
            'company_id': 123,
            'company_name': 'Supplier A',
            'company_running_balance': Decimal('1000.00'),
            'purchases': Decimal('1000.00'),
            'sales': Decimal('0.00'),
        },
        # ... other companies
    },
    'totals': {
        'total_debit_cif': Decimal('10000.00'),
        'total_credit_cif': Decimal('5000.00'),
        'total_debit_amount_inr': Decimal('855000.00'),
        'total_credit_amount_inr': Decimal('427500.00'),
        'total_profit_loss': Decimal('500.00'),
    }
}
```

**Key Differences:**
- Running balance: Already calculated, per transaction
- Commission: `affects_balance` flag indicates commission status
- Company utilization: Separate `company_utilizations` object (not per-transaction)
- Decimal precision: Exact 2 decimal places, ROUND_HALF_UP
- Ordering: Pre-ordered (date ASC, transaction_id ASC)

---

## MIGRATION DECISION MATRIX

| Aspect | Current | Canonical | Action |
|--------|---------|-----------|--------|
| **Data Source** | LicenseTrade.objects.filter() | CanonicalLedgerService | REPLACE |
| **Balance Calc** | Independent loop (lines 100–227) | Provided per transaction | REMOVE loop, use `license_running_balance` |
| **Commission** | Included in balance | Flagged with `affects_balance` | PRESERVE flag, display |
| **Scope** | License-wide | License-wide | ALIGN ✅ |
| **Ordering** | Manual sort (line 110) | Pre-ordered | USE canonical order |
| **Decimal** | float | Decimal | CONVERT to float for formatting |
| **Formatting** | `format_indian_number()` | String conversion needed | PRESERVE function |
| **PDF Structure** | ReportLab tables | ReportLab tables | NO CHANGE |

---

## HARD STOP VERIFICATION GATES

### Before Implementation
- ✅ CanonicalLedgerService exists and provides all required fields
- ✅ Canonical service supports company_id filtering (Phase 4E-B scope)
- ✅ Tests exist for canonical service
- ✅14 golden scenarios documented

### During Implementation
- ❌ DO NOT modify API responses
- ❌ DO NOT change PDF layout or presentation
- ❌ DO NOT alter authorization/security checks
- ❌ DO NOT change field names or types in transaction dicts (if avoidable)
- ❌ DO NOT touch frontend PDF/Excel exporters
- ❌ DO NOT modify database or migrations

### After Implementation
- ✅ Zero independent balance calculations in backend PDF
- ✅ 14 golden scenarios pass
- ✅ All financial values match canonical
- ✅ No N+1 query regressions
- ✅ No performance degradation
- ✅ Authorization unchanged

---

## BASELINE METRICS

### Current Performance
| Metric | Value | Evidence |
|--------|-------|----------|
| DB Queries | 20–50 per PDF | `get_license_transactions()` + trades filtering |
| Query Type | SELECT + prefetch | `prefetch_related('lines__sr_number')` |
| Calculation | Per-transaction | 100–227 in `get_license_transactions()` |
| Memory | 50–100MB | Transaction list buffering |
| PDF Size | 100–500KB | ReportLab output, 1 page per license |

### Expected Changes
| Metric | Current | Post-Canonical | Target |
|--------|---------|---|---|
| DB Queries | 20–50 | ~10–15 | ✅ Reduce N+1 |
| Query Type | Multiple | Single canonical call | ✅ Centralized |
| Calculation | Per-transaction loop | Provided in dataset | ✅ Eliminate |
| Memory | 50–100MB | 40–80MB | ✅ Slight reduction |
| PDF Size | 100–500KB | No change | ✅ Preserve |

---

## IMPLEMENTATION SCOPE

### Phase 4E-B Deliverables
1. **Migrate data source:** Replace `get_license_transactions()` with CanonicalLedgerService call
2. **Remove balance calculation:** Delete lines 100–227 logic from `get_license_transactions()`
3. **Adapt transaction dict:** Map canonical fields to current dict structure (or update all consumers)
4. **Test golden scenarios:** Verify 14 scenarios produce identical financial values
5. **Verify security:** Ensure authorization unchanged
6. **Performance check:** Record baseline metrics post-migration

### Related Code NOT Changed in Phase 4E-B
- Frontend PDF/Excel (ledgerExport.js) — Phase 4E-C
- API responses (CanonicalLedgerSerializer) — Phase 4C (complete)
- Database schema — No changes
- Authorization layers — Preserved

---

## GOLDEN SCENARIOS REFERENCE

| Scenario | Input | Expected Canonical Output | PDF Contract |
|----------|-------|---|---|
| 1 | Single company, 5 purchases | Running balance: 5000, P/L: 0 | ✅ Display balance |
| 2 | Multiple companies | Separate company records | ✅ Group by company |
| 3 | Commission-only | 10 commission txns, balance: 0 | ✅ Include with flag |
| 4 | Company isolation | Company A balance ≠ total | ✅ Use canonical |
| 5 | Decimal precision | 2 places exactly | ✅ Format correctly |
| 6 | Ordering | Date ASC, ID ASC | ✅ Preserve order |
| 7 | Zero amount | 1 zero-valued txn | ✅ Display row |
| 8 | Large dataset | 1000+ txns | ✅ Pagination OK |
| 9 | Empty ledger | No txns | ✅ Empty PDF |
| 10 | Commission-only | Balance: 0 | ✅ Not affected |
| 11 | Opening + closing | Opening balance visible | ⚠️ Canonical provides |
| 12 | Interleaved companies | Company A, B, A | ✅ All separate |
| 13 | Multi-company + commission | Companies + commission | ✅ Correct balance |
| 14 | Comprehensive | Real-world license | ✅ All values match |

---

## NEXT STEPS AFTER BASELINE

1. **Read forensic documents** (already done)
2. **Examine current backend PDF code** (done at lines 43–1454)
3. **Identify migration points** (get_license_transactions, generate_detailed_licenses_pdf)
4. **Implement canonical migration** (this phase)
5. **Test with golden scenarios** (verification gate)
6. **Create migration report** (after-implementation audit)
7. **Hard stop before Phase 4E-C** (frontend PDF)

---

**Baseline Status:** ✅ DOCUMENTED  
**Ready for:** Implementation

