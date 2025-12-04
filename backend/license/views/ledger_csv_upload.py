"""
Custom Ledger CSV Upload View
Allows uploading and processing custom ledger CSV files for license transactions
"""
import csv
import io
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bill_of_entry.models import BillOfEntryModel, RowDetails
from core.models import PortModel
from license.models import LicenseDetailsModel, LicenseImportItemsModel


class LedgerCSVUploadView(APIView):
    """
    Upload and process custom ledger CSV file

    Expected CSV format:
    DFIA,sr_no,BENO,BEDT,PORT,CIFINR,CIFD,QTY

    Example:
    0311031558,1,1234567,01/01/2024,INMUN1,10000.50,1500.25,1000
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Process uploaded CSV file and create ledger entries
        """
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided. Please upload a CSV file.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        csv_file = request.FILES['file']

        # Validate file type
        if not csv_file.name.endswith('.csv'):
            return Response(
                {'error': 'Invalid file type. Please upload a CSV file.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Read and decode CSV file
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            # Validate CSV headers
            required_headers = ['DFIA', 'sr_no', 'BENO', 'BEDT', 'PORT', 'CIFINR', 'CIFD', 'QTY']
            if not all(header in reader.fieldnames for header in required_headers):
                return Response(
                    {
                        'error': f'Invalid CSV format. Required headers: {", ".join(required_headers)}',
                        'found_headers': reader.fieldnames
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Process CSV rows
            results = {
                'success': 0,
                'errors': [],
                'warnings': []
            }

            with transaction.atomic():
                for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is header
                    try:
                        self._process_row(row, row_num, results)
                    except Exception as e:
                        results['errors'].append({
                            'row': row_num,
                            'data': row,
                            'error': str(e)
                        })

            # Prepare response
            response_data = {
                'message': f'Successfully processed {results["success"]} rows',
                'success_count': results['success'],
                'error_count': len(results['errors']),
                'warning_count': len(results['warnings']),
            }

            if results['errors']:
                response_data['errors'] = results['errors'][:10]  # Limit to first 10 errors
                if len(results['errors']) > 10:
                    response_data['note'] = f'{len(results["errors"]) - 10} more errors not shown'

            if results['warnings']:
                response_data['warnings'] = results['warnings'][:10]

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Failed to process CSV file: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_row(self, row, row_num, results):
        """
        Process a single CSV row and create ledger entry
        """
        # Clean DFIA number (remove non-breaking spaces)
        dfia_number = row['DFIA'].replace('\xa0', '').strip()
        serial_number = row['sr_no'].strip()

        # Find license import item
        try:
            sr_number = LicenseImportItemsModel.objects.get(
                license__license_number=dfia_number,
                serial_number=serial_number
            )
        except LicenseImportItemsModel.DoesNotExist:
            raise ValueError(f'License item not found: DFIA={dfia_number}, Sr.No={serial_number}')
        except LicenseImportItemsModel.MultipleObjectsReturned:
            raise ValueError(f'Multiple license items found: DFIA={dfia_number}, Sr.No={serial_number}')

        # Get or create Bill of Entry
        be_number_str = row['BENO'].strip()
        be_number, created = BillOfEntryModel.objects.get_or_create(
            bill_of_entry_number=be_number_str
        )

        # Parse and set BE date
        be_date_str = row['BEDT'].strip()
        if be_date_str:
            try:
                # Try multiple date formats
                for date_format in ['%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d']:
                    try:
                        be_number.bill_of_entry_date = datetime.strptime(be_date_str, date_format).date()
                        break
                    except ValueError:
                        continue
            except Exception:
                results['warnings'].append({
                    'row': row_num,
                    'message': f'Invalid date format: {be_date_str}. Expected DD/MM/YYYY or DD/MM/YY'
                })

        # Get or create Port
        port_code = row['PORT'].strip()
        if port_code:
            port, _ = PortModel.objects.get_or_create(code=port_code)
            be_number.port = port

        # Set product name based on item description
        item_description = str(sr_number.item).upper()
        if 'BEARING' in item_description:
            be_number.product_name = 'BEARING'
        elif 'ALLOY STEEL' in item_description:
            be_number.product_name = 'ALLOY STEEL'
        elif 'AIR FILTER' in item_description:
            be_number.product_name = 'Air Filter'
        else:
            be_number.product_name = str(sr_number.item)[:100]  # Limit length

        be_number.save()

        # Get or create Row Details
        row_details, created = RowDetails.objects.get_or_create(
            bill_of_entry=be_number,
            sr_number=sr_number
        )

        # Update values
        try:
            row_details.cif_inr = Decimal(str(row['CIFINR'])) if row['CIFINR'] else Decimal('0')
            row_details.cif_fc = Decimal(str(row['CIFD'])) if row['CIFD'] else Decimal('0')
            row_details.qty = Decimal(str(row['QTY'])) if row['QTY'] else Decimal('0')
            row_details.transaction_type = 'D'  # Debit transaction
            row_details.save()

            results['success'] += 1
        except Exception as e:
            raise ValueError(f'Invalid numeric value: {str(e)}')

    def get(self, request):
        """
        Return CSV template and instructions
        """
        template_info = {
            'description': 'Upload custom ledger CSV to import DFIA debit transactions',
            'required_headers': ['DFIA', 'sr_no', 'BENO', 'BEDT', 'PORT', 'CIFINR', 'CIFD', 'QTY'],
            'header_descriptions': {
                'DFIA': 'License number (10 digits)',
                'sr_no': 'Serial number of the item',
                'BENO': 'Bill of Entry number',
                'BEDT': 'Bill of Entry date (DD/MM/YYYY or DD/MM/YY)',
                'PORT': 'Port code (e.g., INMUN1)',
                'CIFINR': 'CIF value in INR',
                'CIFD': 'CIF value in foreign currency',
                'QTY': 'Quantity'
            },
            'example_row': {
                'DFIA': '0311031558',
                'sr_no': '1',
                'BENO': '1234567',
                'BEDT': '01/01/2024',
                'PORT': 'INMUN1',
                'CIFINR': '10000.50',
                'CIFD': '1500.25',
                'QTY': '1000'
            },
            'notes': [
                'CSV file should have headers in the first row',
                'All numeric values should use decimal notation (e.g., 1234.56)',
                'Date format: DD/MM/YYYY or DD/MM/YY',
                'License (DFIA) and serial number must exist in the system',
                'This creates DEBIT transactions (imports/consumption)'
            ]
        }

        return Response(template_info, status=status.HTTP_200_OK)
