# allotment/views.py
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from allotment.models import AllotmentModel
from allotment.serializers import AllotmentSerializer
from allotment.views_export import add_grouped_export_action
from core.constants import ROW_TYPE_CHOICES
from core.views.master_view import MasterViewSet


def _get_active_usd_rate():
    """Get the active (latest) USD to INR exchange rate"""
    from core.models import ExchangeRateModel
    try:
        latest_rate = ExchangeRateModel.objects.order_by('-date').first()
        if latest_rate:
            return float(latest_rate.usd)
    except Exception:
        pass
    return None


# Nested field definitions for AllotmentDetails (for list display only, not form)
allotment_nested_field_defs = {
    "allotment_details": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {"name": "license_number", "type": "text", "label": "License Number", "read_only": True},
        {"name": "serial_number", "type": "text", "label": "Serial Number", "read_only": True},
        {"name": "product_description", "type": "text", "label": "Description", "read_only": True},
        {"name": "qty", "type": "number", "label": "Quantity", "read_only": True},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)", "read_only": True},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)", "read_only": True},
        {"name": "exporter", "type": "text", "label": "Exporter", "read_only": True},
        {"name": "license_date", "type": "date", "label": "License Date", "read_only": True},
        {"name": "license_expiry", "type": "date", "label": "License Expiry", "read_only": True},
    ]
}

AllotmentViewSet = MasterViewSet.create_viewset(
    AllotmentModel,
    AllotmentSerializer,
    config={
        "search": ["item_name", "company__name", "invoice", "bl_detail",
                   "allotment_details__item__license__license_number"],
        "filter": {
            "company": {"type": "fk", "fk_endpoint": "/masters/companies/", "label_field": "name"},
            "exclude_company": {"type": "exclude_fk", "fk_endpoint": "/masters/companies/", "label_field": "name",
                                "filter_field": "company"},
            "port": {"type": "fk", "fk_endpoint": "/masters/ports/", "label_field": "name"},
            "exclude_port": {"type": "exclude_fk", "fk_endpoint": "/masters/ports/", "label_field": "name",
                             "filter_field": "port"},
            "type": {"type": "choice", "choices": list(ROW_TYPE_CHOICES)},
            "estimated_arrival_date": {"type": "date_range"},
            "modified_on": {"type": "date_range"},
            "is_boe": {"type": "exact"},
            "is_allotted": {"type": "exact"},
        },
        "list_display": [
            "modified_on",
            "item_name",
            "company__name",
            "port__name",
            "required_quantity",
            "unit_value_per_unit",
            "required_value",
            "estimated_arrival_date",
            "is_approved",
            "invoice",
            "dfia_list"
        ],
        "form_fields": [
            "company",
            "type",
            "port",
            "item_name",
            "required_quantity",
            "cif_inr",
            "exchange_rate",
            "cif_fc",
            "unit_value_per_unit",
            "invoice",
            "estimated_arrival_date",
            "bl_detail",
            "is_boe",
            "is_approved",
        ],
        "ordering": ["estimated_arrival_date"],
        "nested_field_defs": allotment_nested_field_defs,
        "nested_list_display": {
            "allotment_details": [
                "license_number",
                "serial_number",
                "product_description",
                "qty",
                "cif_fc",
                "cif_inr",
                "license_date",
                "license_expiry",
            ]
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
            "related_company": {
                "type": "fk",
                "fk_endpoint": "/masters/companies/",
                "label_field": "name"
            },
            "type": {
                "type": "select",
                "choices": list(ROW_TYPE_CHOICES),
                "default": "AT"  # Default to Allotment
            },
            "exchange_rate": {
                "type": "number",
                "default": _get_active_usd_rate()  # Default to active USD to INR rate
            },
            "is_approved": {
                "type": "boolean",
                "widget": "switch",
                "label": "Approved"
            },
        }
    }
)

# Add grouped export functionality
AllotmentViewSet = add_grouped_export_action(AllotmentViewSet)

# Add default filters and performance optimizations
original_get_queryset = AllotmentViewSet.get_queryset


