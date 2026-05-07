# Generated manually - Create materialized views for better performance

from django.db import migrations
from core.materialized_views import (
    LICENSE_BALANCE_VIEW,
    ITEM_BALANCE_VIEW,
    DASHBOARD_STATS_VIEW
)


def create_materialized_views(apps, schema_editor):
    """Create materialized views."""
    if schema_editor.connection.vendor != 'postgresql':
        return  # Only for PostgreSQL

    with schema_editor.connection.cursor() as cursor:
        # Create license balance view
        cursor.execute(LICENSE_BALANCE_VIEW)

        # Create item balance view
        cursor.execute(ITEM_BALANCE_VIEW)

        # Create dashboard stats view
        cursor.execute(DASHBOARD_STATS_VIEW)


def drop_materialized_views(apps, schema_editor):
    """Drop materialized views."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP MATERIALIZED VIEW IF EXISTS license_balance_mv CASCADE")
        cursor.execute("DROP MATERIALIZED VIEW IF EXISTS item_balance_mv CASCADE")
        cursor.execute("DROP MATERIALIZED VIEW IF EXISTS dashboard_stats_mv CASCADE")


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0030_add_composite_performance_indexes'),
        ('license', '0024_add_composite_performance_indexes'),
        ('bill_of_entry', '0005_add_composite_performance_indexes'),
        ('allotment', '0014_add_composite_performance_indexes'),
    ]

    operations = [
        migrations.RunPython(
            create_materialized_views,
            reverse_code=drop_materialized_views
        ),
    ]
