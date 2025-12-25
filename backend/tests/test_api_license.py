"""
API Tests for License Endpoints
"""
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.api
@pytest.mark.database
class TestLicenseAPI:
    """Test License CRUD operations"""
    
    def test_list_licenses(self, authenticated_client, test_license):
        """Test GET /licenses/"""
        url = reverse('license-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)
    
    def test_retrieve_license(self, authenticated_client, test_license):
        """Test GET /licenses/{id}/"""
        url = reverse('license-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['license_number'] == test_license.license_number
        assert 'import_items' in response.data
    
    def test_license_has_items(self, authenticated_client, test_license):
        """Test license includes related import items"""
        url = reverse('license-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['import_items']) == 3
    
    def test_filter_licenses_by_scheme(self, authenticated_client, test_license):
        """Test GET /licenses/?scheme_code=DFIA"""
        url = reverse('license-list')
        response = authenticated_client.get(url, {'scheme_code': 'DFIA'})
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_search_licenses(self, authenticated_client, test_license):
        """Test GET /licenses/?search={license_number}"""
        url = reverse('license-list')
        response = authenticated_client.get(url, {'search': test_license.license_number[:5]})
        
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.api
@pytest.mark.database
class TestLicenseItemAPI:
    """Test License Import Item operations"""
    
    def test_list_license_items(self, authenticated_client, test_license):
        """Test GET /license-items/"""
        url = reverse('licenseimportitem-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_filter_items_by_license(self, authenticated_client, test_license):
        """Test GET /license-items/?license={id}"""
        url = reverse('licenseimportitem-list')
        response = authenticated_client.get(url, {'license': test_license.id})
        
        assert response.status_code == status.HTTP_200_OK
        if 'results' in response.data:
            assert len(response.data['results']) == 3


@pytest.mark.api
@pytest.mark.integration
class TestLicenseLedgerUpload:
    """Test License Ledger CSV Upload"""
    
    def test_upload_ledger_csv(self, authenticated_client, tmp_path):
        """Test POST /upload-ledger/ with CSV file"""
        # Create a fake CSV file
        csv_content = """Regn.No.,Regn.Date,Lic.No.,Lic.Date,IEC,Scheme.Cd.,Port,Notification
1234,01/01/2024,0310831825,01/01/2024,0123456789,DFIA,INMUN1,NOTIFICATION
"""
        csv_file = tmp_path / "test_ledger.csv"
        csv_file.write_text(csv_content)
        
        url = reverse('upload-ledger')
        with open(csv_file, 'rb') as f:
            response = authenticated_client.post(url, {'ledger': f}, format='multipart')
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        assert 'message' in response.data or 'licenses' in response.data
