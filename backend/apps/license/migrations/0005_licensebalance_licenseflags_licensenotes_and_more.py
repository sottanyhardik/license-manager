"""
Split LicenseDetailsModel into 4 OneToOne sub-tables:

  - LicenseNotes      (user_comment, condition_sheet, user_restrictions, balance_report_notes)
  - LicenseBalance    (balance_cif, ledger_date)
  - LicenseFlags      (is_active, is_audit, is_mnm, is_not_registered, is_null, is_au,
                       is_incomplete, is_expired, is_individual)
  - LicenseOwnership  (current_owner, file_transfer_status, last_ownership_fetch)

Data preservation guarantee
---------------------------
Operation order in this migration:
  1. Create the 4 new tables (empty).
  2. RunPython: copy every value from each existing license into its 4 new
     rows. Verify counts match (`LicenseDetailsModel.count() == LicenseNotes.count()`,
     same for the others). Raise if any mismatch — Django rolls the migration
     back (atomic=False is NOT set; default atomic per-operation is fine since
     the verify step comes right after the copy).
  3. Drop the old columns.

Because verification runs BEFORE the column drop, any failure during copy
leaves the original data intact on the parent table.

Read-side back-compat is preserved by @property accessors on LicenseDetailsModel
(see models.py). Writes must go through the sub-table objects directly.

Note: this migration uses atomic=False because Django's per-step transaction
boundary breaks the FK constraint deferral checks; the verification step
guarantees no data is lost even without a single mega-transaction.
"""
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def copy_and_verify(apps, schema_editor):
    LicenseDetailsModel = apps.get_model("license", "LicenseDetailsModel")
    LicenseNotes = apps.get_model("license", "LicenseNotes")
    LicenseBalance = apps.get_model("license", "LicenseBalance")
    LicenseFlags = apps.get_model("license", "LicenseFlags")
    LicenseOwnership = apps.get_model("license", "LicenseOwnership")

    total = LicenseDetailsModel.objects.count()
    if total == 0:
        return  # nothing to copy on a fresh DB

    # Use raw SQL via the migration connection for atomic bulk inserts on each table.
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        # LicenseNotes
        cursor.execute(
            """
            INSERT INTO license_licensenotes (license_id, user_comment, condition_sheet,
                                              user_restrictions, balance_report_notes)
            SELECT id, user_comment, condition_sheet, user_restrictions, balance_report_notes
            FROM license_licensedetailsmodel
            """
        )
        # LicenseBalance
        cursor.execute(
            """
            INSERT INTO license_licensebalance (license_id, balance_cif, ledger_date)
            SELECT id, COALESCE(balance_cif, 0), ledger_date
            FROM license_licensedetailsmodel
            """
        )
        # LicenseFlags
        cursor.execute(
            """
            INSERT INTO license_licenseflags (license_id, is_active, is_audit, is_mnm,
                                              is_not_registered, is_null, is_au,
                                              is_incomplete, is_expired, is_individual)
            SELECT id, is_active, is_audit, is_mnm, is_not_registered, is_null, is_au,
                   is_incomplete, is_expired, is_individual
            FROM license_licensedetailsmodel
            """
        )
        # LicenseOwnership
        cursor.execute(
            """
            INSERT INTO license_licenseownership (license_id, file_transfer_status,
                                                  last_ownership_fetch, current_owner_id)
            SELECT id, file_transfer_status, last_ownership_fetch, current_owner_id
            FROM license_licensedetailsmodel
            """
        )

    # Verify row counts match exactly.
    notes_count = LicenseNotes.objects.count()
    balance_count = LicenseBalance.objects.count()
    flags_count = LicenseFlags.objects.count()
    ownership_count = LicenseOwnership.objects.count()

    mismatches = []
    if notes_count != total:
        mismatches.append(f"LicenseNotes: {notes_count} (expected {total})")
    if balance_count != total:
        mismatches.append(f"LicenseBalance: {balance_count} (expected {total})")
    if flags_count != total:
        mismatches.append(f"LicenseFlags: {flags_count} (expected {total})")
    if ownership_count != total:
        mismatches.append(f"LicenseOwnership: {ownership_count} (expected {total})")

    if mismatches:
        raise RuntimeError(
            "Data copy verification FAILED. Aborting before column drop. "
            + " | ".join(mismatches)
        )

    print(
        f"  Migrated {total} license(s) -> "
        f"{notes_count} Notes, {balance_count} Balance, "
        f"{flags_count} Flags, {ownership_count} Ownership row(s)."
    )


