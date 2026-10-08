"""Tests for auto-creation of HS codes during PDF parsing"""
from unittest.mock import patch
from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from apps.accounts.permissions import LicensePermission
from apps.core.models import HSCodeModel, PortModel, NotificationNumber, SchemeCode
from apps.license.tests.conftest import SAMPLE_PDF_DATA

User = get_user_model()


class ParsePdfHSCodeAutoCreateTestCase(TestCase):
    """Test auto-creation of HS codes during PDF parsing"""

    def setUp(self):
        """Create test user with license permission"""
        self.user = User.objects.create_user('testuser', 'test@test.com', 'password123')
        self.user.is_staff = True
        self.user.save()

        self.client = Client()
        self.client.login(username='testuser', password='password123')

        # Create required master data
        PortModel.objects.get_or_create(code='TEST', defaults={'name': 'Test Port'})
        NotificationNumber.objects.get_or_create(code='025/2023', defaults={'label': '025/2023'})
        SchemeCode.objects.get_or_create(code='26', defaults={'label': 'DFIA'})

    @patch('apps.license.views.parse_pdf.parse_dfia_pdf')
    def test_auto_create_hs_code_for_unmatched_hsn(self, mock_parse):
        """Test that unmatched HSNs are created as new HS codes"""
        # Mock PDF data with an unmatched HSN
        mock_parse.return_value = {
            'license_number': '3411008564',
            'license_date': '2026-10-06',
            'license_expiry_date': '2027-10-06',
            'company_name': 'Test Company',
            'iec': 'TEST123',
            'port_code': 'TEST',
            'notification_number': '025/2023',
            'items': [
                {
                    'serial_number': 1,
                    'hsn': '27101100',
                    'description': 'Coal products',
                    'quantity': 100.0,
                    'uom': 'KGS',
                    'cif_inr': 85000.0,
                    'cif_fc': 1000.0,
                }
            ],
            'source_kind': 'digital',
        }

        # Ensure HSN doesn't exist
        HSCodeModel.objects.filter(hs_code='27101100').delete()

        # Parse the PDF with auto-create enabled
        response = self.client.post(
            '/api/licenses/parse-pdf/',
            {'file': b'fake pdf'},
            content_type='multipart/form-data'
        )

        assert response.status_code == 200
        data = response.json()

        # Verify HS code was created
        assert data['hs_codes_created'] == 1
        assert len(data['items']) == 1
        assert data['items'][0]['matched_hs_code_id'] is not None
        assert data['items'][0]['hs_code_created'] is True

        # Verify it exists in DB
        hs = HSCodeModel.objects.get(hs_code='27101100')
        assert hs.product_description == 'Coal products'

    @patch('apps.license.views.parse_pdf.parse_dfia_pdf')
    def test_matched_hs_code_not_created(self, mock_parse):
        """Test that matched HS codes are not created again"""
        # Create an HS code first
        existing_hs = HSCodeModel.objects.create(hs_code='27101200', product_description='Coal briquettes')

        mock_parse.return_value = {
            'license_number': '3411008565',
            'license_date': '2026-10-06',
            'license_expiry_date': '2027-10-06',
            'company_name': 'Test Company',
            'iec': 'TEST123',
            'port_code': 'TEST',
            'notification_number': '025/2023',
            'items': [
                {
                    'serial_number': 1,
                    'hsn': '27101200',
                    'description': 'Coal briquettes',
                    'quantity': 100.0,
                    'uom': 'KGS',
                    'cif_inr': 85000.0,
                    'cif_fc': 1000.0,
                }
            ],
            'source_kind': 'digital',
        }

        # Parse the PDF
        response = self.client.post(
            '/api/licenses/parse-pdf/',
            {'file': b'fake pdf'},
            content_type='multipart/form-data'
        )

        assert response.status_code == 200
        data = response.json()

        # Verify no new HS code was created
        assert data['hs_codes_created'] == 0
        assert data['items'][0]['matched_hs_code_id'] == existing_hs.id
        assert data['items'][0]['hs_code_created'] is False

    @patch('apps.license.views.parse_pdf.parse_dfia_pdf')
    def test_disable_hs_code_creation(self, mock_parse):
        """Test that HS code creation can be disabled"""
        mock_parse.return_value = {
            'license_number': '3411008566',
            'license_date': '2026-10-06',
            'license_expiry_date': '2027-10-06',
            'company_name': 'Test Company',
            'iec': 'TEST123',
            'port_code': 'TEST',
            'notification_number': '025/2023',
            'items': [
                {
                    'serial_number': 1,
                    'hsn': '27101300',
                    'description': 'New coal type',
                    'quantity': 100.0,
                    'uom': 'KGS',
                    'cif_inr': 85000.0,
                    'cif_fc': 1000.0,
                }
            ],
            'source_kind': 'digital',
        }

        # Ensure HSN doesn't exist
        HSCodeModel.objects.filter(hs_code='27101300').delete()

        # Parse with create_hs_code=false
        response = self.client.post(
            '/api/licenses/parse-pdf/',
            {'file': b'fake pdf', 'create_hs_code': 'false'},
            content_type='multipart/form-data'
        )

        assert response.status_code == 200
        data = response.json()

        # Verify no HS code was created
        assert data['hs_codes_created'] == 0
        assert data['items'][0]['matched_hs_code_id'] is None
        assert data['items'][0]['hs_code_created'] is False

    @patch('apps.license.views.parse_pdf.parse_dfia_pdf')
    def test_no_create_for_duplicate_license(self, mock_parse):
        """Test that HS codes are not created when re-parsing a duplicate license"""
        # Create an initial license
        mock_parse.return_value = {
            'license_number': '3411008567',
            'license_date': '2026-10-06',
            'license_expiry_date': '2027-10-06',
            'company_name': 'Test Company',
            'iec': 'TEST123',
            'port_code': 'TEST',
            'notification_number': '025/2023',
            'items': [
                {
                    'serial_number': 1,
                    'hsn': '27101400',
                    'description': 'Test coal',
                    'quantity': 100.0,
                    'uom': 'KGS',
                    'cif_inr': 85000.0,
                    'cif_fc': 1000.0,
                }
            ],
            'source_kind': 'digital',
        }

        # Clear HSN
        HSCodeModel.objects.filter(hs_code='27101400').delete()

        # First parse - should create HS code
        response1 = self.client.post(
            '/api/licenses/parse-pdf/',
            {'file': b'fake pdf'},
            content_type='multipart/form-data'
        )
        assert response1.json()['hs_codes_created'] == 1
        created_hs_id = response1.json()['items'][0]['matched_hs_code_id']

        # Second parse (duplicate) - should NOT create another
        response2 = self.client.post(
            '/api/licenses/parse-pdf/',
            {'file': b'fake pdf'},
            content_type='multipart/form-data'
        )
        assert response2.json()['hs_codes_created'] == 0
        assert response2.json()['items'][0]['matched_hs_code_id'] == created_hs_id

    @patch('apps.license.views.parse_pdf.parse_dfia_pdf')
    def test_invalid_hsn_not_created(self, mock_parse):
        """Test that invalid HSNs are not created"""
        mock_parse.return_value = {
            'license_number': '3411008568',
            'license_date': '2026-10-06',
            'license_expiry_date': '2027-10-06',
            'company_name': 'Test Company',
            'iec': 'TEST123',
            'port_code': 'TEST',
            'notification_number': '025/2023',
            'items': [
                {
                    'serial_number': 1,
                    'hsn': 'INVALID',  # Non-numeric
                    'description': 'Invalid HSN',
                    'quantity': 100.0,
                    'uom': 'KGS',
                    'cif_inr': 85000.0,
                    'cif_fc': 1000.0,
                }
            ],
            'source_kind': 'digital',
        }

        # Parse the PDF
        response = self.client.post(
            '/api/licenses/parse-pdf/',
            {'file': b'fake pdf'},
            content_type='multipart/form-data'
        )

        assert response.status_code == 200
        data = response.json()

        # Invalid HSN should not be created
        assert data['hs_codes_created'] == 0
        assert data['items'][0]['matched_hs_code_id'] is None
        assert data['items'][0]['hs_code_created'] is False
