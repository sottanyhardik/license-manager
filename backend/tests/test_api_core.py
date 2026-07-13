"""
API Tests for Core Endpoints (Companies, Ports, Exchange Rates)
"""
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.api
@pytest.mark.database
class TestCompanyAPI:
    """Test Company CRUD operations"""
    
    def test_list_companies(self, authenticated_client, test_company):
        """Test GET /masters/companies/"""
        url = reverse('masters:companymodel-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)
    
    def test_create_company(self, authenticated_client):
        """Test POST /masters/companies/"""
        url = reverse('masters:companymodel-list')
        import uuid
        data = {
            'iec': str(uuid.uuid4().int)[:10],  # required unique field
            'name': 'Test Company Ltd',
            'pan': 'ABCDE1234F',
            'gst_number': '27ABCDE1234F1Z5',
            'address_line_1': '123 Test Street',
            'address_line_2': 'Mumbai',
            'email': 'test@company.com'
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == data['name']
        assert response.data['pan'] == data['pan']
    
    def test_retrieve_company(self, authenticated_client, test_company):
        """Test GET /masters/companies/{id}/"""
        url = reverse('masters:companymodel-detail', kwargs={'pk': test_company.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == test_company.name
    
    def test_update_company(self, authenticated_client, test_company):
        """Test PATCH /masters/companies/{id}/"""
        url = reverse('masters:companymodel-detail', kwargs={'pk': test_company.id})
        data = {'name': 'Updated Company Name'}
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Company Name'
    
    def test_delete_company(self, authenticated_client, test_company_2):
        """Test DELETE /masters/companies/{id}/"""
        url = reverse('masters:companymodel-detail', kwargs={'pk': test_company_2.id})
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.api
@pytest.mark.database
class TestPortAPI:
    """Test Port CRUD operations"""
    
    def test_list_ports(self, authenticated_client, test_port):
        """Test GET /masters/ports/"""
        url = reverse('masters:portmodel-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_create_port(self, authenticated_client):
        """Test POST /masters/ports/"""
        url = reverse('masters:portmodel-list')
        data = {
            'code': 'INMUN1',
            'name': 'Mumbai Port',
            'country': 'India'
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['code'] == data['code']


@pytest.mark.api
@pytest.mark.database
class TestExchangeRateAPI:
    """Test Exchange Rate operations"""
    
    def test_list_exchange_rates(self, authenticated_client, test_exchange_rate):
        """Test GET /masters/exchange-rates/"""
        url = reverse('masters:exchangeratemodel-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_create_exchange_rate(self, authenticated_client):
        """Test POST /masters/exchange-rates/"""
        from datetime import datetime
        url = reverse('masters:exchangeratemodel-list')
        import uuid
        data = {
            'date': (datetime.now().date().replace(year=2020) + __import__('datetime').timedelta(days=int(uuid.uuid4().int) % 1000)).isoformat(),
            'usd': 84.50,
            'euro': 91.20,           # correct field name (not 'eur')
            'pound_sterling': 106.80, # correct field name (not 'gbp')
            'chinese_yuan': 11.60,    # required field
        }
        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert float(response.data['usd']) == data['usd']
