from django import forms

from core import models as core_models
from allotment import models
from core import custom_widgets


class AllotmentForm(forms.ModelForm):
    company = forms.ModelChoiceField(
        queryset=core_models.CompanyModel.objects.all(),
        widget=custom_widgets.CompanyWidget,
        required=False
    )

    port = forms.ModelChoiceField(
        queryset=core_models.PortModel.objects.all(),
        widget=custom_widgets.PortWidget,
        required=False
    )

    class Meta:
        model = models.AllotmentModel
        fields = ['company', 'type', 'required_quantity', 'unit_value_per_unit', 'item_name', 'contact_person',
                  'contact_number', 'port','invoice','eta']

    def __init__(self, *args, **kwargs):
        super(AllotmentForm, self).__init__(*args, **kwargs)
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


class AROForm(forms.Form):
    from_company = forms.CharField(required=True)
    company = forms.CharField(required=True)
    mill_name = forms.CharField(required=True)
    company_address = forms.CharField( widget=forms.Textarea )
    mill_address = forms.CharField( widget=forms.Textarea )
    dgft_address = forms.CharField( widget=forms.Textarea )


class TlForm(forms.Form):
    tl_choice = forms.ModelChoiceField(
        queryset=core_models.TransferLetterModel.objects.all(),
        required=False
    )
    company = forms.CharField(required=True)
    company_address_line1 = forms.CharField( widget=forms.Textarea)
    company_address_line2 = forms.CharField(widget=forms.Textarea)
