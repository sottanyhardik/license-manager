from django import forms

from core import models
from . import custom_widgets

class SIONExportForm(forms.ModelForm):
    hs_code = forms.ModelMultipleChoiceField(
        queryset=models.HSCodeModel.objects.all(),
        widget=custom_widgets.HSCodeWidget,
        required=False
    )

    item = forms.ModelChoiceField(
        queryset=models.ItemNameModel.objects.all(),
        widget=custom_widgets.ItemWidget,
        required=False
    )

    class Meta:
        model = models.SIONExportModel
        fields = ['item', 'quantity', 'unit', 'hs_code']

    def __init__(self, *args, **kwargs):
        super(SIONExportForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'date' in field_name:
                field.widget.input_type = 'date'
            if field.widget.attrs.get('class'):
                field.widget.attrs['class'] += ' form-control'
            else:
                field.widget.attrs['class'] = 'form-control'
            if 'Textarea' in str(field.widget):
                field.widget.attrs['rows'] = '2'


class SIONImportForm(forms.ModelForm):
    sr_no = forms.IntegerField(required=False)
    hs_code = forms.ModelMultipleChoiceField(
        queryset=models.HSCodeModel.objects.all(),
        widget=custom_widgets.HSCodeWidget,
        required=False
    )

    item = forms.ModelChoiceField(
        queryset=models.ItemNameModel.objects.all(),
        widget=custom_widgets.ItemWidget,
        required=False
    )

    class Meta:
        model = models.SIONImportModel
        fields = ['sr_no', 'item', 'quantity', 'unit', 'hs_code']

    def __init__(self, *args, **kwargs):
        super(SIONImportForm, self).__init__(*args, **kwargs)
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


class SionNormClassForm(forms.ModelForm):

    item = forms.ModelChoiceField(
        queryset=models.ItemNameModel.objects.all(),
        widget=custom_widgets.ItemWidget,
        required=False
    )

    head_norm = forms.ModelChoiceField(
        queryset=models.HeadSIONNormsModel.objects.all(),
        widget=custom_widgets.HeadNormWidget,
        required=False
    )

    class Meta:
        model = models.SionNormClassModel
        fields = ['head_norm', 'norm_class', 'item', 'url']

    def __init__(self, *args, **kwargs):
        super(SionNormClassForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'date' in field_name:
                field.widget.input_type = 'date'
            if field.widget.attrs.get('class'):
                field.widget.attrs['class'] += ' form-control'
            else:
                field.widget.attrs['class'] = 'form-control'
            if 'Textarea' in str(field.widget):
                field.widget.attrs['rows'] = '2'
