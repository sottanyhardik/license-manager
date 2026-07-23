"""
Data migration — backfill baseline_used_quantity/baseline_used_cif_fc for
LicenseItemPlan rows that existed before those fields were introduced
(migration 0013).

Every such row defaulted to baseline 0, which means `plan_status_for` would
treat its group's ENTIRE all-time live-allotted total as "used" — i.e. the
same (correct, but potentially alarming) behavior as before this feature
existed for any item that already has both a plan and allotments against
it. To avoid every pre-existing plan across the system suddenly surfacing a
(possibly large negative) Remaining the moment this ships, we instead reset
every existing row's baseline to "whatever is live-allotted for its group
right now" — i.e. every pre-existing plan starts fresh, Used=0, exactly as
if it had just been (re)saved. Going forward, only NEW allotments (made
after this migration runs) will count against it, exactly per
`plan_status_for`'s documented semantics.

This is a one-time approximation for historical rows only — it cannot know
how much was legitimately used between each row's original creation and
this migration running. New plans created after this migration always get
an accurate baseline stamped at save time (see
`plan_enforcement.save_plan_lines_for_license`).
"""
from django.db import migrations


def backfill_baseline(apps, schema_editor):
    LicenseItemPlan = apps.get_model("license", "LicenseItemPlan")
    AllotmentItems = apps.get_model("allotment", "AllotmentItems")
    from django.db.models import Q, Sum, DecimalField, Value
    from django.db.models.functions import Coalesce

    allotted_filter = Q(allotment__bill_of_entry__isnull=True, allotment__type="AT")

    # Group rows by their (already-immutable at this point) import_item — a
    # plain per-item snapshot is a safe, conservative approximation of the
    # group-level baseline `plan_status_for` would compute (a group's members
    # share the same live-allotted-for-group total in the common case of one
    # item per description; multi-serial groups just get a slightly smaller
    # backfilled baseline per row, which only makes Remaining more generous
    # immediately after this migration, never less).
    for plan in LicenseItemPlan.objects.all():
        if not plan.import_item_id:
            continue
        totals = AllotmentItems.objects.filter(
            allotted_filter, item_id=plan.import_item_id,
        ).aggregate(
            qty=Coalesce(Sum("qty"), Value(0), output_field=DecimalField()),
            cif=Coalesce(Sum("cif_fc"), Value(0), output_field=DecimalField()),
        )
        plan.baseline_used_quantity = totals["qty"] or 0
        plan.baseline_used_cif_fc = totals["cif"] or 0
        plan.save(update_fields=["baseline_used_quantity", "baseline_used_cif_fc"])


def noop_reverse(apps, schema_editor):
    """Irreversible in any meaningful sense — leave baselines as they are."""


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0013_licenseitemplan_baseline_used_cif_fc_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_baseline, noop_reverse),
    ]
