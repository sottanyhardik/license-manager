# Generated manually for version 4.4

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_alter_transferlettermodel_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchasestatus',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Whether this purchase status is active and should be shown in UI'),
        ),
        migrations.AddField(
            model_name='purchasestatus',
            name='display_order',
            field=models.IntegerField(default=0, help_text='Order for displaying in dropdowns'),
        ),
        migrations.AlterModelOptions(
            name='purchasestatus',
            options={'ordering': ['display_order', 'label'], 'verbose_name': 'Purchase Status', 'verbose_name_plural': 'Purchase Statuses'},
        ),
    ]
