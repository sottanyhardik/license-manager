import datetime
import os
from io import BytesIO, StringIO
from django.db.models import Sum
import xhtml2pdf.pisa as pisa
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.template.loader import get_template
# Create your views here.
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, TemplateView
from django.views.generic.base import TemplateResponseMixin, ContextMixin
from django_filters.views import FilterView
from easy_pdf.views import PDFTemplateResponseMixin
from extra_views import CreateWithInlinesView, UpdateWithInlinesView, InlineFormSetFactory

from core.utils import PagedFilteredTableView
from license.excel import get_license_table
from license.helper import round_down, check_license, item_wise_debiting, item_wise_allotment, fetch_item_details
from . import forms, tables, filters
from . import models as license
from .item_report import sugar_query, rbd_query, milk_query, wpc_query, skimmed_milk_query, dietary_query, food_query, \
    packing_query, juice_query, oci_query, fruit_query, report_dict_generate, biscuit_2009, biscuit_2019, \
    biscuit_2019_other, confectinery_2009, confectinery_2019, \
    confectinery_2019_other, biscuit_conversion, biscuit_2019_rama_rani, \
    conversion_main, conversion_other, confectinery_2019_rama_rani, confectinery_2009_all, biscuits_2009_all, \
    generate_dict, tartaric_query, essential_oil_query, confectinery_2009_expired_all, biscuits_2009_expired_all


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
    inlines = [LicenseExportItemInline, ]

    def form_valid(self, form):
        if not form.instance.created_by:
            form.instance.created_by = self.request.user
            form.instance.created_on = datetime.datetime.now()
        form.instance.modified_by = self.request.user
        form.instance.modified_on = datetime.datetime.now()
        return super(LicenseDetailCreateView, self).form_valid(form)

    def get_success_url(self):
        return reverse('dfia-details', kwargs={'license': self.object.license_number})


class DFIADetailView(DetailView):
    template_name = 'dfia/box.html'
    model = license.LicenseDetailsModel

    def get_object(self, queryset=None):
        object = self.model.objects.get(license_number=self.kwargs.get('license'))
        return object


class LicenseItemListUpdateView(UpdateWithInlinesView):
    template_name = 'license/item_list_edit.html'
    model = license.LicenseDetailsModel
    inlines = [LicenseImportItemInline, ]
    fields = ()

    def dispatch(self, request, *args, **kwargs):
        # check if there is some video onsite
        license = self.get_object()
        if self.get_object().is_audit:
            return HttpResponseRedirect(reverse('license-detail', kwargs={'license': license.license_number}))
        else:
            return super(LicenseItemListUpdateView, self).dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        object = self.model.objects.get(license_number=self.kwargs.get('license'))
        return object

    def form_valid(self, form):
        if not form.instance.created_by:
            form.instance.created_by = self.request.user
            form.instance.created_on = datetime.datetime.now()
        form.instance.modified_by = self.request.user
        form.instance.modified_on = datetime.datetime.now()
        return super(LicenseItemListUpdateView, self).form_valid(form)

    def get_inlines(self):
        if not self.object.is_audit:
            if self.object.export_license.all().exists():
                for export_item in self.object.export_license.all():
                    if export_item.norm_class:
                        for import_item in export_item.norm_class.import_norm.all():
                            if not self.object.ledger_date:
                                try:
                                    import_item_obj, bool = license.LicenseImportItemsModel.objects.get_or_create(
                                        license=self.object,
                                        serial_number=import_item.sr_no)
                                except:
                                    pass
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
                        if self.object.import_license.all().first() and export_item.net_quantity != 0:
                            value = round(
                                self.object.import_license.all().first().quantity / export_item.net_quantity * 100)
            self.inlines = [LicenseImportItemInline]
        return super(LicenseItemListUpdateView, self).get_inlines()


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
        object = self.model.objects.get(license_number=self.kwargs.get('license'))
        return object

    def form_valid(self, form):
        if not form.instance.created_by:
            form.instance.created_by = self.request.user
            form.instance.created_on = datetime.datetime.now()
        form.instance.modified_by = self.request.user
        form.instance.modified_on = datetime.datetime.now()
        return super(LicenseDetailUpdateView, self).form_valid(form)


