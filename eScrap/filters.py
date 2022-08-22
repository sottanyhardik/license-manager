import django_filters
from django.db import models

from . import models as core_models


class LicenseCompanyFilter(django_filters.FilterSet):

    class Meta:
        model = core_models.CompanyLicenseModel
        fields = ('company__iec_number', 'license_no','scheme')
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