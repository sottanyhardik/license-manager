# license/views/license.py
from core.constants import LICENCE_PURCHASE_CHOICES, SCHEME_CODE_CHOICES, NOTIFICATION_NORM_CHOICES, UNIT_CHOICES, \
    CURRENCY_CHOICES
from core.views.master_view import MasterViewSet
from license.models import LicenseDetailsModel
from license.serializers import LicenseDetailsSerializer

# Nested field definitions for LicenseDetails
license_nested_field_defs = {
    "export_license": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {"name": "description", "type": "text", "label": "Description"},
        {"name": "norm_class", "type": "fk", "label": "Norm Class", "fk_endpoint": "/masters/sion-classes/",
         "label_field": "norm_class", "display_field": "norm_class_label"},
        {"name": "start_serial_number", "type": "number", "label": "Start Serial Number"},
        {"name": "net_quantity", "type": "number", "label": "Net Quantity"},
        {"name": "fob_inr", "type": "number", "label": "FOB (INR)"},
        {"name": "currency", "type": "select", "label": "Currency", "choices": list(CURRENCY_CHOICES)},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)"},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)"},
    ],
    "import_license": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {"name": "serial_number", "type": "number", "label": "Serial Number"},
        {"name": "hs_code", "type": "fk", "label": "HS Code", "fk_endpoint": "/masters/hs-codes/",
         "label_field": "hs_code", "display_field": "hs_code_label"},
        {"name": "description", "type": "text", "label": "Description"},
        {"name": "items", "type": "fk_multi", "label": "Items", "fk_endpoint": "/masters/item-names/",
         "label_field": "name", "show_in_list": False},
        {"name": "quantity", "type": "number", "label": "Quantity"},
        {"name": "unit", "type": "select", "label": "Unit", "choices": list(UNIT_CHOICES)},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)"},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)"},
        {"name": "is_restricted", "type": "boolean", "label": "Is Restricted"},
    ],
    "license_documents": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {"name": "type", "type": "text", "label": "Document Type"},
        {"name": "file", "type": "file", "label": "File"},
    ],
}

# Create base viewset
_LicenseDetailsViewSetBase = MasterViewSet.create(
    LicenseDetailsModel,
    LicenseDetailsSerializer,
    config={
        "search": ["license_number", "file_number", "exporter__name"],
        "filter": {
            "exporter": {"type": "fk", "fk_endpoint": "/masters/companies/", "label_field": "name"},
            "port": {"type": "fk", "fk_endpoint": "/masters/ports/", "label_field": "name"},
            "export_license__norm_class": {"type": "fk", "fk_endpoint": "/masters/sion-classes/",
                                           "label_field": "norm_class"},
            "notification_number": {"type": "choice", "choices": list(NOTIFICATION_NORM_CHOICES)},
            "purchase_status": {"type": "choice", "choices": list(LICENCE_PURCHASE_CHOICES)},
            "license_date": {"type": "date_range"},
            "license_expiry_date": {"type": "date_range"},
            "is_expired": {"type": "exact"},
            "is_null": {"type": "exact"},
        },
        "default_filters": {
            "is_expired": "False",
            "is_null": "False"
        },
        "list_display": [
            "license_number",
            "license_date",
            "license_expiry_date",
            "exporter__name",
            "port__name",
            "purchase_status",
            "balance_cif",
            "latest_transfer",
            "get_norm_class"
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


# Extend the base viewset to add custom filter logic for is_expired and is_null
class LicenseDetailsViewSet(_LicenseDetailsViewSetBase):
    """
    Custom license viewset with special handling for is_expired and is_null filters.

    Filter Logic:
    - is_expired: True when license_expiry_date < today, False when license_expiry_date >= today
    - is_null: True when balance_cif < 200, False when balance_cif >= 200
    """

    def apply_advanced_filters(self, qs, params, filter_config):
        """Override to add custom logic for is_expired and is_null."""
        from datetime import date
        from django.db.models import Q

        # Handle is_expired filter
        is_expired_value = params.get('is_expired')
        if is_expired_value is not None and is_expired_value != "":
            today = date.today()
            if is_expired_value in ("True", "true", "1", True):
                # Show expired licenses: expiry_date < today
                qs = qs.filter(license_expiry_date__lt=today)
            elif is_expired_value in ("False", "false", "0", False):
                # Show non-expired licenses: expiry_date >= today OR null
                qs = qs.filter(Q(license_expiry_date__gte=today) | Q(license_expiry_date__isnull=True))

        # Handle is_null filter
        is_null_value = params.get('is_null')
        if is_null_value is not None and is_null_value != "":
            if is_null_value in ("True", "true", "1", True):
                # Show null licenses: balance_cif < 200
                qs = qs.filter(balance_cif__lt=200)
            elif is_null_value in ("False", "false", "0", False):
                # Show non-null licenses: balance_cif >= 200
                qs = qs.filter(balance_cif__gte=200)

        # Call parent method for remaining filters (exclude is_expired and is_null from parent processing)
        # Create a new QueryDict-like object without is_expired and is_null
        from django.http import QueryDict
        filtered_params = QueryDict(mutable=True)
        for key, value in params.items():
            if key not in ('is_expired', 'is_null'):
                filtered_params[key] = value

        # Create a copy of filter_config without is_expired and is_null
        filtered_config = {k: v for k, v in filter_config.items() if k not in ('is_expired', 'is_null')}

        # Call parent method with filtered params and config
        qs = super().apply_advanced_filters(qs, filtered_params, filtered_config)

        return qs
