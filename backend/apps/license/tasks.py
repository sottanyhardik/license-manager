# license/tasks.py
from celery import shared_task
from datetime import datetime, timedelta
import logging
import os

from apps.license.models import LicenseImportItemsModel

logger = logging.getLogger(__name__)


@shared_task
def update_items():
    """Update balance values for license items (optimized - now synchronous)"""
    from apps.core.scripts.calculate_balance import update_balance_values

    current_date = datetime.now()
    date_90_days_ago = current_date - timedelta(days=90)
    items = LicenseImportItemsModel.objects.filter(
        license__license_expiry_date__gte=date_90_days_ago
    ).order_by('license__license_expiry_date', 'license__license_date')

    for item in items:
        update_balance_values(item)


@shared_task(bind=True)
def update_all_license_balances(self, license_status='all'):
    """
    High-priority task to update balance_cif, is_active, is_expired, and restrictions for all licenses.
    Triggered manually from Item Pivot Report for fast, accurate report generation.

    This task:
    1. Updates balance_cif for all licenses using LicenseBalanceCalculator
    2. Updates is_expired based on license_expiry_date
    3. Updates is_null based on balance < $500
    4. Updates is_active: False if expired, True if not expired
    5. Checks and updates restriction flags on import items

    Args:
        license_status: Filter licenses by status ('active', 'inactive', 'all')

    Returns:
        dict with status, counts, and timing info
    """
    from django.utils import timezone
    from decimal import Decimal
    from apps.license.models import (
        LicenseDetailsModel,
        LicenseImportItemsModel,
        LicenseBalance,
        LicenseFlags,
    )
    from apps.license.services.balance_calculator import LicenseBalanceCalculator

    logger.info(f"Starting update_all_license_balances task: task_id={self.request.id}, license_status={license_status}")
    start_time = datetime.now()

    try:
        # Get licenses based on status filter
        licenses = LicenseDetailsModel.objects.all()

        # Filter by license status if specified
        if license_status == 'active':
            licenses = licenses.filter(flags__is_active=True)
        elif license_status == 'inactive':
            licenses = licenses.filter(flags__is_active=False)
        # else: license_status == 'all', no filter

        total_licenses = licenses.count()

        logger.info(f"Processing {total_licenses} licenses")

        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': total_licenses, 'status': 'Updating license balances...'}
        )

        updated_count = 0
        skipped_count = 0
        error_count = 0
        today = timezone.now().date()

        # Process licenses in batches
        batch_size = 50
        for i, license_obj in enumerate(licenses.iterator(chunk_size=batch_size)):
            try:
                # Calculate balance using centralized service
                # Financial Ledger formula -- same source as `LicenseDetailsModel.
                # get_balance_cif` (see that property's docstring). This task
                # writes the same cached `balance_cif` field that property
                # feeds; using a different formula here would silently
                # overwrite the correct value on every scheduled run.
                balance = LicenseBalanceCalculator.calculate_financial_balance(license_obj)

                # Determine flags
                is_expired = license_obj.license_expiry_date < today if license_obj.license_expiry_date else False
                is_null = balance < Decimal('500')
                is_active = not is_expired  # Mark inactive if expired

                # Check if any value changed - skip update if nothing changed (optimization)
                if (license_obj.balance_cif == balance and
                    license_obj.is_expired == is_expired and
                    license_obj.is_null == is_null and
                    license_obj.is_active == is_active):
                    # Nothing changed, skip this license to reduce DB writes
                    skipped_count += 1
                    continue

                # Update license fields only if something changed.
                # balance_cif lives on LicenseBalance; the is_* flags on LicenseFlags.
                LicenseBalance.objects.filter(license_id=license_obj.pk).update(
                    balance_cif=balance,
                )
                LicenseFlags.objects.filter(license_id=license_obj.pk).update(
                    is_expired=is_expired,
                    is_null=is_null,
                    is_active=is_active,
                )

                updated_count += 1

                # Update progress every batch
                if (i + 1) % batch_size == 0:
                    self.update_state(
                        state='PROGRESS',
                        meta={
                            'current': i + 1,
                            'total': total_licenses,
                            'status': f'Updated {updated_count} licenses, skipped {skipped_count}...'
                        }
                    )

            except Exception as e:
                error_count += 1
                logger.error(f"Error updating license {license_obj.license_number}: {str(e)}")

        # Refresh per-item available_value via the new pool model and keep
        # is_restricted in sync with condition_type. The old path that derived
        # is_restricted from ItemNameModel.restriction_percentage is gone —
        # restrictions now come exclusively from the licence's condition sheet.
        self.update_state(
            state='PROGRESS',
            meta={'current': 90, 'total': 100, 'status': 'Refreshing per-item balances...'}
        )

        restriction_count = 0
        from apps.license.signals import update_license_flags
        for license_obj in LicenseDetailsModel.objects.all().iterator(chunk_size=50):
            try:
                update_license_flags(license_obj)
                restriction_count += 1
            except Exception as e:
                logger.error(f"Error refreshing balances for license {license_obj.license_number}: {e}")

        elapsed = (datetime.now() - start_time).total_seconds()

        result = {
            'status': 'success',
            'updated': updated_count,
            'skipped': skipped_count,
            'errors': error_count,
            'restrictions_updated': restriction_count,
            'total_licenses': total_licenses,
            'elapsed_seconds': elapsed,
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"Update completed: {result}")
        return result

    except Exception as e:
        error_msg = f"Failed to update license balances: {str(e)}"
        logger.error(error_msg)
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


