from django import forms
from django_select2.forms import ModelSelect2Widget

from core import models as core_models
from bill_of_entry import models
from core import custom_widgets
from license import models as license_model


class LicenseSerialNumberWidget(ModelSelect2Widget):
    search_fields = ['license__license_number__icontains', ]
    model = license_model.LicenseImportItemsModel


class BillOfEntryForm(forms.ModelForm):
    company = forms.ModelChoiceField(
        queryset=core_models.CompanyModel.objects.all(),
        widget=custom_widgets.CompanyWidget,
        required=False
    )

    class Meta:
        model = models.BillOfEntryModel
        fields = ['company', 'bill_of_entry_number', 'bill_of_entry_date', 'port', 'exchange_rate', 'allotment',
                  'product_name','invoice_no']

    def __init__(self, *args, **kwargs):
        super(BillOfEntryForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'date' in field_name:
                field.widget.input_type = 'date'
            if field.widget.attrs.get('class'):
                field.widget.attrs['class'] += ' form-control'
            else:
                field.widget.attrs['class'] = 'form-control'
            if 'sr_no' in field_name:
                field.widget.attrs['class'] += ' span1'
            if 'quantity' in field_name:
                field.widget.attrs['class'] += ' span2'
            if 'unit' in field_name:
                field.widget.attrs['class'] += ' span2'
            if 'Textarea' in str(field.widget):
                field.widget.attrs['rows'] = '2'


class ImportItemsForm(forms.ModelForm):
    sr_number = forms.ModelChoiceField(
        queryset=license_model.LicenseImportItemsModel.objects.all(),
        widget=LicenseSerialNumberWidget,
        required=False
    )

    class Meta:
        model = models.RowDetails
        fields = ['sr_number', 'cif_inr', 'cif_fc', 'qty']

    def __init__(self, *args, **kwargs):
        super(ImportItemsForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'date' in field_name:
                field.widget.input_type = 'date'
            if field.widget.attrs.get('class'):
                field.widget.attrs['class'] += ' form-control'
            else:
                field.widget.attrs['class'] = 'form-control'
            if 'serial_number' in field_name:
                field.widget.attrs['class'] += ' span1'
            if 'hs_code' in field_name or 'quantity' in field_name or 'unit' in field_name:
                field.widget.attrs['class'] += ' span2'
            if 'Textarea' in str(field.widget):
                field.widget.attrs['rows'] = '2'


class BillOfEntryCaptcha(forms.Form):
    captcha = forms.CharField(max_length=30)
    cookies = forms.CharField(max_length=30)

    def clean(self):
        cleaned_data = super(BillOfEntryCaptcha, self).clean()
        captcha = cleaned_data.get('captcha')
        cookies = cleaned_data.get('cookies')
        if not captcha and not cookies:
            raise forms.ValidationError('ALL Fields Are Compulsory!')