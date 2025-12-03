# license/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from core.models import SionNormItemModel


@receiver(post_save, sender=LicenseDetailsModel)
def auto_fetch_import_items(sender, instance, created, **kwargs):
    """
    Automatically populate import items from SION norms when a license is saved.
    This fetches items based on the norm classes in export items.
    """
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
    sion_items = SionNormItemModel.objects.filter(
        sion_norm_class__in=norm_classes
    ).select_related('hs_code', 'item_name')

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
