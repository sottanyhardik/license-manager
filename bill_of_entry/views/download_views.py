from decimal import Decimal
import datetime

from .common import FilterView, PDFTemplateResponseMixin, tables, filters, bill_of_entry


class DownloadPendingBillView(PDFTemplateResponseMixin, FilterView):
    table_class = tables.BillOfEntryTable
    filterset_class = filters.BillOfEntryFilter
    paginate_by = 500
    template_name = 'bill_of_entry/download.html'
    model = bill_of_entry.BillOfEntryModel
    ordering = ('company', 'product_name', 'bill_of_entry_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.filterset_class(self.request.GET, queryset=self.get_queryset()).qs
        total_list = [Decimal(data.get_total_inr) for data in queryset]
        context['total_cif'] = sum(total_list)
        context['today'] = datetime.datetime.now().date
        return context


class DownloadPortView(PDFTemplateResponseMixin, FilterView):
    table_class = tables.BillOfEntryTable
    filterset_class = filters.BillOfEntryFilter
    paginate_by = 5000
    template_name = 'bill_of_entry/download_port.html'
    model = bill_of_entry.BillOfEntryModel
    ordering = ('company', 'product_name', 'bill_of_entry_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.filterset_class(self.request.GET, queryset=self.get_queryset()).qs
        total_list = [Decimal(data.get_total_inr) for data in queryset]
        context['total_cif'] = sum(total_list)
        context['today'] = datetime.datetime.now().date
        return context
