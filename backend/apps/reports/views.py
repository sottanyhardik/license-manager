# reports/views.py
"""
Report dispatch and status views.

POST endpoints dispatch Celery tasks (treated as "reads" for permission
purposes — same pattern as LicenseReadOnlyPermission).  GET endpoint
polls CeleryTaskTracker for task status.

Permission class: ReportDispatchPermission
  All authenticated users with any report-related role may dispatch.
  Superusers always pass.
  Unauthenticated requests → 401.
"""
import logging

from django.conf import settings
from django.utils import timezone as dj_timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import BaseRolePermission

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------

class ReportDispatchPermission(BaseRolePermission):
    """
    POST to dispatch is treated as a read (no write roles needed).

    Mirrors LicenseReadOnlyPermission: overrides has_permission so that all
    HTTP methods are gated by required_roles_for_read.
    """

    required_roles_for_read = [
        "REPORT_VIEWER",
        "LICENSE_MANAGER",
        "TRADE_MANAGER",
        "ALLOTMENT_MANAGER",
        "BOE_MANAGER",
        "INCENTIVE_LICENSE_MANAGER",
    ]
    required_roles_for_write = []

    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_any_role(self.required_roles_for_read)


# ---------------------------------------------------------------------------
# Request serializers (validation layer)
# ---------------------------------------------------------------------------

class BalanceReportRequestSerializer(serializers.Serializer):
    license_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        error_messages={"min_length": "At least one license_id is required."},
    )
    format = serializers.ChoiceField(
        choices=["json", "pdf", "excel"],
        default="json",
    )


# ISO date pattern — YYYY-MM-DD, validated before passing to Celery (must remain
# a plain string so it survives JSON serialisation to Redis without conversion).
_ISO_DATE_RE = r"^\d{4}-\d{2}-\d{2}$"


class ItemReportRequestSerializer(serializers.Serializer):
    """Typed params for item utilisation report.  Replaces free-form DictField."""

    item_name_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
        required=False,
        default=list,
    )
    company_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
        required=False,
        default=list,
    )
    min_balance = serializers.FloatField(required=False, allow_null=True)
    license_status = serializers.ChoiceField(
        choices=["active", "all"], default="active", required=False
    )
    expiry_date_from = serializers.RegexField(
        _ISO_DATE_RE, required=False, allow_null=True, allow_blank=True
    )
    expiry_date_to = serializers.RegexField(
        _ISO_DATE_RE, required=False, allow_null=True, allow_blank=True
    )
    format = serializers.ChoiceField(
        choices=["json", "pdf", "excel"],
        default="json",
    )


_ITEM_FILTER_KEYS = frozenset(
    {"item_name_ids", "company_ids", "min_balance", "license_status", "expiry_date_from", "expiry_date_to"}
)


class PivotReportRequestSerializer(serializers.Serializer):
    """Typed params for pivot (norm-class grouped) report.  Replaces free-form DictField."""

    item_name_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
        required=False,
        default=list,
    )
    company_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
        required=False,
        default=list,
    )
    min_balance = serializers.FloatField(required=False, allow_null=True)
    license_status = serializers.ChoiceField(
        choices=["active", "all"], default="active", required=False
    )
    expiry_date_from = serializers.RegexField(
        _ISO_DATE_RE, required=False, allow_null=True, allow_blank=True
    )
    expiry_date_to = serializers.RegexField(
        _ISO_DATE_RE, required=False, allow_null=True, allow_blank=True
    )
    sion_norm = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    format = serializers.ChoiceField(
        choices=["json", "pdf", "excel"],
        default="json",
    )


_PIVOT_FILTER_KEYS = frozenset(
    {"item_name_ids", "company_ids", "min_balance", "license_status", "expiry_date_from", "expiry_date_to", "sion_norm"}
)


class LedgerReportRequestSerializer(serializers.Serializer):
    license_id = serializers.IntegerField(min_value=1)
    format = serializers.ChoiceField(
        choices=["json", "pdf", "excel"],
        default="json",
    )


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------

_STATUS_MAP = {
    "PENDING": "pending",
    "STARTED": "running",
    "RETRY": "running",
    "SUCCESS": "done",
    "FAILURE": "error",
    "REVOKED": "error",
}


