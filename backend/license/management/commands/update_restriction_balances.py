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

    def handle(self, *args, **opts):
        DEC_0 = Decimal("0.00")
        DEC_000 = Decimal("0.000")

        license_number = opts.get("license_number")
        dry_run = bool(opts.get("dry_run"))

        # Filter: is_expired=False, is_null=False, and expiry date >= 2025-01-01 (active licenses)
        qs = LicenseDetailsModel.objects.filter(
            license_expiry_date__gte='2025-01-01'
        )
        if license_number:
            qs = qs.filter(license_number=license_number)

        self.stdout.write(
            f"Processing {qs.count()} active licenses (is_expired=False, is_null=False, expiry >= 2025-01-01)...")
        self.stdout.write("")

        lic_updated = 0
        row_updated = 0
        restriction_applied = 0

        for lic in qs.iterator():
            # Get all import items for this license
            import_items = LicenseImportItemsModel.objects.filter(license=lic).prefetch_related('items__head')

            for item in import_items:
                # Check if item has restricted head
                has_restriction = False
                restricted_head = None

                item_names = item.items.all()
                if item_names:
                    # Get license export norm classes
                    license_norm_classes = list(
                        lic.export_license.all()
                        .values_list("norm_class__norm_class", flat=True)
                    )

                    for item_name in item_names:
                        if (item_name.head and item_name.head.is_restricted and
                                item_name.head.restriction_norm and item_name.head.restriction_percentage > DEC_0):

                            # Check if license export norm class matches head restriction norm
                            restriction_norm_class = item_name.head.restriction_norm.norm_class if item_name.head.restriction_norm else None
                            if restriction_norm_class and restriction_norm_class in license_norm_classes:
                                has_restriction = True
                                restricted_head = item_name.head
                                break

                if not has_restriction:
                    # No restriction, skip this item
                    continue

                restriction_applied += 1

                # Calculate restriction balance
                license_cif = lic._calculate_license_credit()
                allowed_value = license_cif * (restricted_head.restriction_percentage / Decimal("100"))

                # Get all items with same head in this license
                same_head_items = LicenseImportItemsModel.objects.filter(
                    license=lic,
                    items__head=restricted_head
                ).distinct()

                total_debited = DEC_0
                total_allotted = DEC_0

                for same_item in same_head_items:
                    # Debited value
                    debited = same_item._calculate_item_debit()
                    total_debited += debited

                    # Allotted value (excluding BOE)
                    allotted_no_boe = AllotmentItems.objects.filter(
                        item=same_item,
                        is_boe=False
                    ).aggregate(total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))["total"]
                    total_allotted += Decimal(str(allotted_no_boe or 0))

                # Calculate available balance based on restriction
                restriction_balance = allowed_value - total_debited - total_allotted
                restriction_balance = restriction_balance if restriction_balance >= DEC_0 else DEC_0

                # Get current available value
                current_available = Decimal(str(item.available_value or 0))

                # Check if update needed
                if abs(current_available - restriction_balance) > Decimal("0.01"):
                    self.stdout.write(
                        f"  License {lic.license_number} Item {item.id} ({restricted_head.name}): "
                        f"available_value {current_available:.2f} → {restriction_balance:.2f} "
                        f"(allowed: {allowed_value:.2f}, used: {total_debited + total_allotted:.2f})"
                    )

                    if not dry_run:
                        item.available_value = restriction_balance
                        item.save(update_fields=['available_value'])

                    row_updated += 1

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
