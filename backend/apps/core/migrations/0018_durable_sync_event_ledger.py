import uuid

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("core", "0017_hash_sync_peer_credentials")]

    operations = [
        migrations.AddField(
            model_name="synccursor",
            name="remote_event_cursor",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="SyncEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("source_server", models.CharField(db_index=True, max_length=100)),
                ("model_label", models.CharField(db_index=True, max_length=100)),
                ("natural_key", models.CharField(db_index=True, max_length=255)),
                ("op", models.CharField(max_length=10)),
                ("source_version", models.PositiveBigIntegerField(default=1)),
                ("payload", models.JSONField(default=dict)),
                ("occurred_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AddIndex(
            model_name="syncevent",
            index=models.Index(fields=["source_server", "event_id"], name="core_syncev_source__3b168d_idx"),
        ),
        migrations.CreateModel(
            name="SyncInboxEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_server", models.CharField(max_length=100)),
                ("event_id", models.UUIDField()),
                ("received_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("result", models.CharField(default="received", max_length=20)),
                ("error", models.TextField(blank=True, default="")),
            ],
        ),
        migrations.AddConstraint(
            model_name="syncinboxevent",
            constraint=models.UniqueConstraint(fields=("source_server", "event_id"), name="core_sync_inbox_source_event_unique"),
        ),
        migrations.CreateModel(
            name="SyncPeerDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(db_index=True, default="pending", max_length=20)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True, default="")),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="core.syncevent")),
                ("peer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="core.syncpeer")),
            ],
        ),
        migrations.AddConstraint(
            model_name="syncpeerdelivery",
            constraint=models.UniqueConstraint(fields=("peer", "event"), name="core_sync_peer_event_unique"),
        ),
    ]
