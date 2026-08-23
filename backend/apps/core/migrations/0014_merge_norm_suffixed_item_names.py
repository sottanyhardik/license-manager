"""Consolidate only ``ITEM - <existing SION norm code>`` item masters.

This is deliberately narrower than a fuzzy item-name merge: the suffix must
be an actual SION norm code, and all moves occur before a duplicate row is
deleted.  Any database uniqueness collision aborts the surrounding migration
transaction rather than discarding business records.
"""
import re
from collections import defaultdict

from django.db import migrations


def normalize(value):
    return " ".join(str(value or "").strip().split()).upper()


def forward(apps, schema_editor):
    ItemName = apps.get_model("core", "ItemNameModel")
    Norm = apps.get_model("core", "SionNormClassModel")
    ImportItem = apps.get_model("license", "LicenseImportItemsModel")
    Rule = apps.get_model("license", "SionPlanningRule")
    PercentRow = apps.get_model("license", "SionPlanningPercentageRow")
    UnitValueRow = apps.get_model("license", "SionPlanningUnitValueRow")
    Plan = apps.get_model("license", "LicenseItemPlan")
    ExportItem = apps.get_model("license", "LicenseExportItemModel")
    Alias = apps.get_model("license", "SionInputAliasConfig")
    OutputMapping = apps.get_model("license", "SionPlanningOutputMapping")
    BOE = apps.get_model("bill_of_entry", "RowDetails")
    AllotmentItem = apps.get_model("allotment", "AllotmentItems")

    norm_by_code = {norm.norm_class.upper(): norm for norm in Norm.objects.all()}
    suffix = re.compile(r"^(?P<base>.+?)\s*-\s*(?P<norm>[A-Za-z0-9]+)\s*$")
    groups = defaultdict(list)
    for item in ItemName.objects.order_by("pk"):
        matched = suffix.match(item.name or "")
        if not matched or matched.group("norm").upper() not in norm_by_code:
            continue
        base = " ".join(matched.group("base").split()).strip()
        if base:
            groups[normalize(base)].append((item.pk, base, norm_by_code[matched.group("norm").upper()].pk))

    references = (
        (Rule, "import_item_id"),
        (PercentRow, "import_item_id"),
        (UnitValueRow, "import_item_id"),
        (BOE, "planning_target_item_id"),
        (AllotmentItem, "planning_target_item_id"),
        (Plan, "item_name_id"),
        (ExportItem, "item_id"),
        (Alias, "output_item_id"),
        (OutputMapping, "output_item_id"),
    )
    through = ImportItem.items.through

    for key, suffixed in groups.items():
        suffix_ids = [item_id for item_id, _, _ in suffixed]
        base_name = suffixed[0][1]
        existing = ItemName.objects.filter(normalized_name=key).exclude(pk__in=suffix_ids).order_by("pk").first()
        if len(suffixed) < 2 and existing is None:
            continue
        ids = ([existing.pk] if existing else []) + suffix_ids
        rows = list(ItemName.objects.filter(pk__in=ids).order_by("pk"))
        # An existing unsuffixed master is the authoritative identity; this
        # also avoids a transient unique-name collision during the rename.
        survivor = existing or rows[0]
        survivor.name = base_name
        survivor.normalized_name = key
        survivor.save(update_fields=("name", "normalized_name"))
        survivor.norms.add(*[norm_id for _, _, norm_id in suffixed])
        for row in rows:
            survivor.norms.add(*list(row.norms.values_list("pk", flat=True)))
        for duplicate in [row for row in rows if row.pk != survivor.pk]:
            for source_id in through.objects.filter(itemnamemodel_id=duplicate.pk).values_list("licenseimportitemsmodel_id", flat=True):
                through.objects.get_or_create(
                    licenseimportitemsmodel_id=source_id,
                    itemnamemodel_id=survivor.pk,
                )
            through.objects.filter(itemnamemodel_id=duplicate.pk).delete()
            for model, field in references:
                model.objects.filter(**{field: duplicate.pk}).update(**{field: survivor.pk})
            remaining = sum(model.objects.filter(**{field: duplicate.pk}).count() for model, field in references)
            if remaining or through.objects.filter(itemnamemodel_id=duplicate.pk).exists():
                raise RuntimeError(f"ItemNameModel {duplicate.pk} still has references; merge rolled back.")
            duplicate.delete()


def reverse(apps, schema_editor):
    # Identity consolidation is intentionally irreversible: historical
    # references now point to the one canonical master identity.
    return


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_item_name_multi_norms"),
        ("license", "0037_backfill_actual_usage_planning_targets"),
        ("bill_of_entry", "0008_planning_mapping_statuses"),
        ("allotment", "0008_planning_mapping_statuses"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
