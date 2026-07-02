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
from rest_framework.response import Response

from apps.accounts.permissions import LicensePermission
from apps.license.models import (
    LicenseDetailsModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
)
from apps.license.serializers import LicenseItemPlanSerializer


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

    @action(detail=False, methods=["get"], url_path="norm-prefill")
    def norm_prefill(self, request):
        """
        Compute the norm-based (E1/E5/E132) utilization plan for a license and
        return per-import-item planned values so the planning panel can pre-fill.

        Query: ?license=<id>
        Response: {"norm": "E1"|"E5"|"E132"|"", "plan": {"<item_id>": {planned_quantity, unit_price, planned_cif}}}
        """
        from apps.license.services.norm_plan import detect_norm, norm_plan_for_license

        license_id = request.query_params.get("license")
        if not license_id:
            return Response({"error": "license is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            license_obj = LicenseDetailsModel.objects.get(pk=license_id)
        except LicenseDetailsModel.DoesNotExist:
            return Response({"error": "License not found"}, status=status.HTTP_404_NOT_FOUND)

        norm = detect_norm(license_obj)
        plan = norm_plan_for_license(license_obj)
        # Keys as strings for stable JSON.
        return Response({"norm": norm, "plan": {str(k): v for k, v in plan.items()}})

    @action(detail=False, methods=["post"], url_path="bulk-upsert")
    def bulk_upsert(self, request):
        """
        Replace a licence's utilization plan with the supplied split lines.

        An import item may appear on SEVERAL lines (splits), each optionally
        tagged with an item_name and priced with a unit_price.

        Body:
            {
              "license": <license_id>,
              "lines": [
                {"import_item": <id>, "item_name": <id|null>,
                 "planned_quantity": "20.000", "unit_price": "2.70",
                 "planned_cif_fc": "54.00", "note": ""},
                ...
              ]
            }

        Full-replace semantics: all existing plan lines for the licence are
        deleted and recreated from `lines`. Validates:
          * every item belongs to the licence,
          * per item: Σ split planned_quantity ≤ item capacity (live-allotted + available),
          * Σ planned_cif_fc across the licence ≤ licence balance (shared pool).
        Passing an empty `lines` list clears the plan.
        """
        from collections import defaultdict

        license_id = request.data.get("license")
        lines = request.data.get("lines", [])

        if not license_id:
            return Response({"error": "license is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(lines, list):
            return Response({"error": "lines must be a list"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            license_obj = LicenseDetailsModel.objects.get(pk=license_id)
        except LicenseDetailsModel.DoesNotExist:
            return Response({"error": "License not found"}, status=status.HTTP_404_NOT_FOUND)

        # Pre-load the licence's items for validation.
        items_by_id = {
            it.id: it for it in LicenseImportItemsModel.objects.filter(license_id=license_id)
        }

        # --- Validate line membership + accumulate per-item qty / total CIF ---
        errors = []
        qty_by_item = defaultdict(lambda: Decimal("0"))
        total_planned_cif = Decimal("0")
        for idx, ln in enumerate(lines):
            item_id = ln.get("import_item")
            if item_id not in items_by_id:
                errors.append({"index": idx, "import_item": item_id,
                               "error": "Item not found for this licence"})
                continue
            qty_by_item[item_id] += Decimal(str(ln.get("planned_quantity", 0) or 0))
            total_planned_cif += Decimal(str(ln.get("planned_cif_fc", 0) or 0))
        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        # Per-group capacity: Σ split qty for the item's description-group ≤
        # (available + live-allotted) summed across the whole group.
        from apps.license.services.plan_grouping import group_ids_of
        from apps.license.services.plan_enforcement import live_allotted_qty_for
        for item_id, planned_qty in qty_by_item.items():
            item = items_by_id[item_id]
            gids = group_ids_of(item)
            avail_sum = sum(
                (Decimal(str(items_by_id[i].available_quantity or 0)) for i in gids if i in items_by_id),
                Decimal("0"),
            )
            capacity = live_allotted_qty_for(gids) + avail_sum
            if planned_qty > capacity:
                return Response({
                    "error": (
                        f"Item S.No {item.serial_number}: planned split quantity "
                        f"{planned_qty} exceeds capacity {capacity}."
                    ),
                    "import_item": item_id,
                }, status=status.HTTP_400_BAD_REQUEST)

        # Shared CIF pool: Σ planned_cif_fc ≤ licence balance.
        balance_cif = Decimal(str(license_obj.get_balance_cif or 0))
        if total_planned_cif > balance_cif:
            return Response({
                "error": (
                    f"Planned CIF total {total_planned_cif:.2f} exceeds licence "
                    f"balance {balance_cif:.2f}."
                ),
                "planned_cif_total": str(total_planned_cif),
                "balance_cif": str(balance_cif),
            }, status=status.HTTP_400_BAD_REQUEST)

        # --- Full replace in one transaction --------------------------------
        results = []
        with transaction.atomic():
            LicenseItemPlan.objects.filter(license_id=license_id).delete()
            for ln in lines:
                payload = {
                    "import_item": ln.get("import_item"),
                    "item_name": ln.get("item_name"),
                    "planned_quantity": ln.get("planned_quantity", 0) or 0,
                    "unit_price": ln.get("unit_price", 0) or 0,
                    "planned_cif_fc": ln.get("planned_cif_fc", 0) or 0,
                    "planned_cif_inr": ln.get("planned_cif_inr", 0) or 0,
                    "note": ln.get("note", ""),
                }
                serializer = LicenseItemPlanSerializer(data=payload)
                serializer.is_valid(raise_exception=True)
                serializer.save(license=license_obj)
                results.append(serializer.data)

        return Response({"saved": len(results), "lines": results}, status=status.HTTP_200_OK)
