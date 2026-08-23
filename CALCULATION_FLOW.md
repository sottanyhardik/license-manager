# Calculation Flow and Data Dependencies

**Purpose**: Visual reference for how calculations chain together.

---

## Balance Calculation Data Flow

```
LicenseDetailsModel.get_balance_cif (authoritative property)
  ↓
LicenseBalanceCalculator.calculate_financial_balance(license)
  ├─ calculate_opening_balance()
  │   ├─ calculate_credit()
  │   │   └─ SUM(LicenseExportItemModel.cif_fc)
  │   ├─ calculate_hidden_boe_debit_total()
  │   │   └─ RowDetails.cif_fc [transaction_type=D, hidden=True]
  │   └─ calculate_purchase_credit()
  │       └─ LicenseTradeLine.cif_fc [direction=PURCHASE]
  ├─ calculate_purchase_credit()
  │   └─ LicenseTradeLine.cif_fc [direction=PURCHASE]
  ├─ calculate_trade()
  │   └─ LicenseTradeLine.cif_fc [direction=SALE]
  ├─ calculate_debit() ← ALLOCATION-DRIVEN
  │   └─ get_debit_rows()
  │       ├─ RowDetails [sr_number.license=lic, transaction_type=D, !hidden]
  │       └─ Annotate each row:
  │           ├─ allocated = SUM(InvoiceBOEAllocation.allocated_cif_fc
  │           │              [status=ACTIVE, is_current=True])
  │           ├─ linked_excluded = cif_fc (if BOE in represented_set AND allocated=0)
  │           │                  = 0 (else)
  │           ├─ matched = min(cif_fc, allocated + linked_excluded)
  │           └─ contributed = max(cif_fc - matched, 0)
  │       └─ SUM(contributed)
  └─ calculate_allotment()
      └─ AllotmentItems.cif_fc [item.license=lic, allotment.bill_of_entry IS NULL]

Result: quantize_2dp(opening + purchase - sale - debit - allotment), floor at 0
```

---

## BOE Representation (Debit Exclusion)

```
LicenseBalanceCalculator.resolve_boes_represented_by_invoice(license)
  ├─ From InvoiceBOEAllocation (ACTIVE, is_current=True)
  │   └─ row_details.bill_of_entry_id
  │       for row_details.sr_number.license = license
  └─ From legacy trade.boes tag (visible only)
      └─ LicenseTrade [direction=SALE, boes__isnull=False]
          .lines filter: sr_number.license = license
          then annotate_and_exclude_hidden(trade.boes)

Result: {bill_of_entry_id, ...} set for this licence

Impact on debit_rows annotation:
  linked_excluded = cif_fc if (bill_of_entry_id in represented_set AND allocated=0)
                  = 0 otherwise
```

---

## Item Availability / Condition Pool Flow

```
LicenseDetailsModel.get_restriction_balances()
  ↓
condition_pool.compute_condition_pools(license)
  ├─ License credit = calculate_credit()
  ├─ For each condition_type = "N%" on import items:
  │   ├─ pool = N% × credit
  │   ├─ Find items with this condition_type
  │   ├─ debited = SUM(RowDetails.cif_fc [sr_number in group, D, !hidden])
  │   ├─ allotted = SUM(AllotmentItems.cif_fc [item in group, bill_of_entry IS NULL])
  │   ├─ traded = SUM(LicenseTradeLine.cif_fc [sr_number in group, SALE])
  │   ├─ used = debited + allotted + traded
  │   └─ remaining = max(pool - used, 0)
  └─ Return {condition_type: remaining, ...}

For any import item:
  available_value = min(
    condition_pool.remaining[item.condition_type],
    license.get_balance_cif
  )
```

---

## Auto-Plan Waterfall (A3627 Example)

```
compute_a3627_auto_plan(license)
  ├─ ensure_plan_item_names(4 categories)
  ├─ Load import items [select_related(hs_code), prefetch(items), order_by(serial)]
  ├─ remaining_cif = license.get_balance_cif
  ├─ Classify raw items into 4 categories via item_matcher.get_item_filters()
  ├─ For each category bucket:
  │   └─ Group via merge_items_for_classification()
  │       → {representative_id, member_ids, available_qty}
  ├─ For each priority (RUTILE → TITANIUM → SODA → PP):
  │   └─ For each group in that priority:
  │       ├─ price = get_price_for_priority() [rutile: 2.50 or 3.50 based on avg]
  │       ├─ qty = available_qty
  │       ├─ planned_qty, planned_cif = _allocate_fixed_rate(qty, price, remaining_cif)
  │       ├─ validate via validate_group_plan_lines()
  │       ├─ Save LicenseItemPlan on representative_id
  │       └─ remaining_cif -= planned_cif
  └─ Return [(lines...), remaining_cif]
```

---

## Planning Item Grouping

```
merge_items_for_classification(import_items)
  └─ For each item:
      ├─ key = plan_group_key(item)
      │   ├─ IF description: "{norm_hsn}|{norm_desc}"
      │   ├─ ELSE IF names: "{norm_hsn}|N:{sorted_names}"
      │   └─ ELSE: "ID:{id}"
      └─ Group by key
  └─ For each group:
      ├─ representative_id = min(member_ids, key=serial_number)
      ├─ member_ids = sorted(all ids in group)
      ├─ item_names = sorted union of all tags
      └─ available_quantity = SUM(available_qty)

Result: {representative_id, member_ids, hs_code, description, item_names, available_qty}
```

