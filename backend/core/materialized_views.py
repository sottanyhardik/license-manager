"""
Materialized Views for License Manager

Replaces denormalized fields with PostgreSQL materialized views for:
- Better data integrity (no stale data)
- Automatic calculation
- Improved query performance
- Easier maintenance

Materialized views are refreshed:
- On-demand via management command
- After specific model saves (via signals)
- Via scheduled Celery tasks
"""

from django.db import connection
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Materialized View Definitions
# ============================================================================

LICENSE_BALANCE_VIEW = """
CREATE MATERIALIZED VIEW IF NOT EXISTS license_balance_mv AS
SELECT
    ld.id as license_id,
    ld.license_number,
    ld.company_id,
    ld.total_cif,
    ld.license_date,
    ld.license_expiry_date,
    ld.is_active,

    -- Calculate utilized CIF from BOE (debits)
    COALESCE(SUM(CASE
        WHEN rd.transaction_type = 'DEBIT' THEN rd.cif_inr
        ELSE 0
    END), 0) as utilized_cif,

    -- Calculate allotted CIF
    COALESCE(SUM(CASE
        WHEN ai.allotment_id IS NOT NULL THEN ai.allotted_cif
        ELSE 0
    END), 0) as allotted_cif,

    -- Calculate balance CIF (total - utilized - allotted)
    ld.total_cif -
    COALESCE(SUM(CASE
        WHEN rd.transaction_type = 'DEBIT' THEN rd.cif_inr
        ELSE 0
    END), 0) -
    COALESCE(SUM(CASE
        WHEN ai.allotment_id IS NOT NULL THEN ai.allotted_cif
        ELSE 0
    END), 0) as balance_cif,

    -- Metadata
    NOW() as last_refreshed

FROM license_licensedetailsmodel ld

LEFT JOIN license_licenseimportitemsmodel lii
    ON lii.license_id = ld.id

LEFT JOIN bill_of_entry_rowdetails rd
    ON rd.sr_number_id = lii.id
    AND rd.transaction_type IN ('DEBIT', 'CREDIT')

LEFT JOIN allotment_allotmentitems ai
    ON ai.item_id = lii.id

GROUP BY ld.id, ld.license_number, ld.company_id, ld.total_cif,
         ld.license_date, ld.license_expiry_date, ld.is_active;

CREATE UNIQUE INDEX IF NOT EXISTS license_balance_mv_license_id_idx
    ON license_balance_mv(license_id);

CREATE INDEX IF NOT EXISTS license_balance_mv_company_id_idx
    ON license_balance_mv(company_id);

CREATE INDEX IF NOT EXISTS license_balance_mv_balance_cif_idx
    ON license_balance_mv(balance_cif);

CREATE INDEX IF NOT EXISTS license_balance_mv_is_active_idx
    ON license_balance_mv(is_active);
"""


ITEM_BALANCE_VIEW = """
CREATE MATERIALIZED VIEW IF NOT EXISTS item_balance_mv AS
SELECT
    lii.id as item_id,
    lii.license_id,
    lii.serial_number,
    ld.license_number,
    ld.company_id,
    lii.quantity as total_quantity,
    lii.cif as total_cif,

    -- Utilized via BOE
    COALESCE(SUM(CASE
        WHEN rd.transaction_type = 'DEBIT' THEN rd.qty
        ELSE 0
    END), 0) as utilized_quantity,

    COALESCE(SUM(CASE
        WHEN rd.transaction_type = 'DEBIT' THEN rd.cif_inr
        ELSE 0
    END), 0) as utilized_cif,

    -- Allotted
    COALESCE(SUM(ai.allotted_quantity), 0) as allotted_quantity,
    COALESCE(SUM(ai.allotted_cif), 0) as allotted_cif,

    -- Balance (available)
    lii.quantity -
    COALESCE(SUM(CASE
        WHEN rd.transaction_type = 'DEBIT' THEN rd.qty
        ELSE 0
    END), 0) -
    COALESCE(SUM(ai.allotted_quantity), 0) as available_quantity,

    lii.cif -
    COALESCE(SUM(CASE
        WHEN rd.transaction_type = 'DEBIT' THEN rd.cif_inr
        ELSE 0
    END), 0) -
    COALESCE(SUM(ai.allotted_cif), 0) as available_cif,

    -- Item restrictions
    lii.is_restricted,

    -- Metadata
    NOW() as last_refreshed

FROM license_licenseimportitemsmodel lii

INNER JOIN license_licensedetailsmodel ld
    ON ld.id = lii.license_id

LEFT JOIN bill_of_entry_rowdetails rd
    ON rd.sr_number_id = lii.id
    AND rd.transaction_type IN ('DEBIT', 'CREDIT')

LEFT JOIN allotment_allotmentitems ai
    ON ai.item_id = lii.id

GROUP BY lii.id, lii.license_id, lii.serial_number, ld.license_number,
         ld.company_id, lii.quantity, lii.cif, lii.is_restricted;

CREATE UNIQUE INDEX IF NOT EXISTS item_balance_mv_item_id_idx
    ON item_balance_mv(item_id);

CREATE INDEX IF NOT EXISTS item_balance_mv_license_id_idx
    ON item_balance_mv(license_id);

CREATE INDEX IF NOT EXISTS item_balance_mv_company_id_idx
    ON item_balance_mv(company_id);

CREATE INDEX IF NOT EXISTS item_balance_mv_available_cif_idx
    ON item_balance_mv(available_cif);

CREATE INDEX IF NOT EXISTS item_balance_mv_available_quantity_idx
    ON item_balance_mv(available_quantity);
"""


