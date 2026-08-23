"""
API Tests for Allotment Endpoints
"""
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.allotment.models import AllotmentItems


@pytest.mark.api
@pytest.mark.database
class TestAllotmentAPI:
    """Test Allotment CRUD operations"""
    
    def test_list_allotments(self, authenticated_client, test_allotment):
        """Test GET /allotments/"""
        url = reverse('allotment:allotment-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)
    
    def test_create_allotment(self, authenticated_client, fake_allotment_data):
        """Test POST /allotments/"""
        url = reverse('allotment:allotment-list')
        response = authenticated_client.post(url, fake_allotment_data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['item_name'] == fake_allotment_data['item_name']
    
    def test_retrieve_allotment(self, authenticated_client, test_allotment):
        """Test GET /allotments/{id}/"""
        url = reverse('allotment:allotment-detail', kwargs={'pk': test_allotment.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['item_name'] == test_allotment.item_name
    
    def test_update_allotment(self, authenticated_client, test_allotment):
        """Test PATCH /allotments/{id}/"""
        url = reverse('allotment:allotment-detail', kwargs={'pk': test_allotment.id})
        data = {'required_quantity': 2000.0}
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert float(response.data['required_quantity']) == 2000.0
    
    def test_delete_allotment(self, authenticated_client, test_allotment):
        """Test DELETE /allotments/{id}/"""
        url = reverse('allotment:allotment-detail', kwargs={'pk': test_allotment.id})
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_filter_allotments_by_company(self, authenticated_client, test_allotment):
        """Test GET /allotments/?company={id}"""
        url = reverse('allotment:allotment-list')
        response = authenticated_client.get(url, {'company': test_allotment.company.id})
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_filter_allotments_by_approved(self, authenticated_client, test_allotment):
        """Test GET /allotments/?is_approved=false"""
        url = reverse('allotment:allotment-list')
        response = authenticated_client.get(url, {'is_approved': 'false'})
        
        assert response.status_code == status.HTTP_200_OK

    def test_download_grouped_export_rejects_invalid_format(self, authenticated_client):
        url = reverse('allotment:allotment-download-grouped-export')

        response = authenticated_client.get(url, {'_export': 'csv'})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response['Content-Type'].startswith('text/plain')
        assert b"Invalid export format" in response.content

    def test_download_grouped_export_xlsx(self, authenticated_client, test_allotment, test_license):
        item = test_license.import_license.first()
        AllotmentItems.objects.create(
            item=item,
            allotment=test_allotment,
            qty=Decimal("100.000"),
            cif_fc=Decimal("250.00"),
            cif_inr=Decimal("21125.00"),
        )
        test_allotment.is_allotted = True
        test_allotment.save(update_fields=["is_allotted"])
        url = reverse('allotment:allotment-download-grouped-export')

        response = authenticated_client.get(url, {'_export': ' xlsx '})

        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert 'filename="Allotment Report - ' in response['Content-Disposition']
        assert response.content.startswith(b'PK')

    def test_download_grouped_export_pdf(self, authenticated_client, test_allotment, test_license):
        item = test_license.import_license.first()
        AllotmentItems.objects.create(
            item=item,
            allotment=test_allotment,
            qty=Decimal("100.000"),
            cif_fc=Decimal("250.00"),
            cif_inr=Decimal("21125.00"),
        )
        test_allotment.is_allotted = True
        test_allotment.save(update_fields=["is_allotted"])
        url = reverse('allotment:allotment-download-grouped-export')

        response = authenticated_client.get(url, {'_export': ' PDF '})

        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'application/pdf'
        assert response.content.startswith(b'%PDF')

    def test_download_grouped_export_missing_xlsx_dependency(self, authenticated_client, monkeypatch):
        monkeypatch.setattr("apps.allotment.views_export.OPENPYXL_AVAILABLE", False)
        url = reverse('allotment:allotment-download-grouped-export')

        response = authenticated_client.get(url, {'_export': 'xlsx'})

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert b"Excel export not available" in response.content
