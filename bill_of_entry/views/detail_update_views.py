from .common import (
    DetailView, UpdateView, UpdateWithInlinesView, InlineFormSetFactory,
    RowDetails, forms, bill_of_entry
)


class BillOfEntryDetailView(DetailView):
    template_name = 'bill_of_entry/card.html'
    model = bill_of_entry.BillOfEntryModel

    def get_object(self, queryset=None):
        return self.model.objects.get(bill_of_entry_number=self.kwargs.get('boe'))

    def get_context_data(self, **kwargs):
        context = super(BillOfEntryDetailView, self).get_context_data(**kwargs)
        context['important'] = 'show active'
        return context


class BillOfEntryLicenseImportItemInline(InlineFormSetFactory):
    model = bill_of_entry.RowDetails
    form_class = forms.ImportItemsForm
    factory_kwargs = {
        'extra': 0,
    }


class BillOfEntryUpdateDetailView(UpdateView):
    template_name = 'bill_of_entry/add.html'
    model = bill_of_entry.BillOfEntryModel
    form_class = forms.BillOfEntryForm

    def get_object(self, queryset=None):
        return self.model.objects.get(id=self.kwargs.get('pk'))

    def get_success_url(self):
        boe = self.object.bill_of_entry_number
        return reverse('bill-of-entry-ajax-list') + '?bill_of_entry_number=' + str(boe)


class BillOfEntryUpdateView(UpdateWithInlinesView):
    template_name = 'bill_of_entry/add.html'
    model = bill_of_entry.BillOfEntryModel
    fields = ()
    inlines = [BillOfEntryLicenseImportItemInline, ]

    def get_success_url(self):
        boe = self.object.bill_of_entry_number
        return reverse('bill-of-entry-ajax-list') + '?bill_of_entry_number=' + str(boe)

    def dispatch(self, request, *args, **kwargs):
        license = self.get_object()
        return super(BillOfEntryUpdateView, self).dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.model.objects.get(id=self.kwargs.get('pk'))

    def get_inlines(self):
        allotments = self.object.allotment.all()
        for allotment in allotments:
            if allotment.allotment_details.all().exists():
                for allotment_item in allotment.allotment_details.all():
                    if not RowDetails.objects.filter(bill_of_entry=self.object,
                                                     sr_number=allotment_item.item).exists():
                        row, created = RowDetails.objects.get_or_create(bill_of_entry=self.object,
                                                                        sr_number=allotment_item.item)
                        if not row.cif_inr or row.cif_inr == 0:
                            row.cif_inr = allotment_item.cif_inr
                        if not row.cif_fc or row.cif_fc == 0:
                            row.cif_fc = allotment_item.cif_fc
                        if (not row.cif_inr) or (row.qty == 0):
                            row.qty = allotment_item.qty
                        row.save()
                    allotment_item.is_boe = True
                    allotment_item.save()
        self.inlines = [BillOfEntryLicenseImportItemInline, ]
        return super(BillOfEntryUpdateView, self).get_inlines()