class LicenseListView(FilterView):
    template_name = 'dfia/list.html'
    model = license.LicenseDetailsModel
    filterset_class = filters.LicenseDetailFilter
    paginate_by = 50
    queryset = license.LicenseDetailsModel.objects.filter()
    ordering = "license_expiry_date"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context['is_active'] = self.request.GET.get('is_active')
        filterset_class = self.get_filterset_class()
        self.filterset = self.get_filterset(filterset_class)
        context['filter'] = self.filterset
        context['page_title'] = 'DFIA List'
        context['dfia_count'] = self.object_list.count()
        return context

    def get(self, request, **kwargs):
        csv = request.GET.get('csv', False)
        # check for format query key in url (my/url/?format=csv)
        if csv:
            f = self.filterset_class(request.GET, queryset=self.model.objects.all())
            for d in f.qs:
                d.balance_cif = d.get_balance_cif()
                d.export_item = d.get_norm_class
                d.license_number = d.license_number.replace("'", '')
                d.fob = d.opening_fob()
                d.save()
            query = f.qs.values('license_number', 'license_date', 'port__code', 'license_expiry_date', 'file_number',
                                'exporter__name', 'export_item', 'fob', 'balance_cif', 'user_comment', 'ledger_date')
            from djqscsv import render_to_csv_response
            return render_to_csv_response(query.order_by('license_expiry_date'))
        return super(LicenseListView, self).get(request, **kwargs)


class LicenseAjaxListView(FilterView):
    template_name = 'license/ajax-list.html'
    model = license.LicenseDetailsModel
    filterset_class = filters.LicenseDetailFilter
    paginate_by = 50
    queryset = license.LicenseDetailsModel.objects.filter()
    ordering = "license_expiry_date"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context['is_active'] = True
        filterset_class = self.get_filterset_class()
        self.filterset = self.get_filterset(filterset_class)
        context['filter'] = self.filterset
        return context


class LicenseCardView(DetailView):
    template_name = 'license/card.html'
    model = license.LicenseDetailsModel
    context_object_name = 'license'

    def get_object(self, queryset=None):
        return self.model.objects.get(license_number=self.kwargs.get('license'))


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
                                 'Notification', 'Scheme Code', 'Port', 'Export Items', 'Import Items', 'Item',
                                 'Total CIF', 'Balance CIF', "Sr No", 'HS Code', 'Quantity', 'Balance Quantity',
                                 'CIF FC', 'Balance CIF FC']:
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


class PDFLedgerLicenseDetailView(PDFTemplateResponseMixin, DetailView):
    template_name = 'license/pdf_ledger.html'
    model = license.LicenseDetailsModel

    def get_object(self, queryset=None):
        return self.model.objects.get(license_number=self.kwargs.get('license'))


class PDFCReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFCReportView, self).get_context_data()
        tables = conversion_main()
        context['today_date'] = datetime.datetime.now().date()
        context['tables'] = tables
        return context


class PDFNewBiscuitsReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFNewBiscuitsReportView, self).get_context_data()
        context['today_date'] = datetime.datetime.now().date()
        tables = biscuit_2019_rama_rani()
        context['tables'] = tables
        return context


class PDFNewBiscuitsOtherReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFNewBiscuitsOtherReportView, self).get_context_data()
        context['today_date'] = datetime.datetime.now().date()
        tables = biscuit_2019_other()
        context['tables'] = tables
        return context


class PDFNewConfectioneryReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFNewConfectioneryReportView, self).get_context_data()
        tables = confectinery_2019_rama_rani()
        context['today_date'] = datetime.datetime.now().date()
        context['tables'] = tables
        return context


class PDFNewConfectioneryOtherReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFNewConfectioneryOtherReportView, self).get_context_data()
        tables = confectinery_2019_other()
        context['today_date'] = datetime.datetime.now().date()
        context['tables'] = tables
        return context


class PDFOldBisReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFOldBisReportView, self).get_context_data()
        tables = biscuits_2009_all()
        context['today_date'] = datetime.datetime.now().date()
        context['tables'] = tables
        return context


class PDFOldConReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFOldConReportView, self).get_context_data()
        tables = confectinery_2009_all()
        context['today_date'] = datetime.datetime.now().date()
        context['tables'] = tables
        return context


class PDFBiscuitsNewExpiryReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFBiscuitsNewExpiryReportView, self).get_context_data()
        from allotment.scripts.aro import fetch_cif
        fetch_cif()
        tables = []
        from license.tables import LicenseBiscuitReportTable
        from license.models import N2015
        try:
            expiry_limit = datetime.datetime.strptime('2021-08-20', '%Y-%m-%d')
            start_limit = datetime.datetime.strptime('2018-01-01', '%Y-%m-%d')
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__lt=expiry_limit,
                                                                           license_expiry_date__gte=start_limit,
                                                                           is_self=True, is_au=False,
                                                                           balance_cif__gte=4000,
                                                                           export_license__old_quantity__lte=2).order_by(
                'license_expiry_date')
            q_biscuits_queryset = biscuits_queryset.filter(
                Q(exporter__name__icontains='Rama') | Q(exporter__name__icontains='rani'))
            table = LicenseBiscuitReportTable(
                q_biscuits_queryset.filter(notification_number=N2015).distinct())
            tables.append({'label': 'Rama & Rani Biscuits Expired 019/2015 Notification', 'table': table})
            q_biscuits_queryset = biscuits_queryset.filter(exporter__name__icontains='Parle')
            table = LicenseBiscuitReportTable(
                q_biscuits_queryset.filter(notification_number=N2015).distinct())
            tables.append({'label': 'Parle Biscuits Expired 019/2015 Notification', 'table': table})
            q_biscuits_queryset = biscuits_queryset.exclude(
                Q(exporter__name__icontains='Parle') | Q(exporter__name__icontains='Rama') | Q(
                    exporter__name__icontains='rani'))
            table = LicenseBiscuitReportTable(
                q_biscuits_queryset.filter(notification_number=N2015).distinct())
            tables.append({'label': 'Other Biscuits Expired 019/2015 Notification', 'table': table})
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
        from allotment.scripts.aro import fetch_cif
        fetch_cif()
        context = super(PDFConfectioneryNewExpiredReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseConfectineryReportTable
        from license.models import N2015
        try:
            expiry_limit = datetime.datetime.strptime('2021-08-20', '%Y-%m-%d')
            start_limit = datetime.datetime.strptime('2018-01-01', '%Y-%m-%d')
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__lt=expiry_limit,
                license_expiry_date__gte=start_limit,
                is_self=True, is_au=False, balance_cif__gte=4000, export_license__old_quantity__lte=2).order_by(
                'license_expiry_date')

            q_confectionery_queryset = confectionery_queryset.filter(exporter__name__icontains='Parle')
            table = LicenseConfectineryReportTable(
                q_confectionery_queryset.filter(notification_number=N2015).distinct())
            tables.append({'label': 'Parle Confectinery Expired 019/2015 Notification', 'table': table})

            q_confectionery_queryset = confectionery_queryset.filter(
                Q(exporter__name__icontains='Rama') | Q(exporter__name__icontains='rani'))
            table = LicenseConfectineryReportTable(
                q_confectionery_queryset.filter(notification_number=N2015).distinct())
            tables.append({'label': 'Rama & Rani Confectinery Expired 019/2015 Notification', 'table': table})

            q_confectionery_queryset = confectionery_queryset.exclude(
                Q(exporter__name__icontains='parle') | Q(exporter__name__icontains='Rama') | Q(
                    exporter__name__icontains='rani'))
            table = LicenseConfectineryReportTable(
                q_confectionery_queryset.filter(notification_number=N2015).distinct())
            tables.append({'label': 'Other Confectinery Expired 019/2015 Notification', 'table': table})
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
        tables = biscuits_2009_expired_all()
        context['today_date'] = datetime.datetime.now().date()
        context['tables'] = tables
        return context


class PDFConfectioneryOldExpiredReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFConfectioneryOldExpiredReportView, self).get_context_data()
        tables = confectinery_2009_expired_all()
        context['today_date'] = datetime.datetime.now().date()
        context['tables'] = tables
        return context


class PDFOtherConfectioneryOldExpiredReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        from allotment.scripts.aro import fetch_cif
        fetch_cif()
        context = super(PDFOtherConfectioneryOldExpiredReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseConfectineryReportTable
        from license.models import N2009
        try:
            expiry_limit = datetime.datetime.strptime('2020-07-31', '%Y-%m-%d')
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__lt=expiry_limit,
                is_self=True, is_au=False, balance_cif__gte=5000).order_by('license_expiry_date')
            q_confectionery_queryset = confectionery_queryset.exclude(
                Q(exporter__name__icontains='parle') | Q(exporter__name__icontains='Rama') | Q(
                    exporter__name__icontains='rani'))
            table = LicenseConfectineryReportTable(
                q_confectionery_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Other Confectinery Expired 098/2009 Notification', 'table': table})

            context['tables'] = tables
        except:
            pass
        return context


class PDFOCReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFOCReportView, self).get_context_data()
        context['today_date'] = datetime.datetime.now().date()
        tables = conversion_other()
        context['tables'] = tables
        return context


class PDFLedgerItemLicenseDetailView(PDFTemplateResponseMixin, DetailView):
    template_name = 'license/item_pdf.html'
    model = license.LicenseDetailsModel

    def get_object(self, queryset=None):
        return self.model.objects.get(license_number=self.kwargs.get('license'))


class ItemReportView(TemplateView):
    template_name = 'license/report.html'

    def get_context_data(self, **kwargs):
        context = super(ItemReportView, self).get_context_data()
        return context


class ItemListReportView(PDFTemplateResponseMixin, TemplateView):
    template_name = 'license/report_pdf_ITEM.html'
    model = license.LicenseDetailsModel

    def get_context_data(self, **kwargs):
        context = super(ItemListReportView, self).get_context_data()
        total_quantity = 0
        item = self.request.GET.get('item', None)
        if item == 'sugar':
            title = 'Sugar'
            tables = sugar_query()
        elif item == 'rbd':
            title = 'RBD Palmolein Oil'
            tables = rbd_query()
        elif item == 'whey':
            title = 'Milk & Milk [Whey]'
            tables = milk_query()
        elif item == 'wpc':
            title = 'Milk & Milk [WPC]'
            tables = wpc_query()
        elif item == 'skimmed':
            title = 'Milk & Milk [Skimmed Milk]'
            tables = skimmed_milk_query()
        elif item == 'dietary':
            title = 'Dietary Fibre'
            tables = dietary_query()
        elif item == 'flavour':
            title = 'Food Flavour'
            tables = food_query()
        elif item == 'fruit':
            title = 'Fruit (Biscuit)'
            tables = fruit_query()
        elif item == 'pp':
            title = 'PP'
            tables = packing_query()
        elif item == 'oci':
            title = 'Other Confectionery Ingredients'
            tables = oci_query()
        elif item == 'juice':
            title = 'Fruit Juice'
            tables = juice_query()
        elif item == 'tartaric':
            title = 'Tartaric Acid'
            tables = tartaric_query()
        elif item == 'essential':
            title = 'Essential Oil'
            tables = essential_oil_query()
        context['page_title'] = title
        context['tables'] = tables
        for table in tables:
            if table['total']:
                total_quantity = total_quantity + table['total']
        context['total_quantity'] = total_quantity
        context['today'] = datetime.datetime.now().date()
        return context


def check_query(queryset):
    return queryset.exclude(Q(exporter__name__icontains='MOTWANI INTERNATIONAL') |
                            Q(exporter__name__icontains='KHYATI ADVISORY') |
                            Q(exporter__name__icontains='SHAKTI  FOOD  PRODUCTS')
                            | Q(exporter__name__icontains='STRAINA INTERNATIONAL')
                            | Q(exporter__name__icontains='TOPAZ INTERNATIONAL')
                            | Q(exporter__name__icontains='VANILLA')
                            | Q(exporter__name__icontains='VIVA')
                            | Q(exporter__name__icontains='DELMORE')
                            | Q(exporter__name__icontains='Kulubi')
                            | Q(exporter__name__icontains='Jai Gurudev')
                            | Q(exporter__name__icontains='CONTINENTAL EXPORTS')
                            | Q(exporter__name__icontains='KITES BAKERS')
                            | Q(exporter__name__icontains='J K INTERNATIONAL TRADERS')
                            | Q(exporter__name__icontains='DALSON FOOD INDUSTRIES')
                            | Q(exporter__name__icontains='RAMA')
                            | Q(exporter__name__icontains='RANI')
                            | Q(exporter__name__icontains='Parle')).distinct()


class PDFParleConfectioneryOldExpiredReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        from allotment.scripts.aro import fetch_cif
        fetch_cif()
        context = super(PDFParleConfectioneryOldExpiredReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseConfectineryReportTable
        try:
            expiry_limit = datetime.datetime.strptime('2020-07-31', '%Y-%m-%d')
            start_limit = datetime.datetime.strptime('2020-02-29', '%Y-%m-%d')
            queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gte=expiry_limit,
                license_expiry_date__lte=start_limit,
                is_self=True, is_au=False, balance_cif__gte=4000).order_by('license_expiry_date')
            queryset = check_query(queryset)
            table = LicenseConfectineryReportTable(queryset)
            tables.append({'label': 'Confectinery', 'table': table})
            queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                  license_expiry_date__gte=expiry_limit,
                                                                  is_self=True, is_au=False,
                                                                  balance_cif__gte=4000).order_by(
                'license_expiry_date')

            from license.tables import LicenseBiscuitReportTable
            queryset = check_query(queryset)
            table = LicenseBiscuitReportTable(queryset)
            tables.append({'label': 'Biscuits', 'table': table})
            context['tables'] = tables
        except:
            pass
        return context


class PDFAUConfectioneryReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        from allotment.scripts.aro import fetch_cif
        fetch_cif()
        context = super(PDFAUConfectioneryReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseConfectineryReportTable
        from license.models import N2009
        try:
            expiry_limit = datetime.datetime.strptime('2020-02-29', '%Y-%m-%d')
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gte=expiry_limit,
                is_self=True, is_au=True, balance_cif__gte=5000).order_by('license_expiry_date')
            q_confectionery_queryset = confectionery_queryset
            table = LicenseConfectineryReportTable(
                q_confectionery_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'AU Confectinery Active', 'table': table})
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__lt=expiry_limit,
                is_self=True, is_au=True, balance_cif__gte=5000).order_by('license_expiry_date')
            q_confectionery_queryset = confectionery_queryset
            table = LicenseConfectineryReportTable(
                q_confectionery_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'AU Confectinery Expired', 'table': table})
            context['tables'] = tables
        except:
            pass
        return context


class PDFAUBiscuitsReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFAUBiscuitsReportView, self).get_context_data()
        tables = []
        from allotment.scripts.aro import fetch_cif
        fetch_cif()
        from license.tables import LicenseBiscuitReportTable
        from license.models import N2009
        try:
            expiry_limit = datetime.datetime.strptime('2020-02-29', '%Y-%m-%d')
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gte=expiry_limit,
                                                                           is_self=True, is_au=True,
                                                                           balance_cif__gte=4000).order_by(
                'license_expiry_date')

            q_biscuits_queryset = biscuits_queryset
            table = LicenseBiscuitReportTable(
                q_biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'AU Biscuits Active', 'table': table})
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__lt=expiry_limit,
                                                                           is_self=True, is_au=True,
                                                                           balance_cif__gte=4000).order_by(
                'license_expiry_date')

            q_biscuits_queryset = biscuits_queryset
            table = LicenseBiscuitReportTable(
                q_biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'AU Biscuits Expired', 'table': table})

            context['tables'] = tables
        except:
            pass
        return context


