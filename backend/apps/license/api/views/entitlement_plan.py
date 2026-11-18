"""Read-only entitlement planning report for one licence + SION.

GET /api/entitlement-plan/?license_number=<exact>&sion=<norm>[&export=xlsx]

Never writes: it only reads licence records through the authoritative balance
services (see ``EntitlementPlanningService``).  Permission is the same
``LicensePermission`` the licence/planning read endpoints use.
"""
from __future__ import annotations

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import LicensePermission
from apps.license.services.entitlement_planning_service import EntitlementPlanningService
from apps.license.services.exporters.entitlement_plan_excel import render_entitlement_plan_xlsx
from apps.license.services.scoped_sion_planning import ScopedPlanningError

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class EntitlementPlanView(APIView):
    permission_classes = [LicensePermission]

    def get(self, request):
        license_number = request.query_params.get("license_number", "")
        sion = request.query_params.get("sion", "")
        try:
            result = EntitlementPlanningService.build(license_number, sion)
        except ScopedPlanningError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if request.query_params.get("export") == "xlsx":
            response = HttpResponse(render_entitlement_plan_xlsx(result), content_type=XLSX)
            name = f"planning_{result['licence_number']}_{result['sion']}.xlsx"
            response["Content-Disposition"] = f'attachment; filename="{name}"'
            return response
        return Response(result)
