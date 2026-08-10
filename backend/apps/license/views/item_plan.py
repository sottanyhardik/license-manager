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

    def perform_create(self, serializer):
        item = serializer.validated_data["import_item"]
        planned_quantity = serializer.validated_data.get("planned_quantity", 0)
        planned_cif_fc = serializer.validated_data.get("planned_cif_fc", 0)
        with transaction.atomic():
            _validate_plan_line_cap(item, planned_quantity, planned_cif_fc)
            serializer.save()

    def perform_update(self, serializer):
        instance = serializer.instance
        item = serializer.validated_data.get("import_item", instance.import_item)
        planned_quantity = serializer.validated_data.get("planned_quantity", instance.planned_quantity)
        planned_cif_fc = serializer.validated_data.get("planned_cif_fc", instance.planned_cif_fc)
        with transaction.atomic():
            _validate_plan_line_cap(item, planned_quantity, planned_cif_fc, exclude_plan_id=instance.pk)
            serializer.save()

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

        # Normalize request lines to CanonicalPlanningService input format.
        # The service expects import_item_id and requested_quantity keys;
        # the API uses import_item and planned_quantity for compatibility.
        items_input = [
            {
                "import_item_id": ln.get("import_item"),
                "item_name_id": ln.get("item_name"),
                "requested_quantity": ln.get("planned_quantity", 0) or 0,
                "unit_price": ln.get("unit_price", 0) or 0,
                "note": ln.get("note", ""),
            }
            for ln in lines
        ]

        try:
            # The service handles all validation (license exists, items belong,
            # capacity check, CIF pool check) and persistence inside one atomic
            # transaction with row locks, so concurrent calls serialize safely.
            result = CanonicalPlanningService.build_canonical_plan(
                license_id=license_id,
                items=items_input,
                force_replan=True,
                company_id=request.user.company_id if hasattr(request.user, 'company_id') else None,
            )

            # Translate the service result back to the API response format.
            # Map allocated_items to the expected response structure.
            response_lines = []
            for allocated in result["allocated_items"]:
                # Only include lines with allocated quantity > 0 (the service
                # returns all requested items, but we only persist non-zero rows)
                if allocated.get("allocated_quantity", 0) > 0:
                    response_lines.append({
                        "import_item": allocated["import_item_id"],
                        "item_name": allocated.get("item_name_id"),
                        "planned_quantity": allocated["allocated_quantity"],
                        "unit_price": allocated["unit_price"],
                        "planned_cif_fc": allocated["planned_cif_fc"],
                        "note": allocated.get("note", ""),
                    })

            return Response(
                {"saved": len(response_lines), "lines": response_lines},
                status=status.HTTP_200_OK,
            )

        except PlanningError as exc:
            # Translate service errors to API response format, preserving the
            # error code and details for client-side error handling.
            error_dict = exc.as_dict()
            # Map specific error codes to HTTP status codes.
            if error_dict["code"] == "LICENSE_NOT_FOUND":
                http_status = status.HTTP_404_NOT_FOUND
            elif error_dict["code"] in ("COMPANY_MISMATCH", "LICENSE_MISMATCH"):
                http_status = status.HTTP_403_FORBIDDEN
            else:  # INVALID_INPUT, INSUFFICIENT_QUANTITY
                http_status = status.HTTP_400_BAD_REQUEST
            return Response(error_dict, status=http_status)

    @action(detail=False, methods=["post"], url_path="e1-auto-plan")
    def e1_auto_plan(self, request):
        """
        Compute and immediately save an E1 auto-plan for a licence.

        Applies two rules in waterfall order (Rule 1 → Rule 2):
          Rule 1 — OTHER CONFECTIONERY INGREDIENTS: unit_price = 3.0
          Rule 2 — MILK & MILK (SWP / DWP / WPC): avg-price split

        Full-replace semantics: any existing manual plan is overwritten.

        Body:  {"license": <id>}
        Returns: {"norm": "E1", "planned": N, "remaining_cif": X,
                  "lines": [{import_item, item_name_label, planned_quantity,
                              unit_price, planned_cif_fc}]}
        """
        from apps.license.services.e1_auto_plan import compute_e1_auto_plan
        from apps.license.services.norm_plan import detect_norm

        license_id = request.data.get("license")
        if not license_id:
            return Response({"error": "license is required"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            license_obj = LicenseDetailsModel.objects.prefetch_related(
                'export_license__norm_class',
                'import_license__items',
                'import_license__hs_code',
            ).get(pk=license_id)
        except LicenseDetailsModel.DoesNotExist:
            return Response({"error": "License not found"},
                            status=status.HTTP_404_NOT_FOUND)

        norm = detect_norm(license_obj)
        if norm != 'E1':
            return Response(
                {"error": (
                    f"This endpoint is for E1 licenses only. "
                    f"This license uses norm '{norm or 'unknown'}'. "
                    f"Use /auto-plan/ for E5 and E132."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lines, remaining_cif = compute_e1_auto_plan(license_obj)

        if not lines:
            return Response(
                {"error": (
                    "No items could be auto-planned. "
                    "Check that this license has import items classified as "
                    "Other Confectionery Ingredients or Milk & Milk products."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Full-replace: delete existing plan and save computed lines.
        from apps.license.services.plan_enforcement import save_plan_lines_for_license
        with transaction.atomic():
            save_plan_lines_for_license(license_obj, lines)

        return Response(
            {
                "norm": "E1",
                "planned": len(lines),
                "remaining_cif": remaining_cif,
                "lines": [
                    {
                        "import_item":     ln["import_item"],
                        "item_name_label": (ln.get("note", "").split("— ")[-1].rstrip(")") or ""),
                        "planned_quantity": ln["planned_quantity"],
                        "unit_price":      ln["unit_price"],
                        "planned_cif_fc":  ln["planned_cif_fc"],
                    }
                    for ln in lines
                ],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="auto-plan")
    def auto_plan(self, request):
        """
        Unified Auto Plan endpoint — detects the licence norm (E1, E5, E126,
        or E132) and dispatches to the appropriate waterfall service.

        Body:  {"license": <id>}
        Returns: {"norm": "E1"|"E5"|"E126"|"E132", "planned": N, "remaining_cif": X, "lines": [...]}
        """
        from apps.license.services.canonical_planning_service import (
            CanonicalPlanningService,
            PlanningError,
        )
        from apps.license.services.norm_plan import detect_norm

        license_id = request.data.get("license")
        if not license_id:
            return Response({"error": "license is required"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            license_obj = LicenseDetailsModel.objects.prefetch_related(
                'export_license__norm_class',
                'import_license__items',
                'import_license__hs_code',
            ).get(pk=license_id)
        except LicenseDetailsModel.DoesNotExist:
            return Response({"error": "License not found"},
                            status=status.HTTP_404_NOT_FOUND)

        norm = detect_norm(license_obj)
        if norm == 'E1':
            from apps.license.services.e1_auto_plan import compute_e1_auto_plan
            lines, remaining_cif = compute_e1_auto_plan(license_obj)
        elif norm == 'E5':
            from apps.license.services.e5_auto_plan import compute_e5_auto_plan
            lines, remaining_cif = compute_e5_auto_plan(license_obj)
        elif norm == 'E126':
            from apps.license.services.e126_auto_plan import compute_e126_auto_plan
            lines, remaining_cif = compute_e126_auto_plan(license_obj)
        elif norm == 'E132':
            from apps.license.services.e132_auto_plan import compute_e132_auto_plan
            lines, remaining_cif = compute_e132_auto_plan(license_obj)
        else:
            return Response(
                {"error": (
                    f"Auto Plan supports E1, E5, E126, and E132 licenses only. "
                    f"This license uses norm '{norm or 'unknown'}'."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not lines:
            return Response(
                {"error": (
                    "No items could be auto-planned. "
                    "Check that this license has import items matching the "
                    f"{norm} classification rules."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Convert the legacy compute_*_auto_plan output to CanonicalPlanningService input format.
        # The compute functions return dicts with: import_item, item_name, planned_quantity,
        # unit_price, planned_cif_fc, note.
        items_input = [
            {
                "import_item_id": ln["import_item"],
                "item_name_id": ln.get("item_name"),
                "requested_quantity": ln["planned_quantity"],
                "unit_price": ln["unit_price"],
                "note": ln.get("note", ""),
            }
            for ln in lines
        ]

        try:
            # Use CanonicalPlanningService as the authoritative persistence engine.
            # force_replan=True because auto-plan always replaces the existing plan.
            result = CanonicalPlanningService.build_canonical_plan(
                license_id=license_id,
                norm_class=norm,
                items=items_input,
                force_replan=True,
                company_id=request.user.company_id if hasattr(request.user, 'company_id') else None,
            )

            # Build the response with the same format as before for backward compatibility.
            # Extract item_name_label from the note field (format: "Auto-planned (E1 Step X – ...)")
            response_lines = []
            for allocated in result["allocated_items"]:
                if allocated.get("allocated_quantity", 0) > 0:
                    note = allocated.get("note", "")
                    # Extract label from note: "Auto-planned (E1 Step X – Label)" → "Label"
                    item_name_label = (note.split("— ")[-1].rstrip(")") or "") if note else ""
                    response_lines.append({
                        "import_item": allocated["import_item_id"],
                        "item_name_label": item_name_label,
                        "planned_quantity": allocated["allocated_quantity"],
                        "unit_price": allocated["unit_price"],
                        "planned_cif_fc": allocated["planned_cif_fc"],
                    })

            summary = result["allocation_summary"]
            return Response(
                {
                    "norm": norm,
                    "planned": len(response_lines),
                    "remaining_cif": float(summary["remaining_balance_cif"]),
                    "lines": response_lines,
                },
                status=status.HTTP_200_OK,
            )

        except PlanningError as exc:
            error_dict = exc.as_dict()
            if error_dict["code"] == "LICENSE_NOT_FOUND":
                http_status = status.HTTP_404_NOT_FOUND
            elif error_dict["code"] in ("COMPANY_MISMATCH", "LICENSE_MISMATCH"):
                http_status = status.HTTP_403_FORBIDDEN
            else:  # INVALID_INPUT, INSUFFICIENT_QUANTITY
                http_status = status.HTTP_400_BAD_REQUEST
            return Response(error_dict, status=http_status)

    @action(detail=False, methods=["post"], url_path="auto-plan-all")
    def auto_plan_all(self, request):
        """
        Batch Auto Plan for ALL eligible DFIA licenses (E1 / E5 / E126 / E132).

        Eligible: norm in (E1, E5, E126, E132) AND LIVE balance_cif > 0.
        "Already planned": existing plan covers ≥ 99 % of LIVE balance CIF.
        Failures are isolated per-license; the batch always continues.

        Body: {}
        Returns: { total, planned, already_planned, skipped_unknown_norm,
                   failed, errors: [{license, error}] }
        """
        from decimal import Decimal
        from django.db import models as _models
        from apps.license.services.canonical_planning_service import (
            CanonicalPlanningService,
            PlanningError,
        )
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        from apps.license.services.norm_plan import detect_norm
        from apps.license.services.e1_auto_plan import compute_e1_auto_plan
        from apps.license.services.e5_auto_plan import compute_e5_auto_plan
        from apps.license.services.e126_auto_plan import compute_e126_auto_plan
        from apps.license.services.e132_auto_plan import compute_e132_auto_plan

        # BL-LEDGER-02: eligibility used to be filtered at the DB level
        # against the cached `balance__balance_cif` column, which can be
        # stale. Fetch every active license instead and resolve eligibility
        # against the LIVE, batched-computed balance below (a fixed number
        # of queries for the whole batch, not one live call per license).
        licenses = (
            LicenseDetailsModel.objects
            .filter(flags__is_active=True)
            .prefetch_related(
                'export_license__norm_class',
                'import_license__items',
                'import_license__hs_code',
            )
            .select_related('balance')
            .order_by('id')
        )

        license_ids = [lic.id for lic in licenses]
        live_balance_by_license = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(license_ids)

        res = dict(total=0, planned=0, already_planned=0,
                   skipped_unknown_norm=0, failed=0, errors=[])

        for lic in licenses:
            bal = float(live_balance_by_license.get(lic.id, Decimal('0')) or 0)
            if bal <= 0:
                # Same effect as the old `balance__balance_cif__gt=0` DB
                # filter: not eligible at all, not counted anywhere below.
                continue

            norm = detect_norm(lic)
            if norm not in ('E1', 'E5', 'E126', 'E132'):
                res["skipped_unknown_norm"] += 1
                continue

            res["total"] += 1
            try:
                # Check if already planned (existing plan covers >= 99% of LIVE balance)
                existing = float(
                    LicenseItemPlan.objects
                    .filter(license=lic)
                    .aggregate(t=_models.Sum("planned_cif_fc"))["t"] or 0
                )
                if existing >= bal * 0.99:
                    res["already_planned"] += 1
                    continue

                # Compute the plan lines using the appropriate norm engine
                if norm == 'E1':
                    lines, _ = compute_e1_auto_plan(lic)
                elif norm == 'E5':
                    lines, _ = compute_e5_auto_plan(lic)
                elif norm == 'E126':
                    lines, _ = compute_e126_auto_plan(lic)
                else:  # E132
                    lines, _ = compute_e132_auto_plan(lic)

                if not lines:
                    res["already_planned"] += 1
                    continue

                # Convert the legacy compute_*_auto_plan output to CanonicalPlanningService input format
                items_input = [
                    {
                        "import_item_id": ln["import_item"],
                        "item_name_id": ln.get("item_name"),
                        "requested_quantity": ln["planned_quantity"],
                        "unit_price": ln["unit_price"],
                        "note": ln.get("note", ""),
                    }
                    for ln in lines
                ]

                # Use CanonicalPlanningService as the authoritative persistence engine.
                # force_replan=True because auto-plan always replaces the existing plan.
                CanonicalPlanningService.build_canonical_plan(
                    license_id=lic.id,
                    norm_class=norm,
                    items=items_input,
                    force_replan=True,
                    company_id=None,  # Trusted internal batch operation
                )
                res["planned"] += 1

            except PlanningError as exc:
                # Isolate failures per-license; batch continues
                res["failed"] += 1
                res["errors"].append({"license": lic.license_number, "error": exc.message})
            except Exception as exc:
                # Catch other unexpected errors and report them
                res["failed"] += 1
                res["errors"].append({"license": lic.license_number, "error": str(exc)})

        return Response(res, status=status.HTTP_200_OK)
