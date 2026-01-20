from django.db.models import Sum, Q

from core.constants import N2015
from core.utils.decimal_utils import round_decimal_down as round_down


def _get_aggregated_values(instance):
    """
    Perform all aggregate queries in a single pass to improve performance.
    Returns a dict with all calculated values.

    This replaces 6 separate database queries with just 2 queries.
    """
    # Single query for all item_details aggregations
    item_agg = instance.item_details.aggregate(
        debited_qty=Sum('qty', filter=Q(transaction_type='D')),
        debited_value=Sum('cif_fc', filter=Q(transaction_type='D'))
    )

    # Single query for all allotment_details aggregations
    allot_agg = instance.allotment_details.aggregate(
        aro_qty=Sum('qty', filter=Q(allotment__type='ARO')),
        aro_value=Sum('cif_fc', filter=Q(allotment__type='ARO')),
        allotted_qty=Sum('qty', filter=Q(
            allotment__bill_of_entry__isnull=True,
            allotment__type='AT'
        )),
        allotted_value=Sum('cif_fc', filter=Q(
            allotment__bill_of_entry__isnull=True,
            allotment__type='AT'
        ))
    )

    return {
        'debited_qty': float(item_agg['debited_qty'] or 0),
        'debited_value': float(item_agg['debited_value'] or 0),
        'aro_qty': float(allot_agg['aro_qty'] or 0),
        'aro_value': float(allot_agg['aro_value'] or 0),
        'allotted_qty': float(allot_agg['allotted_qty'] or 0),
        'allotted_value': float(allot_agg['allotted_value'] or 0)
    }


def calculate_available_quantity(instance, agg_values=None):
    if agg_values is None:
        agg_values = _get_aggregated_values(instance)

    credit = float(instance.quantity or 0)

    # Use prefetched data if available, otherwise query
    try:
        items = list(instance.items.all())  # Use prefetched data
        first_item = items[0] if items else None
    except Exception:
        first_item = instance.items.first() if instance.items.exists() else None

    # Check if first item has restrictions (sion_norm_class and restriction_percentage)
    if first_item and first_item.sion_norm_class and first_item.restriction_percentage > 0:
        if instance.old_quantity or instance.license.notification_number == N2015:
            credit = float(instance.old_quantity or instance.quantity or 0)

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
    from license.models import LicenseImportItemsModel
    from license.services.balance_calculator import LicenseBalanceCalculator

    # Use the centralized calculator directly to avoid recursion through properties
    available_value = LicenseBalanceCalculator.calculate_balance(instance.license)
    balance_value = available_value

    # Business Logic: If all items OTHER THAN serial_number = 1 have CIF = 0,
    # then serial_number 1's available_value should be balance_cif
    if instance.license:
        all_import_items = LicenseImportItemsModel.objects.filter(license=instance.license)

        # Get all items except serial_number = 1
        other_items = [item for item in all_import_items if item.serial_number != 1]

        # Check if all other items (not serial_number 1) have zero CIF
        all_others_zero_cif = all(
            float(item.cif_fc or 0) == 0 and float(item.cif_inr or 0) == 0
            for item in other_items
        ) if other_items else False

        # If all other items have zero CIF, and this is serial_number 1
        if all_others_zero_cif and instance.serial_number == 1:
            # Return the license's balance_cif (use stored value to avoid recursion)
            return round(float(instance.license.balance_cif or 0), 2)

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
        license = item.license
        balance_cif = license.get_balance_cif
        if balance_cif < Decimal("100") and not license.is_null:
            license.is_null = True
            license.save(update_fields=['is_null'])
