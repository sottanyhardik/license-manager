import django.db.models.deletion
from django.db import migrations, models


def normalize_active_priorities(apps, schema_editor):
    Rule = apps.get_model("license", "SionPlanningRule")
    sion_ids = Rule.objects.filter(is_active=True).values_list("sion_id", flat=True).distinct()
    for sion_id in sion_ids:
        rules = list(Rule.objects.filter(
            sion_id=sion_id, is_active=True,
        ).order_by("priority", "pk"))
        for priority, rule in enumerate(rules, start=1):
            rule.priority = priority
        Rule.objects.bulk_update(rules, ("priority",))


class Migration(migrations.Migration):
    dependencies = [("license", "0018_sionplanningrule")]

    operations = [
        migrations.AddField(
            model_name="licenseitemplan",
            name="planning_rule",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="generated_plan_lines", to="license.sionplanningrule",
            ),
        ),
        migrations.AddField(
            model_name="licenseitemplan", name="planning_rule_priority",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="licenseitemplan", name="planning_rule_version",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(normalize_active_priorities, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="sionplanningrule",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_active=True), fields=("sion", "priority"),
                name="uniq_active_sion_rule_priority",
            ),
        ),
    ]
