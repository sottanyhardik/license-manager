from django.db import migrations


def forward(apps, schema_editor):
    Item = apps.get_model("core", "ItemNameModel")
    target = Item.objects.filter(name="RUTILE").order_by("pk").first()
    if target is None:
        raise RuntimeError("Required canonical ItemNameModel 'RUTILE' is missing.")
    for model, field in ((apps.get_model("bill_of_entry", "BillOfEntryModel"), "product_name"), (apps.get_model("allotment", "AllotmentModel"), "item_name")):
        model.objects.filter(planning_target_item_id__isnull=True, **{f"{field}__icontains": "RUTILE"}).update(
            planning_target_item_id=target.pk, planning_mapping_status="MAPPED_EXPLICIT", planning_mapping_source="APPROVED_ALIAS"
        )


class Migration(migrations.Migration):
    dependencies = [("license", "0041_map_parent_actuals_from_approved_aliases")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
