import datetime
import io
from django.http import FileResponse
from reportlab.pdfgen import canvas
from easy_pdf.views import PDFTemplateResponseMixin
from core.utils import PagedFilteredTableView
from license import models as license
from license import filters
from license import tables


class PDFBReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFBReportView, self).get_context_data()
        context['today_date'] = datetime.datetime.now().date()
        from license.item_report import biscuit_2019_rama_rani
        tables = biscuit_2019_rama_rani()
        context['tables'] = tables
        return context


class PDFCReportView(PDFTemplateResponseMixin, PagedFilteredTableView):
    template_name = 'license/report_pdf.html'
    model = license.LicenseDetailsModel
    table_class = tables.LicenseBiscuitReportTable
    filter_class = filters.LicenseReportFilter
    context_object_name = 'license_list'

    def get_context_data(self, **kwargs):
        context = super(PDFCReportView, self).get_context_data()
        from license.item_report import confectinery_2019_rama_rani
        tables = confectinery_2019_rama_rani()
        context['today_date'] = datetime.datetime.now().date()
        context['tables'] = tables
        return context
