"""
Ledger upload API endpoint for processing DFIA license ledger files.
"""
import csv
import io
import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import LedgerUploadPermission
from scripts.parse_ledger import parse_license_data, create_object
from scripts.parse_ledger_htm import parse_license_data_htm

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class LedgerUploadView(APIView):
    """
    API endpoint to upload and process ledger CSV files.
    Supports both synchronous and asynchronous (Celery) processing.

    POST /api/licenses/upload-ledger/
    """

    permission_classes = [LedgerUploadPermission]
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ['post', 'options']

    from apps.core.throttling import UploadRateThrottle
    throttle_classes = [UploadRateThrottle]

    def post(self, request):
        files = request.FILES.getlist('ledger')

        if not files:
            return Response(
                {'error': 'No files uploaded. Please upload at least one CSV file.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        use_async = request.data.get('async', 'false').lower() == 'true'
        MAX_FILE_SIZE = 50 * 1024 * 1024

        if use_async:
            return self._handle_async(files, MAX_FILE_SIZE)
        return self._handle_sync(files, MAX_FILE_SIZE)

    @staticmethod
    def _is_htm(filename):
        return filename.lower().endswith(('.htm', '.html'))

    @staticmethod
    def _is_csv(filename):
        return filename.lower().endswith('.csv')

    def _read_raw(self, uploaded_file):
        """Read uploaded file bytes."""
        content = b''
        for chunk in uploaded_file.chunks(chunk_size=1024 * 1024):
            content += chunk
        return content

    def _decode_file(self, uploaded_file):
        """Read, decode and pre-process an uploaded CSV file."""
        file_content = self._read_raw(uploaded_file)

        try:
            decoded = file_content.decode('utf-8-sig')
        except UnicodeDecodeError:
            decoded = file_content.decode('latin-1')

        decoded = decoded.replace(':\xa0', '')  # colon + non-breaking space (must come first)
        decoded = decoded.replace(': ', '')      # colon + regular space
        decoded = decoded.replace('\xa0', '')    # any remaining non-breaking spaces
        decoded = decoded.replace(' ', '')       # any remaining regular spaces (field trim)
        return decoded

    def _parse_file(self, uploaded_file):
        """
        Parse an uploaded ledger file (CSV or HTM/HTML) and return a dict_list
        in the same format expected by create_object().
        """
        if self._is_htm(uploaded_file.name):
            raw = self._read_raw(uploaded_file)
            return parse_license_data_htm(raw)
        else:
            decoded_file = self._decode_file(uploaded_file)
            csvfile = io.StringIO(decoded_file)
            reader = csv.reader(csvfile)
            rows = [
                [cell.strip().replace('\xa0', '') for cell in row]
                for row in reader
                if any(cell.strip().replace('\xa0', '') for cell in row)
            ]
            return parse_license_data(rows)

    def _serialize_for_celery(self, dict_data):
        """Convert date/datetime objects to strings for JSON-safe Celery transport."""
        import copy
        data = copy.deepcopy(dict_data)
        if hasattr(data.get('ledger_date'), 'strftime'):
            data['ledger_date'] = data['ledger_date'].strftime('%Y-%m-%d')
        for row in data.get('row', []):
            if row.get('be_date') and hasattr(row['be_date'], 'strftime'):
                row['be_date'] = row['be_date'].strftime('%Y-%m-%d')
        return data

    def _handle_async(self, files, max_file_size):
        """Parse each file and dispatch one Celery task per license (parallel processing)."""
        from apps.license.tasks import process_single_license
        from scripts.parse_ledger import parse_license_data

        file_tasks = []
        errors = []

        for uploaded_file in files:
            if not (self._is_csv(uploaded_file.name) or self._is_htm(uploaded_file.name)):
                errors.append({'file': uploaded_file.name, 'error': 'Only CSV and HTM/HTML files are supported'})
                continue

            if uploaded_file.size > max_file_size:
                errors.append({
                    'file': uploaded_file.name,
                    'error': f'File size exceeds {max_file_size // (1024 * 1024)}MB limit'
                })
                continue

            try:
                dict_list = self._parse_file(uploaded_file)
                logger.info(f"Parsed {len(dict_list)} licenses from {uploaded_file.name}, dispatching tasks")

                tasks = []
                for dict_data in dict_list:
                    serialized = self._serialize_for_celery(dict_data)
                    task = process_single_license.apply_async(args=[serialized], queue='ledger')
                    tasks.append({'task_id': task.id, 'license': dict_data.get('lic_no', 'Unknown')})

                file_tasks.append({
                    'file': uploaded_file.name,
                    'total': len(tasks),
                    'tasks': tasks,
                })
                logger.info(f"Dispatched {len(tasks)} tasks for {uploaded_file.name}")

            except Exception as e:
                logger.exception("Failed to process %s", uploaded_file.name)
                errors.append({'file': uploaded_file.name, 'error': str(e)})

        total_tasks = sum(f['total'] for f in file_tasks)
        return Response({
            'message': f'Queued {total_tasks} licenses from {len(file_tasks)} file(s)',
            'file_tasks': file_tasks,
            'errors': errors,
        }, status=status.HTTP_202_ACCEPTED)

    def _handle_sync(self, files, max_file_size):
        """Process each file synchronously and return results."""
        all_results = []
        total_licenses = []

        for file_sequence_number, uploaded_file in enumerate(files, start=1):
            try:
                logger.info(f"Processing file {file_sequence_number}/{len(files)}: {uploaded_file.name}")

                if not (self._is_csv(uploaded_file.name) or self._is_htm(uploaded_file.name)):
                    all_results.append({
                        'file': uploaded_file.name,
                        'success': False,
                        'error': 'Only CSV and HTM/HTML files are supported'
                    })
                    continue

                if uploaded_file.size > max_file_size:
                    all_results.append({
                        'file': uploaded_file.name,
                        'success': False,
                        'error': f'File size exceeds maximum limit of {max_file_size // (1024 * 1024)}MB'
                    })
                    continue

                dict_list = self._parse_file(uploaded_file)
                logger.info(f"Parsed {len(dict_list)} license(s) from {uploaded_file.name}")

                created_license_numbers = []
                failed_licenses = []
                for idx, dict_data in enumerate(dict_list, start=1):
                    license_no = dict_data.get('lic_no', 'Unknown')
                    try:
                        license_number = create_object(dict_data)
                        created_license_numbers.append(license_number)
                        total_licenses.append(license_number)
                        logger.info(f"Processed license {idx}/{len(dict_list)}: {license_number}")
                    except Exception as license_error:
                        error_msg = str(license_error)
                        failed_licenses.append({'license': license_no, 'error': error_msg})
                        logger.error(f"Error creating license {license_no} at index {idx}: {error_msg}", exc_info=True)

                all_results.append({
                    'file': uploaded_file.name,
                    'success': True,
                    'licenses': created_license_numbers,
                    'count': len(created_license_numbers),
                    'failed': failed_licenses,
                })

                logger.info(f"Done {uploaded_file.name}: {len(created_license_numbers)} ok, {len(failed_licenses)} failed")

            except Exception as e:
                logger.error(f"Error processing file {uploaded_file.name}: {str(e)}", exc_info=True)
                all_results.append({
                    'file': uploaded_file.name,
                    'success': False,
                    'error': str(e)
                })

        failed_files = [r for r in all_results if not r['success']]

        response_data = {
            'message': f'Processed {len(total_licenses)} license(s) from {len([r for r in all_results if r["success"]])} file(s)',
            'licenses': total_licenses,
            'results': all_results,
            'stats': {
                'files_processed': len([r for r in all_results if r['success']]),
                'files_failed': len(failed_files),
                'total_licenses': len(total_licenses),
            }
        }

        if failed_files:
            response_data['message'] += f' ({len(failed_files)} file(s) failed)'

        return Response(response_data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class LedgerTaskStatusView(APIView):
    """
    GET /api/licenses/ledger-task-status/<task_id>/
    Returns current state and progress of an async ledger processing task.
    """

    permission_classes = [LedgerUploadPermission]
    throttle_classes = []
    http_method_names = ['get', 'options']

    def get(self, request, task_id):
        from celery.result import AsyncResult

        result = AsyncResult(task_id)
        state = result.state

        if state == 'PENDING':
            response = {'state': 'PENDING', 'status': 'Task is waiting to be processed'}
        elif state == 'PROGRESS':
            info = result.info or {}
            response = {
                'state': 'PROGRESS',
                'current': info.get('current', 0),
                'total': info.get('total', 0),
                'status': info.get('status', ''),
                'processed_licenses': info.get('processed_licenses', []),
                'failed_licenses': info.get('failed_licenses', []),
            }
        elif state == 'SUCCESS':
            response = {
                'state': 'SUCCESS',
                'result': result.result,
            }
        elif state == 'FAILURE':
            response = {
                'state': 'FAILURE',
                'error': str(result.info),
            }
        else:
            response = {'state': state}

        return Response(response)
