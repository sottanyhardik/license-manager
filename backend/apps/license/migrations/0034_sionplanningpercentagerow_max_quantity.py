import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("license", "0033_backfill_strategy_field")]

    operations = [
        migrations.AddField(
            model_name="sionplanningpercentagerow",
            name="max_quantity",
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                help_text="Optional theoretical quantity ceiling applied after the percentage split.",
                max_digits=15,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0.000"))],
            ),
        ),
    ]
