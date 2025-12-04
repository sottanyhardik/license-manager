# Generated manually to fix NULL constraint mismatches

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_change_restriction_norm_to_fk'),
    ]

    operations = [
        # Fix address_line_2 to allow NULL
        migrations.AlterField(
            model_name='invoiceentity',
            name='address_line_2',
            field=models.TextField(blank=True, default=''),
        ),
    ]
