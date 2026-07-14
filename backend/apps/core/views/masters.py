# core/views/masters.py
"""
ViewSet classes for all core master models.

Permission model:
- All authenticated users can read reference data (ReadOnlyModelViewSet).
- Editable masters (CompanyModel, ExchangeRateModel, etc.) use ModelViewSet
  with staff/manager write gating via MasterWritePermission.
- IsAuthenticated is the minimum bar for all endpoints.

Pagination:
- StandardPagination (25/page) from shared.pagination.
- ?all=true bypasses pagination — for dropdown data only; use with care on
  large tables (ports, HS codes). Views that could return >5 000 rows warn
  in their docstring.

Search / filter / ordering:
- DjangoFilterBackend handles structured filters (filterset_class).
- SearchFilter handles free-text ?search= against search_fields.
- OrderingFilter on all viewsets.
"""
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.response import Response
from shared.pagination import StandardPagination
from shared.permissions import IsAdminUser as ActiveAdminUser

from apps.core.filters import (
    ActivityLogFilter,
    CompanyFilter,
    ExchangeRateFilter,
    HSCodeFilter,
    ItemGroupFilter,
    ItemNameFilter,
    PortFilter,
    PurchaseStatusFilter,
    SchemeCodeFilter,
    SionNormClassFilter,
    TransferLetterFilter,
    UnitPriceFilter,
)
from apps.core.models import (
    ActivityLog,
    CeleryTaskTracker,
    CompanyModel,
    ExchangeRateModel,
    HeadSIONNormsModel,
    HSCodeModel,
    InvoiceEntity,
    ItemGroupModel,
    ItemHeadModel,
    ItemNameModel,
    MasterChange,
    NotificationNumber,
    PortModel,
    ProductDescriptionModel,
    PurchaseStatus,
    SchemeCode,
    SIONExportModel,
    SIONImportModel,
    SionNormClassModel,
    SionNormCondition,
    SionNormNote,
    TransferLetterModel,
    UnitPriceModel,
)
from apps.core.serializers import (
    ActivityLogSerializer,
    CeleryTaskTrackerSerializer,
    CompanySerializer,
    ExchangeRateSerializer,
    HeadSIONNormsSerializer,
    HSCodeSerializer,
    InvoiceEntitySerializer,
    ItemGroupSerializer,
    ItemHeadSerializer,
    ItemNameSerializer,
    MasterChangeSerializer,
    NotificationNumberSerializer,
    PortSerializer,
    ProductDescriptionSerializer,
    PurchaseStatusSerializer,
    SchemeCodeSerializer,
    SIONExportSerializer,
    SIONImportSerializer,
    SionNormClassSerializer,
    SionNormConditionSerializer,
    SionNormNoteSerializer,
    TransferLetterSerializer,
    UnitPriceSerializer,
)

# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

class MasterWritePermission(permissions.BasePermission):
    """
    Allow reads to any authenticated user.
    Restrict writes (POST/PATCH/PUT/DELETE) to staff or users with a
    manager role (LICENSE_MANAGER, TRADE_MANAGER, etc.).
    Superusers always pass.
    """

    _WRITE_ROLES = [
        "LICENSE_MANAGER",
        "TRADE_MANAGER",
        "ALLOTMENT_MANAGER",
        "BOE_MANAGER",
        "USER_MANAGER",
    ]

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated or not request.user.is_active:
            return False
        if request.user.is_superuser:
            return True
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write gate: staff or any manager role
        if request.user.is_staff:
            return True
        return request.user.has_any_role(self._WRITE_ROLES)


# ---------------------------------------------------------------------------
# Base ViewSet mixin
# ---------------------------------------------------------------------------

