"""Data migration: split the E132 "Milk - E132" planning item into three whey
products — SWP ($1.5), DWP ($5), WPC ($22). Creates/activates the three masters,
links them to the E132 SION norm, aligns display_order with the new
PLANNING_ORDER (milk products at rank 5-7, later items shifted to 8-12), and
DEACTIVATES the now-internal "Milk - E132" master (it remains only as the
classification pool inside e132_plan, never an output item). Idempotent.

Names/order frozen here (migration best practice); the live source of truth is
apps.license.services.e132_plan, maintained by `seed_e132_plan_items`.
"""
from django.db import migrations

# Frozen at this migration; must match e132_plan.PLANNING_ORDER.
E132_PLANNING_ORDER = (
    "Yeast - E132",
    "CHEESE CREAM BUTTER AND FATS - E132",
    "PKO - E132",
    "RBD - E132",
    "SWP - E132",
    "DWP - E132",
    "WPC - E132",
    "NUT & NUTS - E132",
    "RAISIN - E132",
    "CEREALS FLAKES - E132",
    "CMC - E132",
    "Aluminium Foil - E132",
)
MILK_POOL = "Milk - E132"


def split(apps, schema_editor):
    ItemNameModel = apps.get_model("core", "ItemNameModel")
    SionNormClassModel = apps.get_model("core", "SionNormClassModel")
    norm = SionNormClassModel.objects.filter(norm_class="E132").first()

    for order, name in enumerate(E132_PLANNING_ORDER, start=1):
        obj, created = ItemNameModel.objects.get_or_create(
            name=name,
            defaults={"is_active": True, "sion_norm_class": norm, "display_order": order},
        )
        if not created:
            fields = []
            if not obj.is_active:
                obj.is_active = True
                fields.append("is_active")
            if norm is not None and obj.sion_norm_class_id != norm.id:
                obj.sion_norm_class = norm
                fields.append("sion_norm_class")
            if obj.display_order != order:
                obj.display_order = order
                fields.append("display_order")
            if fields:
                obj.save(update_fields=fields)

    # Milk is now an internal classification pool only — hide the master.
    milk = ItemNameModel.objects.filter(name=MILK_POOL).first()
    if milk is not None and milk.is_active:
        milk.is_active = False
        milk.save(update_fields=["is_active"])


def unsplit(apps, schema_editor):
    # No-op on reverse: master data is not restored on rollback.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_sync_e132_display_order"),
    ]

    operations = [
        migrations.RunPython(split, unsplit),
    ]