def _make_tracker(task_name: str, task_id: str, args_payload: dict):
    """Create a CeleryTaskTracker in PENDING state before dispatching."""
    from apps.core.models import CeleryTaskTracker

    CeleryTaskTracker.objects.create(
        task_id=task_id,
        task_name=task_name,
        status="PENDING",
        kwargs=args_payload,
    )


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class GenerateBalanceReportView(APIView):
    """POST /reports/balance/generate/"""

    permission_classes = [ReportDispatchPermission]

    def post(self, request):
        from apps.reports.tasks import generate_balance_report_task

        ser = BalanceReportRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        license_ids = ser.validated_data["license_ids"]
        output_format = ser.validated_data["format"]

        # Dispatch first to get the Celery task ID
        result = generate_balance_report_task.apply_async(
            kwargs={
                "license_ids": license_ids,
                "output_format": output_format,
                "user_id": request.user.pk,
            }
        )
        task_id = result.id

        _make_tracker(
            task_name="generate_balance_report_task",
            task_id=task_id,
            args_payload={"license_ids": license_ids, "format": output_format},
        )

        return Response({"task_id": task_id}, status=status.HTTP_202_ACCEPTED)


class GenerateItemReportView(APIView):
    """POST /reports/items/generate/"""

    permission_classes = [ReportDispatchPermission]

    def post(self, request):
        from apps.reports.tasks import generate_item_report_task

        ser = ItemReportRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        output_format = ser.validated_data["format"]
        # Build a filters dict from typed validated fields only — no unknown keys possible.
        # Strip None / empty-list values so service defaults apply cleanly.
        filters = {
            k: v
            for k, v in ser.validated_data.items()
            if k in _ITEM_FILTER_KEYS and v not in (None, "", [])
        }

        result = generate_item_report_task.apply_async(
            kwargs={
                "filters": filters,
                "output_format": output_format,
                "user_id": request.user.pk,
            }
        )
        task_id = result.id

        _make_tracker(
            task_name="generate_item_report_task",
            task_id=task_id,
            args_payload={"filters": filters, "format": output_format},
        )

        return Response({"task_id": task_id}, status=status.HTTP_202_ACCEPTED)


class GeneratePivotReportView(APIView):
    """POST /reports/pivot/generate/"""

    permission_classes = [ReportDispatchPermission]

    def post(self, request):
        from apps.reports.tasks import generate_pivot_report_task

        ser = PivotReportRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        output_format = ser.validated_data["format"]
        # Build a filters dict from typed validated fields only — no unknown keys possible.
        filters = {
            k: v
            for k, v in ser.validated_data.items()
            if k in _PIVOT_FILTER_KEYS and v not in (None, "", [])
        }

        result = generate_pivot_report_task.apply_async(
            kwargs={
                "filters": filters,
                "output_format": output_format,
                "user_id": request.user.pk,
            }
        )
        task_id = result.id

        _make_tracker(
            task_name="generate_pivot_report_task",
            task_id=task_id,
            args_payload={"filters": filters, "format": output_format},
        )

        return Response({"task_id": task_id}, status=status.HTTP_202_ACCEPTED)


class GenerateLedgerReportView(APIView):
    """POST /reports/ledger/generate/"""

    permission_classes = [ReportDispatchPermission]

    def post(self, request):
        from apps.reports.tasks import generate_ledger_report_task

        ser = LedgerReportRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        license_id = ser.validated_data["license_id"]
        output_format = ser.validated_data["format"]

        result = generate_ledger_report_task.apply_async(
            kwargs={
                "license_id": license_id,
                "output_format": output_format,
                "user_id": request.user.pk,
            }
        )
        task_id = result.id

        _make_tracker(
            task_name="generate_ledger_report_task",
            task_id=task_id,
            args_payload={"license_id": license_id, "format": output_format},
        )

        return Response({"task_id": task_id}, status=status.HTTP_202_ACCEPTED)


class ReportTaskStatusView(APIView):
    """GET /reports/task/{task_id}/status/"""

    permission_classes = [ReportDispatchPermission]

    def get(self, request, task_id: str):
        from apps.core.models import CeleryTaskTracker

        try:
            tracker = CeleryTaskTracker.objects.get(task_id=task_id)
        except CeleryTaskTracker.DoesNotExist:
            return Response(
                {"detail": "Task not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        mapped_status = _STATUS_MAP.get(tracker.status, "pending")

        file_url = None
        if tracker.status == "SUCCESS" and tracker.result:
            file_path = tracker.result.get("file_path")
            if file_path:
                media_url = getattr(settings, "MEDIA_URL", "/media/")
                # Ensure exactly one slash between MEDIA_URL and file_path
                file_url = media_url.rstrip("/") + "/" + file_path.lstrip("/")

        return Response(
            {
                "task_id": task_id,
                "status": mapped_status,
                "progress": tracker.current,
                "file_url": file_url,
            },
            status=status.HTTP_200_OK,
        )
