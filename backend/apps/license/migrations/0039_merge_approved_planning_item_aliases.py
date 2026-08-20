"""Apply the explicitly approved planning-item business aliases.

These are named business decisions, not fuzzy matching rules.  Every moved
reference is repointed before a duplicate ItemNameModel is removed.
"""
from django.db import migrations


def forward(apps, schema_editor):
    ItemName = apps.get_model("core", "ItemNameModel")
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
    # This migration intentionally sits before the BOE/allotment target-FK
    # migrations in some historical dependency paths.  Only touch references
    # which exist in the migration's historical app state.
    references = tuple(
        (model, field) for model, field in references
        if any(candidate.attname == field for candidate in model._meta.fields)
    )
    targets = {
        "CHEESE": ("CHEESE", lambda name: any(term in name for term in ("CHEESE", "CREAM", "BUTTER"))),
        "OLIVE OIL": ("OLIVE OIL", lambda name: "OLIVE OIL" in name or "EDIBLE VEGETABLE OIL" in name),
        "PALM KERNEL OIL": ("PALM KERNEL OIL", lambda name: "PKO" in name or "PALM KERNEL OIL" in name),
        "FRUIT JUICE": ("FRUIT JUICE", lambda name: "JUICE" in name),
        "Fruit Cocktail": ("Fruit Cocktail", lambda name: "FRUIT COCKTAIL" in name),
        "NUT & NUTS": ("NUT & NUTS", lambda name: "HAZELNUT" in name or "BRAZIL NUT" in name or name == "NUT & NUTS"),
    }
    through = ImportItem.items.through

    def move(duplicate, survivor):
        survivor.norms.add(*list(duplicate.norms.values_list("pk", flat=True)))
        for source_id in through.objects.filter(itemnamemodel_id=duplicate.pk).values_list("licenseimportitemsmodel_id", flat=True):
            through.objects.get_or_create(licenseimportitemsmodel_id=source_id, itemnamemodel_id=survivor.pk)
        through.objects.filter(itemnamemodel_id=duplicate.pk).delete()
        for model, field in references:
            model.objects.filter(**{field: duplicate.pk}).update(**{field: survivor.pk})
        if sum(model.objects.filter(**{field: duplicate.pk}).count() for model, field in references) or through.objects.filter(itemnamemodel_id=duplicate.pk).exists():
            raise RuntimeError(f"ItemNameModel {duplicate.pk} retained a reference; migration rolled back.")
        duplicate.delete()

    for _, (target_name, matches) in targets.items():
        survivor = ItemName.objects.filter(name=target_name).order_by("pk").first()
        if survivor is None:
            # A migration must be runnable against a clean database as well
            # as against the production master-data snapshot it was authored
            # from.  Creating the approved canonical identity is safe and
            # makes the operation deterministic; failing here made every
            # fresh test database depend on unrelated seed data.
            survivor = ItemName.objects.create(
                name=target_name,
                normalized_name=" ".join(target_name.upper().split()),
                is_active=True,
            )
        for item in list(ItemName.objects.order_by("pk")):
            name = " ".join((item.name or "").upper().split())
            if item.pk != survivor.pk and matches(name):
                move(item, survivor)


class Migration(migrations.Migration):
    dependencies = [
        ("license", "0038_backfill_deterministic_actual_target_mapping"),
        ("core", "0016_merge_numbered_norm_suffixed_item_names"),
        ("bill_of_entry", "0008_planning_mapping_statuses"),
        ("allotment", "0008_planning_mapping_statuses"),
    ]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
