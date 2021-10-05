import datetime

import django_filters
from django.db import models
from django.forms import Select

from license import models as license_model
from allotment import models as allotment_model

BOOLEAN_CHOICES = (
    (True, 'Yes'),
    (False, 'No')
)


class ListFilter(django_filters.Filter):
    def filter(self, queryset, value):
        if value == "":
            return queryset
        value_list = value.split(u',')
        queryset = queryset.filter(allotment_details__item__license__license_number__in=value_list).distinct()
        return queryset


class AllotmentItemFilter(django_filters.FilterSet):
    remove_expired = django_filters.BooleanFilter(field_name='license_expiry_date', method='check_expired',
                                                  label='Is Expired')
    remove_null = django_filters.BooleanFilter(method='remove_null_values', label='Remove Null')
    license__license_number = ListFilter(field_name='license__license_number', label='License Numbers')

    class Meta:
        model = license_model.LicenseImportItemsModel
        fields = ['license__license_number', 'item__name', 'license__notification_number',
                  'license__export_license__norm_class']
        widgets = {
            'license__notification_number': Select(attrs={'class': 'form-control'}),
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

    def remove_null_values(self, queryset, name, value):
        if value:
            id = []
            for row in queryset:
                if row.balance_quantity > 100 and row.balance_cif_fc > 100:
                    id.append(row.id)
                elif row.balance_quantity > 100 and row.balance_cif_fc == 0.01:
                    id.append(row.id)
                    print(row.balance_cif_fc)
            return queryset.filter(id__in=id)
        return queryset

    def check_expired(self, queryset, name, value):
        from datetime import datetime, timedelta
        expiry_limit = datetime.today() - timedelta(days=30)
        if value:
            return queryset.filter(license__license_expiry_date__lt=expiry_limit)
        else:
            return queryset.filter(license__license_expiry_date__gte=expiry_limit)


class AllotmentFilter(django_filters.FilterSet):
    allotment_details__item__license__license_number = ListFilter(field_name='allotment_details__item__license__license_number', label='License Numbers')
    is_be = django_filters.BooleanFilter(method='check_be', label='Is BOE', initial=False)

    class Meta:
        model = allotment_model.AllotmentModel
        fields = ['type', 'company', 'item_name', 'allotment_details__item__license__license_number','port']
        widgets = {
            'company': Select(attrs={'class': 'form-control'}),
            'type': Select(attrs={'class': 'form-control'}),
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

    def __init__(self, data=None, *args, **kwargs):
        # if filterset is bound, use initial values as defaults
        if data is not None:
            # get a mutable copy of the QueryDict
            data = data.copy()

            for name, f in self.base_filters.items():
                initial = f.extra.get('initial')

                # filter param is either missing or empty, use initial as default
                if not data.get(name) and initial:
                    data[name] = initial

        super().__init__(data, *args, **kwargs)

    def check_be(self, queryset, name, value):
        return queryset.exclude(bill_of_entry__isnull=value).distinct()
