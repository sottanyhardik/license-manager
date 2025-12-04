# Generated manually

from django.db import migrations, models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_add_restriction_group_to_item_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemnamemodel',
            name='restriction_percentage',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0'),
                help_text="Restriction percentage for this item (e.g., 2.00 for 2%, 10.00 for 10%)",
                max_digits=5,
                validators=[MinValueValidator(Decimal('0'))]
            ),
        ),
    ]
