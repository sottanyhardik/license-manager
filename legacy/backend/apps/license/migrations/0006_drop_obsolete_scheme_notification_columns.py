"""
Drop obsolete scheme_code / notification_number varchar columns.

Background
----------
Migration 0002_scheme_and_notification_to_fk was supposed to drop the original
varchar `scheme_code` and `notification_number` columns after copying their
values into the new FK columns (`scheme_code_id`, `notification_number_id`).

On at least one deployed database the RemoveField operations didn't actually
drop the columns at the SQL level — Django records 0002 as applied, but
PostgreSQL still has the columns sitting there with a NOT NULL constraint.
Every license INSERT now fails:

    IntegrityError: null value in column "scheme_code" of relation
    "license_licensedetailsmodel" violates not-null constraint

This migration corrects the drift by dropping the columns idempotently with
raw SQL. `IF EXISTS` makes it a no-op on databases where 0002 did the right
thing the first time.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("license", "0005_licensebalance_licenseflags_licensenotes_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                'ALTER TABLE license_licensedetailsmodel DROP COLUMN IF EXISTS scheme_code;',
                'ALTER TABLE license_licensedetailsmodel DROP COLUMN IF EXISTS notification_number;',
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
