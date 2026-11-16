"""Read/retry API for asynchronous licence replanning; never plans inline."""
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView
from django.db.models import Q

from apps.accounts.permissions import LicensePermission
from apps.license.models import LicenseDetailsModel, LicenseReplanRequest
from apps.license.services.replan_requests import request_license_replan


def _planning_state(license_obj):
    request = license_obj.replan_requests.filter(
        status__in=[
            LicenseReplanRequest.STATUS_RUNNING,
            LicenseReplanRequest.STATUS_QUEUED,
            LicenseReplanRequest.STATUS_PENDING,
            LicenseReplanRequest.STATUS_RETRY_PENDING,
            LicenseReplanRequest.STATUS_FAILED,
        ],
    ).order_by("-requested_at", "-pk").first()
    if request and request.status == LicenseReplanRequest.STATUS_FAILED:
        return "REPLAN_FAILED"
    if license_obj.planning_applied_revision == license_obj.planning_source_revision:
        return "CURRENT"
    return "REPLAN_RUNNING" if request and request.status == LicenseReplanRequest.STATUS_RUNNING else "REPLAN_PENDING"


def _resolve_license(license_reference):
    """Accept the overview route's canonical licence number and legacy PK links."""
    query = Q(license_number=str(license_reference))
    if str(license_reference).isdigit():
        query |= Q(pk=int(license_reference))
    return LicenseDetailsModel.objects.filter(query).order_by("pk").first()


class LicenseReplanStatusView(APIView):
    permission_classes = [LicensePermission]

    def get(self, request, license_id):
        license_obj = _resolve_license(license_id)
        if not license_obj:
            raise NotFound("License not found.")
        latest = license_obj.replan_requests.order_by("-requested_at", "-pk").first()
        return Response({
            "license_id": license_obj.pk,
            "planning_state": _planning_state(license_obj),
            "source_revision": license_obj.planning_source_revision,
            "planned_revision": license_obj.planning_applied_revision,
            "replan_request": None if not latest else {
                "id": latest.pk, "status": latest.status, "source_revision": latest.source_revision,
                "planned_revision": latest.planned_revision, "trigger_count": latest.trigger_count,
                "retry_count": latest.retry_count, "last_error_code": latest.last_error_code,
                "last_error_message": latest.last_error_message, "queued_at": latest.queued_at,
                "started_at": latest.started_at, "completed_at": latest.completed_at,
            },
        })

    def post(self, request, license_id):
        # LicensePermission permits this only to LICENSE_MANAGER users.
        license_obj = _resolve_license(license_id)
        if not license_obj:
            raise NotFound("License not found.")
        durable_request = request_license_replan(
            license_id=license_obj.pk, reason="manual_retry", source_model="api", source_pk=license_obj.pk,
        )
        return Response({
            "planning_state": "REPLAN_PENDING",
            "replan_request_id": durable_request.pk,
            "message": "Replanning has been queued.",
        }, status=202)
