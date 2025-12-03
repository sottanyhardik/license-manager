# license/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal
from license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from core.models import SIONImportModel


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
    Automatically populate import items from SION norms when a license is saved.
    Also updates is_null and is_expired flags.
    This fetches items based on the norm classes in export items.
    """
    # Prevent infinite recursion by checking if we're already in a save
    if kwargs.get('raw', False):
        return

    # Update license flags
    update_license_flags(instance)

    # Only auto-fetch if this is a new license OR if there are no existing import items
    if not created and instance.import_license.exists():
        return

    # Get all export items with item names (user_itemname)
    export_items = instance.export_license.filter(item__isnull=False)

    if not export_items.exists():
        return

    # Collect all item names from export items
    item_names = set()
    for export_item in export_items:
        if export_item.item:
            item_names.add(export_item.item)

    if not item_names:
        return

    # Fetch SION norm classes for these item names
    from core.models import SionNormClassModel, ItemNameModel
    norm_classes = SionNormClassModel.objects.filter(
        items__in=item_names
    ).distinct()

    if not norm_classes.exists():
        return

    # Fetch SION import items for these norm classes
    sion_items = SIONImportModel.objects.filter(
        norm_class__in=norm_classes
    ).select_related('hsn_code')

    if not sion_items.exists():
        return

    # Create import items from SION norms with automatic restriction linking
    serial_number = 1
    for sion_item in sion_items:
        # Check if an import item with this HS code already exists
        if instance.import_license.filter(hs_code=sion_item.hsn_code).exists():
            continue

        # Determine if this import item should be restricted
        # Check if any of the export item names have restriction_percentage > 0
        has_restriction = False
        restriction_item = None
        for item_name in item_names:
            if item_name.sion_norm_class == sion_item.norm_class and item_name.restriction_percentage > 0:
                has_restriction = True
                restriction_item = item_name
                break

        # Create import item
        import_item = LicenseImportItemsModel.objects.create(
            license=instance,
            serial_number=serial_number,
            hs_code=sion_item.hsn_code,
            description=sion_item.description or (sion_item.hsn_code.product_description if sion_item.hsn_code else ''),
            quantity=sion_item.quantity if sion_item.quantity else 0,
            unit=sion_item.unit if sion_item.unit else 'kg',
            cif_fc=0,
            cif_inr=0,
            is_restricted=has_restriction
        )

        # Link the restriction ItemNameModel if applicable
        if restriction_item:
            import_item.items.add(restriction_item)

        serial_number += 1


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

        # Also trigger import item auto-fetch if this is a new export item with item name
        if created and instance.item:
            license = instance.license
            # Check if we should auto-fetch import items
            if not license.import_license.exists():
                # Get all item names from this license
                item_names = set()
                for export_item in license.export_license.filter(item__isnull=False):
                    if export_item.item:
                        item_names.add(export_item.item)

                if item_names:
                    # Fetch SION norm classes for these item names
                    from core.models import SionNormClassModel, ItemNameModel
                    norm_classes = SionNormClassModel.objects.filter(
                        items__in=item_names
                    ).distinct()

                    if norm_classes.exists():
                        # Fetch SION import items
                        sion_items = SIONImportModel.objects.filter(
                            norm_class__in=norm_classes
                        ).select_related('hsn_code')

                        serial_number = 1
                        for sion_item in sion_items:
                            if license.import_license.filter(hs_code=sion_item.hsn_code).exists():
                                continue

                            # Determine if this import item should be restricted
                            has_restriction = False
                            restriction_item = None
                            for item_name in item_names:
                                if item_name.sion_norm_class == sion_item.norm_class and item_name.restriction_percentage > 0:
                                    has_restriction = True
                                    restriction_item = item_name
                                    break

                            import_item = LicenseImportItemsModel.objects.create(
                                license=license,
                                serial_number=serial_number,
                                hs_code=sion_item.hsn_code,
                                description=sion_item.description or (sion_item.hsn_code.product_description if sion_item.hsn_code else ''),
                                quantity=sion_item.quantity if sion_item.quantity else 0,
                                unit=sion_item.unit if sion_item.unit else 'kg',
                                cif_fc=0,
                                cif_inr=0,
                                is_restricted=has_restriction
                            )

                            # Link the restriction ItemNameModel if applicable
                            if restriction_item:
                                import_item.items.add(restriction_item)

                            serial_number += 1


# Signals for balance updates on import items
@receiver(post_save, sender=LicenseImportItemsModel)
@receiver(post_delete, sender=LicenseImportItemsModel)
def update_license_on_import_item_change(sender, instance, **kwargs):
    """
    Update license flags when import items are added/modified/deleted.
    This ensures balance_cif, available_quantity, and available_value are updated.
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
@receiver(post_save, sender='boe.BillOfEntryItemsModel')
@receiver(post_delete, sender='boe.BillOfEntryItemsModel')
def update_license_on_boe_item_change(sender, instance, **kwargs):
    """
    Update license flags when BOE items are added/modified/deleted.
    This ensures balance_cif is updated when BOE debits are made.
    """
    if kwargs.get('raw', False):
        return

    # Get the license from the BOE item
    if hasattr(instance, 'license_item') and instance.license_item:
        if hasattr(instance.license_item, 'license') and instance.license_item.license:
            update_license_flags(instance.license_item.license)
