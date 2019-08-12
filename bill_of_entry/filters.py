import datetime

import django_filters
from django.db import models
from django.forms import Select

from license import models as license_model
from allotment import models as allotment_model
from . import models as bill_of_entry

BOOLEAN_CHOICES = (
    (True, 'Yes'),
    (False, 'No')
)


class BillOfEntryFilter(django_filters.FilterSet):
    is_self = django_filters.BooleanFilter(method='check_self', label='All')

    class Meta:
        model = bill_of_entry.BillOfEntryModel
        fields = ['company', 'bill_of_entry_number','port','product_name','is_self']
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

    def check_self(self, queryset, name,value):
        return queryset.filter(item_details__sr_number__license__is_self=True).order_by('bill_of_entry_number').distinct('bill_of_entry_number')
