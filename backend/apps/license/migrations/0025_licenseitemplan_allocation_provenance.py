from django.db import migrations, models


def configure_e5_split(apps, schema_editor):
    Action = apps.get_model("license", "SionPlanningAction")
    for action in Action.objects.filter(stable_key="E5:ACTION:040:NORMAL_MILK"):
        config = dict(action.config or {})
        config.update({
            "algorithm": "SPLIT_BY_UNIT_VALUE",
            "basis": "BALANCE_CIF_PER_QUANTITY",
            "category": "MILK PRODUCTS",
            "buckets": [
                {"code": "SWP", "min_price": "0.00", "max_price": "1.50", "reference_price": "1.50"},
                {"code": "DWP", "min_price": "1.50", "max_price": "6.50", "reference_price": "6.50"},
            ],
        })
        action.config = config
        action.version += 1
        action.save(update_fields=("config", "version"))


class Migration(migrations.Migration):
    dependencies = [("license", "0024_activate_complete_e1_rule_config")]

    operations = [
        migrations.AddField(
            model_name="licenseitemplan",
            name="allocation_provenance",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(configure_e5_split, migrations.RunPython.noop),
    ]
