# allotment/views.py
"""
Allotment views.

AllotmentViewSet     — DRF ModelViewSet for CRUD + copy + PDF generation.
AllotmentActionViewSet — ViewSet for per-allotment actions (available licenses,
                         item allocation, item deletion, PDF, transfer letter).

No ORM lives here. All mutations are delegated to the service layer
(apps.allotment.services.allotment_service). The view is responsible only for
auth/permission, serialization, filtering, and HTTP responses.
"""
import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.accounts.permissions import AllotmentPermission
from apps.allotment.filters import AllotmentFilter
from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.allotment.serializers import AllotmentSerializer
from apps.allotment.services.allotment_service import (
    create_allotment,
    delete_allotment,
    update_allotment,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_int(value, *, default=0, minimum=None):
    """Parse an integer safely; return *default* on failure."""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and result < minimum:
        return minimum
    return result


def _safe_decimal(value, default=Decimal("0")) -> Decimal:
    """Parse a Decimal safely; return *default* on failure."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# AllotmentViewSet
# ---------------------------------------------------------------------------

class AllotmentViewSet(viewsets.ModelViewSet):
    """
    CRUD endpoints for AllotmentModel.

    Mutations (create/update/destroy) are handled by the service layer so
    business logic and side effects (Celery task dispatch) stay out of the view.
    """

    serializer_class = AllotmentSerializer
    permission_classes = [AllotmentPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AllotmentFilter
    search_fields = ["item_name", "company__name", "invoice", "bl_detail"]
    ordering_fields = ["estimated_arrival_date", "modified_on", "company__name", "item_name"]
    ordering = ["-estimated_arrival_date"]

    def get_queryset(self):
        return (
            AllotmentModel.objects
            .select_related("company", "port", "related_company")
            .prefetch_related(
                "allotment_details",
                "allotment_details__item",
                "allotment_details__item__license",
                "allotment_details__item__license__exporter",
                "allotment_details__item__license__port",
                "allotment_details__item__hs_code",
                "bill_of_entry",
            )
            .order_by("-estimated_arrival_date")
            .distinct()
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        allotment = create_allotment(dict(serializer.validated_data), request.user)
        out = AllotmentSerializer(allotment, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        allotment = update_allotment(
            instance.pk, dict(serializer.validated_data), request.user
        )
        out = AllotmentSerializer(allotment, context={"request": request})
        return Response(out.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        delete_allotment(instance.pk, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="generate-pdf")
    def generate_pdf(self, request, pk=None):
        """
        Async PDF generation — dispatch Celery task and return task_id.

        The task import is intentionally lazy; if apps.allotment.tasks is not
        yet available the endpoint degrades gracefully and still returns 202.
        """
        instance = self.get_object()
        try:
            from apps.allotment.tasks import generate_allotment_pdf_task
            task = generate_allotment_pdf_task.delay(instance.pk)
            return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)
        except Exception:
            return Response(
                {"task_id": None, "detail": "PDF task not available"},
                status=status.HTTP_202_ACCEPTED,
            )

    @action(detail=True, methods=["post"], url_path="copy")
    def copy_allotment(self, request, pk=None):
        """
        Copy an allotment without invoice number and allotment items.

        Creates a new AllotmentModel with the same header fields EXCEPT:
        - invoice is cleared
        - allotment_details are NOT copied
        - is_approved is reset to False
        """
        original = self.get_object()

        copied_data = {
            "company": original.company_id,
            "type": original.type,
            "required_quantity": original.required_quantity,
            "unit_value_per_unit": original.unit_value_per_unit,
            "cif_fc": original.cif_fc,
            "cif_inr": original.cif_inr,
            "exchange_rate": original.exchange_rate,
            "item_name": original.item_name,
            "contact_person": original.contact_person,
            "contact_number": original.contact_number,
            "estimated_arrival_date": original.estimated_arrival_date,
            "bl_detail": original.bl_detail,
            "port": original.port_id if original.port_id else None,
            "related_company": original.related_company_id if original.related_company_id else None,
            "is_approved": False,
            # invoice intentionally omitted (cleared on copy)
        }

        # Remove None values so serializer defaults apply
        copied_data = {k: v for k, v in copied_data.items() if v is not None}

        serializer = AllotmentSerializer(data=copied_data, context={"request": request})
        if serializer.is_valid():
            new_allotment = create_allotment(dict(serializer.validated_data), request.user)
            return Response(
                AllotmentSerializer(new_allotment, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# AllotmentActionViewSet
# ---------------------------------------------------------------------------

class AllotmentActionViewSet(ViewSet):
    """
    Per-allotment action endpoints (registered separately as 'allotment-actions').

    All actions take *pk* = allotment ID from the URL.

    Routes (relative to /api/v1/allotment-actions/{id}/):
      GET   available-licenses/       — paginated list of allocatable import items
      POST  allocate-items/           — atomically create/amend AllotmentItems
      DELETE delete-item/{item_id}/   — remove one AllotmentItems row
      GET   generate-pdf/             — async PDF dispatch
      POST  generate-transfer-letter/ — generate transfer letter (stub if not ported)
    """

    permission_classes = [AllotmentPermission]

    def get_permissions(self):
        if self.action == "generate_transfer_letter":
            from apps.accounts.permissions import TransferLetterPermission
            return [TransferLetterPermission()]
        return super().get_permissions()

    # ------------------------------------------------------------------
    # available_licenses
    # ------------------------------------------------------------------

    @action(detail=True, methods=["get"], url_path="available-licenses")
    def available_licenses(self, request, pk=None):
        """
        Paginated list of LicenseImportItemsModel rows with available_quantity > 0.

        Mirrors legacy AllotmentActionViewSet.available_licenses exactly, adapted
        to use ImportItemSerializer (no LicenseImportItemSerializer in this app).
        """
        from apps.license.models import LicenseImportItemsModel
        from apps.license.serializers import ImportItemSerializer
        from django.db.models import Q

        allotment = get_object_or_404(
            AllotmentModel.objects.prefetch_related(
                "allotment_details__item__license__exporter"
            ),
            pk=pk,
        )

        # ------ Query params ------
        params = request.query_params
        search = params.get("search", "")
        license_number = params.get("license_number", "")
        exporter = params.get("exporter", "")
        exclude_exporter = params.get("exclude_exporter", "")
        description = params.get("description", "")
        qty_min = params.get("qty_min", "") or params.get("available_quantity_gte", "")
        qty_max = params.get("qty_max", "") or params.get("available_quantity_lte", "")
        value_min = params.get("value_min", "") or params.get("available_value_gte", "")
        value_max = params.get("value_max", "") or params.get("available_value_lte", "")
        notification_number = params.get("notification_number", "")
        norm_class = params.get("norm_class", "")
        hs_code = params.get("hs_code", "")
        is_restricted = params.get("is_restricted", "")
        purchase_status = params.get("purchase_status", "")
        license_status = params.get("license_status", "")
        item_names = params.get("item_names", "")
        expiry_date_from = params.get("expiry_date_from", "")
        expiry_date_to = params.get("expiry_date_to", "")

        # ------ Base queryset ------
        queryset = (
            LicenseImportItemsModel.objects
            .filter(available_quantity__gt=0)
            .select_related(
                "license",
                "license__exporter",
                "license__port",
                "hs_code",
            )
            .prefetch_related(
                "items",
                "items__sion_norm_class",
                "license__export_license",
            )
            .order_by("license__license_expiry_date", "serial_number")
        )

        # ------ Filters ------
        if search:
            queryset = queryset.filter(
                Q(license__license_number__icontains=search)
                | Q(description__icontains=search)
                | Q(license__exporter__name__icontains=search)
            )

        if license_number:
            queryset = queryset.filter(
                license__license_number__icontains=license_number
            )

        if description:
            # Prefer exact matches to prevent substring false-positives (e.g.
            # "Other" should not match "Mother board").
            exact_qs = queryset.filter(
                Q(items__name__iexact=description)
                | Q(description__iexact=description)
                | Q(hs_code__product_description__iexact=description)
            ).distinct()
            if exact_qs.exists():
                queryset = exact_qs
            else:
                queryset = queryset.filter(
                    Q(items__name__icontains=description)
                    | Q(description__icontains=description)
                    | Q(hs_code__hs_code__icontains=description)
                    | Q(hs_code__product_description__icontains=description)
                ).distinct()

        if exporter:
            queryset = queryset.filter(license__exporter_id=exporter)

        if exclude_exporter:
            queryset = queryset.exclude(license__exporter_id=exclude_exporter)

        if qty_min:
            try:
                queryset = queryset.filter(
                    available_quantity__gte=Decimal(qty_min)
                )
            except InvalidOperation:
                pass

        if qty_max:
            try:
                queryset = queryset.filter(
                    available_quantity__lte=Decimal(qty_max)
                )
            except InvalidOperation:
                pass

        if value_min:
            try:
                queryset = queryset.filter(
                    available_value__gte=Decimal(value_min)
                )
            except InvalidOperation:
                pass

        if value_max:
            try:
                queryset = queryset.filter(
                    available_value__lte=Decimal(value_max)
                )
            except InvalidOperation:
                pass

        if notification_number:
            queryset = queryset.filter(
                license__notification_number__code=notification_number
            )

        if norm_class:
            queryset = queryset.filter(
                license__export_license__norm_class_id=norm_class
            )

        if hs_code:
            queryset = queryset.filter(hs_code__hs_code__startswith=hs_code)

        if is_restricted and is_restricted.lower() != "all":
            if is_restricted.lower() in ("true", "1", "yes"):
                queryset = queryset.filter(is_restricted=True)
            elif is_restricted.lower() in ("false", "0", "no"):
                queryset = queryset.filter(is_restricted=False)

        if purchase_status:
            status_list = [s.strip() for s in purchase_status.split(",") if s.strip()]
            if status_list:
                queryset = queryset.filter(
                    license__purchase_status__code__in=status_list
                )

        if license_status and license_status.lower() != "all":
            from datetime import timedelta
            today = timezone.now().date()
            if license_status.lower() == "active":
                queryset = queryset.filter(license__license_expiry_date__gte=today)
            elif license_status.lower() == "expired":
                queryset = queryset.filter(license__license_expiry_date__lt=today)
            elif license_status.lower() == "expiring_soon":
                expiring_date = today + timedelta(days=30)
                queryset = queryset.filter(
                    license__license_expiry_date__gte=today,
                    license__license_expiry_date__lte=expiring_date,
                )

        if expiry_date_from:
            try:
                from datetime import datetime as _dt
                queryset = queryset.filter(
                    license__license_expiry_date__gte=_dt.strptime(
                        expiry_date_from, "%Y-%m-%d"
                    ).date()
                )
            except (ValueError, TypeError):
                pass

        if expiry_date_to:
            try:
                from datetime import datetime as _dt
                queryset = queryset.filter(
                    license__license_expiry_date__lte=_dt.strptime(
                        expiry_date_to, "%Y-%m-%d"
                    ).date()
                )
            except (ValueError, TypeError):
                pass

        if item_names:
            item_name_ids = [
                int(i.strip())
                for i in item_names.split(",")
                if i.strip().isdigit()
            ]
            if item_name_ids:
                queryset = queryset.filter(items__id__in=item_name_ids).distinct()

        # ------ Pagination ------
        page = _safe_int(params.get("page"), default=1, minimum=1)
        page_size = min(
            _safe_int(params.get("page_size"), default=20, minimum=1), 100
        )
        start = (page - 1) * page_size
        end = start + page_size

        total_count = queryset.count()
        page_qs = queryset[start:end]

        # ------ Serialize ------
        items_data = ImportItemSerializer(
            page_qs, many=True, context={"request": request}
        ).data
        allotment_data = AllotmentSerializer(
            allotment, context={"request": request}
        ).data

        # Add $20 buffer to required_value for value-ceiling filtering on the
        # frontend — matches legacy behaviour exactly.
        allotment_data["required_value_with_buffer"] = str(
            float(allotment_data.get("required_value", 0)) + 20
        )

        return Response(
            {
                "allotment": allotment_data,
                "available_items": items_data,
                "count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size,
            }
        )

    # ------------------------------------------------------------------
    # allocate_items
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="allocate-items")
    @transaction.atomic
    def allocate_items(self, request, pk=None):
        """
        Atomically allocate selected import items to this allotment.

        Accepts either of two payload shapes for backward-compat with the
        legacy API:
          { "allocations": [{ "item_id": N, "qty": X, "cif_fc": Y, "cif_inr": Z }] }
          { "items":       [{ "id": N,      "qty": X, "cif_fc": Y }] }

        For each allocation:
          - validates available_quantity >= requested qty
          - validates available CIF FC (restricted vs unrestricted logic)
          - checks LicenseItemPlan cap if a plan exists
          - creates or amends the AllotmentItems row (unique_together enforced)
          - after commit: dispatches recompute_license_balance_task per license

        Returns:
          { success: <int>, created_items: [...], errors: [...], allotment: {...} }
        """
        from apps.license.models import LicenseImportItemsModel, LicenseItemPlan
        from django.db.models import Sum as _Sum, DecimalField as _DF, Value as _Val
        from django.db.models.functions import Coalesce as _Coalesce

        allotment = get_object_or_404(AllotmentModel, pk=pk)

        # Support both payload shapes
        allocations = request.data.get("allocations") or []
        if not allocations:
            # Try the alternate shape { items: [{ id, qty, cif_fc }] }
            items_payload = request.data.get("items") or []
            for item in items_payload:
                allocations.append(
                    {
                        "item_id": item.get("id"),
                        "qty": item.get("qty", 0),
                        "cif_fc": item.get("cif_fc", 0),
                        "cif_inr": item.get("cif_inr", 0),
                    }
                )

        if not allocations:
            return Response(
                {"error": "No allocations provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_items = []
        errors = []
        affected_license_ids = set()

        for allocation in allocations:
            item_id = allocation.get("item_id")
            qty = _safe_decimal(allocation.get("qty", 0))
            cif_fc = _safe_decimal(allocation.get("cif_fc", 0))
            cif_inr = _safe_decimal(allocation.get("cif_inr", 0))

            try:
                # select_for_update prevents concurrent over-allotment races
                # (the whole action runs in one transaction via @transaction.atomic)
                license_item = (
                    LicenseImportItemsModel.objects.select_for_update().get(pk=item_id)
                )

                # --- Quantity check ---
                avail_qty = _safe_decimal(license_item.available_quantity)
                if avail_qty < qty:
                    errors.append(
                        {
                            "item_id": item_id,
                            "error": (
                                f"Insufficient available quantity. "
                                f"Available: {avail_qty}, Requested: {qty}"
                            ),
                        }
                    )
                    continue

                # --- CIF FC check ---
                # Non-restricted: use available_value (denormalized balance).
                # Restricted: same field, but the field is set by the
                # restriction-balance updater. Exception licenses (098/2009 or
                # Conversion/CO) skip the restriction cap.
                available_cif = _safe_decimal(license_item.available_value)

                if license_item.is_restricted:
                    notif_code = None
                    purchase_code = None
                    if license_item.license_id:
                        try:
                            lic = license_item.license
                            if lic.notification_number_id and lic.notification_number:
                                notif_code = lic.notification_number.code
                            if lic.purchase_status_id and lic.purchase_status:
                                purchase_code = lic.purchase_status.code
                        except Exception:
                            pass

                    is_exception = notif_code == "098/2009" or purchase_code == "CO"

                    has_restriction = license_item.items.filter(
                        sion_norm_class__isnull=False,
                        restriction_percentage__gt=0,
                    ).exists()

                    if has_restriction and not is_exception:
                        stored = _safe_decimal(license_item.available_value)
                        available_cif = stored if stored > 0 else available_cif
                    # else: exception license or no restriction — available_cif already set

                if available_cif < cif_fc:
                    errors.append(
                        {
                            "item_id": item_id,
                            "error": (
                                f"Insufficient available CIF FC. "
                                f"Available: {available_cif:.2f}, Requested: {cif_fc}"
                            ),
                        }
                    )
                    continue

                # --- Allotment balance quantity check ---
                current_allotted = _safe_decimal(allotment.alloted_quantity)
                required_qty = _safe_decimal(allotment.required_quantity)
                remaining = required_qty - current_allotted
                if qty > remaining:
                    errors.append(
                        {
                            "item_id": item_id,
                            "error": (
                                f"Allocation exceeds balance quantity. "
                                f"Balance: {remaining}, Requested: {qty}"
                            ),
                        }
                    )
                    continue

                # --- Utilization-plan cap (per import item) ---
                plans_qs = LicenseItemPlan.objects.filter(
                    import_item_id=item_id
                )
                if plans_qs.exists():
                    plan_agg = plans_qs.aggregate(
                        pq=_Coalesce(
                            _Sum("planned_quantity"),
                            _Val(Decimal("0")),
                            output_field=_DF(),
                        ),
                        pv=_Coalesce(
                            _Sum("planned_cif_fc"),
                            _Val(Decimal("0")),
                            output_field=_DF(),
                        ),
                    )
                    planned_qty = _safe_decimal(plan_agg["pq"])
                    planned_val = _safe_decimal(plan_agg["pv"])

                    already_allotted = AllotmentItems.objects.filter(
                        item_id=item_id
                    ).aggregate(
                        aq=_Coalesce(
                            _Sum("qty"), _Val(Decimal("0")), output_field=_DF()
                        ),
                        av=_Coalesce(
                            _Sum("cif_fc"), _Val(Decimal("0")), output_field=_DF()
                        ),
                    )
                    already_qty = _safe_decimal(already_allotted["aq"])
                    already_val = _safe_decimal(already_allotted["av"])

                    if (already_qty + qty) > planned_qty or (
                        already_val + cif_fc
                    ) > planned_val:
                        errors.append(
                            {
                                "item_id": item_id,
                                "plan_exceeded": True,
                                "error": "Allocation exceeds the utilization plan for this item.",
                                "planned_quantity": str(planned_qty),
                                "planned_cif_fc": str(planned_val),
                                "already_allotted_quantity": str(already_qty),
                                "already_allotted_cif_fc": str(already_val),
                                "requested_quantity": str(qty),
                                "requested_cif_fc": str(cif_fc),
                                "remaining_planned_quantity": str(planned_qty - already_qty),
                                "remaining_planned_cif_fc": str(planned_val - already_val),
                            }
                        )
                        continue

                # --- Create or amend AllotmentItems ---
                existing = AllotmentItems.objects.filter(
                    allotment=allotment,
                    item=license_item,
                ).first()

                if existing:
                    existing.qty += qty
                    existing.cif_fc += cif_fc
                    existing.cif_inr += cif_inr
                    existing.save()
                    allotment_item = existing
                else:
                    allotment_item = AllotmentItems.objects.create(
                        allotment=allotment,
                        item=license_item,
                        qty=qty,
                        cif_fc=cif_fc,
                        cif_inr=cif_inr,
                        is_boe=False,
                    )

                affected_license_ids.add(license_item.license_id)

                created_items.append(
                    {
                        "id": allotment_item.pk,
                        "item_id": item_id,
                        "license_number": license_item.license.license_number,
                        "qty": str(qty),
                        "cif_fc": str(cif_fc),
                        "cif_inr": str(cif_inr),
                    }
                )

            except LicenseImportItemsModel.DoesNotExist:
                errors.append(
                    {"item_id": item_id, "error": "License import item not found"}
                )
            except Exception:
                logger.exception(
                    "allocate_items: unexpected error for item_id=%s allotment=%s",
                    item_id,
                    pk,
                )
                errors.append(
                    {
                        "item_id": item_id,
                        "error": "Allocation failed; check server logs",
                    }
                )

        # Dispatch balance recompute after transaction commits
        if affected_license_ids:
            def _dispatch_balance():
                try:
                    from apps.license.tasks import recompute_license_balance_task
                    for lid in affected_license_ids:
                        recompute_license_balance_task.delay(lid)
                except ImportError:
                    logger.warning(
                        "recompute_license_balance_task not available — skipping dispatch"
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to dispatch balance recompute for licenses=%s: %s",
                        affected_license_ids,
                        exc,
                        exc_info=True,
                    )

            transaction.on_commit(_dispatch_balance)

        allotment.refresh_from_db()
        allotment_data = AllotmentSerializer(allotment).data

        http_status = (
            status.HTTP_201_CREATED if created_items else status.HTTP_400_BAD_REQUEST
        )
        return Response(
            {
                "success": len(created_items),
                "created_items": created_items,
                "errors": errors,
                "allotment": allotment_data,
            },
            status=http_status,
        )

    # ------------------------------------------------------------------
    # delete_allotment_item
    # ------------------------------------------------------------------

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"delete-item/(?P<item_id>[^/.]+)",
    )
    def delete_allotment_item(self, request, pk=None, item_id=None):
        """
        Deallot one AllotmentItems row.

        Signals / balance_service will restore available_quantity for the item;
        recompute_license_balance_task is dispatched after the delete commits.
        """
        allotment_item = get_object_or_404(
            AllotmentItems, pk=item_id, allotment_id=pk
        )

        license_id = None
        try:
            license_id = allotment_item.item.license_id
        except Exception:
            pass

        qty = allotment_item.qty
        license_number = "Unknown"
        try:
            license_number = allotment_item.item.license.license_number
        except Exception:
            pass

        allotment_item.delete()

        if license_id:
            def _dispatch():
                try:
                    from apps.license.tasks import recompute_license_balance_task
                    recompute_license_balance_task.delay(license_id)
                except ImportError:
                    logger.warning(
                        "recompute_license_balance_task not available — skipping dispatch"
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to dispatch balance recompute after item delete: %s",
                        exc,
                        exc_info=True,
                    )

            transaction.on_commit(_dispatch)

        return Response(
            {
                "message": (
                    f"Successfully removed allocation of {qty} from {license_number}"
                ),
                "deleted_qty": str(qty),
            },
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # generate_pdf
    # ------------------------------------------------------------------

    @action(detail=True, methods=["get"], url_path="generate-pdf")
    def generate_pdf(self, request, pk=None):
        """
        Async PDF generation — dispatch Celery task and return task_id.

        Degrades gracefully if apps.allotment.tasks is not yet available.
        """
        get_object_or_404(AllotmentModel, pk=pk)
        try:
            from apps.allotment.tasks import generate_allotment_pdf_task
            task = generate_allotment_pdf_task.delay(int(pk))
            return Response(
                {"task_id": task.id, "message": "PDF generation queued"},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception:
            return Response(
                {"task_id": None, "message": "PDF task not available"},
                status=status.HTTP_202_ACCEPTED,
            )

    # ------------------------------------------------------------------
    # generate_transfer_letter
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="generate-transfer-letter")
    def generate_transfer_letter(self, request, pk=None):
        """
        Generate transfer letter for this allotment.

        Delegates to apps.core.utils.transfer_letter.generate_transfer_letter_generic
        if that utility has been ported from the legacy app. Returns 501 if the
        utility is not yet available in this backend.

        Request body (same as legacy):
          {
            "company_name": "...",
            "address_line1": "...",
            "address_line2": "...",
            "template_id": <int>,
            "cif_edits": { "<allotment_item_id>": <cif_value>, ... }
          }
        """
        allotment = get_object_or_404(
            AllotmentModel.objects.select_related("company"), pk=pk
        )
        try:
            from apps.core.utils.transfer_letter import generate_transfer_letter_generic
            return generate_transfer_letter_generic(
                allotment, request, instance_type="allotment"
            )
        except ImportError:
            return Response(
                {
                    "error": (
                        "Transfer letter generation is not yet available in this backend. "
                        "Use the legacy system for this operation."
                    )
                },
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        except Exception as exc:
            logger.exception(
                "generate_transfer_letter failed for allotment %s: %s", pk, exc
            )
            return Response(
                {"error": "Transfer letter generation failed; check server logs."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
