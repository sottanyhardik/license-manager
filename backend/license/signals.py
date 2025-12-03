# license/signals.py
from django.db.models.signals import post_save
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

    # Get all export items with norm classes
    export_items = instance.export_license.filter(norm_class__isnull=False)

    if not export_items.exists():
        return

    # Collect all norm classes from export items
    norm_classes = set()
    for export_item in export_items:
        if export_item.norm_class:
            norm_classes.add(export_item.norm_class)

    if not norm_classes:
        return

    # Fetch SION norm items for these norm classes
    sion_items = SIONImportModel.objects.filter(
        norm_class__in=norm_classes
    ).select_related('hs_code')

    if not sion_items.exists():
        return

    # Create import items from SION norms
    serial_number = 1
    for sion_item in sion_items:
        # Check if an import item with this HS code already exists
        if instance.import_license.filter(hs_code=sion_item.hs_code).exists():
            continue

        # Create import item
        LicenseImportItemsModel.objects.create(
            license=instance,
            serial_number=serial_number,
            hs_code=sion_item.hs_code,
            description=sion_item.description or (sion_item.hs_code.description if sion_item.hs_code else ''),
            quantity=0,
            unit='kg',
            cif_fc=0,
            cif_inr=0,
            is_restricted=False
        )

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

        # Also trigger import item auto-fetch if this is a new export item with norm_class
        if created and instance.norm_class:
            license = instance.license
            # Check if we should auto-fetch import items
            if not license.import_license.exists():
                # Get all norm classes from this license
                norm_classes = set()
                for export_item in license.export_license.filter(norm_class__isnull=False):
                    if export_item.norm_class:
                        norm_classes.add(export_item.norm_class)

                if norm_classes:
                    # Fetch SION norm items
                    sion_items = SIONImportModel.objects.filter(
                        norm_class__in=norm_classes
                    ).select_related('hs_code')

                    serial_number = 1
                    for sion_item in sion_items:
                        if license.import_license.filter(hs_code=sion_item.hs_code).exists():
                            continue

                        LicenseImportItemsModel.objects.create(
                            license=license,
                            serial_number=serial_number,
                            hs_code=sion_item.hs_code,
                            description=sion_item.description or (sion_item.hs_code.description if sion_item.hs_code else ''),
                            quantity=0,
                            unit='kg',
                            cif_fc=0,
                            cif_inr=0,
                            is_restricted=False
                        )
                        serial_number += 1
