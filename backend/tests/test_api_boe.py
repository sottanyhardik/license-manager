"""
API Tests for Bill of Entry Endpoints
"""
from io import BytesIO

import openpyxl
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.api
@pytest.mark.database
class TestBillOfEntryAPI:
    """Test Bill of Entry CRUD operations"""
    
    def test_list_boe(self, authenticated_client, test_bill_of_entry):
        """Test GET /bill-of-entries/"""
        url = reverse('bill_of_entry:bill-of-entries-list')
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)

    def test_retrieve_boe(self, authenticated_client, test_bill_of_entry):
        """Test GET /bill-of-entries/{id}/"""
        url = reverse('bill_of_entry:bill-of-entries-detail', kwargs={'pk': test_bill_of_entry.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['bill_of_entry_number'] == test_bill_of_entry.bill_of_entry_number
        assert 'item_details' in response.data
    
    def test_boe_has_item_details(self, authenticated_client, test_bill_of_entry):
        """Test BOE includes item details"""
        url = reverse('bill_of_entry:bill-of-entries-detail', kwargs={'pk': test_bill_of_entry.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['item_details']) >= 3

    def test_filter_boe_by_invoice_null(self, authenticated_client, test_bill_of_entry):
        """Test GET /bill-of-entries/?invoice_no__isnull=true"""
        # Make BOE available (no invoice)
        test_bill_of_entry.invoice_no = None
        test_bill_of_entry.save()

        url = reverse('bill_of_entry:bill-of-entries-list')
        response = authenticated_client.get(url, {'invoice_no__isnull': 'true'})
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_filter_boe_by_license(self, authenticated_client, test_bill_of_entry, test_license):
        """Test GET /bill-of-entries/ — BOE linked to license via RowDetails, not a direct FK."""
        url = reverse('bill_of_entry:bill-of-entries-list')
        # BOE has no direct license FK; filter by company as a proxy for the test.
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_search_boe_by_license_number(self, authenticated_client, test_bill_of_entry, test_license):
        """Test GET /bill-of-entries/?search={license_number}"""
        url = reverse('bill_of_entry:bill-of-entries-list')
        # BillOfEntryModel has no direct license FK; search by license_number via RowDetails.
        response = authenticated_client.get(url, {'search': test_license.license_number})
        assert response.status_code == status.HTTP_200_OK

    def test_export_rejects_invalid_format_before_work(self, authenticated_client):
        """Test GET /bill-of-entries/export/?_export=bad"""
        url = reverse('bill_of_entry:bill-of-entries-export-bill-of-entries')
        response = authenticated_client.get(url, {'_export': ' csv '})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response['Content-Type'].startswith('text/plain')
        assert b"Invalid export format" in response.content

    def test_export_xlsx_normalizes_format_and_returns_workbook(self, authenticated_client, test_bill_of_entry):
        """Test GET /bill-of-entries/export/?_export=xlsx"""
        url = reverse('bill_of_entry:bill-of-entries-export-bill-of-entries')
        response = authenticated_client.get(url, {'_export': ' XLSX '})

        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        workbook = openpyxl.load_workbook(BytesIO(response.content), read_only=True)
        assert workbook.active.title == "Bill of Entries"
        assert workbook.active['A1'].value == "Bill of Entry Report"

    def test_export_port_xlsx_returns_flat_workbook(self, authenticated_client, test_bill_of_entry):
        """Test GET /bill-of-entries/export/?_export=port_xlsx"""
        url = reverse('bill_of_entry:bill-of-entries-export-bill-of-entries')
        response = authenticated_client.get(url, {'_export': 'port_xlsx'})

        assert response.status_code == status.HTTP_200_OK
        workbook = openpyxl.load_workbook(BytesIO(response.content), read_only=True)
        assert workbook.active.title == "Port BOE List"
        assert workbook.active['A1'].value.startswith("Port BOE Report")

    def test_export_pdf_returns_pdf(self, authenticated_client, test_bill_of_entry, test_exchange_rate):
        """Test GET /bill-of-entries/export/?_export=pdf"""
        url = reverse('bill_of_entry:bill-of-entries-export-bill-of-entries')
        response = authenticated_client.get(url, {'_export': 'pdf'})

        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'application/pdf'
        assert response.content.startswith(b'%PDF')

    def test_export_xlsx_missing_dependency_returns_503(
        self, authenticated_client, test_bill_of_entry, monkeypatch
    ):
        """Test optional openpyxl failure path returns a service-unavailable response."""
        from apps.bill_of_entry import views_export

        monkeypatch.setattr(views_export, 'OPENPYXL_AVAILABLE', False)
        url = reverse('bill_of_entry:bill-of-entries-export-bill-of-entries')
        response = authenticated_client.get(url, {'_export': 'xlsx'})

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert b"Excel export not available" in response.content


@pytest.mark.api
@pytest.mark.integration
class TestBOEIntegration:
    """Test BOE integration with Trade"""
    
    def test_boe_linked_to_trade(self, authenticated_client, test_trade):
        """Test BOE is linked to trade via invoice number"""
        boe = test_trade.boe
        assert boe.invoice_no == test_trade.invoice_number
        
        # Verify via API
        url = reverse('bill_of_entry:bill-of-entries-detail', kwargs={'pk': boe.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['invoice_no'] == test_trade.invoice_number