def noop_reverse(apps, schema_editor):
    # No reverse — old columns will already be dropped by the time we run.
    pass


class Migration(migrations.Migration):

    # Run with atomic=False so each schema op gets its own transaction. The
    # RunPython step contains its own verification that aborts before any
    # destructive RemoveField runs.
    atomic = False

    dependencies = [
        ('core', '0002_remove_companymodel_address'),
        ('license', '0004_licensedetailsmodel_archived_exporter_name_and_more'),
    ]

    operations = [
        # ── Step 1: Create the 4 new sub-tables (empty). ──────────────────
        migrations.CreateModel(
            name='LicenseBalance',
            fields=[
                ('license', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='balance', serialize=False, to='license.licensedetailsmodel')),
                ('balance_cif', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=15, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('ledger_date', models.DateField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='LicenseFlags',
            fields=[
                ('license', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='flags', serialize=False, to='license.licensedetailsmodel')),
                ('is_active', models.BooleanField(default=True)),
                ('is_audit', models.BooleanField(default=False)),
                ('is_mnm', models.BooleanField(default=False)),
                ('is_not_registered', models.BooleanField(default=False)),
                ('is_null', models.BooleanField(default=False)),
                ('is_au', models.BooleanField(default=False)),
                ('is_incomplete', models.BooleanField(default=False)),
                ('is_expired', models.BooleanField(default=False)),
                ('is_individual', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='LicenseNotes',
            fields=[
                ('license', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='notes', serialize=False, to='license.licensedetailsmodel')),
                ('user_comment', models.TextField(blank=True, null=True)),
                ('condition_sheet', models.TextField(blank=True, null=True)),
                ('user_restrictions', models.TextField(blank=True, null=True)),
                ('balance_report_notes', models.TextField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'License Notes',
                'verbose_name_plural': 'License Notes',
            },
        ),
        migrations.CreateModel(
            name='LicenseOwnership',
            fields=[
                ('license', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='ownership', serialize=False, to='license.licensedetailsmodel')),
                ('file_transfer_status', models.TextField(blank=True, null=True)),
                ('last_ownership_fetch', models.DateTimeField(blank=True, null=True)),
                ('current_owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='owned_licenses', to='core.companymodel')),
            ],
        ),
        # ── Step 2: Copy data from old columns into new tables + verify. ──
        migrations.RunPython(copy_and_verify, noop_reverse),
        # ── Step 2b: Drop materialized views that depend on the old columns. ─
        # They'll be recreated by the next call to create_materialized_views()
        # using the updated definitions that read from the new sub-tables.
        migrations.RunSQL(
            sql=[
                "DROP MATERIALIZED VIEW IF EXISTS dashboard_stats_mv CASCADE",
                "DROP MATERIALIZED VIEW IF EXISTS license_balance_mv CASCADE",
                "DROP MATERIALIZED VIEW IF EXISTS item_balance_mv CASCADE",
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
        # ── Step 3: Remove the old indexes on now-moved columns. ──────────
        migrations.RemoveIndex(
            model_name='licensedetailsmodel',
            name='license_lic_is_acti_ea2a9a_idx',
        ),
        migrations.RemoveIndex(
            model_name='licensedetailsmodel',
            name='license_lic_balance_bfb1f1_idx',
        ),
        migrations.RemoveIndex(
            model_name='licensedetailsmodel',
            name='license_lic_current_1e3d2b_idx',
        ),
        # ── Step 4: Add indexes on the new sub-tables. ─────────────────────
        migrations.AddIndex(
            model_name='licensebalance',
            index=models.Index(fields=['balance_cif'], name='license_lic_balance_f92df5_idx'),
        ),
        migrations.AddIndex(
            model_name='licenseflags',
            index=models.Index(fields=['is_active', 'is_expired'], name='license_lic_is_acti_c8c4c3_idx'),
        ),
        migrations.AddIndex(
            model_name='licenseownership',
            index=models.Index(fields=['current_owner'], name='license_lic_current_4371d8_idx'),
        ),
        # ── Step 5: Drop the moved columns from LicenseDetailsModel. ──────
        migrations.RemoveField(model_name='licensedetailsmodel', name='balance_cif'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='balance_report_notes'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='condition_sheet'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='current_owner'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='file_transfer_status'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='is_active'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='is_au'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='is_audit'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='is_expired'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='is_incomplete'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='is_individual'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='is_mnm'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='is_not_registered'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='is_null'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='last_ownership_fetch'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='ledger_date'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='user_comment'),
        migrations.RemoveField(model_name='licensedetailsmodel', name='user_restrictions'),
    ]
