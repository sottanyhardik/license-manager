# license/views/item_plan.py
"""
CRUD + bulk-upsert for per-import-item utilization plans (LicenseItemPlan).

Endpoints (mounted under /api/):
    GET    /api/license-item-plans/?license=<id>        list plan lines
    POST   /api/license-item-plans/                     create one line
    PATCH  /api/license-item-plans/<id>/                update one line (modify-plan modal)
    DELETE /api/license-item-plans/<id>/                remove one line
    POST   /api/license-item-plans/bulk-upsert/         create/update many lines (planning panel)
"""
from decimal import Decimal

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.accounts.permissions import LicensePermission
from apps.license.models import (
    LicenseDetailsModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
)
from apps.license.serializers import LicenseItemPlanSerializer


def _validate_plan_line_cap(item, planned_quantity, planned_cif_fc, *, exclude_plan_id=None):
    """
    Enforce the same capacity / CIF-pool caps `bulk_upsert` enforces (see its
    docstring) for a SINGLE plan line created/edited via the plain CRUD
    endpoints — the only write path that previously had no cross-line
    validation at all (capacity + CIF pool are cross-line checks; see
    `LicenseItemPlanSerializer`'s docstring).

    Locks the licence and the item's plan-group rows for the duration of the
    check (must be called inside `transaction.atomic()`) so two concurrent
    requests against the same licence can't each read a stale total and
    collectively overcommit it — mirrors `allocate_items`'s
    `select_for_update` pattern in `apps/allotment/views_actions.py`.

    `exclude_plan_id` excludes the row being edited from the "already
    planned" sums so an update compares the NEW value against every OTHER
    line for the group/licence, never the old value plus the new one.
    """
    from django.db.models import DecimalField, Sum, Value
    from django.db.models.functions import Coalesce
    from rest_framework.exceptions import ValidationError

    from apps.core.constants import DEC_0, DEC_000
    from apps.license.services.plan_enforcement import live_allotted_qty_for
    from apps.license.services.plan_grouping import group_ids_of

    planned_quantity = Decimal(str(planned_quantity or 0))
    planned_cif_fc = Decimal(str(planned_cif_fc or 0))

    license_obj = LicenseDetailsModel.objects.select_for_update().get(pk=item.license_id)

    gids = group_ids_of(item)
    group_items = LicenseImportItemsModel.objects.select_for_update().filter(id__in=gids)
    avail_sum = sum(
        (Decimal(str(it.available_quantity or 0)) for it in group_items), Decimal("0"),
    )
    capacity = live_allotted_qty_for(gids) + avail_sum

    group_plans = LicenseItemPlan.objects.filter(import_item_id__in=gids)
    if exclude_plan_id is not None:
        group_plans = group_plans.exclude(pk=exclude_plan_id)
    existing_group_qty = group_plans.aggregate(
        t=Coalesce(Sum("planned_quantity"), Value(DEC_000), output_field=DecimalField()),
    )["t"]
    new_group_qty = existing_group_qty + planned_quantity
    if new_group_qty > capacity:
        raise ValidationError({
            "planned_quantity": (
                f"Planned quantity {new_group_qty} exceeds available capacity "
                f"{capacity} for this item group (Quantity Exceeded)."
            ),
        })

    license_plans = LicenseItemPlan.objects.filter(license_id=license_obj.pk)
    if exclude_plan_id is not None:
        license_plans = license_plans.exclude(pk=exclude_plan_id)
    existing_license_cif = license_plans.aggregate(
        t=Coalesce(Sum("planned_cif_fc"), Value(DEC_0), output_field=DecimalField()),
    )["t"]
    new_license_cif = existing_license_cif + planned_cif_fc
    balance_cif = Decimal(str(license_obj.get_balance_cif or 0))
    if new_license_cif > balance_cif:
        raise ValidationError({
            "planned_cif_fc": (
                f"Planned CIF total {new_license_cif:.2f} exceeds licence balance "
                f"{balance_cif:.2f} (Value Exceeded)."
            ),
        })


