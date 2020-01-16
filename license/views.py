import datetime

import xlsxwriter as xlsxwriter
from django.http import HttpResponseRedirect
# Create your views here.
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView
from easy_pdf.views import PDFTemplateResponseMixin
from extra_views import CreateWithInlinesView, UpdateWithInlinesView, InlineFormSetFactory

from core.utils import PagedFilteredTableView
from license.excel import get_license_table
from license.helper import round_down
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
        return super(LicenseDetailCreateView, self).form_valid(form)


class LicenseDetailUpdateView(UpdateWithInlinesView):
    template_name = 'license/add.html'
    model = license.LicenseDetailsModel
    form_class = forms.LicenseDetailsForm
    inlines = [LicenseExportItemInline, LicenseDocumentInline]

    def dispatch(self, request, *args, **kwargs):
        # check if there is some video onsite
        license = self.get_object()
        if self.get_object().is_audit:
            return HttpResponseRedirect(reverse('license-detail', kwargs={'license': license.license_number}))
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
        return super(LicenseDetailUpdateView, self).form_valid(form)

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
                                    import_item_obj.quantity = round_down(
                                        export_item.net_quantity * import_item.quantity / export_item.norm_class.export_norm.quantity,
                                        3)
                                if import_item_obj.old_quantity == 0:
                                    import_item_obj.old_quantity = round_down(
                                        export_item.old_quantity * import_item.quantity / export_item.norm_class.export_norm.quantity,
                                        0)
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

    def get_object(self, queryset=None):
        return self.model.objects.get(license_number=self.kwargs.get('license'))


class PDFLicenseDetailView(PDFTemplateResponseMixin, DetailView):
    template_name = 'license/pdf.html'
    model = license.LicenseDetailsModel

    def get_object(self, queryset=None):
        return self.model.objects.get(license_number=self.kwargs.get('license'))


class PDFAmendmentLicenseDetailView(PDFTemplateResponseMixin, DetailView):
    template_name = 'license/pdf_amend.html'
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
        return HttpResponseRedirect(reverse('license-detail', kwargs={'license': license_obj.license_number}))


class LicenseDetailLedgerView(DetailView):
    template_name = 'license/license_details.html'
    model = license.LicenseDetailsModel
    context_object_name = 'license'


class PDFLedgerLicenseDetailView(PDFTemplateResponseMixin, DetailView):
    template_name = 'license/pdf_ledger.html'
    model = license.LicenseDetailsModel

    def get_object(self, queryset=None):
        return self.model.objects.get(license_number=self.kwargs.get('license'))


class PDFConsolidatedView(PDFTemplateResponseMixin, ListView):
    template_name = 'license/consolidated.html'
    model = license.LicenseDetailsModel
    context_object_name = 'license_list'

    def get_queryset(self):
        expirty_limit = datetime.datetime.today() - datetime.timedelta(days=30)
        from license.models import LicenseDetailsModel
        notification = self.kwargs.get('notification')
        if notification == '19':
            from license.models import N2015
            notification_number = N2015
        else:
            from license.models import N2009
            notification_number = N2009
        query = LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class=self.kwargs.get('norm'),
                                                   notification_number=notification_number, is_null=False).filter(
            license_expiry_date__gt=expirty_limit).order_by('license_expiry_date')
        return query


class BiscuitsReportView(PagedFilteredTableView):
    template_name = 'core/list.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    page_head = 'License Report List'

    def get_queryset(self, **kwargs):
        norms = self.kwargs.get('norms')
        expirty_limit = datetime.datetime.today() - datetime.timedelta(days=30)
        self.queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                   is_self=True).order_by('license_expiry_date')
        return super(BiscuitsReportView, self).get_queryset()


class ConfectineryReportView(PagedFilteredTableView):
    template_name = 'core/list.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseConfectineryReportTable
    filter_class = filters.LicenseReportFilter
    page_head = 'License Report List'

    def get_queryset(self, **kwargs):
        self.queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E1',
                                                                   is_self=True).order_by('license_expiry_date')
        return super(ConfectineryReportView, self).get_queryset()


class PDFCReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFCReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseBiscuitReportTable, LicenseConfectineryReportTable
        from license.models import N2015
        from django.db.models import Q
        try:
            expirty_limit = datetime.datetime.today()
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gt=expirty_limit,
                                                                           is_self=True).order_by('license_expiry_date')
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gt=expirty_limit,
                is_self=True).order_by('license_expiry_date')

            table = LicenseBiscuitReportTable(biscuits_queryset.filter(notification_number=N2015).filter(
                Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani') | Q(
                    exporter__name__icontains='vanila')).exclude(export_license__old_quantity=0).distinct())
            tables.append({'label': 'RAMA RANI VANNILA Biscuits', 'table': table})
            table = LicenseConfectineryReportTable(confectionery_queryset.filter(notification_number=N2015).filter(
                Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani') | Q(
                    exporter__name__icontains='vanila')).exclude(export_license__old_quantity=0).distinct())
            tables.append({'label': 'RAMA RANI VANNILA Confectinery', 'table': table})
            table = LicenseBiscuitReportTable(
                biscuits_queryset.filter(notification_number=N2015).filter(exporter__name__icontains='parle').exclude(
                    export_license__old_quantity=0).distinct())
            tables.append({'label': 'Parle Biscuits', 'table': table})

            context['tables'] = tables
        except:
            pass
        return context


class PDFNewBiscuitsReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFNewBiscuitsReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseBiscuitReportTable
        from license.models import N2015
        from django.db.models import Q
        try:
            expirty_limit = datetime.datetime.today()
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gt=expirty_limit,
                                                                           is_self=True).order_by('license_expiry_date')

            table = LicenseBiscuitReportTable(
                biscuits_queryset.filter(export_license__old_quantity=0, notification_number=N2015).filter(
                    Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani') | Q(
                        exporter__name__icontains='vanila')).distinct())
            tables.append({'label': 'RAMA RANI Other Biscuits', 'table': table})

            table = LicenseBiscuitReportTable(
                biscuits_queryset.filter(export_license__old_quantity=0, notification_number=N2015).filter(
                    Q(exporter__name__icontains='parle')).distinct())
            tables.append({'label': 'Parle Other Biscuits', 'table': table})

            context['tables'] = tables
        except:
            pass
        return context


class PDFNewBiscuitsOtherReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFNewBiscuitsOtherReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseBiscuitReportTable
        from license.models import N2015
        from django.db.models import Q
        try:
            expirty_limit = datetime.datetime.today()
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gt=expirty_limit,
                                                                           is_self=True).order_by('license_expiry_date')

            table = LicenseBiscuitReportTable(
                biscuits_queryset.filter(export_license__old_quantity=0, notification_number=N2015).exclude(
                    Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani') | Q(
                        exporter__name__icontains='vanila') | Q(exporter__name__icontains='parle')).distinct())
            tables.append({'label': 'Biscuits Remaning 019/2015 Notification', 'table': table})

            context['tables'] = tables
        except:
            pass
        return context


class PDFNewConfectioneryReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFNewConfectioneryReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseConfectineryReportTable
        from license.models import N2015
        from django.db.models import Q
        try:
            expirty_limit = datetime.datetime.today()
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gt=expirty_limit,
                is_self=True).order_by('license_expiry_date')

            table = LicenseConfectineryReportTable(
                confectionery_queryset.filter(export_license__old_quantity=0, notification_number=N2015).filter(
                    Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani') | Q(
                        exporter__name__icontains='vanila')).distinct())
            tables.append({'label': 'RAMA RANI VANNILA Other Confectinery', 'table': table})

            table = LicenseConfectineryReportTable(
                confectionery_queryset.filter(export_license__old_quantity=0, notification_number=N2015).filter(
                    Q(exporter__name__icontains='parle')).distinct())
            tables.append({'label': 'Parle Other Confectinery', 'table': table})

            context['tables'] = tables
        except:
            pass
        return context


class PDFNewConfectioneryOtherReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFNewConfectioneryOtherReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseConfectineryReportTable
        from license.models import N2015
        from django.db.models import Q
        try:
            expirty_limit = datetime.datetime.today()
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gt=expirty_limit,
                is_self=True).order_by('license_expiry_date')

            table = LicenseConfectineryReportTable(
                confectionery_queryset.filter(export_license__old_quantity=0, notification_number=N2015).exclude(
                    Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani') | Q(
                        exporter__name__icontains='vanila') | Q(exporter__name__icontains='parle')).distinct())
            tables.append({'label': 'Confectinery Remaning 019/2015 Notification', 'table': table})
            context['tables'] = tables
        except:
            pass
        return context


class PDFOldAllReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFOldAllReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseBiscuitReportTable, LicenseConfectineryReportTable
        from license.models import N2009
        try:
            expirty_limit = datetime.datetime.today()
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gt=expirty_limit,
                                                                           is_self=True).order_by('license_expiry_date')

            table = LicenseBiscuitReportTable(biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Biscuits 098/2019 Notification', 'table': table})
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gt=expirty_limit,
                is_self=True).order_by('license_expiry_date')
            table = LicenseConfectineryReportTable(confectionery_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Confectinery 098/2019 Notification', 'table': table})

            context['tables'] = tables
        except:
            pass
        return context


class BiscuitsAmmendmentView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/pdf_amend.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(BiscuitsAmmendmentView, self).get_context_data()
        tables = []
        from license.tables import LicenseBiscuitReportTable, LicenseConfectineryReportTable
        from license.models import N2009
        try:
            expirty_limit = datetime.datetime.today()
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gt=expirty_limit,
                                                                           is_self=True).order_by('license_expiry_date')

            table = LicenseBiscuitReportTable(biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Biscuits 098/2019 Notification', 'table': table})
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gt=expirty_limit,
                is_self=True).order_by('license_expiry_date')
            table = LicenseConfectineryReportTable(confectionery_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Confectinery 098/2019 Notification', 'table': table})

            context['tables'] = tables
        except:
            pass
        return context


class PDFBiscuitsNewExpiryReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFBiscuitsNewExpiryReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseBiscuitReportTable
        from license.models import N2015
        try:
            expirty_limit = datetime.datetime.today()
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__lt=expirty_limit,
                                                                           is_self=True).order_by('license_expiry_date')

            table = LicenseBiscuitReportTable(
                biscuits_queryset.filter(notification_number=N2015).distinct())
            tables.append({'label': 'Biscuits Expired 019/2015 Notification', 'table': table})
            context['tables'] = tables
        except:
            pass
        return context


class PDFConfectioneryNewExpiredReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFConfectioneryNewExpiredReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseConfectineryReportTable
        from license.models import N2015
        try:
            expirty_limit = datetime.datetime.today()
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__lt=expirty_limit,
                is_self=True).order_by('license_expiry_date')

            table = LicenseConfectineryReportTable(
                confectionery_queryset.filter(notification_number=N2015).distinct())
            tables.append({'label': 'Confectinery Expired 019/2015 Notification', 'table': table})
            context['tables'] = tables
        except:
            pass
        return context


class PDFBiscuitsOldExpiryReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFBiscuitsOldExpiryReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseBiscuitReportTable
        from license.models import N2009
        try:
            expirty_limit = datetime.datetime.today()
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__lt=expirty_limit,
                                                                           is_self=True).order_by('license_expiry_date')

            table = LicenseBiscuitReportTable(
                biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Biscuits Expired 098/2009 Notification', 'table': table})
            context['tables'] = tables
        except:
            pass
        return context


class PDFConfectioneryOldExpiredReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFConfectioneryOldExpiredReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseConfectineryReportTable
        from license.models import N2009
        try:
            expirty_limit = datetime.datetime.today()
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__lt=expirty_limit,
                is_self=True).order_by('license_expiry_date')

            table = LicenseConfectineryReportTable(
                confectionery_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Confectinery Expired 098/2009 Notification', 'table': table})
            context['tables'] = tables
        except:
            pass
        return context

