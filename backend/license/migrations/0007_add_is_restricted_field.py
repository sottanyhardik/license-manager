# Generated migration for adding is_restricted field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0006_rename_hsn_code_invoiceitem_hs_code_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='licenseimportitemsmodel',
            name='is_restricted',
            field=models.BooleanField(
                default=False,
                help_text='If True, uses restriction-based calculation (2%, 3%, 5%, 10% etc.). If False, uses license balance.'
            ),
        ),
    ]
