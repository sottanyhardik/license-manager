# license/management/commands/export_import_items.py
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from license.models import LicenseImportItemsModel
import csv
from datetime import datetime


class Command(BaseCommand):
    help = "Export all LicenseImportItemsModel data with descriptions, HSN codes, and norms for item name mapping"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Output file path (default: import_items_export_YYYYMMDD_HHMMSS.csv)",
        )
        parser.add_argument(
            "--unique",
            action="store_true",
            help="Export only unique combinations of description + HSN + norm",
        )
        parser.add_argument(
            "--with-count",
            action="store_true",
            help="Include count of occurrences for unique combinations",
        )

    def handle(self, *args, **opts):
        output_file = opts.get("output")
        unique_only = opts.get("unique")
        with_count = opts.get("with_count")

        # Generate default filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"import_items_export_{timestamp}.csv"

        self.stdout.write("=" * 80)
        self.stdout.write("Exporting LicenseImportItemsModel Data")
        self.stdout.write("=" * 80)
        self.stdout.write(f"Output file: {output_file}")
        self.stdout.write(f"Unique only: {unique_only}")
        self.stdout.write(f"With count: {with_count}")
        self.stdout.write("")

        # Get all import items with related data
        import_items = (
            LicenseImportItemsModel.objects
            .select_related('license', 'hs_code')
            .prefetch_related('license__export_license__norm_class', 'items')
            .all()
        )

        total_count = import_items.count()
        self.stdout.write(f"Total import items: {total_count}")
        self.stdout.write("")

        # Collect data
        data_rows = []
        seen_combinations = {}  # For unique tracking

        self.stdout.write("Processing import items...")
        for idx, import_item in enumerate(import_items, 1):
            if idx % 100 == 0:
                self.stdout.write(f"  Processed {idx}/{total_count}...", ending='\r')

            # Get basic fields
            description = import_item.description or ""
            hs_code = import_item.hs_code.hs_code if import_item.hs_code else ""
            quantity = float(import_item.quantity or 0)
            cif_value = float(import_item.cif_fc or 0)

            # Get license info
            license_number = import_item.license.license_number if import_item.license else ""
            exporter = str(import_item.license.exporter) if import_item.license and import_item.license.exporter else ""

            # Get all norms for this license
            norms = []
            if import_item.license:
                norms = list(
                    import_item.license.export_license.all()
                    .values_list("norm_class__norm_class", flat=True)
                    .distinct()
                )
            # Filter out None values and convert to strings
            norms = [str(n) for n in norms if n is not None]
            norms_str = ", ".join(norms) if norms else ""

            # Get current item names (if any)
            current_items = list(import_item.items.all().values_list('name', flat=True))
            # Filter out None values and convert to strings
            current_items = [str(item) for item in current_items if item is not None]
            current_items_str = ", ".join(current_items) if current_items else ""

            # Create row
            row = {
                'description': description,
                'hs_code': hs_code,
                'norms': norms_str,
                'quantity': quantity,
                'cif_value': cif_value,
                'license_number': license_number,
                'exporter': exporter,
                'current_item_names': current_items_str,
                'import_item_id': import_item.id,
            }

            if unique_only:
                # Create unique key
                unique_key = (description.strip().lower(), hs_code, norms_str)

                if unique_key in seen_combinations:
                    # Update count and add to combined list
                    seen_combinations[unique_key]['count'] += 1
                    seen_combinations[unique_key]['total_quantity'] += quantity
                    seen_combinations[unique_key]['total_cif'] += cif_value
                    if license_number not in seen_combinations[unique_key]['licenses']:
                        seen_combinations[unique_key]['licenses'].append(license_number)
                else:
                    # New combination
                    seen_combinations[unique_key] = {
                        'description': description,
                        'hs_code': hs_code,
                        'norms': norms_str,
                        'count': 1,
                        'total_quantity': quantity,
                        'total_cif': cif_value,
                        'licenses': [license_number] if license_number else [],
                        'current_item_names': current_items_str,
                    }
            else:
                data_rows.append(row)

        self.stdout.write(f"  Processed {total_count}/{total_count}")
        self.stdout.write("")

        # Write to CSV
        self.stdout.write(f"Writing to {output_file}...")

        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            if unique_only:
                # Write unique combinations
                fieldnames = [
                    'description',
                    'hs_code',
                    'norms',
                ]
                if with_count:
                    fieldnames.extend([
                        'occurrence_count',
                        'total_quantity',
                        'total_cif_value',
                        'sample_licenses',
                    ])
                fieldnames.append('current_item_names')
                fieldnames.append('suggested_item_name')

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for unique_key, data in sorted(seen_combinations.items(), key=lambda x: x[1]['count'], reverse=True):
                    row = {
                        'description': data['description'],
                        'hs_code': data['hs_code'],
                        'norms': data['norms'],
                        'current_item_names': data['current_item_names'],
                        'suggested_item_name': '',  # Empty for user to fill
                    }
                    if with_count:
                        # Filter out None values from licenses list
                        licenses_list = [str(lic) for lic in data['licenses'][:5] if lic]
                        row.update({
                            'occurrence_count': data['count'],
                            'total_quantity': f"{data['total_quantity']:.3f}",
                            'total_cif_value': f"{data['total_cif']:.2f}",
                            'sample_licenses': ', '.join(licenses_list),
                        })
                    writer.writerow(row)

                unique_count = len(seen_combinations)
                self.stdout.write("")
                self.stdout.write(self.style.SUCCESS(f"✓ Exported {unique_count} unique combinations"))

            else:
                # Write all rows
                fieldnames = [
                    'import_item_id',
                    'license_number',
                    'exporter',
                    'description',
                    'hs_code',
                    'norms',
                    'quantity',
                    'cif_value',
                    'current_item_names',
                    'suggested_item_name',
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for row in data_rows:
                    row['suggested_item_name'] = ''  # Empty for user to fill
                    writer.writerow(row)

                self.stdout.write("")
                self.stdout.write(self.style.SUCCESS(f"✓ Exported {len(data_rows)} rows"))

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS(f"✅ Export complete: {output_file}"))
        self.stdout.write("=" * 80)
        self.stdout.write("")
        self.stdout.write("Next steps:")
        self.stdout.write("1. Open the CSV file in Excel or Google Sheets")
        self.stdout.write("2. Fill in the 'suggested_item_name' column")
        self.stdout.write("3. Use the import command to update item names")
        self.stdout.write("")

        # Print summary statistics
        if unique_only and with_count:
            self.stdout.write("Top 10 most common combinations:")
            for idx, (unique_key, data) in enumerate(
                sorted(seen_combinations.items(), key=lambda x: x[1]['count'], reverse=True)[:10], 1
            ):
                desc_preview = data['description'][:60] + "..." if len(data['description']) > 60 else data['description']
                self.stdout.write(
                    f"  {idx}. [{data['count']:>4}x] {desc_preview} | HSN: {data['hs_code']} | Norms: {data['norms']}"
                )
