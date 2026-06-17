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

from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

from apps.core.cache_utils import invalidate_cache, invalidate_model_caches

logger = logging.getLogger(__name__)

# ============================================================================
# License Model Signals
# ============================================================================


@receiver([post_save, post_delete], sender='license.LicenseDetailsModel')
def invalidate_license_caches(sender, instance, **kwargs):
    """
    Invalidate caches when a license is created, updated, or deleted.

    Affected caches:
    - License list views
    - License detail views
    - Dashboard statistics
    - Item reports (if license has import items)
    """
    logger.debug(f"Invalidating caches for License: {instance.license_number}")

    # Invalidate license-specific caches
    patterns = [
        f'view:license*',  # All license list/detail views
        f'view:dashboard*',  # Dashboard shows license stats
        f'license_balance:{instance.id}',  # Specific license balance
        f'LicenseDetailsModel:*:{instance.id}:*',  # Method caches
        f'view:item_report*',  # Item reports include license data
        f'view:active_licenses*',  # Active license reports
        f'view:expiring_licenses*',  # Expiring license reports
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver([post_save, post_delete], sender='license.LicenseImportItemsModel')
def invalidate_import_item_caches(sender, instance, **kwargs):
    """
    Invalidate caches when import items are modified.

    Affected caches:
    - Item reports
    - Item pivot reports
    - License detail (includes import items)
    - Inventory balance reports
    """
    logger.debug(f"Invalidating caches for LicenseImportItem: {instance.id}")

    patterns = [
        f'view:item_report*',
        f'view:item_pivot*',
        f'view:inventory_balance*',
        f'view:license*:{instance.license_id}*',  # Parent license detail
        f'license_balance:{instance.license_id}',  # License balance affected
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver([post_save, post_delete], sender='license.LicenseExportItemModel')
def invalidate_export_item_caches(sender, instance, **kwargs):
    """Invalidate caches when export items are modified."""
    logger.debug(f"Invalidating caches for LicenseExportItem: {instance.id}")

    patterns = [
        f'view:license*:{instance.license_id}*',
        f'license_balance:{instance.license_id}',
        f'view:item_pivot*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


# M2M signal for LicenseImportItemsModel.items will be connected in ready()
# after models are loaded, since string references don't work with .through
def invalidate_import_item_m2m_caches(sender, instance, **kwargs):
    """Invalidate caches when import item <-> item names relationship changes."""
    logger.debug(f"Invalidating M2M caches for import item: {instance.id}")

    invalidate_cache(f'view:item_report*')
    invalidate_cache(f'view:item_pivot*')


# ============================================================================
# Bill of Entry Signals
# ============================================================================


@receiver([post_save, post_delete], sender='bill_of_entry.BillOfEntryModel')
def invalidate_boe_caches(sender, instance, **kwargs):
    """
    Invalidate caches when BOE is modified.

    Affected caches:
    - BOE list/detail views
    - Dashboard BOE stats
    - Related license balances
    """
    logger.debug(f"Invalidating caches for BOE: {instance.bill_of_entry_number}")

    patterns = [
        f'view:boe*',
        f'view:dashboard*',
        f'view:bill_of_entry*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver([post_save, post_delete], sender='bill_of_entry.RowDetails')
def invalidate_row_details_caches(sender, instance, **kwargs):
    """
    Invalidate caches when BOE line items (RowDetails) are modified.

    CRITICAL: This affects balance calculations!
    """
    logger.debug(f"Invalidating caches for RowDetails: {instance.id}")

    # Invalidate license balance if linked to a license item
    if instance.sr_number and hasattr(instance.sr_number, 'license'):
        license_id = instance.sr_number.license_id
        invalidate_cache(f'license_balance:{license_id}')
        invalidate_cache(f'view:license*:{license_id}*')

    patterns = [
        f'view:boe*:{instance.bill_of_entry_id}*',
        f'view:item_report*',  # Affects balance calculations in item reports
        f'view:inventory_balance*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


# ============================================================================
# Allotment Signals
# ============================================================================


@receiver([post_save, post_delete], sender='allotment.AllotmentModel')
def invalidate_allotment_caches(sender, instance, **kwargs):
    """Invalidate caches when allotment is modified."""
    logger.debug(f"Invalidating caches for Allotment: {instance.id}")

    patterns = [
        f'view:allotment*',
        f'view:dashboard*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver([post_save, post_delete], sender='allotment.AllotmentItems')
def invalidate_allotment_items_caches(sender, instance, **kwargs):
    """
    Invalidate caches when allotment items are modified.

    CRITICAL: This affects license balance calculations!
    """
    logger.debug(f"Invalidating caches for AllotmentItems: {instance.id}")

    # Invalidate license balance if linked
    if instance.item and hasattr(instance.item, 'license'):
        license_id = instance.item.license_id
        invalidate_cache(f'license_balance:{license_id}')
        invalidate_cache(f'view:license*:{license_id}*')

    patterns = [
        f'view:allotment*:{instance.allotment_id}*',
        f'view:item_report*',
        f'view:inventory_balance*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


# ============================================================================
# Master Data Signals (Low-frequency invalidation)
# ============================================================================


@receiver([post_save, post_delete], sender='core.CompanyModel')
def invalidate_company_caches(sender, instance, **kwargs):
    """
    Invalidate caches when company master data is modified.

    Companies are used everywhere, so this is a broad invalidation.
    """
    logger.debug(f"Invalidating caches for Company: {instance.name}")

    patterns = [
        f'view:company*',
        f'view:license*company*',  # License filters by company
        f'view:boe*company*',
        f'view:allotment*company*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver([post_save, post_delete], sender='core.ItemNameModel')
def invalidate_item_name_caches(sender, instance, **kwargs):
    """Invalidate caches when item names are modified."""
    logger.debug(f"Invalidating caches for ItemName: {instance.name}")

    patterns = [
        f'view:item*',
        f'view:item_report*',
        f'view:item_pivot*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver([post_save, post_delete], sender='core.HSCodeModel')
def invalidate_hscode_caches(sender, instance, **kwargs):
    """Invalidate caches when HS codes are modified."""
    logger.debug(f"Invalidating caches for HSCode: {instance.hs_code}")

    patterns = [
        f'view:hscode*',
        f'view:item_report*',
    ]

    for pattern in patterns:
        invalidate_cache(pattern)


@receiver([post_save, post_delete], sender='core.PurchaseStatus')
def invalidate_purchase_status_caches(sender, instance, **kwargs):
    """Invalidate caches when purchase statuses are modified."""
    logger.debug(f"Invalidating caches for PurchaseStatus: {instance.code}")

    # Purchase status is heavily used in license filtering
    patterns = [
        f'view:license*',
        f'view:dashboard*',
        f'view:item_report*',
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
        self.receivers = []
        # Disconnect all cache invalidation receivers
        for receiver_func in [
            invalidate_license_caches,
            invalidate_import_item_caches,
            invalidate_export_item_caches,
            invalidate_boe_caches,
            invalidate_row_details_caches,
            invalidate_allotment_caches,
            invalidate_allotment_items_caches,
            invalidate_company_caches,
            invalidate_item_name_caches,
            invalidate_hscode_caches,
            invalidate_purchase_status_caches,
        ]:
            # Store receiver info for reconnection
            self.receivers.append((receiver_func, receiver_func.sender))
            # Disconnect
            post_save.disconnect(receiver_func, sender=receiver_func.sender)
            post_delete.disconnect(receiver_func, sender=receiver_func.sender)

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Reconnect all receivers
        for receiver_func, sender in self.receivers:
            post_save.connect(receiver_func, sender=sender)
            post_delete.connect(receiver_func, sender=sender)


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
            dispatch_uid='invalidate_import_item_m2m_caches'
        )
        logger.info("Connected M2M cache invalidation signals")
    except Exception as e:
        logger.warning(f"Could not connect M2M signals: {e}")
