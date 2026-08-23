# license/management/commands/populate_license_items.py
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.models import LicenseImportItemsModel
from apps.license.utils.item_matcher import get_item_filters


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
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of matching import-item links to insert per batch (default: 1000).",
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
        batch_size = int(opts.get("batch_size") or 0)

        if batch_size < 1:
            raise CommandError("Batch size must be greater than zero")

        self.stdout.write("=" * 80)
        self.stdout.write("Populating items in LicenseImportItemsModel (Norm-Specific)")
        self.stdout.write("=" * 80)
        self.stdout.write(f"Dry run: {dry_run}")
        self.stdout.write(f"Clear existing: {clear_existing}")
        self.stdout.write(f"Batch size: {batch_size}")
        self.stdout.write("")

        with transaction.atomic():
            self._clear_existing_links(dry_run=dry_run, clear_existing=clear_existing)

            # Generate norm-specific items
            self.stdout.write("Step 2: Creating norm-specific item names...")
            item_definitions = self.get_item_definitions()
            items_to_create = self._build_items_to_create(item_definitions)
            created_count, existing_count, updated_count = self._ensure_item_names(
                items_to_create,
                dry_run=dry_run,
            )

            self.stdout.write(self.style.SUCCESS(
                f"✓ Created {created_count} new items, {existing_count} already exist, "
                f"{updated_count} norm classes updated"
            ))
            self.stdout.write("")

            # Populate item associations
            self.stdout.write("Step 3: Populating norm-specific item associations...")
            total_filters, total_matched, total_updated = self._populate_associations(
                items_to_create,
                dry_run=dry_run,
                batch_size=batch_size,
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

    def _clear_existing_links(self, *, dry_run, clear_existing):
        self.stdout.write("Step 1: Clearing existing item associations...")
        through_model = LicenseImportItemsModel.items.through
        total_links = through_model.objects.count()

        if not clear_existing:
            self.stdout.write(self.style.WARNING("Skipping clear; pass --clear to rebuild all links."))
        elif dry_run:
            self.stdout.write(self.style.WARNING(f"Would clear {total_links} item associations (dry-run)"))
        else:
            through_model.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"✓ Cleared {total_links} item associations"))
        self.stdout.write("")

    def _build_items_to_create(self, item_definitions):
        items_to_create = []
        for definition in item_definitions:
            base_name = (definition.get('base_name') or '').strip()
            norms = definition.get('norms') or []
            filters = definition.get('filters') or []

            if not base_name:
                raise CommandError("Item definition has a blank base_name")
            if not norms:
                raise CommandError(f"Item definition {base_name!r} has no norms")
            if not filters:
                raise CommandError(f"Item definition {base_name!r} has no filters")
            if not all(isinstance(filter_item, Q) for filter_item in filters):
                raise CommandError(f"Item definition {base_name!r} contains a non-Q filter")

            for norm in norms:
                norm = (norm or '').strip()
                if not norm:
                    raise CommandError(f"Item definition {base_name!r} contains a blank norm")
                items_to_create.append({
                    'name': f"{base_name} - {norm}",
                    'base_name': base_name,
                    'norm': norm,
                    'filters': filters,
                    'is_active': definition.get('is_active', True),
                })
        return items_to_create

    def _ensure_item_names(self, items_to_create, *, dry_run):
        created_count = 0
        existing_count = 0
        updated_count = 0
        norms_by_code = {
            norm.norm_class: norm
            for norm in SionNormClassModel.objects.filter(
                norm_class__in={item_data['norm'] for item_data in items_to_create}
            )
        }

        for item_data in items_to_create:
            item_name = item_data['name']
            norm = item_data['norm']
            is_active = item_data.get('is_active', True)

            if dry_run:
                if ItemNameModel.objects.filter(name=item_name).exists():
                    existing_count += 1
                else:
                    created_count += 1
                    self.stdout.write(f"  + Would create: {item_name} (norm: {norm})")
                continue

            item, created = ItemNameModel.objects.get_or_create(name=item_name)
            update_fields = []
            norm_class_obj = norms_by_code.get(norm)
            if norm_class_obj is None:
                self.stdout.write(
                    self.style.WARNING(f"  ! Norm class '{norm}' not found in database for {item_name}")
                )
            elif item.sion_norm_class_id != norm_class_obj.id:
                item.sion_norm_class = norm_class_obj
                update_fields.append('sion_norm_class')

            if item.is_active != is_active:
                item.is_active = is_active
                update_fields.append('is_active')

            if update_fields:
                item.save(update_fields=update_fields)
                updated_count += 1

            if created:
                created_count += 1
                self.stdout.write(f"  + Created: {item_name} (norm: {norm}, is_active: {is_active})")
            else:
                existing_count += 1
        return created_count, existing_count, updated_count

    def _populate_associations(self, items_to_create, *, dry_run, batch_size):
        total_filters = len(items_to_create)
        total_matched = 0
        total_updated = 0

        for idx, item_data in enumerate(items_to_create, 1):
            item_name = item_data['name']
            norm = item_data['norm']
            filters = item_data['filters']

            try:
                item = ItemNameModel.objects.get(name=item_name)
                combined_filter = Q(license__export_license__norm_class__norm_class=norm)
                for filter_item in filters:
                    combined_filter &= filter_item

                matching_imports = LicenseImportItemsModel.objects.filter(combined_filter).distinct()
                match_count = matching_imports.count()

                if match_count > 0:
                    self.stdout.write(
                        f"  [{idx}/{total_filters}] {item_name}: {match_count} import items matched"
                    )

                    if not dry_run:
                        self._bulk_add_item_links(matching_imports, item, batch_size=batch_size)

                    total_matched += match_count
                    total_updated += 1

            except ItemNameModel.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"  [{idx}/{total_filters}] Item '{item_name}' not found in database - skipping")
                )
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(f"  [{idx}/{total_filters}] Error processing '{item_name}': {exc}")
                )
                raise
        return total_filters, total_matched, total_updated

    @staticmethod
    def _bulk_add_item_links(matching_imports, item, *, batch_size):
        through_model = LicenseImportItemsModel.items.through
        source_field = through_model._meta.get_field("licenseimportitemsmodel")
        target_field = through_model._meta.get_field("itemnamemodel")
        batch = []

        for import_item_id in matching_imports.values_list('id', flat=True).iterator(chunk_size=batch_size):
            batch.append(through_model(**{
                f"{source_field.name}_id": import_item_id,
                f"{target_field.name}_id": item.id,
            }))
            if len(batch) >= batch_size:
                through_model.objects.bulk_create(batch, ignore_conflicts=True)
                batch.clear()

        if batch:
            through_model.objects.bulk_create(batch, ignore_conflicts=True)
