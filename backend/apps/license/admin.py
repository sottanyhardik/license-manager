# license/admin.py
"""
Django admin registrations for all License models.

managed=False models can still be registered in admin and are fully usable
when pointed at the production PostgreSQL database.  The admin surfaces
are read-only-safe — edits work only when the DB tables exist.
"""
from django.contrib import admin

from apps.license.models import (
    AlongWithModel,
    DateModel,
    IncentiveLicense,
    Invoice,
    InvoiceItem,
    LicenseBalance,
    LicenseDetailsModel,
    LicenseDocumentModel,
    LicenseExportItemModel,
    LicenseFlags,
    LicenseImportItemsModel,
    LicenseInwardOutwardModel,
    LicenseItemPlan,
    LicenseNotes,
    LicenseOwnership,
    LicensePurchase,
    LicenseTransferModel,
    OfficeModel,
    StatusModel,
)


@admin.register(LicenseDetailsModel)
class LicenseDetailsAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "license_number",
        "license_date",
        "license_expiry_date",
        "exporter",
        "scheme_code",
    ]
    search_fields = ["license_number", "file_number", "registration_number"]
    list_filter = ["scheme_code", "purchase_status"]
    raw_id_fields = ["exporter", "port", "scheme_code", "notification_number", "purchase_status"]


@admin.register(LicenseExportItemModel)
class LicenseExportItemAdmin(admin.ModelAdmin):
    list_display = ["id", "license", "item", "cif_fc", "fob_fc", "currency"]
    search_fields = ["license__license_number", "description"]
    raw_id_fields = ["license", "item", "norm_class"]


@admin.register(LicenseImportItemsModel)
class LicenseImportItemsAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "license",
        "serial_number",
        "quantity",
        "unit",
        "cif_fc",
        "available_quantity",
    ]
    search_fields = ["license__license_number", "description"]
    raw_id_fields = ["license", "hs_code"]


@admin.register(LicenseBalance)
class LicenseBalanceAdmin(admin.ModelAdmin):
    list_display = ["license_id", "balance_cif", "ledger_date"]
    search_fields = ["license__license_number"]


@admin.register(LicenseFlags)
class LicenseFlagsAdmin(admin.ModelAdmin):
    list_display = [
        "license_id",
        "is_active",
        "is_expired",
        "is_null",
        "is_audit",
        "is_incomplete",
    ]
    list_filter = ["is_active", "is_expired", "is_null"]
    search_fields = ["license__license_number"]


@admin.register(LicenseNotes)
class LicenseNotesAdmin(admin.ModelAdmin):
    list_display = ["license_id", "user_comment"]
    search_fields = ["license__license_number"]


@admin.register(LicenseOwnership)
class LicenseOwnershipAdmin(admin.ModelAdmin):
    list_display = ["license_id", "current_owner", "file_transfer_status", "last_ownership_fetch"]
    search_fields = ["license__license_number"]
    raw_id_fields = ["current_owner"]


@admin.register(LicenseDocumentModel)
class LicenseDocumentAdmin(admin.ModelAdmin):
    list_display = ["id", "license", "type", "file"]
    list_filter = ["type"]
    search_fields = ["license__license_number"]
    raw_id_fields = ["license"]


@admin.register(LicenseTransferModel)
class LicenseTransferAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "license",
        "from_company",
        "to_company",
        "transfer_status",
        "transfer_date",
    ]
    list_filter = ["transfer_status"]
    search_fields = ["license__license_number"]
    raw_id_fields = ["license", "from_company", "to_company"]


@admin.register(LicenseItemPlan)
class LicenseItemPlanAdmin(admin.ModelAdmin):
    list_display = ["id", "license", "import_item", "item_name", "planned_quantity", "planned_cif_fc"]
    search_fields = ["license__license_number"]
    raw_id_fields = ["license", "import_item", "item_name"]


@admin.register(LicensePurchase)
class LicensePurchaseAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "license",
        "invoice_number",
        "invoice_date",
        "mode",
        "cif_inr",
        "amount_inr",
    ]
    search_fields = ["license__license_number", "invoice_number", "supplier_pan"]
    list_filter = ["mode", "amount_source"]
    raw_id_fields = ["license", "purchasing_entity", "supplier"]


@admin.register(IncentiveLicense)
class IncentiveLicenseAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "license_number",
        "license_type",
        "exporter",
        "license_value",
        "balance_value",
        "sold_status",
        "is_active",
    ]
    list_filter = ["license_type", "sold_status", "is_active"]
    search_fields = ["license_number"]
    raw_id_fields = ["exporter", "port_code"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["id", "invoice_number", "invoice_date", "billing_mode", "total_amount"]
    search_fields = ["invoice_number", "to_company_name"]
    list_filter = ["billing_mode"]
    raw_id_fields = ["bills_of_entry", "from_entity"]


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ["id", "invoice", "license_no", "hs_code", "qty", "amount"]
    search_fields = ["invoice__invoice_number", "license_no"]
    raw_id_fields = ["invoice", "sr_number"]


@admin.register(StatusModel)
class StatusAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]


@admin.register(OfficeModel)
class OfficeAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]


@admin.register(AlongWithModel)
class AlongWithAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]


@admin.register(DateModel)
class DateAdmin(admin.ModelAdmin):
    list_display = ["id", "date"]


@admin.register(LicenseInwardOutwardModel)
class LicenseInwardOutwardAdmin(admin.ModelAdmin):
    list_display = ["id", "license", "date", "status", "office", "description"]
    search_fields = ["license__license_number", "description"]
    raw_id_fields = ["license", "date", "status", "office", "along_with"]
