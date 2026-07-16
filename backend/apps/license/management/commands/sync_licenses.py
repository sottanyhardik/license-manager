# license/management/commands/sync_licenses.py
"""
Unified command to sync all license data across the database.
Combines functionality from:
- update_license_expiry.py
- update_balance_cif.py
- populate_license_items.py
- update_restriction_balances.py

This ensures all licenses have accurate:
- balance_cif (calculated from exports/imports/allotments/BOE)
- is_expired flag (based on expiry date)
- is_null flag (based on balance < threshold)
- linked items (ItemNameModel relationships)
- import item balance fields (available_quantity, available_value, etc.)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails
from apps.core.constants import DEBIT
from apps.license.models import (
    LicenseBalance,
    LicenseDetailsModel,
    LicenseFlags,
    LicenseImportItemsModel,
)

MONEY_PLACES = Decimal("0.01")
NULL_BALANCE_THRESHOLD = Decimal("500")


def _quantize_money(value):
    return Decimal(str(value or 0)).quantize(MONEY_PLACES)


def _validate_batch_size(value):
    if value < 1:
        raise CommandError("--batch-size must be greater than zero.")


def _normalize_license_number(value):
    if value is None:
        return None

    license_number = value.strip()
    if not license_number:
        raise CommandError("--license must not be blank.")
    return license_number


class Command(BaseCommand):
    help = (
        "Unified command to sync all license data: balance_cif, flags, items, "
        "and import item balances for all licenses in the database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--license",
            dest="license_number",
            help="Limit to a specific license_number (exact match).",
        )
        parser.add_argument(
            "--no-items",
            action="store_true",
            help="Skip import item balance recalculation.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write any changes; just report what would be updated.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of licenses to process in each batch (default: 100).",
        )

    def handle(self, *args, **opts):
        license_number = _normalize_license_number(opts.get("license_number"))
        skip_items = bool(opts.get("no_items"))
        dry_run = bool(opts.get("dry_run"))
        batch_size = opts.get("batch_size")
        _validate_batch_size(batch_size)

        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write(self.style.WARNING("LICENSE SYNC COMMAND"))
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write("")

        # Get queryset
        qs = LicenseDetailsModel.objects.all()
        if license_number:
            qs = qs.filter(license_number=license_number)
            self.stdout.write(f"Processing single license: {license_number}")
        else:
            self.stdout.write("Processing ALL licenses in database")

        qs = qs.select_related("balance", "flags").order_by("id")
        total_count = qs.count()
        self.stdout.write(f"Total licenses to process: {total_count}")
        self.stdout.write(f"Batch size: {batch_size}")
        self.stdout.write(f"Dry run: {dry_run}")
        self.stdout.write("")

        # Counters
        stats = {
            'licenses_processed': 0,
            'balance_updated': 0,
            'is_null_updated': 0,
            'is_expired_updated': 0,
            'import_items_updated': 0,
            'errors': 0,
        }

        # Process in batches
        batch_num = 0
        for i in range(0, total_count, batch_size):
            batch_num += 1
            batch_qs = qs[i : i + batch_size]

            self.stdout.write(
                self.style.HTTP_INFO(
                    f"\n[Batch {batch_num}/{(total_count + batch_size - 1) // batch_size}] "
                    f"Processing licenses {i + 1} to {min(i + batch_size, total_count)}..."
                )
            )

            for lic in batch_qs:
                with transaction.atomic():
                    self._process_license(lic, stats, skip_items, dry_run)

        # Final summary
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write(self.style.SUCCESS("✅ SYNC COMPLETE"))
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write(f"Total licenses processed: {stats['licenses_processed']}")
        self.stdout.write(f"  - balance_cif updated: {stats['balance_updated']}")
        self.stdout.write(f"  - is_null updated: {stats['is_null_updated']}")
        self.stdout.write(f"  - is_expired updated: {stats['is_expired_updated']}")
        self.stdout.write(f"  - import items updated: {stats['import_items_updated']}")
        self.stdout.write(f"  - errors: {stats['errors']}")
        self.stdout.write("")
        if stats["errors"]:
            raise CommandError(f"License sync completed with {stats['errors']} error(s).")
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  DRY RUN - No changes were saved"))
        else:
            self.stdout.write(self.style.SUCCESS("💾 All changes saved to database"))

    def _process_license(self, lic, stats, skip_items, dry_run):
        """Process a single license: update flags, balance, and items"""
        stats['licenses_processed'] += 1

        # 1. Update balance_cif from authoritative property
        try:
            actual_balance = lic.get_balance_cif
            balance_row, _ = LicenseBalance.objects.get_or_create(license=lic)
            flags_row, _ = LicenseFlags.objects.get_or_create(license=lic)
            current_balance = balance_row.balance_cif or Decimal("0")

            # Compare at 2 decimals to avoid micro-diffs
            want = _quantize_money(actual_balance)
            have = _quantize_money(current_balance)

            if want != have:
                if stats['balance_updated'] < 10:  # Only log first 10
                    self.stdout.write(
                        f"  {lic.license_number}: balance_cif {have} → {want}"
                    )
                if not dry_run:
                    balance_row.balance_cif = want
                    balance_row.save(update_fields=["balance_cif"])
                stats['balance_updated'] += 1
        except Exception as e:
            stats['errors'] += 1
            self.stdout.write(
                self.style.ERROR(f"  ERROR calculating balance for {lic.license_number}: {e}")
            )
            return

        # 2. Update is_null flag (balance < $500 threshold)
        # BUSINESS RULE: Null DFIA = balance < $500
        should_be_null = want < NULL_BALANCE_THRESHOLD
        if should_be_null != flags_row.is_null:
            if stats['is_null_updated'] < 10:  # Only log first 10
                self.stdout.write(
                    f"  {lic.license_number}: is_null {flags_row.is_null} → {should_be_null}"
                )
            if not dry_run:
                flags_row.is_null = should_be_null
                flags_row.save(update_fields=["is_null"])
            stats['is_null_updated'] += 1

        # 3. Update is_expired flag (expiry date < today)
        if lic.license_expiry_date:
            today = date.today()
            should_be_expired = lic.license_expiry_date < today
            if should_be_expired != flags_row.is_expired:
                if stats['is_expired_updated'] < 10:  # Only log first 10
                    self.stdout.write(
                        f"  {lic.license_number}: is_expired {flags_row.is_expired} → {should_be_expired}"
                    )
                if not dry_run:
                    flags_row.is_expired = should_be_expired
                    flags_row.save(update_fields=["is_expired"])
                stats['is_expired_updated'] += 1

        # 4. Update import item balances (if not skipped)
        if not skip_items:
            self._update_import_items(lic, stats, dry_run)

    def _update_import_items(self, lic, stats, dry_run):
        """Update balance fields for all import items of a license"""
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

        for row in rows:
            # Calculate debits from BOE
            d_agg = (
                RowDetails.objects.filter(
                    sr_number=row, transaction_type=DEBIT
                ).aggregate(qty=Sum("qty"), cif=Sum("cif_fc"))
                or {}
            )
            debited_qty = d_agg.get("qty") or 0
            debited_val = d_agg.get("cif") or 0

            # Calculate allotments (not yet attached to BOE)
            a_agg = (
                AllotmentItems.objects.filter(
                    item=row,
                    allotment__bill_of_entry__isnull=True,
                ).aggregate(qty=Sum("qty"), cif=Sum("cif_fc"))
                or {}
            )
            allotted_qty = a_agg.get("qty") or 0
            allotted_val = a_agg.get("cif") or 0

            # Calculate available quantity
            base_qty = Decimal(str(row.quantity or 0))
            new_avl_qty = base_qty - Decimal(str(debited_qty)) - Decimal(str(allotted_qty))
            if new_avl_qty < 0:
                new_avl_qty = Decimal("0")

            # Calculate available value (from property)
            calculated_avl_val = Decimal(str(row.balance_cif_fc or 0))

            # Check for restrictions
            has_restriction = row.items.filter(
                sion_norm_class__isnull=False,
                restriction_percentage__gt=Decimal("0")
            ).exists()

            if has_restriction and row.available_value is not None and row.available_value > 0:
                new_avl_val = Decimal(str(row.available_value))
            else:
                new_avl_val = calculated_avl_val

            # Check if update needed
            will_change = any([
                Decimal(str(row.debited_quantity or 0)) != Decimal(str(debited_qty or 0)),
                Decimal(str(row.debited_value or 0)) != Decimal(str(debited_val or 0)),
                Decimal(str(row.allotted_quantity or 0)) != Decimal(str(allotted_qty or 0)),
                Decimal(str(row.allotted_value or 0)) != Decimal(str(allotted_val or 0)),
                Decimal(str(row.available_quantity or 0)) != new_avl_qty,
                Decimal(str(row.available_value or 0)) != new_avl_val,
            ])

            if will_change:
                if not dry_run:
                    LicenseImportItemsModel.objects.filter(pk=row.pk).update(
                        debited_quantity=debited_qty or 0,
                        debited_value=debited_val or 0,
                        allotted_quantity=allotted_qty or 0,
                        allotted_value=allotted_val or 0,
                        available_quantity=new_avl_qty,
                        available_value=new_avl_val,
                    )
                stats['import_items_updated'] += 1
