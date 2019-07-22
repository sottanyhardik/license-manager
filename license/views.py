import datetime

from django.http import HttpResponseRedirect
# Create your views here.
from django.urls import reverse
from django.views.generic import DetailView
from easy_pdf.views import PDFTemplateResponseMixin
from extra_views import CreateWithInlinesView, UpdateWithInlinesView, InlineFormSetFactory

from core.utils import PagedFilteredTableView
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