# license/views/license.py
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import LicensePermission, LicenseReadOnlyPermission
from apps.core.constants import LICENCE_PURCHASE_CHOICES, LICENCE_PURCHASE_CHOICES_ACTIVE, SCHEME_CODE_CHOICES, \
    NOTIFICATION_NORM_CHOICES, UNIT_CHOICES, \
    CURRENCY_CHOICES
from apps.core.filters import CombinedFilterBackend, EnhancedSearchFilter, AdvancedOrderingFilter
from apps.core.filtersets import LicenseFilterSet
from apps.core.views.master_view import MasterViewSet
from apps.license.models import LicenseDetailsModel
from apps.license.serializers import LicenseDetailsSerializer, LicenseExportItemSerializer, LicenseImportItemSerializer, \
    LicenseDocumentSerializer
from apps.license.views.active_dfia_report import add_active_dfia_report_action
from apps.license.views.license_report import add_license_report_action


# Helper function to get default purchase status IDs from codes
def get_default_purchase_status_ids():
    """Convert default purchase status codes to IDs"""
    from apps.core.models import PurchaseStatus
    default_codes = ['GE', 'MI', 'CO']  # GE Purchase, GE Operating, Conversion
    ids = list(PurchaseStatus.objects.filter(code__in=default_codes).values_list('id', flat=True))
    return ','.join(map(str, ids)) if ids else ''

# Nested field definitions for LicenseDetails
license_nested_field_defs = {
    "export_license": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {"name": "description", "type": "text", "label": "Description"},
        {"name": "norm_class", "type": "fk", "label": "Norm Class", "fk_endpoint": "/masters/sion-classes/",
         "label_field": "norm_class", "display_field": "norm_class_label"},
        {"name": "start_serial_number", "type": "number", "label": "Start Serial Number", "default": 0},
        {"name": "net_quantity", "type": "number", "label": "Net Quantity", "default": 0},
        {"name": "fob_inr", "type": "number", "label": "FOB (INR)", "default": 0},
        {"name": "currency", "type": "select", "label": "Currency", "choices": list(CURRENCY_CHOICES),
         "default": "usd"},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)", "default": 0},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)", "default": 0},
    ],
    "import_license": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {"name": "serial_number", "type": "number", "label": "Serial Number", "default": 0},
        {"name": "hs_code", "type": "fk", "label": "HS Code", "fk_endpoint": "/masters/hs-codes/",
         "label_field": "hs_code", "display_field": "hs_code_label"},
        {"name": "description", "type": "textarea", "label": "Description"},
        {"name": "items", "type": "fk_multi", "label": "Items", "fk_endpoint": "/masters/item-names/",
         "label_field": "name", "show_in_list": False},
        {"name": "quantity", "type": "number", "label": "Quantity", "default": 0},
        {"name": "unit", "type": "select", "label": "Unit", "choices": list(UNIT_CHOICES), "default": "kg"},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)", "default": 0},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)", "default": 0},
        # `is_restricted` is derived from `condition_type` (set on save) —
        # hidden from the editable form, surfaced only via the Condition badge.
        {"name": "is_restricted", "type": "boolean", "label": "Is Restricted", "read_only": True, "show_in_list": False, "show_in_form": False},
        {"name": "condition_type", "type": "select", "label": "Condition", "choices": [
            {"value": "", "label": "—"},
            {"value": "AU", "label": "AU (Actual User)"},
            {"value": "2%", "label": "2% restriction"},
            {"value": "3%", "label": "3% restriction"},
            {"value": "5%", "label": "5% restriction"},
            {"value": "10%", "label": "10% restriction"},
        ], "default": "", "show_in_list": False},
    ],
    "license_documents": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {
            "name": "type",
            "type": "select",
            "label": "Document Type",
            "choices": [
                {"value": "LICENSE COPY", "label": "LICENSE COPY"},
                {"value": "TRANSFER LETTER", "label": "TRANSFER LETTER"},
                {"value": "OTHER", "label": "OTHER"}
            ]
        },
        {"name": "file", "type": "file", "label": "File"},
    ],
}

