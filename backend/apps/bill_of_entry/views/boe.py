# bill_of_entry/views/boe.py
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import BillOfEntryPermission
from apps.bill_of_entry.models import BillOfEntryModel
from apps.bill_of_entry.serializers import BillOfEntrySerializer
from apps.bill_of_entry.services import boe_service
from apps.bill_of_entry.views_export import add_grouped_export_action
from apps.core.constants import TYPE_CHOICES, ROW_TYPE_CHOICES
from apps.core.filters import CombinedFilterBackend, EnhancedSearchFilter, AdvancedOrderingFilter
from apps.core.filtersets import BOEFilterSet
from apps.core.views.master_view import MasterViewSet

# Nested field definitions for Bill of Entry
boe_nested_field_defs = {
    "item_details": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {"name": "sr_number", "type": "fk", "label": "License Item",
         "fk_endpoint": "/license-items/",
         "label_field": "description",
         "display_field": "item_description"},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)"},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)"},
        {"name": "qty", "type": "number", "label": "Quantity"},
    ],
}

BaseBillOfEntryViewSet = MasterViewSet.create_viewset(
    BillOfEntryModel,
    BillOfEntrySerializer,
    config={
        "search": [
            "bill_of_entry_number",
            "invoice_no",
            "product_name",
            "item_details__sr_number__license__license_number",  # License number from related items
        ],
        "inline_editable": ["invoice_no"],  # Enable inline editing for invoice_no
        "filter": {
            "company": {"type": "fk", "fk_endpoint": "/masters/companies/", "label_field": "name"},
            "exclude_company": {"type": "exclude_fk", "fk_endpoint": "/masters/companies/", "label_field": "name",
                                "filter_field": "company"},
            "port": {"type": "fk", "fk_endpoint": "/masters/ports/", "label_field": "name"},
            "exclude_port": {"type": "exclude_fk", "fk_endpoint": "/masters/ports/", "label_field": "name",
                             "filter_field": "port"},
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
            "invoice_no",
            "invoice_date",
            "appraisement",
            "ooc_date",
            "cha",
            "comments",
        ],
        "ordering": ["-bill_of_entry_date", "bill_of_entry_number"],
        "nested_field_defs": boe_nested_field_defs,
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
            "company": {
                "type": "fk",
                "fk_endpoint": "/masters/companies/",
                "label_field": "name"
            },
            "port": {
                "type": "fk",
                "fk_endpoint": "/masters/ports/",
                "label_field": "name"
            },
            "allotment": {
                "type": "m2m",
                "fk_endpoint": "/allotments/?is_boe=false",
                "label_field": "display_label"
            },
            "row_type": {
                "type": "select",
                "choices": list(ROW_TYPE_CHOICES)
            },
            "transaction_type": {
                "type": "select",
                "choices": list(TYPE_CHOICES)
            },
        }
    }
)


# Create custom ViewSet with additional filtering
class BillOfEntryViewSet(BaseBillOfEntryViewSet):
    """Extended BOE ViewSet with custom filtering for trade form"""
    permission_classes = [BillOfEntryPermission]

    def get_permissions(self):
        if self.action == 'generate_transfer_letter':
            from apps.accounts.permissions import TransferLetterPermission
            return [TransferLetterPermission()]
        if self.action == 'update_invoice_no':
            from apps.accounts.permissions import AccountAccessPermission
            return [AccountAccessPermission()]
        return super().get_permissions()

    # Apply advanced filter backends
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

    def get_queryset(self):
        """Override to add custom filtering for available_for_trade"""
        queryset = super().get_queryset()

        # Check if filtering for available BOEs for trade
        available_for_trade = self.request.query_params.get('available_for_trade')
        current_boe = self.request.query_params.get('current_boe')
        current_invoice = self.request.query_params.get('current_invoice')

        if available_for_trade == 'true':
            # Build filter conditions
            filter_conditions = Q(invoice_no__isnull=True) | Q(invoice_no='')

            # Include current BOE if provided
            if current_boe:
                filter_conditions |= Q(id=current_boe)

            # Include BOEs with current invoice number if provided
            if current_invoice:
                filter_conditions |= Q(invoice_no=current_invoice)

            queryset = queryset.filter(filter_conditions)

        return queryset

    @action(detail=False, methods=['post'], url_path='bulk-update-product-names')
    def bulk_update_product_names(self, request):
        """
        Bulk update product_name for all BOEs with empty/None product_name.

        Returns:
        - success: True if completed
        - total: Total BOEs processed
        - updated: Count of successfully updated BOEs
        - skipped: Count of BOEs skipped (no items found)
        - message: Summary message
        """
        return Response(boe_service.bulk_update_product_names())


