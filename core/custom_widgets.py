from django_select2.forms import ModelSelect2MultipleWidget, ModelSelect2Widget

from core import models


class HSCodeWidget(ModelSelect2MultipleWidget):
    search_fields = ['hs_code__icontains', ]
    model = models.HSCodeModel


class HSCodeSingleWidget(ModelSelect2Widget):
    search_fields = ['hs_code__icontains', ]
    model = models.HSCodeModel


class NormWidget(ModelSelect2Widget):
    search_fields = ['item__name__icontains', 'norm_class__icontains']
    model = models.SionNormClassModel


class ItemWidget(ModelSelect2Widget):
    search_fields = ['name__icontains', ]
    model = models.ItemNameModel


class CompanyWidget(ModelSelect2Widget):
    search_fields = ['name__icontains', ]
    model = models.CompanyModel


class PortWidget(ModelSelect2Widget):
    search_fields = ['code__icontains', 'name__icontains']
    model = models.PortModel
