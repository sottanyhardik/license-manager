# bill_of_entry/views/boe.py
from core.constants import TYPE_CHOICES, ROW_TYPE_CHOICES
from core.views.master_view import MasterViewSet
from bill_of_entry.models import BillOfEntryModel
from bill_of_entry.serializers import BillOfEntrySerializer

# Nested field definitions for Bill of Entry
boe_nested_field_defs = {
    "item_details": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {"name": "row_type", "type": "select", "label": "Row Type", "choices": list(ROW_TYPE_CHOICES)},
        {"name": "sr_number", "type": "fk", "label": "License Item",
         "fk_endpoint": "/api/license-items/",
         "label_field": "description",
         "display_field": "item_description"},
        {"name": "transaction_type", "type": "select", "label": "Transaction Type", "choices": list(TYPE_CHOICES)},
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
                "row_type",
                "license_number",
                "item_description",
                "hs_code",
                "transaction_type",
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
