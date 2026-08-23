from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import migrations, models


def hash_existing_peer_credentials(apps, schema_editor):
    """One-way upgrade of legacy plaintext peer credentials."""
    SyncPeer = apps.get_model("core", "SyncPeer")
    for peer in SyncPeer.objects.exclude(auth_token="").iterator():
        try:
            identify_hasher(peer.auth_token)
        except ValueError:
            peer.auth_token = make_password(peer.auth_token)
            peer.save(update_fields=["auth_token"])


class Migration(migrations.Migration):
    dependencies = [("core", "0016_merge_numbered_norm_suffixed_item_names")]

    operations = [
        migrations.RunPython(hash_existing_peer_credentials, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="syncpeer",
            name="auth_token",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Password hash of the peer's server-to-server sync credential",
                max_length=255,
            ),
        ),
    ]
