# license/management/commands/check_item_balance.py
from decimal import Decimal
from django.core.management.base import BaseCommand
from license.models import LicenseImportItemsModel


class Command(BaseCommand):
    help = "Check balance details for a specific import item"

    def add_arguments(self, parser):
        parser.add_argument(
            "item_id",
            type=int,
            help="Import item ID to check",
        )

    def handle(self, *args, **opts):
        item_id = opts.get("item_id")

        try:
            item = LicenseImportItemsModel.objects.select_related(
                'license', 'license__exporter'
            ).prefetch_related(
                'items__head__restriction_norm',
                'license__export_license__norm_class'
            ).get(id=item_id)

            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(f"IMPORT ITEM DETAILS - ID: {item.id}")
            self.stdout.write(f"{'='*80}\n")

            # License info
            self.stdout.write(f"License Number: {item.license.license_number}")
            self.stdout.write(f"License Date: {item.license.license_date}")
            self.stdout.write(f"License Expiry: {item.license.license_expiry_date}")
            self.stdout.write(f"Exporter: {item.license.exporter.name if item.license.exporter else 'N/A'}")
            self.stdout.write(f"Notification: {item.license.notification_number}")
            self.stdout.write(f"Purchase Status: {item.license.purchase_status}")
            self.stdout.write(f"Serial Number: {item.serial_number}")
            self.stdout.write(f"Description: {item.description}\n")

            # Export norms
            export_norms = list(
                item.license.export_license.all().values_list("norm_class__norm_class", flat=True)
            )
            self.stdout.write(f"Export Norm Classes: {export_norms}\n")

            # Item financial details
            self.stdout.write(f"{'='*80}")
            self.stdout.write(f"FINANCIAL DETAILS")
            self.stdout.write(f"{'='*80}")
            self.stdout.write(f"CIF FC: {item.cif_fc}")
            self.stdout.write(f"CIF INR: {item.cif_inr}")
            self.stdout.write(f"Quantity: {item.quantity}")
            self.stdout.write(f"Unit: {item.unit}\n")

            self.stdout.write(f"Debited Quantity: {item.debited_quantity}")
            self.stdout.write(f"Debited Value: {item.debited_value}")
            self.stdout.write(f"Allotted Quantity: {item.allotted_quantity}")
            self.stdout.write(f"Allotted Value: {item.allotted_value}")
            self.stdout.write(f"Available Quantity: {item.available_quantity}")
            self.stdout.write(f"Available Value (stored): {item.available_value}\n")

            # Calculated balances
            self.stdout.write(f"{'='*80}")
            self.stdout.write(f"CALCULATED BALANCES")
            self.stdout.write(f"{'='*80}")

            # Calculate simple available
            simple_available = Decimal(str(item.cif_fc or 0)) - Decimal(str(item.debited_value or 0)) - Decimal(str(item.allotted_value or 0))
            self.stdout.write(f"Simple Available (CIF - Debited - Allotted): {simple_available:.2f}")

            # Get balance_cif_fc property
            balance_cif_fc = Decimal(str(item.balance_cif_fc or 0))
            self.stdout.write(f"balance_cif_fc property: {balance_cif_fc:.2f}\n")

            # Check for restrictions
            self.stdout.write(f"{'='*80}")
            self.stdout.write(f"RESTRICTION CHECK")
            self.stdout.write(f"{'='*80}")

            item_names = item.items.all()
            self.stdout.write(f"Item Names Count: {item_names.count()}\n")

            has_restriction = False
            for item_name in item_names:
                self.stdout.write(f"  - Item Name: {item_name.name}")
                if item_name.head:
                    self.stdout.write(f"    Head: {item_name.head.name}")
                    self.stdout.write(f"    Is Restricted: {item_name.head.is_restricted}")
                    if item_name.head.restriction_norm:
                        self.stdout.write(f"    Restriction Norm: {item_name.head.restriction_norm.norm_class}")
                    else:
                        self.stdout.write(f"    Restriction Norm: None")
                    self.stdout.write(f"    Restriction Percentage: {item_name.head.restriction_percentage}%")

                    # Check if restriction applies
                    if (item_name.head.is_restricted and
                        item_name.head.restriction_norm and
                        item_name.head.restriction_percentage > 0):
                        restriction_norm_class = item_name.head.restriction_norm.norm_class
                        if restriction_norm_class in export_norms:
                            has_restriction = True
                            self.stdout.write(f"    ✓ RESTRICTION APPLIES! ({restriction_norm_class} in {export_norms})")
                        else:
                            self.stdout.write(f"    ✗ Restriction norm {restriction_norm_class} NOT in license export norms {export_norms}")
                else:
                    self.stdout.write(f"    Head: None")
                self.stdout.write("")

            self.stdout.write(f"{'='*80}")
            self.stdout.write(f"SUMMARY")
            self.stdout.write(f"{'='*80}")
            self.stdout.write(f"Has Restriction: {has_restriction}")
            self.stdout.write(f"Stored available_value: {item.available_value}")
            self.stdout.write(f"Calculated balance_cif_fc: {balance_cif_fc:.2f}")
            self.stdout.write(f"Simple calculation: {simple_available:.2f}")

            # What should be used
            if has_restriction:
                self.stdout.write(f"\n⚠️  This item HAS restrictions")
                self.stdout.write(f"Should use: available_value = {item.available_value}")
                if item.available_value == 0 or item.available_value is None:
                    self.stdout.write(f"⚠️  WARNING: available_value is 0 or NULL!")
                    self.stdout.write(f"Run: python manage.py update_restriction_balances --license {item.license.license_number}")
            else:
                self.stdout.write(f"\n✓ This item has NO restrictions")
                self.stdout.write(f"Should use: balance_cif_fc = {balance_cif_fc:.2f}")

            self.stdout.write(f"\n{'='*80}\n")

        except LicenseImportItemsModel.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Item with ID {item_id} not found"))
