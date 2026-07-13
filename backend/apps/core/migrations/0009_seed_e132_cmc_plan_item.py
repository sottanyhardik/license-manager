"""Data migration: create/activate the CMC E132 planning-item master and link it
to the E132 SION norm class. Idempotent; runs automatically on deploy.

Names are frozen here (migration best practice); the live source of truth is
apps.license.services.e132_plan.PLANNING_ORDER, kept in sync via the
`seed_e132_plan_items` management command.
"""
from django.db import migrations

# Frozen at this migration; must match the addition in e132_plan.PLANNING_ORDER.
E132_CMC_ITEM = "CMC - E132"


def seed(apps, schema_editor):
    ItemNameModel = apps.get_model("core", "ItemNameModel")
    SionNormClassModel = apps.get_model("core", "SionNormClassModel")
    norm = SionNormClassModel.objects.filter(norm_class="E132").first()
    obj, created = ItemNameModel.objects.get_or_create(
        name=E132_CMC_ITEM,
        defaults={"is_active": True, "sion_norm_class": norm, "display_order": 10},
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
        ("core", "0008_seed_e132_extra_plan_items"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
