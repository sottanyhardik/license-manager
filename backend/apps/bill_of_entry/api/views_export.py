# bill_of_entry/api/views_export.py -- thin HTTP adapter; export building lives in
# apps/bill_of_entry/services/exporters/.
from rest_framework.decorators import action

from apps.bill_of_entry.services.exporters import (
    EXPORT_FORMAT_PDF,
    EXPORT_FORMAT_XLSX,
    SUPPORTED_EXPORT_FORMATS,
    build_export_queryset,
    export_grouped_pdf,
    export_grouped_xlsx,
    export_port_xlsx,
    group_boe,
)
from apps.bill_of_entry.services.exporters.common import _decimal_or_default, _text_response  # noqa: F401


def add_grouped_export_action(viewset_class):
    """
    Decorator to add grouped export functionality to BillOfEntryViewSet
    """

    @action(detail=False, methods=['get'], url_path='export')
    def export_bill_of_entries(self, request):
        """
        Export bill of entries grouped by company.
        URL: /api/bill-of-entries/export/?_export=pdf

        Query params:
            - _export: 'pdf', 'xlsx' or 'port_xlsx' (default: pdf)
            - company: filter by company ID
            - bill_of_entry_date_after: filter by date
            - bill_of_entry_date_before: filter by date
        """
        export_format = (request.query_params.get('_export') or EXPORT_FORMAT_PDF).strip().lower()
        if export_format not in SUPPORTED_EXPORT_FORMATS:
            return _text_response("Invalid export format. Use 'pdf', 'xlsx', or 'port_xlsx'.", 400)

        queryset = build_export_queryset(self.filter_queryset(self.get_queryset()))

        if export_format == EXPORT_FORMAT_PDF:
            return self._export_grouped_pdf(queryset)
        elif export_format == EXPORT_FORMAT_XLSX:
            return self._export_grouped_xlsx(queryset)
        return self._export_port_xlsx(queryset)

    # Kept as viewset methods (same names) for backward compatibility.
    viewset_class.export_bill_of_entries = export_bill_of_entries
    viewset_class._export_grouped_pdf = lambda self, queryset: export_grouped_pdf(queryset)
    viewset_class._export_grouped_xlsx = lambda self, queryset: export_grouped_xlsx(queryset)
    viewset_class._export_port_xlsx = lambda self, queryset: export_port_xlsx(queryset)
    viewset_class._group_boe = lambda self, queryset: group_boe(queryset)

    return viewset_class
