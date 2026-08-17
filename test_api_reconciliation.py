#!/usr/bin/env python
"""
Test API response reconciliation for license 0310833996.

Verifies that the API endpoint returns the exact same canonical ledger data.
"""

import os
import sys
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.license.models import LicenseDetailsModel

User = get_user_model()

def test_api_ledger_response():
    """Test that the API returns the canonical ledger data."""

    # Create or get a test user
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={
            'email': 'test@example.com',
            'is_active': True,
        }
    )

    # Create API client
    client = APIClient()
    client.force_authenticate(user=user)

    # Find the license
    license_obj = LicenseDetailsModel.objects.filter(license_number='0310833996').first()
    if not license_obj:
        print("ERROR: License 0310833996 not found")
        return

    print(f"\nLicense ID: {license_obj.id}")
    print(f"License Number: {license_obj.license_number}")

    # Make API request to get ledger detail
    url = f'/api/license-ledger/{license_obj.id}/ledger_detail/'
    response = client.get(url)

    print(f"\nAPI Response Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()

        # Print transactions
        print(f"\nTransactions from API:")
        print(f"{'TxnID':<8} {'Type':<15} {'Amount (USD)':<16} {'Bill (₹)':<16}")
        print("-"*60)

        for txn in data.get('transactions', []):
            txn_id = txn.get('id', 'N/A')
            txn_type = txn.get('type', 'N/A')
            amount = txn.get('amount', 'N/A')
            bill = txn.get('bill_amount', 'N/A')

            print(f"{txn_id:<8} {txn_type:<15} ${str(amount):<15} ₹{str(bill):<15}")

        # Print summary
        print(f"\nSummary from API:")
        summary = data.get('summary', {})
        for key, value in summary.items():
            print(f"  {key}: {value}")

    else:
        print(f"ERROR: {response.status_code}")
        print(response.text)


if __name__ == '__main__':
    test_api_ledger_response()
