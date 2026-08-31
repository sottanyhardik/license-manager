from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("license", "0050_licensedetails_individual_item_cif_override")]

    operations = [
        migrations.CreateModel(
            name="LicenseLedgerPackageJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(db_index=True, max_length=64, unique=True)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed"), ("partial_failed", "Partial Failed")], db_index=True, default="queued", max_length=20)),
                ("idempotency_key", models.CharField(blank=True, db_index=True, default="", max_length=255)),
                ("requested_ids", models.JSONField(default=list)),
                ("manifest_key", models.CharField(blank=True, default="", max_length=512)),
                ("archive_key", models.CharField(blank=True, default="", max_length=512)),
                ("error", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(blank=True, null=True)), ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="license_ledger_package_jobs", to=settings.AUTH_USER_MODEL)),
            ], options={"indexes": [models.Index(fields=["requested_by", "idempotency_key", "created_at"], name="license_led_request_4ab8f8_idx")]},
        ),
        migrations.CreateModel(
            name="LicenseLedgerPackageItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("licence_number", models.CharField(max_length=100)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], db_index=True, default="queued", max_length=20)),
                ("attempts", models.PositiveIntegerField(default=0)), ("celery_task_id", models.CharField(blank=True, default="", max_length=255)),
                ("started_at", models.DateTimeField(blank=True, null=True)), ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("section_manifest", models.JSONField(default=dict)), ("output_key", models.CharField(blank=True, default="", max_length=512)),
                ("output_checksum", models.CharField(blank=True, default="", max_length=128)), ("output_size", models.BigIntegerField(default=0)),
                ("output_page_count", models.PositiveIntegerField(default=0)), ("error", models.TextField(blank=True, default="")),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="license.licenseledgerpackagejob")),
                ("license", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ledger_package_items", to="license.licensedetailsmodel")),
            ], options={"indexes": [models.Index(fields=["job", "status"], name="license_led_job_id_9940d0_idx")], "constraints": [models.UniqueConstraint(fields=("job", "license"), name="uniq_ledger_package_item_license")]},
        ),
    ]
