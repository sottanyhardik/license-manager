from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bill_of_entry', '0006_remove_billofentrymodel_boe_company_date_desc_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='rowdetails',
            name='is_frozen',
            field=models.BooleanField(default=False, help_text='Set to True when this row is created/updated from a ledger upload. Frozen rows cannot be edited from the frontend.'),
        ),
    ]