# Add grouped export functionality (attaches methods to existing class — no permission reset)
BillOfEntryViewSet = add_grouped_export_action(BillOfEntryViewSet)


# Add custom action to fetch allotment details
@action(detail=False, methods=['get'], url_path='fetch-allotment-details')
def fetch_allotment_details(self, request):
    """
    Fetch allotment details by allotment ID.
    Returns: exchange_rate, product_name, port, and item_details.

    Excludes items (license items) that are already in the current BOE's item_details
    to avoid duplicates when fetching from multiple allotments.
    """
    allotment_id = request.query_params.get('allotment_id')
    boe_id = request.query_params.get('boe_id')  # Current BOE ID (if editing)

    if not allotment_id:
        return Response({'error': 'allotment_id is required'}, status=400)

    try:
        return Response(boe_service.fetch_allotment_item_details(
            allotment_id=allotment_id,
            boe_id=boe_id or None,
        ))
    except Exception as e:
        from apps.core.utils.exceptions import api_error
        return Response(api_error('Failed to fetch allotment details', e, __name__), status=500)


BillOfEntryViewSet.fetch_allotment_details = fetch_allotment_details

# Override retrieve to adjust allotment filter for edit mode
original_retrieve = BillOfEntryViewSet.retrieve


def custom_retrieve(self, request, *args, **kwargs):
    """Override retrieve to include current BOE's allotments in the endpoint filter"""
    response = original_retrieve(self, request, *args, **kwargs)

    # Get the current BOE instance
    instance = self.get_object()

    # Get IDs of allotments assigned to this BOE
    current_allotment_ids = list(instance.allotment.values_list('id', flat=True))

    # Modify the metadata to include current allotments in the filter
    if 'metadata' in response.data:
        if 'allotment' in response.data['metadata'].get('fields', {}):
            # Update the endpoint to include current allotments
            if current_allotment_ids:
                ids_str = ','.join(map(str, current_allotment_ids))
                response.data['metadata']['fields']['allotment'][
                    'fk_endpoint'] = f"/allotments/?is_boe=false_or_current&current_boe_allotments={ids_str}"

    return response


BillOfEntryViewSet.retrieve = custom_retrieve

# Add default filter for is_invoice
original_get_queryset = BillOfEntryViewSet.get_queryset
original_apply_advanced_filters = BillOfEntryViewSet.apply_advanced_filters


def custom_get_queryset_with_defaults(self):
    """Override to apply default is_invoice filter and handle custom logic with performance optimizations"""
    qs = original_get_queryset(self)

    # Add select_related for FK fields to avoid N+1 queries
    qs = qs.select_related('company', 'port')

    # Prefetch item_details and the full FK chain used by RowDetailsSerializer
    qs = qs.prefetch_related(
        'item_details',
        'item_details__sr_number',
        'item_details__sr_number__hs_code',
        'item_details__sr_number__license',
        'item_details__sr_number__license__purchase_status',
        'item_details__sr_number__items',
        'allotment',
    )

    params = self.request.query_params

    # Don't apply default invoice filter for retrieve/update/partial_update actions
    # This allows fetching/updating single BOE by ID regardless of invoice status
    if self.action in ['retrieve', 'update', 'partial_update']:
        return qs

    # Handle is_invoice filter (custom logic, not a model field)
    if 'is_invoice' in params:
        is_invoice = params.get('is_invoice', '').lower()
        if is_invoice == 'all':
            # Show all BOE records (no filter)
            pass
        elif is_invoice in ['true', '1', 'yes']:
            # Filter records where invoice_no is not null and not empty
            qs = qs.filter(Q(invoice_no__isnull=False) & ~Q(invoice_no=''))
        elif is_invoice in ['false', '0', 'no']:
            # Filter records where invoice_no is null or empty
            qs = qs.filter(Q(invoice_no__isnull=True) | Q(invoice_no=''))
    else:
        # Default: is_invoice=False (invoice_no is null or empty)
        # Only apply this default for list view, not retrieve
        qs = qs.filter(Q(invoice_no__isnull=True) | Q(invoice_no=''))

    return qs


def custom_apply_advanced_filters(self, qs, params, filter_config):
    """Override to exclude is_invoice from advanced filter processing"""
    # Remove is_invoice from params before calling parent method
    # since it's handled in get_queryset
    params_copy = params.copy()
    if 'is_invoice' in params_copy:
        del params_copy['is_invoice']

    return original_apply_advanced_filters(self, qs, params_copy, filter_config)


BillOfEntryViewSet.get_queryset = custom_get_queryset_with_defaults
BillOfEntryViewSet.apply_advanced_filters = custom_apply_advanced_filters

