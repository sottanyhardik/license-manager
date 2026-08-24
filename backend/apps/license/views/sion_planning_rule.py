import logging
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Max, Q
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import LicensePermission
from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseReplanRequest, SionInputAliasConfig, SionPlanningAction, SionPlanningProfile, SionPlanningRule
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
from apps.license.services.scoped_sion_planning import ScopedPlanningError, ScopedSionPlanningService

logger = logging.getLogger(__name__)


class SionPlanRequestSerializer(serializers.Serializer):
    """Identifiers accepted by norm-first preview and planning actions.

    An omitted or empty ``license_ids`` value deliberately means the normal
    company-scoped universe of eligible DFIAs.  A non-empty list is only an
    optional restriction; it is never required to plan a SION.
    """

    sion_id = serializers.IntegerField(required=True, min_value=1)
    expiry_scope = serializers.ChoiceField(choices=("EXPIRED", "EXPIRING_SOON"), required=False)
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


class ScopedSionPlanSerializer(serializers.Serializer):
    """Exact external identifiers; IDs are intentionally not accepted here."""
    license_number = serializers.CharField(required=True, trim_whitespace=True)
    sion = serializers.CharField(required=True, trim_whitespace=True)
    preview_version = serializers.CharField(required=False)


class RuleAllocationStrategySerializer(serializers.Serializer):
    """Bounded UI contract backed by the canonical SPLIT action config."""

    strategy = serializers.ChoiceField(choices=("STANDARD", "SPLIT_BY_UNIT_VALUE", "SPLIT_BY_PERCENTAGE"))
    config = serializers.JSONField(required=False)

    def validate(self, values):
        strategy = values["strategy"]
        if strategy == "STANDARD":
            return values

        config = values.get("config")
        if strategy in ("SPLIT_BY_UNIT_VALUE", "SPLIT_BY_PERCENTAGE"):
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
        """Validate SPLIT_BY_PERCENTAGE configuration.

        Validates input_item_id, percentage, and unit_price.
        Derives output_code server-side from ItemNameModel.name.
        Supports both master-rule-derived configs and user-edited percentage rows.
        If rows is empty, we'll attempt to load from master rules.
        If rows has entries, they must be valid and sum to 100%.
        """
        if not isinstance(config, dict):
            raise serializers.ValidationError({"config": "Configuration must be an object."})

        rows = config.get("rows", [])
        if isinstance(rows, list) and len(rows) > 0:
            seen_item_ids = set()
            total_pct = Decimal("0")
            normalized_rows = []

            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    raise serializers.ValidationError({"config": f"Row {index + 1} must be an object."})

                # Extract and validate input_item_id
                input_item_id = row.get("input_item_id")

                # input_item_id can be null/None, but if provided, must be a positive integer
                if input_item_id is not None:
                    try:
                        input_item_id = int(input_item_id)
                        if input_item_id <= 0:
                            raise ValueError()
                    except (TypeError, ValueError):
                        raise serializers.ValidationError({"config": f"Row {index + 1} input_item_id must be a positive integer."})

                    # Check if ItemNameModel exists
                    if not ItemNameModel.objects.filter(pk=input_item_id).exists():
                        raise serializers.ValidationError({"config": f"Row {index + 1} references non-existent item."})

                    # Check for duplicates (only among non-null IDs)
                    if input_item_id in seen_item_ids:
                        raise serializers.ValidationError({"config": f"Duplicate input item: {input_item_id}"})
                    seen_item_ids.add(input_item_id)

                # Validate percentage
                try:
                    percentage = Decimal(str(row.get("percentage", "0")))
                except (InvalidOperation, TypeError, ValueError):
                    raise serializers.ValidationError({"config": f"Row {index + 1} percentage must be a decimal."})
                if not percentage.is_finite() or percentage < 0 or percentage > 100:
                    raise serializers.ValidationError({"config": f"Row {index + 1} percentage must be between 0 and 100."})
                total_pct += percentage

                # Validate unit_price
                try:
                    unit_price = Decimal(str(row.get("unit_price", "0")))
                except (InvalidOperation, TypeError, ValueError):
                    raise serializers.ValidationError({"config": f"Row {index + 1} unit_price must be a decimal."})
                if not unit_price.is_finite() or unit_price < 0:
                    raise serializers.ValidationError({"config": f"Row {index + 1} unit_price must be a non-negative decimal."})

                # Derive output_code from ItemNameModel
                output_code = ""
                if input_item_id is not None:
                    try:
                        item = ItemNameModel.objects.get(pk=input_item_id)
                        output_code = item.name.upper() if item.name else ""
                    except ItemNameModel.DoesNotExist:
                        # Should not happen because we checked existence above, but be safe
                        output_code = ""
                else:
                    output_code = "UNKNOWN"

                # Build normalized row with input_item_id, derived output_code, percentage, and unit_price
                normalized_row = dict(row)
                normalized_row["input_item_id"] = input_item_id
                normalized_row["output_code"] = output_code
                normalized_row["percentage"] = str(percentage)
                normalized_row["unit_price"] = str(unit_price)
                normalized_rows.append(normalized_row)

            if total_pct != Decimal("100"):
                raise serializers.ValidationError({"config": f"Percentages must sum to 100%, got {total_pct}."})

            # Return with normalized rows (both ID and derived code)
            result_config = dict(config)
            result_config["rows"] = normalized_rows
            return {"strategy": "SPLIT_BY_PERCENTAGE", "config": result_config}

        return {"strategy": "SPLIT_BY_PERCENTAGE", "config": config}


