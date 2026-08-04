"""Seed the E132 planning-item masters (idempotent).

Creates/activates the ItemNameModel rows the E132 planning classification uses and
links them to the E132 SION norm class. Item names come from
apps.license.services.e132_plan (the single source of truth), so the masters can
never drift from the classifier. Safe to re-run.

Usage:
    python manage.py seed_e132_plan_items [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.services.e132_plan import NORM, PLANNING_ORDER

# Planning items the E132 rule-set USED to produce, before the "Replace
# Existing Split Logic" rewrite dropped them (Milk/SWP/DWP/WPC/Raisin/Cereals
# Flakes/CMC are no longer part of `PLANNING_ORDER` and never classify a
# record anymore). Named as literal strings, not imported — the constants
# themselves were deleted along with the rules that produced them. A
# production database may still have these masters marked active from
# before the rewrite; hide them so they stop showing up as selectable
# planning items (e.g. the Allotment "Planned Item Name" filter, which only
# lists `is_active=True` names) even though nothing will ever plan into them
# again. Historical `LicenseItemPlan` rows that already reference one are
# untouched (`ItemNameModel.is_active=False` doesn't cascade to existing FKs).
_RETIRED_PLANNING_ITEMS = (
    "Milk - E132",
    "SWP - E132",
    "DWP - E132",
    "WPC - E132",
    "RAISIN - E132",
    "CEREALS FLAKES - E132",
    "CMC - E132",
)


class Command(BaseCommand):
    help = "Create/activate the E132 planning-item masters and link them to the E132 norm class."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would change without writing.")

    @transaction.atomic
    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        norm = SionNormClassModel.objects.filter(norm_class=NORM).first()
        if norm is None:
            self.stdout.write(self.style.WARNING(
                f"SION norm class '{NORM}' not found — items will be created without a norm link."))

        created = updated = 0
        for order, name in enumerate(PLANNING_ORDER, start=1):
            obj = ItemNameModel.objects.filter(name=name).first()
            if obj is None:
                self.stdout.write(f"  + create  {name}")
                created += 1
                if not dry:
                    ItemNameModel.objects.create(
                        name=name, is_active=True, sion_norm_class=norm, display_order=order)
                continue
            changed = []
            fields = []
            if not obj.is_active:
                obj.is_active = True
                changed.append("active")
                fields.append("is_active")
            if norm is not None and obj.sion_norm_class_id != norm.id:
                obj.sion_norm_class = norm
                changed.append("norm=E132")
                fields.append("sion_norm_class")
            # Keep display_order aligned with PLANNING_ORDER so reports that sort by
            # it (Item Pivot, MasterList) show the planning priority order.
            if obj.display_order != order:
                obj.display_order = order
                changed.append(f"order={order}")
                fields.append("display_order")
            if changed:
                self.stdout.write(f"  ~ update  {name} ({', '.join(changed)})")
                updated += 1
                if not dry:
                    obj.save(update_fields=fields)
            else:
                self.stdout.write(f"  = ok      {name}")

        # Hide masters for planning items the rule-set no longer produces at
        # all (see _RETIRED_PLANNING_ITEMS) — safe/idempotent no-op once
        # they're already inactive or don't exist.
        for name in _RETIRED_PLANNING_ITEMS:
            obj = ItemNameModel.objects.filter(name=name).first()
            if obj is not None and obj.is_active:
                self.stdout.write(f"  ~ hide    {name} (retired planning item)")
                updated += 1
                if not dry:
                    obj.is_active = False
                    obj.save(update_fields=["is_active"])

        self.stdout.write(self.style.SUCCESS(
            f"E132 planning items: {created} created, {updated} updated"
            f"{' (dry-run, no writes)' if dry else ''}."))
