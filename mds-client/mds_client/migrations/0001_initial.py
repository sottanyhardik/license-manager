from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MDSSyncState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("model_label", models.CharField(max_length=100, unique=True)),
                ("cursor", models.CharField(blank=True, max_length=64, null=True)),
                ("etag", models.CharField(blank=True, max_length=128, null=True)),
                ("changes_cursor", models.CharField(blank=True, max_length=64, null=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "MDS sync state",
                "verbose_name_plural": "MDS sync state",
                "ordering": ["model_label"],
            },
        ),
    ]
