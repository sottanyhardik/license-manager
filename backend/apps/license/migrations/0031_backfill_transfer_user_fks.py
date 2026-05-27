"""
Migration: Phase 3b-2 (backfill) — Populate the new FK columns on LicenseTransferModel
by resolving the existing user_id_transfer_initiation / user_id_acceptance CharFields
against User.pk.

Rows with non-numeric or non-existent IDs are left as NULL.
"""
from django.conf import settings
from django.db import migrations


def backfill_user_fks(apps, schema_editor):
    LicenseTransferModel = apps.get_model('license', 'LicenseTransferModel')
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)

    existing_user_ids = set(User.objects.values_list('id', flat=True))

    updates = []
    for transfer in LicenseTransferModel.objects.all():
        changed = False

        raw_init = transfer.user_id_transfer_initiation
        if raw_init:
            try:
                uid = int(raw_init)
                if uid in existing_user_ids:
                    transfer.transfer_initiation_user_id = uid
                    changed = True
            except (ValueError, TypeError):
                pass

        raw_accept = transfer.user_id_acceptance
        if raw_accept:
            try:
                uid = int(raw_accept)
                if uid in existing_user_ids:
                    transfer.acceptance_user_id = uid
                    changed = True
            except (ValueError, TypeError):
                pass

        if changed:
            updates.append(transfer)

    if updates:
        LicenseTransferModel.objects.bulk_update(
            updates, ['transfer_initiation_user_id', 'acceptance_user_id']
        )


def reverse_backfill(apps, schema_editor):
    LicenseTransferModel = apps.get_model('license', 'LicenseTransferModel')
    LicenseTransferModel.objects.all().update(
        transfer_initiation_user=None,
        acceptance_user=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0030_licencetransfer_add_user_fks'),
    ]

    operations = [
        migrations.RunPython(backfill_user_fks, reverse_backfill),
    ]
