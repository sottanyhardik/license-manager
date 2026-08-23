"""Apply the second approved set of planning-item aliases (no fuzzy matching)."""
import re

from django.db import migrations


def forward(apps, schema_editor):
    Item = apps.get_model("core", "ItemNameModel")
    Import = apps.get_model("license", "LicenseImportItemsModel")
    refs = (
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
    # BOE/allotment target columns may not exist yet in this historical
    # migration state.  Filtering by the historical model state keeps this
    # data migration valid on both the old and merged migration graphs.
    refs = tuple(
        (model, field) for model, field in refs
        if any(candidate.attname == field for candidate in model._meta.fields)
    )
    whole_oat = re.compile(r"\bOAT\b")
    whole_paper = re.compile(r"^PAPER$")
    aliases = (
        ("CARDAMOM", lambda n: "CARDAMOM" in n),
        ("NUT & NUTS", lambda n: "PECAN NUT" in n or n == "MANDARIN"),
        ("PAPER BOARD", lambda n: "PAPER BOARD" in n),
        ("PAPER", lambda n: bool(whole_paper.match(n))),
        ("RAISIN", lambda n: "RAISIN" in n),
        ("WHEAT GLUTEN", lambda n: "WHEAT GLUTEN" in n or "WHEAT FLOUR" in n),
        ("RUTILE", lambda n: "RUTILE" in n),
        ("WPC", lambda n: "WPC" in n),
        ("Yeast", lambda n: n == "YEAST" or "YEAST EXTRACT" in n),
        ("SODA ASH", lambda n: "SODA ASH" in n),
        ("SWP", lambda n: n == "SWP" or "SWEET WHEY POWDER" in n or n == "WHEY POWDER"),
        ("FRUIT/COCOA", lambda n: "COCOA" in n),
        ("OLIVE OIL", lambda n: "OLIVE OIL" in n),
        ("RBD PALMOLEIN OIL", lambda n: n == "RBD" or "RBD PALMOLEIN OIL" in n),
        ("TITANIUM DIOXIDE", lambda n: "TITANIUM DIOXIDE" in n),
        ("CITRIC ACID / TARTARIC ACID", lambda n: "CITRIC ACID" in n or "TARTARIC" in n),
        ("DWP", lambda n: "DWP" in n),
        ("FOOD FLAVOUR", lambda n: "FOOD FLAVOUR" in n),
        ("DIETARY FIBRE", lambda n: "DIETARY FIBRE" in n),
        ("ESSENTIAL OIL", lambda n: "ESSENTIAL OIL" in n or "LEMON OIL" in n or "LIME OIL" in n or "ORANGE OIL" in n),
        ("FRUIT JUICE", lambda n: "JUICE" in n or "CONC" in n),
        ("CEREALS FLAKES", lambda n: bool(whole_oat.search(n))),
        ("CMC", lambda n: n == "CMC"),
        ("STARCH", lambda n: "STARCH" in n),
        ("OTHER CONFECTIONERY INGREDIENTS", lambda n: "OTHER CONFECTIONERY INGREDIENTS" in n),
        ("PALM KERNEL OIL", lambda n: "PALM KERNEL OIL" in n),
        ("ALUMINIUM FOIL", lambda n: "ALUMINIUM FOIL" in n),
        ("LDPE", lambda n: "LDPE" in n),
        ("SUGAR", lambda n: "SUGAR" in n),
    )
    through = Import.items.through

    def move(source, target):
        target.norms.add(*list(source.norms.values_list("pk", flat=True)))
        for import_id in through.objects.filter(itemnamemodel_id=source.pk).values_list("licenseimportitemsmodel_id", flat=True):
            through.objects.get_or_create(licenseimportitemsmodel_id=import_id, itemnamemodel_id=target.pk)
        through.objects.filter(itemnamemodel_id=source.pk).delete()
        for model, field in refs:
            model.objects.filter(**{field: source.pk}).update(**{field: target.pk})
        if sum(model.objects.filter(**{field: source.pk}).count() for model, field in refs) or through.objects.filter(itemnamemodel_id=source.pk).exists():
            raise RuntimeError(f"ItemNameModel {source.pk} retained a reference; migration rolled back.")
        source.delete()

    for target_name, matches in aliases:
        target = Item.objects.filter(name=target_name).order_by("pk").first()
        if target is None:
            # Canonical planning identities are valid master rows even in a
            # newly-created database.  Do not make migrations contingent on
            # an external production seed.
            target = Item.objects.create(
                name=target_name,
                normalized_name=" ".join(target_name.upper().split()),
                is_active=True,
            )
        for source in list(Item.objects.order_by("pk")):
            normalized = " ".join((source.name or "").upper().split())
            if source.pk != target.pk and matches(normalized):
                move(source, target)


class Migration(migrations.Migration):
    dependencies = [
        ("license", "0039_merge_approved_planning_item_aliases"),
        ("core", "0016_merge_numbered_norm_suffixed_item_names"),
        ("bill_of_entry", "0008_planning_mapping_statuses"),
        ("allotment", "0008_planning_mapping_statuses"),
    ]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
