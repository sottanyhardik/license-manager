"""
Celery tasks for materialized view refresh.

Scheduled tasks to keep materialized views fresh.
"""

import logging

from celery import shared_task

from apps.core.materialized_views import (
    get_materialized_view_stats,
    refresh_all_materialized_views,
    refresh_materialized_view,
)

logger = logging.getLogger(__name__)


@shared_task
def refresh_all_views_task():
    """
    Refresh all materialized views.

    Schedule this task to run periodically (e.g., every 5-15 minutes).
    """
    try:
        logger.info("Starting scheduled refresh of all materialized views")
        refresh_all_materialized_views(concurrently=True)
        logger.info("Successfully refreshed all materialized views")
    except Exception:
        logger.exception("Failed to refresh materialized views")
        raise


@shared_task
def refresh_license_balance_task():
    """Refresh only license balance view (faster, more frequent)."""
    try:
        refresh_materialized_view('license_balance_mv', concurrently=True)
        logger.info("Refreshed license_balance_mv")
    except Exception:
        logger.exception("Failed to refresh license_balance_mv")
        raise


@shared_task
def refresh_item_balance_task():
    """Refresh only item balance view."""
    try:
        refresh_materialized_view('item_balance_mv', concurrently=True)
        logger.info("Refreshed item_balance_mv")
    except Exception:
        logger.exception("Failed to refresh item_balance_mv")
        raise


@shared_task
def refresh_dashboard_stats_task():
    """Refresh dashboard stats view (less frequent)."""
    try:
        refresh_materialized_view('dashboard_stats_mv', concurrently=True)
        logger.info("Refreshed dashboard_stats_mv")
    except Exception:
        logger.exception("Failed to refresh dashboard_stats_mv")
        raise


@shared_task
def check_materialized_view_health():
    """
    Check health of materialized views and log warnings.

    Can be scheduled daily to monitor view freshness.
    """
    try:
        stats = get_materialized_view_stats()
        logger.info("Materialized view health check: %d views checked", len(stats))

        for stat in stats:
            logger.info(
                "%s: Size: %s, Rows: %s",
                stat['view_name'],
                stat['size'],
                stat['rows_inserted'],
            )

        return {'status': 'healthy', 'views_checked': len(stats)}
    except Exception as e:
        logger.exception("Health check failed")
        return {'status': 'unhealthy', 'error': str(e)}
