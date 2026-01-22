# license/views/license.py
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import LicensePermission
from core.constants import LICENCE_PURCHASE_CHOICES, LICENCE_PURCHASE_CHOICES_ACTIVE, SCHEME_CODE_CHOICES, \
    NOTIFICATION_NORM_CHOICES, UNIT_CHOICES, \
    CURRENCY_CHOICES
from core.views.master_view import MasterViewSet
from license.models import LicenseDetailsModel
from license.serializers import LicenseDetailsSerializer, LicenseExportItemSerializer, LicenseImportItemSerializer, \
    LicenseDocumentSerializer
from license.views.active_dfia_report import add_active_dfia_report_action
from license.views.license_report import add_license_report_action


# Helper function to get default purchase status IDs from codes
def get_default_purchase_status_ids():
    """Convert default purchase status codes to IDs"""
    from core.models import PurchaseStatus
    default_codes = ['GE', 'MI', 'CO']  # GE Purchase, GE Operating, Conversion
    ids = list(PurchaseStatus.objects.filter(code__in=default_codes).values_list('id', flat=True))
    return ','.join(map(str, ids)) if ids else ''

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
            "purchase_status": {"type": "fk", "fk_endpoint": "/masters/purchase-statuses/", "label_field": "label", "filter_params": {"is_active": "true"}},
            "license_date": {"type": "date_range"},
            "license_expiry_date": {"type": "date_range"},
            "balance_cif": {"type": "range"},
            "is_expired": {"type": "exact"},
            "is_null": {"type": "exact"},
        },
        "default_filters": {
            "is_expired": "False",
            "is_null": "False",
        },
        "list_display": [
            "license_number",
            "license_date",
            "license_expiry_date",
            "exporter__name",
            "port__name",
            "purchase_status_label",
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
                "type": "fk",
                "fk_endpoint": "/masters/purchase-statuses/",
                "label_field": "label",
                "filter_params": {"is_active": "true"}
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
    permission_classes = [LicensePermission]
    lookup_value_regex = '[^/]+'  # Allow both numbers and strings

    def list(self, request, *args, **kwargs):
        """Override list to add dynamic purchase_status default to metadata"""
        response = super().list(request, *args, **kwargs)

        # Add purchase_status default to metadata if present
        if isinstance(response.data, dict) and 'default_filters' in response.data:
            default_ps_ids = get_default_purchase_status_ids()
            if default_ps_ids:
                response.data['default_filters']['purchase_status'] = default_ps_ids

        return response

    def get_object(self):
        """
        Override to support lookup by either pk (ID) or license_number.
        """
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}

        # Try to get by primary key first (if it's a number)
        lookup_value = self.kwargs[lookup_url_kwarg]
        try:
            # If lookup value is numeric, try ID first
            if lookup_value.isdigit():
                filter_kwargs = {'pk': int(lookup_value)}
                obj = self.get_queryset().get(**filter_kwargs)
            else:
                # Otherwise lookup by license number
                filter_kwargs = {'license_number': lookup_value}
                obj = self.get_queryset().get(**filter_kwargs)
        except (ValueError, self.queryset.model.DoesNotExist):
            # If ID lookup fails, try license_number
            try:
                filter_kwargs = {'license_number': lookup_value}
                obj = self.get_queryset().get(**filter_kwargs)
            except self.queryset.model.DoesNotExist:
                from django.http import Http404
                raise Http404(f"License with identifier '{lookup_value}' not found")

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)
        return obj

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
        skip_default_filters = self.action in ['retrieve', 'update', 'partial_update', 'destroy', 'nested_items', 'item_usage', 'balance_pdf']

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

        # Call parent method for remaining filters (exclude is_expired and is_null)
        # Create a new QueryDict-like object
        from django.http import QueryDict
        filtered_params = QueryDict(mutable=True)
        for key, value in params.items():
            if key not in ('is_expired', 'is_null'):
                # Handle array format for purchase_status
                if key == 'purchase_status[]':
                    # Frontend sends purchase_status[] for multi-select
                    for val in params.getlist(key):
                        filtered_params.appendlist('purchase_status[]', val)
                else:
                    filtered_params[key] = value

        # Create a copy of filter_config without custom-handled fields
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

    @action(detail=True, methods=['get'], url_path='item-usage')
    def item_usage(self, request, pk=None):
        """
        Get real-time usage details for a specific license item (export or import).
        Shows where the item is used in BOEs and Allotments.

        Query params:
        - item_id: ID of the export or import item
        - type: 'export' or 'import'
        """
        from bill_of_entry.models import RowDetails
        from allotment.models import AllotmentItems

        license_obj = self.get_object()
        item_id = request.query_params.get('item_id')
        item_type = request.query_params.get('type')

        if not item_id or not item_type:
            return Response({'error': 'item_id and type parameters are required'}, status=400)

        boes = []
        allotments = []

        if item_type == 'import':
            # Find BOE usage through RowDetails (sr_number points to LicenseImportItemsModel)
            # Only show transaction_type = 'D' (Debited)
            row_details = RowDetails.objects.filter(
                sr_number_id=item_id,
                transaction_type='D'
            ).select_related(
                'bill_of_entry',
                'bill_of_entry__company',
                'bill_of_entry__port'
            ).values(
                'bill_of_entry__id',
                'bill_of_entry__bill_of_entry_number',
                'bill_of_entry__bill_of_entry_date',
                'bill_of_entry__port__name',
                'bill_of_entry__company__name',
                'qty',
                'cif_fc',
                'cif_inr'
            )

            for detail in row_details:
                boes.append({
                    'id': detail['bill_of_entry__id'],
                    'bill_of_entry_number': detail['bill_of_entry__bill_of_entry_number'],
                    'date': detail['bill_of_entry__bill_of_entry_date'],
                    'port': detail['bill_of_entry__port__name'],
                    'company': detail['bill_of_entry__company__name'],
                    'quantity': float(detail['qty']),
                    'cif_fc': float(detail['cif_fc']),
                    'cif_inr': float(detail['cif_inr'])
                })

            # Find Allotment usage through AllotmentItems
            # Only show allotments where bill_of_entry is NULL (not yet converted to BOE)
            allotment_items = AllotmentItems.objects.filter(
                item_id=item_id,
                allotment__bill_of_entry__isnull=True
            ).select_related(
                'allotment',
                'allotment__company'
            ).values(
                'allotment__id',
                'allotment__invoice',
                'allotment__company__name',
                'qty',
                'cif_fc',
                'cif_inr'
            )

            for item in allotment_items:
                allotments.append({
                    'id': item['allotment__id'],
                    'allotment_number': item['allotment__invoice'] or f"Allotment #{item['allotment__id']}",
                    'company': item['allotment__company__name'],
                    'quantity': float(item['qty']),
                    'cif_fc': float(item['cif_fc']),
                    'cif_inr': float(item['cif_inr'])
                })

        elif item_type == 'export':
            # For export items, check allotments (AllotmentItems might link to export items)
            # This depends on your data model structure
            pass

        return Response({
            'boes': boes,
            'allotments': allotments
        })

    @action(detail=True, methods=['get'], url_path='balance-pdf')
    def balance_pdf(self, request, pk=None):
        """
        Generate PDF report for license balance details with all BOEs and Allotments.
        """
        from django.http import HttpResponse
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        import io
        from datetime import date

        license_obj = self.get_object()

        # Create PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                              rightMargin=10*mm, leftMargin=10*mm,
                              topMargin=12*mm, bottomMargin=12*mm)

        # Container for PDF elements
        elements = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a1a1a'),
            alignment=TA_CENTER,
            spaceAfter=8,
            spaceBefore=3,
            fontName='Helvetica-Bold'
        )

        section_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            spaceBefore=5,
            spaceAfter=3,
            fontName='Helvetica-Bold'
        )

        # Add title
        title = Paragraph(f"<b>License Balance Report</b>", title_style)
        elements.append(title)
        elements.append(Spacer(1, 3))

        # Add license header information split into 2 rows for clarity
        # Check if license has specific document types
        has_tl = license_obj.license_documents.filter(type='TRANSFER LETTER').exists()
        has_copy = license_obj.license_documents.filter(type='LICENSE COPY').exists()

        # Build license number with link if documents exist
        license_number_text = license_obj.license_number or '-'
        if has_tl or has_copy:
            # Get the base URL from request
            base_url = request.build_absolute_uri('/').rstrip('/')
            merge_url = f"{base_url}/api/licenses/{license_obj.id}/merged-documents/"
            license_number_text = f'{license_obj.license_number or "-"} (<link href="{merge_url}" color="blue"><u>Copy</u></link>)'

        header_data = [
            # Row 1: Headers
            ['License Number', 'License Date', 'License Expiry Date', 'Exporter Name', 'Port Name'],
            # Row 1: Values
            [
                Paragraph(license_number_text, styles['Normal']),
                license_obj.license_date.strftime('%d-%m-%Y') if license_obj.license_date else '-',
                license_obj.license_expiry_date.strftime('%d-%m-%Y') if license_obj.license_expiry_date else '-',
                Paragraph(license_obj.exporter.name if license_obj.exporter else '-', styles['Normal']),
                Paragraph(license_obj.port.name if license_obj.port else '-', styles['Normal'])
            ],
            # Row 2: Headers (spanning to match 5 columns)
            ['Purchase Status', 'Balance CIF', 'Get Norm Class', '', 'Latest Transfer'],
            # Row 2: Values
            [
                license_obj.purchase_status or '-',
                f"{float(license_obj.balance_cif or 0):.2f}",
                license_obj.get_norm_class or '-',
                '',
                Paragraph(str(license_obj.latest_transfer) if license_obj.latest_transfer else '-', styles['Normal'])
            ]
        ]

        # Landscape A4 is ~277mm wide, with margins = ~257mm usable width
        # Split into 5 columns: 50mm, 35mm, 40mm, 70mm, 62mm = 257mm
        header_table = Table(header_data, colWidths=[50*mm, 35*mm, 40*mm, 70*mm, 62*mm])
        header_table.setStyle(TableStyle([
            # Row 1 header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            # Row 2 header
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 2), (-1, 2), colors.whitesmoke),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            # Data rows
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#ecf0f1')),
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#ecf0f1')),
            # Common styles
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 2), (-1, 2), 8),
            ('FONTSIZE', (0, 1), (-1, 1), 7.5),
            ('FONTSIZE', (0, 3), (-1, 3), 7.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 5))

        # Export Items Section
        if license_obj.export_license.exists():
            # Section header as table row
            export_section_header = Table([['Export Items']], colWidths=[275*mm])
            export_section_header.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(export_section_header)

            export_data = [['Item', 'Total CIF', 'Balance CIF']]
            for item in license_obj.export_license.all():
                item_desc = item.description or (str(item.norm_class) if item.norm_class else None) or 'None'
                export_data.append([
                    Paragraph(item_desc, styles['Normal']),
                    f"{float(item.cif_fc or item.fob_fc or 0):.2f}",
                    f"{float(license_obj.balance_cif or 0):.2f}"
                ])

            export_table = Table(export_data, colWidths=[185*mm, 45*mm, 45*mm])
            export_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')])
            ]))
            elements.append(export_table)
            elements.append(Spacer(1, 8))

        # Import Items Section with Usage Details
        if license_obj.import_license.exists():
            # Section header as table row
            import_section_header = Table([['Import Items']], colWidths=[275*mm])
            import_section_header.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(import_section_header)

            from bill_of_entry.models import RowDetails
            from allotment.models import AllotmentItems

            for item in license_obj.import_license.all():
                # Main item data
                item_names = ', '.join([i.name for i in item.items.all()]) if item.items.exists() else '-'

                # Get HS code label
                hs_code_display = str(item.hs_code.hs_code if item.hs_code else '-')

                item_data = [[
                    'Sr', 'HS Code', 'Description', 'Item', 'Total Qty',
                    'Allotted', 'Debited', 'Available', 'CIF FC', 'Bal CIF'
                ], [
                    str(item.serial_number or '-'),
                    hs_code_display,
                    Paragraph(str(item.description or '-'), styles['Normal']),
                    Paragraph(item_names, styles['Normal']),
                    f"{float(item.quantity or 0):.2f}",
                    f"{float(item.allotted_quantity or 0):.2f}",
                    f"{float(item.debited_quantity or 0):.2f}",
                    f"{float(item.available_quantity or 0):.2f}",
                    f"{float(item.cif_fc or 0):.2f}",
                    f"{float(item.balance_cif_fc or 0):.2f}"
                ]]

                item_table = Table(item_data, colWidths=[12*mm, 25*mm, 60*mm, 50*mm, 23*mm, 21*mm, 21*mm, 21*mm, 21*mm, 21*mm])
                item_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('FONTSIZE', (0, 1), (-1, -1), 7.5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1'))
                ]))
                elements.append(item_table)
                elements.append(Spacer(1, 3))

                # BOEs
                boes = RowDetails.objects.filter(
                    sr_number_id=item.id,
                    transaction_type='D'
                ).select_related('bill_of_entry', 'bill_of_entry__company', 'bill_of_entry__port')

                if boes.exists():
                    # BOEs header as section row
                    boe_section_header = Table([['BOEs']], colWidths=[275*mm])
                    boe_section_header.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#27ae60')),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#333333')),
                    ]))
                    elements.append(boe_section_header)

                    boe_data = [['BOE Number', 'Date', 'Port', 'Company', 'Qty', 'CIF $', 'CIF INR']]

                    # Calculate totals
                    total_qty = 0
                    total_cif_fc = 0
                    total_cif_inr = 0

                    for detail in boes:
                        total_qty += float(detail.qty or 0)
                        total_cif_fc += float(detail.cif_fc or 0)
                        total_cif_inr += float(detail.cif_inr or 0)

                        boe_data.append([
                            detail.bill_of_entry.bill_of_entry_number,
                            detail.bill_of_entry.bill_of_entry_date.strftime('%d/%m/%Y') if detail.bill_of_entry.bill_of_entry_date else '-',
                            Paragraph(detail.bill_of_entry.port.name if detail.bill_of_entry.port else '-', styles['Normal']),
                            Paragraph(detail.bill_of_entry.company.name if detail.bill_of_entry.company else '-', styles['Normal']),
                            f"{float(detail.qty):.2f}",
                            f"{float(detail.cif_fc):.2f}",
                            f"{float(detail.cif_inr):.2f}"
                        ])

                    # Add total footer row
                    boe_data.append([
                        '', '', '', 'Total',
                        f"{total_qty:.2f}",
                        f"{total_cif_fc:.2f}",
                        f"{total_cif_inr:.2f}"
                    ])

                    boe_table = Table(boe_data, colWidths=[40*mm, 25*mm, 50*mm, 70*mm, 25*mm, 30*mm, 35*mm])
                    boe_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('FONTSIZE', (0, 1), (-1, -2), 7.5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('LEFTPADDING', (0, 0), (-1, -1), 2),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#e8f5e9')]),
                        # Footer row styling
                        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d4edda')),
                        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, -1), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                    ]))
                    elements.append(boe_table)
                    elements.append(Spacer(1, 5))

                # Allotments
                # Only show allotments where bill_of_entry is NULL (not yet converted to BOE)
                allotments = AllotmentItems.objects.filter(
                    item_id=item.id,
                    allotment__bill_of_entry__isnull=True
                ).select_related('allotment', 'allotment__company')

                if allotments.exists():
                    # Allotments header as section row
                    allot_section_header = Table([['Allotments']], colWidths=[275*mm])
                    allot_section_header.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e67e22')),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#333333')),
                    ]))
                    elements.append(allot_section_header)

                    allot_data = [['Company', 'Qty', 'CIF $', 'CIF INR']]

                    # Calculate totals
                    total_allot_qty = 0
                    total_allot_cif_fc = 0
                    total_allot_cif_inr = 0

                    for allot in allotments:
                        total_allot_qty += float(allot.qty or 0)
                        total_allot_cif_fc += float(allot.cif_fc or 0)
                        total_allot_cif_inr += float(allot.cif_inr or 0)

                        allot_data.append([
                            Paragraph(allot.allotment.company.name if allot.allotment.company else '-', styles['Normal']),
                            f"{float(allot.qty):.2f}",
                            f"{float(allot.cif_fc):.2f}",
                            f"{float(allot.cif_inr):.2f}"
                        ])

                    # Add total footer row
                    allot_data.append([
                        'Total',
                        f"{total_allot_qty:.2f}",
                        f"{total_allot_cif_fc:.2f}",
                        f"{total_allot_cif_inr:.2f}"
                    ])

                    allot_table = Table(allot_data, colWidths=[155*mm, 40*mm, 40*mm, 40*mm])
                    allot_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('FONTSIZE', (0, 1), (-1, -2), 7.5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('LEFTPADDING', (0, 0), (-1, -1), 2),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#fef5e7')]),
                        # Footer row styling
                        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fdebd0')),
                        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, -1), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                    ]))
                    elements.append(allot_table)
                    elements.append(Spacer(1, 5))

                # Balance calculation as table footer
                balance = float(item.quantity or 0) - float(item.debited_quantity or 0) - float(item.allotted_quantity or 0)
                balance_table = Table([[f'Balance Quantity: {balance:.2f}']], colWidths=[275*mm])
                balance_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e8e8e8')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#e74c3c')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 5),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                ]))
                elements.append(balance_table)
                elements.append(Spacer(1, 8))

        # Add Notes Section if notes exist
        if license_obj.balance_report_notes:
            notes_header = Table([['Notes']], colWidths=[275*mm])
            notes_header.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(notes_header)

            notes_content = Table([[Paragraph(license_obj.balance_report_notes, styles['Normal'])]], colWidths=[275*mm])
            notes_content.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffacd')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            elements.append(notes_content)

        # Build PDF
        doc.build(elements)

        # Get PDF from buffer
        pdf = buffer.getvalue()
        buffer.close()

        # Create response
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{license_obj.license_number}-balance.pdf"'
        response.write(pdf)

        return response

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
