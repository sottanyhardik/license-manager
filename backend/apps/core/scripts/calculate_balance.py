from django.db.models import Sum, Q

from apps.core.utils.decimal_utils import round_decimal_down as round_down, to_float


def _get_aggregated_values(instance):
    """
    Compute item-level debit/allotment aggregations.

    item_details (RowDetails):
      When the caller has prefetched 'item_details' the debited sums are computed
      in Python from the cache — zero extra queries. Filter is purely on
      transaction_type, a direct column with no FK traversal, so the Python
      result is bit-for-bit identical to the SQL SUM(... WHERE transaction_type='D').

    allotment_details (AllotmentItems):
      `allotted_qty`/`allotted_value` (AT-type, outstanding-only) are computed
      via `LicenseBalanceCalculator.get_outstanding_allotment_totals` — the
      SAME Balance Engine query (`Exists()` against the real `BillOfEntryModel
      .allotment` M2M, plus `BOEAllotmentAllocation` partial-allocation
      netting) the Financial/Customs Ledgers and Item Summary use, so this
      stored-field writer can never structurally drift from them. `aro_qty`/
      `aro_value` (ARO-type, folded into "debited" rather than "allotted" —
      unchanged business rule) stay a plain local aggregate; ARO allotments
      aren't subject to BOE-linking exclusion.
    """
    from apps.license.services.balance_calculator import LicenseBalanceCalculator

    prefetch_cache = getattr(instance, '_prefetched_objects_cache', {})

    # ------------------------------------------------------------------ #
    # item_details (RowDetails): debited rows only                        #
    # Prefetch-cache path: zero extra queries, exact same result as SQL.  #
    # ------------------------------------------------------------------ #
    if 'item_details' in prefetch_cache:
        rows = prefetch_cache['item_details']
        debited_qty = sum(float(r.qty or 0) for r in rows if r.transaction_type == 'D')
        debited_value = sum(float(r.cif_fc or 0) for r in rows if r.transaction_type == 'D')
    else:
        item_agg = instance.item_details.aggregate(
            debited_qty=Sum('qty', filter=Q(transaction_type='D')),
            debited_value=Sum('cif_fc', filter=Q(transaction_type='D'))
        )
        debited_qty = to_float(item_agg['debited_qty'])
        debited_value = to_float(item_agg['debited_value'])

    # ------------------------------------------------------------------ #
    # allotment_details (AllotmentItems): ARO stays a plain local aggregate;
    # AT (outstanding, BOE-link-excluded) delegates to the shared Balance
    # Engine helper — one extra query, but this function already runs
    # per-item (from a per-item save signal), so it's not a new N+1 pattern.
    # ------------------------------------------------------------------ #
    aro_agg = instance.allotment_details.aggregate(
        aro_qty=Sum('qty', filter=Q(allotment__type='ARO')),
        aro_value=Sum('cif_fc', filter=Q(allotment__type='ARO')),
    )
    allotted_qty, allotted_value = LicenseBalanceCalculator.get_outstanding_allotment_totals(instance)

    return {
        'debited_qty': debited_qty,
        'debited_value': debited_value,
        'aro_qty': to_float(aro_agg['aro_qty']),
        'aro_value': to_float(aro_agg['aro_value']),
        'allotted_qty': to_float(allotted_qty),
        'allotted_value': to_float(allotted_value),
    }


def calculate_available_quantity(instance, agg_values=None):
    """
    Available Quantity = current stored licence item quantity − Debited −
    Outstanding (unlinked) Allotted, floored at 0.

    Always uses `instance.quantity` (the current, possibly-amended licence
    item quantity) — NEVER `instance.old_quantity`. A prior restricted-item/
    notification-019-2015 branch substituted `old_quantity` (a frozen,
    pre-amendment snapshot) as the ceiling here, which silently reintroduced
    the item's ORIGINAL quantity after a licence amendment increased it —
    e.g. old_quantity=857, current quantity=2909.261, already debited=857:
    the old branch computed `857 - 857 = 0` (wrong — pinned to the obsolete
    baseline) instead of `2909.261 - 857 = 2052.261` (correct — reflects the
    amendment). Removed entirely; this is now the single, unconditional
    formula for every licence item, restricted or not.
    """
    if agg_values is None:
        agg_values = _get_aggregated_values(instance)

    credit = to_float(instance.quantity)
    debited = agg_values['debited_qty'] + agg_values['aro_qty']
    allotted = agg_values['allotted_qty']
    value = round_down(credit - debited - allotted, 0)
    return max(round(value, 2), 0)


