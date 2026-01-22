# Generated manually for version 4.4
# Updates the purchase_status index after FK migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0017_rename_license_lic_purchas_97c381_idx_license_lic_purchas_dadd94_idx'),
    ]

    operations = [
        # Remove old index if it exists (it may have been auto-created with wrong name)
        # Then add the correct index for the FK field
        migrations.AlterField(
            model_name='licensedetailsmodel',
            name='purchase_status',
            field=models.ForeignKey(
                blank=True,
                help_text='Purchase status for this license',
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name='licenses',
                to='core.purchasestatus'
            ),
        ),
    ]
