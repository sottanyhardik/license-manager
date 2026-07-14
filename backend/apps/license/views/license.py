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

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from shared.pagination import StandardPagination
from shared.serializers import EnvelopeMixin

from apps.license.filters import IncentiveLicenseFilter, LicenseFilter
from apps.license.models import (
    IncentiveLicense,
    LicenseDetailsModel,
    LicenseDocumentModel,
    LicenseImportItemsModel,
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
    search_fields = ["license_number"]
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
