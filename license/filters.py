import datetime

import django_filters
from django.db import models
from django.forms import Select

from . import models as lic_model

BOOLEAN_CHOICES = (
    (True, 'Yes'),
    (False, 'No')
)


class LicenseDetailFilter(django_filters.FilterSet):
    is_expired = django_filters.BooleanFilter(field_name='license_expiry_date', method='check_expired',
                                              label='Is Expired')
    is_individual = django_filters.BooleanFilter(method='check_individual', label='Is Individual')

    class Meta:
        model = lic_model.LicenseDetailsModel
        fields = ['license_number', 'import_license__item__name', 'exporter', 'is_audit', 'is_null']
        widgets = {
            'exporter': Select(attrs={'class': 'form-control'}),
            'is_audit': Select(attrs={'class': 'form-control'}),
            'is_null': Select(attrs={'class': 'form-control'}),
            'is_expired': Select(attrs={'class': 'form-control'}),
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

    def check_expired(self, queryset, name, value):
        from datetime import datetime, timedelta
        expirty_limit = datetime.today()
        if value:
            return queryset.filter(license_expiry_date__lt=expirty_limit)
        else:
            return queryset.filter(license_expiry_date__gte=expirty_limit)

    def check_individual(self, queryset, name, value):
        if value:
            return queryset.filter(import_license__item_details__cif_fc=.01).distinct()
        else:
            return queryset


class LicenseReportFilter(django_filters.FilterSet):
    is_expired = django_filters.BooleanFilter(field_name='license_expiry_date', method='check_expired',
                                              label='Is Expired')
    is_conversion = django_filters.BooleanFilter(method='check_conversion', label='Is Conversion')
    is_individual = django_filters.BooleanFilter(method='check_individual', label='Is Individual')

    class Meta:
        model = lic_model.LicenseDetailsModel
        fields = ['license_number', 'exporter', 'is_conversion', 'notification_number']
        widgets = {
            'exporter': Select(attrs={'class': 'form-control'}),
            'is_audit': Select(attrs={'class': 'form-control'}),
            'is_null': Select(attrs={'class': 'form-control'}),
            'is_expired': Select(attrs={'class': 'form-control'}),
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

    def check_expired(self, queryset, name, value):
        from datetime import datetime, timedelta
        expirty_limit = datetime.today()
        if value:
            return queryset.filter(license_expiry_date__lt=expirty_limit)
        else:
            return queryset.filter(license_expiry_date__gte=expirty_limit)

    def check_individual(self, queryset, name, value):
        if value:
            return queryset.filter(import_license__item_details__cif_fc=.01).distinct()
        else:
            return queryset

    def check_conversion(self, queryset, name, value):
        if value:
            return queryset.exclude(export_license__old_quantity=0).distinct()
        else:
            return queryset.filter(export_license__old_quantity=0).distinct()
