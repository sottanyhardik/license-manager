from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("license", "0051_licenseledgerpackagejob")]

    operations = [
        # Existing completed records mean only that a worker made an artifact;
        # no historic browser save was verified, so represent them accurately.
        migrations.RunSQL("UPDATE license_licenseledgerpackageitem SET status = 'server_ready' WHERE status = 'completed';", "UPDATE license_licenseledgerpackageitem SET status = 'completed' WHERE status = 'server_ready';"),
        migrations.RunSQL("UPDATE license_licenseledgerpackagejob SET status = 'server_ready' WHERE status = 'completed';", "UPDATE license_licenseledgerpackagejob SET status = 'completed' WHERE status = 'server_ready';"),
        migrations.AlterField(
            model_name="licenseledgerpackagejob", name="status",
            field=models.CharField(choices=[
                ("queued", "Queued"), ("generating", "Generating"),
                ("validating_sources", "Validating Sources"), ("merging", "Merging"),
                ("server_ready", "Server Ready"), ("failed", "Failed"), ("partial_failed", "Partial Failed"),
            ], db_index=True, default="queued", max_length=20),
        ),
        migrations.AlterField(
            model_name="licenseledgerpackageitem", name="status",
            field=models.CharField(choices=[
                ("queued", "Queued"), ("generating", "Generating"),
                ("validating_sources", "Validating Sources"), ("merging", "Merging"),
                ("server_ready", "Server Ready"), ("failed", "Failed"),
            ], db_index=True, default="queued", max_length=20),
        ),
    ]
