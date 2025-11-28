# license/management/commands/import_item_names.py
from django.core.management.base import BaseCommand
from django.db.models import Q
from license.models import LicenseImportItemsModel
from core.models import ItemNameModel
import csv


class Command(BaseCommand):
    help = "Import item name mappings from CSV file and update LicenseImportItemsModel"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Path to CSV file with item name mappings",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without actually updating",
        )
        parser.add_argument(
            "--create-items",
            action="store_true",
            help="Automatically create ItemNameModel entries if they don't exist",
        )

    def handle(self, *args, **opts):
        csv_file = opts.get("csv_file")
        dry_run = opts.get("dry_run")
        create_items = opts.get("create_items")

        self.stdout.write("=" * 80)
        self.stdout.write("Importing Item Name Mappings")
        self.stdout.write("=" * 80)
        self.stdout.write(f"CSV file: {csv_file}")
        self.stdout.write(f"Dry run: {dry_run}")
        self.stdout.write(f"Create items: {create_items}")
        self.stdout.write("")

        # Read CSV file
        mappings = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip rows without suggested item name
                if not row.get('suggested_item_name', '').strip():
                    continue

                mappings.append({
                    'description': row.get('description', '').strip(),
                    'hs_code': row.get('hs_code', '').strip(),
                    'norms': row.get('norms', '').strip(),
                    'item_name': row.get('suggested_item_name', '').strip(),
                })

        self.stdout.write(f"Found {len(mappings)} mappings in CSV")
        self.stdout.write("")

        # Process mappings
        stats = {
            'items_created': 0,
            'items_found': 0,
            'items_not_found': 0,
            'import_items_updated': 0,
            'import_items_matched': 0,
            'errors': [],
        }

        self.stdout.write("Processing mappings...")
        for idx, mapping in enumerate(mappings, 1):
            self.stdout.write(f"  [{idx}/{len(mappings)}] Processing: {mapping['item_name'][:50]}...", ending='\r')

            # Get or create ItemNameModel
            try:
                item_name_obj = ItemNameModel.objects.get(name=mapping['item_name'])
                stats['items_found'] += 1
            except ItemNameModel.DoesNotExist:
                if create_items:
                    if not dry_run:
                        item_name_obj = ItemNameModel.objects.create(name=mapping['item_name'])
                        stats['items_created'] += 1
                        self.stdout.write(f"\n  + Created: {mapping['item_name']}")
                    else:
                        self.stdout.write(f"\n  + Would create: {mapping['item_name']}")
                        stats['items_created'] += 1
                        continue
                else:
                    stats['items_not_found'] += 1
                    stats['errors'].append(f"Item not found: {mapping['item_name']}")
                    continue

            # Build query to find matching import items
            query = Q()

            # Match by description (case-insensitive contains)
            if mapping['description']:
                query &= Q(description__icontains=mapping['description'])

            # Match by HS code
            if mapping['hs_code']:
                query &= Q(hs_code__hs_code__startswith=mapping['hs_code'][:6])  # Match first 6 digits

            # Match by norms
            if mapping['norms']:
                norms_list = [n.strip() for n in mapping['norms'].split(',')]
                for norm in norms_list:
                    if norm:
                        query &= Q(license__export_license__norm_class__norm_class=norm)

            # Find matching import items
            if query:
                matching_imports = LicenseImportItemsModel.objects.filter(query).distinct()
                match_count = matching_imports.count()
                stats['import_items_matched'] += match_count

                if match_count > 0:
                    # Update import items
                    if not dry_run:
                        for import_item in matching_imports:
                            import_item.items.add(item_name_obj)
                        stats['import_items_updated'] += match_count
                    else:
                        stats['import_items_updated'] += match_count

        self.stdout.write(f"  [{len(mappings)}/{len(mappings)}] Processing complete")
        self.stdout.write("")

        # Print statistics
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ Import Complete"))
        self.stdout.write("=" * 80)
        self.stdout.write("")
        self.stdout.write("Statistics:")
        self.stdout.write(f"  Total mappings processed: {len(mappings)}")
        self.stdout.write(f"  Items found: {stats['items_found']}")
        self.stdout.write(f"  Items created: {stats['items_created']}")
        self.stdout.write(f"  Items not found: {stats['items_not_found']}")
        self.stdout.write(f"  Import items matched: {stats['import_items_matched']}")
        self.stdout.write(f"  Import items updated: {stats['import_items_updated']}")

        if stats['errors']:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(f"⚠️  {len(stats['errors'])} errors:"))
            for error in stats['errors'][:10]:  # Show first 10
                self.stdout.write(f"  - {error}")
            if len(stats['errors']) > 10:
                self.stdout.write(f"  ... and {len(stats['errors']) - 10} more")

        if dry_run:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("DRY RUN - No changes were made"))
            self.stdout.write("Run without --dry-run to apply changes")

        self.stdout.write("")
