"""Data migration: align the E132 planning-item masters' display_order with the
E132 planning priority (e132_plan.PLANNING_ORDER), so reports that sort by
display_order (Item Pivot, MasterList) show items in the planning order —
Aluminium Foil last. Idempotent.

The pre-existing masters kept stale/duplicate display_order values (several at 1)
because earlier get_or_create seeds only set display_order on CREATE. This fixes
the data. Order is frozen here (migration best practice); the live source of truth
is PLANNING_ORDER, maintained by the `seed_e132_plan_items` command.
"""
from django.db import migrations

# Frozen at this migration; must match e132_plan.PLANNING_ORDER (Aluminium last).
E132_PLANNING_ORDER = (
    "Yeast - E132",
    "CHEESE CREAM BUTTER AND FATS - E132",
    "PKO - E132",
    "RBD - E132",
    "Milk - E132",
    "NUT & NUTS - E132",
    "RAISIN - E132",
    "CEREALS FLAKES - E132",
    "CMC - E132",
    "Aluminium Foil - E132",
)


def sync(apps, schema_editor):
    ItemNameModel = apps.get_model("core", "ItemNameModel")
    for order, name in enumerate(E132_PLANNING_ORDER, start=1):
        obj = ItemNameModel.objects.filter(name=name).first()
        if obj is not None and obj.display_order != order:
            obj.display_order = order
            obj.save(update_fields=["display_order"])


def unsync(apps, schema_editor):
    # No-op on reverse: display_order is not restored on rollback.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_seed_e132_cmc_plan_item"),
    ]

    operations = [
        migrations.RunPython(sync, unsync),
    ]
