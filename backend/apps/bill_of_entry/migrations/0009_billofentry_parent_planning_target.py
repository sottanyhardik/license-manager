from django.db import migrations, models
import django.db.models.deletion


def promote_detail_targets(apps, schema_editor):
    BillOfEntry = apps.get_model("bill_of_entry", "BillOfEntryModel")
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'bill_of_entry_rowdetails' AND column_name = 'planning_target_item_id'")
        has_legacy_target = cursor.fetchone() is not None
    for boe in BillOfEntry.objects.all().iterator():
        # The legacy field existed in a draft migration and may not be in the
        # historical Django state after that migration was corrected.
        if has_legacy_target:
            with schema_editor.connection.cursor() as cursor:
                cursor.execute("SELECT DISTINCT planning_target_item_id FROM bill_of_entry_rowdetails WHERE bill_of_entry_id = %s AND planning_target_item_id IS NOT NULL", [boe.pk])
                targets = {value[0] for value in cursor.fetchall()}
        else:
            targets = set()
        if len(targets) == 1:
            boe.planning_target_item_id = targets.pop()
            boe.planning_mapping_status = "MAPPED_EXPLICIT"
            boe.planning_mapping_source = "MIGRATED_DETAIL_MAPPING"
        elif len(targets) > 1:
            boe.planning_mapping_status = "UNMAPPED_AMBIGUOUS"
            boe.planning_mapping_source = ""
        boe.save(update_fields=["planning_target_item", "planning_mapping_status", "planning_mapping_source"])


class Migration(migrations.Migration):
    dependencies = [("bill_of_entry", "0008_planning_mapping_statuses"), ("core", "0016_merge_numbered_norm_suffixed_item_names")]
    operations = [migrations.SeparateDatabaseAndState(
        database_operations=[migrations.RunPython(promote_detail_targets, migrations.RunPython.noop)],
        state_operations=[
            migrations.AddField(model_name="billofentrymodel", name="planning_target_item", field=models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="boe_planning_targets", to="core.itemnamemodel")),
            migrations.AddField(model_name="billofentrymodel", name="planning_mapping_status", field=models.CharField(db_index=True, default="UNMAPPED_AMBIGUOUS", max_length=32)),
            migrations.AddField(model_name="billofentrymodel", name="planning_mapping_source", field=models.CharField(blank=True, default="", max_length=32)),
        ],
    )]
