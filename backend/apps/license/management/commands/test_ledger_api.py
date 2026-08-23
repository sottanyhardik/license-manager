"""
Django management command: Test Ledger API response reconciliation.
"""

from django.core.management.base import BaseCommand
from rest_framework.test import APIClient
from apps.license.models import LicenseDetailsModel


class Command(BaseCommand):
    help = 'Test API ledger response for a license'

    def add_arguments(self, parser):
        parser.add_argument(
            'license_number',
            type=str,
            help='License number to test (e.g., 0310833996)'
        )

    def handle(self, *args, **options):
        license_number = options['license_number']

        # Find the license
        license_obj = LicenseDetailsModel.objects.filter(
            license_number=license_number
        ).first()

        if not license_obj:
            self.stdout.write(self.style.ERROR(f'License {license_number} not found'))
            return

        self.stdout.write(f'\nLicense ID: {license_obj.id}')
        self.stdout.write(f'License Number: {license_obj.license_number}')

        # Create API client with no authentication (to test public access)
        client = APIClient()

        # Try to get ledger detail
        url = f'/api/license-ledger/{license_obj.id}/ledger_detail/'
        self.stdout.write(f'\nAPI Endpoint: {url}')

        response = client.get(url)

        self.stdout.write(f'\nAPI Response Status: {response.status_code}')

        if response.status_code == 200:
            data = response.json()

            # Print transactions
            self.stdout.write(f'\nTransactions from API:')
            self.stdout.write(f'{"TxnID":<8} {"Type":<15} {"Amount (USD)":<16} {"Bill (₹)":<16}')
            self.stdout.write("-"*60)

            for txn in data.get('transactions', []):
                txn_id = txn.get('id', 'N/A')
                txn_type = txn.get('type', 'N/A')
                amount = txn.get('amount', 'N/A')
                bill = txn.get('bill_amount', 'N/A')

                self.stdout.write(f'{txn_id:<8} {txn_type:<15} ${str(amount):<15} ₹{str(bill):<15}')

            # Print summary
            self.stdout.write(f'\nSummary from API:')
            summary = data.get('summary', {})
            for key, value in summary.items():
                self.stdout.write(f'  {key}: {value}')

        elif response.status_code == 401:
            self.stdout.write(self.style.WARNING('Unauthorized (401) - Need authentication'))
            self.stdout.write(response.text)

        elif response.status_code == 403:
            self.stdout.write(self.style.WARNING('Forbidden (403) - Check permissions'))
            self.stdout.write(response.text)

        else:
            self.stdout.write(self.style.ERROR(f'ERROR: {response.status_code}'))
            self.stdout.write(response.text)
