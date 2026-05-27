"""
Migration: Phase 3b-1 (expand) — Add proper FK columns to LicenseTransferModel
to replace the plain CharField user-ID copies.

Old fields (kept, not dropped yet):
  user_id_transfer_initiation = CharField
  user_id_acceptance = CharField

New FK fields (nullable, backfilled by next data migration):
  transfer_initiation_user = ForeignKey(User)
  acceptance_user = ForeignKey(User)
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0029_licensedetailsmodel_last_ownership_fetch'),
        ('accounts', '0007_add_avatar_to_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='licensetransfermodel',
            name='transfer_initiation_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='transfer_initiations',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='licensetransfermodel',
            name='acceptance_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='transfer_acceptances',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
