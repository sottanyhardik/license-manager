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
from apps.license.services.e132_plan import MILK, NORM, PLANNING_ORDER


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

        # Milk is now an internal classification pool only (split into SWP/DWP/WPC),
        # never an output planning item — hide its master.
        milk = ItemNameModel.objects.filter(name=MILK).first()
        if milk is not None and milk.is_active:
            self.stdout.write(f"  ~ hide    {MILK} (now internal pool)")
            updated += 1
            if not dry:
                milk.is_active = False
                milk.save(update_fields=["is_active"])

        self.stdout.write(self.style.SUCCESS(
            f"E132 planning items: {created} created, {updated} updated"
            f"{' (dry-run, no writes)' if dry else ''}."))
