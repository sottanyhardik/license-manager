# license/management/commands/debug_item.py
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Sum, DecimalField, Value
from django.db.models.functions import Coalesce
from license.models import LicenseImportItemsModel
from allotment.models import AllotmentItems


class Command(BaseCommand):
    help = "Debug specific item balance calculation"

    def add_arguments(self, parser):
        parser.add_argument("item_id", type=int, help="Item ID")

    def handle(self, *args, **opts):
        item_id = opts["item_id"]

        try:
            item = LicenseImportItemsModel.objects.select_related('license').prefetch_related(
                'items__head__restriction_norm',
                'license__export_license__norm_class'
            ).get(id=item_id)

            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(f"DEBUGGING ITEM {item_id}")
            self.stdout.write(f"{'='*80}\n")

            # Basic info
            self.stdout.write(f"License: {item.license.license_number}")
            self.stdout.write(f"Serial Number: {item.serial_number}")
            self.stdout.write(f"Notification: {item.license.notification_number}")
            self.stdout.write(f"Purchase Status: {item.license.purchase_status}")

            # Check if exception
            is_exception = (
                item.license.notification_number == "098/2009" or
                item.license.purchase_status == "CO"
            )
            self.stdout.write(f"Is Exception (098/2009 or Conversion): {is_exception}\n")

            # Financial data
            self.stdout.write(f"CIF FC: {item.cif_fc}")
            self.stdout.write(f"Debited Value: {item.debited_value}")
            self.stdout.write(f"Allotted Value: {item.allotted_value}")
            self.stdout.write(f"Available Value (stored): {item.available_value}\n")

            # Calculate simple balance
            simple = Decimal(str(item.cif_fc or 0)) - Decimal(str(item.debited_value or 0)) - Decimal(str(item.allotted_value or 0))
            self.stdout.write(f"Simple Calculation: {item.cif_fc} - {item.debited_value} - {item.allotted_value} = {simple:.2f}\n")

            # Check property
            self.stdout.write(f"balance_cif_fc property: {item.balance_cif_fc}\n")

            # Check restrictions
            has_restriction = item.items.filter(
                head__is_restricted=True,
                head__restriction_norm__isnull=False,
                head__restriction_percentage__gt=0
            ).exists()
            self.stdout.write(f"Has Restriction: {has_restriction}\n")

            if has_restriction:
                for item_name in item.items.all():
                    if item_name.head:
                        self.stdout.write(f"  Head: {item_name.head.name}")
                        self.stdout.write(f"  Is Restricted: {item_name.head.is_restricted}")
                        self.stdout.write(f"  Restriction %: {item_name.head.restriction_percentage}")
                        if item_name.head.restriction_norm:
                            self.stdout.write(f"  Restriction Norm: {item_name.head.restriction_norm.norm_class}")

            # What serializer would return
            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(f"WHAT API RETURNS")
            self.stdout.write(f"{'='*80}")

            if is_exception:
                self.stdout.write(f"Exception license → Use balance_cif_fc: {item.balance_cif_fc}")
            elif has_restriction:
                if item.available_value and item.available_value > 0:
                    self.stdout.write(f"Restricted → Use available_value: {item.available_value}")
                else:
                    self.stdout.write(f"Restricted but available_value=0 → Use balance_cif_fc: {item.balance_cif_fc}")
            else:
                self.stdout.write(f"No restriction → Use balance_cif_fc: {item.balance_cif_fc}")

            self.stdout.write(f"\n{'='*80}\n")

        except LicenseImportItemsModel.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Item {item_id} not found"))