@shared_task
def sync_all_licenses():
    """
    Daily task to sync all licenses: update balance_cif, flags, and import item balances.
    Runs at 12:00 AM IST every day via Celery Beat.
    """
    from django.core.management import call_command
    from io import StringIO
    import sys

    logger.info("Starting daily license sync task...")

    # Capture command output
    output = StringIO()
    try:
        # Run the sync_licenses management command
        call_command(
            'sync_licenses',
            batch_size=100,
            stdout=output,
            stderr=output
        )

        output_str = output.getvalue()
        logger.info(f"License sync completed successfully:\n{output_str}")
        return {
            'status': 'success',
            'output': output_str,
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        error_msg = f"License sync failed: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Output: {output.getvalue()}")
        return {
            'status': 'error',
            'error': str(e),
            'output': output.getvalue(),
            'timestamp': datetime.now().isoformat()
        }


@shared_task(name='identify_licenses_needing_update')
def identify_licenses_needing_update():
    """
    LEVEL 1 TASK: Identify which licenses need updates without actually updating them.
    This prevents creating unnecessary update tasks.

    Checks:
    - balance_cif (from LicenseBalanceCalculator)
    - is_expired (based on expiry_date)
    - is_null (balance < $500)
    - is_active (False if expired)

    Returns:
        - If updates needed: Triggers level-2 task with list of license IDs
        - If no updates needed: Returns immediately with 0 tasks created
    """
    from django.utils import timezone
    from decimal import Decimal
    from apps.license.models import LicenseDetailsModel
    from apps.license.services.balance_calculator import LicenseBalanceCalculator
    from apps.core.models import CeleryTaskTracker

    task_id = identify_licenses_needing_update.request.id
    logger.info(f"[LEVEL-1] Starting license identification: task_id={task_id}")
    start_time = datetime.now()

    # Track task in database
    tracker = CeleryTaskTracker.objects.create(
        task_id=task_id,
        task_name='identify_licenses_needing_update',
        status='STARTED',
        started_at=start_time
    )

    try:
        licenses = LicenseDetailsModel.objects.all()
        total_licenses = licenses.count()
        today = timezone.now().date()

        licenses_to_update = []

        # Identify licenses that need updates
        for license_obj in licenses.iterator(chunk_size=200):
            try:
                # Calculate what the values should be
                # Financial Ledger formula -- same source as `LicenseDetailsModel.
                # get_balance_cif` (see that property's docstring). This task
                # writes the same cached `balance_cif` field that property
                # feeds; using a different formula here would silently
                # overwrite the correct value on every scheduled run.
                balance = LicenseBalanceCalculator.calculate_financial_balance(license_obj)
                is_expired = license_obj.license_expiry_date < today if license_obj.license_expiry_date else False
                is_null = balance < Decimal('500')
                is_active = not is_expired

                # Check if any value changed
                if (license_obj.balance_cif != balance or
                    license_obj.is_expired != is_expired or
                    license_obj.is_null != is_null or
                    license_obj.is_active != is_active):
                    # This license needs update
                    licenses_to_update.append(license_obj.id)

            except Exception as e:
                logger.error(f"Error checking license {license_obj.license_number}: {str(e)}")

        elapsed = (datetime.now() - start_time).total_seconds()

        result = {
            'status': 'success',
            'total_checked': total_licenses,
            'needs_update': len(licenses_to_update),
            'skipped': total_licenses - len(licenses_to_update),
            'elapsed_seconds': elapsed,
            'timestamp': datetime.now().isoformat()
        }

        # Update tracker
        tracker.status = 'SUCCESS'
        tracker.completed_at = timezone.now()
        tracker.result = result
        tracker.save(update_fields=['status', 'completed_at', 'result'])

        # Only trigger level-2 task if there are licenses to update
        if licenses_to_update:
            logger.info(f"[LEVEL-1] Found {len(licenses_to_update)} licenses needing update. Triggering level-2 task.")
            # Trigger level-2 task with the list of IDs
            update_identified_licenses.apply_async(args=[licenses_to_update])
            result['level2_triggered'] = True
        else:
            logger.info(f"[LEVEL-1] No licenses need updating. Skipping level-2 task.")
            result['level2_triggered'] = False

        return result

    except Exception as e:
        error_msg = f"[LEVEL-1] License identification failed: {str(e)}"
        logger.error(error_msg)

        # Update tracker
        tracker.status = 'FAILURE'
        tracker.completed_at = timezone.now()
        tracker.result = {'status': 'error', 'error': str(e)}
        tracker.traceback = str(e)
        tracker.save(update_fields=['status', 'completed_at', 'result', 'traceback'])

        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


