"""Product-wise Item Report endpoints (additive; ``reports/item-report/`` is unchanged).

All figures come from the canonical Item Pivot engine via ``services.item_report_products``.
"""
import logging
from datetime import date

from django.http import HttpResponse, JsonResponse
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView

from apps.accounts.permissions import ReportPermission
from apps.license.api.views.item_report import _ExcelPassthroughRenderer
from apps.license.services import item_report_products as service

logger = logging.getLogger(__name__)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class _Base(APIView):
    permission_classes = [ReportPermission]
    renderer_classes = [JSONRenderer, _ExcelPassthroughRenderer]

    def _filters(self, request):
        try:
            return service.parse_filters(request.GET), None
        except service.FilterError as exc:
            return None, JsonResponse({exc.field: str(exc)}, status=400)


class ItemReportProductsView(_Base):
    """GET reports/item-report/products/ (``_format=excel`` for the workbook)."""

    def get(self, request, *args, **kwargs):
        filters, error = self._filters(request)
        if error:
            return error
        output_format = (request.GET.get("_format") or request.GET.get("format") or "json").lower()
        try:
            if output_format == "excel":
                report, detail = service.build_products_with_detail(filters)
                response = HttpResponse(service.build_excel(report, detail), content_type=XLSX)
                response["Content-Disposition"] = f'attachment; filename="item_report_products_{date.today().isoformat()}.xlsx"'
                return response
            return JsonResponse(service.build_products(filters), safe=False)
        except Exception as exc:  # same contract as the Item Report view
            logger.exception("Error generating product-wise item report")
            return JsonResponse({"error": str(exc)}, status=500)


class ItemReportProductDrilldownView(_Base):
    """GET reports/item-report/products/drilldown/?key=<product key>&<same filters>."""

    def get(self, request, *args, **kwargs):
        key = (request.GET.get("key") or "").strip()
        if not key:
            return JsonResponse({"key": "This query parameter is required."}, status=400)
        filters, error = self._filters(request)
        if error:
            return error
        try:
            data = service.build_drilldown(filters, key)
        except Exception as exc:
            logger.exception("Error generating product drill-down")
            return JsonResponse({"error": str(exc)}, status=500)
        if data is None:
            return JsonResponse({"key": "Product not found in this scope."}, status=404)
        return JsonResponse(data, safe=False)
