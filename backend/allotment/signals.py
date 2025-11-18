# allotment/signals.py
from decimal import Decimal
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import Sum, DecimalField, Value
from django.db.models.functions import Coalesce
from allotment.models import AllotmentItems

DEC_0 = Decimal("0")
DEC_000 = Decimal("0.000")


def update_license_balance(license_item):
    """
    Update the available_quantity and available_value for a license item
    based on allotments that are not yet BOE.
    Also updates license is_null flag if balance_cif < 100.

    CRITICAL: For restricted items, available_value must respect restriction limits
    and NEVER exceed balance_cif_fc.
    """
    if not license_item:
        return

    # Calculate total allotted quantity and value (excluding BOE)
    allotment_totals = license_item.allotment_details.filter(
        is_boe=False
    ).aggregate(
        total_qty=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()),
        total_value=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
    )

    allotted_qty = allotment_totals['total_qty'] or DEC_000
    allotted_value = allotment_totals['total_value'] or DEC_0

    # Update allotted fields
    license_item.allotted_quantity = allotted_qty
    license_item.allotted_value = allotted_value

    # Calculate available balance: quantity - debited - allotted
    available_qty = license_item.quantity - license_item.debited_quantity - allotted_qty
    available_val = license_item.cif_fc - license_item.debited_value - allotted_value

    # Ensure non-negative
    license_item.available_quantity = available_qty if available_qty >= DEC_000 else DEC_000
    calculated_available_value = available_val if available_val >= DEC_0 else DEC_0

    # CRITICAL: Check if item has restrictions
    has_restriction = license_item.items.filter(
        head__is_restricted=True,
        head__restriction_norm__isnull=False,
        head__restriction_percentage__gt=DEC_0
    ).exists()

    if has_restriction:
        # For restricted items, use balance_cif_fc which includes restriction logic
        # This ensures we never exceed the restriction limit
        restriction_balance = Decimal(str(license_item.balance_cif_fc or 0))
        # Use minimum of calculated and restriction balance
        license_item.available_value = min(calculated_available_value, restriction_balance)
    else:
        # For non-restricted items, use the calculated value
        license_item.available_value = calculated_available_value

    # CRITICAL: available_value should NEVER exceed balance_cif_fc under any circumstance
    balance_cif_fc = Decimal(str(license_item.balance_cif_fc or 0))
    if license_item.available_value > balance_cif_fc:
        license_item.available_value = balance_cif_fc

    license_item.save(update_fields=['allotted_quantity', 'allotted_value', 'available_quantity', 'available_value'])

    # Check and update license is_null if balance_cif < 100
    if license_item.license:
        license = license_item.license
        balance_cif = license.get_balance_cif
        if balance_cif < Decimal("100") and not license.is_null:
            license.is_null = True
            license.save(update_fields=['is_null'])


@receiver(post_save, sender=AllotmentItems)
def update_is_allotted_on_save(sender, instance, created, **kwargs):
    """
    Update is_allotted to True when an AllotmentItems is created or updated
    Also update the license item's available balance
    """
    # Prevent recursive signal calls
    if kwargs.get('raw', False):
        return

    if instance.allotment:
        instance.allotment.is_allotted = True
        instance.allotment.save(update_fields=['is_allotted'])

    # Update license item balance
    if instance.item:
        update_license_balance(instance.item)


@receiver(post_delete, sender=AllotmentItems)
def update_is_allotted_on_delete(sender, instance, **kwargs):
    """
    Update is_allotted to False if no more AllotmentItems exist for this allotment
    Also update the license item's available balance
    """
    if instance.allotment:
        # Check if there are any remaining allotment_details
        has_details = instance.allotment.allotment_details.exists()
        instance.allotment.is_allotted = has_details
        instance.allotment.save(update_fields=['is_allotted'])

    # Update license item balance
    if instance.item:
        update_license_balance(instance.item)
