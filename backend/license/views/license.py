# license/views/license.py
from rest_framework.decorators import action
from rest_framework.response import Response

from core.constants import LICENCE_PURCHASE_CHOICES, LICENCE_PURCHASE_CHOICES_ACTIVE, SCHEME_CODE_CHOICES, \
    NOTIFICATION_NORM_CHOICES, UNIT_CHOICES, \
    CURRENCY_CHOICES
from core.views.master_view import MasterViewSet
from license.models import LicenseDetailsModel
from license.serializers import LicenseDetailsSerializer, LicenseExportItemSerializer, LicenseImportItemSerializer, \
    LicenseDocumentSerializer
from license.views.active_dfia_report import add_active_dfia_report_action
from license.views.license_report import add_license_report_action

# Nested field definitions for LicenseDetails
license_nested_field_defs = {
    "export_license": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {"name": "description", "type": "text", "label": "Description"},
        {"name": "norm_class", "type": "fk", "label": "Norm Class", "fk_endpoint": "/masters/sion-classes/",
         "label_field": "norm_class", "display_field": "norm_class_label"},
        {"name": "start_serial_number", "type": "number", "label": "Start Serial Number", "default": 0},
        {"name": "net_quantity", "type": "number", "label": "Net Quantity", "default": 0},
        {"name": "fob_inr", "type": "number", "label": "FOB (INR)", "default": 0},
        {"name": "currency", "type": "select", "label": "Currency", "choices": list(CURRENCY_CHOICES),
         "default": "usd"},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)", "default": 0},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)", "default": 0},
    ],
    "import_license": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {"name": "serial_number", "type": "number", "label": "Serial Number", "default": 0},
        {"name": "hs_code", "type": "fk", "label": "HS Code", "fk_endpoint": "/masters/hs-codes/",
         "label_field": "hs_code", "display_field": "hs_code_label"},
        {"name": "description", "type": "text", "label": "Description"},
        {"name": "items", "type": "fk_multi", "label": "Items", "fk_endpoint": "/masters/item-names/",
         "label_field": "name", "show_in_list": False},
        {"name": "quantity", "type": "number", "label": "Quantity", "default": 0},
        {"name": "unit", "type": "select", "label": "Unit", "choices": list(UNIT_CHOICES), "default": "kg"},
        {"name": "cif_fc", "type": "number", "label": "CIF (FC)", "default": 0},
        {"name": "cif_inr", "type": "number", "label": "CIF (INR)", "default": 0},
        {"name": "is_restricted", "type": "boolean", "label": "Is Restricted"},
    ],
    "license_documents": [
        {"name": "id", "type": "text", "label": "ID", "read_only": True, "show_in_list": False},
        {
            "name": "type",
            "type": "select",
            "label": "Document Type",
            "choices": [
                {"value": "LICENSE COPY", "label": "LICENSE COPY"},
                {"value": "TRANSFER LETTER", "label": "TRANSFER LETTER"},
                {"value": "OTHER", "label": "OTHER"}
            ]
        },
        {"name": "file", "type": "file", "label": "File"},
    ],
}

