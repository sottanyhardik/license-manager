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


class AllotmentItemFilter(django_filters.FilterSet):
    remove_expired = django_filters.BooleanFilter(field_name='license_expiry_date', method='check_expired',
                                                  label='Is Expired')
    remove_null = django_filters.BooleanFilter(method='remove_null_values', label='Remove Null')

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
            return queryset.filter(id__in=id)
        return queryset

    def check_expired(self, queryset, name, value):
        from datetime import datetime, timedelta
        expirty_limit = datetime.today() - timedelta(days=30)
        if value:
            return queryset.filter(license__license_expiry_date__lt=expirty_limit)
        else:
            return queryset.filter(license__license_expiry_date__gte=expirty_limit)


class AllotmentFilter(django_filters.FilterSet):
    allotment_details__item__license__license_number  = django_filters.CharFilter(label='License Number')
    is_be = django_filters.BooleanFilter(method='check_be', label='Is BOE')

    class Meta:
        model = allotment_model.AllotmentModel
        fields = ['type', 'company', 'item_name', 'allotment_details__item__license__license_number']
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

    def check_be(self, queryset, name, value):
        return queryset.exclude(bill_of_entry__isnull=value).distinct()
