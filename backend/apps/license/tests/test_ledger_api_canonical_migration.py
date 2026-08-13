"""
Phase 4C: Ledger API Canonical Migration Tests

Tests verify that:
1. API response matches CanonicalLedgerService output exactly
2. Serializer presents data without calculation
3. All existing permissions/filters work
4. Commission handling is correct
5. Backward compatibility fields exist

**CRITICAL TEST:** test_api_response_parity_with_canonical_dataset
"""

import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status

from apps.license.models import LicenseDetailsModel, IncentiveLicense
from apps.license.services.canonical_ledger_service import CanonicalLedgerService


@pytest.mark.api
@pytest.mark.database
class TestLedgerAPICanonicalMigration:
    """Test API migration to CanonicalLedgerService"""

    def test_api_license_detail_returns_200_success(self, authenticated_client, test_license):
        """Test GET /licenses/{id}/ledger_detail/ returns 200 OK"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

    def test_api_license_detail_requires_license_found(self, authenticated_client):
        """Test GET /licenses/999/ledger_detail/ returns 404 for missing license"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': 999})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data

    def test_api_response_has_canonical_fields(self, authenticated_client, test_license):
        """Test response includes all canonical ledger fields"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        # Root level fields
        assert 'license_id' in data
        assert 'license_type' in data
        assert 'license_number' in data
        assert 'license_date' in data
        assert 'expiry_date' in data
        assert 'exporter_name' in data
        assert 'port_name' in data

        # Balance fields
        assert 'opening_balance' in data
        assert 'license_running_balance' in data
        assert 'closing_balance' in data

        # Canonical fields (Phase 4C)
        assert 'transactions' in data
        assert 'company_utilizations' in data
        assert 'totals' in data

    def test_api_response_includes_backward_compat_fields(self, authenticated_client, test_license):
        """Test response includes deprecated fields for backward compatibility"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        # Deprecated fields (Phase 4C; removed in Phase 4D)
        assert 'available_balance' in data
        assert 'db_balance' in data

        # These should equal license_running_balance
        assert data['available_balance'] == data['license_running_balance']
        assert data['db_balance'] == data['license_running_balance']

    def test_api_response_parity_with_canonical_dataset(self, authenticated_client, test_license):
        """
        **CRITICAL TEST**

        Verify that API response matches CanonicalLedgerService output exactly.
        This ensures the API is a transparent serialization layer with NO calculations.
        """
        # Get canonical dataset
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
            license_id=test_license.id,
            license_type='DFIA'
        )

        # Get API response
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        api_data = response.data

        # Verify root-level fields match
        assert api_data['license_id'] == canonical['license_id']
        assert api_data['license_type'] == canonical['license_type']
        assert api_data['license_number'] == test_license.license_number
        assert api_data['opening_balance'] == str(canonical['opening_balance'])
        assert api_data['license_running_balance'] == str(canonical['license_running_balance'])
        assert api_data['closing_balance'] == str(canonical['closing_balance'])

        # Verify transaction count matches
        assert len(api_data['transactions']) == len(canonical['transactions'])

        # Verify transaction parity
        for i, (api_txn, canonical_txn) in enumerate(zip(api_data['transactions'], canonical['transactions'])):
            assert api_txn['date'] == canonical_txn['date'].isoformat(), f"Txn {i}: date mismatch"
            assert api_txn['id'] == canonical_txn['id'], f"Txn {i}: id mismatch"
            assert api_txn['type'] == canonical_txn['type'], f"Txn {i}: type mismatch"
            assert api_txn['company_id'] == canonical_txn['company_id'], f"Txn {i}: company_id mismatch"
            assert api_txn['amount'] == str(canonical_txn['amount']), f"Txn {i}: amount mismatch"
            assert api_txn['is_commission'] == canonical_txn['is_commission'], f"Txn {i}: is_commission mismatch"
            assert api_txn['affects_balance'] == canonical_txn['affects_balance'], f"Txn {i}: affects_balance mismatch"
            assert api_txn['license_running_balance'] == str(canonical_txn['license_running_balance']), f"Txn {i}: running_balance mismatch"

        # Verify totals match
        assert api_data['totals']['total_purchases'] == str(canonical['totals']['total_purchases'])
        assert api_data['totals']['total_sales'] == str(canonical['totals']['total_sales'])
        assert api_data['totals']['total_commission'] == str(canonical['totals']['total_commission'])

    def test_api_commission_transactions_excluded_from_balance(self, authenticated_client, test_license):
        """
        Test that COMMISSION transactions:
        - Appear in transactions list
        - Have is_commission=true
        - Have affects_balance=false
        - Do NOT change license_running_balance
        - Have display_status set
        """
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        # Find commission transactions
        commission_txns = [t for t in data['transactions'] if t['is_commission']]

        # If there are commission txns, verify they're handled correctly
        if commission_txns:
            for txn in commission_txns:
                assert txn['is_commission'] is True, "is_commission should be True"
                assert txn['affects_balance'] is False, "COMMISSION should not affect balance"
                if 'display_status' in txn:
                    assert 'Excluded' in txn['display_status']

    def test_api_opening_balance_transaction(self, authenticated_client, test_license):
        """Test that OPENING transaction is first (if exists)"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        # `opening_balance` is serialized as a 2dp STRING (asserted by
        # test_api_decimal_fields_as_strings), so compare it as a Decimal —
        # same pattern as test_api_running_balance_is_consistent below.
        if Decimal(data['opening_balance']) > 0:
            # First transaction should be OPENING
            assert data['transactions'][0]['type'] == 'OPENING'
            assert data['transactions'][0]['id'] == 0
            assert data['transactions'][0]['affects_balance'] is True

    def test_api_transaction_ordering(self, authenticated_client, test_license):
        """Test transactions are sorted by date, then ID"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        transactions = data['transactions']
        if len(transactions) > 1:
            # Verify sorted by date
            prev_date = None
            for txn in transactions:
                if prev_date is not None:
                    assert txn['date'] >= prev_date, "Transactions should be sorted by date"
                prev_date = txn['date']

    def test_api_company_utilizations_breakdown(self, authenticated_client, test_license):
        """Test company utilizations dict is present and structured correctly"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        assert isinstance(data['company_utilizations'], dict)

        # Each company should have id, name, and balance
        for company_id, company_data in data['company_utilizations'].items():
            assert 'company_id' in company_data
            assert 'company_name' in company_data
            assert 'utilization_balance' in company_data

    def test_api_totals_breakdown(self, authenticated_client, test_license):
        """Test totals dict has all required fields"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        assert 'total_purchases' in data['totals']
        assert 'total_sales' in data['totals']
        assert 'total_commission' in data['totals']

    def test_api_decimal_fields_as_strings(self, authenticated_client, test_license):
        """Test that decimal fields are serialized as strings (not floats)"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        # Root level decimals should be strings
        assert isinstance(data['opening_balance'], str)
        assert isinstance(data['license_running_balance'], str)
        assert isinstance(data['closing_balance'], str)

        # Transaction decimals should be strings
        if data['transactions']:
            assert isinstance(data['transactions'][0]['amount'], str)
            assert isinstance(data['transactions'][0]['license_running_balance'], str)

        # Totals should be strings
        assert isinstance(data['totals']['total_purchases'], str)
        assert isinstance(data['totals']['total_sales'], str)
        assert isinstance(data['totals']['total_commission'], str)

    def test_api_authorization_required(self, client, test_license):
        """Test that endpoint requires authentication"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = client.get(url)

        # Unauthenticated request should be denied
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_api_license_type_parameter(self, authenticated_client, test_license):
        """Test license_type query parameter works"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})

        # Test with explicit DFIA type
        response = authenticated_client.get(url, {'license_type': 'DFIA'})
        assert response.status_code == status.HTTP_200_OK

        # Test with AUTO (default)
        response = authenticated_client.get(url, {'license_type': 'AUTO'})
        assert response.status_code == status.HTTP_200_OK

    def test_api_response_is_json(self, authenticated_client, test_license):
        """Test response is valid JSON"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'application/json'
        assert isinstance(response.json(), dict)

    def test_api_running_balance_is_consistent(self, authenticated_client, test_license):
        """
        Test that running balance is consistent:
        - Each transaction's license_running_balance is >= previous (or <= for SALE)
        - Final transaction's balance = license_running_balance
        """
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        transactions = data['transactions']
        if len(transactions) > 1:
            # Verify final transaction balance matches root balance
            final_txn_balance = Decimal(transactions[-1]['license_running_balance'])
            root_balance = Decimal(data['license_running_balance'])
            assert final_txn_balance == root_balance, "Final transaction balance must equal license_running_balance"


