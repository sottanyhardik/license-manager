"""
API Tests for Allotment Endpoints
"""
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.api
@pytest.mark.database
class TestAllotmentAPI:
    """Test Allotment CRUD operations"""
    
    def test_list_allotments(self, authenticated_client, test_allotment):
        """Test GET /allotments/"""
        url = reverse('allotment-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)
    
    def test_create_allotment(self, authenticated_client, fake_allotment_data):
        """Test POST /allotments/"""
        url = reverse('allotment-list')
        response = authenticated_client.post(url, fake_allotment_data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['item_name'] == fake_allotment_data['item_name']
    
    def test_retrieve_allotment(self, authenticated_client, test_allotment):
        """Test GET /allotments/{id}/"""
        url = reverse('allotment-detail', kwargs={'pk': test_allotment.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['item_name'] == test_allotment.item_name
    
    def test_update_allotment(self, authenticated_client, test_allotment):
        """Test PATCH /allotments/{id}/"""
        url = reverse('allotment-detail', kwargs={'pk': test_allotment.id})
        data = {'required_quantity': 2000.0}
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert float(response.data['required_quantity']) == 2000.0
    
    def test_delete_allotment(self, authenticated_client, test_allotment):
        """Test DELETE /allotments/{id}/"""
        url = reverse('allotment-detail', kwargs={'pk': test_allotment.id})
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_filter_allotments_by_company(self, authenticated_client, test_allotment):
        """Test GET /allotments/?company={id}"""
        url = reverse('allotment-list')
        response = authenticated_client.get(url, {'company': test_allotment.company.id})
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_filter_allotments_by_approved(self, authenticated_client, test_allotment):
        """Test GET /allotments/?is_approved=false"""
        url = reverse('allotment-list')
        response = authenticated_client.get(url, {'is_approved': 'false'})
        
        assert response.status_code == status.HTTP_200_OK
