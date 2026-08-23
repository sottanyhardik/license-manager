"""
Data migration — backfill remaining_quantity/remaining_cif_fc for
LicenseItemPlan rows that existed before those fields were introduced
(migration 0015).

Every pre-existing row starts with its remaining balance equal to its full
planned amount — i.e. as if it had just been created, with nothing allotted
against it yet via the new plan-line-aware `allocate_items` path. This is a
one-time approximation: it cannot know how much of a pre-existing plan line
was already, in effect, consumed before this feature existed (the whole
point of this feature is that such attribution was previously impossible to
track per plan line at all). New plans created after this migration always
get remaining_quantity/remaining_cif_fc stamped from planned_quantity/
planned_cif_fc at save time (see `plan_enforcement.save_plan_lines_for_license`).
"""
from django.db import migrations
from django.db.models import F


def backfill_remaining(apps, schema_editor):
    LicenseItemPlan = apps.get_model("license", "LicenseItemPlan")
    LicenseItemPlan.objects.filter(remaining_quantity__isnull=True).update(
        remaining_quantity=F("planned_quantity"),
    )
    LicenseItemPlan.objects.filter(remaining_cif_fc__isnull=True).update(
        remaining_cif_fc=F("planned_cif_fc"),
    )


def noop_reverse(apps, schema_editor):
    """Irreversible in any meaningful sense — leave remaining balances as they are."""


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0015_add_licenseitemplan_remaining_balance'),
    ]

    operations = [
        migrations.RunPython(backfill_remaining, noop_reverse),
    ]
