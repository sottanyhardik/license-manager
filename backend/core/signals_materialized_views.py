"""
Signal handlers for automatic materialized view refresh.

Refreshes materialized views when underlying data changes.

Note: These are trigger-based refreshes. For most use cases, scheduled
Celery tasks are preferred to avoid refresh overhead on every save.
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction

from core.tasks_materialized_views import (
    refresh_license_balance_task,
    refresh_item_balance_task,
    refresh_dashboard_stats_task
)

logger = logging.getLogger(__name__)

# Flag to enable/disable automatic refresh (disabled by default for performance)
AUTO_REFRESH_ENABLED = False


def refresh_on_commit(task_func):
    """
    Schedule a refresh task to run after transaction commits.

    This prevents refreshing mid-transaction and reduces unnecessary refreshes.
    """
    if not AUTO_REFRESH_ENABLED:
        return

    def _refresh():
        try:
            # Use apply_async with countdown to debounce rapid saves
            task_func.apply_async(countdown=5)
        except Exception as e:
            logger.warning(f"Could not schedule refresh task: {e}")

    transaction.on_commit(_refresh)


# ============================================================================
# License Model Signals
# ============================================================================

@receiver([post_save, post_delete], sender='license.LicenseDetailsModel')
def refresh_views_on_license_change(sender, instance, **kwargs):
    """Refresh views when license is created/updated/deleted."""
    logger.debug(f"License change detected: {instance.license_number}")
    refresh_on_commit(refresh_license_balance_task)
    refresh_on_commit(refresh_dashboard_stats_task)


@receiver([post_save, post_delete], sender='license.LicenseImportItemsModel')
def refresh_views_on_import_item_change(sender, instance, **kwargs):
    """Refresh views when import items are created/updated/deleted."""
    logger.debug(f"Import item change detected: {instance.id}")
    refresh_on_commit(refresh_item_balance_task)
    refresh_on_commit(refresh_license_balance_task)


# ============================================================================
# BOE Signals
# ============================================================================

@receiver([post_save, post_delete], sender='bill_of_entry.RowDetails')
def refresh_views_on_row_details_change(sender, instance, **kwargs):
    """
    Refresh views when BOE row details change.

    CRITICAL: This affects balance calculations!
    """
    logger.debug(f"Row details change detected: {instance.id}")
    refresh_on_commit(refresh_item_balance_task)
    refresh_on_commit(refresh_license_balance_task)
    refresh_on_commit(refresh_dashboard_stats_task)


# ============================================================================
# Allotment Signals
# ============================================================================

@receiver([post_save, post_delete], sender='allotment.AllotmentItems')
def refresh_views_on_allotment_items_change(sender, instance, **kwargs):
    """
    Refresh views when allotment items change.

    CRITICAL: This affects balance calculations!
    """
    logger.debug(f"Allotment items change detected: {instance.id}")
    refresh_on_commit(refresh_item_balance_task)
    refresh_on_commit(refresh_license_balance_task)


# ============================================================================
# Manual Refresh Trigger
# ============================================================================

def enable_auto_refresh():
    """Enable automatic materialized view refresh on model changes."""
    global AUTO_REFRESH_ENABLED
    AUTO_REFRESH_ENABLED = True
    logger.info("Automatic materialized view refresh ENABLED")


def disable_auto_refresh():
    """Disable automatic materialized view refresh (default)."""
    global AUTO_REFRESH_ENABLED
    AUTO_REFRESH_ENABLED = False
    logger.info("Automatic materialized view refresh DISABLED")


class auto_refresh_context:
    """
    Context manager to temporarily enable auto-refresh.

    Usage:
        with auto_refresh_context():
            # Changes here will trigger view refreshes
            license.save()
    """
    def __enter__(self):
        enable_auto_refresh()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        disable_auto_refresh()