@shared_task(name='update_identified_licenses')
def update_identified_licenses(license_ids):
    """
    LEVEL 2 TASK: Update ONLY the licenses identified by level-1 task.
    This task only runs if there are licenses that actually need updating.

    Args:
        license_ids: List of license IDs that need updating (from level-1)

    Returns:
        dict with update statistics
    """
    from django.utils import timezone
    from decimal import Decimal
    from apps.license.models import LicenseDetailsModel, LicenseBalance, LicenseFlags
    from apps.license.services.balance_calculator import LicenseBalanceCalculator
    from apps.core.models import CeleryTaskTracker

    task_id = update_identified_licenses.request.id
    logger.info(f"[LEVEL-2] Starting update of {len(license_ids)} identified licenses: task_id={task_id}")
    start_time = datetime.now()

    # Track task in database
    tracker = CeleryTaskTracker.objects.create(
        task_id=task_id,
        task_name='update_identified_licenses',
        status='STARTED',
        started_at=start_time,
        total=len(license_ids)
    )

    try:
        # Fetch only the licenses that need updating
        licenses = LicenseDetailsModel.objects.filter(id__in=license_ids)
        today = timezone.now().date()

        updated_count = 0
        error_count = 0
        batch_size = 100

        for i, license_obj in enumerate(licenses.iterator(chunk_size=batch_size)):
            try:
                # Calculate balance
                # Financial Ledger formula -- same source as `LicenseDetailsModel.
                # get_balance_cif` (see that property's docstring). This task
                # writes the same cached `balance_cif` field that property
                # feeds; using a different formula here would silently
                # overwrite the correct value on every scheduled run.
                balance = LicenseBalanceCalculator.calculate_financial_balance(license_obj)

                # Determine flags
                is_expired = license_obj.license_expiry_date < today if license_obj.license_expiry_date else False
                is_null = balance < Decimal('500')
                is_active = not is_expired

                # Update license (we already know it needs updating from level-1).
                # balance_cif is on LicenseBalance; is_* flags on LicenseFlags.
                LicenseBalance.objects.filter(license_id=license_obj.pk).update(
                    balance_cif=balance,
                )
                LicenseFlags.objects.filter(license_id=license_obj.pk).update(
                    is_expired=is_expired,
                    is_null=is_null,
                    is_active=is_active,
                )

                updated_count += 1

                # Update progress every batch
                if (i + 1) % batch_size == 0:
                    tracker.current = i + 1
                    tracker.progress_message = f'Updated {updated_count} licenses...'
                    tracker.save(update_fields=['current', 'progress_message'])

            except Exception as e:
                error_count += 1
                logger.error(f"Error updating license {license_obj.license_number}: {str(e)}")

        elapsed = (datetime.now() - start_time).total_seconds()

        result = {
            'status': 'success',
            'updated': updated_count,
            'errors': error_count,
            'total_identified': len(license_ids),
            'elapsed_seconds': elapsed,
            'timestamp': datetime.now().isoformat()
        }

        # Update tracker
        tracker.status = 'SUCCESS'
        tracker.completed_at = timezone.now()
        tracker.result = result
        tracker.save(update_fields=['status', 'completed_at', 'result'])

        logger.info(f"[LEVEL-2] Update completed: {result}")
        return result

    except Exception as e:
        error_msg = f"[LEVEL-2] Update failed: {str(e)}"
        logger.error(error_msg)

        # Update tracker
        tracker.status = 'FAILURE'
        tracker.completed_at = timezone.now()
        tracker.result = {'status': 'error', 'error': str(e)}
        tracker.traceback = str(e)
        tracker.save(update_fields=['status', 'completed_at', 'result', 'traceback'])

        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


