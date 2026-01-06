# allotment/signals.py
from decimal import Decimal

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from allotment.models import AllotmentItems


def update_license_balance(license_item):
    """
    Update balance values for a license item using the optimized calculation function.
    This replaces the old manual calculation with the centralized, optimized version.
    """
    if not license_item:
        return

    from core.scripts.calculate_balance import update_balance_values
    update_balance_values(license_item)


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


@receiver(pre_delete, sender=AllotmentItems)
def update_is_allotted_on_delete(sender, instance, **kwargs):
    """
    Update is_allotted to False if no more AllotmentItems exist for this allotment
    Also update the license item's available balance
    """
    # Use try-except to handle case where allotment is being cascade-deleted
    try:
        if instance.allotment:
            # Check if allotment still exists in database
            from allotment.models import AllotmentModel
            if AllotmentModel.objects.filter(pk=instance.allotment.pk).exists():
                # Check if there are any remaining allotment_details
                has_details = instance.allotment.allotment_details.exists()
                if has_details:
                    instance.allotment.allotment_details.delete()
    except Exception as e:
        # Allotment is being deleted, skip the update
        pass

    # Update license item balance
    if instance.item:
        try:
            update_license_balance(instance.item)
        except Exception:
            # Item might be deleted or in invalid state, skip
            pass
