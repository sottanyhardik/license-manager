"""
Dashboard API views.

All endpoints require authentication.  Content is role-filtered inside the
service layer where needed.  Each view is deliberately thin — it delegates all
aggregation logic to dashboard_service and returns the result unchanged.
"""
import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.dashboard_service import (
    get_dashboard_stats,
    get_expiring_licenses,
    get_license_utilisation_chart,
    get_monthly_activity,
)

logger = logging.getLogger(__name__)


class DashboardStatsView(APIView):
    """GET /dashboard/stats/ — headline KPI counters."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        try:
            data = get_dashboard_stats(request.user)
            return Response(data)
        except Exception:
            logger.exception("Unexpected error in DashboardStatsView")
            return Response(
                {"detail": "An unexpected error occurred."},
                status=500,
            )


class UtilisationChartView(APIView):
    """GET /dashboard/charts/utilisation/ — top-10 licenses by balance_cif."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        try:
            data = get_license_utilisation_chart(request.user)
            return Response(data)
        except Exception:
            logger.exception("Unexpected error in UtilisationChartView")
            return Response(
                {"detail": "An unexpected error occurred."},
                status=500,
            )


class ActivityChartView(APIView):
    """GET /dashboard/charts/activity/ — BOE + allotment counts per month (last 12 months)."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        try:
            data = get_monthly_activity(request.user)
            return Response(data)
        except Exception:
            logger.exception("Unexpected error in ActivityChartView")
            return Response(
                {"detail": "An unexpected error occurred."},
                status=500,
            )


class ExpiringLicensesView(APIView):
    """GET /dashboard/expiring-licenses/ — licenses expiring in next 30 days."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        try:
            data = get_expiring_licenses(request.user)
            return Response(data)
        except Exception:
            logger.exception("Unexpected error in ExpiringLicensesView")
            return Response(
                {"detail": "An unexpected error occurred."},
                status=500,
            )
