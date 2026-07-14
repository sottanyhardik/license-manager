# license/filters.py
"""
FilterSet classes for the License module.

All filter lookups operate on database columns — no Python-side filtering.
Filters traverse relations using double-underscore paths; the ORM handles JOINs.
"""
from django_filters import BooleanFilter, CharFilter, DateFilter, FilterSet, NumberFilter

from apps.license.models import IncentiveLicense, LicenseDetailsModel


class LicenseFilter(FilterSet):
    """Filters for LicenseDetailsModel list endpoint."""

    license_type = CharFilter(field_name="scheme_code__code", lookup_expr="icontains")
    is_expired = BooleanFilter(field_name="flags__is_expired")
    is_active = BooleanFilter(field_name="flags__is_active")
    company = NumberFilter(field_name="exporter_id")
    expiry_before = DateFilter(field_name="license_expiry_date", lookup_expr="lte")
    expiry_after = DateFilter(field_name="license_expiry_date", lookup_expr="gte")
    license_number = CharFilter(field_name="license_number", lookup_expr="icontains")

    class Meta:
        model = LicenseDetailsModel
        fields = []


class IncentiveLicenseFilter(FilterSet):
    """Filters for IncentiveLicense list endpoint."""

    license_type = CharFilter(field_name="license_type", lookup_expr="iexact")
    is_active = BooleanFilter(field_name="is_active")
    company = NumberFilter(field_name="exporter_id")
    sold_status = CharFilter(field_name="sold_status", lookup_expr="iexact")
    expiry_before = DateFilter(field_name="license_expiry_date", lookup_expr="lte")
    expiry_after = DateFilter(field_name="license_expiry_date", lookup_expr="gte")
    license_number = CharFilter(field_name="license_number", lookup_expr="icontains")

    class Meta:
        model = IncentiveLicense
        fields = []
