import csv
import os
from django.core.management.base import BaseCommand

from backend.scripts.parse_ledger import parse_license_data


class Command(BaseCommand):
    help = "Parse a CSV file (from license ledger tables) and convert to structured dict_list JSON"

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            type=str,
            required=True,
            help='Path to the CSV file containing ledger table rows'
        )

    def handle(self, *args, **options):
        csv_path = options['csv']

        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f"CSV file not found: {csv_path}"))
            return

        rows = []
        with open(csv_path, newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                # Skip rows where all fields are empty
                if not any(field.strip() for field in row):
                    continue
                rows.append(row)

        dict_list = parse_license_data(rows)

        for dict_data in dict_list:
            from core.scripts.ledger import create_object
            create_object(dict_data)
            self.stdout.write(
                self.style.SUCCESS(f"Successfully Created for DFIA {(dict_data['lic_no'])}."))
        self.stdout.write(self.style.SUCCESS(f"Successfully converted to dict_list with {len(dict_list)} licenses."))
