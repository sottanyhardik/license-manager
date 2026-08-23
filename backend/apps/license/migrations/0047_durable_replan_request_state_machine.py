from django.db import migrations, models
from django.db.models import Q


def normalize_replan_statuses(apps, schema_editor):
    Request = apps.get_model("license", "LicenseReplanRequest")
    Request.objects.filter(status="retry").update(status="retry_pending")


class Migration(migrations.Migration):
    dependencies = [("license", "0046_replan_request_revisions")]

    operations = [
        migrations.RemoveConstraint(
            model_name="licensereplanrequest",
            name="one_active_replan_request_per_license",
        ),
        migrations.AddField(model_name="licensereplanrequest", name="source_model", field=models.CharField(blank=True, default="", max_length=128)),
        migrations.AddField(model_name="licensereplanrequest", name="source_pk", field=models.CharField(blank=True, default="", max_length=128)),
        migrations.AddField(model_name="licensereplanrequest", name="queued_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="licensereplanrequest", name="trigger_count", field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name="licensereplanrequest", name="retry_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="licensereplanrequest", name="next_retry_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="licensereplanrequest", name="last_error_code", field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="licensereplanrequest", name="last_error_message", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="licensereplanrequest", name="celery_task_id", field=models.CharField(blank=True, default="", max_length=255)),
        migrations.RunPython(normalize_replan_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="licensereplanrequest", name="status",
            field=models.CharField(choices=[("pending", "Pending"), ("queued", "Queued"), ("running", "Running"), ("retry_pending", "Retry pending"), ("succeeded", "Succeeded"), ("failed", "Failed"), ("superseded", "Superseded")], db_index=True, default="pending", max_length=20),
        ),
        migrations.AddConstraint(
            model_name="licensereplanrequest",
            constraint=models.UniqueConstraint(
                condition=Q(status__in=["pending", "queued", "running", "retry_pending"]),
                fields=("license",), name="one_active_replan_request_per_license",
            ),
        ),
    ]
