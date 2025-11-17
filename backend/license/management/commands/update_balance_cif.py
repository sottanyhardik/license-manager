# license/management/commands/recompute_balances.py
from __future__ import annotations

from decimal import Decimal

from allotment.models import AllotmentItems
from bill_of_entry.models import RowDetails
from core.constants import DEBIT
from django.core.management.base import BaseCommand
from django.db.models import Sum
from license.models import LicenseDetailsModel, LicenseImportItemsModel


class Command(BaseCommand):
    help = (
        "Recompute license.balance_cif from get_balance_cif and (optionally) "
        "recompute related import rows' available_quantity and available_value."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--license",
            dest="license_number",
            help="Limit to a specific license_number (exact match).",
        )
        parser.add_argument(
            "--no-rows",
            action="store_true",
            help="Skip per-row recomputation; only update license.balance_cif.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write any changes; just report what would be updated.",
        )

    def handle(self, *args, **opts):
        from datetime import date, timedelta

        license_number = opts.get("license_number")
        skip_rows = bool(opts.get("no_rows"))
        dry_run = bool(opts.get("dry_run"))

        qs = LicenseDetailsModel.objects.filter(license_expiry_date__gte='2025-01-01')
        if license_number:
            qs = qs.filter(license_number=license_number)

        lic_updates = 0
        row_updates = 0

        for lic in qs.iterator():
            # --- Update stored license.balance_cif from authoritative property
            actual_balance = lic.get_balance_cif
            current_balance = lic.balance_cif or 0.0

            # Compare at 2 decimals to avoid micro-diffs
            want = Decimal(str(round(float(actual_balance), 2)))
            have = Decimal(str(round(float(current_balance), 2)))

            fields_to_update = []

            if want != have:
                self.stdout.write(
                    f"License {lic.license_number}: balance_cif {have} → {want}"
                )
                if not dry_run:
                    lic.balance_cif = float(want)
                    fields_to_update.append("balance_cif")
                lic_updates += 1

            # --- Check and update is_null if balance_cif < 100
            should_be_null = want < Decimal("100")
            if should_be_null != lic.is_null:
                self.stdout.write(
                    f"License {lic.license_number}: is_null {lic.is_null} → {should_be_null}"
                )
                if not dry_run:
                    lic.is_null = should_be_null
                    fields_to_update.append("is_null")

            # --- Check and update is_expired if expiry date <= today - 30 days
            if lic.license_expiry_date:
                thirty_days_ago = date.today() - timedelta(days=30)
                should_be_expired = lic.license_expiry_date <= thirty_days_ago
                if should_be_expired != lic.is_expired:
                    self.stdout.write(
                        f"License {lic.license_number}: is_expired {lic.is_expired} → {should_be_expired}"
                    )
                    if not dry_run:
                        lic.is_expired = should_be_expired
                        fields_to_update.append("is_expired")

            # Save all updates at once
            if fields_to_update and not dry_run:
                lic.save(update_fields=fields_to_update)

            # --- Optionally recompute related import rows
            if skip_rows:
                continue

            rows = LicenseImportItemsModel.objects.filter(license=lic).only(
                "id",
                "quantity",
                "available_quantity",
                "available_value",
                "cif_fc",
                "debited_quantity",
                "debited_value",
                "allotted_quantity",
                "allotted_value",
            )

            for row in rows.iterator():
                # Debits from BOE
                d_agg = (
                        RowDetails.objects.filter(
                            sr_number=row, transaction_type=DEBIT
                        ).aggregate(qty=Sum("qty"), cif=Sum("cif_fc"))
                        or {}
                )
                debited_qty = d_agg.get("qty") or 0
                debited_val = d_agg.get("cif") or 0

                # Allotments still not attached to a BOE
                a_agg = (
                        AllotmentItems.objects.filter(
                            item=row,
                            allotment__bill_of_entry__bill_of_entry_number__isnull=True,
                        ).aggregate(qty=Sum("qty"), cif=Sum("cif_fc"))
                        or {}
                )
                allotted_qty = a_agg.get("qty") or 0
                allotted_val = a_agg.get("cif") or 0

                # Available quantity
                base_qty = Decimal(str(row.quantity or 0))
                new_avl_qty = base_qty - Decimal(str(debited_qty)) - Decimal(str(allotted_qty))
                if new_avl_qty < 0:
                    new_avl_qty = Decimal("0")

                # Available value → use row-level property (includes restriction logic)
                # This automatically applies:
                # - Head-based restrictions (with 098/2009 OR Conversion exception)
                # - License-level vs item-level calculation priority
                new_avl_val = Decimal(str(row.balance_cif_fc or 0))

                # Only write if something actually changed
                will_change = any(
                    [
                        Decimal(str(row.debited_quantity or 0)) != Decimal(str(debited_qty or 0)),
                        Decimal(str(row.debited_value or 0)) != Decimal(str(debited_val or 0)),
                        Decimal(str(row.allotted_quantity or 0)) != Decimal(str(allotted_qty or 0)),
                        Decimal(str(row.allotted_value or 0)) != Decimal(str(allotted_val or 0)),
                        Decimal(str(row.available_quantity or 0)) != new_avl_qty,
                        Decimal(str(row.available_value or 0)) != new_avl_val,
                    ]
                )

                if will_change:
                    self.stdout.write(
                        f"  Row {row.id}: "
                        f"avail_qty → {new_avl_qty} | avail_val → {new_avl_val} | "
                        f"debited({debited_qty}/{debited_val}) | allotted({allotted_qty}/{allotted_val})"
                    )
                    if not dry_run:
                        LicenseImportItemsModel.objects.filter(pk=row.pk).update(
                            debited_quantity=debited_qty or 0,
                            debited_value=debited_val or 0,
                            allotted_quantity=allotted_qty or 0,
                            allotted_value=allotted_val or 0,
                            available_quantity=new_avl_qty,
                            available_value=new_avl_val,
                        )
                    row_updates += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Done. Licenses updated: {lic_updates} | Rows updated: {row_updates} | dry_run={dry_run}"
            )
        )
