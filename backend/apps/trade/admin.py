from django.contrib import admin
from .models import LicenseTrade, LicenseTradeLine, IncentiveTradeLine, LicenseTradePayment


@admin.register(LicenseTrade)
class LicenseTradeAdmin(admin.ModelAdmin):
    list_display = [
        "id", "direction", "license_type", "invoice_number",
        "invoice_date", "from_company", "to_company", "total_amount",
    ]
    list_filter = ["direction", "license_type"]
    search_fields = ["invoice_number"]


admin.site.register(LicenseTradeLine)
admin.site.register(IncentiveTradeLine)
admin.site.register(LicenseTradePayment)
