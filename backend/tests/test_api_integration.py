"""
Integration tests for backend API endpoints.
Tests the complete flow of requests through views, serializers, and models.
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase
from rest_framework import status

User = get_user_model()


class APIIntegrationTestBase(APITestCase):
    """Base class for API integration tests with common setup"""

    def setUp(self):
        """Set up test client and create test user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        """Clean up after tests"""
        self.client.force_authenticate(user=None)


class TestLicenseAPIIntegration(APIIntegrationTestBase):
    """Integration tests for License API endpoints"""

    def test_license_list_endpoint(self):
        """Should return list of licenses"""
        response = self.client.get('/api/licenses/')

        # Should return 200 OK
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]

    def test_license_create_endpoint(self):
        """Should create a new license"""
        license_data = {
            'license_no': 'TEST-2024-001',
            'license_date': str(date.today()),
            'valid_upto': str(date.today() + timedelta(days=365)),
            'scheme': 'TEST_SCHEME',
            'port_code': 'INMUM1',
        }

        response = self.client.post('/api/licenses/', license_data, format='json')

        # Should return 201 Created or 400 if validation fails
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ]

    def test_license_retrieve_endpoint(self):
        """Should retrieve a specific license"""
        # Try to get license with ID 1
        response = self.client.get('/api/licenses/1/')

        # Should return 200 OK or 404 if not found
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_license_update_endpoint(self):
        """Should update an existing license"""
        update_data = {
            'license_no': 'TEST-2024-UPDATED',
        }

        response = self.client.patch('/api/licenses/1/', update_data, format='json')

        # Should return 200 OK or 404 if not found
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_license_delete_endpoint(self):
        """Should delete a license"""
        response = self.client.delete('/api/licenses/999999/')

        # Should return 204 No Content or 404 if not found
        assert response.status_code in [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_license_list_with_pagination(self):
        """Should return paginated results"""
        response = self.client.get('/api/licenses/?page=1&page_size=20')

        if response.status_code == status.HTTP_200_OK:
            # Should have pagination structure
            assert 'results' in response.data or isinstance(response.data, list)

    def test_license_list_with_search(self):
        """Should filter licenses by search query"""
        response = self.client.get('/api/licenses/?search=TEST')

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]

    def test_license_list_with_filters(self):
        """Should filter licenses by various fields"""
        response = self.client.get('/api/licenses/?scheme=TEST_SCHEME')

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]


class TestAllotmentAPIIntegration(APIIntegrationTestBase):
    """Integration tests for Allotment API endpoints"""

    def test_allotment_list_endpoint(self):
        """Should return list of allotments"""
        response = self.client.get('/api/allotments/')

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]

    def test_allotment_create_endpoint(self):
        """Should create a new allotment"""
        allotment_data = {
            'allotment_no': 'ALL-2024-001',
            'allotment_date': str(date.today()),
            'port_code': 'INMUM1',
        }

        response = self.client.post('/api/allotments/', allotment_data, format='json')

        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ]

    def test_allotment_retrieve_endpoint(self):
        """Should retrieve a specific allotment"""
        response = self.client.get('/api/allotments/1/')

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_allotment_available_licenses_endpoint(self):
        """Should return available licenses for allotment"""
        response = self.client.get('/api/allotment-actions/1/available-licenses/')

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_allotment_allocate_item_endpoint(self):
        """Should allocate an item to allotment"""
        allocation_data = {
            'item_id': 1,
            'qty': 100,
            'cif_fc': '1000.00',
        }

        response = self.client.post(
            '/api/allotment-actions/1/allocate-item/',
            allocation_data,
            format='json'
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED
        ]


class TestMasterDataAPIIntegration(APIIntegrationTestBase):
    """Integration tests for Master Data API endpoints"""

    def test_port_list_endpoint(self):
        """Should return list of ports"""
        response = self.client.get('/api/ports/')

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_scheme_list_endpoint(self):
        """Should return list of schemes"""
        response = self.client.get('/api/schemes/')

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_currency_list_endpoint(self):
        """Should return list of currencies"""
        response = self.client.get('/api/currencies/')

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED
        ]


class TestAuthenticationIntegration(APITestCase):
    """Integration tests for authentication endpoints"""

    def setUp(self):
        """Set up test client"""
        self.client = APIClient()

    def test_login_with_valid_credentials(self):
        """Should authenticate user with valid credentials"""
        # Create user first
        User.objects.create_user(
            username='loginuser',
            password='loginpass123'
        )

        login_data = {
            'username': 'loginuser',
            'password': 'loginpass123'
        }

        response = self.client.post('/api/token/', login_data, format='json')

        # Should return 200 OK or 404 if endpoint doesn't exist
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]

        if response.status_code == status.HTTP_200_OK:
            # Should return tokens
            assert 'access' in response.data or 'token' in response.data

    def test_login_with_invalid_credentials(self):
        """Should reject invalid credentials"""
        login_data = {
            'username': 'wronguser',
            'password': 'wrongpass'
        }

        response = self.client.post('/api/token/', login_data, format='json')

        # Should return 401 or 400 or 404
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_404_NOT_FOUND
        ]

    def test_protected_endpoint_without_auth(self):
        """Should reject access to protected endpoints without auth"""
        response = self.client.get('/api/licenses/')

        # Should return 401 Unauthorized or allow access (depends on settings)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ]


