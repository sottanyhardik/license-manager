"""
API Tests for Trade Endpoints
"""
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.api
@pytest.mark.database
class TestTradeAPI:
    """Test Trade CRUD operations"""
    
    def test_list_trades(self, authenticated_client, test_trade):
        """Test GET /trades/"""
        url = reverse('trade-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)
    
    def test_retrieve_trade(self, authenticated_client, test_trade):
        """Test GET /trades/{id}/"""
        url = reverse('trade-detail', kwargs={'pk': test_trade.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['invoice_number'] == test_trade.invoice_number
        assert 'lines' in response.data
    
    def test_create_trade(self, authenticated_client, fake_trade_data):
        """Test POST /trades/"""
        url = reverse('trade-list')
        response = authenticated_client.post(url, fake_trade_data, format='json')
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
    
    def test_trade_has_lines(self, authenticated_client, test_trade):
        """Test trade includes trade lines"""
        url = reverse('trade-detail', kwargs={'pk': test_trade.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['lines']) >= 2
    
    def test_filter_trades_by_direction(self, authenticated_client, test_trade):
        """Test GET /trades/?direction=PURCHASE"""
        url = reverse('trade-list')
        response = authenticated_client.get(url, {'direction': 'PURCHASE'})
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_filter_trades_by_company(self, authenticated_client, test_trade):
        """Test GET /trades/?from_company={id}"""
        url = reverse('trade-list')
        response = authenticated_client.get(url, {'from_company': test_trade.from_company.id})
        
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.api
@pytest.mark.integration
class TestTradeBillOfSupply:
    """Test Trade Bill of Supply generation"""
    
    def test_generate_bill_of_supply(self, authenticated_client, test_trade):
        """Test GET /trades/{id}/generate-bill-of-supply/"""
        # First make it a SALE trade
        test_trade.direction = 'SALE'
        test_trade.save()
        
        url = reverse('trade-generate-bill-of-supply', kwargs={'pk': test_trade.id})
        response = authenticated_client.get(url, {'include_signature': 'true'})
        
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'application/pdf'


@pytest.mark.api
@pytest.mark.database
class TestLicenseLedgerAPI:
    """Test License Ledger endpoints"""
    
    def test_license_ledger_view(self, authenticated_client, test_license):
        """Test GET /ledger/license-ledger/"""
        url = reverse('license-ledger')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_license_ledger_detail(self, authenticated_client, test_license):
        """Test GET /ledger/license-ledger/{license_number}/"""
        url = reverse('license-ledger-detail', kwargs={'license_number': test_license.license_number})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'transactions' in response.data
