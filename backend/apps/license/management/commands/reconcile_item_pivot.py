"""
Debug command: Reconcile Item Pivot Available/Planned quantities for a specific SION.

Usage:
  python manage.py reconcile_item_pivot --sion E1 [--item "DWP - E1"]

Shows per-license available_qty, planned_qty, remaining for each item.
"""

from django.core.management.base import BaseCommand
from django.db.models import Q, Sum, Prefetch
from decimal import Decimal
from datetime import timedelta
from datetime import date

from apps.license.models import LicenseDetailsModel, LicenseItemPlan, LicenseImportItemsModel
from apps.core.models import ItemNameModel
from apps.core.constants import GE, MI, CO, DEC_0, DEC_000


class Command(BaseCommand):
    help = "Reconcile Item Pivot Available vs Planned quantities"

    def add_arguments(self, parser):
        parser.add_argument('--sion', type=str, help='SION norm (E1, E5, E132, etc.)')
        parser.add_argument('--item', type=str, help='Item name filter (optional)')
        parser.add_argument('--license', type=str, help='License number filter (optional)')

    def handle(self, *args, **options):
        sion = options.get('sion')
        item_filter = options.get('item')
        license_filter = options.get('license')

        # Get licenses matching criteria
        licenses = LicenseDetailsModel.objects.filter(
            purchase_status__code__in=[GE, MI, CO],
            flags__is_active=True,
            license_expiry_date__gt=date.today() - timedelta(days=30),
        )

        if sion:
            licenses = licenses.filter(export_license__norm_class__norm_class=sion).distinct()

        if license_filter:
            licenses = licenses.filter(license_number=license_filter)

        # Prefetch related data
        licenses = licenses.select_related(
            'exporter',
            'port',
        ).prefetch_related(
            Prefetch('import_license', queryset=LicenseImportItemsModel.objects.select_related('hs_code').prefetch_related('items'))
        )

        print(f"\n=== Item Pivot Reconciliation ===")
        print(f"SION: {sion or 'all'}")
        print(f"Item filter: {item_filter or 'none'}")
        print(f"License filter: {license_filter or 'none'}")
        print(f"Licenses found: {licenses.count()}\n")

        # Load all plans for these licenses
        plans = LicenseItemPlan.objects.filter(
            license__in=licenses
        ).select_related('license').prefetch_related('license__export_license')

        # Group plans by (license, item_name)
        by_license_item = {}
        for plan in plans:
            key = (plan.license_id, plan.item_name)
            if key not in by_license_item:
                by_license_item[key] = {
                    'planned_qty': Decimal('0'),
                    'planned_cif': Decimal('0'),
                    'plans': []
                }
            by_license_item[key]['planned_qty'] += plan.planned_quantity or Decimal('0')
            by_license_item[key]['planned_cif'] += plan.planned_cif_fc or Decimal('0')
            by_license_item[key]['plans'].append(plan)

        # Build available_qty per (license, import_item) then reconcile
        print(f"{'License':<20} {'Item Name':<40} {'Available Qty':<20} {'Planned Qty':<20} {'Issue':<40}")
        print("=" * 140)

        for license_obj in licenses:
            # Get available quantities from import items
            import_items = license_obj.import_license.all()

            # Group import item quantities by the item names they're tagged with
            by_item_name = {}
            for ii in import_items:
                for item in ii.items.all():
                    if item_filter and item.name != item_filter:
                        continue
                    if item.name not in by_item_name:
                        by_item_name[item.name] = Decimal('0')
                    by_item_name[item.name] += Decimal(str(ii.available_quantity or 0))

            # Now check against plans
            for item_name, available_qty in by_item_name.items():
                plan_key = (license_obj.id, item_name)
                planned_qty = by_license_item.get(plan_key, {}).get('planned_qty', Decimal('0'))

                issue = ''
                if planned_qty > available_qty:
                    issue = "PLANNED > AVAILABLE"
                elif planned_qty == 0 and available_qty > 0:
                    issue = "No plan for available qty"

                if issue:
                    print(f"{license_obj.license_number:<20} {item_name:<40} {float(available_qty):<20.3f} {float(planned_qty):<20.3f} {issue:<40}")

        print("\n=== Summary ===")
        total_available = sum(
            (Decimal(str(ii.available_quantity or 0)) for lic in licenses for ii in lic.import_license.all()),
            Decimal('0')
        )
        total_planned = sum(
            (plan.planned_cif_fc or Decimal('0') for plan in plans),
            Decimal('0')
        )

        print(f"Total Available: {float(total_available):.3f}")
        print(f"Total Planned:   {float(total_planned):.3f}")
        print(f"Difference:      {float(total_available - total_planned):.3f}")

        if total_planned > total_available:
            print("\n⚠️ PROBLEM: Total Planned > Total Available")
            print("This indicates the aggregation is including plans not attributed to available items.")
            print("Likely cause: Split items (DWP/SWP) have zero available_qty in Item Pivot but nonzero planned_qty")