class PremiumCalculationView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/preimum_calc.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitPreimiumTable
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PremiumCalculationView, self).get_context_data()
        tables = []
        from allotment.scripts.aro import fetch_cif
        fetch_cif()
        from license.models import N2015
        try:
            expiry_limit = datetime.datetime.strptime('2020-07-31', '%Y-%m-%d')
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gte=expiry_limit,
                                                                           is_self=True,
                                                                           balance_cif__gte=4000).order_by(
                'license_expiry_date')

            q_biscuits_queryset = biscuits_queryset.filter(
                Q(export_license__old_quantity=0) | Q(export_license__old_quantity=None))
            from license.tables import LicenseBiscuitPreimiumTable
            table = LicenseBiscuitPreimiumTable(
                q_biscuits_queryset.filter(notification_number=N2015).distinct())
            tables.append({'label': 'Biscuits Active', 'table': table})
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gte=expiry_limit,
                is_self=True,
                balance_cif__gte=4000).order_by('license_expiry_date')
            q_confectionery_queryset = confectionery_queryset.filter(
                Q(export_license__old_quantity=0) | Q(export_license__old_quantity=None))
            from license.tables import LicenseConfectioneryPreimiumTable
            table = LicenseConfectioneryPreimiumTable(
                q_confectionery_queryset.filter(notification_number=N2015).distinct())
            tables.append({'label': 'Confectionery Active', 'table': table})
            context['tables'] = tables
        except Exception as e:
            pass
        return context


def analysis(requests):
    check_license()
    return HttpResponseRedirect(reverse('license-list'))


class LicenseReportListView(TemplateResponseMixin, ContextMixin, View):
    template_name = 'license/report_form.html'

    def render_to_file(self, data_dict, folder_name=None):
        template = get_template(data_dict['template_name'])
        html = template.render(data_dict)
        file_name = "{0}.pdf".format(data_dict['page_title'])
        file_path = os.path.join(os.path.abspath(os.path.dirname("__file__")), folder_name)
        if not os.path.exists(file_path):
            os.mkdir(file_path)
        file_path = os.path.join(os.path.abspath(os.path.dirname("__file__")), folder_name, file_name)
        with open(file_path, 'wb') as pdf:
            pisa.pisaDocument(BytesIO(html.encode("UTF-8")), pdf)
        return [file_name, file_path]

    def get(self, request, *args, **kwargs):
        item_report = self.request.GET.get('item_report', None)
        item_generate = self.request.GET.get('item_generate', None)
        start_date = self.request.GET.get('start_date', None)
        end_date = self.request.GET.get('end_date', None)
        date_range = {
            'start': start_date,
            'end': end_date
        }
        if item_report:
            file_name = "Item Report " + str(datetime.datetime.now().date())
            self.render_to_file(report_dict_generate(sugar_query(date_range=date_range), 'Sugar', total_quantity=0),
                                folder_name=file_name)
            self.render_to_file(
                report_dict_generate(rbd_query(date_range=date_range), 'RBD Palmolein Oil', total_quantity=0),
                folder_name=file_name)
            self.render_to_file(
                report_dict_generate(milk_query(date_range=date_range), 'Milk & Milk [Whey]', total_quantity=0),
                folder_name=file_name)
            self.render_to_file(
                report_dict_generate(wpc_query(date_range=date_range), 'Milk & Milk [WPC]', total_quantity=0),
                folder_name=file_name)
            self.render_to_file(
                report_dict_generate(skimmed_milk_query(date_range=date_range), 'Milk & Milk [Skimmed Milk]',
                                     total_quantity=0), folder_name=file_name)
            self.render_to_file(
                report_dict_generate(dietary_query(date_range=date_range), 'Dietary Fibre', total_quantity=0),
                folder_name=file_name)
            self.render_to_file(
                report_dict_generate(food_query(date_range=date_range), 'Food Flavour', total_quantity=0),
                folder_name=file_name)
            self.render_to_file(
                report_dict_generate(fruit_query(date_range=date_range), 'Fruit (Biscuit)', total_quantity=0),
                folder_name=file_name)
            self.render_to_file(report_dict_generate(packing_query(date_range=date_range), 'PP', total_quantity=0),
                                folder_name=file_name)
            self.render_to_file(
                report_dict_generate(oci_query(date_range=date_range), 'Other Confectionery Ingredients',
                                     total_quantity=0), folder_name=file_name)
            self.render_to_file(
                report_dict_generate(juice_query(date_range=date_range), 'Fruit Juice', total_quantity=0),
                folder_name=file_name)
            files_path = os.path.join(os.path.abspath(os.path.dirname("__file__")), file_name)
            from shutil import make_archive
            path_to_zip = make_archive(files_path, "zip", files_path)
            zip_file = open(path_to_zip, 'rb')
            from django.http import HttpResponse
            response = HttpResponse(zip_file, content_type='application/force-download')
            response['Content-Disposition'] = 'attachment; filename="{filename}.zip"'.format(
                filename=file_name.replace(" ", "_")
            )
            return response
        elif item_generate:
            file_name = "License Report " + str(datetime.datetime.now().date())
            self.render_to_file(report_dict_generate(conversion_other(date_range=date_range), 'Conversion V Group'),
                                folder_name=file_name)
            self.render_to_file(report_dict_generate(conversion_main(date_range=date_range), 'Conversion Main'),
                                folder_name=file_name)
            self.render_to_file(report_dict_generate(biscuit_2009(date_range=date_range), 'Biscuit 98_2009'),
                                folder_name=file_name)
            self.render_to_file(report_dict_generate(biscuit_2019_rama_rani(date_range=date_range), 'Biscuit 19_2015'),
                                folder_name=file_name)
            self.render_to_file(
                report_dict_generate(biscuit_2019_other(date_range=date_range), 'Biscuit 19_2015 Other'),
                folder_name=file_name)
            self.render_to_file(report_dict_generate(confectinery_2009(date_range=date_range), 'Confectionery 98_2009'),
                                folder_name=file_name)
            self.render_to_file(report_dict_generate(confectinery_2019(date_range=date_range), 'Confectionery 19_2015'),
                                folder_name=file_name)
            self.render_to_file(
                report_dict_generate(confectinery_2019_other(date_range=date_range), 'Confectionery 19_2015 Other'),
                folder_name=file_name)
            files_path = os.path.join(os.path.abspath(os.path.dirname("__file__")), file_name)
            from shutil import make_archive
            path_to_zip = make_archive(files_path, "zip", files_path)
            zip_file = open(path_to_zip, 'rb')
            from django.http import HttpResponse
            response = HttpResponse(zip_file, content_type='application/force-download')
            response['Content-Disposition'] = 'attachment; filename="{filename}.zip"'.format(
                filename=file_name.replace(" ", "_")
            )
            return response
        else:
            context = self.get_context_data(**kwargs)
            return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(LicenseReportListView, self).get_context_data()
        return context


