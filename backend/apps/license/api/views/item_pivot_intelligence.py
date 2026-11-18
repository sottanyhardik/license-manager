"""Read-only Item Pivot intelligence endpoints (overview / products / licences /
eligibility + Auto Plan recommendations), mounted on ``ItemPivotViewSet``.

Same filters and licence population as the classic report
(``item_pivot_selection.select_pivot_licenses``); nothing is written.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from apps.license.api.views.item_pivot_helpers import _safe_int
from apps.license.api.views.item_report import _ExcelPassthroughRenderer
from apps.license.services.item_pivot_intelligence import build_intelligence, recommend_for_licenses
from apps.license.services.item_pivot_intelligence_export import REC_COLUMNS, SHEETS, workbook_response as _workbook
from apps.license.services.item_pivot_selection import select_pivot_licenses

FILTER_KEYS = ("sion_norm", "company_ids", "exclude_company_ids", "license_status", "expiry_date_from", "expiry_date_to", "purchase_status")


def _filters(params) -> dict:
    values = {key: params.get(key) or None for key in FILTER_KEYS}
    values["license_status"] = values["license_status"] or "active"
    values["min_balance"] = _safe_int(params.get("min_balance"), 200)
    values["days"] = _safe_int(params.get("days"), 30)
    return values


class ItemPivotIntelligenceMixin:
    """Actions for ``ItemPivotViewSet``. Permission: the viewset's ReportPermission."""

    # `?format=excel` is DRF's format override: the pass-through renderer lets it reach the view.
    @action(detail=False, methods=["get"], url_path="intelligence", renderer_classes=[JSONRenderer, _ExcelPassthroughRenderer])
    def intelligence(self, request):
        data = build_intelligence(select_pivot_licenses(**_filters(request.query_params)))
        if (request.query_params.get("format") or "").lower() == "excel":
            warnings = [row for row in data["eligibility"] if row["status"] in {"WARNING", "OVERPLANNED", "BLOCKED"}]
            sheets = [(title, cols, data[key]) for title, (key, cols) in SHEETS.items()]
            sheets.append(("Exceptions", SHEETS["Eligibility"][1], warnings))
            return _workbook(sheets)
        return Response(data)

    @action(detail=False, methods=["get"], url_path="recommendations", renderer_classes=[JSONRenderer, _ExcelPassthroughRenderer])
    def recommendations(self, request):
        raw = request.query_params.get("license_ids", "")
        try:
            ids = [int(v) for v in raw.split(",") if v.strip()]
        except ValueError:
            return Response({"license_ids": "Comma-separated licence ids are required."}, status=status.HTTP_400_BAD_REQUEST)
        if not ids:
            return Response({"license_ids": "At least one licence id is required."}, status=status.HTTP_400_BAD_REQUEST)
        data = recommend_for_licenses(ids, limit=25)
        if (request.query_params.get("format") or "").lower() == "excel":
            return _workbook([("Recommendations", REC_COLUMNS, data["recommendations"])])
        return Response(data)
