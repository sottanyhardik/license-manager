"""Normalize remaining single norm-suffixed and ``- COMMON`` item names."""
import re
from collections import defaultdict

from django.db import migrations


def _key(value):
    return " ".join(str(value or "").strip().split()).upper()


def forward(apps, schema_editor):
    ItemName = apps.get_model("core", "ItemNameModel")
    Norm = apps.get_model("core", "SionNormClassModel")
    ImportItem = apps.get_model("license", "LicenseImportItemsModel")
    models_and_fields = (
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
    norms = {norm.norm_class.upper(): norm.pk for norm in Norm.objects.all()}
    active_norm_ids = list(Norm.objects.filter(is_active=True).values_list("pk", flat=True))
    matcher = re.compile(r"^(?P<base>.+?)\s*-\s*(?P<suffix>[A-Za-z0-9]+)\s*$")
    groups = defaultdict(list)
    for item in ItemName.objects.order_by("pk"):
        match = matcher.match(item.name or "")
        if not match:
            continue
        base = " ".join(match.group("base").split()).strip()
        suffix = match.group("suffix").upper()
        norm_ids = active_norm_ids if suffix == "COMMON" else ([norms[suffix]] if suffix in norms else [])
        if base and norm_ids:
            groups[_key(base)].append((item.pk, base, norm_ids))

    through = ImportItem.items.through
    for normalized, members in groups.items():
        member_ids = [item_id for item_id, _, _ in members]
        base = members[0][1]
        existing = ItemName.objects.filter(normalized_name=normalized).exclude(pk__in=member_ids).order_by("pk").first()
        rows = list(ItemName.objects.filter(pk__in=(([existing.pk] if existing else []) + member_ids)).order_by("pk"))
        survivor = existing or rows[0]
        survivor.name = base
        survivor.normalized_name = normalized
        survivor.save(update_fields=("name", "normalized_name"))
        survivor.norms.add(*[norm_id for _, _, ids in members for norm_id in ids])
        for row in rows:
            survivor.norms.add(*list(row.norms.values_list("pk", flat=True)))
        for duplicate in [row for row in rows if row.pk != survivor.pk]:
            for source_id in through.objects.filter(itemnamemodel_id=duplicate.pk).values_list("licenseimportitemsmodel_id", flat=True):
                through.objects.get_or_create(licenseimportitemsmodel_id=source_id, itemnamemodel_id=survivor.pk)
            through.objects.filter(itemnamemodel_id=duplicate.pk).delete()
            for model, field in models_and_fields:
                model.objects.filter(**{field: duplicate.pk}).update(**{field: survivor.pk})
            if sum(model.objects.filter(**{field: duplicate.pk}).count() for model, field in models_and_fields) or through.objects.filter(itemnamemodel_id=duplicate.pk).exists():
                raise RuntimeError(f"ItemNameModel {duplicate.pk} retained a reference; migration rolled back.")
            duplicate.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_merge_norm_suffixed_item_names"),
        ("license", "0037_backfill_actual_usage_planning_targets"),
        ("bill_of_entry", "0008_planning_mapping_statuses"),
        ("allotment", "0008_planning_mapping_statuses"),
    ]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
