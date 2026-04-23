from decimal import Decimal

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('bill_of_entry', '0007_rowdetails_is_frozen'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rowdetails',
            name='cif_inr',
            field=models.DecimalField(
                default=Decimal('0'),
                decimal_places=3,
                max_digits=15,
                validators=[django.core.validators.MinValueValidator(Decimal('0'))],
            ),
        ),
        migrations.AlterField(
            model_name='rowdetails',
            name='cif_fc',
            field=models.DecimalField(
                default=Decimal('0'),
                decimal_places=3,
                max_digits=15,
                validators=[django.core.validators.MinValueValidator(Decimal('0'))],
            ),
        ),
    ]
