"""
Ledger upload API endpoint for processing DFIA license ledger files.
"""
import csv
import io
import logging

from celery.result import AsyncResult
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from scripts.parse_ledger import parse_license_data, create_object

logger = logging.getLogger(__name__)


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
        """
        Process uploaded ledger file(s) asynchronously using Celery.
        Returns immediately with task IDs for progress tracking.
        """
        # Check if async mode is requested (default: True)
        use_async = request.data.get('async', 'true').lower() in ['true', '1', 'yes']

        files = request.FILES.getlist('ledger')

        if not files:
            return Response(
                {'error': 'No files uploaded. Please upload at least one CSV file.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Max file size: 50MB
        MAX_FILE_SIZE = 50 * 1024 * 1024

        if use_async:
            # ASYNC MODE: Queue files for background processing
            from license.tasks import process_ledger_file_async

            tasks = []
            validation_errors = []

            logger.info(f"Queueing {len(files)} file(s) for async processing")

            for uploaded_file in files:
                try:
                    # Validate file type
                    if not uploaded_file.name.endswith('.csv'):
                        validation_errors.append({
                            'file': uploaded_file.name,
                            'error': 'Only CSV files are supported'
                        })
                        continue

                    # Validate file size
                    if uploaded_file.size > MAX_FILE_SIZE:
                        validation_errors.append({
                            'file': uploaded_file.name,
                            'error': f'File size exceeds maximum limit of {MAX_FILE_SIZE // (1024 * 1024)}MB'
                        })
                        continue

                    # Read and decode file
                    file_content = b''
                    chunk_size = 1024 * 1024
                    for chunk in uploaded_file.chunks(chunk_size=chunk_size):
                        file_content += chunk

                    try:
                        decoded_file = file_content.decode('utf-8-sig')
                    except UnicodeDecodeError:
                        decoded_file = file_content.decode('latin-1')

                    # Clean file content
                    decoded_file = decoded_file.replace(': ', '')
                    decoded_file = decoded_file.replace(' ', '')
                    decoded_file = decoded_file.replace(':\xa0', '')

                    # Queue task
                    task = process_ledger_file_async.apply_async(
                        args=[decoded_file, uploaded_file.name]
                    )

                    tasks.append({
                        'file': uploaded_file.name,
                        'task_id': task.id,
                        'status': 'QUEUED'
                    })

                    logger.info(f"Queued {uploaded_file.name} with task_id={task.id}")

                except Exception as e:
                    logger.error(f"Error queueing file {uploaded_file.name}: {str(e)}")
                    validation_errors.append({
                        'file': uploaded_file.name,
                        'error': str(e)
                    })

            # Build response
            response_data = {
                'message': f'Queued {len(tasks)} file(s) for processing',
                'mode': 'async',
                'tasks': tasks
            }

            if validation_errors:
                response_data['validation_errors'] = validation_errors
                response_data['message'] += f' ({len(validation_errors)} file(s) failed validation)'

            return Response(response_data, status=status.HTTP_202_ACCEPTED)

        else:
            # SYNC MODE: Original synchronous processing (kept for backward compatibility)
            all_results = []
            total_licenses = []

            logger.info(f"Starting synchronous processing of {len(files)} file(s)")

            for file_sequence_number, uploaded_file in enumerate(files, start=1):
                try:
                    logger.info(f"Processing file {file_sequence_number}/{len(files)}: {uploaded_file.name}")

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

                    # Read file in chunks
                    file_content = b''
                    chunk_size = 1024 * 1024
                    for chunk in uploaded_file.chunks(chunk_size=chunk_size):
                        file_content += chunk

                    # Decode the uploaded file
                    try:
                        decoded_file = file_content.decode('utf-8-sig')
                    except UnicodeDecodeError:
                        decoded_file = file_content.decode('latin-1')

                    decoded_file = decoded_file.replace(': ', '')
                    decoded_file = decoded_file.replace(' ', '')
                    decoded_file = decoded_file.replace(':\xa0', '')
                    csvfile = io.StringIO(decoded_file)

                    reader = csv.reader(csvfile)

                    # Read all rows
                    rows = []
                    for row in reader:
                        if not any(field.strip() for field in row):
                            continue
                        rows.append(row)

                    logger.info(f"Read {len(rows)} rows from {uploaded_file.name}")

                    # Parse the CSV data
                    dict_list = parse_license_data(rows)

                    logger.info(f"Parsed {len(dict_list)} license(s) from {uploaded_file.name}")

                    # Create/update license objects
                    created_license_numbers = []
                    for idx, dict_data in enumerate(dict_list, start=1):
                        try:
                            license_number = create_object(dict_data)
                            created_license_numbers.append(license_number)
                            total_licenses.append(license_number)

                            if idx % 10 == 0:
                                logger.info(f"Processed {idx}/{len(dict_list)} licenses from {uploaded_file.name}")
                        except Exception as license_error:
                            logger.error(f"Error creating license {idx} from {uploaded_file.name}: {str(license_error)}")

                    all_results.append({
                        'file': uploaded_file.name,
                        'success': True,
                        'licenses': created_license_numbers,
                        'count': len(created_license_numbers)
                    })

                    logger.info(f"Successfully processed {uploaded_file.name}: {len(created_license_numbers)} licenses")

                except Exception as e:
                    logger.error(f"Error processing file {uploaded_file.name}: {str(e)}", exc_info=True)
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
                'mode': 'sync',
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


@method_decorator(csrf_exempt, name='dispatch')
class LedgerTaskStatusView(APIView):
    """
    API endpoint to check the status of ledger processing tasks.

    GET /api/licenses/ledger-task-status/<task_id>/

    Response:
        {
            "task_id": "abc-123-def",
            "state": "PROGRESS",
            "current": 5,
            "total": 10,
            "status": "Processed 5/10 licenses",
            "processed_licenses": ["3011006401", "3011006402"],
            "failed_licenses": []
        }
    """

    permission_classes = []
    authentication_classes = []
    http_method_names = ['get', 'options']

    def get(self, request, task_id):
        """Check the status of a background task."""
        try:
            task_result = AsyncResult(task_id)

            response_data = {
                'task_id': task_id,
                'state': task_result.state,
            }

            if task_result.state == 'PENDING':
                response_data['status'] = 'Task is waiting to be processed'

            elif task_result.state == 'PROGRESS':
                # Task is in progress, return progress info
                info = task_result.info or {}
                response_data.update({
                    'current': info.get('current', 0),
                    'total': info.get('total', 0),
                    'status': info.get('status', 'Processing...'),
                    'processed_licenses': info.get('processed_licenses', []),
                    'failed_licenses': info.get('failed_licenses', [])
                })

            elif task_result.state == 'SUCCESS':
                # Task completed successfully
                result = task_result.result
                response_data.update({
                    'status': 'Completed',
                    'result': result
                })

            elif task_result.state == 'FAILURE':
                # Task failed
                response_data.update({
                    'status': 'Failed',
                    'error': str(task_result.info)
                })

            else:
                # Other states (RETRY, REVOKED, etc.)
                response_data['status'] = f'Task state: {task_result.state}'

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error checking task status for {task_id}: {str(e)}")
            return Response(
                {'error': f'Failed to check task status: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
