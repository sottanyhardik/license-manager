"""
Module 04 — Master Synchronization fields migration.

Adds sync fields (master_uid, sync_version, is_tombstone, origin_server, synced_at)
to all 20 Master models, and creates the sync infrastructure tables
(SyncConflictLog, SyncPeer, SyncCursor, MediaSyncTask).
"""
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


# All Master models that receive sync fields
SYNC_MODELS = [
    "companymodel",
    "portmodel",
    "itemheadmodel",
    "itemgroupmodel",
    "itemnamemodel",
    "hscodemodel",
    "headsionnormsmodel",
    "sionnormclassmodel",
    "sionexportmodel",
    "sionimportmodel",
    "sionnormnote",
    "sionnormcondition",
    "productdescriptionmodel",
    "transferlettermodel",
    "unitpricemodel",
    "invoiceentity",
    "schemecode",
    "notificationnumber",
    "purchasestatus",
    "exchangeratemodel",
]


def _add_sync_fields(model_name):
    """Return migration operations to add sync fields to a model."""
    return [
        migrations.AddField(
            model_name=model_name,
            name="master_uid",
            field=models.UUIDField(
                blank=True, db_index=True, editable=False,
                help_text="Deterministic UUID derived from natural key — convergence anchor.",
                null=True, unique=True,
            ),
        ),
        migrations.AddField(
            model_name=model_name,
            name="sync_version",
            field=models.PositiveBigIntegerField(
                default=1,
                help_text="Monotonically increasing version; bumped on every write.",
            ),
        ),
        migrations.AddField(
            model_name=model_name,
            name="is_tombstone",
            field=models.BooleanField(
                db_index=True, default=False,
                help_text="True → record is soft-deleted (tombstone).",
            ),
        ),
        migrations.AddField(
            model_name=model_name,
            name="origin_server",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=100,
                help_text="Server ID that last wrote this record.",
            ),
        ),
        migrations.AddField(
            model_name=model_name,
            name="synced_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp of last successful sync receipt.",
                null=True,
            ),
        ),
    ]


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_split_milk_into_swp_dwp_wpc"),
    ]

    operations = []

    # Add sync fields to all Master models
    for _model in SYNC_MODELS:
        operations.extend(_add_sync_fields(_model))

    # Create sync infrastructure tables
    operations.extend([
        migrations.CreateModel(
            name="SyncConflictLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("model_label", models.CharField(db_index=True, max_length=100)),
                ("natural_key", models.CharField(max_length=255)),
                ("op", models.CharField(max_length=10)),
                ("source_server", models.CharField(max_length=100)),
                ("source_version", models.PositiveBigIntegerField(default=0)),
                ("local_version", models.PositiveBigIntegerField(default=0)),
                ("detail", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SyncPeer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("server_id", models.CharField(max_length=100, unique=True)),
                ("base_url", models.URLField(help_text="Base URL of the peer's sync API")),
                ("auth_token", models.CharField(blank=True, default="", help_text="Bearer token for authenticating with this peer", max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("last_seen", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name="SyncCursor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_synced_at", models.DateTimeField(blank=True, help_text="Timestamp of the last change successfully received from this peer", null=True)),
                ("last_pull_at", models.DateTimeField(blank=True, help_text="When we last pulled from this peer", null=True)),
                ("peer", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="cursor", to="core.syncpeer")),
            ],
        ),
        migrations.CreateModel(
            name="MediaSyncTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("model_label", models.CharField(max_length=100)),
                ("natural_key", models.CharField(max_length=255)),
                ("field_name", models.CharField(max_length=100)),
                ("source_server", models.CharField(max_length=100)),
                ("source_path", models.CharField(max_length=500)),
                ("expected_sha256", models.CharField(blank=True, default="", max_length=64)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("in_progress", "In Progress"), ("complete", "Complete"), ("failed", "Failed")], db_index=True, default="pending", max_length=20)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
    ])
