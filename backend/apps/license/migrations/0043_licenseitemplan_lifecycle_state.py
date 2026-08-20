from django.db import migrations, models


class Migration(migrations.Migration):
    """Add non-destructive lifecycle state for persisted plan lines."""

    dependencies = [("license", "0042_map_rutile_parent_actuals")]

    operations = [
        migrations.AddField(
            model_name="licenseitemplan",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="licenseitemplan",
            name="is_deleted",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="licenseitemplan",
            name="is_cancelled",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
