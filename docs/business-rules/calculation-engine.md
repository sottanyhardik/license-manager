# Calculation Engine — Complete Reference

> **Every formula in the system with inputs, outputs, sources, and examples.**  
> Last updated: 2026-07-15.

---

## 1. License Balance CIF

**Formula**: `balance_cif = max(0, credit − debit − allotment − trade)`  
**Result precision**: Decimal(15,2), ROUND_DOWN  
**Unit**: Foreign currency (USD for DFIA)

| Variable | Formula | Data source | Filter |
|---|---|---|---|
| `credit` | `SUM(cif_fc)` | LicenseExportItemModel | WHERE license_id=X |
| `debit` | `SUM(cif_fc)` | RowDetails (BOE) | WHERE license_id=X (via sr_number) AND type='D' AND no trade link |
| `allotment` | `SUM(cif_fc)` | AllotmentItems | WHERE license_id=X (via item) AND allotment.bill_of_entry IS NULL |
| `trade` | `SUM(cif_fc)` | LicenseTradeLine | WHERE license_id=X (via sr_number) AND direction='SALE' |

**Triggers**: After allotment CRUD, after BOE row CRUD, manual recompute endpoint  
**Written to**: `LicenseBalance.balance_cif`  
**Celery task**: `recompute_license_balance_task(license_id)`

**Example**:
```
Export authorisation:  $50,000  (credit)
BOE imports so far:    $15,000  (debit)
Pending allotments:    $10,000  (allotment)
Trade sales:           $5,000   (trade)
─────────────────────────────────
Balance:               $20,000  = max(0, 50000 - 15000 - 10000 - 5000)
```

---

## 2. Import Item Available Quantity

**Formula**: `available_quantity = max(0, quantity − debited_quantity − allotted_quantity)`  
**Result precision**: Decimal(15,3), ROUND_DOWN  
**Unit**: Import quantity units (KG, NOS, etc.)

| Variable | Formula | Data source | Filter |
|---|---|---|---|
| `quantity` | Stored on item | LicenseImportItemsModel | Authorised quantity |
| `debited_quantity` | `SUM(qty)` | RowDetails | WHERE sr_number_id=X AND type='D' |
| `allotted_quantity` | `SUM(qty)` | AllotmentItems | WHERE item_id=X AND allotment.bill_of_entry IS NULL AND type='AT' |

**Written to**: `LicenseImportItemsModel.available_quantity` (and debited_, allotted_ fields)  
**Computed by**: `balance_service._update_item_level_balances()`  
**Called from**: Inside `recompute_license_balance()` in the same `transaction.atomic()`

**Example**:
```
Authorised quantity:   1000 KG
Already debited:        200 KG
Pending allotments:     100 KG
─────────────────────────────
Available:              700 KG = max(0, 1000 - 200 - 100)
```

---

## 3. LicenseTradeLine Amount

**Formula** (varies by billing mode):

| Mode | Formula | Variables |
|---|---|---|
| `CIF_INR` | `q2(cif_inr) × (Decimal(str(pct)) / 100)` | cif_inr, pct (3dp) |
| `FOB_INR` | `q2(fob_inr) × (Decimal(str(pct)) / 100)` | fob_inr, pct (3dp) |
| `QTY` | `q4(qty_kg) × q2(rate_inr_per_kg)` | qty_kg (4dp), rate_inr_per_kg (2dp) |

**Critical precision rule**: `pct` and `rate_pct` MUST be wrapped in `Decimal(str(value))` NOT `q2(value)` before dividing by 100. Using `q2()` would round to 2dp BEFORE division, losing 3dp precision.

**Example** (CIF_INR mode, pct=7.925):
```
pct = Decimal("7.925")   # 3dp precision preserved
cif_inr = 100,000.00
amount = q2(100000.00) × (7.925 / 100)
       = 100000.00 × 0.07925
       = 7925.00  ✓

# Wrong with q2(pct):
pct = q2(7.925) = 7.93  # rounded to 2dp BEFORE division!
amount = 100000.00 × (7.93 / 100) = 7930.00  ✗
```

---

## 4. IncentiveTradeLine Amount

Same billing modes as LicenseTradeLine, with `rate_pct` instead of `pct`:

| Mode | Formula |
|---|---|
| `CIF_INR` | `q2(cif_inr) × (Decimal(str(rate_pct)) / 100)` |
| `FOB_INR` | `q2(fob_inr) × (Decimal(str(rate_pct)) / 100)` |
| `QTY` | `q4(qty_kg) × q2(rate_inr_per_kg)` |

Same 3dp precision requirement for `rate_pct`.

---

## 5. LicenseTrade Total Amount

**Formula**: `total_amount_inr = SUM(all LicenseTradeLine.amount_inr) + SUM(all IncentiveTradeLine.amount_inr)`  
**Computed by**: `LicenseTrade.recompute_totals()` called in `LicenseTrade.save()`  
**Written to**: `LicenseTrade.total_amount_inr`

