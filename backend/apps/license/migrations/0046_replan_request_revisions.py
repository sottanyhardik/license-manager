from django.db import migrations, models
from django.db.models import Q


def pending_to_queued(apps, schema_editor):
    apps.get_model("license", "LicenseReplanRequest").objects.filter(status="pending").update(status="queued")


class Migration(migrations.Migration):
    dependencies = [("license", "0045_licensereplanrequest")]

    operations = [
        migrations.AddField(model_name="licensedetailsmodel", name="planning_source_revision", field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="licensedetailsmodel", name="planning_applied_revision", field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="licensereplanrequest", name="source_revision", field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="licensereplanrequest", name="planned_revision", field=models.PositiveBigIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="licensereplanrequest", name="started_source_revision", field=models.PositiveBigIntegerField(blank=True, null=True)),
        migrations.RunPython(pending_to_queued, migrations.RunPython.noop),
        migrations.AlterField(model_name="licensereplanrequest", name="status", field=models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("retry", "Retry"), ("succeeded", "Succeeded"), ("failed", "Failed"), ("superseded", "Superseded")], db_index=True, default="queued", max_length=16)),
        migrations.RemoveConstraint(model_name="licensereplanrequest", name="one_active_replan_request_per_license"),
        migrations.AddConstraint(model_name="licensereplanrequest", constraint=models.UniqueConstraint(condition=Q(("status__in", ["queued", "running", "retry"])), fields=("license",), name="one_active_replan_request_per_license")),
    ]
