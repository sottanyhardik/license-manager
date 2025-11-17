# allotment/views.py
from allotment.models import AllotmentModel
from allotment.serializers import AllotmentSerializer
from core.constants import ROW_TYPE_CHOICES
from core.views.master_view import MasterViewSet

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

AllotmentViewSet = MasterViewSet.create(
    AllotmentModel,
    AllotmentSerializer,
    config={
        "search": ["item_name", "company__name", "invoice", "bl_detail"],
        "filter": {
            "company": {"type": "fk", "fk_endpoint": "/masters/companies/", "label_field": "name"},
            "port": {"type": "fk", "fk_endpoint": "/masters/ports/", "label_field": "name"},
            "related_company": {"type": "fk", "fk_endpoint": "/masters/companies/", "label_field": "name"},
            "type": {"type": "choice", "choices": list(ROW_TYPE_CHOICES)},
            "estimated_arrival_date": {"type": "date_range"},
            "created_on": {"type": "date_range"},
            "item_name": {"type": "icontains"},
            "is_boe": {"type": "exact"},
        },
        "list_display": [
            "modified_on",
            "company__name",
            "item_name",
            "required_quantity",
            "unit_value_per_unit",
            "required_value",
            "estimated_arrival_date",
            "invoice",
            "is_boe",
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
        ],
        "ordering": ["estimated_arrival_date"],
        # "nested_field_defs": allotment_nested_field_defs,
        "nested_list_display": {
            "allotment_details": [
                "license_number",
                "serial_number",
                "product_description",
                "qty",
                "cif_fc",
                "cif_inr",
                "exporter",
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
                "choices": list(ROW_TYPE_CHOICES)
            },
        }
    }
)
