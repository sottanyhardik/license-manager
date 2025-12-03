# license/signals.py
from decimal import Decimal

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

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
        # Extract base name for matching:
        # Always use just the first word to avoid overly specific matches
        # e.g., "FOOD FLAVOUR - E126" → "FOOD" (matches "Food Additives")
        # e.g., "PICKLE 3% Restriction" → "PICKLE"
        base_name = item_name.name.split()[0] if item_name.name.split() else item_name.name

        # Build filter based on description/HS code patterns
        description_filter = Q(description__icontains=base_name)

        # Find matching import items for this license
        matching_imports = instance.import_license.filter(description_filter)

        # For short names (<=3 chars), filter out false matches using word boundary check
        import re
        if len(base_name) <= 3:
            pattern = r'\b' + re.escape(base_name) + r'\b'
            # Further filter to only include items where base_name is a standalone word
            matching_imports = [
                imp for imp in matching_imports
                if re.search(pattern, imp.description, re.IGNORECASE)
            ]

        # Special HS code validation for PP items
        # PP should only match if HS code starts with 3902 (Polypropylene)
        if base_name.upper() == 'PP':
            matching_imports = [
                imp for imp in matching_imports
                if imp.hs_code and imp.hs_code.hs_code.startswith('3902')
            ]

        # Special logic for PICKLE items
        # If description contains "Food Additives for Pickles", exclude (FOOD FLAVOUR should match instead)
        if base_name.upper() == 'PICKLE':
            matching_imports = [
                imp for imp in matching_imports
                if not ('food additive' in imp.description.lower() and 'for pickle' in imp.description.lower())
            ]

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
    import logging
    logger = logging.getLogger(__name__)

    if kwargs.get('raw', False):
        logger.debug(f"Signal skipped (raw=True) for import item {instance.id}")
        return

    logger.info(f"Signal fired for import item {instance.id} (created={created})")

    if instance.license:
        update_license_flags(instance.license)

        # Auto-link ItemNameModel items when import item is created or updated
        # Get license export norm classes
        license_norm_classes = list(
            instance.license.export_license.values_list('norm_class__norm_class', flat=True).distinct()
        )

        logger.info(f"License norm classes: {license_norm_classes}")

        if license_norm_classes and instance.description:
            from core.models import ItemNameModel
            from django.db.models import Q

            # Get all ItemNameModel items that match the license norm classes
            matching_items = ItemNameModel.objects.filter(
                sion_norm_class__norm_class__in=license_norm_classes
            )

            logger.info(f"Found {matching_items.count()} matching items for norm classes {license_norm_classes}")

            # Try to match and link items based on description
            for item_name in matching_items:
                # Extract base name for matching:
                # Always use just the first word to avoid overly specific matches
                # e.g., "FOOD FLAVOUR - E126" → "FOOD" (matches "Food Additives")
                # e.g., "PICKLE 3% Restriction" → "PICKLE"
                # e.g., "OLIVE OIL - E126" → "OLIVE" (will still match "Olive Oil")
                base_name = item_name.name.split()[0] if item_name.name.split() else item_name.name

                logger.debug(f"Checking if '{base_name}' in '{instance.description}'")

                # Use word boundary matching for short names (<=3 chars) to avoid false matches
                # e.g., "PP" should not match "approved", only "PP " or " PP" or standalone "PP"
                import re
                if len(base_name) <= 3:
                    # Use word boundary regex for short names
                    pattern = r'\b' + re.escape(base_name) + r'\b'
                    matched = bool(re.search(pattern, instance.description, re.IGNORECASE))
                else:
                    # For longer names, simple substring match is fine
                    matched = base_name.lower() in instance.description.lower()

                # Special HS code validation for PP items
                # PP should only match if HS code starts with 3902 (Polypropylene)
                if matched and base_name.upper() == 'PP':
                    hs_code = instance.hs_code.hs_code if instance.hs_code else ''
                    if not hs_code.startswith('3902'):
                        logger.debug(f"Skipping PP for item {instance.id}: HS code {hs_code} does not start with 3902")
                        matched = False

                # Special logic for PICKLE items
                # If description contains "Food Additives for Pickles", match FOOD FLAVOUR not PICKLE
                if matched and base_name.upper() == 'PICKLE':
                    if 'food additive' in instance.description.lower() and 'for pickle' in instance.description.lower():
                        logger.debug(f"Skipping PICKLE for item {instance.id}: 'Food Additives for Pickles' should match FOOD FLAVOUR")
                        matched = False

                if matched:
                    # Add item if not already linked
                    if not instance.items.filter(id=item_name.id).exists():
                        logger.info(f"Linking item {item_name.id} ({item_name.name}) to import item {instance.id}")
                        instance.items.add(item_name)

                        # Update is_restricted flag if item has restriction
                        if item_name.restriction_percentage > 0 and not instance.is_restricted:
                            logger.info(
                                f"Setting is_restricted=True for import item {instance.id} (restriction: {item_name.restriction_percentage}%)")
                            instance.is_restricted = True
                            instance.save(update_fields=['is_restricted'])
                        break  # Only link one item per import item
                    else:
                        logger.debug(f"Item {item_name.id} already linked to import item {instance.id}")
        else:
            if not license_norm_classes:
                logger.warning(f"No license norm classes found for license {instance.license.id}")
            if not instance.description:
                logger.warning(f"No description for import item {instance.id}")


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
