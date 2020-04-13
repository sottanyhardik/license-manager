from django import forms
from core import models as core_model, custom_widgets
from . import models as license_model


class ExportItemsForm(forms.ModelForm):
    norm_class = forms.ModelChoiceField(
        queryset=core_model.SionNormClassModel.objects.all(),
        widget=custom_widgets.NormWidget,
        required=False
    )

    item = forms.ModelChoiceField(
        queryset=core_model.ItemNameModel.objects.all(),
        widget=custom_widgets.ItemWidget,
        required=False
    )

    class Meta:
        model = license_model.LicenseExportItemModel
        fields = ['item', 'norm_class', 'duty_type', 'net_quantity', 'old_quantity','unit',
                  'fob_fc', 'fob_inr', 'currency', 'fob_exchange_rate', 'value_addition', 'cif_fc', 'cif_inr']

    def __init__(self, *args, **kwargs):
        super(ExportItemsForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'date' in field_name:
                field.widget.input_type = 'date'
            if field.widget.attrs.get('class'):
                field.widget.attrs['class'] += ' form-control'
            else:
                field.widget.attrs['class'] = 'form-control'
            if 'Textarea' in str(field.widget):
                field.widget.attrs['rows'] = '2'


class ImportItemsForm(forms.ModelForm):
    hs_code = forms.ModelChoiceField(
        queryset=core_model.HSCodeModel.objects.all(),
        widget=custom_widgets.HSCodeSingleWidget,
        required=False
    )

    item = forms.ModelChoiceField(
        queryset=core_model.ItemNameModel.objects.all(),
        widget=custom_widgets.ItemWidget,
        required=False
    )

    class Meta:
        model = license_model.LicenseImportItemsModel
        fields = ['serial_number', 'hs_code', 'item', 'quantity','old_quantity', 'cif_fc','comment']

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


class LicenseDetailsForm(forms.ModelForm):
    port = forms.ModelChoiceField(
        queryset=core_model.PortModel.objects.all(),
        widget=custom_widgets.PortWidget,
        required=False
    )
    exporter = forms.ModelChoiceField(
        queryset=core_model.CompanyModel.objects.all(),
        widget=custom_widgets.CompanyWidget,
        required=False
    )

    class Meta:
        model = license_model.LicenseDetailsModel
        fields = ['scheme_code', 'notification_number', 'license_number', 'license_date', 'license_expiry_date',
                  'file_number', 'exporter', 'port', 'registration_number', 'registration_date', 'user_restrictions',
                  'user_comment','is_self','is_au','user_comment']

    def __init__(self, *args, **kwargs):
        super(LicenseDetailsForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'date' in field_name:
                field.widget.input_type = 'date'
            if field.widget.attrs.get('class'):
                field.widget.attrs['class'] += ' form-control'
            else:
                field.widget.attrs['class'] = 'form-control'
            if 'Textarea' in str(field.widget):
                field.widget.attrs['rows'] = '2'


class LicenseDocumentForm(forms.ModelForm):

    class Meta:
        model = license_model.LicenseDocumentModel
        fields = ['license', 'type', 'file']

    def __init__(self, *args, **kwargs):
        super(LicenseDocumentForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'date' in field_name:
                field.widget.input_type = 'date'
            if field.widget.attrs.get('class'):
                field.widget.attrs['class'] += ' form-control'
            else:
                field.widget.attrs['class'] = 'form-control'
            if 'Textarea' in str(field.widget):
                field.widget.attrs['rows'] = '2'
