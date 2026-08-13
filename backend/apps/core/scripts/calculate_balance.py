from django.db.models import Sum, Q

from apps.core.constants import DEBIT
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
    from apps.license.services.balance_calculator import ItemBalanceCalculator, LicenseBalanceCalculator

    prefetch_cache = getattr(instance, '_prefetched_objects_cache', {})

    # ------------------------------------------------------------------ #
    # item_details (RowDetails): debited rows only                        #
    # Prefetch-cache path: zero extra queries, exact same result as SQL.  #
    # ------------------------------------------------------------------ #
    if 'item_details' in prefetch_cache:
        rows = prefetch_cache['item_details']
        debited_qty = sum(float(r.qty or 0) for r in rows if r.transaction_type == DEBIT)
        debited_value = sum(float(r.cif_fc or 0) for r in rows if r.transaction_type == DEBIT)
    else:
        item_agg = instance.item_details.aggregate(
            debited_qty=Sum('qty', filter=Q(transaction_type=DEBIT)),
            debited_value=Sum('cif_fc', filter=Q(transaction_type=DEBIT))
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
    direct_sale_qty = ItemBalanceCalculator.calculate_direct_sale_quantity(instance)

    return {
        'debited_qty': debited_qty,
        'debited_value': debited_value,
        'aro_qty': to_float(aro_agg['aro_qty']),
        'aro_value': to_float(aro_agg['aro_value']),
        'allotted_qty': to_float(allotted_qty),
        'allotted_value': to_float(allotted_value),
        'direct_sale_qty': to_float(direct_sale_qty),
    }


def calculate_available_quantity(instance, agg_values=None):
    """
    Available Quantity = current stored licence item quantity − Debited −
    Outstanding (unlinked) Allotted, and direct SALE quantity (a SALE with
    no BOE), floored at 0. A BOE-linked sale is excluded because its BOE is
    already the physical debit.

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
    direct_sale_qty = agg_values['direct_sale_qty']
    value = round_down(credit - debited - allotted - direct_sale_qty, 0)
    return max(round(value, 2), 0)


def calculate_debited_quantity(instance, agg_values=None):
    if agg_values is None:
        agg_values = _get_aggregated_values(instance)
    return round(agg_values['debited_qty'] + agg_values['aro_qty'] + agg_values['direct_sale_qty'], 2)


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
    """
    Single source of truth: `LicenseImportItemsModel.available_value_calculated`
    (condition_type `%`-pool + 0.01-CIF-marker aware) — the same property
    `apps.license.signals._update_all_import_items_available_value` writes
    from the item-save signal. Previously this re-derived its own formula
    (a bare `LicenseBalanceCalculator.calculate_balance()` call, blind to
    both the pool and marker rules), which could disagree with that other
    writer for restricted/marker items. The one carve-out that ISN'T part
    of the pooled property: if every OTHER item on the licence has zero
    CIF, serial_number 1 takes the licence's full balance directly.

    BL-LEDGER-02: that "full balance" now reads the LIVE
    `LicenseBalanceCalculator.calculate_financial_balance()` figure rather
    than `instance.license.balance_cif` (the denormalized `LicenseBalance`
    cache) — the cache has no signal on reconciliation-allocation changes
    and can go stale, while this rule's business semantics ("serial 1
    absorbs the licence's full balance when nothing else carries CIF")
    are unchanged; only the source of "full balance" is now guaranteed
    live instead of potentially stale.
    """
    from apps.license.models import LicenseImportItemsModel
    from apps.license.services.balance_calculator import LicenseBalanceCalculator

    if instance.license:
        all_import_items = LicenseImportItemsModel.objects.filter(license=instance.license)
        other_items = [item for item in all_import_items if item.serial_number != 1]
        all_others_zero_cif = all(
            to_float(item.cif_fc) == 0 and to_float(item.cif_inr) == 0
            for item in other_items
        ) if other_items else False

        if all_others_zero_cif and instance.serial_number == 1:
            live_balance = LicenseBalanceCalculator.calculate_financial_balance(instance.license)
            return round(to_float(live_balance), 2)

    return round(to_float(instance.available_value_calculated), 2)


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
