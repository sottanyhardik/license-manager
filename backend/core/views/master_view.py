from __future__ import annotations

import math
from typing import Any, Dict, Optional, Type
from datetime import datetime

from django.db import models
from django.db.models import F
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.request import Request
from rest_framework.response import Response

try:
    import openpyxl
    from openpyxl.styles import Font, Alignment
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class StandardPagination(PageNumberPagination):
    """Reusable pagination for all master data endpoints."""
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


class MasterViewSet(viewsets.ModelViewSet):
    """
    🔹 Generic Reusable Master CRUD ViewSet

    Provides:
        - Full CRUD
        - Search, Filter, Ordering, Pagination
        - list_display / form_fields driven from backend config
        - Annotated FK display support (e.g., head_norm__name)
        - Exposes 'nested_field_defs' and 'field_meta' in list() and OPTIONS metadata
    """

    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]  # Removed DjangoFilterBackend
    ordering_fields = "__all__"

    # Defaults (overwritten by factory)
    search_fields: list[str] = ["id"]
    filterset_fields: list[str] = []
    filter_config: Dict[str, Any] = {}  # Advanced filter configuration
    list_display: list[str] = []
    form_fields: list[str] = []
    nested_field_defs: Dict[str, Any] = {}
    nested_list_display: Dict[str, Any] = {}
    field_meta: Dict[str, Any] = {}
    model_name: Optional[str] = None
    serializer_class = None
    queryset = None

    def perform_create(self, serializer):
        """Attach created_by when possible."""
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            serializer.save(created_by=user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        """Attach modified_by when possible."""
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            serializer.save(modified_by=user)
        else:
            serializer.save()

    # --- Factory Method ---
    @classmethod
    def create_viewset(cls, model: Type[models.Model], serializer, config: Optional[dict] | list = None):
        """
        Factory to dynamically generate CRUD ViewSet classes.

        Args:
            model: Django model class
            serializer: DRF serializer class
            config: dict or list controlling fields and behavior
                - search: list of searchable fields
                - filter: list of filterable fields OR dict with advanced filter config
                - filter_config: dict mapping field names to filter types:
                    {
                        "field_name": {"type": "icontains"},
                        "date_field": {"type": "date_range"},
                        "price_field": {"type": "range", "min_field": "price_min", "max_field": "price_max"},
                        "exact_field": {"type": "exact"}
                    }
                - list_display: visible table columns (can include __ lookups)
                - form_fields: editable fields in form
                - ordering: list of sortable fields
                - nested_field_defs: dict describing nested export/import fields (optional)
                - field_meta: dict describing special UI metadata for fields (optional)
        """
        # Normalize config
        if isinstance(config, list):
            config = {"search": config}
        elif not isinstance(config, dict):
            config = {}

        # Determine safe fields for filters (exclude file/image fields)
        safe_fields = [
            f.name
            for f in model._meta.get_fields()
            if not isinstance(f, (models.FileField, models.ImageField))
        ]

        # Process filter configuration
        filter_fields = config.get("filter", safe_fields)
        filter_config = config.get("filter_config", {})

        # If filter is a dict, it's the filter_config
        if isinstance(filter_fields, dict):
            filter_config = filter_fields
            filter_fields = list(filter_config.keys())

        # Attributes for the generated class
        attrs = {
            "queryset": model.objects.all(),
            "serializer_class": serializer,
            "search_fields": config.get("search", ["id"]),
            "filterset_fields": filter_fields,
            "filter_config": filter_config,
            "list_display": config.get("list_display", safe_fields),
            "form_fields": config.get("form_fields", safe_fields),
            "ordering_fields": config.get("ordering", safe_fields),
            "model_name": model.__name__,
            "nested_field_defs": config.get("nested_field_defs", {}),
            "nested_list_display": config.get("nested_list_display", {}),
            "field_meta": config.get("field_meta", {}),
            "default_filters": config.get("default_filters", {}),
        }

        # --- Dynamically create the subclass ---
        class _ViewSet(cls):  # type: ignore[misc]
            # set attributes on the subclass
            queryset = attrs["queryset"]
            serializer_class = attrs["serializer_class"]
            search_fields = attrs["search_fields"]
            filterset_fields = attrs["filterset_fields"]
            filter_config = attrs["filter_config"]
            list_display = attrs["list_display"]
            form_fields = attrs["form_fields"]
            ordering_fields = attrs["ordering_fields"]
            nested_field_defs = attrs["nested_field_defs"]
            nested_list_display = attrs["nested_list_display"]
            field_meta = attrs["field_meta"]
            model_name = attrs["model_name"]
            default_filters = attrs["default_filters"]

            def get_queryset(self):
                """
                Annotate queryset with FK display lookups and apply advanced filters.
                """
                qs = super().get_queryset()

                # Annotate FK lookups
                annotations: Dict[str, F] = {}
                for field in getattr(self, "list_display", []):
                    if "__" in field:
                        alias = field.replace("__", "_")
                        annotations[alias] = F(field)
                if annotations:
                    qs = qs.annotate(**annotations)

                # Apply advanced filters (always apply, even if filter_config is empty)
                filter_config = getattr(self, "filter_config", {})
                request = getattr(self, "request", None)

                if request:
                    qs = self.apply_advanced_filters(qs, request.query_params, filter_config)

                return qs

            def apply_advanced_filters(self, qs, params, filter_config):
                """Apply advanced filters based on filter_config."""
                from django.db.models import Q
                from django.db import models as dj_models

                # Get model fields
                model = qs.model
                model_fields = {f.name: f for f in model._meta.get_fields()}

                # Track processed fields to avoid duplicates
                processed_fields = set()

                # First, process fields defined in filter_config
                for field_name, config in filter_config.items():
                    processed_fields.add(field_name)
                    filter_type = config.get("type", "icontains")  # Default to icontains for text fields

                    if filter_type == "icontains":
                        # Case-insensitive contains
                        value = params.get(field_name)
                        if value:
                            qs = qs.filter(**{f"{field_name}__icontains": value})

                    elif filter_type == "date_range":
                        # Date range filter
                        processed_fields.add(f"{field_name}_from")
                        processed_fields.add(f"{field_name}_to")
                        date_from = params.get(f"{field_name}_from")
                        date_to = params.get(f"{field_name}_to")
                        if date_from:
                            qs = qs.filter(**{f"{field_name}__gte": date_from})
                        if date_to:
                            qs = qs.filter(**{f"{field_name}__lte": date_to})

                    elif filter_type == "range":
                        # Numeric range filter
                        min_field = config.get("min_field", f"{field_name}_min")
                        max_field = config.get("max_field", f"{field_name}_max")
                        processed_fields.add(min_field)
                        processed_fields.add(max_field)
                        min_value = params.get(min_field)
                        max_value = params.get(max_field)
                        if min_value:
                            qs = qs.filter(**{f"{field_name}__gte": min_value})
                        if max_value:
                            qs = qs.filter(**{f"{field_name}__lte": max_value})

                    elif filter_type == "exact":
                        # Exact match (with boolean conversion)
                        value = params.get(field_name)
                        if value is not None and value != "":
                            # Skip filtering if value is "all" (show all records)
                            if isinstance(value, str) and value.lower() == "all":
                                continue

                            # Convert string boolean values to actual boolean
                            if isinstance(value, str):
                                if value.lower() in ("true", "1", "yes"):
                                    value = True
                                elif value.lower() in ("false", "0", "no"):
                                    value = False

                            # Special handling for is_boe field - filter by bill_of_entry relationship instead of database field
                            if field_name == "is_boe":
                                if value:
                                    # is_boe=True: has bill of entry
                                    qs = qs.filter(bill_of_entry__isnull=False).distinct()
                                else:
                                    # is_boe=False: no bill of entry
                                    qs = qs.filter(bill_of_entry__isnull=True)
                            else:
                                # Apply filter even if value is False (important for boolean fields)
                                qs = qs.filter(**{field_name: value})

                    elif filter_type == "in":
                        # IN filter (comma-separated values)
                        value = params.get(field_name)
                        if value:
                            values = [v.strip() for v in value.split(",")]
                            qs = qs.filter(**{f"{field_name}__in": values})

                    elif filter_type == "fk":
                        # Foreign key filter - supports multi-select (comma-separated IDs)
                        value = params.get(field_name)
                        if value:
                            # Check if value contains comma (multi-select)
                            if ',' in str(value):
                                values = [v.strip() for v in str(value).split(",") if v.strip()]
                                qs = qs.filter(**{f"{field_name}__in": values})
                            else:
                                # Single value exact match
                                qs = qs.filter(**{field_name: value})

                    elif filter_type == "choice":
                        # Choice field filter - supports multi-select (comma-separated values)
                        value = params.get(field_name)
                        if value:
                            # Check if value contains comma (multi-select)
                            if ',' in str(value):
                                values = [v.strip() for v in str(value).split(",") if v.strip()]
                                qs = qs.filter(**{f"{field_name}__in": values})
                            else:
                                # Single value exact match
                                qs = qs.filter(**{field_name: value})

                    elif filter_type == "exclude_fk":
                        # Exclude foreign key filter - supports multi-select (comma-separated IDs)
                        value = params.get(field_name)
                        if value:
                            # Get the actual field name to filter on
                            filter_field = config.get("filter_field", field_name.replace("exclude_", ""))
                            # Check if value contains comma (multi-select)
                            if ',' in str(value):
                                values = [v.strip() for v in str(value).split(",") if v.strip()]
                                qs = qs.exclude(**{f"{filter_field}__in": values})
                            else:
                                # Single value exact match
                                qs = qs.exclude(**{filter_field: value})

                # Now, process any remaining query parameters not in filter_config
                # Apply icontains for text fields by default
                ignore_params = {'page', 'page_size', 'ordering', 'search', 'export'}

                for param_name, param_value in params.items():
                    if param_name in processed_fields or param_name in ignore_params:
                        continue

                    if not param_value:
                        continue

                    # Check if this is a valid model field
                    if param_name in model_fields:
                        field = model_fields[param_name]

                        # Skip reverse relations (ManyToOneRel, ManyToManyRel, etc.)
                        if isinstance(field, (dj_models.ManyToOneRel, dj_models.ManyToManyRel,
                                             dj_models.OneToOneRel)):
                            continue

                        # Apply icontains for CharField and TextField
                        if isinstance(field, (dj_models.CharField, dj_models.TextField)):
                            try:
                                # Check for comma-separated values (multi-select for text fields)
                                if ',' in str(param_value):
                                    values = [v.strip() for v in str(param_value).split(",") if v.strip()]
                                    # Use __in for multi-select text values
                                    qs = qs.filter(**{f"{param_name}__in": values})
                                else:
                                    qs = qs.filter(**{f"{param_name}__icontains": param_value})
                            except Exception:
                                # Skip if filter fails
                                pass
                        # Apply filter for other field types
                        elif isinstance(field, (dj_models.ForeignKey, dj_models.IntegerField,
                                               dj_models.DecimalField, dj_models.BooleanField,
                                               dj_models.DateField, dj_models.DateTimeField)):
                            try:
                                # ALWAYS support multi-select (comma-separated values) for ForeignKey and numeric fields
                                if ',' in str(param_value):
                                    values = [v.strip() for v in str(param_value).split(",") if v.strip()]
                                    qs = qs.filter(**{f"{param_name}__in": values})
                                else:
                                    # Single value exact match
                                    qs = qs.filter(**{param_name: param_value})
                            except Exception:
                                # Skip if filter fails
                                pass

                return qs

            def list(self, request: Request, *args, **kwargs) -> Response:
                """
                Return list of objects with frontend metadata and pagination details:
                  - total_pages
                  - current_page
                  - page_size
                  - has_next
                  - has_previous
                Keeps original 'count', 'next', 'previous' keys when paginated.
                """
                # Use parent's list implementation (handles filtering, pagination, serialization)
                response = super().list(request, *args, **kwargs)

                # Extract results and pagination info
                if isinstance(response.data, dict) and "results" in response.data:
                    results = response.data.get("results", [])
                    count = response.data.get("count", None)
                    next_link = response.data.get("next", None)
                    previous_link = response.data.get("previous", None)
                else:
                    results = response.data
                    count = None
                    next_link = None
                    previous_link = None

                # Default pagination metadata
                total_pages = 1
                current_page = 1
                page_size = None
                has_next = False
                has_previous = False

                paginator = getattr(self, "paginator", None)
                if count is not None:
                    # Determine page_size
                    try:
                        if paginator is not None:
                            page_size = paginator.get_page_size(request)
                    except Exception:
                        page_size = None

                    if not page_size:
                        page_size = getattr(self.pagination_class, "page_size", 1) or 1

                    # Compute pages
                    try:
                        total_pages = int(math.ceil(float(count) / float(page_size))) if page_size and int(
                            page_size) > 0 else 1
                    except Exception:
                        total_pages = 1

                    # current page from query params (PageNumberPagination param is 'page')
                    try:
                        current_page = int(request.query_params.get("page", 1))
                        if current_page < 1:
                            current_page = 1
                        if current_page > total_pages:
                            current_page = total_pages
                    except Exception:
                        current_page = 1

                    # has_next/has_previous derived from next/previous links if present
                    has_next = bool(next_link)
                    has_previous = bool(previous_link)

                # Build final payload
                data: Dict[str, Any] = {
                    "results": results,
                    "list_display": getattr(self, "list_display", []),
                    "form_fields": getattr(self, "form_fields", []),
                    "search_fields": getattr(self, "search_fields", []),
                    "filter_fields": getattr(self, "filterset_fields", []),
                    "filter_config": getattr(self, "filter_config", {}),
                    "ordering_fields": getattr(self, "ordering_fields", []),
                    "nested_field_defs": getattr(self, "nested_field_defs", {}),
                    "nested_list_display": getattr(self, "nested_list_display", {}),
                    "field_meta": getattr(self, "field_meta", {}),
                    "default_filters": getattr(self, "default_filters", {}),

                    # Pagination metadata
                    "total_pages": total_pages,
                    "current_page": current_page,
                    "page_size": page_size,
                    "has_next": has_next,
                    "has_previous": has_previous,
                }

                # Preserve count/next/previous if present in original paginated response
                if isinstance(response.data, dict):
                    for key in ("count", "next", "previous"):
                        if key in response.data:
                            data[key] = response.data[key]

                # Replace response data
                response.data = data
                return response

            def options(self, request: Request, *args, **kwargs) -> Response:
                """
                Extend OPTIONS response with extra metadata including nested_field_defs and field_meta
                """
                response = super().options(request, *args, **kwargs)
                try:
                    if isinstance(response.data, dict):
                        extra = {
                            "list_display": getattr(self, "list_display", []),
                            "form_fields": getattr(self, "form_fields", []),
                            "search_fields": getattr(self, "search_fields", []),
                            "filter_fields": getattr(self, "filterset_fields", []),
                            "filter_config": getattr(self, "filter_config", {}),
                            "ordering_fields": getattr(self, "ordering_fields", []),
                            "model_name": getattr(self, "model_name", None),
                            "nested_field_defs": getattr(self, "nested_field_defs", {}),
                            "nested_list_display": getattr(self, "nested_list_display", {}),
                            "field_meta": getattr(self, "field_meta", {}),
                        }
                        response.data.update(extra)
                except Exception:
                    # Never raise from OPTIONS metadata enrichment
                    pass
                return response

            @action(detail=False, methods=['get'], url_path='export')
            def export_data(self, request: Request) -> HttpResponse:
                """
                Export filtered queryset to XLSX or PDF format.
                Query params:
                    - export: 'xlsx' or 'pdf' (default: 'xlsx')
                    - All filter params from the list view
                """
                export_format = request.query_params.get('export', 'xlsx').lower()

                # Get filtered queryset (applies all filters, search, ordering)
                queryset = self.filter_queryset(self.get_queryset())

                # Get display columns
                columns = getattr(self, "list_display", [])
                model_name = getattr(self, "model_name", "Export")

                if export_format == 'xlsx':
                    return self._export_xlsx(queryset, columns, model_name)
                elif export_format == 'pdf':
                    return self._export_pdf(queryset, columns, model_name)
                else:
                    return HttpResponse("Invalid export format. Use 'xlsx' or 'pdf'.", status=400)

            def _export_xlsx(self, queryset, columns, model_name):
                """Export to Excel format"""
                if not OPENPYXL_AVAILABLE:
                    return HttpResponse(
                        "Excel export not available. Install openpyxl: pip install openpyxl",
                        status=500
                    )

                # Create workbook
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = model_name[:31]  # Excel sheet name limit

                # Header row
                headers = [col.replace("_", " ").title() for col in columns]
                ws.append(headers)

                # Style header
                for cell in ws[1]:
                    cell.font = Font(bold=True)
                    cell.alignment = Alignment(horizontal='center')

                # Data rows
                for obj in queryset:
                    row = []
                    for col in columns:
                        if "__" in col:
                            # Try annotated field first
                            alias = col.replace("__", "_")
                            value = getattr(obj, alias, None)

                            # If annotated field doesn't exist, traverse the relation
                            if value is None:
                                parts = col.split("__")
                                value = obj
                                for part in parts:
                                    if value is None:
                                        break
                                    value = getattr(value, part, None)
                        else:
                            value = getattr(obj, col, None)

                        # Format value
                        if value is None:
                            row.append("")
                        elif hasattr(value, 'strftime'):  # datetime/date
                            row.append(value.strftime('%Y-%m-%d %H:%M:%S') if hasattr(value, 'hour') else value.strftime('%Y-%m-%d'))
                        else:
                            row.append(str(value))

                    ws.append(row)

                # Auto-size columns
                for column in ws.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    ws.column_dimensions[column_letter].width = adjusted_width

                # Generate response
                response = HttpResponse(
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                filename = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                wb.save(response)

                return response

            def _export_pdf(self, queryset, columns, model_name):
                """Export to PDF format"""
                if not REPORTLAB_AVAILABLE:
                    return HttpResponse(
                        "PDF export not available. Install reportlab: pip install reportlab",
                        status=500
                    )

                # Create response
                response = HttpResponse(content_type='application/pdf')
                filename = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'

                # Create PDF
                doc = SimpleDocTemplate(response, pagesize=A4)
                elements = []
                styles = getSampleStyleSheet()

                # Title
                title = Paragraph(f"<b>{model_name} Report</b>", styles['Title'])
                elements.append(title)
                elements.append(Spacer(1, 0.3 * inch))

                # Prepare table data
                headers = [col.replace("_", " ").title() for col in columns]
                data = [headers]

                for obj in queryset:
                    row = []
                    for col in columns:
                        if "__" in col:
                            alias = col.replace("__", "_")
                            value = getattr(obj, alias, None)
                        else:
                            value = getattr(obj, col, None)

                        # Format value
                        if value is None:
                            row.append("")
                        elif hasattr(value, 'strftime'):
                            row.append(value.strftime('%Y-%m-%d %H:%M') if hasattr(value, 'hour') else value.strftime('%Y-%m-%d'))
                        else:
                            # Truncate long values
                            str_value = str(value)
                            row.append(str_value[:50] + "..." if len(str_value) > 50 else str_value)

                    data.append(row)

                # Create table
                # Calculate column widths dynamically based on page width
                available_width = A4[0] - 2 * inch
                col_width = available_width / len(columns) if columns else 1 * inch
                col_widths = [col_width] * len(columns)

                table = Table(data, colWidths=col_widths)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))

                elements.append(table)

                # Add footer with date
                elements.append(Spacer(1, 0.3 * inch))
                footer = Paragraph(
                    f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    styles['Normal']
                )
                elements.append(footer)

                # Build PDF
                doc.build(elements)

                return response

        # Give the generated class a helpful name
        _ViewSet.__name__ = f"{model.__name__}ViewSet"

        # Attach attrs to generated class for easy inspection (alternatively already set above)
        for k, v in attrs.items():
            setattr(_ViewSet, k, v)

        return _ViewSet
