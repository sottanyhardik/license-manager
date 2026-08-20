"""Merge ``ITEM - <SION norm> - <numeric duplicate marker>`` masters."""
import re

from django.db import migrations


def key(value):
    return " ".join(str(value or "").strip().split()).upper()


def forward(apps, schema_editor):
    ItemName = apps.get_model("core", "ItemNameModel")
    Norm = apps.get_model("core", "SionNormClassModel")
    ImportItem = apps.get_model("license", "LicenseImportItemsModel")
    references = (
        (apps.get_model("license", "SionPlanningRule"), "import_item_id"),
        (apps.get_model("license", "SionPlanningPercentageRow"), "import_item_id"),
        (apps.get_model("license", "SionPlanningUnitValueRow"), "import_item_id"),
        (apps.get_model("bill_of_entry", "RowDetails"), "planning_target_item_id"),
        (apps.get_model("allotment", "AllotmentItems"), "planning_target_item_id"),
        (apps.get_model("license", "LicenseItemPlan"), "item_name_id"),
        (apps.get_model("license", "LicenseExportItemModel"), "item_id"),
        (apps.get_model("license", "SionInputAliasConfig"), "output_item_id"),
        (apps.get_model("license", "SionPlanningOutputMapping"), "output_item_id"),
    )
    norm_ids = {norm.norm_class.upper(): norm.pk for norm in Norm.objects.all()}
    matcher = re.compile(r"^(?P<base>.+?)\s*-\s*(?P<norm>[A-Za-z0-9]+)\s*-\s*(?P<marker>[0-9]+)\s*$")
    through = ImportItem.items.through

    for duplicate in ItemName.objects.order_by("pk"):
        match = matcher.match(duplicate.name or "")
        if not match or match.group("norm").upper() not in norm_ids:
            continue
        base = " ".join(match.group("base").split()).strip()
        if not base:
            continue
        survivor = ItemName.objects.filter(normalized_name=key(base)).exclude(pk=duplicate.pk).order_by("pk").first()
        if survivor is None:
            # A numeric duplicate marker is not a standalone product identity.
            # Renaming is safe when there is no existing base row.
            duplicate.name = base
            duplicate.normalized_name = key(base)
            duplicate.save(update_fields=("name", "normalized_name"))
            duplicate.norms.add(norm_ids[match.group("norm").upper()])
            continue
        survivor.norms.add(norm_ids[match.group("norm").upper()])
        for source_id in through.objects.filter(itemnamemodel_id=duplicate.pk).values_list("licenseimportitemsmodel_id", flat=True):
            through.objects.get_or_create(licenseimportitemsmodel_id=source_id, itemnamemodel_id=survivor.pk)
        through.objects.filter(itemnamemodel_id=duplicate.pk).delete()
        for model, field in references:
            model.objects.filter(**{field: duplicate.pk}).update(**{field: survivor.pk})
        if sum(model.objects.filter(**{field: duplicate.pk}).count() for model, field in references) or through.objects.filter(itemnamemodel_id=duplicate.pk).exists():
            raise RuntimeError(f"ItemNameModel {duplicate.pk} retained a reference; migration rolled back.")
        duplicate.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0015_normalize_single_norm_and_common_item_names"),
        ("license", "0037_backfill_actual_usage_planning_targets"),
        ("bill_of_entry", "0008_planning_mapping_statuses"),
        ("allotment", "0008_planning_mapping_statuses"),
    ]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
