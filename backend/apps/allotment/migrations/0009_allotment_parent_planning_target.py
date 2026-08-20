from django.db import migrations, models
import django.db.models.deletion


def promote_detail_targets(apps, schema_editor):
    Allotment = apps.get_model("allotment", "AllotmentModel")
    Details = apps.get_model("allotment", "AllotmentItems")
    for allotment in Allotment.objects.all().iterator():
        targets = set(Details.objects.filter(allotment_id=allotment.pk).exclude(planning_target_item_id__isnull=True).values_list("planning_target_item_id", flat=True))
        if len(targets) == 1:
            allotment.planning_target_item_id = targets.pop()
            allotment.planning_mapping_status = "MAPPED_EXPLICIT"
            allotment.planning_mapping_source = "MIGRATED_DETAIL_MAPPING"
        elif len(targets) > 1:
            allotment.planning_mapping_status = "UNMAPPED_AMBIGUOUS"
            allotment.planning_mapping_source = ""
        allotment.save(update_fields=["planning_target_item", "planning_mapping_status", "planning_mapping_source"])


class Migration(migrations.Migration):
    dependencies = [("allotment", "0008_planning_mapping_statuses"), ("core", "0016_merge_numbered_norm_suffixed_item_names")]
    operations = [migrations.SeparateDatabaseAndState(
        database_operations=[migrations.RunPython(promote_detail_targets, migrations.RunPython.noop)],
        state_operations=[
            migrations.AddField(model_name="allotmentmodel", name="planning_target_item", field=models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="allotment_planning_targets", to="core.itemnamemodel")),
            migrations.AddField(model_name="allotmentmodel", name="planning_mapping_status", field=models.CharField(db_index=True, default="UNMAPPED_AMBIGUOUS", max_length=32)),
            migrations.AddField(model_name="allotmentmodel", name="planning_mapping_source", field=models.CharField(blank=True, default="", max_length=32)),
        ],
    )]
