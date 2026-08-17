from django.db import transaction
from django.db.models import Max
from apps.core.models import SionNormClassModel
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import LicensePermission
from apps.license.models import SionPlanningRule
from apps.license.serializers import SionPlanningRuleSerializer
from apps.license.services.canonical_planning_service import (
    CompanyIsolationError, PlanningError,
)
from apps.license.services.sion_rule_engine import SionRulePlanningService


class SionPlanningRuleViewSet(viewsets.ModelViewSet):
    """Versioned rule definitions plus read-only preview and explicit plan."""
    permission_classes = [LicensePermission]
    serializer_class = SionPlanningRuleSerializer
    filterset_fields = ("sion", "is_active")

    def get_queryset(self):
        return SionPlanningRule.objects.select_related(
            "sion", "created_by", "modified_by",
        ).all()

    def perform_create(self, serializer):
        values = serializer.validated_data
        with transaction.atomic():
            SionNormClassModel.objects.select_for_update().get(pk=values["sion"].pk)
            latest = SionPlanningRule.objects.filter(
                sion=values["sion"], name=values["name"],
            ).aggregate(value=Max("version"))["value"] or 0
            serializer.save(
                version=latest + 1, created_by=self.request.user,
                modified_by=self.request.user,
            )

    def update(self, request, *args, **kwargs):
        """Edits append a version; the prior audit row is never overwritten."""
        current = self.get_object()
        serializer = self.get_serializer(current, data=request.data, partial=kwargs.pop("partial", False))
        serializer.is_valid(raise_exception=True)
        values = {
            field: serializer.validated_data.get(field, getattr(current, field))
            for field in ("sion", "name", "expression", "max_unit_price", "unit", "priority", "is_active")
        }
        with transaction.atomic():
            SionNormClassModel.objects.select_for_update().get(pk=values["sion"].pk)
            current.is_active = False
            current.modified_by = request.user
            current.save(update_fields=("is_active", "modified_on", "modified_by"))
            latest = SionPlanningRule.objects.filter(
                sion=values["sion"], name=values["name"],
            ).aggregate(value=Max("version"))["value"] or 0
            created = SionPlanningRule.objects.create(
                **values, version=latest + 1,
                created_by=request.user, modified_by=request.user,
            )
        return Response(self.get_serializer(created).data)

    def destroy(self, request, *args, **kwargs):
        """Retire a rule; audit versions are intentionally never deleted."""
        rule = self.get_object()
        rule.is_active = False
        rule.modified_by = request.user
        rule.save(update_fields=("is_active", "modified_on", "modified_by"))
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
        return self._execute(request, persist=False)

    @action(detail=True, methods=("post",), url_path="plan")
    def plan_rule(self, request, pk=None):
        return self._execute(request, persist=True)
