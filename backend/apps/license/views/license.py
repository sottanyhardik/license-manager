# license/views/license.py
"""
ViewSets for the License module.

Design rules:
  - No ORM in views — all DB access delegated to services.
  - Permission enforced via LicensePermission / IncentiveLicensePermission.
  - All list responses are paginated (StandardPagination from shared.pagination).
  - Envelope pattern: {"success": true/false, "data": ..., "message": ...}
    List responses use the StandardPagination envelope automatically.
    Detail / action responses return explicit Response(EnvelopeMixin.wrap(...)).
"""
import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.core.models import (
    CompanyModel,
    HSCodeModel,
    NotificationNumber,
    PortModel,
    SchemeCode,
)
from apps.license.filters import IncentiveLicenseFilter, LicenseFilter
from apps.license.models import (
    IncentiveLicense,
    LicenseDetailsModel,
    LicenseDocumentModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
    LicenseTransferModel,
)
from apps.license.permissions import IncentiveLicensePermission, LicensePermission
from apps.license.serializers import (
    ImportItemSerializer,
    IncentiveLicenseSerializer,
    LicenseCreateSerializer,
    LicenseDetailSerializer,
    LicenseDocumentSerializer,
    LicenseListSerializer,
)
from apps.license.services import license_service
from shared.pagination import StandardPagination
from shared.serializers import EnvelopeMixin

logger = logging.getLogger(__name__)


class LicenseViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for LicenseDetailsModel.

    GET    /api/v1/licenses/              → list (paginated, filterable)
    POST   /api/v1/licenses/              → create
    GET    /api/v1/licenses/{id}/         → retrieve
    PUT    /api/v1/licenses/{id}/         → full update
    PATCH  /api/v1/licenses/{id}/         → partial update
    DELETE /api/v1/licenses/{id}/         → destroy

    Extra actions:
      GET   /api/v1/licenses/{id}/balance/          → balance data
      POST  /api/v1/licenses/{id}/recompute_balance/ → dispatch balance task
      GET   /api/v1/licenses/search/?q=              → free-text search
      POST  /api/v1/licenses/{id}/generate_pdf/      → dispatch PDF task
    """

    permission_classes = [LicensePermission]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = LicenseFilter
    search_fields = ["license_number"]
    ordering_fields = ["license_number", "license_date", "license_expiry_date"]
    ordering = ["license_expiry_date"]

    def get_queryset(self):
        return (
            LicenseDetailsModel.objects.select_related(
                "exporter",
                "scheme_code",
                "notification_number",
                "port",
                "purchase_status",
                "balance",
                "flags",
                "notes",
                "ownership",
                "ownership__current_owner",
            )
            .order_by("license_expiry_date", "license_date")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return LicenseDetailSerializer
        if self.action in ("create", "update", "partial_update"):
            return LicenseCreateSerializer
        return LicenseListSerializer

    # ------------------------------------------------------------------
    # Standard CRUD — delegates to service layer
    # ------------------------------------------------------------------

    def create(self, request, *args, **kwargs):
        serializer = LicenseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Extract FK PKs to pass as plain fields
        validated = serializer.validated_data
        data = {
            field: (value.pk if hasattr(value, "pk") else value)
            for field, value in validated.items()
        }

        license_obj = license_service.create_license(data, request.user)
        out = LicenseDetailSerializer(license_obj, context={"request": request})
        return Response(
            EnvelopeMixin.wrap(data=out.data, message="License created successfully."),
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = LicenseCreateSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        data = {
            field: (value.pk if hasattr(value, "pk") else value)
            for field, value in validated.items()
        }

        license_obj = license_service.update_license(instance.pk, data, request.user)
        out = LicenseDetailSerializer(license_obj, context={"request": request})
        return Response(EnvelopeMixin.wrap(data=out.data))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        license_service.delete_license(instance.pk, request.user)
        return Response(
            EnvelopeMixin.wrap(message="License deleted successfully."),
            status=status.HTTP_204_NO_CONTENT,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = LicenseDetailSerializer(instance, context={"request": request})
        return Response(EnvelopeMixin.wrap(data=serializer.data))

    # ------------------------------------------------------------------
    # Extra actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        """Return the current balance snapshot for a license."""
        instance = self.get_object()
        try:
            bal = instance.balance
            data = {
                "license_id": instance.pk,
                "license_number": instance.license_number,
                "balance_cif": bal.balance_cif,
                "ledger_date": bal.ledger_date,
            }
        except LicenseDetailsModel.balance.RelatedObjectDoesNotExist:
            data = {
                "license_id": instance.pk,
                "license_number": instance.license_number,
                "balance_cif": None,
                "ledger_date": None,
            }
        return Response(EnvelopeMixin.wrap(data=data))

    @action(detail=True, methods=["post"], url_path="recompute_balance")
    def recompute_balance(self, request, pk=None):
        """Dispatch an async balance recomputation task."""
        from apps.license.tasks import recompute_license_balance_task

        result = recompute_license_balance_task.delay(int(pk))
        return Response(
            EnvelopeMixin.wrap(
                data={"task_id": result.id},
                message="Balance recomputation queued.",
            ),
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["get"])
    def search(self, request):
        """Free-text search on license_number via ?q= param."""
        q = request.query_params.get("q", "").strip()
        qs = self.get_queryset()
        if q:
            qs = qs.filter(license_number__icontains=q)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = LicenseListSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = LicenseListSerializer(qs, many=True, context={"request": request})
        return Response(EnvelopeMixin.wrap(data=serializer.data))

    @action(detail=True, methods=["get"], url_path="items/grouped")
    def items_grouped(self, request, pk=None):
        """GET /api/v1/licenses/{id}/items/grouped/ — grouped by ItemNameModel."""
        from apps.license.services.balance_service import group_import_items_by_name
        instance = self.get_object()
        data = group_import_items_by_name(instance.pk)
        return Response(EnvelopeMixin.wrap(data=data))

    @action(detail=True, methods=["post"], url_path="generate_pdf")
    def generate_pdf(self, request, pk=None):
        """Dispatch an async PDF generation task."""
        from apps.license.tasks import generate_license_pdf_task

        report_type = request.data.get("report_type", "license_detail")
        result = generate_license_pdf_task.delay(int(pk), report_type, request.user.id)
        return Response(
            EnvelopeMixin.wrap(
                data={"task_id": result.id},
                message="PDF generation queued.",
            ),
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        """
        GET /api/v1/licenses/{id}/history/
        Returns a chronological timeline of events for this license.
        Sources: ActivityLog, LicenseTransferModel, creation/modification timestamps.
        """
        from apps.core.models import ActivityLog

        instance = self.get_object()
        events = []

        # 1. License creation event
        if instance.created_on:
            events.append({
                "event_type": "created",
                "description": f"License {instance.license_number} created",
                "timestamp": (
                    instance.created_on.isoformat()
                    if hasattr(instance.created_on, "isoformat")
                    else str(instance.created_on)
                ),
                "user": str(instance.created_by) if instance.created_by else None,
            })

        # 2. ActivityLog entries for this license
        try:
            logs = ActivityLog.objects.filter(
                module="LICENSE",
                resource_id=str(pk),
            ).order_by("-timestamp").values(
                "action", "description", "timestamp", "username"
            )[:50]
            for log in logs:
                events.append({
                    "event_type": log["action"].lower(),
                    "description": log["description"] or f"{log['action']} on license",
                    "timestamp": log["timestamp"].isoformat() if log["timestamp"] else None,
                    "user": log["username"],
                })
        except Exception:
            pass

        # 3. Transfer history
        try:
            transfers = LicenseTransferModel.objects.filter(
                license_id=pk
            ).select_related("from_company", "to_company").order_by("-transfer_date")
            for tr in transfers:
                from_name = tr.from_company.name if tr.from_company else "Unknown"
                to_name = tr.to_company.name if tr.to_company else "Unknown"
                events.append({
                    "event_type": "transfer",
                    "description": (
                        f"License transferred from {from_name} to {to_name}"
                        f" — Status: {tr.transfer_status or 'N/A'}"
                    ),
                    "timestamp": tr.transfer_initiation_date.isoformat() if tr.transfer_initiation_date else (
                        str(tr.transfer_date) if tr.transfer_date else None
                    ),
                    "user": tr.user_id_transfer_initiation or (
                        str(tr.transfer_initiation_user)
                        if tr.transfer_initiation_user else None
                    ),
                })
        except Exception:
            pass

        # Sort all events by timestamp (newest first); None timestamps sort last
        events.sort(key=lambda e: e.get("timestamp") or "", reverse=True)

        return Response(EnvelopeMixin.wrap(data=events))

    # ------------------------------------------------------------------
    # DFIA PDF parse — prefill the License create form from an upload
    # ------------------------------------------------------------------

    @action(
        detail=False,
        methods=["post"],
        url_path="parse-pdf",
        parser_classes=[MultiPartParser, FormParser],
    )
    def parse_pdf(self, request):  # noqa: C901
        """
        POST /api/v1/licenses/parse-pdf/
        Multipart field: ``file`` — the DFIA licence PDF.
        Optional field:  ``create_company`` (default "true").

        Extracts licence fields and import-item rows, matches/creates
        Company, Port, NotificationNumber, and SchemeCode, and returns a
        ``prefill`` dict ready for the licence create/update form.
        """
        from decimal import Decimal, InvalidOperation

        from apps.license.parsers.dfia_pdf import parse_dfia_pdf

        # DFIA licences default to scheme code "26" (≈99% of existing rows).
        DFIA_DEFAULT_SCHEME_CODE = "26"

        def _decimal(value, default=None):
            if value in (None, ""):
                return default
            try:
                return Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                return default

        def _match_or_create_company(parsed, create_if_missing):
            iec = (parsed.get("iec") or "").strip()
            name = (parsed.get("company_name") or "").strip()
            company = None
            created = False

            if iec:
                company = CompanyModel.objects.filter(iec=iec).first()
            if not company and name:
                company = CompanyModel.objects.filter(name__iexact=name).first()

            if not company and create_if_missing and iec and name:
                company = CompanyModel.objects.create(
                    iec=iec,
                    name=name,
                    address_line_1=(parsed.get("company_address") or "").strip(),
                )
                created = True

            return company, created

        def _match_port(port_code):
            if not port_code:
                return None
            return PortModel.objects.filter(code__iexact=port_code.strip()).first()

        def _match_hs_code(hsn):
            if not hsn:
                return None
            return HSCodeModel.objects.filter(hs_code=hsn.strip()).first()

        def _resolve_notification_number(code):
            if not code:
                return None
            code = code.strip()
            if not code:
                return None
            obj, _ = NotificationNumber.objects.get_or_create(
                code=code, defaults={"label": code}
            )
            return obj

        def _resolve_scheme_code(code):
            if not code:
                return None
            return SchemeCode.objects.filter(code=code.strip()).first()

        def _annotate_items(items):
            out = []
            for item in items:
                hs = _match_hs_code(item.get("hsn"))
                out.append({**item, "matched_hs_code_id": hs.id if hs else None})
            return out

        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"detail": "No file uploaded. Send the PDF as multipart field 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parsed = parse_dfia_pdf(upload)
        except Exception as exc:
            return Response(
                {"detail": f"Failed to parse PDF: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not parsed.get("license_number"):
            return Response(
                {
                    "detail": (
                        "Could not detect a licence number — this may not be a "
                        "DGFT DFIA licence PDF, or the layout is unsupported."
                    ),
                    "parsed": parsed,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        existing = (
            LicenseDetailsModel.objects.filter(
                license_number=parsed["license_number"]
            )
            .only("id", "license_number")
            .first()
        )

        create_company = str(request.data.get("create_company", "true")).lower() != "false"
        company, company_created = _match_or_create_company(parsed, create_company)
        port = _match_port(parsed.get("port_code"))
        notification = _resolve_notification_number(parsed.get("notification_number"))
        scheme = _resolve_scheme_code(DFIA_DEFAULT_SCHEME_CODE)

        items = _annotate_items(parsed.get("items") or [])

        # Auto-calculate registration_number: strip leading zero from license_number.
        lic_no = parsed.get("license_number") or ""
        reg_number = (lic_no[1:] if lic_no.startswith("0") else lic_no) or None

        prefill = {
            "license_number": parsed.get("license_number"),
            "license_date": parsed.get("license_date"),
            "license_expiry_date": parsed.get("license_expiry_date"),
            "file_number": parsed.get("file_number"),
            "registration_number": reg_number,
            "registration_date": parsed.get("license_date"),
            # SlugRelatedField expects the code string, not the PK.
            "notification_number": notification.code if notification else None,
            "scheme_code": scheme.code if scheme else None,
            "exporter": company.id if company else None,
            "port": port.id if port else None,
            "condition_sheet": parsed.get("condition_sheet"),
        }

        return Response({
            "parsed": parsed,
            "prefill": prefill,
            "item_conditions": parsed.get("item_conditions") or [],
            "matched_company_id": company.id if company else None,
            "matched_company_name": company.name if company else parsed.get("company_name"),
            "company_created": company_created,
            "matched_port_id": port.id if port else None,
            "matched_port_code": parsed.get("port_code"),
            "items": items,
            "existing_license_id": existing.id if existing else None,
        })

    # ------------------------------------------------------------------
    # Ledger PDF download
    # ------------------------------------------------------------------

    @action(detail=True, methods=["get"], url_path="download-ledger")
    def download_ledger(self, request, pk=None):
        """
        GET /api/v1/licenses/{id}/download-ledger/
        Returns a PDF of the license ledger (items, allotments, BOE debits).
        """
        from apps.accounts.permissions import LicenseLedgerViewPermission
        from apps.license.services.ledger_pdf_service import (
            PDFGenerationError,
            generate_license_ledger_pdf,
        )

        # Enforce LicenseLedgerViewPermission in addition to the viewset default
        perm = LicenseLedgerViewPermission()
        if not perm.has_permission(request, self):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()

        license_obj = get_object_or_404(
            LicenseDetailsModel.objects.prefetch_related(
                "import_license__items",
                "import_license__hs_code",
                "import_license__allotment_details__allotment__company",
                "import_license__item_details__bill_of_entry__company",
            ).select_related("exporter", "port", "balance", "notification_number"),
            pk=pk,
        )

        try:
            pdf_content = generate_license_ledger_pdf(license_obj)
            filename = f"License_Ledger_{license_obj.license_number}.pdf"
            response = HttpResponse(pdf_content, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{filename}"'
            return response
        except PDFGenerationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            logger.exception("Unexpected error generating ledger PDF for pk=%s: %s", pk, exc)
            return Response(
                {"detail": "Failed to generate PDF."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ImportItemViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for LicenseImportItemsModel nested under /licenses/{license_pk}/items/.

    After create / update the balance recompute task is dispatched asynchronously.
    """

    permission_classes = [LicensePermission]
    serializer_class = ImportItemSerializer
    pagination_class = StandardPagination

    def _get_license_pk(self) -> int:
        return int(self.kwargs["license_pk"])

    def get_queryset(self):
        return LicenseImportItemsModel.objects.filter(
            license_id=self._get_license_pk()
        ).select_related("hs_code").order_by("serial_number")

    def create(self, request, *args, **kwargs):
        serializer = ImportItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        data = {
            field: (value.pk if hasattr(value, "pk") else value)
            for field, value in validated.items()
            if field != "license"  # license_id injected from URL
        }

        license_pk = self._get_license_pk()
        item = license_service.create_import_item(license_pk, data, request.user)

        # Async balance recompute
        from apps.license.tasks import recompute_license_balance_task
        recompute_license_balance_task.delay(license_pk)

        out = ImportItemSerializer(item, context={"request": request})
        return Response(
            EnvelopeMixin.wrap(data=out.data, message="Import item created."),
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = ImportItemSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        data = {
            field: (value.pk if hasattr(value, "pk") else value)
            for field, value in validated.items()
            if field != "license"
        }

        item = license_service.update_import_item(instance.pk, data, request.user)

        # Async balance recompute
        from apps.license.tasks import recompute_license_balance_task
        recompute_license_balance_task.delay(self._get_license_pk())

        out = ImportItemSerializer(item, context={"request": request})
        return Response(EnvelopeMixin.wrap(data=out.data))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        license_pk = self._get_license_pk()
        license_service.delete_import_item(instance.pk, request.user)

        # Async balance recompute after deletion
        from apps.license.tasks import recompute_license_balance_task
        recompute_license_balance_task.delay(license_pk)

        return Response(
            EnvelopeMixin.wrap(message="Import item deleted."),
            status=status.HTTP_204_NO_CONTENT,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ImportItemSerializer(instance, context={"request": request})
        return Response(EnvelopeMixin.wrap(data=serializer.data))


class LicenseDocumentViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for LicenseDocumentModel nested under /licenses/{license_pk}/documents/.
    """

    permission_classes = [LicensePermission]
    serializer_class = LicenseDocumentSerializer
    pagination_class = StandardPagination

    def _get_license_pk(self) -> int:
        return int(self.kwargs["license_pk"])

    def get_queryset(self):
        return LicenseDocumentModel.objects.filter(license_id=self._get_license_pk())

    def perform_create(self, serializer):
        serializer.save(license_id=self._get_license_pk())


class IncentiveLicenseViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for IncentiveLicense.

    GET/POST  /api/v1/incentive-licenses/
    GET/PUT/PATCH/DELETE  /api/v1/incentive-licenses/{id}/
    """

    permission_classes = [IncentiveLicensePermission]
    serializer_class = IncentiveLicenseSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = IncentiveLicenseFilter
    search_fields = ["license_number", "exporter__name"]
    ordering_fields = ["license_number", "license_date", "license_expiry_date"]
    ordering = ["license_expiry_date"]

    def get_queryset(self):
        return IncentiveLicense.objects.select_related("exporter", "port_code").order_by(
            "license_expiry_date"
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, modified_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(modified_by=self.request.user)


# ---------------------------------------------------------------------------
# Export items viewset (read-only — credit side of a license)
# ---------------------------------------------------------------------------


class ExportItemSerializer(drf_serializers.ModelSerializer):
    """Read-only serializer for LicenseExportItemModel."""

    norm_class_label = drf_serializers.CharField(
        source="norm_class.norm_class", read_only=True, default=None
    )
    item_label = drf_serializers.CharField(
        source="item.name", read_only=True, default=None
    )

    class Meta:
        model = LicenseExportItemModel
        fields = [
            "id", "license", "description", "item", "item_label",
            "norm_class", "norm_class_label", "duty_type",
            "net_quantity", "old_quantity", "unit",
            "fob_fc", "fob_inr", "fob_exchange_rate", "currency",
            "value_addition", "cif_fc", "cif_inr",
        ]
        read_only_fields = ["id", "license", "norm_class_label", "item_label"]


class ExportItemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for LicenseExportItemModel.
    Nested under /api/v1/licenses/{license_pk}/export-items/
    Shows the credit side of a license (what products are being exported).
    """

    permission_classes = [LicensePermission]
    serializer_class = ExportItemSerializer
    pagination_class = None  # always return the full list for a single license

    def get_queryset(self):
        license_pk = self.kwargs.get("license_pk")
        return (
            LicenseExportItemModel.objects
            .select_related("item", "norm_class")
            .filter(license_id=license_pk)
            .order_by("id")
        )


# ---------------------------------------------------------------------------
# LicenseItemPlan viewset
# ---------------------------------------------------------------------------


class LicenseItemPlanSerializer(drf_serializers.ModelSerializer):
    """Serializer for LicenseItemPlan — planning allocations per import item."""

    import_item_description = drf_serializers.CharField(
        source="import_item.description", read_only=True, default=None
    )
    license_number = drf_serializers.CharField(
        source="license.license_number", read_only=True, default=None
    )

    class Meta:
        model = LicenseItemPlan
        fields = [
            "id",
            "license",
            "license_number",
            "import_item",
            "import_item_description",
            "item_name",
            "planned_quantity",
            "unit_price",
            "planned_cif_fc",
            "planned_cif_inr",
            "note",
        ]
        read_only_fields = ["id", "license_number", "import_item_description"]


class LicenseItemPlanViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for LicenseItemPlan.

    Nested under a license:
      GET    /api/v1/licenses/{license_pk}/item-plans/        → list plans for license
      POST   /api/v1/licenses/{license_pk}/item-plans/        → create plan
      GET    /api/v1/licenses/{license_pk}/item-plans/{pk}/   → retrieve plan
      PATCH  /api/v1/licenses/{license_pk}/item-plans/{pk}/   → update plan
      DELETE /api/v1/licenses/{license_pk}/item-plans/{pk}/   → delete plan

    Plans are optional — an import item without a plan has no allotment restriction.
    Creating a plan for an import item that already has one is blocked by DB unique
    constraint (one plan per item).
    """

    permission_classes = [LicensePermission]
    serializer_class = LicenseItemPlanSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        license_pk = self.kwargs.get("license_pk")
        qs = LicenseItemPlan.objects.select_related(
            "license", "import_item", "item_name"
        )
        if license_pk:
            qs = qs.filter(license_id=license_pk)
        return qs

    def perform_create(self, serializer):
        license_pk = self.kwargs.get("license_pk")
        # If license_pk is in the URL, force it on the created object
        kwargs = {"created_by": self.request.user, "modified_by": self.request.user}
        if license_pk and not serializer.validated_data.get("license"):
            try:
                license_obj = LicenseDetailsModel.objects.get(pk=license_pk)
                kwargs["license"] = license_obj
            except LicenseDetailsModel.DoesNotExist:
                pass
        serializer.save(**kwargs)

    def perform_update(self, serializer):
        serializer.save(modified_by=self.request.user)
