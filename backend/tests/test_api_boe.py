"""
API Tests for Bill of Entry Endpoints
"""
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.api
@pytest.mark.database
class TestBillOfEntryAPI:
    """Test Bill of Entry CRUD operations"""
    
    def test_list_boe(self, authenticated_client, test_bill_of_entry):
        """Test GET /bill-of-entries/"""
        url = reverse('billofentry-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)
    
    def test_retrieve_boe(self, authenticated_client, test_bill_of_entry):
        """Test GET /bill-of-entries/{id}/"""
        url = reverse('billofentry-detail', kwargs={'pk': test_bill_of_entry.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['bill_of_entry_number'] == test_bill_of_entry.bill_of_entry_number
        assert 'item_details' in response.data
    
    def test_boe_has_item_details(self, authenticated_client, test_bill_of_entry):
        """Test BOE includes item details"""
        url = reverse('billofentry-detail', kwargs={'pk': test_bill_of_entry.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['item_details']) >= 3
    
    def test_filter_boe_by_invoice_null(self, authenticated_client, test_bill_of_entry):
        """Test GET /bill-of-entries/?invoice_no__isnull=true"""
        # Make BOE available (no invoice)
        test_bill_of_entry.invoice_no = None
        test_bill_of_entry.save()
        
        url = reverse('billofentry-list')
        response = authenticated_client.get(url, {'invoice_no__isnull': 'true'})
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_filter_boe_by_license(self, authenticated_client, test_bill_of_entry):
        """Test GET /bill-of-entries/?license={id}"""
        url = reverse('billofentry-list')
        response = authenticated_client.get(url, {'license': test_bill_of_entry.license.id})
        
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.api
@pytest.mark.integration
class TestBOEIntegration:
    """Test BOE integration with Trade"""
    
    def test_boe_linked_to_trade(self, authenticated_client, test_trade):
        """Test BOE is linked to trade via invoice number"""
        boe = test_trade.boe
        assert boe.invoice_no == test_trade.invoice_number
        
        # Verify via API
        url = reverse('billofentry-detail', kwargs={'pk': boe.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['invoice_no'] == test_trade.invoice_number
