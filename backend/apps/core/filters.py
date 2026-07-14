# core/filters.py
"""
django-filter FilterSet classes for core master models.

Each FilterSet maps query parameters to ORM lookups. Only the fields
relevant to common UI search/filter patterns are declared; additional
filtering is handled by DRF SearchFilter and OrderingFilter in the viewsets.
"""
import django_filters

from apps.core.models import (
    ActivityLog,
    CompanyModel,
    ExchangeRateModel,
    HSCodeModel,
    ItemGroupModel,
    ItemNameModel,
    PortModel,
    PurchaseStatus,
    SchemeCode,
    SionNormClassModel,
    TransferLetterModel,
    UnitPriceModel,
)


class CompanyFilter(django_filters.FilterSet):
    """Filter companies by name (case-insensitive contains) and IEC."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    iec = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = CompanyModel
        fields = ["name", "iec"]


class PortFilter(django_filters.FilterSet):
    """Filter ports by code (startswith) and name (icontains)."""

    code = django_filters.CharFilter(lookup_expr="istartswith")
    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = PortModel
        fields = ["code", "name"]


class HSCodeFilter(django_filters.FilterSet):
    """Filter HS codes by code prefix and description keyword."""

    code = django_filters.CharFilter(field_name="hs_code", lookup_expr="istartswith")
    description = django_filters.CharFilter(
        field_name="product_description", lookup_expr="icontains"
    )

    class Meta:
        model = HSCodeModel
        fields = ["code", "description"]


class SionNormClassFilter(django_filters.FilterSet):
    """Filter SION norm classes by norm_class code and active status."""

    norm_class = django_filters.CharFilter(lookup_expr="icontains")
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = SionNormClassModel
        fields = ["norm_class", "is_active"]


class ItemGroupFilter(django_filters.FilterSet):
    """Filter item groups by name."""

    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = ItemGroupModel
        fields = ["name"]


class ItemNameFilter(django_filters.FilterSet):
    """Filter item names by name, group, and active status."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    is_active = django_filters.BooleanFilter()
    group = django_filters.NumberFilter(field_name="group__id")

    class Meta:
        model = ItemNameModel
        fields = ["name", "is_active", "group"]


class ExchangeRateFilter(django_filters.FilterSet):
    """Filter exchange rates by date range."""

    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    date = django_filters.DateFilter()

    class Meta:
        model = ExchangeRateModel
        fields = ["date", "date_from", "date_to"]


class PurchaseStatusFilter(django_filters.FilterSet):
    """Filter purchase statuses by active flag."""

    is_active = django_filters.BooleanFilter()

    class Meta:
        model = PurchaseStatus
        fields = ["is_active"]


class SchemeCodeFilter(django_filters.FilterSet):
    """Filter scheme codes by code."""

    code = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = SchemeCode
        fields = ["code"]


class TransferLetterFilter(django_filters.FilterSet):
    """Filter transfer letters by name."""

    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = TransferLetterModel
        fields = ["name"]


class UnitPriceFilter(django_filters.FilterSet):
    """Filter unit prices by name and label."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    label = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = UnitPriceModel
        fields = ["name", "label"]


class ActivityLogFilter(django_filters.FilterSet):
    """Filter activity logs by user, action, module, and date range."""

    action = django_filters.CharFilter(lookup_expr="exact")
    module = django_filters.CharFilter(lookup_expr="icontains")
    username = django_filters.CharFilter(lookup_expr="icontains")
    timestamp_from = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="gte")
    timestamp_to = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="lte")

    class Meta:
        model = ActivityLog
        fields = ["action", "module", "username", "timestamp_from", "timestamp_to"]