# Create base viewset
_LicenseDetailsViewSetBase = MasterViewSet.create_viewset(
    LicenseDetailsModel,
    LicenseDetailsSerializer,
    config={
        "search": ["license_number", "file_number", "exporter__name"],
        "filter": {
            "exporter": {"type": "fk", "fk_endpoint": "/masters/companies/", "label_field": "name"},
            "exclude_exporter": {"type": "exclude_fk", "fk_endpoint": "/masters/companies/", "label_field": "name",
                                 "filter_field": "exporter"},
            "port": {"type": "fk", "fk_endpoint": "/masters/ports/", "label_field": "name"},
            "exclude_port": {"type": "exclude_fk", "fk_endpoint": "/masters/ports/", "label_field": "name",
                             "filter_field": "port"},
            "export_license__norm_class": {"type": "fk", "fk_endpoint": "/masters/sion-classes/",
                                           "label_field": "norm_class"},
            "notification_number": {"type": "fk", "fk_endpoint": "/masters/notification-numbers/", "label_field": "code", "value_field": "code"},
            "scheme_code": {"type": "fk", "fk_endpoint": "/masters/scheme-codes/", "label_field": "code", "value_field": "code"},
            "purchase_status": {"type": "fk", "fk_endpoint": "/masters/purchase-statuses/", "label_field": "label", "filter_params": {"is_active": "true"}},
            "license_date": {"type": "date_range"},
            "license_expiry_date": {"type": "date_range"},
            "balance__balance_cif": {"type": "range"},
            "flags__is_expired": {"type": "exact"},
            "flags__is_null": {"type": "exact"},
            "is_planned": {"type": "exact"},
        },
        "default_filters": {
            "flags__is_expired": "False",
            "flags__is_null": "False",
        },
        "list_display": [
            "license_number",
            "license_date",
            "license_expiry_date",
            "exporter__name",
            "exporter__iec",
            "port__name",
            "purchase_status_label",
            "balance_cif",
            "latest_transfer",
            "get_norm_class",
            "ledger_date"
        ],
        "form_fields": [
            "scheme_code",
            "notification_number",
            "license_number",
            "license_date",
            "license_expiry_date",
            "port",
            "registration_number",
            "registration_date",
            "file_number",
            "exporter",
            "purchase_status",
            "condition_sheet",
        ],
        "ordering": ["-license_expiry_date", "license_number"],
        "nested_field_defs": license_nested_field_defs,
        "nested_list_display": {
            "export_license": ["norm_class_label", "fob_inr", "cif_fc", "cif_inr"],
            "import_license": ["serial_number", "hs_code_label", "description", "quantity", "unit", "cif_fc",
                               "cif_inr", "allotted_quantity", "allotted_value", "debited_quantity", "debited_value",
                               "available_quantity", "available_value"],
            "license_documents": ["type", "file"],
        },
        "field_meta": {
            "exporter": {
                "type": "fk",
                "fk_endpoint": "/masters/companies/",
                "label_field": "name"
            },
            "port": {
                "type": "fk",
                "fk_endpoint": "/masters/ports/",
                "label_field": "name"
            },
            "current_owner": {
                "type": "fk",
                "fk_endpoint": "/masters/companies/",
                "label_field": "name"
            },
            "purchase_status": {
                "type": "fk",
                "fk_endpoint": "/masters/purchase-statuses/",
                "label_field": "label",
                "filter_params": {"is_active": "true"}
            },
            "scheme_code": {
                "type": "fk",
                "fk_endpoint": "/masters/scheme-codes/",
                "label_field": "code",
                "value_field": "code",
            },
            "notification_number": {
                "type": "fk",
                "fk_endpoint": "/masters/notification-numbers/",
                "label_field": "code",
                "value_field": "code",
            },
        }
    }
)


