from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("license", "0020_sion_planner_profiles_actions_runs")]

    operations = [
        migrations.AddField(
            model_name="sionplanningrule",
            name="stable_key",
            field=models.CharField(blank=True, max_length=120, null=True, unique=True),
        ),
    ]
