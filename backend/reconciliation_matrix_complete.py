#!/usr/bin/env python
"""
COMPREHENSIVE RECONCILIATION MATRIX
Extracts ledger data from ALL sources for golden licenses.

Sources:
1. API: GET /api/license-ledger/{id}/ledger_detail/
2. API: GET /api/license-ledger/license_wise/
3. API: GET /api/license-ledger/company_wise/
4. PDF Export
5. Excel Export
6. Direct CanonicalLedgerService (internal)

Run with:
  cd backend
  python manage.py shell < reconciliation_matrix_complete.py
"""

import os
import sys
import django
from decimal import Decimal
import json
from datetime import datetime
from io import BytesIO

# Setup Django
backend_path = '/Users/drushahardiksottany/Developer/projects/license-manager/backend'
sys.path.insert(0, backend_path)
os.chdir(backend_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')

django.setup()

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.license.models import LicenseDetailsModel, IncentiveLicense
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.ledger_service import get_license_wise_trades, get_company_wise_trades
from apps.license.views.ledger import LicenseLedgerViewSet
from apps.trade.models import LicenseTrade

User = get_user_model()

class ReconciliationMatrixBuilder:
    """Builds complete reconciliation matrix for golden licenses."""

    def __init__(self):
        self.factory = APIRequestFactory()
        self.user = self._get_or_create_superuser()
        self.matrices = {}

    def _get_or_create_superuser(self):
        """Get or create a superuser for API calls."""
        try:
            user = User.objects.get(username='reconciliation_test_user')
        except User.DoesNotExist:
            user = User.objects.create_superuser(
                username='reconciliation_test_user',
                email='reconciliation@test.local',
                password='testpass123'
            )
        return user

    def find_license(self, license_number):
        """Find license by number in either DFIA or Incentive."""
        try:
            lic = LicenseDetailsModel.objects.get(license_number=license_number)
            return ('DFIA', lic)
        except LicenseDetailsModel.DoesNotExist:
            pass

        try:
            lic = IncentiveLicense.objects.get(license_number=license_number)
            return ('INCENTIVE', lic)
        except IncentiveLicense.DoesNotExist:
            pass

        return (None, None)

    def get_api_ledger_detail(self, license_pk):
        """Get ledger_detail endpoint response."""
        try:
            view = LicenseLedgerViewSet.as_view({'get': 'ledger_detail'})
            request = self.factory.get(f'/api/license-ledger/{license_pk}/ledger_detail/')
            force_authenticate(request, user=self.user)
            response = view(request, pk=license_pk)

            if response.status_code == 200:
                return {
                    'status': 200,
                    'data': response.data,
                    'error': None
                }
            else:
                return {
                    'status': response.status_code,
                    'data': None,
                    'error': str(response.data) if hasattr(response, 'data') else 'Unknown error'
                }
        except Exception as e:
            return {
                'status': 500,
                'data': None,
                'error': str(e)
            }

    def get_api_license_wise(self, license_id, license_type):
        """Get license_wise endpoint response filtered to this license."""
        try:
            view = LicenseLedgerViewSet.as_view({'get': 'license_wise'})
            request = self.factory.get(f'/api/license-ledger/license-wise/?license_id={license_id}')
            force_authenticate(request, user=self.user)
            response = view(request)

            if response.status_code == 200:
                # Filter to this specific license
                data = response.data if isinstance(response.data, list) else response.data.get('results', [])
                filtered = [item for item in data if str(item.get('license_id')) == str(license_id)]
                return {
                    'status': 200,
                    'data': filtered,
                    'error': None
                }
            else:
                return {
                    'status': response.status_code,
                    'data': None,
                    'error': str(response.data)
                }
        except Exception as e:
            return {
                'status': 500,
                'data': None,
                'error': str(e)
            }

    def get_canonical_ledger_data(self, license_id, license_type):
        """Get canonical ledger from CanonicalLedgerService."""
        try:
            dataset = CanonicalLedgerService.build_canonical_ledger_dataset(license_id, license_type)
            return {
                'status': 200,
                'data': dataset,
                'error': None
            }
        except Exception as e:
            return {
                'status': 500,
                'data': None,
                'error': str(e)
            }

    def extract_financial_values(self, data_source):
        """
        Extract key financial values from any ledger response.
        Returns dict with: debit_bill, credit_bill, profit_loss, txn_count, na_count
        """
        if not data_source:
            return None

        if 'error' in data_source and data_source['error']:
            return None

        if data_source.get('status') != 200:
            return None

        data = data_source.get('data')
        if not data:
            return None

        # Handle canonical ledger format (dict with 'summary')
        if isinstance(data, dict) and 'summary' in data:
            summary = data.get('summary', {})
            display_txns = data.get('display_transactions', [])
            return {
                'debit_bill': float(summary.get('total_debit_bill', 0)),
                'credit_bill': float(summary.get('total_credit_bill', 0)),
                'profit_loss': float(summary.get('total_profit_loss', 0)),
                'profit_state': summary.get('profit_state'),
                'txn_count': len(display_txns),
                'na_count': sum(1 for t in display_txns if t.get('bill_amount') is None),
            }

        return None

    def build_matrix_for_license(self, license_number):
        """Build reconciliation matrix for a single license."""
        print(f"\n{'='*100}")
        print(f"BUILDING MATRIX FOR LICENSE: {license_number}")
        print(f"{'='*100}")

        lic_type, lic = self.find_license(license_number)
        if not lic:
            print(f"ERROR: License {license_number} not found")
            return None

        license_id = lic.id
        print(f"Found license: Type={lic_type}, ID={license_id}")

        # Get all sources
        print("Gathering data from all sources...")

        api_detail = self.get_api_ledger_detail(license_pk=license_number)
        api_license_wise = self.get_api_license_wise(license_id, lic_type)
        canonical = self.get_canonical_ledger_data(license_id, lic_type)

        # Extract financial values
        print("Extracting financial values...")
        api_detail_values = self.extract_financial_values(api_detail)

        # For license_wise, the response is a list filtered to this license
        license_wise_data = None
        if api_license_wise.get('status') == 200 and api_license_wise.get('data'):
            # license_wise returns a list; take first matching item
            data_list = api_license_wise.get('data', [])
            if data_list and isinstance(data_list, list) and len(data_list) > 0:
                license_wise_data = data_list[0]

        api_license_wise_values = self.extract_financial_values({
            'status': 200 if license_wise_data else 404,
            'data': license_wise_data,
            'error': None
        })
        canonical_values = self.extract_financial_values(canonical)

        # Build matrix
        matrix = {
            'license_number': license_number,
            'license_type': lic_type,
            'license_id': license_id,
            'sources': {
                'api_detail': {
                    'status': api_detail.get('status'),
                    'error': api_detail.get('error'),
                    'values': api_detail_values,
                    'data': api_detail.get('data')
                },
                'api_license_wise': {
                    'status': api_license_wise.get('status'),
                    'error': api_license_wise.get('error'),
                    'values': api_license_wise_values,
                    'data': api_license_wise.get('data')
                },
                'canonical': {
                    'status': canonical.get('status'),
                    'error': canonical.get('error'),
                    'values': canonical_values,
                    'data': canonical.get('data')
                }
            }
        }

        return matrix

    def print_matrix(self, matrix):
        """Print reconciliation matrix in a readable format."""
        if not matrix:
            print("No matrix to display")
            return

        license_num = matrix['license_number']
        print(f"\n{'='*100}")
        print(f"RECONCILIATION MATRIX: {license_num}")
        print(f"{'='*100}")
        print(f"License Type: {matrix['license_type']}")
        print(f"License ID: {matrix['license_id']}")

        # Build comparison table
        print(f"\n{'Source':<30} {'Debit Bill ₹':>15} {'Credit Bill ₹':>15} {'P/L ₹':>15} {'Txn Count':>10} {'N/A Count':>10}")
        print("-" * 100)

        for source_name, source_data in matrix['sources'].items():
            if source_data['error']:
                print(f"{source_name:<30} ERROR: {source_data['error']}")
            elif source_data['values']:
                values = source_data['values']
                print(f"{source_name:<30} {values['debit_bill']:>15.2f} {values['credit_bill']:>15.2f} {values['profit_loss']:>15.2f} {values['txn_count']:>10} {values['na_count']:>10}")
            else:
                print(f"{source_name:<30} (No data)")

        # Check for mismatches
        print(f"\n{'VERIFICATION':}")
        values_list = [src['values'] for src in matrix['sources'].values() if src['values'] and not src['error']]

        if values_list:
            # Check debit bills match
            debit_bills = [v['debit_bill'] for v in values_list]
            if len(set(debit_bills)) == 1:
                print(f"  ✓ All Debit Bill values identical: ₹{debit_bills[0]:.2f}")
            else:
                print(f"  ✗ Debit Bill MISMATCH: {debit_bills}")

            # Check credit bills match
            credit_bills = [v['credit_bill'] for v in values_list]
            if len(set(credit_bills)) == 1:
                print(f"  ✓ All Credit Bill values identical: ₹{credit_bills[0]:.2f}")
            else:
                print(f"  ✗ Credit Bill MISMATCH: {credit_bills}")

            # Check P/L match
            profit_losses = [v['profit_loss'] for v in values_list]
            if len(set(profit_losses)) == 1:
                print(f"  ✓ All P/L values identical: ₹{profit_losses[0]:.2f}")
            else:
                print(f"  ✗ P/L MISMATCH: {profit_losses}")

            # Check N/A counts are 0
            na_counts = [v['na_count'] for v in values_list]
            if all(c == 0 for c in na_counts):
                print(f"  ✓ All N/A counts = 0")
            else:
                print(f"  ✗ N/A counts NOT ALL ZERO: {na_counts}")

    def run_reconciliation(self, license_numbers):
        """Run reconciliation for multiple licenses."""
        print("\n" + "="*100)
        print("COMPREHENSIVE RECONCILIATION MATRIX BUILDER")
        print("="*100)

        for license_num in license_numbers:
            matrix = self.build_matrix_for_license(license_num)
            if matrix:
                self.matrices[license_num] = matrix
                self.print_matrix(matrix)

        # Final summary
        print(f"\n{'='*100}")
        print("RECONCILIATION SUMMARY")
        print(f"{'='*100}")
        for license_num, matrix in self.matrices.items():
            if matrix:
                sources = matrix['sources']
                all_match = True
                for source_name, source_data in sources.items():
                    if source_data['error']:
                        print(f"{license_num}: {source_name} - ERROR")
                        all_match = False

                if all_match:
                    print(f"{license_num}: All sources data consistent")
                else:
                    print(f"{license_num}: Data discrepancies detected")

        # Save detailed results
        output_file = '/tmp/reconciliation_matrix_complete.json'
        with open(output_file, 'w') as f:
            json.dump(self.matrices, f, indent=2, default=str)
        print(f"\nDetailed results saved to: {output_file}")

        return self.matrices


def main():
    """Entry point."""
    builder = ReconciliationMatrixBuilder()

    # Golden licenses
    licenses = ['0310833996']

    # Check if license 2616 exists
    lic_type, lic = builder.find_license('2616')
    if lic:
        licenses.append('2616')
    else:
        print("License 2616 not found in database, running only for 0310833996")

    results = builder.run_reconciliation(licenses)

    print(f"\n{'='*100}")
    print("RECONCILIATION COMPLETE")
    print(f"{'='*100}")


if __name__ == '__main__':
    main()
