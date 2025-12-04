"""
Ledger upload API endpoint for processing DFIA license ledger files.
"""
import csv
import io

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from scripts.parse_ledger import parse_license_data, create_object


@method_decorator(csrf_exempt, name='dispatch')
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

    permission_classes = []  # Allow access without authentication for now
    parser_classes = [MultiPartParser, FormParser]
    authentication_classes = []  # Disable authentication requirements
    http_method_names = ['post', 'options']  # Explicitly allow POST and OPTIONS

    def post(self, request):
        """Process uploaded ledger file(s)."""
        files = request.FILES.getlist('ledger')

        if not files:
            return Response(
                {'error': 'No files uploaded. Please upload at least one CSV file.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        all_results = []
        total_licenses = []

        # Max file size: 50MB
        MAX_FILE_SIZE = 50 * 1024 * 1024

        for file_sequence_number, uploaded_file in enumerate(files, start=1):
            try:
                # Validate file type
                if not uploaded_file.name.endswith('.csv'):
                    all_results.append({
                        'file': uploaded_file.name,
                        'success': False,
                        'error': 'Only CSV files are supported'
                    })
                    continue

                # Validate file size
                if uploaded_file.size > MAX_FILE_SIZE:
                    all_results.append({
                        'file': uploaded_file.name,
                        'success': False,
                        'error': f'File size exceeds maximum limit of {MAX_FILE_SIZE // (1024 * 1024)}MB'
                    })
                    continue

                # Read file in chunks for large files
                file_content = b''
                for chunk in uploaded_file.chunks():
                    file_content += chunk

                # Decode the uploaded file and wrap it for csv.reader
                decoded_file = file_content.decode('utf-8-sig')
                decoded_file = decoded_file.replace(': ', '')
                decoded_file = decoded_file.replace(' ', '')
                decoded_file = decoded_file.replace(':\xa0', '')
                csvfile = io.StringIO(decoded_file)

                reader = csv.reader(csvfile)

                # Read all rows, skipping empty ones
                rows = []
                for row in reader:
                    if not any(field.strip() for field in row):
                        continue
                    rows.append(row)

                # Parse the CSV data into license dictionaries
                dict_list = parse_license_data(rows)

                # Create/update license objects
                created_license_numbers = []
                for dict_data in dict_list:
                    license_number = create_object(dict_data)
                    created_license_numbers.append(license_number)
                    total_licenses.append(license_number)

                all_results.append({
                    'file': uploaded_file.name,
                    'success': True,
                    'licenses': created_license_numbers,
                    'count': len(created_license_numbers)
                })

            except Exception as e:
                all_results.append({
                    'file': uploaded_file.name,
                    'success': False,
                    'error': str(e)
                })

        # Aggregate results
        failed_files = []
        for result in all_results:
            if not result['success']:
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
