from django_filters import CharFilter, DateFilter, FilterSet, NumberFilter

from apps.trade.models import LicenseTrade


class TradeFilter(FilterSet):
    direction = CharFilter(field_name="direction", lookup_expr="iexact")
    license_type = CharFilter(field_name="license_type", lookup_expr="iexact")
    from_company = NumberFilter(field_name="from_company_id")
    to_company = NumberFilter(field_name="to_company_id")
    invoice_date_after = DateFilter(field_name="invoice_date", lookup_expr="gte")
    invoice_date_before = DateFilter(field_name="invoice_date", lookup_expr="lte")
    invoice_number = CharFilter(field_name="invoice_number", lookup_expr="icontains")

    class Meta:
        model = LicenseTrade
        fields = []