# Override list method to inject is_invoice into filter_config
original_list = BillOfEntryViewSet.list


def custom_list(self, request, *args, **kwargs):
    """Override list to add is_invoice to filter_config for UI"""
    response = original_list(self, request, *args, **kwargs)

    # Add is_invoice to filter_config so it appears in the UI
    if isinstance(response.data, dict) and 'filter_config' in response.data:
        response.data['filter_config']['is_invoice'] = {
            'type': 'exact',
            'label': 'Has Invoice'
        }

    return response


BillOfEntryViewSet.list = custom_list


# Add generate transfer letter action
@action(detail=True, methods=['post'], url_path='generate-transfer-letter')
def generate_transfer_letter(self, request, pk=None):
    """
    Generate transfer letter for BOE using generic utility.

    Request body:
    - company_name: Company name (optional, uses BOE company if not provided)
    - address_line1: Address line 1
    - address_line2: Address line 2
    - template_id: ID of the transfer letter template
    - cif_edits: Dict of boe_item_id -> edited CIF FC value
    """
    from django.shortcuts import get_object_or_404
    from apps.core.utils.transfer_letter import generate_transfer_letter_generic

    # Transfer-letter generation requires the request object (carries auth + payload)
    # so it remains orchestrated in the view; the generic utility handles the domain work.
    boe = get_object_or_404(BillOfEntryModel.objects.select_related('company'), id=pk)
    return generate_transfer_letter_generic(boe, request, instance_type='boe')


BillOfEntryViewSet.generate_transfer_letter = generate_transfer_letter


# Add update product_name action
@action(detail=True, methods=['post'], url_path='update-product-name')
def update_product_name(self, request, pk=None):
    """
    Update product_name for BOE by fetching item names from item_details -> sr_number -> items.
    Only updates if product_name is empty/None (keeps existing values).

    Returns:
    - success: True if updated, False if skipped
    - product_name: The current product name
    - message: Success or skip message
    """
    from django.shortcuts import get_object_or_404

    boe = get_object_or_404(BillOfEntryModel, id=pk)
    result = boe_service.update_product_name_for_boe(boe)

    if not result["success"] and result["message"].startswith("No items"):
        return Response(result, status=400)
    return Response(result)


BillOfEntryViewSet.update_product_name = update_product_name


# Add resolve-dispute action — clears is_dispute flag on all rows of a BOE
@action(detail=True, methods=['post'], url_path='resolve-dispute')
def resolve_dispute(self, request, pk=None):
    """
    Clear the is_dispute flag on all RowDetails of a BOE.
    Used when a user has manually reviewed and resolved the dispute.

    Returns:
    - success: True
    - cleared: number of rows whose dispute flag was cleared
    """
    from django.shortcuts import get_object_or_404

    boe = get_object_or_404(BillOfEntryModel, id=pk)
    return Response(boe_service.resolve_dispute(boe))


BillOfEntryViewSet.resolve_dispute = resolve_dispute


# Add merge BOE action
@action(detail=True, methods=['post'], url_path='merge')
def merge_boe(self, request, pk=None):
    """
    Merge a source BOE into this (target) BOE.

    - Moves RowDetails from source to target (skips duplicate sr_number+transaction_type)
    - Transfers allotments from source to target
    - Updates target's port to source's port
    - Deletes source BOE

    Request body:
    - source_boe_id: ID of the BOE to merge from (will be deleted)
    """
    from django.shortcuts import get_object_or_404

    target_boe = get_object_or_404(BillOfEntryModel, id=pk)
    source_boe_id = request.data.get('source_boe_id')

    try:
        result = boe_service.merge_boe(target_boe, source_boe_id=source_boe_id)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            return Response({'error': msg}, status=404)
        return Response({'error': msg}, status=400)

    return Response(result)


BillOfEntryViewSet.merge_boe = merge_boe


# ── Update invoice number — accessible to ACCOUNT_ACCESS (accounts team) ──────
@action(detail=True, methods=['post'], url_path='update-invoice-no')
def update_invoice_no(self, request, pk=None):
    """
    Update only the invoice_no field on a BOE.
    Accessible to ACCOUNT_ACCESS role (accounts team) and BOE_MANAGER.
    Payload: { "invoice_no": "INV-12345" }
    """
    from django.shortcuts import get_object_or_404

    boe = get_object_or_404(BillOfEntryModel, pk=pk)
    return Response(boe_service.update_invoice_no(boe, invoice_no=request.data.get('invoice_no', '')))


BillOfEntryViewSet.update_invoice_no = update_invoice_no
