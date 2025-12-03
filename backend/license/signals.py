# license/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal
from license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel


def update_license_flags(license_instance):
    """
    Helper function to update is_null and is_expired flags for a license.
    """
    needs_update = False

    # Update is_expired based on license_expiry_date
    if license_instance.license_expiry_date:
        new_is_expired = license_instance.license_expiry_date < timezone.now().date()
        if license_instance.is_expired != new_is_expired:
            needs_update = True
            license_instance.is_expired = new_is_expired

    # Update is_null based on balance_cif
    try:
        balance = license_instance.get_balance_cif
        new_is_null = balance <= Decimal('0.01')  # Consider <= 0.01 as null
        if license_instance.is_null != new_is_null:
            needs_update = True
            license_instance.is_null = new_is_null
    except Exception:
        pass  # If balance calculation fails, skip

    # Save if flags changed (use update to avoid triggering signal again)
    if needs_update:
        LicenseDetailsModel.objects.filter(pk=license_instance.pk).update(
            is_expired=license_instance.is_expired,
            is_null=license_instance.is_null
        )


@receiver(post_save, sender=LicenseDetailsModel)
def auto_fetch_import_items(sender, instance, created, **kwargs):
    """
    Automatically link ItemNameModel items to existing LicenseImportItemsModel when a license is saved.
    Also updates is_null and is_expired flags.
    This works like populate_license_items command - matches based on description/HS filters and norm class.
    """
    # Prevent infinite recursion by checking if we're already in a save
    if kwargs.get('raw', False):
        return

    # Update license flags
    update_license_flags(instance)

    # Only auto-link items if import items exist
    if not instance.import_license.exists():
        return

    # Get license export norm classes
    license_norm_classes = list(
        instance.export_license.values_list('norm_class__norm_class', flat=True).distinct()
    )

    if not license_norm_classes:
        return

    # Get all ItemNameModel items that match the license norm classes
    from core.models import ItemNameModel
    from django.db.models import Q

    matching_items = ItemNameModel.objects.filter(
        sion_norm_class__norm_class__in=license_norm_classes
    )

    if not matching_items.exists():
        return

    # For each ItemNameModel, find and link matching import items
    for item_name in matching_items:
        # Build filter based on description/HS code patterns
        # This is simplified - in production you'd want the full filter logic from populate_license_items
        description_filter = Q(description__icontains=item_name.name.split(' - ')[0])

        # Find matching import items for this license
        matching_imports = instance.import_license.filter(description_filter)

        # Link this ItemNameModel to matching import items
        for import_item in matching_imports:
            # Add item if not already linked
            if not import_item.items.filter(id=item_name.id).exists():
                import_item.items.add(item_name)

                # Update is_restricted flag if item has restriction
                if item_name.restriction_percentage > 0 and not import_item.is_restricted:
                    import_item.is_restricted = True
                    import_item.save(update_fields=['is_restricted'])


@receiver(post_save, sender=LicenseExportItemModel)
def update_license_on_export_item_change(sender, instance, created, **kwargs):
    """
    Update license flags when export items are added/modified.
    This ensures is_null and is_expired are updated after export items are created.
    """
    if kwargs.get('raw', False):
        return

    if instance.license:
        update_license_flags(instance.license)


# Signals for balance updates on import items
@receiver(post_save, sender=LicenseImportItemsModel)
def update_license_on_import_item_change(sender, instance, created, **kwargs):
    """
    Update license flags when import items are added/modified.
    Also auto-link ItemNameModel items based on description/HS code and norm class.
    This ensures balance_cif, available_quantity, and available_value are updated.
    """
    if kwargs.get('raw', False):
        return

    if instance.license:
        update_license_flags(instance.license)

        # Auto-link ItemNameModel items when import item is created or updated
        # Get license export norm classes
        license_norm_classes = list(
            instance.license.export_license.values_list('norm_class__norm_class', flat=True).distinct()
        )

        if license_norm_classes and instance.description:
            from core.models import ItemNameModel
            from django.db.models import Q

            # Get all ItemNameModel items that match the license norm classes
            matching_items = ItemNameModel.objects.filter(
                sion_norm_class__norm_class__in=license_norm_classes
            )

            # Try to match and link items based on description
            for item_name in matching_items:
                # Simple matching by base name (before ' - ')
                base_name = item_name.name.split(' - ')[0]

                if base_name.lower() in instance.description.lower():
                    # Add item if not already linked
                    if not instance.items.filter(id=item_name.id).exists():
                        instance.items.add(item_name)

                        # Update is_restricted flag if item has restriction
                        if item_name.restriction_percentage > 0 and not instance.is_restricted:
                            instance.is_restricted = True
                            instance.save(update_fields=['is_restricted'])
                        break  # Only link one item per import item


@receiver(post_delete, sender=LicenseImportItemsModel)
def update_license_on_import_item_delete(sender, instance, **kwargs):
    """
    Update license flags when import items are deleted.
    """
    if kwargs.get('raw', False):
        return

    if instance.license:
        update_license_flags(instance.license)


# Signals for balance updates on allotment items
@receiver(post_save, sender='allotment.AllotmentItems')
@receiver(post_delete, sender='allotment.AllotmentItems')
def update_license_on_allotment_item_change(sender, instance, **kwargs):
    """
    Update license flags when allotment items are added/modified/deleted.
    This ensures balance_cif is updated when allocations change.
    """
    if kwargs.get('raw', False):
        return

    # Get the license from the allotment item
    if hasattr(instance, 'item') and instance.item:
        if hasattr(instance.item, 'license') and instance.item.license:
            update_license_flags(instance.item.license)


# Signals for balance updates on BOE items
@receiver(post_save, sender='bill_of_entry.RowDetails')
@receiver(post_delete, sender='bill_of_entry.RowDetails')
def update_license_on_boe_item_change(sender, instance, **kwargs):
    """
    Update license flags when BOE row details are added/modified/deleted.
    This ensures balance_cif is updated when BOE debits are made.
    """
    if kwargs.get('raw', False):
        return

    # Get the license from the BOE row detail via sr_number (LicenseImportItemsModel)
    if hasattr(instance, 'sr_number') and instance.sr_number:
        if hasattr(instance.sr_number, 'license') and instance.sr_number.license:
            update_license_flags(instance.sr_number.license)