def custom_get_queryset_with_defaults(self):
    """Override to apply default filters and performance optimizations"""
    from django.db.models import Q

    qs = original_get_queryset(self)

    # Add select_related for FK fields to avoid N+1 queries
    qs = qs.select_related('company', 'port', 'related_company')

    # Prefetch related allotment_details for better performance
    qs = qs.prefetch_related('allotment_details')

    params = self.request.query_params

    # Don't apply default filters for retrieve/update/delete operations (detail views)
    # Check if this is a detail operation by looking at the action
    action = getattr(self, 'action', None)
    if action in ['retrieve', 'update', 'partial_update', 'destroy']:
        # For detail views, return all records without default filters
        return qs

    # Handle is_boe filter
    is_boe_param = params.get('is_boe', '')

    if is_boe_param == 'false_or_current':
        # Special case for BOE edit: include current BOE's allotments
        current_boe_allotments = params.get('current_boe_allotments', '')
        if current_boe_allotments:
            allotment_ids = [int(id) for id in current_boe_allotments.split(',') if id.isdigit()]
            # Show allotments that either don't have BOE OR are in the current BOE
            qs = qs.filter(Q(is_boe=False) | Q(id__in=allotment_ids))
        else:
            qs = qs.filter(is_boe=False)
    elif is_boe_param in ['false', 'False', '0']:
        # Explicitly filter for is_boe=False
        qs = qs.filter(is_boe=False)
    elif is_boe_param in ['true', 'True', '1']:
        # Explicitly filter for is_boe=True
        qs = qs.filter(is_boe=True)
    elif is_boe_param.lower() == 'all':
        # Show all records - no filtering by is_boe
        pass
    elif 'is_boe' not in params:
        # Default: Not BOE (only if not specified)
        qs = qs.filter(is_boe=False)

    # Apply default filters only if the user hasn't specified these filters
    if 'type' not in params:
        qs = qs.filter(type='AT')  # Default: Allotment type

    # Handle is_allotted filter - skip if "all"
    is_allotted_param = params.get('is_allotted', '')
    if is_allotted_param.lower() != 'all' and 'is_allotted' not in params:
        qs = qs.filter(is_allotted=True)  # Default: Allotted

    return qs


AllotmentViewSet.get_queryset = custom_get_queryset_with_defaults

# Override create to inject exchange_rate default in metadata
original_create = AllotmentViewSet.create


def custom_create_with_defaults(self, request, *args, **kwargs):
    """Override create to add exchange_rate default to metadata"""
    response = original_create(self, request, *args, **kwargs)

    # If this is a GET request to the create endpoint (for metadata), add exchange_rate default
    if request.method == 'GET' and hasattr(response, 'data') and 'metadata' in response.data:
        exchange_rate_default = _get_active_usd_rate()
        if exchange_rate_default and 'fields' in response.data['metadata']:
            if 'exchange_rate' in response.data['metadata']['fields']:
                response.data['metadata']['fields']['exchange_rate']['default'] = exchange_rate_default

    return response


AllotmentViewSet.create = custom_create_with_defaults


# Add copy action
@action(detail=True, methods=['post'], url_path='copy')
def copy_allotment(self, request, pk=None):
    """
    Copy an allotment without invoice number and allotment items.
    Creates a new allotment with the same data except invoice and allotment_details.
    """
    try:
        # Get the original allotment
        original = self.get_object()

        # Create a copy without invoice and allotment items
        copied_data = {
            'company': original.company_id,
            'type': original.type,
            'required_quantity': original.required_quantity,
            'unit_value_per_unit': original.unit_value_per_unit,
            'cif_fc': original.cif_fc,
            'cif_inr': original.cif_inr,
            'exchange_rate': original.exchange_rate,
            'item_name': original.item_name,
            'contact_person': original.contact_person,
            'contact_number': original.contact_number,
            'estimated_arrival_date': original.estimated_arrival_date,
            'bl_detail': original.bl_detail,
            'port': original.port_id if original.port else None,
            'related_company': original.related_company_id if original.related_company else None,
            'is_approved': False,  # Reset approval status
        }

        # Remove None values
        copied_data = {k: v for k, v in copied_data.items() if v is not None}

        # Create new allotment using serializer
        serializer = AllotmentSerializer(data=copied_data, context={'request': request})
        if serializer.is_valid():
            new_allotment = serializer.save()
            return Response(
                AllotmentSerializer(new_allotment, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


AllotmentViewSet.copy_allotment = copy_allotment
