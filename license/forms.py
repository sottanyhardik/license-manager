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
        fields = ['item', 'norm_class', 'duty_type', 'net_quantity', 'old_quantity', 'unit',
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
                field.widget.attrs['rows'] = '1'


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
        fields = ['serial_number', 'hs_code', 'item','description', 'quantity', 'old_quantity', 'cif_fc', 'comment', 'is_restrict']

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
                field.widget.attrs['rows'] = '1'


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
                  'user_comment', 'purchase_status', 'is_au', 'is_not_registered', 'user_comment',
                  'ge_file_number','is_mnm','condition_sheet']

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
                field.widget.attrs['rows'] = '1'


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
                field.widget.attrs['rows'] = '1'


class LicenseInwardOutwardForm(forms.ModelForm):
    license = forms.ModelChoiceField(
        queryset=license_model.LicenseDetailsModel.objects.all(),
        widget=custom_widgets.LicenseWidget,
        required=False
    )
    copy = forms.BooleanField(initial=True, required=False)
    tl = forms.BooleanField(initial=True, required=False)
    status = forms.ModelChoiceField(
        queryset=license_model.StatusModel.objects.all(),
        initial=3
    )
    office = forms.ModelChoiceField(
        queryset=license_model.OfficeModel.objects.all(),
        initial=1
    )

    class Meta:
        model = license_model.LicenseInwardOutwardModel
        fields = ['date', 'license', 'status', 'office', 'description', 'amd_sheets_number', 'copy', 'annexure', 'tl',
                  'aro', 'along_with']

    def __init__(self, *args, **kwargs):
        super(LicenseInwardOutwardForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'date' in field_name:
                field.widget.input_type = 'date'
            if field.widget.attrs.get('class'):
                field.widget.attrs['class'] += ' form-control'
            else:
                field.widget.attrs['class'] = 'form-control'
            if 'Textarea' in str(field.widget):
                field.widget.attrs['rows'] = '1'
