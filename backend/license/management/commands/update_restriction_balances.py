# license/management/commands/update_restriction_balances.py
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum, DecimalField, Value
from django.db.models.functions import Coalesce

from allotment.models import AllotmentItems
from license.models import LicenseDetailsModel, LicenseImportItemsModel


class Command(BaseCommand):
    help = (
        "Update available balances for all licenses with restrictions "
        "where is_expired=False and is_null=False. "
        "Ensures we don't debit/allot more than the restriction allows."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--license",
            dest="license_number",
            help="Limit to a specific license_number (exact match).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write any changes; just report what would be updated.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limit number of licenses to process (useful for testing).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of licenses to process in each batch (default: 50).",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed debug information.",
        )

    def handle(self, *args, **opts):
        DEC_0 = Decimal("0.00")
        DEC_000 = Decimal("0.000")

        license_number = opts.get("license_number")
        dry_run = bool(opts.get("dry_run"))
        limit = opts.get("limit")
        batch_size = opts.get("batch_size", 50)
        verbose = bool(opts.get("verbose"))

        # Filter: is_expired=False, is_null=False, and expiry date >= 2025-01-01 (active licenses)
        qs = LicenseDetailsModel.objects.filter(
            license_expiry_date__gte='2025-01-01'
        ).prefetch_related('export_license__norm_class')

        if license_number:
            qs = qs.filter(license_number=license_number)

        if limit:
            qs = qs[:limit]

        total_licenses = qs.count()
        self.stdout.write(
            f"Processing {total_licenses} active licenses (expiry >= 2025-01-01)...")
        self.stdout.write(f"Batch size: {batch_size} | Dry run: {dry_run}")
        self.stdout.write("")

        lic_updated = 0
        row_updated = 0
        restriction_applied = 0
        processed_count = 0

        for lic in qs.iterator(chunk_size=batch_size):
            processed_count += 1

            # Show progress every 10 licenses
            if processed_count % 10 == 0:
                self.stdout.write(f"Progress: {processed_count}/{total_licenses} licenses processed...")

            # Get all import items for this license
            import_items = LicenseImportItemsModel.objects.filter(license=lic).prefetch_related(
                'items__head__restriction_norm'
            )

            # Cache license norm classes for this license
            license_norm_classes = list(
                lic.export_license.all()
                .values_list("norm_class__norm_class", flat=True)
            )

            # Check exception: 098/2009 OR Conversion - restrictions do not apply
            N2009 = "098/2009"
            CO = "CO"
            skip_restriction = (lic.notification_number == N2009 or lic.purchase_status == CO)

            if verbose:
                self.stdout.write(f"\n  License {lic.license_number}:")
                self.stdout.write(f"    Notification: {lic.notification_number}")
                self.stdout.write(f"    Purchase Status: {lic.purchase_status}")
                if skip_restriction:
                    self.stdout.write(f"    ⚠️  Exception: Restrictions do NOT apply (098/2009 or Conversion)")

            # Calculate total license CIF for restriction calculation
            total_license_cif = lic.import_license.aggregate(
                total_cif=Coalesce(Sum('cif_fc'), Value(DEC_0), output_field=DecimalField())
            )['total_cif']

            if verbose:
                self.stdout.write(f"    Total CIF: {total_license_cif}")
                self.stdout.write(f"    Export Norm Classes: {license_norm_classes}")

            # Now process each import item to check if it has restrictions
            for item in import_items:
                if verbose:
                    self.stdout.write(f"\n    SR {item.serial_number} (Item ID: {item.id}):")
                    self.stdout.write(f"      Item CIF: {item.cif_fc}")

                # Get item's balance_cif_fc (actual available balance without restriction)
                item_balance_cif_fc = Decimal(str(item.balance_cif_fc or 0))
                current_available = Decimal(str(item.available_value or 0))

                # CRITICAL CHECK: available_value should NEVER exceed balance_cif_fc
                if current_available > item_balance_cif_fc:
                    self.stdout.write(
                        f"  ⚠️  CRITICAL FIX - License {lic.license_number} SR {item.serial_number} Item {item.id}: "
                        f"available_value {current_available:.2f} > balance_cif_fc {item_balance_cif_fc:.2f} "
                        f"→ CAPPING to {item_balance_cif_fc:.2f}"
                    )
                    if not dry_run:
                        item.available_value = item_balance_cif_fc
                        item.save()
                        self.stdout.write(f"     ✓ Updated available_value to {item_balance_cif_fc:.2f}")
                    else:
                        self.stdout.write(f"     (DRY RUN - would update to {item_balance_cif_fc:.2f})")
                    row_updated += 1
                    # Update current_available for subsequent checks
                    current_available = item_balance_cif_fc

                # Check if this item is under a restricted head
                has_restriction = False
                restricted_head_name = "N/A"
                restriction_percentage = DEC_0
                head_id = None

                item_names = item.items.all()

                if verbose:
                    self.stdout.write(f"      Item Names Count: {item_names.count()}")

                for item_name in item_names:
                    if verbose:
                        head_info = f"Head: {item_name.head.name if item_name.head else 'None'}"
                        if item_name.head:
                            head_info += f", is_restricted: {item_name.head.is_restricted}"
                            head_info += f", restriction_norm: {item_name.head.restriction_norm.norm_class if item_name.head.restriction_norm else 'None'}"
                            head_info += f", restriction_percentage: {item_name.head.restriction_percentage}%"
                        self.stdout.write(f"        - {head_info}")

                    if (item_name.head and item_name.head.is_restricted and
                            item_name.head.restriction_norm and item_name.head.restriction_percentage > DEC_0):
                        # Check if license export norm class matches head restriction norm
                        restriction_norm_class = item_name.head.restriction_norm.norm_class

                        if verbose:
                            self.stdout.write(
                                f"          Checking: {restriction_norm_class} in {license_norm_classes} = {restriction_norm_class in license_norm_classes}")

                        if restriction_norm_class in license_norm_classes:
                            has_restriction = True
                            head_id = item_name.head.id
                            restricted_head_name = item_name.head.name
                            restriction_percentage = item_name.head.restriction_percentage
                            if verbose:
                                self.stdout.write(f"          ✓ RESTRICTION APPLIES!")
                            break

                # Only process restriction logic if item has restrictions AND license is not exception
                if not has_restriction or skip_restriction:
                    if verbose:
                        if skip_restriction:
                            self.stdout.write(f"      → Skipping restriction (098/2009 or Conversion)")
                        else:
                            self.stdout.write(f"      → No restriction for this item")

                    # For non-restricted items or exception licenses, set available_value = balance_cif_fc
                    item_balance_cif_fc = Decimal(str(item.balance_cif_fc or 0))
                    current_available = Decimal(str(item.available_value or 0))

                    # Update if different
                    if abs(current_available - item_balance_cif_fc) > Decimal("0.01"):
                        self.stdout.write(
                            f"  License {lic.license_number} SR {item.serial_number} Item {item.id} "
                            f"(No restriction): "
                            f"available_value {current_available:.2f} → {item_balance_cif_fc:.2f}"
                        )
                        if not dry_run:
                            item.available_value = item_balance_cif_fc
                            item.save(update_fields=['available_value'])
                        row_updated += 1

                    continue

                # Calculate restriction amount for this head: total_license_cif * restriction_percentage / 100
                restriction_amount = (total_license_cif * restriction_percentage) / Decimal("100")
                # Get total debited for this head and license
                # AllotmentItems -> item (LicenseImportItemsModel) -> items (ItemNameModel) -> head
                debited_amount = AllotmentItems.objects.filter(
                    item__license=lic,
                    item__items__head_id=head_id
                ).aggregate(
                    total_debited=Coalesce(Sum('cif_fc'), Value(DEC_0), output_field=DecimalField())
                )['total_debited']

                # Calculate available as: restriction_amount - debited_amount
                calculated_balance = restriction_amount - debited_amount

                # Ensure non-negative
                calculated_balance = max(calculated_balance, DEC_0)

                # CRITICAL: Use minimum of calculated restriction balance and item's actual balance
                # balance_cif_fc is MOST IMPORTANT - cannot allocate more than what's actually available
                # This ensures the system won't break by trying to allocate more than available
                final_balance = min(calculated_balance, item_balance_cif_fc)
                if final_balance > lic.balance_cif:
                    final_balance = lic.balance_cif

                # Get current available value (re-fetch in case it was updated in critical check)
                current_available = Decimal(str(item.available_value or 0))

                # Check if update needed
                if abs(current_available - final_balance) > Decimal("0.01"):
                    restriction_info = f"({restricted_head_name} {restriction_percentage}% restriction)"
                    limiting_factor = "balance_cif_fc" if item_balance_cif_fc < calculated_balance else "restriction"

                    self.stdout.write(
                        f"  License {lic.license_number} SR {item.serial_number} Item {item.id} "
                        f"{restriction_info}: "
                        f"Total CIF: {total_license_cif:.2f}, "
                        f"Restriction: {restriction_amount:.2f}, "
                        f"Debited: {debited_amount:.2f}, "
                        f"Item balance_cif_fc: {item_balance_cif_fc:.2f}, "
                        f"Limiting factor: {limiting_factor}, "
                        f"available_value {current_available:.2f} → {final_balance:.2f}"
                    )

                    if not dry_run:
                        # final_balance already has the minimum logic applied
                        item.available_value = final_balance
                        item.save(update_fields=['available_value'])

                    row_updated += 1
                    restriction_applied += 1

            # Update license balance_cif
            actual_balance = lic.get_balance_cif
            current_balance = lic.balance_cif or 0.0

            want = Decimal(str(round(float(actual_balance), 2)))
            have = Decimal(str(round(float(current_balance), 2)))

            if abs(want - have) > Decimal("0.01"):
                self.stdout.write(
                    f"License {lic.license_number}: balance_cif {have} → {want}"
                )
                if not dry_run:
                    lic.balance_cif = float(want)
                    lic.save(update_fields=["balance_cif"])
                lic_updated += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Done. Licenses updated: {lic_updated} | "
                f"Import items updated: {row_updated} | "
                f"Restrictions applied: {restriction_applied} | "
                f"dry_run={dry_run}"
            )
        )
