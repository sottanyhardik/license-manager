# Generated manually for version 4.4

from django.db import migrations, models
import django.db.models.deletion


def migrate_purchase_status_to_fk(apps, schema_editor):
    """Migrate existing purchase_status values to FK references"""
    LicenseDetailsModel = apps.get_model('license', 'LicenseDetailsModel')
    PurchaseStatus = apps.get_model('core', 'PurchaseStatus')

    # Create a mapping of code -> PurchaseStatus instance
    purchase_status_map = {ps.code: ps for ps in PurchaseStatus.objects.all()}

    # Update all licenses with the new FK
    for license in LicenseDetailsModel.objects.all():
        old_code = license.purchase_status
        if old_code in purchase_status_map:
            license.purchase_status_new = purchase_status_map[old_code]
            license.save(update_fields=['purchase_status_new'])


def reverse_migrate(apps, schema_editor):
    """Reverse migration - copy FK back to CharField"""
    LicenseDetailsModel = apps.get_model('license', 'LicenseDetailsModel')

    for license in LicenseDetailsModel.objects.all():
        if license.purchase_status_new:
            license.purchase_status = license.purchase_status_new.code
            license.save(update_fields=['purchase_status'])


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0015_licenseimportitemsmodel_license_lic_availab_1f176a_idx_and_more'),
        ('core', '0029_populate_purchase_status_data'),
    ]

    operations = [
        # Step 1: Add new FK field
        migrations.AddField(
            model_name='licensedetailsmodel',
            name='purchase_status_new',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='core.purchasestatus',
                related_name='licenses',
                help_text='Purchase status for this license'
            ),
        ),

        # Step 2: Migrate data
        migrations.RunPython(migrate_purchase_status_to_fk, reverse_migrate),

        # Step 3: Remove old CharField
        migrations.RemoveField(
            model_name='licensedetailsmodel',
            name='purchase_status',
        ),

        # Step 4: Rename new field to original name
        migrations.RenameField(
            model_name='licensedetailsmodel',
            old_name='purchase_status_new',
            new_name='purchase_status',
        ),
    ]
