# in core/views.py (or wherever your other MasterViewSet registrations are)
from core.views import MasterViewSet
from core.views.views import enhance_config_with_fk, API_PREFIX
from license.models import LicenseDetailsModel
from license.serializers import LicenseDetailsSerializer

# ensure enhance_config_with_fk is in the same module (your file contains it)

LicenseDetailsViewSet = MasterViewSet.create(
    LicenseDetailsModel,
    LicenseDetailsSerializer,
    config=enhance_config_with_fk(
        LicenseDetailsModel,
        {
            "search": ["license_number", "exporter__name", "port__name"],
            "filter": ["license_number", "scheme_code", "exporter", "port", "is_active"],
            "list_display": [
                "license_number",
                "license_date",
                "license_expiry_date",
                "exporter__name",
                "port__name",
                "balance_cif",
                "is_active",
            ],
            "form_fields": [
                "license_number",
                "license_date",
                "license_expiry_date",
                "exporter",
                "port",
                "scheme_code",
                "notification_number",
                "registration_number",
                "registration_date",
                "is_active",
                "balance_cif",
                "current_owner",
            ],
            "fk_endpoint_overrides": {
                "exporter": "/masters/companies/",
                "port": "/masters/ports/",
                "current_owner": "/masters/companies/"
            },
            "nested_field_defs": {
                # these definitions help the frontend decide which nested sections to show
                "export_license": [
                    {"name": "description", "label": "Description", "type": "string"},
                    {
                        "name": "item",
                        "label": "Export Item",
                        "type": "foreignkey",
                        "fk_endpoint": f"{API_PREFIX}item-names/",
                        "label_field": "name"
                    },
                    {
                        "name": "norm_class",
                        "type": "foreignkey",
                        "label": "Norm Class",
                        "required": False,
                        "fk_endpoint": f"{API_PREFIX}sion-classes/",  # preferred single endpoint
                        "endpoints": [f"{API_PREFIX}sion-classes/"],  # alternatives (here only one)
                        "label_field": "norm_class",
                    },
                    {"name": "net_quantity", "label": "Net Quantity", "type": "number"},
                    {"name": "unit", "label": "Unit", "type": "string"},
                    {"name": "cif_fc", "label": "CIF (FC)", "type": "number"},
                ],
                "import_license": [
                    {"name": "serial_number", "label": "SR #", "type": "integer"},
                    {
                        "name": "hs_code",
                        "label": "HS Code",
                        "type": "foreignkey",
                        "fk_endpoint": f"{API_PREFIX}hs-codes/",
                        "label_field": "code"
                    },
                    {
                        "name": "items",
                        "label": "Items",
                        "type": "many2many",
                        "fk_endpoint": f"{API_PREFIX}item-names/",
                        "label_field": "name"
                    },
                    {"name": "quantity", "label": "Quantity", "type": "number"},
                    {"name": "available_quantity", "label": "Available Qty", "type": "number"},
                    {"name": "cif_fc", "label": "CIF (FC)", "type": "number"},
                ],
                "license_documents": [
                    {"name": "type", "label": "Type", "type": "string"},
                    {"name": "file", "label": "File", "type": "file"},
                ],
                "transfers": [
                    {"name": "transfer_date", "label": "Transfer Date", "type": "date"},
                    {
                        "name": "from_company",
                        "label": "Transfer From",
                        "type": "foreignkey",
                        "fk_endpoint": f"{API_PREFIX}companies/",
                        "label_field": "name"
                    },
                    {
                        "name": "to_company",
                        "label": "Transfer To",
                        "type": "foreignkey",
                        "fk_endpoint": f"{API_PREFIX}companies/",
                        "label_field": "name"
                    },
                    {"name": "transfer_status", "label": "Status", "type": "string"},
                ],
                "purchases": [
                    {"name": "invoice_number", "label": "Invoice #", "type": "string"},
                    {"name": "invoice_date", "label": "Invoice Date", "type": "date"},
                    {"name": "amount_inr", "label": "Amount (INR)", "type": "number"},
                    {
                        "name": "supplier",
                        "label": "Supplier",
                        "type": "foreignkey",
                        "fk_endpoint": f"{API_PREFIX}companies/",
                        "label_field": "name"
                    }
                ],
            },
            # field_meta will be enhanced by enhance_config_with_fk (adding endpoints & label_field for exporter, port, etc.)
        },
    ),
)