import xlsxwriter


def WriteToExcel(weather_data, town=None):
    output = StringIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet_s = workbook.add_worksheet("Summary")
    from django.utils.translation import ugettext
    title_text = "{0} {1}".format(ugettext("Weather History for"), 'town_text')
    title = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'align': 'center',
        'valign': 'vcenter'
    })
    header = workbook.add_format({
        'bg_color': '#F7F7F7',
        'color': 'black',
        'align': 'center',
        'valign': 'top',
        'border': 1
    })
    worksheet_s.merge_range('B2:H2', title_text, title)
    worksheet_s.write(4, 0, ugettext("No"), header)
    worksheet_s.write(4, 1, ugettext("Town"), header)
    worksheet_s.write(4, 3, ugettext("Max T."), header)
    # Here we will adding the code to add data

    workbook.close()
    xlsx_data = output.getvalue()
    # xlsx_data contains the Excel file
    return xlsx_data


class LicensePDFConsolidateView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/pdf_consolidate.html'
    model = license.LicenseDetailsModel
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(LicensePDFConsolidateView, self).get_context_data()
        context['today_date'] = datetime.datetime.now().date()
        total_dict = {
            'balance': {'cif': 0},
            'sugar': {'cif': 0, 'quantity': 0},
            'rbd': {'cif': 0, 'quantity': 0},
            'dietary_fibre': {'cif': 0, 'quantity': 0},
            'food_flavour': {'cif': 0, 'quantity': 0},
            'fruit': {'cif': 0, 'quantity': 0},
            'm_n_m': {'cif': 0, 'quantity': 0},
            'wheat': {'cif': 0, 'quantity': 0},
            'leavening_agent': {'cif': 0, 'quantity': 0},
            'pp': {'cif': 0, 'quantity': 0},

        }
        biscuit_list = []
        objects = biscuit_2009()
        for object in objects:
            dicts, total_dict = generate_dict(object, total_dict)
            biscuit_list.append(dicts)
        objects = biscuit_conversion()
        for object in objects:
            dicts, total_dict = generate_dict(object, total_dict)
            biscuit_list.append(dicts)
        objects = biscuit_2019()
        for object in objects:
            dicts, total_dict = generate_dict(object, total_dict, new=True)
            biscuit_list.append(dicts)
        context['biscuit_list'] = biscuit_list
        context['total_dict'] = total_dict
        return context


