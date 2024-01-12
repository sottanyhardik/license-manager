from django.db.models import Q
import django_filters
from django.db import models
from django.forms import Select
from django_filters import DateFromToRangeFilter

from core.filter_helper import RangeWidget
from . import models as bill_of_entry

BOOLEAN_CHOICES = (
    (True, 'Yes'),
    (False, 'No')
)

from django_filters.fields import Lookup


class ListFilter(django_filters.Filter):
    def filter(self, queryset, value):
        if value:
            value_list = value.split(u',')
            queryset = queryset.filter(item_details__sr_number__license__license_number__in=value_list).distinct()
            return queryset
        elif value == "":
            return queryset
        else:
            return queryset


class BillOfEntryFilter(django_filters.FilterSet):
    is_self = django_filters.BooleanFilter(method='check_self', label='All')
    item_details__sr_number__license__license_number = ListFilter(
        field_name='item_details__sr_number__license__license_number', label='License Numbers')
    bill_of_entry_date = DateFromToRangeFilter(
        widget=RangeWidget(attrs={'placeholder': 'DD/MM/YYYY', 'format': 'dd/mm/yyyy', 'type': 'date'}))
    is_invoice = django_filters.BooleanFilter(method='check_is_invoice', label='Is Invoice')
    is_ooc = django_filters.BooleanFilter(method='check_is_ooc', label='Is OOC')
    bill_of_entry_number = ListFilter(
        field_name='bill_of_entry_number', label='BOE Numbers')

    class Meta:
        model = bill_of_entry.BillOfEntryModel
        fields = ['company', 'bill_of_entry_number', 'port', 'product_name', 'is_self',
                  'item_details__sr_number__license__license_number', 'appraisement']
        widgets = {
            'company': Select(attrs={'class': 'form-control'}),
        }
        filter_overrides = {
            models.CharField: {
                'filter_class': django_filters.CharFilter,
                'extra': lambda f: {
                    'lookup_expr': 'icontains',
                },
            },
            models.TextField: {
                'filter_class': django_filters.CharFilter,
                'extra': lambda f: {
                    'lookup_expr': 'icontains',
                },
            }
        }

    def check_self(self, queryset, name, value):
        return queryset.filter(item_details__sr_number__license__is_self=True).distinct()

    def check_is_invoice(self, queryset, name, value):
        if value:
            return queryset.exclude(invoice_no=None)
        else:
            return queryset.filter(invoice_no=None)

    def check_is_ooc(self, queryset, name, value):
        if value:
            return queryset.exclude(Q(ooc_date=None) | Q(ooc_date='N.A.'))
        else:
            return queryset.filter(Q(ooc_date=None) | Q(ooc_date='N.A.'))
