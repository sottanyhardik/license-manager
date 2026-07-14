import django_filters

from apps.bill_of_entry.models import BillOfEntryModel


class BillOfEntryFilter(django_filters.FilterSet):
    bill_of_entry_number = django_filters.CharFilter(lookup_expr="icontains")
    company = django_filters.NumberFilter(field_name="company")
    port = django_filters.NumberFilter(field_name="port")
    bill_of_entry_date_after = django_filters.DateFilter(
        field_name="bill_of_entry_date", lookup_expr="gte"
    )
    bill_of_entry_date_before = django_filters.DateFilter(
        field_name="bill_of_entry_date", lookup_expr="lte"
    )
    is_fetch = django_filters.BooleanFilter()

    class Meta:
        model = BillOfEntryModel
        fields = ["company", "port", "is_fetch"]
