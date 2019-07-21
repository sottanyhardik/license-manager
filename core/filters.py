import django_filters
from django.db import models
from django_filters.widgets import BooleanWidget

from . import models as core_models


class CompanyFilter(django_filters.FilterSet):

    class Meta:
        model = core_models.CompanyModel
        fields = ('iec', 'name')
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


class SionNormClassFilter(django_filters.FilterSet):
    class Meta:
        model = core_models.SionNormClassModel
        fields = ('norm_class', 'item')
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


class HSNCodeFilter(django_filters.FilterSet):
    class Meta:
        model = core_models.HSCodeModel
        fields = ('hs_code', 'product_description')
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


class ItemFilter(django_filters.FilterSet):
    class Meta:
        model = core_models.ItemNameModel
        fields = ('name',)
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