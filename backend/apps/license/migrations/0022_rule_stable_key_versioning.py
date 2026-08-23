from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("license", "0021_sionplanningrule_stable_key")]

    operations = [
        migrations.AlterField(
            model_name="sionplanningrule",
            name="stable_key",
            field=models.CharField(blank=True, db_index=True, max_length=120, null=True),
        ),
        migrations.AddConstraint(
            model_name="sionplanningrule",
            constraint=models.UniqueConstraint(
                condition=models.Q(stable_key__isnull=False),
                fields=("sion", "stable_key", "version"),
                name="uniq_sion_rule_stable_key_version",
            ),
        ),
    ]
