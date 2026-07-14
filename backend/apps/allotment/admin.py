from django.contrib import admin

from apps.allotment.models import AllotmentItems, AllotmentModel


@admin.register(AllotmentModel)
class AllotmentModelAdmin(admin.ModelAdmin):
    list_display = [
        "item_name",
        "company",
        "type",
        "required_quantity",
        "invoice",
        "estimated_arrival_date",
        "is_approved",
    ]
    list_filter = ["type", "is_boe", "is_allotted", "is_approved"]
    search_fields = ["item_name", "company__name", "invoice"]
    raw_id_fields = ["company", "port", "related_company"]


@admin.register(AllotmentItems)
class AllotmentItemsAdmin(admin.ModelAdmin):
    list_display = ["allotment", "item", "qty", "cif_fc", "cif_inr", "is_boe"]
    raw_id_fields = ["item", "allotment"]