class SionPlanningRuleViewSet(viewsets.ModelViewSet):
    """Versioned rule definitions plus read-only preview and explicit plan."""
    permission_classes = [LicensePermission]
    serializer_class = SionPlanningRuleSerializer
    filterset_fields = ("sion", "is_active")

    def get_queryset(self):
        return SionPlanningRule.objects.select_related(
            "sion", "created_by", "modified_by",
        ).all()

    @action(detail=False, methods=("get",), url_path="import-items")
    def import_items(self, request):
        """Search active import items belonging to one exact SION norm."""
        try:
            sion_id = int(request.query_params.get("sion_id", ""))
        except (TypeError, ValueError):
            return Response(
                {"sion_id": "A valid SION id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sion = SionNormClassModel.objects.filter(pk=sion_id).first()
        if sion is None:
            return Response({"sion_id": "SION norm was not found."}, status=status.HTTP_404_NOT_FOUND)

        items = ItemNameModel.objects.filter(
            norms=sion_id,
            is_active=True,
        ).prefetch_related("norms")
        search = request.query_params.get("search", "").strip()
        if search:
            search_filter = Q(name__icontains=search) | Q(group__name__icontains=search)
            scoped_aliases = SionInputAliasConfig.objects.filter(
                Q(sion_id=sion_id) | Q(sion__isnull=True),
                is_active=True,
            )
            canonical_codes = scoped_aliases.filter(
                Q(canonical_input_code__icontains=search) | Q(alias_normalized__icontains=search)
            ).values_list("canonical_input_code", flat=True)
            aliases = scoped_aliases.filter(
                canonical_input_code__in=canonical_codes,
            ).values_list("alias_normalized", flat=True)
            for alias in aliases:
                search_filter |= Q(name__icontains=alias)
            compact_search = re.sub(r"[^A-Za-z0-9]", "", search)
            if 2 <= len(compact_search) <= 6:
                acronym_pattern = r"(^|[^A-Za-z0-9])" + r"[A-Za-z0-9]*[^A-Za-z0-9]+".join(
                    re.escape(character) for character in compact_search
                )
                search_filter |= Q(name__iregex=acronym_pattern)
            items = items.filter(search_filter)

        item_id = request.query_params.get("item_id")
        if item_id:
            try:
                items = items.filter(pk=int(item_id))
            except (TypeError, ValueError):
                return Response(
                    {"item_id": "A valid item id is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        items = items.order_by("display_order", "name")
        page = self.paginate_queryset(items)
        source = page if page is not None else items
        data = [
            {
                "id": item.pk,
                "name": item.name,
                "sion_code": sion.norm_class,
            }
            for item in source
        ]
        if page is not None:
            response = self.get_paginated_response(data)
        else:
            response = Response(data)
        response["Cache-Control"] = "no-store"
        return response

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
        unit_value_rows = serializer.validated_data.get("unit_value_rows")
        percentage_rows = serializer.validated_data.get("percentage_rows")
        values = {
            field: serializer.validated_data.get(field, getattr(current, field))
            for field in (
                "name", "expression", "max_unit_price", "unit", "is_active",
                "execution_output", "import_item", "strategy",
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
            if unit_value_rows is None:
                unit_value_rows = [
                    {"import_item": row.import_item, "min_unit_price": row.min_unit_price,
                     "max_unit_price": row.max_unit_price, "preferred_unit_price": row.preferred_unit_price,
                     "priority": row.priority}
                    for row in current.unit_value_rows.all()
                ]
            if percentage_rows is None:
                percentage_rows = [
                    {"import_item": row.import_item, "percentage": row.percentage,
                     "unit_price": row.unit_price, "max_quantity": row.max_quantity,
                     "priority": row.priority}
                    for row in current.percentage_rows.all()
                ]
            for row_data in unit_value_rows:
                created.unit_value_rows.create(**row_data)
            for row_data in percentage_rows:
                created.percentage_rows.create(**row_data)
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

    def _execute(self, request, *, persist):
        try:
            result = (
                SionRulePlanningService.plan if persist else SionRulePlanningService.preview
            )(self.get_object(), request.data.get("license_ids"), company_id=None)
        except CompanyIsolationError as exc:
            return Response(exc.as_dict(), status=status.HTTP_403_FORBIDDEN)
        except PlanningError as exc:
            return Response(exc.as_dict(), status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @action(detail=True, methods=("get", "patch"), url_path="allocation-strategy")
    def allocation_strategy(self, request, pk=None):
        """Read or update the legacy strategy-editor projection.

        The planning editor still uses this small endpoint while it migrates
        to versioned rule rows.  Persist the configuration in the canonical
        profile action model; never attach an ad-hoc strategy blob to a rule.
        """
        rule = self.get_object()
        action = self._allocation_action_for(rule)
        if request.method == "GET":
            if action is None:
                return Response(
                    {"detail": "No allocation strategy is configured for this rule."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response({
                "action_id": action.pk,
                "strategy": (action.config or {}).get("algorithm", "STANDARD"),
                "config": action.config or {},
                "version": action.version,
            })

        payload = RuleAllocationStrategySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        with transaction.atomic():
            SionRulePriorityService._lock_sion(rule.sion_id)
            profile = action.profile if action is not None else None
            if action is None:
                profile = SionPlanningProfile.objects.filter(
                    sion_id=rule.sion_id, is_active=True,
                ).order_by("-version", "-pk").first()
                if profile is None:
                    profile = SionPlanningProfile.objects.create(
                        sion_id=rule.sion_id,
                        stable_key=f"{rule.sion.norm_class}:EDITOR",
                        is_active=False,
                    )
                next_priority = (
                    SionPlanningAction.objects.filter(profile=profile, is_active=True)
                    .aggregate(max_priority=Max("priority"))["max_priority"] or 0
                ) + 1
                action = SionPlanningAction.objects.create(
                    profile=profile,
                    stable_key=f"rule:{rule.pk}:strategy",
                    action_type="SPLIT",
                    priority=next_priority,
                    config={},
                )

            config = dict(action.config or {})
            config.update(values.get("config") or {})
            config["algorithm"] = values["strategy"]
            if values["strategy"] == "SPLIT_BY_PERCENTAGE" and not config.get("rows"):
                # An empty editor starts from persisted SION master rules;
                # callers never need to manufacture labels or retired output
                # fields.  Explicit rows still go through serializer-level
                # canonical item validation above.
                defaults = SionPlanningRule.objects.filter(
                    sion_id=rule.sion_id, is_active=True,
                    percentage_constraint__isnull=False,
                    import_item__isnull=False,
                ).exclude(pk=rule.pk).order_by("priority", "pk")
                config["rows"] = [{
                    "input_item_id": candidate.import_item_id,
                    "output_code": candidate.import_item.name.upper(),
                    "percentage": str(candidate.percentage_constraint),
                    "unit_price": str(candidate.max_unit_price),
                } for candidate in defaults]
            config["source_rule_id"] = rule.pk
            config.setdefault("category", rule.execution_output or rule.name)
            config.setdefault("granularity", "ITEM_SEQUENTIAL")
            action.config = config
            action.version += 1
            action.is_active = True
            action.save(update_fields=("config", "version", "is_active", "modified_on"))
            if not profile.is_active:
                # The action now exists, satisfying the profile invariant.
                profile.is_active = True
                profile.save(update_fields=("is_active", "modified_on"))
        self._audit("RULE_ALLOCATION_STRATEGY_UPDATED", rule=rule, extra={"action_id": action.pk})
        return Response({
            "action_id": action.pk,
            "strategy": values["strategy"],
            "config": action.config,
            "version": action.version,
        })

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
        """Queue one durable REPLACE request per explicitly selected licence.

        This route previously ran a potentially unbounded Auto Plan operation
        inside the web request.  It now only resolves licence identifiers and
        creates one coalesced durable request per licence; workers isolate the
        actual locks and failures.
        """
        if "rules" in request.data or "expression" in request.data:
            return Response(
                {"error": "Planning accepts only saved database rules."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request_serializer = SionPlanRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        identifiers = request_serializer.validated_data
        sion = SionNormClassModel.objects.filter(
            pk=identifiers["sion_id"], is_active=True,
        ).only("pk").first()
        if not sion:
            return Response(
                {
                    "code": "SION_NOT_FOUND_OR_INACTIVE",
                    "detail": "sion_id must reference an active SION norm.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        requested_ids = identifiers.get("license_ids") or []
        queryset = LicenseDetailsModel.objects.all()
        if requested_ids:
            queryset = queryset.filter(pk__in=requested_ids)
        else:
            # This is identifier-only filtering, not plan eligibility or
            # arithmetic.  It preserves the established "plan this SION"
            # UI while leaving all Auto Plan work to the queue.
            queryset = queryset.filter(export_license__norm_class_id=identifiers["sion_id"]).distinct()
        expiry_scope = identifiers.get("expiry_scope")
        if expiry_scope == "EXPIRED":
            queryset = queryset.filter(license_expiry_date__lt=date.today())
        elif expiry_scope == "EXPIRING_SOON":
            queryset = queryset.filter(
                license_expiry_date__gte=date.today(),
                license_expiry_date__lte=date.today() + timedelta(days=30),
            )
        licenses = list(queryset.only("pk"))
        if requested_ids and len(licenses) != len(set(requested_ids)):
            return Response({"code": "LICENSE_NOT_FOUND", "detail": "One or more licenses are unavailable."}, status=status.HTTP_404_NOT_FOUND)

        from apps.license.services.replan_requests import request_license_replan
        requests = [
            request_license_replan(
                license_id=license_obj.pk,
                reason=f"manual_plan_sion_{(expiry_scope or 'all').lower()}",
                scope=LicenseReplanRequest.SCOPE_SION,
                sion_id=identifiers["sion_id"],
                source_model="sion_planning_rule.plan_sion",
                source_pk=identifiers["sion_id"],
                dispatch=False,
            )
            for license_obj in licenses
        ]
        from apps.license.tasks import replan_sion_batch
        transaction.on_commit(lambda request_ids=[row.pk for row in requests]: replan_sion_batch.delay(request_ids))
        self._audit("SION_REPLAN_QUEUED", sion_id=identifiers["sion_id"], extra={"license_ids": [row.pk for row in licenses], "request_ids": [row.pk for row in requests]})
        return Response({
            "sion_id": identifiers["sion_id"],
            "mode": identifiers["mode"],
            "planning_state": "REPLAN_PENDING",
            "replan_request_ids": [row.pk for row in requests],
            "message": "Licence replanning has been queued for sequential processing.",
        }, status=status.HTTP_202_ACCEPTED)

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
                company_id=None, mode=identifiers["mode"],
            )
        except CompanyIsolationError as exc:
            return Response(exc.as_dict(), status=status.HTTP_403_FORBIDDEN)
        except (PlanningError, ValueError, TypeError) as exc:
            payload = exc.as_dict() if isinstance(exc, PlanningError) else {"error": str(exc)}
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @action(detail=False, methods=("post",), url_path="preview-scoped")
    def preview_scoped(self, request):
        """Preview precisely the licence/SION named by the planning URL."""
        payload = ScopedSionPlanSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            return Response(ScopedSionPlanningService.preview(**payload.validated_data))
        except ScopedPlanningError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=("post",), url_path="save-scoped")
    def save_scoped(self, request):
        payload = ScopedSionPlanSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        if not payload.validated_data.get("preview_version"):
            return Response({"error": "preview_version is required for save."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(ScopedSionPlanningService.save(**payload.validated_data))
        except ScopedPlanningError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)


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

    @staticmethod
    def _resolve_sion_for_license(license_id):
        """Load license and determine its single SION norm.

        Enforces the one-license-one-SION rule: a license must resolve to
        exactly one SION norm, no more, no less.

        Returns: (license_obj, sion_id)
        Raises: PlanningError if no SION or multiple SIONs found
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
                f"License {license_obj.license_number} has no SION norm.",
                code="NO_SION",
            )

        unique_sion_ids = set(sion_ids)
        if len(unique_sion_ids) > 1:
            raise PlanningError(
                f"License {license_obj.license_number} resolves to multiple SION norms. "
                "A license must have exactly one SION.",
                code="MULTIPLE_SIONS",
            )

        return license_obj, next(iter(unique_sion_ids))

    @action(detail=False, methods=("post",), url_path="plan-license")
    def plan_license(self, request):
        """Queue a full REPLACE replan for one licence.

        The worker resolves applicable SIONs from committed source data.  This
        endpoint must not inspect, calculate, or replace plans inline.
        """
        request_serializer = LicenseIdOnlySerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        values = request_serializer.validated_data

        license_obj = LicenseDetailsModel.objects.filter(pk=values["license_id"]).first()
        if not license_obj:
            return Response({"code": "LICENSE_NOT_FOUND", "detail": "License not found."}, status=status.HTTP_404_NOT_FOUND)
        from apps.license.services.replan_requests import request_license_replan
        durable_request = request_license_replan(
            license_id=license_obj.pk,
            reason="manual_plan_license",
            scope=LicenseReplanRequest.SCOPE_LICENSE,
            source_model="sion_planning_rule.plan_license",
            source_pk=license_obj.pk,
        )
        self._audit("LICENSE_REPLAN_QUEUED", extra={"license_id": license_obj.pk, "mode": values["mode"], "request_id": durable_request.pk})
        return Response({
            "license_id": license_obj.pk,
            "license_number": license_obj.license_number,
            "mode": values["mode"],
            "planning_state": "REPLAN_PENDING",
            "replan_request_id": durable_request.pk,
            "message": "Licence replanning has been queued.",
        }, status=status.HTTP_202_ACCEPTED)
