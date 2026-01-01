# license/management/commands/populate_license_items.py
from django.core.management.base import BaseCommand

from core.models import ItemNameModel, SionNormClassModel
from license.models import LicenseImportItemsModel
from license.utils.item_matcher import get_item_filters


class Command(BaseCommand):
    help = "Populate items (ManyToMany) in LicenseImportItemsModel based on description and HS code filters - with norm-specific items"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write any changes; just report what would be updated.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear all existing items before populating.",
        )

    def get_item_definitions(self):
        """
        Returns list of item definitions with base name, norms list, and description/hs filters
        Each item will be created separately for each norm (e.g., 'SUGAR - E1', 'SUGAR - E5')
        Uses the shared item_matcher utility for consistency.
        """
        return get_item_filters()

    def handle(self, *args, **opts):
        dry_run = bool(opts.get("dry_run"))
        clear_existing = bool(opts.get("clear"))

        self.stdout.write("=" * 80)
        self.stdout.write("Populating items in LicenseImportItemsModel (Norm-Specific)")
        self.stdout.write("=" * 80)
        self.stdout.write(f"Dry run: {dry_run}")
        self.stdout.write(f"Clear existing: {clear_existing}")
        self.stdout.write("")

        # Clear existing items
        self.stdout.write("Step 1: Clearing all existing item associations...")
        if not dry_run:
            total_cleared = 0
            for import_item in LicenseImportItemsModel.objects.all():
                item_count = import_item.items.count()
                import_item.items.clear()
                total_cleared += item_count
            self.stdout.write(self.style.SUCCESS(f"✓ Cleared {total_cleared} item associations"))
        else:
            total_items = sum(import_item.items.count() for import_item in LicenseImportItemsModel.objects.all())
            self.stdout.write(self.style.WARNING(f"Would clear {total_items} item associations (dry-run)"))
        self.stdout.write("")

        # Generate norm-specific items
        self.stdout.write("Step 2: Creating norm-specific item names...")
        item_definitions = self.get_item_definitions()
        items_to_create = []

        for definition in item_definitions:
            base_name = definition['base_name']
            norms = definition['norms']

            for norm in norms:
                # Always create norm-specific item name with suffix
                item_name = f"{base_name} - {norm}"

                items_to_create.append({
                    'name': item_name,
                    'base_name': base_name,
                    'norm': norm,
                    'filters': definition['filters']
                })

        created_count = 0
        existing_count = 0
        updated_count = 0

        for item_data in items_to_create:
            item_name = item_data['name']
            norm = item_data['norm']

            if not dry_run:
                # Get or create the item
                item, created = ItemNameModel.objects.get_or_create(name=item_name)

                # Set sion_norm_class for all items
                try:
                    norm_class_obj = SionNormClassModel.objects.get(norm_class=norm)
                    if item.sion_norm_class != norm_class_obj:
                        item.sion_norm_class = norm_class_obj
                        item.save(update_fields=['sion_norm_class'])
                        updated_count += 1
                except SionNormClassModel.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"  ! Norm class '{norm}' not found in database for {item_name}"))

                if created:
                    created_count += 1
                    self.stdout.write(f"  + Created: {item_name} (norm: {norm})")
                else:
                    existing_count += 1
            else:
                if ItemNameModel.objects.filter(name=item_name).exists():
                    existing_count += 1
                else:
                    created_count += 1
                    self.stdout.write(f"  + Would create: {item_name} (norm: {norm})")

        self.stdout.write(self.style.SUCCESS(
            f"✓ Created {created_count} new items, {existing_count} already exist, "
            f"{updated_count} norm classes updated"
        ))
        self.stdout.write("")

        # Populate item associations
        self.stdout.write("Step 3: Populating norm-specific item associations...")
        total_filters = len(items_to_create)
        total_matched = 0
        total_updated = 0

        for idx, item_data in enumerate(items_to_create, 1):
            item_name = item_data['name']
            norm = item_data['norm']
            filters = item_data['filters']

            try:
                # Get the item
                item = ItemNameModel.objects.get(name=item_name)

                # Build query: description/hs filters AND norm filter
                # All items are norm-specific now
                combined_filter = Q(license__export_license__norm_class__norm_class=norm)
                for f in filters:
                    combined_filter &= f

                # Find matching import items
                matching_imports = LicenseImportItemsModel.objects.filter(combined_filter)
                match_count = matching_imports.count()

                if match_count > 0:
                    self.stdout.write(
                        f"  [{idx}/{total_filters}] {item_name}: {match_count} import items matched"
                    )

                    if not dry_run:
                        # Add item to each matching import item (ManyToMany)
                        for import_item in matching_imports:
                            import_item.items.add(item)

                    total_matched += match_count
                    total_updated += 1

            except ItemNameModel.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"  [{idx}/{total_filters}] Item '{item_name}' not found in database - skipping")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  [{idx}/{total_filters}] Error processing '{item_name}': {str(e)}")
                )

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Norm-Specific Migration Complete!\n"
                f"   - Processed {total_filters} norm-specific filter definitions\n"
                f"   - Updated {total_updated} item types\n"
                f"   - Matched {total_matched} import items\n"
                f"   - Dry run: {dry_run}"
            )
        )
        self.stdout.write("=" * 80)
