"""Persist only deterministic BOE/unlinked-allotment planning targets.

This is deliberately configuration-driven.  It preserves explicit mappings,
does not use item/product-name heuristics, and leaves ambiguous history null.
"""
from django.db import migrations


def forward(apps, schema_editor):
    from apps.license.services.sion_rule_engine import evaluate_expression

    BOE = apps.get_model("bill_of_entry", "BillOfEntryModel")
    Allotment = apps.get_model("allotment", "AllotmentModel")
    RowDetails = apps.get_model("bill_of_entry", "RowDetails")
    AllotmentItem = apps.get_model("allotment", "AllotmentItems")
    ExportItem = apps.get_model("license", "LicenseExportItemModel")
    Rule = apps.get_model("license", "SionPlanningRule")

    def targets_for(source):
        sion_ids = list(ExportItem.objects.filter(license_id=source.license_id).exclude(norm_class_id__isnull=True).values_list("norm_class_id", flat=True).distinct())
        if len(sion_ids) != 1:
            return set()
        record = {
            "hs_code": source.hs_code.hs_code if source.hs_code_id else "",
            "description": source.description or "",
            "item_key": ", ".join(sorted(item.name for item in source.items.all())),
            "total_qty": source.quantity,
            "available_qty": source.available_quantity,
            "unit": source.unit or "",
            "serial_number": source.serial_number,
        }
        target_ids = set()
        for rule in Rule.objects.filter(sion_id=sion_ids[0], is_active=True).prefetch_related("percentage_rows__import_item", "unit_value_rows__import_item").select_related("import_item"):
            if not evaluate_expression(rule.expression or {}, record):
                continue
            def valid(item):
                return item and (item.norms.filter(pk=rule.sion_id).exists() or item.sion_norm_class_id == rule.sion_id)
            if (rule.strategy or "STANDARD") == "SPLIT_BY_PERCENT":
                target_ids.update(row.import_item_id for row in rule.percentage_rows.all() if valid(row.import_item))
            elif (rule.strategy or "STANDARD") == "SPLIT_BY_UNIT_VALUE":
                target_ids.update(row.import_item_id for row in rule.unit_value_rows.all() if valid(row.import_item))
            elif rule.import_item_id and valid(rule.import_item):
                target_ids.add(rule.import_item_id)
        return target_ids

    cache = {}
    parent_sources = []
    for usage in BOE.objects.all():
        parent_sources.append((usage, list(RowDetails.objects.filter(bill_of_entry_id=usage.pk, transaction_type="D").select_related("sr_number"))))
    for usage in Allotment.objects.filter(bill_of_entry__isnull=True, is_boe=False):
        parent_sources.append((usage, list(AllotmentItem.objects.filter(allotment_id=usage.pk, is_boe=False).select_related("item"))))
    for usage, detail_rows in parent_sources:
        source_items = [getattr(row, "sr_number", None) or getattr(row, "item", None) for row in detail_rows]
        source_items = [source for source in source_items if source is not None]
        if not source_items:
            usage.planning_mapping_status = "UNMAPPED_NO_TARGET"
            usage.planning_mapping_source = ""
        else:
            resolved = []
            for source in source_items:
                if source.pk not in cache:
                    cache[source.pk] = targets_for(source)
                resolved.append(cache[source.pk])
            target_ids = set.intersection(*resolved) if resolved else set()
            if usage.planning_target_item_id:
                if usage.planning_target_item_id in target_ids:
                    usage.planning_mapping_status = "MAPPED_EXPLICIT"
                    usage.planning_mapping_source = "USER_SELECTED"
                else:
                    usage.planning_mapping_status = "INVALID_PERSISTED_TARGET"
                    usage.planning_mapping_source = ""
            elif len(target_ids) == 1:
                usage.planning_target_item_id = next(iter(target_ids))
                usage.planning_mapping_status = "MAPPED_DETERMINISTIC"
                usage.planning_mapping_source = "UNIQUE_TARGET"
            elif target_ids:
                usage.planning_mapping_status = "UNMAPPED_AMBIGUOUS"
                usage.planning_mapping_source = ""
            else:
                usage.planning_mapping_status = "UNMAPPED_NO_TARGET"
                usage.planning_mapping_source = ""
        usage.save(update_fields=("planning_target_item", "planning_mapping_status", "planning_mapping_source"))


class Migration(migrations.Migration):
    dependencies = [
        ("license", "0037_backfill_actual_usage_planning_targets"),
        ("core", "0016_merge_numbered_norm_suffixed_item_names"),
        ("bill_of_entry", "0009_billofentry_parent_planning_target"),
        ("allotment", "0009_allotment_parent_planning_target"),
    ]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
