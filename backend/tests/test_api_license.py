"""
API Tests for License Endpoints
"""
from io import BytesIO

from openpyxl import load_workbook
import pytest
from django.urls import reverse
from rest_framework import status

from apps.license.models import LicenseDetailsModel


@pytest.mark.api
@pytest.mark.database
class TestLicenseAPI:
    """Test License CRUD operations"""
    
    def test_list_licenses(self, authenticated_client, test_license):
        """Test GET /licenses/"""
        url = reverse('license:licenses-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)
    
    def test_retrieve_license(self, authenticated_client, test_license):
        """Test GET /licenses/{id}/"""
        url = reverse('license:licenses-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['license_number'] == test_license.license_number
        assert 'import_license' in response.data
    
    def test_license_has_items(self, authenticated_client, test_license):
        """Test license includes related import items"""
        url = reverse('license:licenses-detail', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['import_license']) == 3
    
    def test_filter_licenses_by_scheme(self, authenticated_client, test_license):
        """Test GET /licenses/?scheme_code=DFIA"""
        url = reverse('license:licenses-list')
        response = authenticated_client.get(url, {'scheme_code': 'DFIA'})
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_search_licenses(self, authenticated_client, test_license):
        """Test GET /licenses/?search={license_number}"""
        url = reverse('license:licenses-list')
        response = authenticated_client.get(url, {'search': test_license.license_number[:5]})
        
        assert response.status_code == status.HTTP_200_OK

    def test_fetch_ledger_returns_explicit_not_configured_response(self, authenticated_client, test_license):
        """Remote DGFT ledger fetch is intentionally unsupported."""
        url = reverse('license:license-actions-fetch-ledger', kwargs={'pk': test_license.id})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
        assert response.data == {
            'success': False,
            'message': 'Remote DGFT ledger fetch is not configured. Use ledger upload instead.',
            'license_number': test_license.license_number,
        }

    def test_balance_excel_returns_expected_workbook_shape(self, authenticated_client, test_license):
        """Single-license balance Excel keeps its public workbook contract."""
        url = reverse('license:licenses-balance-excel', kwargs={'pk': test_license.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == (
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        assert (
            f'filename="{test_license.license_number}-summary.xlsx"'
            in response['Content-Disposition']
        )

        workbook = load_workbook(BytesIO(response.content), data_only=False)

        assert workbook.sheetnames == ['Summary']
        sheet = workbook['Summary']
        assert sheet['A1'].value.startswith(f'License No: {test_license.license_number}')
        assert sheet['A2'].value == 'Summary (BOE & Allotments)'
        assert any(
            cell.value == 'Summary (Balance Quantity)'
            for row in sheet.iter_rows()
            for cell in row
        )

    def test_bulk_balance_excel_returns_summary_and_license_sheets(
        self,
        authenticated_client,
        test_license,
    ):
        """Bulk balance Excel keeps the summary sheet plus per-license sheet."""
        url = reverse('license:licenses-bulk-balance-excel')
        response = authenticated_client.post(
            url,
            {'license_numbers': [test_license.license_number]},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == (
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        assert 'filename="bulk_license_summary.xlsx"' in response['Content-Disposition']

        workbook = load_workbook(BytesIO(response.content), data_only=False)

        assert workbook.sheetnames[0] == 'Utilization Planning Summary'
        assert test_license.license_number[:31] in workbook.sheetnames
        summary = workbook['Utilization Planning Summary']
        assert summary['A1'].value == 'UTILIZATION PLANNING SUMMARY'

    def test_bulk_balance_excel_rejects_non_list_license_numbers(self, authenticated_client, test_license):
        """Bulk balance Excel validates request shape before querying licenses."""
        url = reverse('license:licenses-bulk-balance-excel')
        response = authenticated_client.post(
            url,
            {'license_numbers': test_license.license_number},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            'error': 'license_numbers must be a non-empty list of strings.',
        }

    def test_bulk_balance_excel_summary_formulas_use_actual_duplicate_sheet_titles(
        self,
        authenticated_client,
        test_company,
        test_port,
    ):
        """Summary formulas point to OpenPyXL-renamed sheets when titles collide."""
        prefix = 'LIC-DUPLICATE-SHEET-NAME-12345'
        first = LicenseDetailsModel.objects.create(
            license_number=f'{prefix}A',
            exporter=test_company,
            port=test_port,
        )
        second = LicenseDetailsModel.objects.create(
            license_number=f'{prefix}B',
            exporter=test_company,
            port=test_port,
        )

        url = reverse('license:licenses-bulk-balance-excel')
        response = authenticated_client.post(
            url,
            {'license_numbers': [first.license_number, second.license_number]},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        workbook = load_workbook(BytesIO(response.content), data_only=False)
        sheet_titles = workbook.sheetnames[1:]
        assert len(sheet_titles) == 2
        assert len(set(sheet_titles)) == 2

        formulas = [
            cell.value
            for row in workbook['Utilization Planning Summary'].iter_rows()
            for cell in row
            if isinstance(cell.value, str) and cell.value.startswith("='")
        ]

        for title in sheet_titles:
            assert any(formula.startswith(f"='{title}'!") for formula in formulas)


@pytest.mark.api
@pytest.mark.database
class TestLicenseItemAPI:
    """Test License Import Item operations"""
    
    def test_list_license_items(self, authenticated_client, test_license):
        """Test GET /license-items/"""
        url = reverse('license:license-items-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_filter_items_by_license(self, authenticated_client, test_license):
        """Test GET /license-items/?license={id}"""
        url = reverse('license:license-items-list')
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
        
        url = reverse('license:upload-ledger')
        with open(csv_file, 'rb') as f:
            response = authenticated_client.post(url, {'ledger': f}, format='multipart')
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        assert 'message' in response.data or 'licenses' in response.data
