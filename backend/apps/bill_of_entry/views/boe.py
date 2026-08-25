# bill_of_entry/views/boe.py
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import BillOfEntryPermission, TransferLetterPermission, AccountAccessPermission
from apps.bill_of_entry.models import BillOfEntryModel, annotate_and_exclude_hidden
from apps.bill_of_entry.serializers import BillOfEntrySerializer
from apps.bill_of_entry.services import boe_service
from apps.bill_of_entry.views_export import add_grouped_export_action
from apps.core.constants import TYPE_CHOICES, ROW_TYPE_CHOICES
from apps.core.filters import CombinedFilterBackend, EnhancedSearchFilter, AdvancedOrderingFilter
from apps.core.filtersets import BOEFilterSet
from apps.core.utils.exceptions import api_error
from apps.core.utils.transfer_letter import generate_transfer_letter_generic
from apps.core.views.master_view import MasterViewSet

# Nested field definitions for Bill of Entry
BOE_NESTED_FIELD_DEFS = {
    "item_details": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {
            "name": "sr_number", "type": "fk", "label": "License Item",
            "fk_endpoint": "/license-items/",
            "label_field": "description",
            "display_field": "item_description"
        },
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)"},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)"},
        {"name": "qty", "type": "number", "label": "Quantity"},
    ],
}

# BOE ViewSet configuration
BOE_VIEWSET_CONFIG = {
    "search": [
        "bill_of_entry_number",
        "invoice_no",
        "product_name",
        "planning_target_item",
        "item_details__sr_number__license__license_number",
    ],
    "inline_editable": ["invoice_no"],
    "filter": {
        "company": {"type": "fk", "fk_endpoint": "/masters/companies/", "label_field": "name"},
        "exclude_company": {"type": "exclude_fk", "fk_endpoint": "/masters/companies/", "label_field": "name", "filter_field": "company"},
        "port": {"type": "fk", "fk_endpoint": "/masters/ports/", "label_field": "name"},
        "exclude_port": {"type": "exclude_fk", "fk_endpoint": "/masters/ports/", "label_field": "name", "filter_field": "port"},
        "bill_of_entry_date": {"type": "date_range"},
        "is_fetch": {"type": "exact"},
    },
    "list_display": [
        "bill_of_entry_number",
        "bill_of_entry_date",
        "port__name",
        "company__name",
        "product_name",
        "total_fc",
        "total_inr",
        "total_quantity",
        "invoice_no",
        "licenses",
    ],
    "form_fields": [
        "bill_of_entry_number",
        "bill_of_entry_date",
        "port",
        "allotment",
        "company",
        "exchange_rate",
        "product_name",
        "planning_target_item",
        "invoice_no",
        "invoice_date",
        "appraisement",
        "ooc_date",
        "cha",
        "comments",
    ],
    "ordering": ["bill_of_entry_date", "bill_of_entry_number"],
    "nested_field_defs": BOE_NESTED_FIELD_DEFS,
    "nested_list_display": {
        "item_details": [
            "license_number",
            "item_description",
            "hs_code",
            "qty",
            "cif_fc",
            "cif_inr",
        ],
    },
    "field_meta": {
        "company": {"type": "fk", "fk_endpoint": "/masters/companies/", "label_field": "name"},
        "port": {"type": "fk", "fk_endpoint": "/masters/ports/", "label_field": "name"},
        "allotment": {"type": "m2m", "fk_endpoint": "/allotments/?is_boe=false", "label_field": "display_label"},
        "planning_target_item": {"type": "fk", "fk_endpoint": "/masters/item-names/?is_active=true", "label_field": "name"},
        "row_type": {"type": "select", "choices": list(ROW_TYPE_CHOICES)},
        "transaction_type": {"type": "select", "choices": list(TYPE_CHOICES)},
    }
}

BaseBillOfEntryViewSet = MasterViewSet.create_viewset(
    BillOfEntryModel,
    BillOfEntrySerializer,
    config=BOE_VIEWSET_CONFIG
)


