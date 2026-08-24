"""Detach PLAN allocations from disposable plan projections.

The old FK is deliberately retained as nullable SET_NULL for one release so
existing rows can be deployed safely.  Runtime code uses only the copied
business dimensions; a later removal migration can drop the FK after the
deployment audit has reported no unmapped rows.
"""
from django.db import migrations, models
from django.db.models import F, Sum
from django.core.validators import MinValueValidator


def copy_plan_dimensions(apps, schema_editor):
    AllotmentItems = apps.get_model("allotment", "AllotmentItems")
    # Copy the target while the referenced projection still exists.  Do not
    # overwrite an explicit target and do not silently discard unmappable rows.
    for row in AllotmentItems.objects.filter(plan_line__isnull=False, planning_target_item__isnull=True).select_related("plan_line"):
        if row.plan_line_id and row.plan_line.item_name_id:
            row.planning_target_item_id = row.plan_line.item_name_id
            row.save(update_fields=["planning_target_item"])


def consolidate_master_rows(apps, schema_editor):
    """Merge only complete durable identities, retaining their total facts."""
    AllotmentItems = apps.get_model("allotment", "AllotmentItems")
    identities = (
        AllotmentItems.objects.values("allotment_id", "item_id", "allocation_basis", "planning_target_item_id")
        .annotate(count=models.Count("id"))
        .filter(count__gt=1)
    )
    for identity in identities:
        rows = AllotmentItems.objects.filter(
            allotment_id=identity["allotment_id"], item_id=identity["item_id"],
            allocation_basis=identity["allocation_basis"],
            planning_target_item_id=identity["planning_target_item_id"],
        ).order_by("id")
        keeper = rows.first()
        totals = rows.aggregate(qty=Sum("qty"), cif_fc=Sum("cif_fc"), cif_inr=Sum("cif_inr"))
        keeper.qty = totals["qty"] or 0
        keeper.cif_fc = totals["cif_fc"] or 0
        keeper.cif_inr = totals["cif_inr"] or 0
        keeper.save(update_fields=["qty", "cif_fc", "cif_inr"])
        rows.exclude(pk=keeper.pk).delete()


class Migration(migrations.Migration):
    # PostgreSQL cannot alter constraints while deferred FK trigger events from
    # the data backfill are pending.  Keep this deploy migration non-atomic so
    # the backfill commits before the constraint replacement operations.
    atomic = False

    dependencies = [("allotment", "0014_plan_line_allocation_identity")]

    operations = [
        migrations.AddField(
            model_name="allotmentitems", name="planning_sion_key",
            field=models.CharField(blank=True, db_index=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="allotmentitems", name="effective_unit_price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15, validators=[MinValueValidator(0)]),
        ),
        migrations.RunPython(copy_plan_dimensions, migrations.RunPython.noop),
        migrations.RunPython(consolidate_master_rows, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="allotmentitems", name="allotment_unique_item_plan_line",
        ),
        migrations.RemoveConstraint(
            model_name="allotmentitems", name="allotment_unique_item_without_plan_line",
        ),
        migrations.AddConstraint(
            model_name="allotmentitems",
            constraint=models.UniqueConstraint(
                condition=models.Q(planning_target_item__isnull=False),
                fields=("item", "allotment", "allocation_basis", "planning_target_item"),
                name="allotment_unique_stable_plan_identity",
            ),
        ),
        migrations.AddConstraint(
            model_name="allotmentitems",
            constraint=models.UniqueConstraint(
                condition=models.Q(planning_target_item__isnull=True),
                fields=("item", "allotment", "allocation_basis"),
                name="allotment_unique_item_without_plan_line",
            ),
        ),
        migrations.AddIndex(
            model_name="allotmentitems",
            index=models.Index(
                fields=["allotment", "item", "allocation_basis", "planning_target_item"],
                name="allotment_stable_identity_idx",
            ),
        ),
    ]