def calculate_debited_quantity(instance, agg_values=None):
    if agg_values is None:
        agg_values = _get_aggregated_values(instance)
    return round(agg_values['debited_qty'] + agg_values['aro_qty'], 2)


def calculate_allotted_quantity(instance, agg_values=None):
    if agg_values is None:
        agg_values = _get_aggregated_values(instance)
    return round(agg_values['allotted_qty'], 2)


def calculate_debited_value(instance, agg_values=None):
    if agg_values is None:
        agg_values = _get_aggregated_values(instance)
    return round(agg_values['debited_value'] + agg_values['aro_value'], 2)


def calculate_allotted_value(instance, agg_values=None):
    if agg_values is None:
        agg_values = _get_aggregated_values(instance)
    return round(agg_values['allotted_value'], 2)


def calculate_available_value(instance):
    from apps.license.models import LicenseImportItemsModel
    from apps.license.services.balance_calculator import LicenseBalanceCalculator

    # Use the centralized calculator directly to avoid recursion through properties
    available_value = LicenseBalanceCalculator.calculate_balance(instance.license)

    # Business Logic: If all items OTHER THAN serial_number = 1 have CIF = 0,
    # then serial_number 1's available_value should be balance_cif
    if instance.license:
        all_import_items = LicenseImportItemsModel.objects.filter(license=instance.license)

        # Get all items except serial_number = 1
        other_items = [item for item in all_import_items if item.serial_number != 1]

        # Check if all other items (not serial_number 1) have zero CIF
        all_others_zero_cif = all(
            to_float(item.cif_fc) == 0 and to_float(item.cif_inr) == 0
            for item in other_items
        ) if other_items else False

        # If all other items have zero CIF, and this is serial_number 1
        if all_others_zero_cif and instance.serial_number == 1:
            # Return the license's balance_cif (use stored value to avoid recursion)
            return round(to_float(instance.license.balance_cif), 2)

    # NOTE: This logic is now handled by available_value_calculated property in the model
    # which uses restriction_percentage directly from ItemNameModel
    # Keeping this for backward compatibility but it should delegate to the model property
    value = available_value
    return round(value, 2)


def update_balance_values(item):
    from decimal import Decimal

    # OPTIMIZATION: Get all aggregated values in just 2 queries instead of 6
    agg_values = _get_aggregated_values(item)

    values = {
        'available_quantity': calculate_available_quantity(item, agg_values),
        'debited_quantity': calculate_debited_quantity(item, agg_values),
        'allotted_quantity': calculate_allotted_quantity(item, agg_values),
        'allotted_value': calculate_allotted_value(item, agg_values),
        'debited_value': calculate_debited_value(item, agg_values),
        'available_value': calculate_available_value(item),
    }

    # Flags if a value has changed
    is_changed = False

    # Iterate over each item in the dictionary
    for attr, value in values.items():
        # If the item's current value is different from the new value, update it
        if float(getattr(item, attr)) != float(value):
            setattr(item, attr, value)
            is_changed = True

    # CRITICAL: Ensure available_value never exceeds balance_cif_fc
    balance_cif_fc = Decimal(str(item.balance_cif_fc or 0))
    current_available = Decimal(str(item.available_value or 0))
    if current_available > balance_cif_fc:
        item.available_value = balance_cif_fc
        is_changed = True

    # If any values have been changed, save the item
    # Use update_fields to only save changed fields and avoid triggering full model validation
    if is_changed:
        item.save(update_fields=[
            'available_quantity', 'debited_quantity', 'allotted_quantity',
            'allotted_value', 'debited_value', 'available_value'
        ])

    # Check and update license is_null if balance_cif < 100
    if item.license:
        from apps.license.models import LicenseFlags

        license = item.license
        balance_cif = license.get_balance_cif
        is_null = balance_cif < Decimal("100")
        if license.is_null != is_null:
            LicenseFlags.objects.update_or_create(
                license=license,
                defaults={'is_null': is_null},
            )
