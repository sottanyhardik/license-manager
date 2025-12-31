"""
Management command to link 'Sugar' items to license import items.

Links items where:
- hsn_code starts with '1701' OR
- description contains '1701'

Creates/links ItemNameModel based on license export norm_class:
- E1 -> 'SUGAR - E1'
- E132 -> 'SUGAR - E132'
- etc.

Removes item links from all other license import items.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from license.models import LicenseImportItemsModel
from core.models import ItemNameModel


class Command(BaseCommand):
    help = 'Link "Sugar" item variants based on license norm_class and remove other item links'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes',
        )

    def get_or_create_item(self, name, dry_run=False):
        """Get or create ItemNameModel with the given name."""
        if dry_run:
            try:
                return ItemNameModel.objects.get(name=name), False
            except ItemNameModel.DoesNotExist:
                return None, True
        else:
            return ItemNameModel.objects.get_or_create(name=name)

    def get_norm_class(self, license_item):
        """Get norm_class from license's first export item."""
        if not license_item.license:
            return None

        # Get first export item's norm_class
        first_export = license_item.license.export_license.first()
        if first_export and first_export.norm_class:
            return first_export.norm_class.norm_class
        return None

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write("=" * 80)
        self.stdout.write("🔧 Sugar Item Linking Tool")
        self.stdout.write("=" * 80)

        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️  DRY RUN MODE - No changes will be saved\n"))
        else:
            self.stdout.write(self.style.WARNING("\n⚠️  This will modify item links in the database\n"))

        # Query for license import items matching criteria
        # HSN code starts with '1701' OR description contains '1701'
        sugar_items = LicenseImportItemsModel.objects.filter(
            hs_code__hs_code__startswith='1701'
        ) | LicenseImportItemsModel.objects.filter(
            description__icontains='1701'
        )
        sugar_items = sugar_items.select_related(
            'license', 'hs_code'
        ).prefetch_related(
            'license__export_license__norm_class', 'items'
        ).distinct()

        # Get all other items that have item links
        other_items = LicenseImportItemsModel.objects.exclude(
            id__in=sugar_items.values_list('id', flat=True)
        ).filter(items__isnull=False).distinct()

        sugar_count = sugar_items.count()
        other_count = other_items.count()

        self.stdout.write(f"\n📊 Statistics:")
        self.stdout.write(f"   License items to be linked to Sugar variants: {sugar_count}")
        self.stdout.write(f"   License items to have item links removed: {other_count}")
        self.stdout.write(f"   Total license items to be modified: {sugar_count + other_count}\n")

        if sugar_count == 0 and other_count == 0:
            self.stdout.write(self.style.WARNING("No items to update."))
            return

        # Count by license norm_class
        if sugar_count > 0:
            self.stdout.write("\n📋 Breakdown by license export norm_class:")
            norm_counts = {}
            for item in sugar_items:
                norm = self.get_norm_class(item)
                norm = norm or 'No Norm'
                norm_counts[norm] = norm_counts.get(norm, 0) + 1

            for norm, count in sorted(norm_counts.items()):
                new_name = f'SUGAR - {norm}' if norm != 'No Norm' else 'SUGAR'
                self.stdout.write(f"   • {norm}: {count} items → '{new_name}'")

        # Show sample items
        if sugar_count > 0:
            self.stdout.write("\n📝 Sample items to be linked (first 10):")
            for item in sugar_items[:10]:
                norm = self.get_norm_class(item)
                norm = norm or 'No Norm'
                new_name = f'SUGAR - {norm}' if norm != 'No Norm' else 'SUGAR'
                current_items = ', '.join([i.name for i in item.items.all()]) or 'None'
                self.stdout.write(
                    f"   • License: {item.license.license_number if item.license else 'N/A'}, "
                    f"Serial: {item.serial_number}, "
                    f"HSN: {item.hs_code.hs_code if item.hs_code else 'N/A'}, "
                    f"Norm: {norm}, "
                    f"Current: [{current_items}] → New: [{new_name}]"
                )

        if other_count > 0:
            self.stdout.write("\n🗑️  Sample items to have links removed (first 10):")
            for item in other_items[:10]:
                current_items = ', '.join([i.name for i in item.items.all()])
                self.stdout.write(
                    f"   • License: {item.license.license_number if item.license else 'N/A'}, "
                    f"Serial: {item.serial_number}, "
                    f"HSN: {item.hs_code.hs_code if item.hs_code else 'N/A'}, "
                    f"Current items: [{current_items}]"
                )

        if not dry_run:
            self.stdout.write("\n" + "=" * 80)
            confirm = input("⚠️  Proceed with updates? Type 'yes' to confirm: ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return

        # Perform updates
        try:
            with transaction.atomic():
                # Track created items
                created_items = set()

                # Update sugar items
                sugar_updated = 0
                if sugar_count > 0:
                    self.stdout.write(f"\n🔄 Linking {sugar_count} items to Sugar variants...")
                    for item in sugar_items:
                        norm = self.get_norm_class(item)
                        if norm:
                            item_name = f'SUGAR - {norm}'
                        else:
                            item_name = 'SUGAR'

                        # Get or create the ItemNameModel
                        item_obj, created = self.get_or_create_item(item_name, dry_run)

                        if created and not dry_run:
                            created_items.add(item_name)

                        if not dry_run and item_obj:
                            # Clear existing items and add new one
                            item.items.clear()
                            item.items.add(item_obj)

                        sugar_updated += 1

                        # Progress indicator
                        if sugar_updated % 100 == 0:
                            self.stdout.write(f"   Processed {sugar_updated}/{sugar_count} items...")

                # Clear item links for other items
                other_updated = 0
                if other_count > 0:
                    self.stdout.write(f"🔄 Removing item links from {other_count} items...")
                    for item in other_items:
                        if not dry_run:
                            item.items.clear()
                        other_updated += 1

                        if other_updated % 100 == 0:
                            self.stdout.write(f"   Processed {other_updated}/{other_count} items...")

                if dry_run:
                    self.stdout.write(self.style.WARNING("\n✓ DRY RUN - No changes were made"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"\n✅ Successfully updated {sugar_updated + other_updated} items!"))

                self.stdout.write(f"\n📊 Final Results:")
                self.stdout.write(f"   License items linked to Sugar variants: {sugar_updated}")
                self.stdout.write(f"   License items with links removed: {other_updated}")
                if created_items:
                    self.stdout.write(f"   New ItemNameModel entries created: {len(created_items)}")
                    for name in sorted(created_items):
                        self.stdout.write(f"      - {name}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Error updating items: {str(e)}"))
            import traceback
            traceback.print_exc()
            raise

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("✅ Operation completed!")
        self.stdout.write("=" * 80 + "\n")
