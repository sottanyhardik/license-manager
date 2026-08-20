from django.db import migrations, models


def populate_norms_and_keys(apps, schema_editor):
    ItemName = apps.get_model("core", "ItemNameModel")
    for item in ItemName.objects.all().iterator(chunk_size=500):
        normalized = " ".join((item.name or "").strip().split()).upper()
        ItemName.objects.filter(pk=item.pk).update(normalized_name=normalized)
        if item.sion_norm_class_id:
            item.norms.add(item.sion_norm_class_id)


def reverse_populate(apps, schema_editor):
    # The legacy FK remains authoritative during this additive transition.
    return


class Migration(migrations.Migration):
    dependencies = [("core", "0012_master_sync_fields")]

    operations = [
        migrations.AddField(
            model_name="itemnamemodel",
            name="norms",
            field=models.ManyToManyField(blank=True, help_text="All SION norms for which this planning item is legitimate.", related_name="planning_items", to="core.sionnormclassmodel"),
        ),
        migrations.AddField(
            model_name="itemnamemodel",
            name="normalized_name",
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=255, null=True),
        ),
        migrations.RunPython(populate_norms_and_keys, reverse_populate),
    ]
