from django.contrib import admin

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails


@admin.register(BillOfEntryModel)
class BillOfEntryAdmin(admin.ModelAdmin):
    list_display = [
        "bill_of_entry_number",
        "bill_of_entry_date",
        "company",
        "port",
        "invoice_no",
        "is_fetch",
    ]
    search_fields = ["bill_of_entry_number", "invoice_no"]
    list_filter = ["is_fetch", "bill_of_entry_date"]


@admin.register(RowDetails)
class RowDetailsAdmin(admin.ModelAdmin):
    list_display = [
        "bill_of_entry",
        "sr_number",
        "cif_inr",
        "cif_fc",
        "qty",
        "is_frozen",
        "is_dispute",
    ]
    list_filter = ["is_frozen", "is_dispute", "transaction_type"]