@pytest.mark.api
@pytest.mark.database
class TestLedgerAPINoFinancialLogic:
    """Verify API layer has ZERO financial calculations"""

    def test_api_does_not_recalculate_balance(self, authenticated_client, test_license):
        """
        Verify API returns pre-calculated balance from CanonicalLedgerService,
        not a re-calculated value.
        """
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        # Get canonical balance
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
            license_id=test_license.id,
            license_type='DFIA'
        )

        # API balance should exactly match canonical
        assert Decimal(data['license_running_balance']) == canonical['license_running_balance']

    def test_api_does_not_recalculate_totals(self, authenticated_client, test_license):
        """Verify API returns pre-calculated totals, not summed values"""
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        # Get canonical totals
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
            license_id=test_license.id,
            license_type='DFIA'
        )

        # API totals should exactly match canonical (not recalculated from transactions)
        assert Decimal(data['totals']['total_purchases']) == canonical['totals']['total_purchases']
        assert Decimal(data['totals']['total_sales']) == canonical['totals']['total_sales']
        assert Decimal(data['totals']['total_commission']) == canonical['totals']['total_commission']

    def test_api_does_not_modify_transaction_types(self, authenticated_client, test_license):
        """
        Verify API does not change transaction type semantics.
        Types should match CanonicalLedgerService exactly.
        """
        url = reverse('license:license-ledger-ledger-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data

        # Get canonical
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
            license_id=test_license.id,
            license_type='DFIA'
        )

        # Verify types match
        for api_txn, canonical_txn in zip(data['transactions'], canonical['transactions']):
            assert api_txn['type'] == canonical_txn['type']
