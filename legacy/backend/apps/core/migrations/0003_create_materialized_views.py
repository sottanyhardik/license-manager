"""Ensure materialized views exist after the normalization refactor.

Migration license/0005 dropped license_balance_mv / item_balance_mv / dashboard_stats_mv
and noted they'd be recreated by the next call to create_materialized_views(),
but no automated path actually called it. Servers that ran 0005 ended up without
the views, surfacing as `relation "license_balance_mv" does not exist` at query time.

This migration calls create_materialized_views() — the helper uses
`CREATE MATERIALIZED VIEW IF NOT EXISTS`, so it's safe on servers that already
have the views (e.g. manually recreated ones).
"""
from django.db import migrations


def _create_views(apps, schema_editor):
    # Lazy import — keeps the migration importable even if the helper module
    # changes later. The helper SQL targets the post-0005 schema.
    from apps.core.materialized_views import create_materialized_views
    create_materialized_views()


def _drop_views(apps, schema_editor):
    from apps.core.materialized_views import drop_materialized_views
    drop_materialized_views()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_remove_companymodel_address"),
        # Depends on the normalization migration that introduced LicenseFlags etc.
        # The view SQL references license_licenseflags.
        ("license", "0005_licensebalance_licenseflags_licensenotes_and_more"),
    ]

    operations = [
        migrations.RunPython(_create_views, reverse_code=_drop_views),
    ]
