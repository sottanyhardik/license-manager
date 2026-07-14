"""
Drop the remaining orphan columns left over from migration 0005.

Background
----------
Migration 0005_licensebalance_licenseflags_licensenotes_and_more moved 18
fields off LicenseDetailsModel into four OneToOne sub-tables (LicenseBalance,
LicenseFlags, LicenseNotes, LicenseOwnership). It also issued RemoveField
operations for all 18 columns on the parent — but on at least one production
database the column drops didn't actually execute at the SQL level, leaving
both halves of the schema in place.

Django thinks the columns are gone (the migration is recorded as applied),
so its INSERT statements never mention them. PostgreSQL still has them with
NOT NULL constraints intact, so every new license INSERT fails with:

    IntegrityError: null value in column "is_audit" violates not-null constraint

(also reproducible for is_active, is_mnm, is_null, is_au, is_incomplete,
is_expired, is_individual, balance_cif).

This migration corrects the drift idempotently with DROP COLUMN IF EXISTS.
On databases where 0005 worked the first time, every statement is a no-op;
on the drifted ones, the 18 orphan columns are removed.

Safety: every column on the parent has an equivalent column on the
corresponding sub-table that the @property accessors and the rest of the
application have been reading from since 0005 was applied — the parent
copies are dead data.
"""
from django.db import migrations


# Grouped by destination sub-table just for readability; the actual SQL just
# drops the column off the parent regardless of where it now lives.
_ORPHAN_COLUMNS = [
    # → LicenseBalance
    "balance_cif",
    "ledger_date",
    # → LicenseFlags
    "is_active",
    "is_audit",
    "is_mnm",
    "is_not_registered",
    "is_null",
    "is_au",
    "is_incomplete",
    "is_expired",
    "is_individual",
    # → LicenseOwnership
    "current_owner_id",
    "file_transfer_status",
    "last_ownership_fetch",
    # → LicenseNotes
    "user_comment",
    "condition_sheet",
    "user_restrictions",
    "balance_report_notes",
]


class Migration(migrations.Migration):

    dependencies = [
        ("license", "0006_drop_obsolete_scheme_notification_columns"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                f'ALTER TABLE license_licensedetailsmodel '
                f'DROP COLUMN IF EXISTS "{col}" CASCADE;'
                for col in _ORPHAN_COLUMNS
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