class MasterViewSetMixin:
    """
    Common configuration for all master viewsets:
    - StandardPagination with ?all=true bypass for dropdown use-cases.
    - DjangoFilterBackend + SearchFilter + OrderingFilter.
    - IsAuthenticated minimum permission.
    """

    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = "__all__"
    permission_classes = [permissions.IsAuthenticated]

    def get_paginated_response_or_all(self, queryset, serializer_class, request):
        """
        Helper: return an unpaginated list when ?all=true is present,
        otherwise return the standard paginated response.
        """
        if request.query_params.get("all", "").lower() == "true":
            serializer = serializer_class(queryset, many=True, context={"request": request})
            return Response(serializer.data)
        # Delegate to normal DRF pagination path
        return None  # signals caller to fall through to standard list()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        # ?all=true — bypass pagination (for dropdown lists)
        if request.query_params.get("all", "").lower() == "true":
            ALL_LIMIT = getattr(settings, "MASTER_ALL_LIMIT", 2000)
            count = queryset.count()
            if count > ALL_LIMIT:
                return Response(
                    {
                        "success": False,
                        "data": None,
                        "errors": [],
                        "message": f"Too many rows ({count}). Use filters or pagination.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer = self.get_serializer(queryset, many=True)
            return Response({"success": True, "data": serializer.data, "errors": [], "message": None})
        return super().list(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Priority masters — editable (ModelViewSet)
# ---------------------------------------------------------------------------

class CompanyViewSet(MasterViewSetMixin, viewsets.ModelViewSet):
    """
    Company master CRUD.

    GET  /api/v1/masters/companies/          — paginated list
    GET  /api/v1/masters/companies/?all=true — unpaginated list for dropdowns
    GET  /api/v1/masters/companies/:id/      — detail
    POST /PATCH/DELETE                        — staff / manager only

    Filters: name (icontains), iec (icontains)
    Search:  name, iec, gst_number
    """

    queryset = CompanyModel.objects.select_related("created_by", "modified_by").all()
    serializer_class = CompanySerializer
    filterset_class = CompanyFilter
    search_fields = ["name", "iec", "gst_number", "pan"]
    ordering_fields = "__all__"
    permission_classes = [MasterWritePermission]


class ExchangeRateViewSet(MasterViewSetMixin, viewsets.ModelViewSet):
    """
    Exchange rate master CRUD.

    Filters: date, date_from, date_to
    Search:  date
    Write:   staff / manager only
    """

    queryset = ExchangeRateModel.objects.all()
    serializer_class = ExchangeRateSerializer
    filterset_class = ExchangeRateFilter
    search_fields = ["date"]
    ordering_fields = "__all__"
    permission_classes = [MasterWritePermission]


class ItemGroupViewSet(MasterViewSetMixin, viewsets.ModelViewSet):
    """
    Item group master CRUD.

    Search:  name
    Write:   staff / manager only
    """

    queryset = ItemGroupModel.objects.all()
    serializer_class = ItemGroupSerializer
    filterset_class = ItemGroupFilter
    search_fields = ["name"]
    ordering_fields = "__all__"
    permission_classes = [MasterWritePermission]


class ItemNameViewSet(MasterViewSetMixin, viewsets.ModelViewSet):
    """
    Item name master CRUD.

    Filters: name, is_active, group
    Search:  name, group__name
    Write:   staff / manager only
    """

    queryset = ItemNameModel.objects.select_related("group", "sion_norm_class").all()
    serializer_class = ItemNameSerializer
    filterset_class = ItemNameFilter
    search_fields = ["name", "group__name"]
    ordering_fields = "__all__"
    permission_classes = [MasterWritePermission]


class TransferLetterViewSet(MasterViewSetMixin, viewsets.ModelViewSet):
    """
    Transfer letter document store CRUD.

    Write:   staff / manager only
    """

    queryset = TransferLetterModel.objects.all()
    serializer_class = TransferLetterSerializer
    filterset_class = TransferLetterFilter
    search_fields = ["name"]
    ordering_fields = "__all__"
    permission_classes = [MasterWritePermission]


class UnitPriceViewSet(MasterViewSetMixin, viewsets.ModelViewSet):
    """
    Unit price master CRUD.

    Search:  name, label
    Write:   staff / manager only
    """

    queryset = UnitPriceModel.objects.all()
    serializer_class = UnitPriceSerializer
    filterset_class = UnitPriceFilter
    search_fields = ["name", "label"]
    ordering_fields = "__all__"
    permission_classes = [MasterWritePermission]


class SionNormClassViewSet(MasterViewSetMixin, viewsets.ModelViewSet):
    """
    SION norm class CRUD.

    Filters: norm_class (icontains), is_active
    Search:  norm_class, description, head_norm__name
    Write:   staff / manager only
    """

    queryset = SionNormClassModel.objects.select_related("head_norm").all()
    serializer_class = SionNormClassSerializer
    filterset_class = SionNormClassFilter
    search_fields = ["norm_class", "description", "head_norm__name"]
    ordering_fields = "__all__"
    permission_classes = [MasterWritePermission]


class ProductDescriptionViewSet(MasterViewSetMixin, viewsets.ModelViewSet):
    """
    Product description master CRUD.

    Search:  product_description, hs_code__hs_code
    Write:   staff / manager only
    """

    queryset = ProductDescriptionModel.objects.select_related("hs_code").all()
    serializer_class = ProductDescriptionSerializer
    search_fields = ["product_description", "hs_code__hs_code"]
    ordering_fields = "__all__"
    permission_classes = [MasterWritePermission]


class InvoiceEntityViewSet(MasterViewSetMixin, viewsets.ModelViewSet):
    """
    Invoice entity (billing company) CRUD.

    Search:  name, gst_number
    Write:   staff / manager only
    """

    queryset = InvoiceEntity.objects.all()
    serializer_class = InvoiceEntitySerializer
    search_fields = ["name", "gst_number"]
    ordering_fields = "__all__"
    permission_classes = [MasterWritePermission]


class PurchaseStatusViewSet(MasterViewSetMixin, viewsets.ModelViewSet):
    """
    Purchase status master CRUD.

    Filters: is_active
    Search:  code, label
    Write:   staff / manager only
    """

    queryset = PurchaseStatus.objects.all()
    serializer_class = PurchaseStatusSerializer
    filterset_class = PurchaseStatusFilter
    search_fields = ["code", "label"]
    ordering_fields = "__all__"
    permission_classes = [MasterWritePermission]


class SchemeCodeViewSet(MasterViewSetMixin, viewsets.ModelViewSet):
    """
    DGFT scheme code master CRUD.

    Filters: code
    Search:  code, label
    Write:   staff / manager only
    """

    queryset = SchemeCode.objects.all()
    serializer_class = SchemeCodeSerializer
    filterset_class = SchemeCodeFilter
    search_fields = ["code", "label"]
    ordering_fields = "__all__"
    permission_classes = [MasterWritePermission]


class NotificationNumberViewSet(MasterViewSetMixin, viewsets.ModelViewSet):
    """
    DGFT notification number master CRUD.

    Search:  code, label
    Write:   staff / manager only
    """

    queryset = NotificationNumber.objects.all()
    serializer_class = NotificationNumberSerializer
    search_fields = ["code", "label"]
    ordering_fields = "__all__"
    permission_classes = [MasterWritePermission]


# ---------------------------------------------------------------------------
# Reference data — read-only viewsets (ReadOnlyModelViewSet)
# ---------------------------------------------------------------------------

class PortViewSet(MasterViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Port master — read-only reference data.

    Filters: code (startswith), name (icontains)
    Search:  code, name

    NOTE: This table can have 500+ rows; use ?all=true only for small
    dropdown payloads; prefer search/filter for large lists.
    """

    queryset = PortModel.objects.select_related("created_by", "modified_by").all()
    serializer_class = PortSerializer
    filterset_class = PortFilter
    search_fields = ["code", "name"]
    ordering_fields = "__all__"


class HSCodeViewSet(MasterViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    HS Code master — read-only reference data.

    Filters: code (startswith), description (icontains)
    Search:  hs_code, product_description

    NOTE: This table can have thousands of rows. Always filter or search
    before requesting ?all=true.
    """

    queryset = HSCodeModel.objects.all()
    serializer_class = HSCodeSerializer
    filterset_class = HSCodeFilter
    search_fields = ["hs_code", "product_description"]
    ordering_fields = "__all__"


class HeadSIONNormsViewSet(MasterViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    SION norm headings — read-only reference data.

    Search:  name
    """

    queryset = HeadSIONNormsModel.objects.all()
    serializer_class = HeadSIONNormsSerializer
    search_fields = ["name"]
    ordering_fields = "__all__"


class SIONExportViewSet(MasterViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    SION export norms — read-only reference data.

    Search:  description, unit
    """

    queryset = SIONExportModel.objects.select_related("norm_class").all()
    serializer_class = SIONExportSerializer
    search_fields = ["description", "unit"]
    ordering_fields = "__all__"


class SIONImportViewSet(MasterViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    SION import norms — read-only reference data.

    Search:  description, unit, condition
    """

    queryset = SIONImportModel.objects.select_related("norm_class", "hsn_code").all()
    serializer_class = SIONImportSerializer
    search_fields = ["description", "unit", "condition"]
    ordering_fields = "__all__"


class SionNormNoteViewSet(MasterViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """SION norm notes — read-only."""

    queryset = SionNormNote.objects.select_related("sion_norm").all()
    serializer_class = SionNormNoteSerializer
    search_fields = ["note_text"]
    ordering_fields = "__all__"


class SionNormConditionViewSet(MasterViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """SION norm conditions — read-only."""

    queryset = SionNormCondition.objects.select_related("sion_norm").all()
    serializer_class = SionNormConditionSerializer
    search_fields = ["condition_text"]
    ordering_fields = "__all__"


# ---------------------------------------------------------------------------
# Deprecated viewsets (read-only for backward compat)
# ---------------------------------------------------------------------------

class ItemHeadViewSet(MasterViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    DEPRECATED: Use ItemGroupViewSet instead.
    Retained as read-only for backward compatibility.
    """

    queryset = ItemHeadModel.objects.select_related("restriction_norm").all()
    serializer_class = ItemHeadSerializer
    search_fields = ["name"]
    ordering_fields = "__all__"


# ---------------------------------------------------------------------------
# System / ops viewsets (read-only for operational monitoring)
# ---------------------------------------------------------------------------

class MasterChangeViewSet(MasterViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Master change feed — read-only. Staff-only access.

    Search:  model_label, natural_key, op
    """

    queryset = MasterChange.objects.all()
    serializer_class = MasterChangeSerializer
    search_fields = ["model_label", "natural_key", "op"]
    ordering_fields = "__all__"
    permission_classes = [ActiveAdminUser]


class CeleryTaskTrackerViewSet(MasterViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Celery task tracker — read-only. Staff-only access.

    Search:  task_name, status
    """

    queryset = CeleryTaskTracker.objects.all()
    serializer_class = CeleryTaskTrackerSerializer
    search_fields = ["task_name", "status"]
    ordering_fields = "__all__"
    permission_classes = [ActiveAdminUser]


class ActivityLogViewSet(MasterViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    User activity audit log — read-only. Staff-only access.

    Filters: action, module, username, timestamp_from, timestamp_to
    Search:  username, action, module, description
    """

    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer
    filterset_class = ActivityLogFilter
    search_fields = ["username", "action", "module", "description"]
    ordering_fields = "__all__"
    permission_classes = [ActiveAdminUser]
