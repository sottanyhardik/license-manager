import datetime

import xlsxwriter as xlsxwriter
from django.db.models import Q
from django.http import HttpResponseRedirect
# Create your views here.
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, TemplateView
from django_filters.views import FilterView
from easy_pdf.views import PDFTemplateResponseMixin
from extra_views import CreateWithInlinesView, UpdateWithInlinesView, InlineFormSetFactory

from core.utils import PagedFilteredTableView
from license.excel import get_license_table
from license.helper import round_down, check_license
from . import forms, tables, filters
from . import models as license
from .item_report import sugar_query, rbd_query, milk_query, wpc_query, skimmed_milk_query, dietary_query, food_query, \
    packing_query, juice_query, oci_query, fruit_query, get_table_query


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
        return reverse('license-ajax-list') + '?license_number=' + self.object.license_number


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
                        if self.object.import_license.all().first():
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
    template_name = 'license/list.html'
    model = license.LicenseDetailsModel
    filterset_class = filters.LicenseDetailFilter
    paginate_by = 50
    queryset = license.LicenseDetailsModel.objects.filter(is_active=True)
    ordering = "license_expiry_date"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context['is_active'] = True
        filterset_class = self.get_filterset_class()
        self.filterset = self.get_filterset(filterset_class)
        context['filter'] = self.filterset
        return context


class LicenseAjaxListView(FilterView):
    template_name = 'license/ajax-list.html'
    model = license.LicenseDetailsModel
    filterset_class = filters.LicenseDetailFilter
    paginate_by = 50
    queryset = license.LicenseDetailsModel.objects.filter()
    ordering = "license_expiry_date"


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
        tables = []
        from license.tables import LicenseBiscuitReportTable, LicenseConfectineryReportTable
        from license.models import N2015
        try:
            query_dict = {
                'export_license__norm_class__norm_class': 'E5',
                'notification_number': N2015
            }
            or_filters = {
                'exporter__name__icontains': ['rama', 'rani', 'VANILA']
            }
            exclude_or_filters={
                'export_license__old_quantity':0
            }
            queryset = get_table_query(query_dict, or_filters=or_filters,exclude_or_filters=exclude_or_filters)
            table = LicenseBiscuitReportTable(queryset)
            tables.append({'label': 'RAMA RANI VANNILA Biscuits', 'table': table})
            query_dict = {
                'export_license__norm_class__norm_class': 'E1',
                'notification_number': N2015
            }
            or_filters = {
                'exporter__name__icontains': ['rama', 'rani', 'VANILA']
            }
            exclude_or_filters = {
                'export_license__old_quantity': 0
            }
            queryset = get_table_query(query_dict, or_filters=or_filters, exclude_or_filters=exclude_or_filters)
            table = LicenseConfectineryReportTable(queryset)
            tables.append({'label': 'RAMA RANI VANNILA Confectinery', 'table': table})
            query_dict = {
                'export_license__norm_class__norm_class': 'E5',
                'notification_number': N2015
            }
            or_filters = {
                'exporter__name__icontains': ['Parle']
            }
            exclude_or_filters = {
                'export_license__old_quantity': 0
            }
            queryset = get_table_query(query_dict, or_filters=or_filters, exclude_or_filters=exclude_or_filters)
            table = LicenseBiscuitReportTable(queryset)
            tables.append({'label': 'Parle Biscuits', 'table': table})
            context['today_date'] = datetime.datetime.now().date()
            context['tables'] = tables
        except Exception as e:
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
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gt=expiry_limit,
                                                                           is_self=True, is_au=False).order_by(
                'license_expiry_date')
            filter_query = biscuits_queryset.filter(export_license__old_quantity=0, notification_number=N2015).filter(
                Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani') | Q(
                    exporter__name__icontains='vanila')).distinct()
            table = LicenseBiscuitReportTable(filter_query)
            tables.append({'label': 'RAMA RANI Other Biscuits', 'table': table})
            filter_query = biscuits_queryset.filter(export_license__old_quantity=0, notification_number=N2015).filter(
                Q(exporter__name__icontains='parle')).distinct()
            table = LicenseBiscuitReportTable(filter_query)
            tables.append({'label': 'Parle Other Biscuits', 'table': table})
            context['today_date'] = datetime.datetime.now().date()
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
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gt=expiry_limit,
                                                                           is_self=True, is_au=False).order_by(
                'license_expiry_date')
            filter_query = biscuits_queryset.filter(export_license__old_quantity=0, notification_number=N2015).exclude(
                Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani') | Q(
                    exporter__name__icontains='vanila') | Q(exporter__name__icontains='parle')).distinct()
            table = LicenseBiscuitReportTable(filter_query)
            tables.append({'label': 'Biscuits Remaning 019/2015 Notification', 'table': table})
            context['today_date'] = datetime.datetime.now().date()
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
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gt=expiry_limit,
                is_self=True, is_au=False).order_by('license_expiry_date')
            filter_query = confectionery_queryset.filter(export_license__old_quantity=0,
                                                         notification_number=N2015).filter(
                Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani') | Q(
                    exporter__name__icontains='vanila')).distinct()
            table = LicenseConfectineryReportTable(filter_query)
            tables.append({'label': 'RAMA RANI VANNILA Other Confectinery', 'table': table})
            filter_query = confectionery_queryset.filter(export_license__old_quantity=0,
                                                         notification_number=N2015).filter(
                Q(exporter__name__icontains='parle')).distinct()
            table = LicenseConfectineryReportTable(filter_query)
            tables.append({'label': 'Parle Other Confectinery', 'table': table})
            context['today_date'] = datetime.datetime.now().date()
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
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gt=expiry_limit,
                is_self=True, is_au=False).order_by('license_expiry_date')
            filter_query = confectionery_queryset.filter(export_license__old_quantity=0,
                                                         notification_number=N2015).exclude(
                Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani') | Q(
                    exporter__name__icontains='vanila') | Q(exporter__name__icontains='parle')).distinct()
            table = LicenseConfectineryReportTable(filter_query)
            tables.append({'label': 'Confectinery Remaning 019/2015 Notification', 'table': table})
            context['today_date'] = datetime.datetime.now().date()
            context['tables'] = tables
        except Exception as e:
            pass
        return context


class PDFOldBisReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFOldBisReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseBiscuitReportTable
        from license.models import N2009
        try:
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gt=expiry_limit,
                                                                           is_self=True, is_au=False).order_by(
                'license_expiry_date')
            q_biscuits_queryset = biscuits_queryset.exclude(
                Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani'))
            table = LicenseBiscuitReportTable(q_biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Biscuits 098/2019 Notification [ No Rama & Rani]', 'table': table})
            q_biscuits_queryset = biscuits_queryset.filter(
                Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani'))
            table = LicenseBiscuitReportTable(q_biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Rama Rani Biscuits 098/2019 Notification', 'table': table})
            context['today_date'] = datetime.datetime.now().date()
            context['tables'] = tables
        except:
            pass
        return context


class PDFOldConReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFOldConReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseConfectineryReportTable
        from license.models import N2009
        try:
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gt=expiry_limit,
                is_self=True, is_au=False).order_by('license_expiry_date')
            q_confectionery_queryset = confectionery_queryset.exclude(
                Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani'))
            table = LicenseConfectineryReportTable(
                q_confectionery_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Confectinery 098/2019 Notification [ No Rama & Rani]', 'table': table})
            q_confectionery_queryset = confectionery_queryset.filter(
                Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani'))
            table = LicenseConfectineryReportTable(
                q_confectionery_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Rama & Rani Confectinery 098/2019 Notification', 'table': table})
            context['today_date'] = datetime.datetime.now().date()
            context['tables'] = tables
        except:
            pass
        return context


class PDFOldRajawaniReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFOldRajawaniReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseBiscuitReportTable, LicenseConfectineryReportTable
        from license.models import N2009
        try:
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gt=expiry_limit,
                                                                           is_self=True, is_au=False).order_by(
                'license_expiry_date')
            q_biscuits_queryset = biscuits_queryset.filter(
                Q(exporter__name__icontains='rajwani'))
            table = LicenseBiscuitReportTable(q_biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Biscuits 098/2019 Notification [Rajwani]', 'table': table})
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gt=expiry_limit,
                is_self=True, is_au=False).order_by('license_expiry_date')
            q_confectionery_queryset = confectionery_queryset.filter(
                Q(exporter__name__icontains='rajwani'))
            table = LicenseConfectineryReportTable(
                q_confectionery_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Confectinery 098/2019 Notification [Rajwani]', 'table': table})
            context['today_date'] = datetime.datetime.now().date()
            context['tables'] = tables
        except:
            pass
        return context


class BiscuitsAmendmentView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/pdf_amend.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(BiscuitsAmendmentView, self).get_context_data()
        tables = []
        from license.tables import LicenseBiscuitReportTable, LicenseConfectineryReportTable
        from license.models import N2009
        try:
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gt=expiry_limit,
                                                                           is_self=True, is_au=False).order_by(
                'license_expiry_date')
            table = LicenseBiscuitReportTable(biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Biscuits 098/2019 Notification', 'table': table})
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gt=expiry_limit,
                is_self=True, is_au=False).order_by('license_expiry_date')
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
        from allotment.scripts.aro import fetch_cif
        fetch_cif()
        tables = []
        from license.tables import LicenseBiscuitReportTable
        from license.models import N2015
        try:
            expiry_limit = datetime.datetime.today()
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__lt=expiry_limit,
                                                                           is_self=True, is_au=False,
                                                                           balance_cif__gte=4000).order_by(
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
            expiry_limit = datetime.datetime.today()
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__lt=expiry_limit,
                is_self=True, is_au=False, balance_cif__gte=4000).order_by('license_expiry_date')

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
        tables = []
        from allotment.scripts.aro import fetch_cif
        fetch_cif()
        from license.tables import LicenseBiscuitReportTable
        from license.models import N2009
        try:
            expiry_limit = datetime.datetime.today()
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__lt=expiry_limit,
                                                                           is_self=True, is_au=False,
                                                                           balance_cif__gte=4000).order_by(
                'license_expiry_date')

            q_biscuits_queryset = biscuits_queryset.filter(
                Q(exporter__name__icontains='Rama') | Q(exporter__name__icontains='rani'))
            table = LicenseBiscuitReportTable(
                q_biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Rama & Rani Biscuits Expired 098/2009 Notification', 'table': table})
            q_biscuits_queryset = biscuits_queryset.filter(exporter__name__icontains='Parle')
            table = LicenseBiscuitReportTable(
                q_biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Parle Biscuits Expired 098/2009 Notification', 'table': table})
            q_biscuits_queryset = biscuits_queryset.exclude(
                Q(exporter__name__icontains='Parle') | Q(exporter__name__icontains='Rama') | Q(
                    exporter__name__icontains='rani'))
            table = LicenseBiscuitReportTable(
                q_biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Other Biscuits Expired 098/2009 Notification', 'table': table})
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
        from allotment.scripts.aro import fetch_cif
        fetch_cif()
        context = super(PDFConfectioneryOldExpiredReportView, self).get_context_data()
        tables = []
        from license.tables import LicenseConfectineryReportTable
        from license.models import N2009
        try:
            expiry_limit = datetime.datetime.today()
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__lt=expiry_limit,
                is_self=True, is_au=False, balance_cif__gte=5000).order_by('license_expiry_date')
            q_confectionery_queryset = confectionery_queryset.filter(exporter__name__icontains='Parle')
            table = LicenseConfectineryReportTable(
                q_confectionery_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Parle Confectinery Expired 098/2009 Notification', 'table': table})

            q_confectionery_queryset = confectionery_queryset.filter(
                Q(exporter__name__icontains='Rama') | Q(exporter__name__icontains='rani'))
            table = LicenseConfectineryReportTable(
                q_confectionery_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'Rama & Rani Confectinery Expired 098/2009 Notification', 'table': table})

            context['tables'] = tables
        except:
            pass
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
            expiry_limit = datetime.datetime.today()
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
        tables = []
        from license.tables import LicenseBiscuitReportTable, LicenseConfectineryReportTable
        from license.models import N2015
        from django.db.models import Q
        try:
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__gt=expiry_limit,
                                                                           is_self=True, is_au=False).order_by(
                'license_expiry_date')
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gt=expiry_limit,
                is_self=True, is_au=False).order_by('license_expiry_date')

            table = LicenseBiscuitReportTable(biscuits_queryset.filter(notification_number=N2015).exclude(
                Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani') | Q(
                    exporter__name__icontains='vanila') | Q(
                    exporter__name__icontains='parle')).exclude(export_license__old_quantity=0).distinct())
            tables.append({'label': 'Viva, V A global, Vipul Kumar Biscuits', 'table': table})
            table = LicenseConfectineryReportTable(confectionery_queryset.filter(notification_number=N2015).exclude(
                Q(exporter__name__icontains='rama') | Q(exporter__name__icontains='rani') | Q(
                    exporter__name__icontains='vanila') | Q(
                    exporter__name__icontains='parle')).exclude(export_license__old_quantity=0).distinct())
            tables.append({'label': 'Viva, V A global, Vipul Kumar Confectinery', 'table': table})
            table = LicenseConfectineryReportTable(
                confectionery_queryset.filter(notification_number=N2015).filter(
                    exporter__name__icontains='parle').exclude(
                    export_license__old_quantity=0).distinct())
            tables.append({'label': 'Parle Confectinery', 'table': table})
            context['tables'] = tables
        except:
            pass
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
                            | Q(exporter__name__icontains='VANILA')
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
            expiry_limit = datetime.datetime.today()
            queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gte=expiry_limit,
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
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
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
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=60)
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
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=30)
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