@shared_task(name='cleanup_old_task_records')
def cleanup_old_task_records():
    """
    Cleanup task that runs every hour to delete completed Celery task records older than 2 hours.
    Keeps the database clean and prevents table bloat.

    Returns:
        dict with count of deleted records
    """
    from django.utils import timezone
    from apps.core.models import CeleryTaskTracker

    logger.info("Starting cleanup of old task records")

    # Delete completed/failed tasks older than 2 hours
    cutoff_time = timezone.now() - timedelta(hours=2)

    old_tasks = CeleryTaskTracker.objects.filter(
        status__in=['SUCCESS', 'FAILURE', 'REVOKED'],
        completed_at__lt=cutoff_time
    )

    count = old_tasks.count()
    old_tasks.delete()

    logger.info(f"Cleaned up {count} old task records")

    return {
        'status': 'success',
        'deleted_count': count,
        'cutoff_time': cutoff_time.isoformat(),
        'timestamp': datetime.now().isoformat()
    }


@shared_task(bind=True)
def process_ledger_file_async(self, file_content, file_name):
    """
    Process ledger file asynchronously, one license at a time.
    This prevents timeouts during large file uploads.

    Args:
        file_content: Decoded CSV content (string)
        file_name: Original filename

    Returns:
        dict with processing results
    """
    import csv
    import io
    import sys
    from scripts.parse_ledger import parse_license_data, create_object

    task_id = self.request.id
    logger.info(f"Starting async ledger processing: task_id={task_id}, file={file_name}")
    start_time = datetime.now()

    # Increase recursion limit temporarily for this task
    old_recursion_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(3000)

    # Update task state
    self.update_state(
        state='PROGRESS',
        meta={
            'current': 0,
            'total': 0,
            'status': 'Parsing CSV file...',
            'processed_licenses': [],
            'failed_licenses': []
        }
    )

    try:
        # Parse CSV
        csvfile = io.StringIO(file_content)
        reader = csv.reader(csvfile)

        # Read all rows
        rows = []
        for row in reader:
            if not any(field.strip() for field in row):
                continue
            rows.append(row)

        logger.info(f"Read {len(rows)} rows from {file_name}")

        # Parse into license dictionaries
        dict_list = parse_license_data(rows)
        total_licenses = len(dict_list)

        logger.info(f"Parsed {total_licenses} license(s) from {file_name}")

        # Update state with total count
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0,
                'total': total_licenses,
                'status': f'Processing {total_licenses} licenses...',
                'processed_licenses': [],
                'failed_licenses': []
            }
        )

        # Process licenses one by one
        processed_licenses = []
        failed_licenses = []

        for idx, dict_data in enumerate(dict_list, start=1):
            license_no = dict_data.get('lic_no', 'Unknown')
            try:
                logger.info(f"Processing license {idx}/{total_licenses}: {license_no}")
                license_number = create_object(dict_data)
                processed_licenses.append({
                    'license_number': license_number,
                    'index': idx
                })

                # Update progress
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx,
                        'total': total_licenses,
                        'status': f'Processed {idx}/{total_licenses} licenses',
                        'processed_licenses': [license_data['license_number'] for license_data in processed_licenses],
                        'failed_licenses': failed_licenses
                    }
                )

                logger.info(f"Successfully processed license {idx}/{total_licenses}: {license_number}")

            except RecursionError:
                error_msg = f"Recursion error (maximum depth exceeded)"
                failed_licenses.append({
                    'index': idx,
                    'error': error_msg,
                    'license_data': license_no
                })
                logger.error(f"RecursionError for license {license_no} at index {idx}: {error_msg}", exc_info=True)
                # Continue processing other licenses

            except Exception as license_error:
                error_msg = str(license_error)
                failed_licenses.append({
                    'index': idx,
                    'error': error_msg,
                    'license_data': license_no
                })
                logger.error(f"Error creating license {license_no} at index {idx}: {error_msg}", exc_info=True)
                # Continue processing other licenses

        elapsed = (datetime.now() - start_time).total_seconds()

        result = {
            'status': 'SUCCESS',
            'file_name': file_name,
            'total_licenses': total_licenses,
            'processed_count': len(processed_licenses),
            'failed_count': len(failed_licenses),
            'processed_licenses': [license_data['license_number'] for license_data in processed_licenses],
            'failed_licenses': failed_licenses,
            'elapsed_seconds': elapsed,
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"Ledger processing complete: {result}")
        return result

    except Exception as e:
        error_msg = f"Failed to process ledger file: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Update state to FAILURE
        self.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'exc_type': type(e).__name__
            }
        )

        # Re-raise to mark task as failed
        raise
    finally:
        # Restore original recursion limit
        sys.setrecursionlimit(old_recursion_limit)


@shared_task(bind=True, name='process_single_license')
def process_single_license(self, dict_data):
    """
    Process a single license dict (already parsed from CSV).
    Dispatched individually so licenses are processed in parallel.

    Args:
        dict_data: Serialized license dict from parse_license_data()

    Returns:
        dict with license_number or error details
    """
    from scripts.parse_ledger import create_object

    license_no = dict_data.get('lic_no', 'Unknown')
    logger.info(f"Processing single license: {license_no} (task={self.request.id})")

    try:
        license_number = create_object(dict_data)
        logger.info(f"Successfully processed license: {license_number}")
        return {
            'status': 'SUCCESS',
            'license_number': license_number,
            'lic_no': license_no,
        }
    except Exception as e:
        logger.error(f"Error processing license {license_no}: {e}", exc_info=True)
        raise