# Create base viewset
_LicenseDetailsViewSetBase = MasterViewSet.create_viewset(
    LicenseDetailsModel,
    LicenseDetailsSerializer,
    config={
        "search": ["license_number", "file_number", "exporter__name"],
        "filter": {
            "exporter": {"type": "fk", "fk_endpoint": "/masters/companies/", "label_field": "name"},
            "exclude_exporter": {"type": "exclude_fk", "fk_endpoint": "/masters/companies/", "label_field": "name",
                                 "filter_field": "exporter"},
            "port": {"type": "fk", "fk_endpoint": "/masters/ports/", "label_field": "name"},
            "exclude_port": {"type": "exclude_fk", "fk_endpoint": "/masters/ports/", "label_field": "name",
                             "filter_field": "port"},
            "export_license__norm_class": {"type": "fk", "fk_endpoint": "/masters/sion-classes/",
                                           "label_field": "norm_class"},
            "notification_number": {"type": "choice", "choices": list(NOTIFICATION_NORM_CHOICES)},
            "purchase_status": {"type": "choice", "choices": list(LICENCE_PURCHASE_CHOICES_ACTIVE)},
            "license_date": {"type": "date_range"},
            "license_expiry_date": {"type": "date_range"},
            "balance_cif": {"type": "range"},
            "is_expired": {"type": "exact"},
            "is_null": {"type": "exact"},
        },
        "default_filters": {
            "is_expired": "False",
            "is_null": "False",
            "purchase_status": "GE,NP,SM,CO"
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
                "choices": list(SCHEME_CODE_CHOICES),
                "default": "26"
            },
            "notification_number": {
                "type": "select",
                "choices": list(NOTIFICATION_NORM_CHOICES),
                "default": "025/2023"
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

    def update(self, request, *args, **kwargs):
        """Override to log incoming request data."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info("=" * 50)
        logger.info("ViewSet.update called")
        logger.info("request.data type: %s", type(request.data))
        logger.info("request.data keys: %s", list(request.data.keys()) if hasattr(request.data, 'keys') else 'N/A')

        # Log license_documents from request.data
        if 'license_documents' in request.data:
            docs = request.data.getlist('license_documents') if hasattr(request.data, 'getlist') else request.data.get(
                'license_documents')
            logger.info("license_documents in request.data: %s", docs)
        else:
            logger.info("license_documents NOT in request.data")

        # Log all keys that contain 'license_documents'
        if hasattr(request.data, 'keys'):
            doc_keys = [k for k in request.data.keys() if 'license_documents' in k]
            logger.info("Keys containing 'license_documents': %s", doc_keys)
            for key in doc_keys[:5]:  # Log first 5
                logger.info("  %s = %s", key, request.data.get(key))

        return super().update(request, *args, **kwargs)

    def get_queryset(self):
        """
        Override to add performance optimizations with select_related and prefetch_related.
        For detail view (retrieve/update/partial_update), don't apply default filters so expired licenses can be edited.
        """
        # For detail view actions, skip default filters by temporarily clearing them
        skip_default_filters = self.action in ['retrieve', 'update', 'partial_update', 'destroy', 'nested_items']

        if skip_default_filters:
            # Save original default filters
            original_default_filters = getattr(self, 'default_filters', {})
            # Temporarily clear default filters
            self.default_filters = {}

        qs = super().get_queryset()

        # Restore original default filters if they were cleared
        if skip_default_filters:
            self.default_filters = original_default_filters

        # Add select_related for ForeignKey fields to avoid N+1 queries
        qs = qs.select_related('exporter', 'port', 'current_owner')

        # Only prefetch nested items for detail view (single object)
        # For list view, this causes massive performance issues
        if self.action == 'retrieve':
            # Prefetch nested relationships for detail view only
            qs = qs.prefetch_related(
                'export_license',
                'export_license__norm_class',
                'import_license',
                'import_license__hs_code',
                'import_license__items',
                'import_license__items__sion_norm_class',
                'license_documents'
            )

        return qs

    def apply_advanced_filters(self, qs, params, filter_config):
        """Override to add custom logic for is_expired and is_null with default values."""
        from datetime import date
        from django.db.models import Q

        # Get default filters
        default_filters = getattr(self, "default_filters", {})

        # Handle is_expired filter - apply default if not provided
        is_expired_value = params.get('is_expired')

        # Special case: if user explicitly selects "all", don't apply any filter
        if is_expired_value and is_expired_value.lower() == "all":
            is_expired_value = None
        elif is_expired_value is None or is_expired_value == "":
            # Apply default if no value provided
            is_expired_value = default_filters.get('is_expired')

        if is_expired_value is not None and is_expired_value != "":
            today = date.today()
            if is_expired_value in ("True", "true", "1", True):
                # Show expired licenses: expiry_date < today
                qs = qs.filter(license_expiry_date__lt=today)
            elif is_expired_value in ("False", "false", "0", False):
                # Show non-expired licenses: expiry_date >= today OR null
                qs = qs.filter(Q(license_expiry_date__gte=today) | Q(license_expiry_date__isnull=True))

        # Handle is_null filter - apply default if not provided
        is_null_value = params.get('is_null')

        # Special case: if user explicitly selects "all", don't apply any filter
        if is_null_value and is_null_value.lower() == "all":
            is_null_value = None
        elif is_null_value is None or is_null_value == "":
            # Apply default if no value provided
            is_null_value = default_filters.get('is_null')

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

    @action(detail=True, methods=['get'])
    def nested_items(self, request, pk=None):
        """
        Fetch nested items for a specific license on demand.
        This endpoint is called lazily when user expands a license row.
        """
        license_obj = self.get_object()

        return Response({
            'export_license': LicenseExportItemSerializer(license_obj.export_license.all(), many=True).data,
            'import_license': LicenseImportItemSerializer(license_obj.import_license.all(), many=True,
                                                          context={'request': request}).data,
            'license_documents': LicenseDocumentSerializer(license_obj.license_documents.all(), many=True).data
        })

    @action(detail=True, methods=['get'], url_path='merged-documents')
    def merged_documents(self, request, pk=None):
        """
        Merge all license documents (LICENSE COPY + TRANSFER LETTER) into one PDF.
        Converts images to PDF if needed.
        """
        from django.http import FileResponse, HttpResponse
        import io
        import os
        import logging

        logger = logging.getLogger(__name__)
        license_obj = LicenseDetailsModel.objects.get(pk=pk)
        documents = license_obj.license_documents.all()

        if not documents.exists():
            return HttpResponse("No documents found for this license", status=404)

        # Check if required libraries are installed
        try:
            from PyPDF2 import PdfMerger, PdfReader
            from PIL import Image
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.utils import ImageReader
        except ImportError as e:
            return HttpResponse(f"Missing required library: {str(e)}. Please install PyPDF2 and Pillow.", status=500)

        try:
            merger = PdfMerger()

            # Sort documents: TRANSFER LETTER first, then LICENSE COPY, then OTHER
            type_order = {'TRANSFER LETTER': 0, 'LICENSE COPY': 1, 'OTHER': 2}
            sorted_documents = sorted(documents, key=lambda doc: type_order.get(doc.type, 3))

            for doc in sorted_documents:
                if not doc.file:
                    continue

                file_path = doc.file.path
                file_ext = os.path.splitext(file_path)[1].lower()

                if file_ext == '.pdf':
                    # Add PDF directly
                    merger.append(file_path)
                    logger.info(f"Added PDF: {file_path}")
                elif file_ext in ['.doc', '.docx']:
                    # Skip DOCX/DOC files - don't convert them
                    logger.info(f"Skipping DOCX/DOC file: {file_path}")
                    continue
                elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    # Convert image to PDF
                    img = Image.open(file_path)

                    # Convert to RGB if necessary
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    # Create PDF from image using ReportLab
                    img_buffer = io.BytesIO()
                    img_width, img_height = img.size

                    # Use A4 size for PDF
                    pdf_canvas = canvas.Canvas(img_buffer, pagesize=A4)
                    a4_width, a4_height = A4

                    # Calculate scaling to fit image on A4 page
                    scale = min(a4_width / img_width, a4_height / img_height)
                    new_width = img_width * scale
                    new_height = img_height * scale

                    # Center image on page
                    x = (a4_width - new_width) / 2
                    y = (a4_height - new_height) / 2

                    # Use ImageReader for PIL Image object
                    img_reader = ImageReader(img)
                    pdf_canvas.drawImage(img_reader, x, y, width=new_width, height=new_height)
                    pdf_canvas.save()

                    # Rewind buffer and create PdfReader from it
                    img_buffer.seek(0)
                    pdf_reader = PdfReader(img_buffer)
                    merger.append(pdf_reader)
                    logger.info(f"Converted and added image: {file_path}")

            # Write merged PDF to buffer
            output_buffer = io.BytesIO()
            merger.write(output_buffer)
            merger.close()
            output_buffer.seek(0)

            # Return merged PDF
            response = FileResponse(
                output_buffer,
                content_type='application/pdf',
                as_attachment=False,
                filename=f'license_{license_obj.license_number}_documents.pdf'
            )
            return response

        except Exception as e:
            logger.error(f"Error merging documents: {str(e)}", exc_info=True)
            return HttpResponse(f"Error merging documents: {str(e)}", status=500)


# Add license report actions to viewset
LicenseDetailsViewSet = add_license_report_action(LicenseDetailsViewSet)
LicenseDetailsViewSet = add_active_dfia_report_action(LicenseDetailsViewSet)
