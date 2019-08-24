import datetime

import xlsxwriter as xlsxwriter
from django.http import HttpResponseRedirect
# Create your views here.
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView
from easy_pdf.views import PDFTemplateResponseMixin
from extra_views import CreateWithInlinesView, UpdateWithInlinesView, InlineFormSetFactory

from core.utils import PagedFilteredTableView
from license.excel import get_license_table
from . import forms, tables, filters
from . import models as license


class LicenseExportItemInline(InlineFormSetFactory):
    model = license.LicenseExportItemModel
    form_class = forms.ExportItemsForm
    factory_kwargs = {
        'extra': 0,
    }


class LicenseImportItemInline(InlineFormSetFactory):
    model = license.LicenseImportItemsModel
    form_class = forms.ImportItemsForm
    factory_kwargs = {
        'extra': 0,
    }


class LicenseDocumentInline(InlineFormSetFactory):
    model = license.LicenseDocumentModel
    form_class = forms.LicenseDocumentForm
    factory_kwargs = {
        'extra': 1,
    }


class LicenseDetailCreateView(CreateWithInlinesView):
    template_name = 'license/add.html'
    model = license.LicenseDetailsModel
    form_class = forms.LicenseDetailsForm
    inlines = [LicenseExportItemInline, LicenseDocumentInline]

    def form_valid(self, form):
        if not form.instance.created_by:
            form.instance.created_by = self.request.user
            form.instance.created_on = datetime.datetime.now()
        form.instance.modified_by = self.request.user
        form.instance.modified_on = datetime.datetime.now()
        return super().form_valid(form)


class LicenseDetailUpdateView(UpdateWithInlinesView):
    template_name = 'license/add.html'
    model = license.LicenseDetailsModel
    form_class = forms.LicenseDetailsForm
    inlines = [LicenseExportItemInline, LicenseDocumentInline]

    def dispatch(self, request, *args, **kwargs):
        # check if there is some video onsite
        license = self.get_object()
        if self.get_object().is_audit:
            return HttpResponseRedirect(reverse('license-detail', kwargs={'pk': license.id}))
        else:
            return super(LicenseDetailUpdateView, self).dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        object = self.model.objects.get(id=self.kwargs.get('pk'))
        return object

    def form_valid(self, form):
        if not form.instance.created_by:
            form.instance.created_by = self.request.user
            form.instance.created_on = datetime.datetime.now()
        form.instance.modified_by = self.request.user
        form.instance.modified_on = datetime.datetime.now()
        return super().form_valid(form)

    def get_inlines(self):
        if not self.object.is_audit:
            if self.object.export_license.all().exists():
                for export_item in self.object.export_license.all():
                    if export_item.norm_class:
                        for import_item in export_item.norm_class.import_norm.all():
                            if not self.object.ledger_date:
                                import_item_obj, bool = license.LicenseImportItemsModel.objects.get_or_create(
                                    license=self.object,
                                    serial_number=import_item.sr_no)
                            else:
                                try:
                                    import_item_obj = license.LicenseImportItemsModel.objects.get(license=self.object,
                                                                                                  serial_number=import_item.sr_no)
                                except:
                                    import_item_obj = None
                            if import_item_obj:
                                if not import_item_obj.item or import_item_obj.item.pk == 141:
                                    import_item_obj.item = import_item.item
                                if not import_item_obj.quantity:
                                    import_item_obj.quantity = round(
                                        export_item.net_quantity * import_item.quantity / export_item.norm_class.export_norm.quantity,
                                        3)
                                if not import_item_obj.hs_code:
                                    import_item_obj.hs_code = import_item.hs_code.first()
                                import_item_obj.save()
                    else:
                        if self.object.import_license.all().first():
                            value = round(
                                self.object.import_license.all().first().quantity / export_item.net_quantity * 100)
            self.inlines = [LicenseExportItemInline, LicenseImportItemInline, LicenseDocumentInline]
        return super(LicenseDetailUpdateView, self).get_inlines()


class LicenseDetailListView(PagedFilteredTableView):
    template_name = 'core/list.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseDetailTable
    filter_class = filters.LicenseDetailFilter
    page_head = 'License List'


class LicenseDetailView(DetailView):
    template_name = 'license/detail.html'
    model = license.LicenseDetailsModel


class PDFLicenseDetailView(PDFTemplateResponseMixin, DetailView):
    template_name = 'license/pdf.html'
    model = license.LicenseDetailsModel

    def get_object(self, queryset=None):
        return self.model.objects.get(license_number=self.kwargs.get('license'))


class ExcelLicenseDetailView(View):

    def get(self, request, license):
        # Create an in-memory output file for the new workbook.
        import io
        from django.http import HttpResponse
        output = io.BytesIO()
        # Even though the final file will be in memory the module uses temp
        # files during assembly for efficiency. To avoid this on servers that
        # don't allow temp files, for example the Google APP Engine, set the
        # 'in_memory' Workbook() constructor option as shown in the docs.
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()
        # Get some data to write to the spreadsheet.
        data = get_license_table(license)
        # Write some test data.
        col_width = 256 * 30
        width_dict = {}
        for row_num, columns in enumerate(data):
            for col_num, cell_data in enumerate(columns):
                if cell_data in ['License Number', 'License Date', 'License Expiry', 'File Number', 'Exporter',
                                 'Notification', 'Scheme Code',
                                 'Port', 'Export Items', 'Import Items', 'Item',
                                 'Total CIF', 'Balance CIF',
                                 "Sr No", 'HS Code', 'Quantity', 'Balance Quantity', 'CIF FC', 'Balance CIF FC']:
                    cell_format = workbook.add_format({'bold': True, 'text_wrap': True})
                    worksheet.write(row_num, col_num, cell_data, cell_format)
                    worksheet.set_column(row_num, col_num, 15)
                else:
                    cell_format = workbook.add_format({'text_wrap': True})
                    worksheet.write(row_num, col_num, cell_data, cell_format)
                    width_dict[col_num] = len(str(cell_data))
                    worksheet.set_column(row_num, col_num, 15)
        # Close the workbook before sending the data.
        workbook.close()
        # Rewind the buffer.
        output.seek(0)
        # Set up the Http response.
        filename = license + '.xlsx'
        response = HttpResponse(
            output,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=%s' % filename
        return response


class LicenseVerifyView(View):

    def get(self, requests, pk):
        license_obj = license.LicenseDetailsModel.objects.get(id=pk)
        license_obj.is_audit = True
        license_obj.save()
        return HttpResponseRedirect(reverse('license-detail', kwargs={'pk': license_obj.id}))


class LicenseDetailLedgerView(DetailView):
    template_name = 'license/license_details.html'
    model = license.LicenseDetailsModel
    context_object_name = 'license'
