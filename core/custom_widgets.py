from django_select2.forms import ModelSelect2MultipleWidget, ModelSelect2Widget

from allotment.models import AllotmentModel
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


class HeadNormWidget(ModelSelect2Widget):
    search_fields = ['name__icontains', ]
    model = models.HeadSIONNormsModel


class ItemWidget(ModelSelect2Widget):
    search_fields = ['name__icontains', ]
    model = models.ItemNameModel


class CompanyWidget(ModelSelect2Widget):
    search_fields = ['name__icontains', ]
    model = models.CompanyModel


class AllotmentWidget(ModelSelect2Widget):
    search_fields = ['item_name__icontains', 'company__name__icontains']
    model = AllotmentModel


class PortWidget(ModelSelect2Widget):
    search_fields = ['code__icontains', 'name__icontains']
    model = models.PortModel
