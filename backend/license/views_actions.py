# license/views_actions.py
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from license.models import LicenseDetailsModel
from license.ledger_pdf import generate_license_ledger_pdf


class LicenseActionViewSet(ViewSet):
    """
    ViewSet for license actions like downloading ledger
    """

    @action(detail=True, methods=['get'], url_path='download-ledger')
    def download_ledger(self, request, pk=None):
        """
        Download detailed ledger PDF for a license.
        Groups items by head and shows:
        - Import items with quantities and CIF
        - Allotments (pending BOE)
        - Bill of Entry (debited)
        - Available balance
        """
        license_obj = get_object_or_404(
            LicenseDetailsModel.objects.prefetch_related(
                'import_license__items__head',
                'import_license__allotment_details__allotment__company',
                'import_license__hs_code',
                'exporter',
                'port'
            ),
            pk=pk
        )

        try:
            # Generate PDF grouped by item
            pdf_content = generate_license_ledger_pdf(license_obj)

            # Create response
            response = HttpResponse(pdf_content, content_type='application/pdf')
            filename = f"License_Ledger_{license_obj.license_number}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            return response

        except Exception as e:
            return Response(
                {'error': f'Failed to generate PDF: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
