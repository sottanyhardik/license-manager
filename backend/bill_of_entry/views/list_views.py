# from .common import (
#     FilterView, ExportMixin, SingleTableView, CreateView,
#     bill_of_entry, forms, tables, filters
# )
#
# class BillOfEntryView(FilterView, ExportMixin, SingleTableView):
#     template_name = 'bill_of_entry/list.html'
#     model = bill_of_entry.BillOfEntryModel
#     table_class = tables.BillOfEntryTable
#     filterset_class = filters.BillOfEntryFilter
#     paginate_by = 50
#     ordering = '-bill_of_entry_date'
#
#
# class BillOfEntryAjaxListView(FilterView):
#     template_name = 'bill_of_entry/ajax_list.html'
#     model = bill_of_entry.BillOfEntryModel
#     table_class = tables.BillOfEntryTable
#     filterset_class = filters.BillOfEntryFilter
#     paginate_by = 50
#     ordering = '-bill_of_entry_date'
#
#
# class BillOfEntryCreateView(CreateView):
#     template_name = 'bill_of_entry/add.html'
#     model = bill_of_entry.BillOfEntryModel
#     form_class = forms.BillOfEntryForm
#
#     def get_context_data(self, **kwargs):
#         context = super(BillOfEntryCreateView, self).get_context_data(**kwargs)
#         context['inline'] = True
#         return context