class LicenseItemPlanViewSet(viewsets.ModelViewSet):
    """Manage a licence's per-item utilization plan."""
    queryset = (
        LicenseItemPlan.objects
        .select_related("import_item", "import_item__license", "license")
        .all()
    )
    serializer_class = LicenseItemPlanSerializer
    permission_classes = [LicensePermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["license", "import_item"]

    def _company_id(self):
        user = self.request.user
        if user.is_superuser:
            return None
        company_id = getattr(user, "company_id", None)
        if not company_id:
            raise PermissionDenied("A company-scoped user is required.")
        return company_id

    def _authorized_licenses(self):
        queryset = LicenseDetailsModel.objects.all()
        company_id = self._company_id()
        return queryset if company_id is None else queryset.filter(exporter_id=company_id)

    def get_queryset(self):
        queryset = super().get_queryset()
        company_id = self._company_id()
        if company_id is None:
            return queryset
        return queryset.filter(import_item__license__exporter_id=company_id)

    def _assert_item_access(self, item):
        company_id = self._company_id()
        if company_id is not None and item.license.exporter_id != company_id:
            raise PermissionDenied("This planning item belongs to another company.")

    def perform_create(self, serializer):
        item = serializer.validated_data["import_item"]
        self._assert_item_access(item)
        planned_quantity = serializer.validated_data.get("planned_quantity", 0)
        planned_cif_fc = serializer.validated_data.get("planned_cif_fc", 0)
        with transaction.atomic():
            _validate_plan_line_cap(item, planned_quantity, planned_cif_fc)
            serializer.save()

    def perform_update(self, serializer):
        instance = serializer.instance
        item = serializer.validated_data.get("import_item", instance.import_item)
        self._assert_item_access(item)
        planned_quantity = serializer.validated_data.get("planned_quantity", instance.planned_quantity)
        planned_cif_fc = serializer.validated_data.get("planned_cif_fc", instance.planned_cif_fc)
        with transaction.atomic():
            _validate_plan_line_cap(item, planned_quantity, planned_cif_fc, exclude_plan_id=instance.pk)
            serializer.save()

    @action(detail=False, methods=["post"], url_path="bulk-upsert")
    def bulk_upsert(self, request):
        """Replace one license's manual plan through the canonical writer."""
        from apps.license.services.canonical_planning_service import (
            CanonicalPlanningService,
            PlanningError,
        )

        license_id = request.data.get("license")
        lines = request.data.get("lines", [])
        if not license_id:
            return Response({"error": "license is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(lines, list):
            return Response({"error": "lines must be a list"}, status=status.HTTP_400_BAD_REQUEST)

        items_input = [{
            "import_item_id": line.get("import_item"),
            "item_name_id": line.get("item_name"),
            "requested_quantity": line.get("planned_quantity", 0) or 0,
            "unit_price": line.get("unit_price", 0) or 0,
            "note": line.get("note", ""),
        } for line in lines]
        try:
            result = CanonicalPlanningService.build_canonical_plan(
                license_id=license_id,
                items=items_input,
                force_replan=True,
                company_id=self._company_id(),
            )
        except PlanningError as exc:
            error = exc.as_dict()
            if error["code"] == "LICENSE_NOT_FOUND":
                http_status = status.HTTP_404_NOT_FOUND
            elif error["code"] in ("COMPANY_MISMATCH", "LICENSE_MISMATCH"):
                http_status = status.HTTP_403_FORBIDDEN
            else:
                http_status = status.HTTP_400_BAD_REQUEST
            return Response(error, status=http_status)

        response_lines = [{
            "import_item": row["import_item_id"],
            "item_name": row.get("item_name_id"),
            "planned_quantity": row["allocated_quantity"],
            "unit_price": row["unit_price"],
            "planned_cif_fc": row["planned_cif_fc"],
            "note": row.get("note", ""),
        } for row in result["allocated_items"] if row.get("allocated_quantity", 0) > 0]
        return Response(
            {"saved": len(response_lines), "lines": response_lines},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="planning-norms")
    def planning_norms(self, request):
        """Canonical selected-SION rows and totals; no client aggregation."""
        from apps.license.services.canonical_planning_service import (
            CompanyIsolationError,
            PlanningError,
            CanonicalPlanningService,
        )

        raw_ids = request.query_params.getlist("license_ids")
        if len(raw_ids) == 1:
            raw_ids = [part.strip() for part in raw_ids[0].split(",") if part.strip()]
        try:
            common = dict(
                company_id=self._company_id(),
                hsn=request.query_params.get("hsn", ""),
                product=request.query_params.get("product", ""),
                logic=request.query_params.get("logic", "AND"),
            )
            sion_id = request.query_params.get("sion_id")
            result = (
                CanonicalPlanningService.planning_sion_snapshot(sion_id, raw_ids, **common)
                if sion_id not in (None, "")
                else CanonicalPlanningService.applicable_planning_sions(raw_ids, **common)
            )
        except CompanyIsolationError as exc:
            return Response(exc.as_dict(), status=status.HTTP_403_FORBIDDEN)
        except PlanningError as exc:
            return Response(exc.as_dict(), status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)
