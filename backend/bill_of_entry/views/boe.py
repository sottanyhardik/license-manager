# bill_of_entry/views/boe.py
from django.db.models import Q

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
         "fk_endpoint": "/api/license-items/",
         "label_field": "description",
         "display_field": "item_description"},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)"},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)"},
        {"name": "qty", "type": "number", "label": "Quantity"},
        {"name": "license_number", "type": "text", "label": "License Number", "read_only": True},
        {"name": "hs_code", "type": "text", "label": "HS Code", "read_only": True},
    ],
}

BillOfEntryViewSet = MasterViewSet.create(
    BillOfEntryModel,
    BillOfEntrySerializer,
    config={
        "search": ["bill_of_entry_number", "invoice_no", "product_name"],
        "filter": {
            "company": {"type": "fk", "fk_endpoint": "/masters/companies/", "label_field": "name"},
            "port": {"type": "fk", "fk_endpoint": "/masters/ports/", "label_field": "name"},
            "bill_of_entry_date": {"type": "date_range"},
            "invoice_date": {"type": "date_range"},
            "is_fetch": {"type": "exact"},
        },
        "list_display": [
            "bill_of_entry_number",
            "bill_of_entry_date",
            "company__name",
            "port__name",
            "invoice_no",
            "invoice_date",
            "total_fc",
            "total_inr",
            "total_quantity",
            "licenses",
        ],
        "form_fields": [
            "company",
            "bill_of_entry_number",
            "bill_of_entry_date",
            "port",
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

# Add grouped export functionality
BillOfEntryViewSet = add_grouped_export_action(BillOfEntryViewSet)

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

    # Handle is_invoice filter (custom logic, not a model field)
    if 'is_invoice' in params:
        is_invoice = params.get('is_invoice', '').lower()
        if is_invoice in ['true', '1', 'yes']:
            # Filter records where invoice_no is not null and not empty
            qs = qs.filter(Q(invoice_no__isnull=False) & ~Q(invoice_no=''))
        elif is_invoice in ['false', '0', 'no']:
            # Filter records where invoice_no is null or empty
            qs = qs.filter(Q(invoice_no__isnull=True) | Q(invoice_no=''))
    else:
        # Default: is_invoice=False (invoice_no is null or empty)
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