---

## 6. LicenseTrade Payment Status

**Formula**:  
`paid_or_received = SUM(LicenseTradePayment.amount WHERE trade_id=X)`  
`due_amount = total_amount_inr - paid_or_received`

Both are `cached_property` on `LicenseTrade` — computed on access, not stored.

---

## 7. BOE Exchange Rate

**Formula**: `exchange_rate = get_total_inr / get_total_fc`  
Where:
- `get_total_inr = SUM(RowDetails.cif_inr)`
- `get_total_fc = SUM(RowDetails.cif_fc)`

Computed in `BillOfEntryModel.save()`. Only updates when new rate differs by >1 from stored (prevents spurious writes). Also recomputed after every RowDetails save/delete via `recalc_exchange_rate_on_row_save` signal.

---

## 8. AllotmentModel Required Value

**Formula**: `required_value = required_quantity × unit_value_per_unit`  
Rounded to 2dp using `ROUND_HALF_UP`.  
**Type**: `cached_property` on AllotmentModel — not stored in DB.

---

## 9. AllotmentModel Balanced Quantity

**Formula**: `balanced_quantity = max(0, required_quantity - alloted_quantity)`  
**Type**: `cached_property` — not stored in DB.  
Represents remaining unfulfilled allotment quantity.

---

## 10. Dashboard KPI Statistics

All computed in `dashboard_service.get_dashboard_stats()` using a single conditional aggregation query:

```python
stats = LicenseDetailsModel.objects.aggregate(
    total_licenses=Count("pk"),
    active_licenses=Count("pk", filter=Q(flags__is_active=True, flags__is_expired=False, flags__is_null=False)),
    expired_licenses=Count("pk", filter=Q(flags__is_expired=True)),
    null_licenses=Count("pk", filter=Q(flags__is_null=True)),
    expiring_soon=Count("pk", filter=Q(
        flags__is_active=True,
        flags__is_expired=False,
        license_expiry_date__gte=today,
        license_expiry_date__lte=today + timedelta(days=30),
        balance__balance_cif__gte=Decimal("100.00")
    )),
    total_balance_cif_sum=Sum("balance__balance_cif"),
)
```

Additional separate aggregates:
- `recent_boes`: Count BOEs from last 30 days
- `recent_allotments`: Count allotments from last 30 days

**Cached for 5 minutes** via Django cache.

---

## 11. Dashboard Utilisation Chart

**Data**: Top 10 licenses by `balance_cif` descending  
**Query**: `LicenseDetailsModel.objects.select_related("balance", "flags").filter(balance__balance_cif__isnull=False).order_by("-balance__balance_cif")[:10]`  
**Output**: `[{license_number, balance_cif}, ...]`

---

## 12. Dashboard Monthly Activity

**Data**: BOE and allotment counts by month for last 12 months  
**Formula**: Group by month using Django's `TruncMonth`  
**Output**: `[{month: "2025-09", boe_count: 5, allotment_count: 3}, ...]`  
**Cached for 5 minutes**.

---

## 13. Dashboard Expiring Licenses

**Filter**:
- `flags__is_active=True`
- `flags__is_expired=False`
- `license_expiry_date >= today`
- `license_expiry_date <= today + 30 days`
- `balance__balance_cif >= 100.00`

**Sorted by**: `license_expiry_date ASC`  
**Output includes**: `days_to_expiry = (expiry_date - today).days`

---

## 14. LicenseItemPlan Remaining

Not stored as a field. Frontend computes visually:

```
Planned (displayed) = LicenseItemPlan.planned_quantity  (after allotment decrements)
Available = LicenseImportItemsModel.available_quantity   (after debit + allotment)
```

The `planned_quantity` field on LicenseItemPlan represents what's still available FOR FUTURE ALLOTMENTS. The `available_quantity` on LicenseImportItemsModel represents what's still available for actual imports.

---

## 15. Balance Report CIF (divergence from live balance)

⚠️ **Warning**: `reports/services/balance_report.py` re-implements balance aggregation instead of calling `balance_service._compute_*`. This can diverge from the live balance if the report service is not kept in sync.

**Report balance formula** (as implemented):
```python
# In balance_report.py:
total_authorised = SUM(LicenseExportItemModel.cif_fc)
debited_cif = SUM(RowDetails.cif_fc WHERE type=DEBIT)
allotted_cif = SUM(AllotmentItems.cif_fc WHERE no BOE)
available_cif = max(0, total_authorised - debited_cif - allotted_cif)
```

**Missing from report**: Trade component (`_compute_trade`). If any license has trade sales, the report will show a higher available than the live `balance_cif`.

**Recommendation**: Refactor `balance_report.py` to call `recompute_license_balance()` per license instead of reimplementing the formula.
