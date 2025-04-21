import datetime
import os
from io import BytesIO, StringIO

import xlsxwriter
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy
import xhtml2pdf.pisa as pisa
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.template.loader import get_template
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, TemplateView, ListView
from django.views.generic.base import TemplateResponseMixin, ContextMixin
from django_filters.views import FilterView
from django_tables2 import SingleTableView
from easy_pdf.views import PDFTemplateResponseMixin
from extra_views import CreateWithInlinesView, UpdateWithInlinesView, InlineFormSetFactory

from core.utils import PagedFilteredTableView
from license.excel import get_license_table
from license.helper import round_down, check_license, fetch_item_details
from . import forms, tables, filters
from . import models as license
from .item_report import item_filter
from .models import GE, MI, LicenseDetailsModel, SM, OT, CO, RA
from .tables import LicenseBiscuitReportTable, LicenseConfectioneryReportTable, LicenseNamkeenReportTable, \
    LicenseSteelReportTable, LicenseTractorReportTable, LicenseGlassReportTable, LicensePickleReportTable
from .tasks import update_items


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
                    if self.object.import_license.all().first() and export_item.net_quantity != 0:
                        value = round(float(
                            self.object.import_license.all().first().quantity) / float(
                            export_item.net_quantity) * 100)
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
                d.balance_cif = d.get_balance_cif
                d.export_item = d.get_norm_class
                d.license_number = d.license_number.replace("'", '')
                d.fob = d.opening_fob
                d.file_transfer_status = str(d.latest_transfer)
                d.save()
            query = f.qs.values('license_number', 'license_date', 'port__code', 'license_expiry_date', 'file_number',
                                'exporter__name', 'export_item', 'fob', 'balance_cif', 'user_comment', 'ledger_date',
                                'file_transfer_status')
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


# class LicenseVerifyView(View):
#
#     def get(self, requests, pk):
#         license_obj = license.LicenseDetailsModel.objects.get(id=pk)
#         license_obj.is_audit = True
#         license_obj.save()
#         return HttpResponseRedirect(reverse('license-detail', kwargs={'license': license_obj.license_number}))


class PDFLedgerLicenseDetailView(PDFTemplateResponseMixin, DetailView):
    template_name = 'license/pdf_ledger.html'
    model = license.LicenseDetailsModel

    def get_object(self, queryset=None):
        return self.model.objects.get(license_number=self.kwargs.get('license'))


class BaseReportView(TemplateView):
    template_name = 'license/report_list.html'
    model = license.LicenseDetailsModel
    norm_class = None
    table_class = None

    def get_queryset(self):
        date = datetime.datetime.now() - datetime.timedelta(days=30)
        is_expired = self.kwargs.get('status') == 'expired'
        if not is_expired:
            return self.model.objects.filter(license_expiry_date__gte=date,
                                             export_license__norm_class__norm_class__in=self.norm_class)
        else:
            return self.model.objects.filter(license_expiry_date__lt=date,
                                             export_license__norm_class__norm_class__in=self.norm_class)

    def get_context_data(self, **kwargs):
        queryset = self.get_queryset()
        lower_balance_query = queryset.filter(balance_cif__lt=500)
        higher_balance_query = queryset.filter(balance_cif__gte=500)

        lower_table = self.table_class(lower_balance_query)
        higher_table = self.table_class(higher_balance_query)

        context = super().get_context_data(**kwargs)
        context['lower_table'] = lower_table
        context['higher_table'] = higher_table

        return context


class BiscuitReportView(BaseReportView):
    template_name = 'license/report_list.html'
    table_class = LicenseBiscuitReportTable

    def get_queryset(self):
        date = datetime.datetime.now() - datetime.timedelta(days=30)
        party = self.kwargs.get('party')
        is_expired = self.kwargs.get('status') == 'expired'
        if party == 'parle':
            if not is_expired:
                queryset = LicenseDetailsModel.objects.filter(exporter__name__icontains=self.kwargs.get('party'),
                                                              license_expiry_date__gte=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=GE)
            else:
                queryset = LicenseDetailsModel.objects.filter(exporter__name__icontains=self.kwargs.get('party'),
                                                              license_expiry_date__lt=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=GE)
        elif party == 'mi':
            if not is_expired:
                queryset = LicenseDetailsModel.objects.filter(license_expiry_date__gte=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=MI)
            else:
                queryset = LicenseDetailsModel.objects.filter(license_expiry_date__lt=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=MI)
        elif party == 'sm':
            if not is_expired:
                queryset = LicenseDetailsModel.objects.filter(license_expiry_date__gte=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=SM)
            else:
                queryset = LicenseDetailsModel.objects.filter(license_expiry_date__lt=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=SM)
        elif party == 'ot':
            if not is_expired:
                queryset = LicenseDetailsModel.objects.filter(license_expiry_date__gte=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=OT)
            else:
                queryset = LicenseDetailsModel.objects.filter(license_expiry_date__lt=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=OT)
        elif party.lower() == 'co':
            if not is_expired:
                queryset = LicenseDetailsModel.objects.filter(license_expiry_date__gte=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=CO)
            else:
                queryset = LicenseDetailsModel.objects.filter(license_expiry_date__lt=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=CO)
        elif party.lower() == 'ra':
            if not is_expired:
                queryset = LicenseDetailsModel.objects.filter(license_expiry_date__gte=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=RA)
            else:
                queryset = LicenseDetailsModel.objects.filter(license_expiry_date__lt=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=RA)
        else:
            if not is_expired:
                queryset = LicenseDetailsModel.objects.filter(license_expiry_date__gte=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=GE).exclude(
                    exporter__name__icontains='parle')
            else:
                queryset = LicenseDetailsModel.objects.filter(license_expiry_date__lt=date,
                                                              export_license__norm_class__norm_class='E5',
                                                              purchase_status=GE).exclude(
                    exporter__name__icontains='parle')
        return queryset