class MovementItemInline(InlineFormSetFactory):
    model = license.LicenseInwardOutwardModel
    form_class = forms.LicenseInwardOutwardForm


class MovementListView(PagedFilteredTableView):
    template_name = 'core/list.html'
    model = license.LicenseInwardOutwardModel
    table_class = tables.LicenseInwardOutwardTable
    filter_class = filters.LicenseInwardOutwardFilter
    ordering = ('date__date', 'license__ge_file_number')


class MovementUpdateView(UpdateWithInlinesView):
    model = license.DateModel
    template_name = 'core/add.html'
    fields = "__all__"
    inlines = [MovementItemInline, ]

    def get_object(self, queryset=None):
        model, bool = self.model.objects.get_or_create(date=datetime.datetime.now().date())
        return model

    def get_success_url(self):
        return reverse('movement-list')


class PDFSummaryLicenseDetailView(PDFTemplateResponseMixin, DetailView):
    template_name = 'license/summary_pdf.html'
    model = license.LicenseDetailsModel

    def get_object(self, queryset=None):
        return self.model.objects.get(license_number=self.kwargs.get('license'))

    def get_context_data(self, **kwargs):
        context = super(PDFSummaryLicenseDetailView, self).get_context_data()
        dfia = self.object
        context['total_debits'] = round(dfia.get_total_allotment + dfia.get_total_debit, 2)
        dict_list = []
        estimation_dict = {}
        items = ['gluten', 'Palmolein', 'Yeast', 'juice', 'milk', 'Packing Material']
        for item in items:
            if 'milk' in item:
                import_item = dfia.import_license.filter(item__name__icontains=item)
                if import_item:
                    milk_dict = fetch_item_details(import_item.first().item, import_item.first().hs_code.hs_code, dfia)
                    print(milk_dict)
                    total_qty = milk_dict['opening_balance']
                    half = total_qty / 2
                    wpc_dict = fetch_item_details(import_item.first().item, import_item.first().hs_code.hs_code, dfia,
                                                  'wpc')
                    cheese_dict = fetch_item_details(import_item.first().item, '04060000', dfia, 'cheese')
                    if wpc_dict['total_debited_qty'] > half:
                        wpc_dict['opening_balance'] = wpc_dict['total_debited_qty']
                        wpc_dict['balance_qty'] = 0
                        cheese_dict['opening_balance'] = milk_dict['opening_balance'] - wpc_dict['total_debited_qty']
                        cheese_dict['balance_qty'] = cheese_dict['opening_balance'] - cheese_dict['total_debited_qty']
                    elif cheese_dict['total_debited_qty'] > half:
                        cheese_dict['opening_balance'] = cheese_dict['total_debited_qty']
                        cheese_dict['balance_qty'] = 0
                        wpc_dict['opening_balance'] = milk_dict['opening_balance'] - cheese_dict['total_debited_qty']
                        wpc_dict['balance_qty'] = wpc_dict['opening_balance'] - wpc_dict['total_debited_qty']
                    else:
                        wpc_dict['opening_balance'] = half
                        wpc_dict['balance_qty'] = wpc_dict['opening_balance'] - wpc_dict['total_debited_qty']
                        cheese_dict['opening_balance'] = half
                        cheese_dict['balance_qty'] = cheese_dict['opening_balance'] - cheese_dict['total_debited_qty']
                    dict_list.append(milk_dict)
                    dict_list.append(wpc_dict)
                    dict_list.append(cheese_dict)

            else:
                import_item = dfia.import_license.filter(item__name__icontains=item)
                if import_item.first() and import_item.first().item:
                    dict_data = fetch_item_details(import_item.first().item, import_item.first().hs_code.hs_code, dfia)
                    dict_list.append(dict_data)
        context['item_list'] = dict_list
        return context
