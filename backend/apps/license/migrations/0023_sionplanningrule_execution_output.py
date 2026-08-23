from django.db import migrations, models


def backfill_known_outputs(apps, schema_editor):
    Rule = apps.get_model("license", "SionPlanningRule")
    known = {
        ("E1", "OTHER CONFECTIONERY"): "OTHER CONFECTIONERY INGREDIENTS",
        ("E1", "WPC"): "EGG ALBUMIN",
    }
    for rule in Rule.objects.filter(execution_output="").select_related("sion"):
        output = known.get((rule.sion.norm_class.strip().upper(), rule.name.strip().upper()))
        if output:
            rule.execution_output = output
            rule.save(update_fields=("execution_output",))


class Migration(migrations.Migration):
    dependencies = [("license", "0022_rule_stable_key_versioning")]
    operations = [
        migrations.AddField(
            model_name="sionplanningrule",
            name="execution_output",
            field=models.CharField(
                blank=True, default="", max_length=120,
                help_text="Legacy execution bucket supplied by the SION planning profile/UI.",
            ),
        ),
        migrations.RunPython(backfill_known_outputs, migrations.RunPython.noop),
    ]
