# Generated migration for cif_restriction_percentage fields

from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("license", "0055_rename_license_led_trade_i_0b20a4_idx_license_lic_trade_i_795ec5_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="sionplanningrule",
            name="cif_restriction_percentage",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    "Max CIF % of each matched import item's total CIF that can be planned "
                    "(debited + allotted). Allowed values: 2, 3, 5, 10, or NULL (no restriction)."
                ),
                max_digits=4,
                null=True,
                validators=[
                    MinValueValidator(Decimal("0")),
                    MaxValueValidator(Decimal("100")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="sionplanningunitvaluerow",
            name="cif_restriction_percentage",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    "Max CIF % of this import item's total CIF that can be planned. "
                    "Allowed values: 2, 3, 5, 10, or NULL (inherit from rule)."
                ),
                max_digits=4,
                null=True,
                validators=[
                    MinValueValidator(Decimal("0")),
                    MaxValueValidator(Decimal("100")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="sionplanningpercentagerow",
            name="cif_restriction_percentage",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    "Max CIF % of this import item's total CIF that can be planned. "
                    "Allowed values: 2, 3, 5, 10, or NULL (inherit from rule)."
                ),
                max_digits=4,
                null=True,
                validators=[
                    MinValueValidator(Decimal("0")),
                    MaxValueValidator(Decimal("100")),
                ],
            ),
        ),
    ]