class ConfectioneryReportView(BaseReportView):
    norm_class = ['E1', ]
    table_class = LicenseConfectioneryReportTable

    def get_queryset(self):
        date = datetime.datetime.now() - datetime.timedelta(days=30)
        is_expired = self.kwargs.get('status') == 'expired'
        party = self.kwargs.get('party')
        if party.lower() == 'co' and not is_expired:
            return self.model.objects.filter(license_expiry_date__gte=date,
                                             export_license__norm_class__norm_class__in=self.norm_class, is_mnm=False,
                                             purchase_status=CO)
        elif party.lower() == 'co' and is_expired:
            return self.model.objects.filter(license_expiry_date__lt=date,
                                             export_license__norm_class__norm_class__in=self.norm_class, is_mnm=False,
                                             purchase_status=CO)
        elif not is_expired:
            return self.model.objects.filter(license_expiry_date__gte=date,
                                             export_license__norm_class__norm_class__in=self.norm_class,
                                             is_mnm=False).exclude(purchase_status=CO)
        else:
            return self.model.objects.filter(license_expiry_date__lt=date,
                                             export_license__norm_class__norm_class__in=self.norm_class,
                                             is_mnm=False).exclude(purchase_status=CO)


class ConfectioneryMilkReportView(BaseReportView):
    norm_class = ['E1', ]
    table_class = LicenseConfectioneryReportTable

    def get_queryset(self):
        date = datetime.datetime.now() - datetime.timedelta(days=30)
        is_expired = self.kwargs.get('status') == 'expired'
        if not is_expired:
            return self.model.objects.filter(license_expiry_date__gte=date,
                                             export_license__norm_class__norm_class__in=self.norm_class,
                                             is_mnm=True).exclude(purchase_status=CO)
        else:
            return self.model.objects.filter(license_expiry_date__lt=date,
                                             export_license__norm_class__norm_class__in=self.norm_class,
                                             is_mnm=True).exclude(purchase_status=CO)


class NamkeenReportView(BaseReportView):
    norm_class = ['E132', ]
    table_class = LicenseNamkeenReportTable


class TractorReportView(BaseReportView):
    norm_class = ['C969', ]
    table_class = LicenseTractorReportTable


class SteelReportView(BaseReportView):
    norm_class = ['C471', 'C460', 'C473']
    table_class = LicenseSteelReportTable


class GlassReportView(BaseReportView):
    norm_class = ['A3627', ]
    table_class = LicenseGlassReportTable


class PickleReportView(BaseReportView):
    norm_class = ['E126', ]
    table_class = LicensePickleReportTable


class PDFLedgerItemLicenseDetailView(PDFTemplateResponseMixin, DetailView):
    template_name = 'license/item_pdf.html'
    model = license.LicenseDetailsModel

    def get_object(self, queryset=None):
        return self.model.objects.get(license_number=self.kwargs.get('license'))


class ItemReportView(TemplateView):
    template_name = 'license/report.html'

    def get_context_data(self, **kwargs):
        context = super(ItemReportView, self).get_context_data()
        from core.models import ItemNameModel
        context['items'] = ItemNameModel.objects.filter(is_active=True).values('name', 'id')
        return context


