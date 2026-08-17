import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Max
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import LicensePermission
from apps.license.models import LicenseDetailsModel, SionPlanningAction, SionPlanningProfile, SionPlanningRule
from apps.license.serializers import SionPlanningRuleSerializer
from apps.license.serializers.incentive import (
    BulkLicensePlanningSerializer, LicenseIdOnlySerializer,
)
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
    mode = serializers.ChoiceField(
        choices=("NEW", "ALL"), required=False, default="NEW",
    )


class LicensePlanRequestSerializer(serializers.Serializer):
    """Request for planning a specific license by license_id."""

    license_id = serializers.IntegerField(required=True, min_value=1)
    mode = serializers.ChoiceField(
        choices=("NEW", "ALL"), required=False, default="NEW",
    )


class RuleAllocationStrategySerializer(serializers.Serializer):
    """Bounded UI contract backed by the canonical SPLIT action config."""

    strategy = serializers.ChoiceField(choices=("STANDARD", "SPLIT_BY_UNIT_VALUE", "SPLIT_BY_PERCENTAGE"))
    config = serializers.JSONField(required=False)

    def validate(self, values):
        strategy = values["strategy"]
        if strategy == "STANDARD":
            return values

        config = values.get("config")
        if not isinstance(config, dict):
            raise serializers.ValidationError({"config": "Split configuration is required."})

        if strategy == "SPLIT_BY_UNIT_VALUE":
            return self._validate_unit_value_config(config)
        elif strategy == "SPLIT_BY_PERCENTAGE":
            return self._validate_percentage_config(config)

        return values

    def _validate_unit_value_config(self, config):
        """Validate SPLIT_BY_UNIT_VALUE configuration."""
        if config.get("algorithm") != "SPLIT_BY_UNIT_VALUE":
            raise serializers.ValidationError({"config": "Unsupported split algorithm."})
        if config.get("basis") != "BALANCE_CIF_PER_QUANTITY":
            raise serializers.ValidationError({"config": "Unsupported allocation basis."})
        buckets = config.get("buckets")
        if not isinstance(buckets, list) or len(buckets) < 2:
            raise serializers.ValidationError({"config": "At least two allocation buckets are required."})
        parsed = []
        codes = set()
        for index, bucket in enumerate(buckets):
            code = str(bucket.get("code", "")).strip().upper() if isinstance(bucket, dict) else ""
            if not code:
                raise serializers.ValidationError({"config": f"Bucket {index + 1} requires a code."})
            if code in codes:
                raise serializers.ValidationError({"config": "Output bucket codes must be unique."})
            codes.add(code)
            try:
                minimum = Decimal(str(bucket["min_price"]))
                maximum = Decimal(str(bucket["max_price"]))
                reference = Decimal(str(bucket["reference_price"]))
            except (KeyError, InvalidOperation, TypeError, ValueError):
                raise serializers.ValidationError({"config": f"Bucket {index + 1} prices must be decimals."})
            if (
                not minimum.is_finite() or not maximum.is_finite() or not reference.is_finite()
                or minimum < 0 or maximum <= minimum or not minimum <= reference <= maximum
            ):
                raise serializers.ValidationError({"config": f"Bucket {index + 1} has an invalid price band."})
            parsed.append((minimum, maximum, reference))
        # Validate that buckets are adjacent and ordered
        for i in range(len(parsed) - 1):
            current_min, current_max, current_ref = parsed[i]
            next_min, next_max, next_ref = parsed[i + 1]
            if next_min != current_max or next_max <= current_max or next_ref <= current_ref:
                raise serializers.ValidationError({"config": f"Buckets {i + 1} and {i + 2} must be adjacent and ordered."})
        return {"strategy": "SPLIT_BY_UNIT_VALUE", "config": config}

    def _validate_percentage_config(self, config):
        """Validate SPLIT_BY_PERCENTAGE configuration."""
        # Percentage config is loaded from the rule; user provides no custom config
        # Config validation happens when the rule is retrieved
        return {"strategy": "SPLIT_BY_PERCENTAGE", "config": config or {}}


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
            for field in (
                "name", "expression", "max_unit_price", "unit", "is_active",
                "execution_output", "output_item",
            )
        }
        with transaction.atomic():
            SionRulePriorityService._lock_sion(current.sion_id)
            current.is_active = False
            current.modified_by = request.user
            current.save(update_fields=("is_active", "modified_on", "modified_by"))
            created = SionPlanningRule.objects.create(
                **values, sion=current.sion, stable_key=current.stable_key,
                priority=current.priority,
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

    @staticmethod
    def _allocation_action_for(rule):
        profile = SionPlanningProfile.objects.filter(
            sion_id=rule.sion_id, is_active=True,
        ).order_by("-version", "-pk").first()
        if not profile:
            return None
        actions = list(SionPlanningAction.objects.filter(
            profile=profile, action_type="SPLIT",
        ).order_by("priority", "pk"))
        for candidate in actions:
            if str((candidate.config or {}).get("source_rule_id", "")) == str(rule.pk):
                return candidate
        output = (rule.execution_output or "").strip().casefold()
        if output:
            for candidate in actions:
                config = candidate.config or {}
                categories = {
                    str(config.get(key, "")).strip().casefold()
                    for key in ("category", "milk_category", "source_category")
                }
                if output in categories:
                    return candidate
        return actions[0] if len(actions) == 1 else None

    @action(detail=True, methods=("get", "patch"), url_path="allocation-strategy")
    def allocation_strategy(self, request, pk=None):
        """Read/update the rule's canonical profile SPLIT action; never copy it onto the rule."""
        rule = self.get_object()
        split_action = self._allocation_action_for(rule)
        if request.method == "GET":
            if not split_action or not split_action.is_active:
                return Response({"strategy": "STANDARD", "action_id": getattr(split_action, "pk", None)})
            return Response({
                "strategy": "SPLIT_BY_UNIT_VALUE", "action_id": split_action.pk,
                "config": split_action.config,
            })

        serializer = RuleAllocationStrategySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        with transaction.atomic():
            if not split_action and values["strategy"] == "SPLIT_BY_UNIT_VALUE":
                profile = SionPlanningProfile.objects.filter(
                    sion_id=rule.sion_id, is_active=True,
                ).order_by("-version", "-pk").first()
                if profile is None:
                    profile = SionPlanningProfile.objects.create(
                        sion_id=rule.sion_id,
                        stable_key=f"{rule.sion.norm_class}:PROFILE:UI:{rule.pk}",
                        strategy_type="ACTION_PIPELINE",
                        config={},
                        is_active=True,
                        created_by=request.user,
                        modified_by=request.user,
                    )
                next_priority = (profile.actions.aggregate(value=Max("priority"))["value"] or 0) + 1
                split_action = SionPlanningAction.objects.create(
                    profile=profile,
                    stable_key=f"{rule.sion.norm_class}:RULE:{rule.pk}:SPLIT",
                    action_type="SPLIT",
                    priority=next_priority,
                    config={
                        "source_rule_id": rule.pk,
                        "category": (rule.execution_output or rule.name).strip(),
                    },
                    is_active=False,
                    created_by=request.user,
                    modified_by=request.user,
                )
            if split_action is None:
                return Response({"strategy": "STANDARD"})
            split_action = SionPlanningAction.objects.select_for_update().get(pk=split_action.pk)
            if values["strategy"] == "STANDARD":
                split_action.is_active = False
                split_action.modified_by = request.user
                split_action.save(update_fields=("is_active", "modified_by", "modified_on"))
                response = {"strategy": "STANDARD", "action_id": split_action.pk}
            else:
                # Preserve pipeline membership/category/granularity and any
                # other proven execution mechanics; only the bounded allocator
                # fields are UI-owned.
                requested = values["config"]
                config = dict(split_action.config or {})
                config["source_rule_id"] = rule.pk
                config["category"] = (rule.execution_output or rule.name).strip()
                for key in ("algorithm", "basis", "buckets"):
                    config[key] = requested[key]
                split_action.config = config
                split_action.is_active = True
                split_action.version += 1
                split_action.modified_by = request.user
                split_action.full_clean()
                split_action.save(update_fields=(
                    "config", "is_active", "version", "modified_by", "modified_on",
                ))
                response = {
                    "strategy": "SPLIT_BY_UNIT_VALUE", "action_id": split_action.pk,
                    "config": split_action.config,
                }
        self._audit("RULE_ALLOCATION_UPDATED", rule=rule, extra={"strategy": values["strategy"]})
        return Response(response)

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
                mode=identifiers["mode"],
            )
        except CompanyIsolationError as exc:
            return Response(exc.as_dict(), status=status.HTTP_403_FORBIDDEN)
        except (PlanningError, ValueError, TypeError) as exc:
            payload = exc.as_dict() if isinstance(exc, PlanningError) else {"error": str(exc)}
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        self._audit(
            "SION_PLAN_EXECUTED", sion_id=result["sion_id"],
            extra={
                "rules_executed": result["rules_executed"],
                "mode": result["mode"],
            },
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
                company_id=self._company_id(), mode=identifiers["mode"],
            )
        except CompanyIsolationError as exc:
            return Response(exc.as_dict(), status=status.HTTP_403_FORBIDDEN)
        except (PlanningError, ValueError, TypeError) as exc:
            payload = exc.as_dict() if isinstance(exc, PlanningError) else {"error": str(exc)}
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


    @staticmethod
    def _resolve_sions_for_license(license_id, company_id=None):
        """Load license and determine applicable SION norms from export manifest.

        Returns: (license_obj, sion_ids_list)
        Raises: PlanningError or CompanyIsolationError
        """
        license_obj = (
            LicenseDetailsModel.objects
            .filter(pk=license_id)
            .select_related("exporter")
            .prefetch_related("export_license__norm_class")
            .first()
        )
        if not license_obj:
            raise PlanningError(
                f"License {license_id} not found.",
                code="LICENSE_NOT_FOUND",
            )

        if company_id is not None and license_obj.exporter_id != int(company_id):
            raise CompanyIsolationError(
                f"License {license_id} belongs to another company."
            )

        export_items = license_obj.export_license.all()
        if not export_items.exists():
            raise PlanningError(
                f"License {license_id} has no export manifest.",
                code="NO_EXPORT_MANIFEST",
            )

        sion_ids = sorted(set(
            item.norm_class_id
            for item in export_items
            if item.norm_class_id is not None
        ))

        if not sion_ids:
            raise PlanningError(
                f"License {license_id} has no SION norms in export manifest.",
                code="NO_SION_NORMS",
            )

        return license_obj, sion_ids

    @action(detail=False, methods=("post",), url_path="plan-license")
    def plan_license(self, request):
        """Plan a single license through all applicable SION norms.

        INTERNAL: This endpoint is used by the /planning page and related planning
        workflows. It auto-discovers applicable SIONs for a license and plans through
        all of them. This is an alternative to plan-sion (SION-first planning) but
        both flow through the same execution engine.

        For new planning integrations, prefer plan-sion and have the caller specify
        the SION directly.
        """
        request_serializer = LicenseIdOnlySerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data

        try:
            license_obj, sion_ids = self._resolve_sions_for_license(
                values["license_id"], company_id=self._company_id()
            )
        except CompanyIsolationError as exc:
            return Response(exc.as_dict(), status=status.HTTP_403_FORBIDDEN)
        except PlanningError as exc:
            return Response(exc.as_dict(), status=status.HTTP_400_BAD_REQUEST)

        mode = values["mode"]
        applicable_sions = []

        for sion_id in sion_ids:
            try:
                with transaction.atomic():
                    result = SionRulePlanningService.plan_sion(
                        sion_id, license_ids=[license_obj.pk],
                        company_id=self._company_id(),
                        mode=mode,
                    )
            except CompanyIsolationError as exc:
                return Response(exc.as_dict(), status=status.HTTP_403_FORBIDDEN)
            except PlanningError as exc:
                return Response(exc.as_dict(), status=status.HTTP_400_BAD_REQUEST)

            applicable_sions.append({
                "sion_id": sion_id,
                "sion_code": result.get("sion"),
                "status": "EXECUTED" if result.get("write_results") else "SKIPPED",
                "rules_executed": result.get("rules_executed", []),
                "write_results": result.get("write_results", []),
            })

        self._audit(
            "LICENSE_PLAN_EXECUTED",
            extra={
                "license_id": license_obj.pk,
                "license_number": license_obj.license_number,
                "sions_count": len(applicable_sions),
                "mode": mode,
            },
        )

        return Response({
            "license_id": license_obj.pk,
            "license_number": license_obj.license_number,
            "mode": mode,
            "applicable_sions": applicable_sions,
            "total_results": {
                "sions_processed": len(applicable_sions),
                "sions_executed": len([s for s in applicable_sions if s["status"] == "EXECUTED"]),
                "total_lines_written": sum(
                    len(wr.get("write_results", []))
                    for s in applicable_sions
                    for wr in s.get("write_results", [])
                ),
            },
        })

