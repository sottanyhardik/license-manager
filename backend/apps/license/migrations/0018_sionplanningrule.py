from decimal import Decimal

import django.db.models.deletion
import django.core.validators
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_split_milk_into_swp_dwp_wpc"),
        ("license", "0017_alter_licensedetailsmodel_port"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SionPlanningRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("modified_on", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("version", models.PositiveIntegerField(default=1)),
                ("expression", models.JSONField(default=dict)),
                ("max_unit_price", models.DecimalField(decimal_places=2, max_digits=15, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("unit", models.CharField(choices=[("kg", "Kgs"), ("pcs", "Pcs"), ("nos", "Nos"), ("mts", "Mts")], max_length=10)),
                ("priority", models.IntegerField(db_index=True, default=100)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("modified_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
                ("sion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="planning_rules", to="core.sionnormclassmodel")),
            ],
            options={"ordering": ("sion_id", "priority", "name", "-version")},
        ),
        migrations.AddConstraint(
            model_name="sionplanningrule",
            constraint=models.UniqueConstraint(fields=("sion", "name", "version"), name="uniq_sion_planning_rule_version"),
        ),
        migrations.AddConstraint(
            model_name="sionplanningrule",
            constraint=models.CheckConstraint(condition=models.Q(("max_unit_price__gte", Decimal("0"))), name="sion_rule_nonnegative_max_price"),
        ),
        migrations.AddIndex(
            model_name="sionplanningrule",
            index=models.Index(fields=["sion", "is_active", "priority"], name="license_sio_sion_id_82a099_idx"),
        ),
    ]
