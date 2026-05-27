# Generated manually

from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_remove_sionimportmodel_hs_code_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemheadmodel',
            name='restriction_norm',
            field=models.CharField(blank=True, help_text='Norm code for restriction (e.g., E132)', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='itemheadmodel',
            name='restriction_percentage',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), help_text='Restriction percentage (e.g., 3.00 for 3%)', max_digits=5, validators=[MinValueValidator(Decimal('0'))]),
        ),
    ]