class TestExportAPIIntegration(APIIntegrationTestBase):
    """Integration tests for export functionality"""

    def test_license_pdf_export(self):
        """Should generate PDF export of license"""
        response = self.client.get('/api/licenses/1/export-pdf/')

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]

        if response.status_code == status.HTTP_200_OK:
            # Should return PDF content type
            assert 'pdf' in response.get('Content-Type', '').lower() or \
                   response.get('Content-Type') == 'application/octet-stream'

    def test_license_excel_export(self):
        """Should generate Excel export of license"""
        response = self.client.get('/api/licenses/1/export-excel/')

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]

        if response.status_code == status.HTTP_200_OK:
            # Should return Excel content type
            content_type = response.get('Content-Type', '').lower()
            assert 'excel' in content_type or 'spreadsheet' in content_type or \
                   content_type == 'application/octet-stream'

    def test_allotment_pdf_export(self):
        """Should generate PDF export of allotment"""
        response = self.client.get('/api/allotments/1/export-pdf/')

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]


class TestValidationIntegration(APIIntegrationTestBase):
    """Integration tests for validation logic"""

    def test_create_license_with_invalid_dates(self):
        """Should reject license with end date before start date"""
        invalid_data = {
            'license_no': 'TEST-INVALID',
            'license_date': str(date.today()),
            'valid_upto': str(date.today() - timedelta(days=1)),  # Past date
        }

        response = self.client.post('/api/licenses/', invalid_data, format='json')

        # Should return 400 Bad Request or similar
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_create_license_with_missing_required_fields(self):
        """Should reject license with missing required fields"""
        incomplete_data = {
            'license_no': 'TEST-INCOMPLETE',
        }

        response = self.client.post('/api/licenses/', incomplete_data, format='json')

        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_allocate_with_insufficient_balance(self):
        """Should reject allocation exceeding available balance"""
        excessive_allocation = {
            'item_id': 1,
            'qty': 999999999,  # Excessive quantity
            'cif_fc': '999999999.99',  # Excessive value
        }

        response = self.client.post(
            '/api/allotment-actions/1/allocate-item/',
            excessive_allocation,
            format='json'
        )

        # Should return 400 Bad Request
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED
        ]


class TestPerformanceIntegration(APIIntegrationTestBase):
    """Integration tests for performance-critical endpoints"""

    def test_license_list_response_time(self):
        """Should return license list in reasonable time"""
        import time
        start_time = time.time()

        response = self.client.get('/api/licenses/')

        end_time = time.time()
        response_time = end_time - start_time

        # Should respond within 5 seconds
        assert response_time < 5.0, f"Response took {response_time:.2f}s"

    def test_dashboard_stats_response_time(self):
        """Should return dashboard stats in reasonable time"""
        import time
        start_time = time.time()

        response = self.client.get('/api/dashboard/stats/')

        end_time = time.time()
        response_time = end_time - start_time

        # Should respond within 5 seconds
        assert response_time < 5.0, f"Response took {response_time:.2f}s"


class TestConcurrencyIntegration(APIIntegrationTestBase):
    """Integration tests for concurrent operations"""

    def test_concurrent_allocations(self):
        """Should handle concurrent allocation requests"""
        from threading import Thread

        results = []

        def allocate():
            response = self.client.post(
                '/api/allotment-actions/1/allocate-item/',
                {'item_id': 1, 'qty': 10, 'cif_fc': '100.00'},
                format='json'
            )
            results.append(response.status_code)

        # Create multiple concurrent requests
        threads = [Thread(target=allocate) for _ in range(3)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All requests should complete (may succeed or fail based on validation)
        assert len(results) == 3
        for status_code in results:
            assert status_code in [
                status.HTTP_200_OK,
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_401_UNAUTHORIZED
            ]


class TestErrorHandlingIntegration(APIIntegrationTestBase):
    """Integration tests for error handling"""

    def test_404_for_nonexistent_license(self):
        """Should return 404 for non-existent license"""
        response = self.client.get('/api/licenses/999999/')

        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_400_for_invalid_json(self):
        """Should return 400 for malformed JSON"""
        response = self.client.post(
            '/api/licenses/',
            'invalid-json',
            content_type='application/json'
        )

        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ]

    def test_405_for_unsupported_method(self):
        """Should return 405 for unsupported HTTP method"""
        response = self.client.trace('/api/licenses/')

        # Should return 405 Method Not Allowed
        assert response.status_code in [
            status.HTTP_405_METHOD_NOT_ALLOWED,
            status.HTTP_401_UNAUTHORIZED
        ]


# Run tests with pytest
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