DASHBOARD_STATS_VIEW = """
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_stats_mv AS
SELECT
    -- Active licenses stats
    (SELECT COUNT(*) FROM license_licensedetailsmodel
     WHERE is_active = true) as active_licenses_count,

    (SELECT COUNT(*) FROM license_licensedetailsmodel
     WHERE is_active = true
     AND license_expiry_date < CURRENT_DATE) as expired_licenses_count,

    (SELECT COUNT(*) FROM license_licensedetailsmodel
     WHERE is_active = true
     AND license_expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days')
     as expiring_soon_count,

    -- Total CIF values
    (SELECT COALESCE(SUM(total_cif), 0) FROM license_licensedetailsmodel
     WHERE is_active = true) as total_cif_value,

    (SELECT COALESCE(SUM(balance_cif), 0) FROM license_balance_mv
     WHERE is_active = true) as available_cif_value,

    (SELECT COALESCE(SUM(utilized_cif), 0) FROM license_balance_mv
     WHERE is_active = true) as utilized_cif_value,

    -- BOE stats
    (SELECT COUNT(*) FROM bill_of_entry_billofentrymodel
     WHERE boe_date >= CURRENT_DATE - INTERVAL '30 days') as boe_last_30_days,

    -- Allotment stats
    (SELECT COUNT(*) FROM allotment_allotmentmodel
     WHERE allotment_date >= CURRENT_DATE - INTERVAL '30 days') as allotments_last_30_days,

    -- Companies with active licenses
    (SELECT COUNT(DISTINCT company_id) FROM license_licensedetailsmodel
     WHERE is_active = true) as active_companies_count,

    -- Metadata
    NOW() as last_refreshed;

CREATE UNIQUE INDEX IF NOT EXISTS dashboard_stats_mv_idx
    ON dashboard_stats_mv(last_refreshed);
"""


# ============================================================================
# Materialized View Management Functions
# ============================================================================

def create_materialized_views():
    """Create all materialized views."""
    views = [
        ('license_balance_mv', LICENSE_BALANCE_VIEW),
        ('item_balance_mv', ITEM_BALANCE_VIEW),
        ('dashboard_stats_mv', DASHBOARD_STATS_VIEW),
    ]

    with connection.cursor() as cursor:
        for view_name, sql in views:
            try:
                logger.info(f"Creating materialized view: {view_name}")
                cursor.execute(sql)
                logger.info(f"✓ Created {view_name}")
            except Exception as e:
                logger.error(f"✗ Failed to create {view_name}: {e}")
                raise


def drop_materialized_views():
    """Drop all materialized views."""
    views = ['license_balance_mv', 'item_balance_mv', 'dashboard_stats_mv']

    with connection.cursor() as cursor:
        for view_name in views:
            try:
                logger.info(f"Dropping materialized view: {view_name}")
                cursor.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view_name} CASCADE")
                logger.info(f"✓ Dropped {view_name}")
            except Exception as e:
                logger.error(f"✗ Failed to drop {view_name}: {e}")


def refresh_materialized_view(view_name: str, concurrently: bool = False):
    """
    Refresh a single materialized view.

    Args:
        view_name: Name of the materialized view
        concurrently: If True, refresh without locking (requires unique index)
    """
    concurrent_sql = "CONCURRENTLY " if concurrently else ""

    with connection.cursor() as cursor:
        try:
            logger.info(f"Refreshing materialized view: {view_name}")
            cursor.execute(f"REFRESH MATERIALIZED VIEW {concurrent_sql}{view_name}")
            logger.info(f"✓ Refreshed {view_name}")
        except Exception as e:
            logger.error(f"✗ Failed to refresh {view_name}: {e}")
            raise