# Extend the base viewset to add custom filter logic for is_expired and is_null
class LicenseDetailsViewSet(_LicenseDetailsViewSetBase):
    """
    Custom license viewset with special handling for is_expired and is_null filters.

    Filter Logic:
    - is_expired: True when license_expiry_date < today, False when license_expiry_date >= today
    - is_null: True when balance_cif < 200, False when balance_cif >= 200
    """
    permission_classes = [LicensePermission]
    lookup_value_regex = '[^/]+'  # Allow both numbers and strings

    def get_permissions(self):
        # bulk_balance_excel uses POST only because the licence-number list
        # goes in the request body; behaviour is read-only. Allow any role
        # that can read licences.
        if getattr(self, 'action', None) == 'bulk_balance_excel':
            return [LicenseReadOnlyPermission()]
        return super().get_permissions()

    # Apply advanced filter backends
    filterset_class = LicenseFilterSet
    filter_backends = [CombinedFilterBackend, EnhancedSearchFilter, AdvancedOrderingFilter]
    search_fields = ['license_number', 'file_number', 'exporter__name']
    ordering_fields = ['license_date', 'license_expiry_date', 'balance_cif', 'exporter__name', 'license_number']

    def list(self, request, *args, **kwargs):
        """Override list to add dynamic purchase_status default to metadata"""
        response = super().list(request, *args, **kwargs)

        # Add purchase_status default to metadata if present
        if isinstance(response.data, dict) and 'default_filters' in response.data:
            default_ps_ids = get_default_purchase_status_ids()
            if default_ps_ids:
                response.data['default_filters']['purchase_status'] = default_ps_ids

        return response

    def get_object(self):
        """
        Override to support lookup by either pk (ID) or license_number.
        """
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}

        # Try to get by primary key first (if it's a number)
        lookup_value = self.kwargs[lookup_url_kwarg]
        try:
            # If lookup value is numeric, try ID first
            if lookup_value.isdigit():
                filter_kwargs = {'pk': int(lookup_value)}
                obj = self.get_queryset().get(**filter_kwargs)
            else:
                # Otherwise lookup by license number
                filter_kwargs = {'license_number': lookup_value}
                obj = self.get_queryset().get(**filter_kwargs)
        except (ValueError, self.queryset.model.DoesNotExist):
            # If ID lookup fails, try license_number
            try:
                filter_kwargs = {'license_number': lookup_value}
                obj = self.get_queryset().get(**filter_kwargs)
            except self.queryset.model.DoesNotExist:
                from django.http import Http404
                raise Http404(f"License with identifier '{lookup_value}' not found")

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)
        return obj

    def update(self, request, *args, **kwargs):
        """Override to log incoming request data."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info("=" * 50)
        logger.info("ViewSet.update called")
        logger.info("request.data type: %s", type(request.data))
        logger.info("request.data keys: %s", list(request.data.keys()) if hasattr(request.data, 'keys') else 'N/A')

        # Log license_documents from request.data
        if 'license_documents' in request.data:
            docs = request.data.getlist('license_documents') if hasattr(request.data, 'getlist') else request.data.get(
                'license_documents')
            logger.info("license_documents in request.data: %s", docs)
        else:
            logger.info("license_documents NOT in request.data")

        # Log all keys that contain 'license_documents'
        if hasattr(request.data, 'keys'):
            doc_keys = [k for k in request.data.keys() if 'license_documents' in k]
            logger.info("Keys containing 'license_documents': %s", doc_keys)
            for key in doc_keys[:5]:  # Log first 5
                logger.info("  %s = %s", key, request.data.get(key))

        return super().update(request, *args, **kwargs)

    def get_queryset(self):
        """
        Override to add performance optimizations with select_related and prefetch_related.
        For detail view (retrieve/update/partial_update), don't apply default filters so expired licenses can be edited.
        """
        # For detail view actions, skip default filters by temporarily clearing them
        skip_default_filters = self.action in ['retrieve', 'update', 'partial_update', 'destroy', 'nested_items', 'item_usage', 'balance_pdf', 'balance_excel']

        if skip_default_filters:
            # Save original default filters
            original_default_filters = getattr(self, 'default_filters', {})
            # Temporarily clear default filters
            self.default_filters = {}

        qs = super().get_queryset()

        # Restore original default filters if they were cleared
        if skip_default_filters:
            self.default_filters = original_default_filters

        # Add select_related for ForeignKey fields to avoid N+1 queries.
        # current_owner now lives on LicenseOwnership sub-table; balance and flags
        # are also sub-tables we want pre-joined so the back-compat @property
        # accessors don't issue separate queries.
        qs = qs.select_related(
            'exporter', 'port', 'purchase_status',
            'balance', 'flags', 'ownership', 'ownership__current_owner', 'notes',
        )

        # Flag licenses that have a manual utilization plan (drives list colour) and
        # which document types they carry — annotated so the list serializer doesn't
        # fire an .exists() query per row (was 2 extra queries/row for has_tl/has_copy).
        from django.db.models import Exists, OuterRef
        from apps.license.models import LicenseItemPlan, LicenseDocumentModel
        qs = qs.annotate(
            _has_manual_plan=Exists(LicenseItemPlan.objects.filter(license=OuterRef('pk'))),
            _has_tl=Exists(LicenseDocumentModel.objects.filter(license=OuterRef('pk'), type='TRANSFER LETTER')),
            _has_copy=Exists(LicenseDocumentModel.objects.filter(license=OuterRef('pk'), type='LICENSE COPY')),
        )

        # Only prefetch deep nested items for detail view (single object).
        # For list view, those relations cause massive performance issues,
        # but license_documents is lightweight (0–3 rows per license) and
        # must be prefetched so the serializer can build the merge-link stub
        # without firing 2 extra queries per row (.exists() + .all()[:1]).
        if self.action == 'retrieve':
            # Prefetch nested relationships for detail view only
            qs = qs.prefetch_related(
                'export_license',
                'export_license__norm_class',
                'import_license',
                'import_license__hs_code',
                'import_license__items',
                'import_license__items__sion_norm_class',
                'import_license__allotment_details',
                'import_license__item_details',
                'license_documents',
            )
        else:
            # List view: prefetch only license_documents so the serializer can
            # read the prefetch cache (zero per-row queries) instead of calling
            # .exists() + .all()[:1] which fired 2 queries per row.
            qs = qs.prefetch_related('license_documents')

        return qs

    def apply_advanced_filters(self, qs, params, filter_config):
        """Override to add custom logic for is_expired and is_null with default values."""
        from datetime import date
        from django.db.models import Q

        # Get default filters
        default_filters = getattr(self, "default_filters", {})

        # Handle is_expired filter - apply default if not provided
        is_expired_value = params.get('is_expired')

        # Special case: if user explicitly selects "all", don't apply any filter
        if is_expired_value and is_expired_value.lower() == "all":
            is_expired_value = None
        elif is_expired_value is None or is_expired_value == "":
            # Apply default if no value provided
            is_expired_value = default_filters.get('is_expired')

        if is_expired_value is not None and is_expired_value != "":
            today = date.today()
            if is_expired_value in ("True", "true", "1", True):
                # Show expired licenses: expiry_date < today
                qs = qs.filter(license_expiry_date__lt=today)
            elif is_expired_value in ("False", "false", "0", False):
                # Show non-expired licenses: expiry_date >= today OR null
                qs = qs.filter(Q(license_expiry_date__gte=today) | Q(license_expiry_date__isnull=True))

        # Handle is_null filter - apply default if not provided
        is_null_value = params.get('is_null')

        # Special case: if user explicitly selects "all", don't apply any filter
        if is_null_value and is_null_value.lower() == "all":
            is_null_value = None
        elif is_null_value is None or is_null_value == "":
            # Apply default if no value provided
            is_null_value = default_filters.get('is_null')

        if is_null_value is not None and is_null_value != "":
            if is_null_value in ("True", "true", "1", True):
                # Show null licenses: balance_cif < 200
                qs = qs.filter(balance__balance_cif__lt=200)
            elif is_null_value in ("False", "false", "0", False):
                # Show non-null licenses: balance_cif >= 200
                qs = qs.filter(balance__balance_cif__gte=200)

        # Handle is_planned filter - based on whether the license has a manual
        # utilization plan (i.e. at least one LicenseItemPlan row). This mirrors
        # the `is_manually_planned` flag surfaced in the serializer/list UI.
        # The `_has_manual_plan` annotation is added later in get_queryset (after
        # this method runs), so we filter with an Exists subquery here instead.
        is_planned_value = params.get('is_planned')

        # Special case: if user explicitly selects "all", don't apply any filter
        if is_planned_value and is_planned_value.lower() == "all":
            is_planned_value = None

        if is_planned_value is not None and is_planned_value != "":
            from django.db.models import Exists, OuterRef
            from apps.license.models import LicenseItemPlan
            has_manual_plan = Exists(LicenseItemPlan.objects.filter(license=OuterRef('pk')))
            if is_planned_value in ("True", "true", "1", True):
                # Show planned licenses: has at least one item plan
                qs = qs.filter(has_manual_plan)
            elif is_planned_value in ("False", "false", "0", False):
                # Show licenses that are not planned: no item plans
                qs = qs.filter(~has_manual_plan)

        # Call parent method for remaining filters (exclude is_expired and is_null)
        # Create a new QueryDict-like object
        from django.http import QueryDict
        filtered_params = QueryDict(mutable=True)
        for key, value in params.items():
            if key not in ('is_expired', 'is_null', 'is_planned'):
                # Handle array format for purchase_status
                if key == 'purchase_status[]':
                    # Frontend sends purchase_status[] for multi-select
                    for val in params.getlist(key):
                        filtered_params.appendlist('purchase_status[]', val)
                else:
                    filtered_params[key] = value

        # Create a copy of filter_config without custom-handled fields
        filtered_config = {k: v for k, v in filter_config.items() if k not in ('is_expired', 'is_null', 'is_planned')}

        # Call parent method with filtered params and config
        qs = super().apply_advanced_filters(qs, filtered_params, filtered_config)

        return qs

    @action(detail=True, methods=['get'])
    def nested_items(self, request, pk=None):
        """
        Fetch nested items for a specific license on demand.
        This endpoint is called lazily when user expands a license row.
        """
        license_obj = self.get_object()

        return Response({
            'export_license': LicenseExportItemSerializer(license_obj.export_license.all(), many=True).data,
            'import_license': LicenseImportItemSerializer(license_obj.import_license.all(), many=True,
                                                          context={'request': request}).data,
            'license_documents': LicenseDocumentSerializer(license_obj.license_documents.all(), many=True).data
        })

    @action(detail=True, methods=['get'], url_path='item-usage')
    def item_usage(self, request, pk=None):
        """
        Get real-time usage details for a specific license item (export or import).
        Shows where the item is used in BOEs and Allotments.

        Query params:
        - item_id: ID of the export or import item
        - type: 'export' or 'import'
        """
        from apps.bill_of_entry.models import RowDetails
        from apps.allotment.models import AllotmentItems

        self.get_object()
        item_id = request.query_params.get('item_id')
        item_type = request.query_params.get('type')

        if not item_id or not item_type:
            return Response({'error': 'item_id and type parameters are required'}, status=400)

        boes = []
        allotments = []

        if item_type == 'import':
            # Find BOE usage through RowDetails (sr_number points to LicenseImportItemsModel)
            # Only show transaction_type = 'D' (Debited)
            row_details = RowDetails.objects.filter(
                sr_number_id=item_id,
                transaction_type='D'
            ).select_related(
                'bill_of_entry',
                'bill_of_entry__company',
                'bill_of_entry__port'
            ).values(
                'bill_of_entry__id',
                'bill_of_entry__bill_of_entry_number',
                'bill_of_entry__bill_of_entry_date',
                'bill_of_entry__port__name',
                'bill_of_entry__company__name',
                'qty',
                'cif_fc',
                'cif_inr'
            )

            for detail in row_details:
                boes.append({
                    'id': detail['bill_of_entry__id'],
                    'bill_of_entry_number': detail['bill_of_entry__bill_of_entry_number'],
                    'date': detail['bill_of_entry__bill_of_entry_date'],
                    'port': detail['bill_of_entry__port__name'],
                    'company': detail['bill_of_entry__company__name'],
                    'quantity': float(detail['qty']),
                    'cif_fc': float(detail['cif_fc']),
                    'cif_inr': float(detail['cif_inr'])
                })

            # Find Allotment usage through AllotmentItems
            # Only show allotments where bill_of_entry is NULL (not yet converted to BOE)
            allotment_items = AllotmentItems.objects.filter(
                item_id=item_id,
                allotment__bill_of_entry__isnull=True
            ).select_related(
                'allotment',
                'allotment__company'
            ).values(
                'allotment__id',
                'allotment__invoice',
                'allotment__company__name',
                'qty',
                'cif_fc',
                'cif_inr'
            )

            for item in allotment_items:
                allotments.append({
                    'id': item['allotment__id'],
                    'allotment_number': item['allotment__invoice'] or f"Allotment #{item['allotment__id']}",
                    'company': item['allotment__company__name'],
                    'quantity': float(item['qty']),
                    'cif_fc': float(item['cif_fc']),
                    'cif_inr': float(item['cif_inr'])
                })

        elif item_type == 'export':
            # For export items, check allotments (AllotmentItems might link to export items)
            # This depends on your data model structure
            pass

        return Response({
            'boes': boes,
            'allotments': allotments
        })

    @action(detail=True, methods=['get'], url_path='balance-pdf')
    def balance_pdf(self, request, pk=None):
        """Generate PDF report for license balance details with all BOEs and Allotments."""
        from apps.license.services.exporters.license_balance_pdf import build_balance_pdf_response
        license_obj = self.get_object()
        return build_balance_pdf_response(license_obj, request)

    @action(detail=False, methods=['post'], url_path='bulk-balance-excel')
    def bulk_balance_excel(self, request):
        """Generate a multi-sheet Excel with one sheet per license."""
        from apps.license.services.exporters.license_balance_excel import build_bulk_balance_excel
        return build_bulk_balance_excel(request)

    @action(detail=True, methods=['get'], url_path='balance-excel')
    def balance_excel(self, request, pk=None):
        """Generate Excel summary report (BOE & Allotments + Balance Quantity)."""
        from apps.license.services.exporters.license_balance_excel import build_balance_excel
        license_obj = self.get_object()
        return build_balance_excel(license_obj)

    @action(detail=True, methods=['get'], url_path='balance-excel-unused')
    def balance_excel_unused(self, request, pk=None):
        """Original full balance Excel — kept for reference, no longer exposed."""
        from apps.license.services.exporters.license_balance_excel import build_balance_excel_unused
        license_obj = self.get_object()
        return build_balance_excel_unused(license_obj)

    @action(detail=True, methods=['get'], url_path='merged-documents')
    def merged_documents(self, request, pk=None):
        """
        Merge all license documents (LICENSE COPY + TRANSFER LETTER) into one PDF.
        Converts images to PDF if needed.
        """
        from django.http import FileResponse, HttpResponse
        import io
        import os
        import logging

        logger = logging.getLogger(__name__)
        try:
            license_obj = LicenseDetailsModel.objects.get(pk=pk)
        except LicenseDetailsModel.DoesNotExist:
            from django.http import HttpResponse
            return HttpResponse("License not found", status=404)
        documents = license_obj.license_documents.all()

        if not documents.exists():
            return HttpResponse("No documents found for this license", status=404)

        # Check if required libraries are installed
        try:
            from pypdf import PdfWriter, PdfReader
            from PIL import Image
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.utils import ImageReader
        except ImportError as e:
            return HttpResponse(f"Missing required library: {str(e)}. Please install pypdf and Pillow.", status=500)

        try:
            writer = PdfWriter()

            # Sort documents: TRANSFER LETTER first, then LICENSE COPY, then OTHER
            type_order = {'TRANSFER LETTER': 0, 'LICENSE COPY': 1, 'OTHER': 2}
            sorted_documents = sorted(documents, key=lambda doc: type_order.get(doc.type, 3))

            for doc in sorted_documents:
                if not doc.file:
                    continue

                # Use Django storage API so this works for local, S3, or any backend
                storage = doc.file.storage
                file_name = doc.file.name

                if not storage.exists(file_name):
                    logger.warning(f"File not found in storage: {file_name}")
                    continue

                file_ext = os.path.splitext(file_name)[1].lower()

                if file_ext == '.pdf':
                    # Add PDF directly
                    with storage.open(file_name, 'rb') as f:
                        reader = PdfReader(f)
                        for page in reader.pages:
                            writer.add_page(page)
                    logger.info(f"Added PDF: {file_name}")
                elif file_ext in ['.doc', '.docx']:
                    # Convert DOCX/DOC to PDF
                    try:
                        from docx import Document
                        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                        from reportlab.lib.pagesizes import A4
                        from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
                        import tempfile

                        # Read DOCX content using storage API
                        with storage.open(file_name, 'rb') as docx_f:
                            doc_bytes = io.BytesIO(docx_f.read())
                        doc = Document(doc_bytes)

                        # Create temporary PDF file
                        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
                            tmp_pdf_path = tmp_pdf.name

                        # Create PDF
                        pdf = SimpleDocTemplate(tmp_pdf_path, pagesize=A4)
                        story = []
                        styles = getSampleStyleSheet()

                        # Add custom style
                        normal_style = ParagraphStyle(
                            'CustomNormal',
                            parent=styles['Normal'],
                            fontSize=10,
                            leading=14,
                            alignment=TA_LEFT
                        )

                        # Convert paragraphs to PDF
                        for paragraph in doc.paragraphs:
                            if paragraph.text.strip():
                                # Escape special characters for reportlab
                                text = paragraph.text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                p = Paragraph(text, normal_style)
                                story.append(p)
                                story.append(Spacer(1, 6))

                        # Build PDF
                        pdf.build(story)

                        # Add converted PDF pages to writer
                        with open(tmp_pdf_path, 'rb') as tmp_f:
                            tmp_reader = PdfReader(tmp_f)
                            for page in tmp_reader.pages:
                                writer.add_page(page)
                        logger.info(f"Converted and added DOCX/DOC: {file_name}")

                        # Clean up temp file
                        try:
                            os.remove(tmp_pdf_path)
                        except OSError:
                            pass

                    except Exception as e:
                        logger.error(f"Error converting DOCX file {file_name}: {str(e)}")
                        continue
                elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    # Convert image to PDF
                    with storage.open(file_name, 'rb') as img_f:
                        img = Image.open(io.BytesIO(img_f.read()))

                    # Convert to RGB if necessary
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    # Create PDF from image using ReportLab
                    img_buffer = io.BytesIO()
                    img_width, img_height = img.size

                    # Use A4 size for PDF
                    pdf_canvas = canvas.Canvas(img_buffer, pagesize=A4)
                    a4_width, a4_height = A4

                    # Calculate scaling to fit image on A4 page
                    scale = min(a4_width / img_width, a4_height / img_height)
                    new_width = img_width * scale
                    new_height = img_height * scale

                    # Center image on page
                    x = (a4_width - new_width) / 2
                    y = (a4_height - new_height) / 2

                    # Use ImageReader for PIL Image object
                    img_reader = ImageReader(img)
                    pdf_canvas.drawImage(img_reader, x, y, width=new_width, height=new_height)
                    pdf_canvas.save()

                    # Add image-converted PDF pages to writer
                    img_buffer.seek(0)
                    img_pdf_reader = PdfReader(img_buffer)
                    for page in img_pdf_reader.pages:
                        writer.add_page(page)
                    logger.info(f"Converted and added image: {file_name}")

            if len(writer.pages) == 0:
                return HttpResponse("Document files are missing from the server storage. The files may not have been synced to this environment.", status=404)

            # Write merged PDF to buffer
            output_buffer = io.BytesIO()
            writer.write(output_buffer)
            output_buffer.seek(0)

            # Return merged PDF
            import traceback as tb
            pdf_bytes = output_buffer.getvalue()
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="license_{license_obj.license_number}_documents.pdf"'
            return response

        except Exception as e:
            import traceback as tb
            full_trace = tb.format_exc()
            logger.error(f"Error merging documents: {full_trace}")
            return HttpResponse(f"Error: {str(e)}\n\n{full_trace}", status=500, content_type='text/plain')


# Add license report actions to viewset
LicenseDetailsViewSet = add_license_report_action(LicenseDetailsViewSet)
LicenseDetailsViewSet = add_active_dfia_report_action(LicenseDetailsViewSet)
