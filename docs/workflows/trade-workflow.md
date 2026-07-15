# Trade Workflow

> **End-to-end workflows for Trade module — purchase invoices and bills of supply.**

---

## Business Context

When a company buys or sells an advance license:
- **PURCHASE**: Company buys a DFIA license from another company → issues a Purchase Invoice
- **SALE**: Company sells (transfers) a DFIA license → issues a Bill of Supply

Both operations reduce the license balance (SALE reduces via `_compute_trade`; PURCHASE is for accounting only).

---

## Workflow 1: Create Trade (DFIA License Sale)

### Preconditions
- License exists with remaining balance
- From-company and To-company exist in masters
- User has `TRADE_MANAGER` role

### User Steps
1. Navigate to `/trades/new`
2. Select direction: **SALE** (or PURCHASE)
3. Select license type: **DFIA**
4. Enter: From Company, To Company, Invoice Date
5. Click "Prefill Invoice Number" → auto-generated `LM/YYYY-YY/{seq}`
6. Add DFIA trade lines: select SR (import item), set qty, CIF FC, choose mode
7. Add payment record (if upfront payment)
8. Review Financial Summary → "Create Trade"

### Backend Flow
```
POST /api/v1/trades/
  → TradePermission (TRADE_MANAGER required)
  → LicenseTradeSerializer.is_valid()
    → validates license type (DFIA vs INCENTIVE)
    → _sync_nested() for lines and payments
  → LicenseTrade.save()
    → snapshot_parties()  ← stores company name/address snapshot
    → recompute_totals()  ← computes total_amount_inr from all lines
  → For each line: LicenseTradeLine.save()
    → compute_amount() called unconditionally
    → amount_inr = Decimal(str(pct)) / 100 × cif_fc  [3dp precision]
```

### Database Changes
| Table | Change |
|---|---|
| `trade_licensetrade` | INSERT header with snapshot |
| `trade_licensetradelline` | INSERT per line, amount_inr computed |
| `trade_licensetradepayment` | INSERT per payment (if any) |

### Balance Impact (SALE only)
- `_compute_trade` increases by SUM(LicenseTradeLine.cif_fc WHERE direction='SALE')
- `balance_cif` decreases after next recompute
- **Note**: Trade does NOT automatically trigger balance recompute. It will be included in the next recompute (triggered by allotment or BOE changes, or manual recompute).

### Invoice Number Generation (Race-Safe)
```python
# trade/models.py:get_next_invoice_number()
with transaction.atomic():
    existing = LicenseTrade.objects.select_for_update().filter(
        invoice_number__startswith=pattern_prefix, ...
    ).values_list("invoice_number", flat=True)
    # compute max sequential number from existing
    # return next number
```

The `select_for_update()` prevents two concurrent requests from generating the same invoice number.

---

## Workflow 2: Edit Trade

### Constraints
- Can edit header fields and line items
- `amount_inr` is always recomputed on line save (no stale data possible)
- Invoice number cannot be changed once set

### Backend Flow
```
PUT/PATCH /api/v1/trades/{id}/
  → LicenseTradeSerializer.update()
    → _sync_nested() for lines:
      → update existing lines
      → delete removed lines
      → create new lines
    → LicenseTrade.save() → recompute_totals()
```

---

## Workflow 3: Generate Purchase Invoice PDF

### Preconditions
- Trade exists with PURCHASE direction
- From company has logo and company details set in masters
- User has `TRADE_MANAGER` role

### User Steps
1. Open trade detail page
2. Click "Generate Purchase Invoice PDF"
3. PDF downloads automatically to browser

### Backend Flow
```
GET /api/v1/trades/{id}/generate-purchase-invoice/
  → TradePermission
  → purchase_invoice_pdf.generate_purchase_invoice_pdf(trade)
    → Synchronous PDF generation (ReportLab)
    → Returns HttpResponse with PDF binary
```

### Frontend Implementation
```typescript
// Correct (authenticated blob download):
const response = await apiClient.get(ENDPOINTS.TRADES.PURCHASE_INVOICE_PDF(id), {
  responseType: 'blob'
})
const url = URL.createObjectURL(response.data as Blob)
const a = document.createElement('a')
a.href = url; a.download = `purchase-invoice-${id}.pdf`
a.click()
URL.revokeObjectURL(url)
```

⚠️ **Known Issue**: PDF generation is synchronous — blocks a gunicorn worker for several seconds. `generate_trade_pdf_task` Celery stub exists but is not connected. See improvement register H-001.

---

## Workflow 4: Link Trades (Bidirectional)

When one company sells a license, the counterpart creates a mirrored PURCHASE trade.

```
POST /api/v1/trades/{id}/link-trade/
  Body: {partner_trade_pk: 42}
  → trade_service.link_trades(trade_pk, partner_pk)
    → validates both trades exist
    → raises PartnerTradeNotFound if partner_pk not found
    → creates bidirectional link
```

---

## Incentive License Trade (RODTEP/ROSTL/MEIS)

Trades against incentive licenses use `IncentiveTradeLine` instead of `LicenseTradeLine`.

Key difference: `rate_pct` field (3dp precision) instead of `pct`.

Formula:
```
amount_inr = q2(license_value) × (Decimal(str(rate_pct)) / 100)
```

---

## Failure Scenarios

| Failure | HTTP | Message |
|---|---|---|
| Invoice number collision (race condition) | 409 | UniqueConstraint violation |
| PartnerTradeNotFound | 404 | "Partner trade not found" |
| PDF generation failure | 500 | Internal server error |
| Invalid mode for line | 400 | Validation error |