---

## Allocation Service Constraints

```
AllocationService.calculate_max_allocation(allotment, import_item, unit_price)
  ├─ Constraints:
  │   ├─ balanced_qty = allotment.balanced_quantity
  │   ├─ available_qty = ItemBalanceCalculator.calculate_available_quantity(item)
  │   ├─ balance_cif_fc = ItemBalanceCalculator.calculate_item_balance(item)
  │   ├─ balanced_value_with_buffer = allotment.required_value_with_buffer - allotted
  │   └─ unit_price (given or allotment.unit_value_per_unit)
  └─ Result:
      max_qty = min(balanced_qty, available_qty)
      max_value = max_qty * unit_price
      IF max_value > balance_cif_fc:
        max_qty = floor(balance_cif_fc / unit_price)
      IF max_qty * unit_price > balanced_value_with_buffer:
        max_qty = floor(balanced_value_with_buffer / unit_price)
      RETURN max_qty, max_qty * unit_price

Is used to prevent:
  - Over-allotting quantity beyond available
  - Over-allocating CIF value beyond item balance
  - Exceeding allotment's buffer-padded requirement
```

---

## Reconciliation Query Flow

```
ReconciliationViewSet.summary()
  ├─ missing_boe() → LicenseTradeLine [!boes linked, direction=SALE]
  ├─ missing_invoice() → RowDetails [invoice_no blank]
  ├─ duplicate_debits() → same BOE + item, 2+ trade lines
  ├─ duplicate_boes() → near-identical BOEs (CIF within tolerance)
  ├─ cif_comparison() → trade.cif_fc vs BOE.cif_fc mismatch
  ├─ qty_comparison() → trade.qty vs BOE.qty mismatch
  ├─ multi_boe_per_invoice() → 1 trade, 2+ BOEs
  └─ multi_invoice_per_boe() → 1 BOE, 2+ trades

User action:
  → allocation_service.create_invoice_boe_allocation()
    or allocation_service.create_boe_allotment_allocation()
    → ReconciliationLog [action=ALLOCATE, before={}, after={...}]
    → Debit recalculated on next balance query
```

---

## Key Transaction Points

### Point A: Auto-Plan Save
```
LicenseItemPlan.save()
  ├─ mark old is_current=False
  ├─ create new is_current=True on representative_id
  ├─ does NOT immediately recalculate balance
  └─ balance updated on next get_balance_cif call
```

### Point B: Allocation Save
```
InvoiceBOEAllocation.save() [inside transaction.atomic()]
  ├─ row-level locking (SELECT ... FOR UPDATE)
  ├─ check remaining_for_row_details_invoice_side() >= allocated_cif
  ├─ check over-allocation does not occur
  ├─ if edit: mark old is_current=False, superseded_by=new
  ├─ ReconciliationLog written same transaction
  └─ debit() recalculates via get_debit_rows() on next call
```

### Point C: Balance Recalculation Trigger
```
Every call to:
  - license.get_balance_cif (property, recalculates every time)
  - license.balance_cif (cached field, updated by signal or explicit update)
  - LicenseBalance.balance_cif (explicit row update)

Triggers:
  - When new RowDetails created
  - When LicenseTradeLine created
  - When LicenseItemPlan created
  - When InvoiceBOEAllocation created/edited/reversed
  - When AllotmentItems created
  - Manual recalculate action in reconciliation panel
```

---

## Caching and Invalidation

```
LicenseDetailsModel
  ├─ balance_cif (property, live calculation)
  │   └─ reads LicenseBalance.balance_cif (cached field)
  ├─ get_balance_cif (property, recalculates every time)
  │   └─ calls calculate_financial_balance()
  ├─ opening_balance (cached_property)
  │   └─ set via @cached_property, persists for lifetime
  ├─ get_norm_class (cached_property)
  │   └─ CSV of SION norms on export items

Signal-driven update:
  post_save on RowDetails → trigger balance update task (or sync in V2)
  post_save on LicenseTradeLine → similar
  post_save on LicenseItemPlan → similar
```

---

## Test Coverage Checklist

| Area | Test File | Key Assertions |
|------|-----------|-----------------|
| **Balance Consistency** | `test_balance_cif_single_source.py` | Export → Credit, BOE → Debit |
| **Item Pivot** | `test_item_pivot_balance_consistency.py` | Group totals match item sums |
| **Allocation** | `test_allocate_items_*.py` | Qty cap, CIF cap, group plan cap, E1/E126/E132 rules |
| **E1 Plan** | `test_e1_auto_plan.py` | Parity, grouping, idempotency, preservation |
| **E126 Plan** | `test_e126_auto_plan.py` | 50/50 split, wastage rebalance, fractional invariant |
| **E132 Plan** | `test_e132_auto_plan.py` | 40/60 split, wastage rebalance, fractional invariant |
| **A3627 Plan** | `test_a3627_auto_plan.py` | 4-priority waterfall, rutile avg price, rounding |
| **Reconciliation** | `test_reconciliation.py` | Missing BOE/invoice, duplicate debits, CIF mismatch |
| **Allocation Service** | `test_allocation_service.py` | Partial allocation, unmatched remainder, over-allocation rejection |
| **Plan Grouping** | `test_plan_grouping.py` | Merge key normalization, representative selection, validation gates |

