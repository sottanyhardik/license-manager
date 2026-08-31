import uuid

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def populate_request_public_ids(apps, schema_editor):
    Request = apps.get_model("license", "LicenseLedgerPackageJob")
    for row in Request.objects.filter(public_id__isnull=True).only("pk").iterator():
        Request.objects.filter(pk=row.pk).update(public_id=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("license", "0053_licenseledgerrecoveryaudit")]

    operations = [
        # Adding a unique UUID with a default in a single PostgreSQL ALTER
        # evaluates the default once for all historical rows. Backfill each
        # row explicitly before enforcing the constraint.
        migrations.AddField(model_name="licenseledgerpackagejob", name="public_id", field=models.UUIDField(null=True, editable=False)),
        migrations.RunPython(populate_request_public_ids, migrations.RunPython.noop),
        migrations.AlterField(model_name="licenseledgerpackagejob", name="public_id", field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)),
        migrations.AddField(model_name="licenseledgerpackagejob", name="archive_filename", field=models.CharField(max_length=255, blank=True, default="")),
        migrations.AddField(model_name="licenseledgerpackagejob", name="archive_size", field=models.BigIntegerField(default=0)),
        migrations.AddField(model_name="licenseledgerpackagejob", name="archive_checksum", field=models.CharField(max_length=64, blank=True, default="")),
        migrations.AddField(model_name="licenseledgerpackagejob", name="root_task_id", field=models.CharField(max_length=255, blank=True, default="")),
        *[migrations.AddField(model_name="licenseledgerpackagejob", name=name, field=models.PositiveIntegerField(default=0)) for name in ("requested_count", "queued_count", "processing_count", "server_ready_count", "blocked_count", "failed_count")],
        *[migrations.AddField(model_name="licenseledgerpackageitem", name=name, field=field) for name, field in (
            ("request_order", models.PositiveIntegerField(default=0)), ("readiness_status", models.CharField(max_length=48, blank=True, default="queued")), ("processing_status", models.CharField(max_length=48, blank=True, default="queued")),
            ("purchase_expected_count", models.PositiveIntegerField(default=0)), ("purchase_included_count", models.PositiveIntegerField(default=0)), ("sales_expected_count", models.PositiveIntegerField(default=0)), ("sales_included_count", models.PositiveIntegerField(default=0)), ("interlinked_sales_excluded_count", models.PositiveIntegerField(default=0)), ("unknown_sales_count", models.PositiveIntegerField(default=0)), ("blocking_reason_codes", models.JSONField(default=list)),
        )],
        migrations.CreateModel(name="LicensePackageArtifact", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("kind", models.CharField(max_length=48)), ("document_ids", models.JSONField(default=list)), ("storage_key", models.CharField(max_length=512)), ("checksum", models.CharField(max_length=64)), ("size", models.BigIntegerField(default=0)), ("page_count", models.PositiveIntegerField(default=0)), ("page_range_start", models.PositiveIntegerField(null=True, blank=True)), ("page_range_end", models.PositiveIntegerField(null=True, blank=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="artifacts", to="license.licenseledgerpackageitem")), ("request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="artifacts", to="license.licenseledgerpackagejob")),
        ]),
        migrations.CreateModel(name="LicensePackageAuditEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("event", models.CharField(max_length=64)), ("detail", models.JSONField(default=dict)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)), ("item", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.CASCADE, related_name="audit_events", to="license.licenseledgerpackageitem")), ("request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_events", to="license.licenseledgerpackagejob")),
        ]),
    ]