class BillOfEntryViewSet(BaseBillOfEntryViewSet):
    """BOE ViewSet with custom filtering, invoice tracking, and business operations."""

    permission_classes = [BillOfEntryPermission]
    ordering = ["-bill_of_entry_date", "-bill_of_entry_number"]
    filterset_class = BOEFilterSet
    filter_backends = [CombinedFilterBackend, EnhancedSearchFilter, AdvancedOrderingFilter]
    search_fields = [
        'bill_of_entry_number',
        'invoice_no',
        'product_name',
        'port__name',
        'company__name',
        'item_details__sr_number__license__license_number',
    ]
    ordering_fields = ['bill_of_entry_date', 'bill_of_entry_number', 'company__name', 'port__name']

    def get_permissions(self):
        """Override permissions for special actions."""
        if self.action == 'generate_transfer_letter':
            return [TransferLetterPermission()]
        if self.action == 'update_invoice_no':
            return [AccountAccessPermission()]
        return super().get_permissions()

    def get_queryset(self):
        """Apply custom filtering and performance optimizations."""
        queryset = super().get_queryset()

        # Apply select_related for FK optimization
        queryset = queryset.select_related('company', 'port')

        # Prefetch related data to avoid N+1 queries
        queryset = queryset.prefetch_related(
            'item_details',
            'item_details__sr_number',
            'item_details__sr_number__hs_code',
            'item_details__sr_number__license',
            'item_details__sr_number__license__purchase_status',
            'item_details__sr_number__items',
            'allotment',
        )

        # Handle available_for_trade filtering
        if self.request.query_params.get('available_for_trade') == 'true':
            queryset = annotate_and_exclude_hidden(queryset)
            return queryset

        # Don't filter single-item retrieval by invoice status
        if self.action in ['retrieve', 'update', 'partial_update']:
            return queryset

        # Apply is_invoice filter with defaults
        return self._apply_invoice_filter(queryset)

    def _apply_invoice_filter(self, queryset):
        """Apply is_invoice filter logic."""
        is_invoice = self.request.query_params.get('is_invoice', 'false').lower()

        if is_invoice == 'all':
            return queryset
        elif is_invoice in ('true', '1', 'yes'):
            return queryset.filter(Q(invoice_no__isnull=False) & ~Q(invoice_no=''))
        else:
            return queryset.filter(Q(invoice_no__isnull=True) | Q(invoice_no=''))

    def apply_advanced_filters(self, qs, params, filter_config):
        """Exclude is_invoice from advanced filter processing (handled in get_queryset)."""
        params_copy = params.copy() if hasattr(params, 'copy') else dict(params)
        params_copy.pop('is_invoice', None)
        return super().apply_advanced_filters(qs, params_copy, filter_config)

    def retrieve(self, request, *args, **kwargs):
        """Include current BOE's allotments in metadata for edit mode."""
        response = super().retrieve(request, *args, **kwargs)
        instance = self.get_object()
        current_allotment_ids = list(instance.allotment.values_list('id', flat=True))

        if 'metadata' in response.data and current_allotment_ids:
            fields = response.data['metadata'].get('fields', {})
            if 'allotment' in fields:
                ids_str = ','.join(map(str, current_allotment_ids))
                fields['allotment']['fk_endpoint'] = f"/allotments/?is_boe=false_or_current&current_boe_allotments={ids_str}"

        return response

    def list(self, request, *args, **kwargs):
        """Inject is_invoice into filter_config for UI."""
        response = super().list(request, *args, **kwargs)
        if isinstance(response.data, dict) and 'filter_config' in response.data:
            response.data['filter_config']['is_invoice'] = {
                'type': 'exact',
                'label': 'Has Invoice'
            }
        return response

    @action(detail=False, methods=['get'], url_path='fetch-allotment-details')
    def fetch_allotment_details(self, request):
        """Fetch allotment details by ID, excluding items already in current BOE."""
        allotment_id = request.query_params.get('allotment_id')
        boe_id = request.query_params.get('boe_id')

        if not allotment_id:
            return Response({'error': 'allotment_id is required'}, status=400)

        try:
            return Response(boe_service.fetch_allotment_item_details(
                allotment_id=allotment_id,
                boe_id=boe_id or None,
            ))
        except Exception as e:
            return Response(api_error('Failed to fetch allotment details', e, __name__), status=500)

    @action(detail=True, methods=['post'], url_path='generate-transfer-letter')
    def generate_transfer_letter(self, request, pk=None):
        """Generate transfer letter for BOE."""
        boe = get_object_or_404(BillOfEntryModel.objects.select_related('company'), id=pk)
        return generate_transfer_letter_generic(boe, request, instance_type='boe')

    @action(detail=True, methods=['post'], url_path='update-product-name')
    def update_product_name(self, request, pk=None):
        """Update product_name from item_details if empty."""
        boe = get_object_or_404(BillOfEntryModel, id=pk)
        result = boe_service.update_product_name_for_boe(boe)

        status_code = 400 if (not result["success"] and result["message"].startswith("No items")) else 200
        return Response(result, status=status_code)

    @action(detail=True, methods=['post'], url_path='resolve-dispute')
    def resolve_dispute(self, request, pk=None):
        """Clear is_dispute flag on all RowDetails of a BOE."""
        boe = get_object_or_404(BillOfEntryModel, id=pk)
        return Response(boe_service.resolve_dispute(boe))

    @action(detail=True, methods=['post'], url_path='merge')
    def merge_boe(self, request, pk=None):
        """Merge a source BOE into this (target) BOE."""
        target_boe = get_object_or_404(BillOfEntryModel, id=pk)
        source_boe_id = request.data.get('source_boe_id')

        try:
            result = boe_service.merge_boe(target_boe, source_boe_id=source_boe_id)
        except ValueError as exc:
            msg = str(exc)
            status_code = 404 if "not found" in msg else 400
            return Response({'error': msg}, status=status_code)

        return Response(result)

    @action(detail=False, methods=['post'], url_path='bulk-update-product-names')
    def bulk_update_product_names(self, request):
        """Bulk update product_name for BOEs with empty product_name."""
        return Response(boe_service.bulk_update_product_names())

    @action(detail=True, methods=['post'], url_path='update-invoice-no')
    def update_invoice_no(self, request, pk=None):
        """Update invoice_no field (ACCOUNT_ACCESS or BOE_MANAGER only)."""
        boe = get_object_or_404(BillOfEntryModel, pk=pk)
        return Response(boe_service.update_invoice_no(boe, invoice_no=request.data.get('invoice_no', '')))


# Add grouped export functionality
BillOfEntryViewSet = add_grouped_export_action(BillOfEntryViewSet)
