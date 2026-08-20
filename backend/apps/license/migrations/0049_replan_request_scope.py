from django.db import migrations, models


def populate_scope(apps, schema_editor):
    Request = apps.get_model("license", "LicenseReplanRequest")
    Request.objects.filter(source_model="sion_planning_rule.plan_sion").update(
        scope="SION",
        sion_id=models.functions.Cast("source_pk", models.PositiveBigIntegerField()),
    )


class Migration(migrations.Migration):
    dependencies = [("license", "0048_seed_canonical_e5_planner_profile")]

    operations = [
        migrations.AddField(
            model_name="licensereplanrequest",
            name="scope",
            field=models.CharField(
                choices=[("LICENSE", "Licence"), ("SION", "SION")],
                default="LICENSE",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="licensereplanrequest",
            name="sion_id",
            field=models.PositiveBigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(populate_scope, migrations.RunPython.noop),
    ]
