# bill_of_entry/views/boe.py
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.response import Response

from bill_of_entry.models import BillOfEntryModel
from bill_of_entry.serializers import BillOfEntrySerializer
from bill_of_entry.views_export import add_grouped_export_action
from core.constants import TYPE_CHOICES, ROW_TYPE_CHOICES
from core.views.master_view import MasterViewSet

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
        # Get all BOEs with empty product_name
        empty_product_boes = BillOfEntryModel.objects.filter(
            Q(Q(product_name__isnull=True) | Q(product_name='')) & Q(invoice_no__isnull=True)
        ).prefetch_related('item_details__sr_number__items')

        total_count = empty_product_boes.count()
        updated_count = 0
        skipped_count = 0

        for boe in empty_product_boes:
            generated_name = boe.generate_product_name_from_items()

            if generated_name:
                boe.product_name = generated_name
                boe.save(update_fields=['product_name'])
                updated_count += 1
            else:
                skipped_count += 1

        return Response({
            'success': True,
            'total': total_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'message': f'Processed {total_count} BOEs: {updated_count} updated, {skipped_count} skipped (no items found)'
        })


# Add grouped export functionality
BillOfEntryViewSet = add_grouped_export_action(BillOfEntryViewSet)


# Add custom action to fetch allotment details
@action(detail=False, methods=['get'], url_path='fetch-allotment-details')
def fetch_allotment_details(self, request):
    """
    Fetch allotment details by allotment ID
    Returns: exchange_rate, product_name, port, and item_details
    """
    allotment_id = request.query_params.get('allotment_id')

    if not allotment_id:
        return Response({'error': 'allotment_id is required'}, status=400)

    try:
        from allotment.models import AllotmentModel
        allotment = AllotmentModel.objects.select_related('company', 'port').prefetch_related(
            'allotment_details__item__license__import_license',
            'allotment_details__item__hs_code'
        ).get(id=allotment_id)

        # Get allotment items (license items linked to this allotment)
        allotment_items = allotment.allotment_details.select_related(
            'item__license', 'item__hs_code'
        ).all()

        # Build item details from allotment items
        item_details = []
        exchange_rate = float(allotment.exchange_rate) if allotment.exchange_rate else 0.0

        for allot_item in allotment_items:
            license_item = allot_item.item
            if license_item:
                # Use CIF values from allotment_items if available, else calculate
                cif_fc = float(allot_item.cif_fc) if allot_item.cif_fc else 0.0
                cif_inr = float(allot_item.cif_inr) if allot_item.cif_inr else (cif_fc * exchange_rate)

                # If no CIF in allotment, calculate from license item
                if cif_fc == 0.0 and license_item.unit_price and license_item.quantity:
                    cif_fc = float(license_item.unit_price * license_item.quantity)
                    cif_inr = cif_fc * exchange_rate

                item_details.append({
                    'sr_number': license_item.id,
                    'license_number': license_item.license.license_number if license_item.license else '',
                    'item_description': license_item.description or '',
                    'hs_code': license_item.hs_code.hs_code if license_item.hs_code else '',
                    'qty': float(allot_item.qty) if allot_item.qty else (
                        float(license_item.quantity) if license_item.quantity else 0.0),
                    'cif_fc': cif_fc,
                    'cif_inr': cif_inr,
                })

        return Response({
            'exchange_rate': exchange_rate,
            'product_name': allotment.item_name or '',
            'port': allotment.port.id if allotment.port else None,
            'port_name': allotment.port.name if allotment.port else '',
            'company': allotment.company.id if allotment.company else None,
            'company_name': allotment.company.name if allotment.company else '',
            'item_details': item_details,
        })

    except Exception as e:
        return Response({'error': str(e)}, status=500)


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

    # Prefetch related item_details for better performance
    qs = qs.prefetch_related('item_details')

    params = self.request.query_params

    # Don't apply default invoice filter for retrieve action (fetching single BOE by ID)
    # This allows HybridSelect to fetch BOEs even if they have an invoice assigned
    if self.action == 'retrieve':
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
    from core.utils.transfer_letter import generate_transfer_letter_generic

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
    from rest_framework.response import Response

    boe = get_object_or_404(BillOfEntryModel, id=pk)

    # Check if product_name is already filled
    if boe.product_name and boe.product_name.strip():
        return Response({
            'success': False,
            'product_name': boe.product_name,
            'message': f'Product name already exists: {boe.product_name}. Skipped update.'
        })

    # Generate product name from items
    generated_name = boe.generate_product_name_from_items()

    if not generated_name:
        return Response({
            'success': False,
            'message': 'No items found to generate product name',
            'product_name': boe.product_name
        }, status=400)

    # Update product_name only if it was empty
    boe.product_name = generated_name
    boe.save(update_fields=['product_name'])

    return Response({
        'success': True,
        'product_name': generated_name,
        'message': f'Product name updated successfully to: {generated_name}'
    })


BillOfEntryViewSet.update_product_name = update_product_name
