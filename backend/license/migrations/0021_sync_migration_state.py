# Generated manually to sync migration state with actual database
# After purchase_status migration to ForeignKey, Django's state got out of sync

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0029_populate_purchase_status_data'),
        ('license', '0020_remove_licensedetailsmodel_license_lic_purchas_97c381_idx'),
    ]

    operations = [
        # This AlterField operation updates Django's migration state to match reality
        # The purchase_status field is already a ForeignKey in the database
        # This just tells Django's migration system about it
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
            # db_column is not specified, so Django uses default: purchase_status_id
        ),
    ]
