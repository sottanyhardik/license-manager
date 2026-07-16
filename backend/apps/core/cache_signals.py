"""
Automatic Cache Invalidation via Django Signals
================================================

Automatically invalidates relevant caches when models are modified.

This ensures cache consistency without manual invalidation in views.

Usage:
    Import in apps.py ready() method:

    class CoreConfig(AppConfig):
        def ready(self):
            from apps.core import cache_signals  # noqa
"""

import logging

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from apps.core.cache_utils import invalidate_cache

logger = logging.getLogger(__name__)

# ============================================================================
# License Model Signals
# ============================================================================


@receiver(
    [post_save, post_delete],
    sender='license.LicenseDetailsModel',
    dispatch_uid='invalidate_license_caches',
)
def invalidate_license_caches(sender, instance, **kwargs):
    """
    Invalidate caches when a license is created, updated, or deleted.

    Affected caches:
    - License list views
    - License detail views
    - Dashboard statistics
    - Item reports (if license has import items)
    """
    logger.debug("Invalidating caches for License: %s", instance.license_number)

    # Invalidate license-specific caches
    patterns = [
        'view:license*',  # All license list/detail views
        'view:dashboard*',  # Dashboard shows license stats
        f'license_balance:{instance.id}',  # Specific license balance
        f'LicenseDetailsModel:*:{instance.id}:*',  # Method caches
        'view:item_report*',  # Item reports include license data
        'view:active_licenses*',  # Active license reports
        'view:expiring_licenses*',  # Expiring license reports
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver(
    [post_save, post_delete],
    sender='license.LicenseImportItemsModel',
    dispatch_uid='invalidate_import_item_caches',
)
def invalidate_import_item_caches(sender, instance, **kwargs):
    """
    Invalidate caches when import items are modified.

    Affected caches:
    - Item reports
    - Item pivot reports
    - License detail (includes import items)
    - Inventory balance reports
    """
    logger.debug("Invalidating caches for LicenseImportItem: %s", instance.id)

    patterns = [
        'view:item_report*',
        'view:item_pivot*',
        'view:inventory_balance*',
        f'view:license*:{instance.license_id}*',  # Parent license detail
        f'license_balance:{instance.license_id}',  # License balance affected
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver(
    [post_save, post_delete],
    sender='license.LicenseExportItemModel',
    dispatch_uid='invalidate_export_item_caches',
)
def invalidate_export_item_caches(sender, instance, **kwargs):
    """Invalidate caches when export items are modified."""
    logger.debug("Invalidating caches for LicenseExportItem: %s", instance.id)

    patterns = [
        f'view:license*:{instance.license_id}*',
        f'license_balance:{instance.license_id}',
        'view:item_pivot*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


# M2M signal for LicenseImportItemsModel.items will be connected in ready()
# after models are loaded, since string references don't work with .through
def invalidate_import_item_m2m_caches(sender, instance, **kwargs):
    """Invalidate caches when import item <-> item names relationship changes."""
    logger.debug("Invalidating M2M caches for import item: %s", instance.id)

    invalidate_cache('view:item_report*')
    invalidate_cache('view:item_pivot*')


# ============================================================================
# Bill of Entry Signals
# ============================================================================


@receiver(
    [post_save, post_delete],
    sender='bill_of_entry.BillOfEntryModel',
    dispatch_uid='invalidate_boe_caches',
)
def invalidate_boe_caches(sender, instance, **kwargs):
    """
    Invalidate caches when BOE is modified.

    Affected caches:
    - BOE list/detail views
    - Dashboard BOE stats
    - Related license balances
    """
    logger.debug("Invalidating caches for BOE: %s", instance.bill_of_entry_number)

    patterns = [
        'view:boe*',
        'view:dashboard*',
        'view:bill_of_entry*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver(
    [post_save, post_delete],
    sender='bill_of_entry.RowDetails',
    dispatch_uid='invalidate_row_details_caches',
)
def invalidate_row_details_caches(sender, instance, **kwargs):
    """
    Invalidate caches when BOE line items (RowDetails) are modified.

    CRITICAL: This affects balance calculations!
    """
    logger.debug("Invalidating caches for RowDetails: %s", instance.id)

    # Invalidate license balance if linked to a license item
    if instance.sr_number and hasattr(instance.sr_number, 'license'):
        license_id = instance.sr_number.license_id
        invalidate_cache(f'license_balance:{license_id}')
        invalidate_cache(f'view:license*:{license_id}*')

    patterns = [
        f'view:boe*:{instance.bill_of_entry_id}*',
        'view:item_report*',  # Affects balance calculations in item reports
        'view:inventory_balance*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


# ============================================================================
# Allotment Signals
# ============================================================================


@receiver(
    [post_save, post_delete],
    sender='allotment.AllotmentModel',
    dispatch_uid='invalidate_allotment_caches',
)
def invalidate_allotment_caches(sender, instance, **kwargs):
    """Invalidate caches when allotment is modified."""
    logger.debug("Invalidating caches for Allotment: %s", instance.id)

    patterns = [
        'view:allotment*',
        'view:dashboard*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver(
    [post_save, post_delete],
    sender='allotment.AllotmentItems',
    dispatch_uid='invalidate_allotment_items_caches',
)
def invalidate_allotment_items_caches(sender, instance, **kwargs):
    """
    Invalidate caches when allotment items are modified.

    CRITICAL: This affects license balance calculations!
    """
    logger.debug("Invalidating caches for AllotmentItems: %s", instance.id)

    # Invalidate license balance if linked
    if instance.item and hasattr(instance.item, 'license'):
        license_id = instance.item.license_id
        invalidate_cache(f'license_balance:{license_id}')
        invalidate_cache(f'view:license*:{license_id}*')

    patterns = [
        f'view:allotment*:{instance.allotment_id}*',
        'view:item_report*',
        'view:inventory_balance*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


# ============================================================================
# Master Data Signals (Low-frequency invalidation)
# ============================================================================


@receiver(
    [post_save, post_delete],
    sender='core.CompanyModel',
    dispatch_uid='invalidate_company_caches',
)
def invalidate_company_caches(sender, instance, **kwargs):
    """
    Invalidate caches when company master data is modified.

    Companies are used everywhere, so this is a broad invalidation.
    """
    logger.debug("Invalidating caches for Company: %s", instance.name)

    patterns = [
        'view:company*',
        'view:license*company*',  # License filters by company
        'view:boe*company*',
        'view:allotment*company*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver(
    [post_save, post_delete],
    sender='core.ItemNameModel',
    dispatch_uid='invalidate_item_name_caches',
)
def invalidate_item_name_caches(sender, instance, **kwargs):
    """Invalidate caches when item names are modified."""
    logger.debug("Invalidating caches for ItemName: %s", instance.name)

    patterns = [
        'view:item*',
        'view:item_report*',
        'view:item_pivot*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver(
    [post_save, post_delete],
    sender='core.HSCodeModel',
    dispatch_uid='invalidate_hscode_caches',
)
def invalidate_hscode_caches(sender, instance, **kwargs):
    """Invalidate caches when HS codes are modified."""
    logger.debug("Invalidating caches for HSCode: %s", instance.hs_code)

    patterns = [
        'view:hscode*',
        'view:item_report*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver(
    [post_save, post_delete],
    sender='core.PurchaseStatus',
    dispatch_uid='invalidate_purchase_status_caches',
)
def invalidate_purchase_status_caches(sender, instance, **kwargs):
    """Invalidate caches when purchase statuses are modified."""
    logger.debug("Invalidating caches for PurchaseStatus: %s", instance.code)

    # Purchase status is heavily used in license filtering
    patterns = [
        'view:license*',
        'view:dashboard*',
        'view:item_report*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


# ============================================================================
# Utility: Manual Cache Invalidation Endpoints
# ============================================================================

def get_invalidation_patterns_for_model(model_name: str) -> list:
    """
    Get recommended cache invalidation patterns for a model.

    Useful for manual cache clearing in admin interface.

    Args:
        model_name: Model name (e.g., 'LicenseDetailsModel')

    Returns:
        List of cache key patterns to invalidate
    """
    patterns_map = {
        'LicenseDetailsModel': [
            'view:license*',
            'view:dashboard*',
            'view:item_report*',
            'license_balance:*',
        ],
        'BillOfEntryModel': [
            'view:boe*',
            'view:bill_of_entry*',
            'view:dashboard*',
        ],
        'AllotmentModel': [
            'view:allotment*',
            'view:dashboard*',
        ],
        'CompanyModel': [
            'view:company*',
            'view:license*',
            'view:boe*',
        ],
        'ItemNameModel': [
            'view:item*',
        ],
    }

    return patterns_map.get(model_name, [f'*{model_name.lower()}*'])


CACHE_INVALIDATION_RECEIVERS = (
    (invalidate_license_caches, 'license.LicenseDetailsModel', 'invalidate_license_caches'),
    (invalidate_import_item_caches, 'license.LicenseImportItemsModel', 'invalidate_import_item_caches'),
    (invalidate_export_item_caches, 'license.LicenseExportItemModel', 'invalidate_export_item_caches'),
    (invalidate_boe_caches, 'bill_of_entry.BillOfEntryModel', 'invalidate_boe_caches'),
    (invalidate_row_details_caches, 'bill_of_entry.RowDetails', 'invalidate_row_details_caches'),
    (invalidate_allotment_caches, 'allotment.AllotmentModel', 'invalidate_allotment_caches'),
    (invalidate_allotment_items_caches, 'allotment.AllotmentItems', 'invalidate_allotment_items_caches'),
    (invalidate_company_caches, 'core.CompanyModel', 'invalidate_company_caches'),
    (invalidate_item_name_caches, 'core.ItemNameModel', 'invalidate_item_name_caches'),
    (invalidate_hscode_caches, 'core.HSCodeModel', 'invalidate_hscode_caches'),
    (invalidate_purchase_status_caches, 'core.PurchaseStatus', 'invalidate_purchase_status_caches'),
)


# ============================================================================
# Debug/Testing: Disable Signals
# ============================================================================

class disable_cache_invalidation:
    """
    Context manager to temporarily disable cache invalidation signals.

    Useful for bulk imports or testing.

    Usage:
        with disable_cache_invalidation():
            # Import 1000 licenses without cache thrashing
            for license in licenses:
                license.save()
    """
    def __enter__(self):
        # Disconnect all cache invalidation receivers
        for receiver_func, sender, dispatch_uid in CACHE_INVALIDATION_RECEIVERS:
            post_save.disconnect(receiver_func, sender=sender, dispatch_uid=dispatch_uid)
            post_delete.disconnect(receiver_func, sender=sender, dispatch_uid=dispatch_uid)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Reconnect all receivers
        for receiver_func, sender, dispatch_uid in CACHE_INVALIDATION_RECEIVERS:
            post_save.connect(receiver_func, sender=sender, dispatch_uid=dispatch_uid)
            post_delete.connect(receiver_func, sender=sender, dispatch_uid=dispatch_uid)


# ============================================================================
# Connect M2M signals after app is ready
# ============================================================================

def connect_m2m_signals():
    """
    Connect M2M signals that can't use string references.
    Call this from apps.py ready() after models are loaded.
    """
    try:
        from apps.license.models import LicenseImportItemsModel

        # Connect the M2M signal for import items <-> item names
        m2m_changed.connect(
            invalidate_import_item_m2m_caches,
            sender=LicenseImportItemsModel.items.through,
            dispatch_uid='invalidate_import_item_m2m_caches',
        )
        logger.info("Connected M2M cache invalidation signals")
    except Exception:
        logger.warning("Could not connect M2M signals", exc_info=True)
