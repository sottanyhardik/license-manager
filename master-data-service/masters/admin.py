from django.contrib import admin

from .models import Company, ExchangeRate, MasterChange, Port


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("iec", "name", "modified_on")
    search_fields = ("iec", "name")


@admin.register(Port)
class PortAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "modified_on")
    search_fields = ("code", "name")


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("date", "currency", "rate", "modified_on")
    list_filter = ("currency",)


@admin.register(MasterChange)
class MasterChangeAdmin(admin.ModelAdmin):
    list_display = ("at", "op", "model_label", "natural_key")
    list_filter = ("op", "model_label")
    search_fields = ("natural_key",)
