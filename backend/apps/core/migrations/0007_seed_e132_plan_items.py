"""Data migration: create/activate the six E132 planning-item masters and link
them to the E132 SION norm class. Idempotent; runs automatically on deploy so the
masters the E132 planning classifier expects always exist.

Names are frozen here (migration best practice); the live source of truth is
apps.license.services.e132_plan.PLANNING_ORDER, kept in sync via the
`seed_e132_plan_items` management command.
"""
from django.db import migrations

# Frozen at this migration; must match e132_plan.PLANNING_ORDER.
E132_PLANNING_ITEMS = (
    "Yeast - E132",
    "CHEESE CREAM BUTTER AND FATS - E132",
    "PKO - E132",
    "RBD - E132",
    "Aluminium Foil - E132",
    "Milk - E132",
)


def seed(apps, schema_editor):
    ItemNameModel = apps.get_model("core", "ItemNameModel")
    SionNormClassModel = apps.get_model("core", "SionNormClassModel")
    norm = SionNormClassModel.objects.filter(norm_class="E132").first()
    for order, name in enumerate(E132_PLANNING_ITEMS, start=1):
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
            if fields:
                obj.save(update_fields=fields)


def unseed(apps, schema_editor):
    # No-op on reverse: master data is not deleted on rollback.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_backfill_master_uids"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
