# allotment/filters.py
"""
django-filters FilterSet for AllotmentModel.

Supports filtering by company, port, type, license_number (traverses FK to
allotment_details → item → license), boolean flags, and estimated_arrival_date
range. Produces a single JOIN-based queryset, no N+1.
"""
import django_filters

from apps.allotment.models import AllotmentModel


class AllotmentFilter(django_filters.FilterSet):
    company = django_filters.NumberFilter(field_name="company_id")
    port = django_filters.NumberFilter(field_name="port_id")
    type = django_filters.CharFilter(field_name="type", lookup_expr="exact")
    license_number = django_filters.CharFilter(
        field_name="allotment_details__item__license__license_number",
        lookup_expr="icontains",
    )
    is_boe = django_filters.BooleanFilter(field_name="is_boe")
    is_allotted = django_filters.BooleanFilter(field_name="is_allotted")
    is_approved = django_filters.BooleanFilter(field_name="is_approved")
    estimated_arrival_date_after = django_filters.DateFilter(
        field_name="estimated_arrival_date",
        lookup_expr="gte",
    )
    estimated_arrival_date_before = django_filters.DateFilter(
        field_name="estimated_arrival_date",
        lookup_expr="lte",
    )

    class Meta:
        model = AllotmentModel
        fields = ["company", "port", "type", "is_boe", "is_allotted", "is_approved"]
