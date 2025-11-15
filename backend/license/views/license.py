# license/views/license.py
from core.views.master_view import MasterViewSet
from license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from license.serializers import LicenseDetailsSerializer, LicenseExportItemSerializer, LicenseImportItemSerializer
from core.constants import LICENCE_PURCHASE_CHOICES, SCHEME_CODE_CHOICES, NOTIFICATION_NORM_CHOICES, UNIT_CHOICES, CURRENCY_CHOICES


# Nested field definitions for LicenseDetails
license_nested_field_defs = {
    "export_license": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True},
        {"name": "description", "type": "text", "label": "Description"},
        {"name": "item", "type": "fk", "label": "Item", "fk_endpoint": "/masters/item-names/", "label_field": "name"},
        {"name": "norm_class", "type": "fk", "label": "Norm Class", "fk_endpoint": "/masters/sion-classes/", "label_field": "norm_class"},
        {"name": "start_serial_number", "type": "number", "label": "Start Serial Number"},
        {"name": "duty_type", "type": "text", "label": "Duty Type"},
        {"name": "net_quantity", "type": "number", "label": "Net Quantity"},
        {"name": "unit", "type": "select", "label": "Unit", "choices": list(UNIT_CHOICES)},
        {"name": "fob_fc", "type": "number", "label": "FOB (FC)"},
        {"name": "fob_inr", "type": "number", "label": "FOB (INR)"},
        {"name": "fob_exchange_rate", "type": "number", "label": "FOB Exchange Rate"},
        {"name": "currency", "type": "select", "label": "Currency", "choices": list(CURRENCY_CHOICES)},
        {"name": "value_addition", "type": "number", "label": "Value Addition"},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)"},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)"},
    ],
    "import_license": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True},
        {"name": "serial_number", "type": "number", "label": "Serial Number"},
        {"name": "hs_code", "type": "fk", "label": "HS Code", "fk_endpoint": "/masters/hs-codes/", "label_field": "hs_code"},
        {"name": "items", "type": "fk_multi", "label": "Items", "fk_endpoint": "/masters/item-names/", "label_field": "name"},
        {"name": "description", "type": "text", "label": "Description"},
        {"name": "duty_type", "type": "text", "label": "Duty Type"},
        {"name": "quantity", "type": "number", "label": "Quantity"},
        {"name": "unit", "type": "select", "label": "Unit", "choices": list(UNIT_CHOICES)},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)"},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)"},
        {"name": "available_quantity", "type": "number", "label": "Available Quantity"},
        {"name": "available_value", "type": "number", "label": "Available Value"},
    ],
}


LicenseDetailsViewSet = MasterViewSet.create(
    LicenseDetailsModel,
    LicenseDetailsSerializer,
    config={
        "search": ["license_number", "file_number", "exporter__name"],
        "filter": {
            "license_number": {"type": "icontains"},
            "file_number": {"type": "icontains"},
            "exporter": {"type": "fk", "fk_endpoint": "/masters/companies/", "label_field": "name"},
            "port": {"type": "fk", "fk_endpoint": "/masters/ports/", "label_field": "name"},
            "license_date": {"type": "date_range"},
            "license_expiry_date": {"type": "date_range"},
            "purchase_status": {"type": "choice", "choices": list(LICENCE_PURCHASE_CHOICES)},
            "scheme_code": {"type": "choice", "choices": list(SCHEME_CODE_CHOICES)},
            "notification_number": {"type": "choice", "choices": list(NOTIFICATION_NORM_CHOICES)},
            "is_active": {"type": "exact"},
        },
        "list_display": [
            "license_number",
            "license_date",
            "license_expiry_date",
            "exporter__name",
            "port__name",
            "purchase_status",
            "balance_cif",
            "is_active",
        ],
        "form_fields": [
            "license_number",
            "license_date",
            "license_expiry_date",
            "file_number",
            "exporter",
            "port",
            "purchase_status",
            "scheme_code",
            "notification_number",
            "registration_number",
            "registration_date",
            "user_comment",
            "condition_sheet",
            "user_restrictions",
            "ledger_date",
            "is_audit",
            "is_mnm",
            "is_not_registered",
            "is_null",
            "is_au",
            "is_active",
            "balance_cif",
            "export_item",
            "is_incomplete",
            "is_expired",
            "is_individual",
            "ge_file_number",
            "fob",
            "billing_rate",
            "billing_amount",
            "current_owner",
            "file_transfer_status",
        ],
        "ordering": ["-license_date", "license_number"],
        "nested_field_defs": license_nested_field_defs,
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
                "type": "select",
                "choices": list(LICENCE_PURCHASE_CHOICES)
            },
            "scheme_code": {
                "type": "select",
                "choices": list(SCHEME_CODE_CHOICES)
            },
            "notification_number": {
                "type": "select",
                "choices": list(NOTIFICATION_NORM_CHOICES)
            },
        }
    }
)
