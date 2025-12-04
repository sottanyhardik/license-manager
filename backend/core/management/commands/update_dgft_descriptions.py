"""
Management command to fetch all SION norms from DGFT and update existing descriptions
Uses the DGFT DataTables API to get comprehensive norm data
"""
from django.core.management.base import BaseCommand
from django.db import transaction
import requests
import json
import time

from core.models import SionNormClassModel, SIONExportModel, SIONImportModel, HeadSIONNormsModel


class Command(BaseCommand):
    help = 'Fetch all SION norms from DGFT and update existing descriptions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--product-group',
            type=str,
            help='Fetch only specific product group (e.g., "Food Products")',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        product_group_filter = options.get('product_group')
        dry_run = options.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))

        self.stdout.write('Fetching SION norms from DGFT...')

        # Get session and CSRF token
        session, csrf_token = self.get_session_and_csrf()
        if not session or not csrf_token:
            self.stdout.write(self.style.ERROR('Failed to get session'))
            return

        # Product groups to fetch
        product_groups = [
            {'key': '67', 'value': 'Food Products'},
            {'key': '66', 'value': 'Engineering Products'},
            {'key': '65', 'value': 'Chemical and Allied Products'},
            {'key': '64', 'value': 'Textiles and Textile Articles'},
            {'key': '63', 'value': 'Plastic Products'},
            {'key': '62', 'value': 'Leather and Leather Products'},
            {'key': '61', 'value': 'Wood and Wood Products'},
            {'key': '60', 'value': 'Electronics and IT Products'},
            {'key': '59', 'value': 'Other Products'},
        ]

        if product_group_filter:
            product_groups = [pg for pg in product_groups if pg['value'] == product_group_filter]
            if not product_groups:
                self.stdout.write(self.style.ERROR(f'Product group "{product_group_filter}" not found'))
                return

        total_updated = 0
        total_created = 0
        total_skipped = 0

        for pg in product_groups:
            self.stdout.write(f'\n=== {pg["value"]} ===')

            updated, created, skipped = self.fetch_and_update_group(
                session, csrf_token, pg, dry_run
            )

            total_updated += updated
            total_created += created
            total_skipped += skipped

            # Be nice to the server
            time.sleep(2)

        self.stdout.write(self.style.SUCCESS(
            f'\n\nSummary:'
            f'\n  Updated: {total_updated}'
            f'\n  Created: {total_created}'
            f'\n  Skipped: {total_skipped}'
            f'\n  Total processed: {total_updated + total_created + total_skipped}'
        ))

    def get_session_and_csrf(self):
        """Get session and CSRF token from DGFT website"""
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            })

            response = session.get('https://www.dgft.gov.in/CP/?opt=norms-search', timeout=30)

            if response.status_code != 200:
                return None, None

            # Extract CSRF token from meta tag
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            csrf_meta = soup.find('meta', {'name': '_csrf'})
            csrf_token = csrf_meta.get('content') if csrf_meta else None

            if not csrf_token:
                return None, None

            return session, csrf_token

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting session: {e}'))
            return None, None

    def fetch_and_update_group(self, session, csrf_token, product_group, dry_run):
        """Fetch all norms for a product group and update database"""
        updated = 0
        created = 0
        skipped = 0

        try:
            # Fetch norms from DGFT
            norms_data = self.fetch_norms_for_group(
                session, csrf_token,
                product_group['key'],
                product_group['value']
            )

            if not norms_data:
                self.stdout.write(self.style.WARNING('  No data received'))
                return updated, created, skipped

            self.stdout.write(f'  Found {len(norms_data)} norms')

            for norm_data in norms_data:
                try:
                    result = self.update_or_create_norm(norm_data, product_group['value'], dry_run)
                    if result == 'updated':
                        updated += 1
                    elif result == 'created':
                        created += 1
                    else:
                        skipped += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Error processing {norm_data.get("sionSerialNo")}: {e}'))
                    continue

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error fetching group: {e}'))

        self.stdout.write(f'  Updated: {updated}, Created: {created}, Skipped: {skipped}')
        return updated, created, skipped

    def fetch_norms_for_group(self, session, csrf_token, group_id, group_name, limit=1000):
        """Fetch all norms for a specific product group"""
        base_url = 'https://www.dgft.gov.in/CP/webHP'

        params = {
            'requestType': 'ApplicationRH',
            'actionVal': 'getSION',
            'screenId': '90000534',
            '_csrf': csrf_token,
        }

        headers = {
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'x-requested-with': 'XMLHttpRequest',
            'origin': 'https://www.dgft.gov.in',
            'referer': 'https://www.dgft.gov.in/CP/?opt=norms-search',
        }

        form_data = {
            "exportProductGroup": {
                "key": group_id,
                "value": group_name
            },
            "exportItc": {
                "key": "-1",
                "value": "Search based on ITC(HS) Code or Product Description. e.g. 52081230 or Shirting Fabrics"
            },
            "sionSerialNo": {
                "key": "-1",
                "value": "Please select export product group"
            },
            "importItc": {
                "key": "-1",
                "value": "Search based on ITC(HS) Code or Product Description. e.g. 52081230 or Shirting Fabrics"
            },
            "exportItemName": "",
            "exportProductGroup_Value": group_name,
            "exportProductGroup_key": group_id,
            "sionSerialNo_Value": "Please select export product group",
            "sionSerialNo_key": "-1",
            "exportItc_Value": "Search based on ITC(HS) Code or Product Description. e.g. 52081230 or Shirting Fabrics",
            "exportItc_key": "-1",
            "importItc_Value": "Search based on ITC(HS) Code or Product Description. e.g. 52081230 or Shirting Fabrics",
            "importItc_key": "-1"
        }

        all_records = []
        start = 0
        page_size = 100

        while True:
            data_dict = {
                'draw': '1',
                'start': str(start),
                'length': str(page_size),
                'search[value]': '',
                'search[regex]': 'false',
                'order[0][column]': '0',
                'order[0][dir]': 'asc',
                f'dataJson[formData]': json.dumps(form_data)
            }

            # Add column definitions
            columns = ['', 'sionSerialNo', 'description', 'exportItemQtyAndUom',
                      'qtyExportItem', 'uomExport', 'caseNo', 'qtyExportItem',
                      'exportItemName', 'siNo']

            for i, col in enumerate(columns):
                data_dict[f'columns[{i}][data]'] = col
                data_dict[f'columns[{i}][name]'] = ''
                data_dict[f'columns[{i}][searchable]'] = 'true'
                data_dict[f'columns[{i}][orderable]'] = 'true'
                data_dict[f'columns[{i}][search][value]'] = ''
                data_dict[f'columns[{i}][search][regex]'] = 'false'

            try:
                response = session.post(base_url, params=params, headers=headers, data=data_dict, timeout=60)

                if response.status_code != 200:
                    self.stdout.write(self.style.WARNING(f'  HTTP {response.status_code}'))
                    break

                result = response.json()
                records = result.get('data', [])

                if not records:
                    break

                all_records.extend(records)
                start += page_size

                # Check if we've fetched all records
                records_total = result.get('recordsFiltered', 0)
                if start >= records_total or start >= limit:
                    break

                # Progress indicator
                self.stdout.write(f'  Fetched {len(all_records)}/{records_total}...', ending='\r')
                self.stdout.flush()

            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Error fetching page: {e}'))
                break

        return all_records

    def update_or_create_norm(self, norm_data, product_group_name, dry_run):
        """Update or create a SION norm and its export item"""
        sion_number = (norm_data.get('sionSerialNo') or '').strip()
        description = (norm_data.get('description') or '').strip()
        qty = norm_data.get('qtyExportItem', 0)
        uom = (norm_data.get('uomExport') or '').strip()

        if not sion_number:
            return 'skipped'

        # Find or create the norm class
        try:
            norm_class = SionNormClassModel.objects.get(norm_class=sion_number)
            action = 'updated'
        except SionNormClassModel.DoesNotExist:
            if dry_run:
                self.stdout.write(f'  [DRY RUN] Would create: {sion_number}')
                return 'created'

            # Get or create head norm for this product group
            head_norm, _ = HeadSIONNormsModel.objects.get_or_create(
                name=product_group_name
            )

            # Create new norm class
            norm_class = SionNormClassModel.objects.create(
                norm_class=sion_number,
                head_norm=head_norm,
                description=description if description else ''
            )
            action = 'created'
            self.stdout.write(f'  Created new norm: {sion_number}')

        if dry_run:
            if action == 'updated':
                self.stdout.write(f'  [DRY RUN] Would update: {sion_number}')
            return action

        # Update description if provided and different
        with transaction.atomic():
            updated_fields = []

            if description and norm_class.description != description:
                norm_class.description = description
                updated_fields.append('description')

            if updated_fields:
                norm_class.save(update_fields=updated_fields)

            # Update or create export item
            if description and qty and uom:
                export_item, export_created = SIONExportModel.objects.update_or_create(
                    norm_class=norm_class,
                    description=description[:255],
                    defaults={
                        'quantity': self.parse_decimal(qty),
                        'unit': uom[:255],
                    }
                )

                if export_created:
                    self.stdout.write(f'  Created export item for: {sion_number}')

        return action

    def parse_decimal(self, value):
        """Parse decimal value from string or number"""
        try:
            if not value:
                return 0
            import re
            clean_value = re.sub(r'[^\d.-]', '', str(value))
            return float(clean_value) if clean_value else 0
        except:
            return 0
