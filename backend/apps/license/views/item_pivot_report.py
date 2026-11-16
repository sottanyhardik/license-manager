"""
Item-wise Pivot Report

Shows licenses with items as column headers, displaying quantities and values per item.
Similar to the GE DFIA report format.

Facade module: the implementation is split across ``item_pivot_helpers``,
``item_pivot_generate``, ``item_pivot_row`` and ``item_pivot_excel``; every
name is re-exported here so existing imports / patches keep working.
"""

import hashlib
import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Any

from django.db.models import Prefetch
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from apps.accounts.permissions import ReportPermission
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.constants import DEC_0, DEC_000, GE, MI, CO
from apps.core.models import ItemNameModel
from apps.license.models import (
    LicenseDetailsModel, LicenseImportItemsModel,
    LicenseExportItemModel, LicenseTransferModel,
)
from apps.license.services.a3627_classifier import registry_version
from apps.license.services.plan_grouping import (
    merge_planned_import_items as _merge_planned_import_items,
    merge_items_for_classification as _merge_items_for_classification,
)
from apps.license.views.item_report import _ExcelPassthroughRenderer
from apps.license.views.item_pivot_helpers import (  # noqa: F401  (re-exports)
    PIVOT_ITEM_FIELDS,
    PIVOT_ALWAYS_SHOWN_FIELDS,
    PIVOT_ITEM_TINTS,
    _pivot_item_fill,
    _pivot_has_value,
    _pivot_item_fields,
    _fit_sheet_columns,
    TOTAL_SUMMARY_TITLE,
    ITEM_SUMMARY_EXCEL_METRICS,
    _item_summary_name,
    _item_summary_rows_from_matrix,
    _item_summary_rows_from_projection,
    _item_summary_subtotal,
    _write_item_summary_table,
    _safe_int,
    _effective_planned_cif,
    _effective_planned_quantity,
    _build_notification_summary,
    _xlsx_safe_row,
    _planning_split_sheet_rows,
    _write_notification_summary_block,
)
from apps.license.views.item_pivot_excel import ItemPivotExcelMixin
from apps.license.views.item_pivot_generate import ItemPivotGenerateMixin
from apps.license.views.item_pivot_row import ItemPivotRowMixin

logger = logging.getLogger(__name__)


class ItemPivotReportView(ItemPivotGenerateMixin, ItemPivotRowMixin, ItemPivotExcelMixin, APIView):
    """
    Report showing licenses with items as columns (pivot format).

    GET parameters:
        - format: 'json' or 'excel' (default: json)
        - days: Number of days to look back (default: 30)
    """
    permission_classes = [ReportPermission]
    # Without this, DRF's own content negotiation intercepts ?format=excel
    # before get() ever runs and raises Http404 (rest_framework.negotiation.
    # DefaultContentNegotiation.filter_renderers has no renderer whose
    # `.format` is 'excel', since DEFAULT_RENDERER_CLASSES only registers
    # JSONRenderer) — i.e. the Export button 404s outright. Registering the
    # passthrough renderer (same fix already applied to ItemReportView) makes
    # 'excel' a recognised format so content negotiation succeeds; the view
    # still returns a plain StreamingHttpResponse for excel, so this renderer
    # is never actually invoked.
    renderer_classes = [JSONRenderer, _ExcelPassthroughRenderer]

    def get(self, request, *args, **kwargs):
        output_format = request.GET.get('format', 'json').lower()
        days = _safe_int(request.GET.get('days'), 30)
        sion_norm = request.GET.get('sion_norm')
        company_ids = request.GET.get('company_ids')  # Comma-separated company IDs
        exclude_company_ids = request.GET.get('exclude_company_ids')  # Comma-separated company IDs to exclude
        min_balance = _safe_int(request.GET.get('min_balance'), 200)
        license_status = request.GET.get('license_status', 'active')
        expiry_date_from = request.GET.get('expiry_date_from')  # YYYY-MM-DD
        expiry_date_to = request.GET.get('expiry_date_to')      # YYYY-MM-DD
        purchase_status = request.GET.get('purchase_status')    # Comma-separated codes

        # For Excel export, use streaming approach to avoid timeout
        if output_format == 'excel':
            try:
                return self.export_to_excel_streaming(days, sion_norm, company_ids, exclude_company_ids, min_balance, license_status, expiry_date_from, expiry_date_to, purchase_status)
            except Exception as e:
                logger.exception("Error exporting item pivot report to Excel")
                return JsonResponse({
                    'error': str(e)
                }, status=500)

        # The pivot is a large, read-only DTO and may take several seconds to
        # calculate.  Cache by the complete normalized request so repeated tab
        # selections return the exact same payload without repeating the ORM
        # and balance-calculation work.  Existing `view:item_pivot*` signal
        # invalidation removes these entries whenever source data changes.
        cache_parts = tuple(sorted((key, tuple(request.GET.getlist(key))) for key in request.GET))
        # The classification registry version is part of the key: a changed rule or label
        # misses the cache at once instead of serving a pivot built by the old rules.
        cache_key = f"view:item_pivot:{registry_version()}:{hashlib.sha256(repr(cache_parts).encode()).hexdigest()}"
        cached_report = cache.get(cache_key)
        if cached_report is not None:
            return JsonResponse(cached_report, safe=False)

        # For JSON, generate full report
        try:
            report_data = self.generate_report(days, sion_norm, company_ids, exclude_company_ids, min_balance,
                                               license_status, expiry_date_from, expiry_date_to, purchase_status)
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=500)

        cache.set(cache_key, report_data, timeout=300)
        return JsonResponse(report_data, safe=False)


