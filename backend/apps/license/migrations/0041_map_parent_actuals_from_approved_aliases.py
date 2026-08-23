"""Map parent BOE/allotment actuals using the explicitly approved aliases."""
import re
from django.db import migrations


def forward(apps, schema_editor):
    Item = apps.get_model("core", "ItemNameModel")
    BOE = apps.get_model("bill_of_entry", "BillOfEntryModel")
    Allotment = apps.get_model("allotment", "AllotmentModel")
    aliases = (
        ("CARDAMOM", r"CARDAMOM"), ("NUT & NUTS", r"PECAN NUT|MANDARIN|HAZELNUT|BRAZIL NUT"),
        ("CHEESE", r"CHEESE|CREAM|BUTTER"), ("OLIVE OIL", r"OLIVE OIL|EDIBLE VEGETABLE OIL"),
        ("PALM KERNEL OIL", r"\bPKO\b|PALM KERNEL OIL"), ("FRUIT JUICE", r"JUICE|CONC"),
        ("RUTILE", r"RUTILE"),
        ("WHEAT GLUTEN", r"WHEAT GLUTEN|WHEAT FLOUR"), ("SWP", r"\bSWP\b|SWEET WHEY POWDER|WHEY POWDER"),
        ("ESSENTIAL OIL", r"ESSENTIAL OIL|LEMON OIL|LIME OIL|ORANGE OIL"), ("CEREALS FLAKES", r"\bOAT\b"),
        ("RBD PALMOLEIN OIL", r"\bRBD\b|RBD PALMOLEIN OIL"), ("FRUIT/COCOA", r"COCOA"),
    )
    targets = [(Item.objects.filter(name=name).order_by("pk").first(), re.compile(pattern)) for name, pattern in aliases]
    for model, field in ((BOE, "product_name"), (Allotment, "item_name")):
        for obj in model.objects.filter(planning_target_item_id__isnull=True).iterator():
            text = " ".join((getattr(obj, field) or "").upper().split())
            matched = [target for target, pattern in targets if target and pattern.search(text)]
            if len(matched) == 1:
                obj.planning_target_item_id = matched[0].pk
                obj.planning_mapping_status = "MAPPED_EXPLICIT"
                obj.planning_mapping_source = "APPROVED_ALIAS"
                obj.save(update_fields=["planning_target_item", "planning_mapping_status", "planning_mapping_source"])


class Migration(migrations.Migration):
    dependencies = [("license", "0040_merge_explicit_planning_item_aliases_v2"), ("bill_of_entry", "0009_billofentry_parent_planning_target"), ("allotment", "0009_allotment_parent_planning_target")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
