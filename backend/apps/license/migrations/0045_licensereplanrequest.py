from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("license", "0044_licenseitemplan_lifecycle_constraint")]

    operations = [
        migrations.CreateModel(
            name="LicenseReplanRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(max_length=100)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("succeeded", "Succeeded"), ("failed", "Failed")], db_index=True, default="pending", max_length=16)),
                ("requested_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("task_id", models.CharField(blank=True, default="", max_length=255)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("last_error", models.TextField(blank=True, default="")),
                ("license", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="replan_requests", to="license.licensedetailsmodel")),
            ],
            options={"ordering": ("-requested_at", "-pk")},
        ),
        migrations.AddConstraint(
            model_name="licensereplanrequest",
            constraint=models.UniqueConstraint(condition=Q(("status__in", ["pending", "running"])), fields=("license",), name="one_active_replan_request_per_license"),
        ),
    ]