class ItemPivotViewSet(viewsets.ViewSet):
    """
    ViewSet for Item Pivot Report.

    Permissions: ReportPermission.
    """
    permission_classes = [ReportPermission]

    def list(self, request):
        """
        Get item pivot report.

        Query Parameters:
            days: Number of days to look back (default: 30)
        """
        view = ItemPivotReportView()
        return view.get(request)

    @action(detail=False, methods=['get'], url_path='available-norms')
    def available_norms(self, request):
        """
        Get list of all active norm classes with their descriptions.
        Returns only norms that are marked as active (is_active=True) in SionNormClassModel.
        """
        try:
            # Get only active SION norm classes from the database
            from apps.core.models import SionNormClassModel
            active_norms_data = SionNormClassModel.objects.filter(
                is_active=True
            ).values('norm_class', 'description').order_by('norm_class')

            # Build result with norm_class and description
            result = [
                {
                    'norm_class': norm['norm_class'],
                    'description': norm['description'] or ''
                }
                for norm in active_norms_data
            ]

            return Response(result)
        except Exception as e:
            logger.exception("Error generating item pivot report")
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='task-status/(?P<task_id>[^/.]+)')
    def task_status(self, request, task_id=None):
        """
        Check the status of an async Excel generation task.

        Returns:
            state: Task state (PENDING, PROGRESS, SUCCESS, FAILURE)
            current: Current progress (0-100)
            total: Total progress (100)
            status: Status message
            result: Result data (if completed)
        """
        from celery.result import AsyncResult

        task = AsyncResult(task_id)

        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'current': 0,
                'total': 100,
                'status': 'Pending...'
            }
        elif task.state == 'PROGRESS':
            response = {
                'state': task.state,
                'current': task.info.get('current', 0),
                'total': task.info.get('total', 100),
                'status': task.info.get('status', '')
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'current': 100,
                'total': 100,
                'status': 'Completed!',
                'result': task.info
            }
        else:
            # Something went wrong
            response = {
                'state': task.state,
                'current': 100,
                'total': 100,
                'status': str(task.info) if task.info else 'Unknown error'
            }

        return Response(response)

    @action(detail=False, methods=['post'], url_path='update-balance')
    def update_balance(self, request):
        """
        Trigger high-priority task to update balance_cif, is_active, is_expired, and restrictions.

        This task:
        1. Updates balance_cif for all licenses using LicenseBalanceCalculator
        2. Updates is_expired based on license_expiry_date
        3. Updates is_null based on balance < $500
        4. Updates is_active based on expiry (mark inactive if expired)
        5. Checks and updates restriction flags on import items

        Returns:
            task_id: ID to check status using task-status endpoint
        """
        from apps.license.tasks import update_all_license_balances

        # Get license_status parameter from request body
        license_status = request.data.get('license_status', 'all')

        # Start the Celery task with high priority
        task = update_all_license_balances.apply_async(
            args=[license_status],
            priority=9  # High priority (0-9, 9 is highest)
        )

        return Response({
            'task_id': task.id,
            'status': 'PENDING',
            'license_status': license_status,
            'message': f'Balance update started for {license_status} licenses. Use the task_id to check status.'
        }, status=202)