class ItemListReportView(PDFTemplateResponseMixin, TemplateView):
    template_name = 'license/report_pdf_ITEM.html'
    model = license.LicenseDetailsModel

    def get_context_data(self, **kwargs):
        context = super(ItemListReportView, self).get_context_data()
        total_quantity = 0
        item = self.request.GET.get('item', None)
        title = item
        tables = item_filter(item=item)
        context['page_title'] = title
        context['tables'] = tables
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
        from license.tables import LicenseConfectioneryReportTable
        try:
            expiry_limit = datetime.datetime.strptime('2020-07-31', '%Y-%m-%d')
            start_limit = datetime.datetime.strptime('2020-02-29', '%Y-%m-%d')
            queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gte=expiry_limit,
                license_expiry_date__lte=start_limit,
                is_ge=True, is_au=False, balance_cif__gte=4000).order_by('license_expiry_date')
            queryset = check_query(queryset)
            table = LicenseConfectioneryReportTable(queryset)
            tables.append({'label': 'Confectinery', 'table': table})
            queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                  license_expiry_date__gte=expiry_limit,
                                                                  is_ge=True, is_au=False,
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
        from license.tables import LicenseConfectioneryReportTable
        from license.models import N2009
        try:
            expiry_limit = datetime.datetime.strptime('2020-02-29', '%Y-%m-%d')
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__gte=expiry_limit,
                is_ge=True, is_au=True, balance_cif__gte=5000).order_by('license_expiry_date')
            q_confectionery_queryset = confectionery_queryset
            table = LicenseConfectioneryReportTable(
                q_confectionery_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'AU Confectinery Active', 'table': table})
            confectionery_queryset = license.LicenseDetailsModel.objects.filter(
                export_license__norm_class__norm_class='E1',
                license_expiry_date__lt=expiry_limit,
                is_ge=True, is_au=True, balance_cif__gte=5000).order_by('license_expiry_date')
            q_confectionery_queryset = confectionery_queryset
            table = LicenseConfectioneryReportTable(
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
                                                                           is_ge=True, is_au=True,
                                                                           balance_cif__gte=4000).order_by(
                'license_expiry_date')

            q_biscuits_queryset = biscuits_queryset
            table = LicenseBiscuitReportTable(
                q_biscuits_queryset.filter(notification_number=N2009).distinct())
            tables.append({'label': 'AU Biscuits Active', 'table': table})
            biscuits_queryset = license.LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5',
                                                                           license_expiry_date__lt=expiry_limit,
                                                                           is_ge=True, is_au=True,
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


def analysis(requests):
    check_license()
    return HttpResponseRedirect(reverse('license-list'))


def WriteToExcel(weather_data, town=None):
    output = StringIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet_s = workbook.add_worksheet("Summary")
    title_text = "{0} {1}".format(gettext_lazy("Weather History for"), 'town_text')
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
    worksheet_s.write(4, 0, gettext_lazy("No"), header)
    worksheet_s.write(4, 1, gettext_lazy("Town"), header)
    worksheet_s.write(4, 3, gettext_lazy("Max T."), header)
    # Here we will adding the code to add data

    workbook.close()
    xlsx_data = output.getvalue()
    # xlsx_data contains the Excel file
    return xlsx_data


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
        estimation_dict = {'balance_cif': "1", 'palmolein': None, 'yeast': None, 'juice': None, 'cheese': None,
                           'wpc': None, 'gluten': None}
        items = ['gluten', 'palmolein', '2009', 'Dietary', 'milk', 'Packing Material']
        for item in items:
            import_item = dfia.import_license.filter(description__icontains=item)
            if import_item.first() and import_item.first().item:
                dict_data = fetch_item_details(import_item.first().item, import_item.first().hs_code.hs_code,
                                               dfia, item_name=item)
                dict_list.append(dict_data)
                estimation_dict[item] = {'balance_qty': dict_data['balance_qty']}
        context['item_list'] = dict_list
        estimation_list = []
        balance_value = dfia.export_license.all().first().balance_cif_fc()
        context['balance_cif_fc'] = balance_value
        et = 0
        for v in estimation_list:
            et = et + v['value']
        context['estimation_list'] = estimation_list
        context['estimation_total'] = et
        context['balance_value'] = balance_value
        return context


def calculate_balance(balance_value, ditem_dict, debits):
    if balance_value > ditem_dict['quantity'] * ditem_dict['unit_price']:
        ditem_dict['value'] = ditem_dict['quantity'] * ditem_dict['unit_price']
        debits = debits + ditem_dict['value']
        balance_value = balance_value - ditem_dict['quantity'] * ditem_dict['unit_price']
    else:
        ditem_dict['value'] = balance_value
        debits = debits + ditem_dict['value']
        ditem_dict['unit_price'] = balance_value / ditem_dict['quantity']
        balance_value = 0
    return debits, balance_value, ditem_dict


class RefreshItems(View):
    def get(self, request, *args, **kwargs):
        # Check if the 'run_task' parameter is present in the query string
        update_items.delay()  # Run the task in the background
        return redirect(reverse('dashboard'))  # Redirect back to the same page without parameters
