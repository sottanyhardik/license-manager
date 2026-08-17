import logging

from django.db import transaction
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import LicensePermission
from apps.license.models import SionPlanningRule
from apps.license.serializers import SionPlanningRuleSerializer
from apps.license.services.canonical_planning_service import (
    CompanyIsolationError, PlanningError,
)
from apps.license.services.sion_rule_engine import (
    SionRulePlanningService, SionRulePriorityService,
)

logger = logging.getLogger(__name__)


class SionPlanRequestSerializer(serializers.Serializer):
    """Identifiers accepted by norm-first preview and planning actions.

    An omitted or empty ``license_ids`` value deliberately means the normal
    company-scoped universe of eligible DFIAs.  A non-empty list is only an
    optional restriction; it is never required to plan a SION.
    """

    sion_id = serializers.IntegerField(required=True, min_value=1)
    license_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )


class SionPlanningRuleViewSet(viewsets.ModelViewSet):
    """Versioned rule definitions plus read-only preview and explicit plan."""
    permission_classes = [LicensePermission]
    serializer_class = SionPlanningRuleSerializer
    filterset_fields = ("sion", "is_active")

    def get_queryset(self):
        return SionPlanningRule.objects.select_related(
            "sion", "created_by", "modified_by",
        ).all()

    def _audit(self, event, *, rule=None, sion_id=None, extra=None):
        from apps.core.models import ActivityLog
        try:
            ActivityLog.objects.create(
                user=self.request.user, username=self.request.user.username or "",
                action=(
                    ActivityLog.ACTION_CREATE if event == "RULE_CREATED"
                    else ActivityLog.ACTION_DELETE if event == "RULE_DEACTIVATED"
                    else ActivityLog.ACTION_UPDATE
                ),
                module="SION_PLANNING", resource_id=str(getattr(rule, "pk", sion_id) or ""),
                description=event, endpoint=self.request.path, method=self.request.method,
                status_code=200, extra={
                    "event": event, "sion_id": getattr(rule, "sion_id", sion_id),
                    "rule_id": getattr(rule, "pk", None),
                    "rule_version": getattr(rule, "version", None), **(extra or {}),
                },
            )
        except Exception:
            logger.exception("Unable to persist SION planning audit event %s", event)

    def perform_create(self, serializer):
        values = serializer.validated_data
        with transaction.atomic():
            priority = SionRulePriorityService.next_priority(values["sion"].pk)
            rule = serializer.save(
                version=1, priority=priority, created_by=self.request.user,
                modified_by=self.request.user,
            )
        self._audit("RULE_CREATED", rule=rule)

    def update(self, request, *args, **kwargs):
        """Edits append a version; the prior audit row is never overwritten."""
        current = self.get_object()
        was_active = current.is_active
        serializer = self.get_serializer(current, data=request.data, partial=kwargs.pop("partial", False))
        serializer.is_valid(raise_exception=True)
        values = {
            field: serializer.validated_data.get(field, getattr(current, field))
            for field in ("name", "expression", "max_unit_price", "unit", "is_active")
        }
        with transaction.atomic():
            SionRulePriorityService._lock_sion(current.sion_id)
            current.is_active = False
            current.modified_by = request.user
            current.save(update_fields=("is_active", "modified_on", "modified_by"))
            created = SionPlanningRule.objects.create(
                **values, sion=current.sion, priority=current.priority,
                version=current.version + 1,
                created_by=request.user, modified_by=request.user,
            )
            if not created.is_active:
                SionRulePriorityService.normalize(current.sion_id)
        event = (
            "RULE_DEACTIVATED" if not created.is_active
            else "RULE_ACTIVATED" if not was_active
            else "RULE_UPDATED"
        )
        self._audit(event, rule=created)
        return Response(self.get_serializer(created).data)

    def destroy(self, request, *args, **kwargs):
        """Retire a rule; audit versions are intentionally never deleted."""
        with transaction.atomic():
            rule = self.get_object()
            SionRulePriorityService._lock_sion(rule.sion_id)
            rule.is_active = False
            rule.modified_by = request.user
            rule.save(update_fields=("is_active", "modified_on", "modified_by"))
            SionRulePriorityService.normalize(rule.sion_id)
        self._audit("RULE_DEACTIVATED", rule=rule)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _company_id(self):
        return None if self.request.user.is_superuser else self.request.user.company_id

    def _execute(self, request, *, persist):
        try:
            result = (
                SionRulePlanningService.plan if persist else SionRulePlanningService.preview
            )(self.get_object(), request.data.get("license_ids"), company_id=self._company_id())
        except CompanyIsolationError as exc:
            return Response(exc.as_dict(), status=status.HTTP_403_FORBIDDEN)
        except PlanningError as exc:
            return Response(exc.as_dict(), status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @action(detail=True, methods=("post",), url_path="test")
    def test_rule(self, request, pk=None):
        response = self._execute(request, persist=False)
        if response.status_code < 400:
            self._audit("RULE_TESTED", rule=self.get_object())
        return response

    @action(detail=False, methods=("post",), url_path="reorder")
    def reorder(self, request):
        try:
            with transaction.atomic():
                rules = SionRulePriorityService.reorder(
                    request.data.get("sion_id"), request.data.get("rule_order"),
                )
        except PlanningError as exc:
            return Response(exc.as_dict(), status=status.HTTP_400_BAD_REQUEST)
        self._audit(
            "RULE_REORDERED", sion_id=request.data.get("sion_id"),
            extra={"rule_order": request.data.get("rule_order")},
        )
        return Response(self.get_serializer(rules, many=True).data)

    @action(detail=False, methods=("post",), url_path="plan-sion")
    def plan_sion(self, request):
        if "rules" in request.data or "expression" in request.data:
            return Response(
                {"error": "Planning accepts only saved database rules."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request_serializer = SionPlanRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        identifiers = request_serializer.validated_data
        try:
            result = SionRulePlanningService.plan_sion(
                identifiers["sion_id"], identifiers.get("license_ids"),
                company_id=self._company_id(),
            )
        except CompanyIsolationError as exc:
            return Response(exc.as_dict(), status=status.HTTP_403_FORBIDDEN)
        except (PlanningError, ValueError, TypeError) as exc:
            payload = exc.as_dict() if isinstance(exc, PlanningError) else {"error": str(exc)}
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        self._audit(
            "SION_PLAN_EXECUTED", sion_id=result["sion_id"],
            extra={"rules_executed": result["rules_executed"]},
        )
        return Response(result)

    @action(detail=False, methods=("post",), url_path="preview-sion")
    def preview_sion(self, request):
        """Preview the selected norm using saved DB rules, without writes."""
        if "rules" in request.data or "expression" in request.data:
            return Response(
                {"error": "Preview accepts only saved database rules."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request_serializer = SionPlanRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        identifiers = request_serializer.validated_data
        try:
            result = SionRulePlanningService.preview_sion(
                identifiers["sion_id"], identifiers.get("license_ids"),
                company_id=self._company_id(),
            )
        except CompanyIsolationError as exc:
            return Response(exc.as_dict(), status=status.HTTP_403_FORBIDDEN)
        except (PlanningError, ValueError, TypeError) as exc:
            payload = exc.as_dict() if isinstance(exc, PlanningError) else {"error": str(exc)}
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)