def refresh_all_materialized_views(concurrently: bool = True):
    """
    Refresh all materialized views.

    Args:
        concurrently: If True, refresh without locking (requires unique indexes)
    """
    views = ['license_balance_mv', 'item_balance_mv', 'dashboard_stats_mv']

    for view_name in views:
        refresh_materialized_view(view_name, concurrently=concurrently)


def get_materialized_view_stats() -> List[dict]:
    """Get statistics about materialized views."""
    sql = """
    SELECT
        schemaname,
        matviewname as view_name,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||matviewname)) as size,
        n_tup_ins as rows_inserted,
        n_tup_upd as rows_updated,
        n_tup_del as rows_deleted,
        last_autovacuum,
        last_autoanalyze
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
    AND relname IN ('license_balance_mv', 'item_balance_mv', 'dashboard_stats_mv')
    """

    with connection.cursor() as cursor:
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def check_materialized_view_freshness(view_name: str) -> Optional[dict]:
    """
    Check when a materialized view was last refreshed.

    Returns dict with last_refreshed timestamp or None if view doesn't exist.
    """
    sql = f"SELECT last_refreshed FROM {view_name} LIMIT 1"

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            result = cursor.fetchone()
            if result:
                return {'view_name': view_name, 'last_refreshed': result[0]}
    except Exception as e:
        logger.warning(f"Could not check freshness of {view_name}: {e}")

    return None


# ============================================================================
# Smart Refresh Strategy
# ============================================================================

def refresh_license_related_views():
    """Refresh views related to license changes."""
    refresh_materialized_view('license_balance_mv', concurrently=True)
    refresh_materialized_view('item_balance_mv', concurrently=True)
    refresh_materialized_view('dashboard_stats_mv', concurrently=True)


def refresh_boe_related_views():
    """Refresh views related to BOE changes."""
    refresh_materialized_view('license_balance_mv', concurrently=True)
    refresh_materialized_view('item_balance_mv', concurrently=True)
    refresh_materialized_view('dashboard_stats_mv', concurrently=True)


def refresh_allotment_related_views():
    """Refresh views related to allotment changes."""
    refresh_materialized_view('license_balance_mv', concurrently=True)
    refresh_materialized_view('item_balance_mv', concurrently=True)
    refresh_materialized_view('dashboard_stats_mv', concurrently=True)


# ============================================================================
# Query Helpers (Use Materialized Views)
# ============================================================================

def get_license_balance(license_id: int) -> Optional[dict]:
    """Get license balance from materialized view."""
    sql = """
    SELECT
        license_id,
        license_number,
        total_cif,
        utilized_cif,
        allotted_cif,
        balance_cif,
        last_refreshed
    FROM license_balance_mv
    WHERE license_id = %s
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, [license_id])
        row = cursor.fetchone()
        if row:
            return {
                'license_id': row[0],
                'license_number': row[1],
                'total_cif': row[2],
                'utilized_cif': row[3],
                'allotted_cif': row[4],
                'balance_cif': row[5],
                'last_refreshed': row[6],
            }
    return None


def get_item_balance(item_id: int) -> Optional[dict]:
    """Get item balance from materialized view."""
    sql = """
    SELECT
        item_id,
        license_id,
        license_number,
        total_quantity,
        total_cif,
        utilized_quantity,
        utilized_cif,
        allotted_quantity,
        allotted_cif,
        available_quantity,
        available_cif,
        is_restricted,
        last_refreshed
    FROM item_balance_mv
    WHERE item_id = %s
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, [item_id])
        row = cursor.fetchone()
        if row:
            return {
                'item_id': row[0],
                'license_id': row[1],
                'license_number': row[2],
                'total_quantity': row[3],
                'total_cif': row[4],
                'utilized_quantity': row[5],
                'utilized_cif': row[6],
                'allotted_quantity': row[7],
                'allotted_cif': row[8],
                'available_quantity': row[9],
                'available_cif': row[10],
                'is_restricted': row[11],
                'last_refreshed': row[12],
            }
    return None


def get_dashboard_stats() -> Optional[dict]:
    """Get dashboard statistics from materialized view."""
    sql = "SELECT * FROM dashboard_stats_mv LIMIT 1"

    with connection.cursor() as cursor:
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        if row:
            return dict(zip(columns, row))
    return None
