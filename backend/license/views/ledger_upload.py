"""
Ledger upload API endpoint for processing DFIA license ledger files.
"""
import io
import csv
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from scripts.ledger_parser_refactored import process_ledger_file


class LedgerUploadView(APIView):
    """
    API endpoint to upload and process ledger CSV files.

    POST /api/licenses/upload-ledger/

    Request:
        - Files: One or more CSV files with 'ledger' as the field name

    Response:
        {
            "message": "Successfully processed 3 licenses",
            "licenses": ["3011006401", "3011006402", "3011006403"],
            "stats": {
                "licenses_created": 2,
                "licenses_updated": 1,
                "total_transactions": 15
            }
        }
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """Process uploaded ledger file(s)."""
        files = request.FILES.getlist('ledger')

        if not files:
            return Response(
                {'error': 'No files uploaded. Please upload at least one CSV file.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        all_results = []

        for uploaded_file in files:
            try:
                # Validate file type
                if not uploaded_file.name.endswith('.csv'):
                    all_results.append({
                        'file': uploaded_file.name,
                        'success': False,
                        'error': 'Only CSV files are supported'
                    })
                    continue

                # Read and decode file
                try:
                    decoded_file = uploaded_file.read().decode('utf-8-sig')
                except UnicodeDecodeError:
                    decoded_file = uploaded_file.read().decode('latin-1')

                # Clean up the content
                decoded_file = decoded_file.replace(': ', '').replace(' ', '')

                # Process the ledger file
                created_licenses = process_ledger_file(decoded_file, is_csv=True)

                all_results.append({
                    'file': uploaded_file.name,
                    'success': True,
                    'licenses': created_licenses,
                    'count': len(created_licenses)
                })

            except Exception as e:
                all_results.append({
                    'file': uploaded_file.name,
                    'success': False,
                    'error': str(e)
                })

        # Aggregate results
        total_licenses = []
        failed_files = []

        for result in all_results:
            if result['success']:
                total_licenses.extend(result['licenses'])
            else:
                failed_files.append({
                    'file': result['file'],
                    'error': result['error']
                })

        # Build response
        response_data = {
            'message': f'Successfully processed {len(total_licenses)} license(s) from {len([r for r in all_results if r["success"]])} file(s)',
            'licenses': total_licenses,
            'stats': {
                'files_processed': len([r for r in all_results if r['success']]),
                'files_failed': len(failed_files),
                'total_licenses': len(total_licenses),
            }
        }

        if failed_files:
            response_data['failures'] = failed_files
            response_data['message'] += f' ({len(failed_files)} file(s) failed)'

        return Response(response_data, status=status.HTTP_200_OK)
