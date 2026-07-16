"""Shared management-command workflow for commodity item linking."""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import ItemNameModel
from apps.license.models import LicenseImportItemsModel

logger = logging.getLogger(__name__)


class CommodityItemLinkCommand(BaseCommand):
    """Link import items matching an HSN marker to norm-specific ItemName rows."""

    commodity_label: str
    hsn_marker: str
    item_prefix: str

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making actual changes",
        )

    def get_or_create_item(self, name, dry_run=False):
        """Get or create ItemNameModel with the given name."""
        if dry_run:
            try:
                return ItemNameModel.objects.get(name=name), False
            except ItemNameModel.DoesNotExist:
                return None, True
        return ItemNameModel.objects.get_or_create(name=name)

    def get_norm_class(self, license_item):
        """Get norm_class from license's first export item."""
        if not license_item.license:
            return None

        export_items = list(license_item.license.export_license.all())
        first_export = export_items[0] if export_items else None
        if first_export and first_export.norm_class:
            return first_export.norm_class.norm_class
        return None

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        self.stdout.write("=" * 80)
        self.stdout.write(f"🔧 {self.commodity_label} Item Linking Tool")
        self.stdout.write("=" * 80)

        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️  DRY RUN MODE - No changes will be saved\n"))
        else:
            self.stdout.write(self.style.WARNING("\n⚠️  This will modify item links in the database\n"))

        matching_items = self._matching_items()
        other_items = (
            LicenseImportItemsModel.objects.exclude(id__in=matching_items.values_list("id", flat=True))
            .filter(items__isnull=False)
            .select_related("license", "hs_code")
            .prefetch_related("items")
            .distinct()
        )

        matching_count = matching_items.count()
        other_count = other_items.count()

        self.stdout.write("\n📊 Statistics:")
        self.stdout.write(f"   License items to be linked to {self.commodity_label} variants: {matching_count}")
        self.stdout.write(f"   License items to have item links removed: {other_count}")
        self.stdout.write(f"   Total license items to be modified: {matching_count + other_count}\n")

        if matching_count == 0 and other_count == 0:
            self.stdout.write(self.style.WARNING("No items to update."))
            return

        self._print_breakdown(matching_items, matching_count)
        self._print_matching_samples(matching_items, matching_count)
        self._print_other_samples(other_items, other_count)

        if not dry_run:
            self.stdout.write("\n" + "=" * 80)
            confirm = input("⚠️  Proceed with updates? Type 'yes' to confirm: ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return

        try:
            linked_count, cleared_count, created_items = self._apply_updates(
                matching_items,
                matching_count,
                other_items,
                other_count,
                dry_run,
            )
        except Exception:
            logger.exception("Error updating %s item links", self.commodity_label)
            self.stdout.write(self.style.ERROR(f"\n❌ Error updating {self.commodity_label} items"))
            raise

        self._print_final_results(linked_count, cleared_count, created_items, dry_run)

    def _matching_items(self):
        return (
            (
                LicenseImportItemsModel.objects.filter(hs_code__hs_code__startswith=self.hsn_marker)
                | LicenseImportItemsModel.objects.filter(description__icontains=self.hsn_marker)
            )
            .select_related("license", "hs_code")
            .prefetch_related("license__export_license__norm_class", "items")
            .distinct()
        )

    def _item_name_for_norm(self, norm):
        return f"{self.item_prefix} - {norm}" if norm != "No Norm" else self.item_prefix

    def _print_breakdown(self, matching_items, matching_count):
        if matching_count <= 0:
            return

        self.stdout.write("\n📋 Breakdown by license export norm_class:")
        norm_counts = {}
        for item in matching_items:
            norm = self.get_norm_class(item) or "No Norm"
            norm_counts[norm] = norm_counts.get(norm, 0) + 1

        for norm, count in sorted(norm_counts.items()):
            self.stdout.write(f"   • {norm}: {count} items → '{self._item_name_for_norm(norm)}'")

    def _print_matching_samples(self, matching_items, matching_count):
        if matching_count <= 0:
            return

        self.stdout.write("\n📝 Sample items to be linked (first 10):")
        for item in matching_items[:10]:
            norm = self.get_norm_class(item) or "No Norm"
            current_items = ", ".join([item_name.name for item_name in item.items.all()]) or "None"
            self.stdout.write(
                f"   • License: {item.license.license_number if item.license else 'N/A'}, "
                f"Serial: {item.serial_number}, "
                f"HSN: {item.hs_code.hs_code if item.hs_code else 'N/A'}, "
                f"Norm: {norm}, "
                f"Current: [{current_items}] → New: [{self._item_name_for_norm(norm)}]"
            )

    def _print_other_samples(self, other_items, other_count):
        if other_count <= 0:
            return

        self.stdout.write("\n🗑️  Sample items to have links removed (first 10):")
        for item in other_items[:10]:
            current_items = ", ".join([item_name.name for item_name in item.items.all()])
            self.stdout.write(
                f"   • License: {item.license.license_number if item.license else 'N/A'}, "
                f"Serial: {item.serial_number}, "
                f"HSN: {item.hs_code.hs_code if item.hs_code else 'N/A'}, "
                f"Current items: [{current_items}]"
            )

    def _apply_updates(self, matching_items, matching_count, other_items, other_count, dry_run):
        with transaction.atomic():
            created_items = set()
            linked_count = 0

            if matching_count > 0:
                self.stdout.write(f"\n🔄 Linking {matching_count} items to {self.commodity_label} variants...")
                for item in matching_items:
                    norm = self.get_norm_class(item)
                    item_name = f"{self.item_prefix} - {norm}" if norm else self.item_prefix
                    item_obj, created = self.get_or_create_item(item_name, dry_run)

                    if created and not dry_run:
                        created_items.add(item_name)

                    if not dry_run and item_obj:
                        item.items.clear()
                        item.items.add(item_obj)

                    linked_count += 1
                    if linked_count % 100 == 0:
                        self.stdout.write(f"   Processed {linked_count}/{matching_count} items...")

            cleared_count = 0
            if other_count > 0:
                self.stdout.write(f"🔄 Removing item links from {other_count} items...")
                for item in other_items:
                    if not dry_run:
                        item.items.clear()
                    cleared_count += 1

                    if cleared_count % 100 == 0:
                        self.stdout.write(f"   Processed {cleared_count}/{other_count} items...")

            return linked_count, cleared_count, created_items

    def _print_final_results(self, linked_count, cleared_count, created_items, dry_run):
        if dry_run:
            self.stdout.write(self.style.WARNING("\n✓ DRY RUN - No changes were made"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Successfully updated {linked_count + cleared_count} items!"))

        self.stdout.write("\n📊 Final Results:")
        self.stdout.write(f"   License items linked to {self.commodity_label} variants: {linked_count}")
        self.stdout.write(f"   License items with links removed: {cleared_count}")
        if created_items:
            self.stdout.write(f"   New ItemNameModel entries created: {len(created_items)}")
            for name in sorted(created_items):
                self.stdout.write(f"      - {name}")

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("✅ Operation completed!")
        self.stdout.write("=" * 80 + "\n")
