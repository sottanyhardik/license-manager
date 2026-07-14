# core/admin.py
"""
Django admin registration for core master models.

All models are managed=False (tables owned by legacy), so admin provides
read/edit access to the shared PostgreSQL data without creating tables.
"""
from django.contrib import admin

from apps.core.models import (
    ActivityLog,
    CeleryTaskTracker,
    CompanyModel,
    ExchangeRateModel,
    HeadSIONNormsModel,
    HSCodeModel,
    InvoiceEntity,
    ItemGroupModel,
    ItemHeadModel,
    ItemNameModel,
    MasterChange,
    NotificationNumber,
    PortModel,
    ProductDescriptionModel,
    PurchaseStatus,
    SchemeCode,
    SIONExportModel,
    SIONImportModel,
    SionNormClassModel,
    SionNormCondition,
    SionNormNote,
    TransferLetterModel,
    UnitPriceModel,
)


@admin.register(CompanyModel)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("iec", "name", "gst_number", "contact_person")
    search_fields = ("iec", "name", "gst_number", "pan")
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(PortModel)
class PortAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(HSCodeModel)
class HSCodeAdmin(admin.ModelAdmin):
    list_display = ("hs_code", "product_description", "unit_price", "unit")
    search_fields = ("hs_code", "product_description")
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(HeadSIONNormsModel)
class HeadSIONNormsAdmin(admin.ModelAdmin):
    list_display = ("name", "created_on")
    search_fields = ("name",)
    readonly_fields = ("created_on", "modified_on")


@admin.register(SionNormClassModel)
class SionNormClassAdmin(admin.ModelAdmin):
    list_display = ("norm_class", "description", "is_active", "head_norm")
    list_filter = ("is_active",)
    search_fields = ("norm_class", "description")
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(ItemGroupModel)
class ItemGroupAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(ItemNameModel)
class ItemNameAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "is_active", "display_order")
    list_filter = ("is_active",)
    search_fields = ("name", "group__name")
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(ExchangeRateModel)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("date", "usd", "euro", "pound_sterling", "chinese_yuan")
    search_fields = ("date",)
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(InvoiceEntity)
class InvoiceEntityAdmin(admin.ModelAdmin):
    list_display = ("name", "gst_number", "bank_name")
    search_fields = ("name", "gst_number")


@admin.register(SchemeCode)
class SchemeCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "label")
    search_fields = ("code", "label")


@admin.register(NotificationNumber)
class NotificationNumberAdmin(admin.ModelAdmin):
    list_display = ("code", "label")
    search_fields = ("code", "label")


@admin.register(PurchaseStatus)
class PurchaseStatusAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "is_active", "display_order")
    list_filter = ("is_active",)
    search_fields = ("code", "label")


@admin.register(TransferLetterModel)
class TransferLetterAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(UnitPriceModel)
class UnitPriceAdmin(admin.ModelAdmin):
    list_display = ("name", "unit_price", "label")
    search_fields = ("name", "label")
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(ProductDescriptionModel)
class ProductDescriptionAdmin(admin.ModelAdmin):
    list_display = ("hs_code", "product_description")
    search_fields = ("product_description", "hs_code__hs_code")
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(SIONExportModel)
class SIONExportAdmin(admin.ModelAdmin):
    list_display = ("norm_class", "description", "quantity", "unit")
    search_fields = ("description",)
    readonly_fields = ("created_on", "modified_on")


@admin.register(SIONImportModel)
class SIONImportAdmin(admin.ModelAdmin):
    list_display = ("norm_class", "serial_number", "description", "quantity", "unit")
    search_fields = ("description",)
    readonly_fields = ("created_on", "modified_on")


@admin.register(SionNormNote)
class SionNormNoteAdmin(admin.ModelAdmin):
    list_display = ("sion_norm", "display_order", "note_text")
    search_fields = ("note_text",)
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(SionNormCondition)
class SionNormConditionAdmin(admin.ModelAdmin):
    list_display = ("sion_norm", "display_order", "condition_text")
    search_fields = ("condition_text",)
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(ItemHeadModel)
class ItemHeadAdmin(admin.ModelAdmin):
    list_display = ("name", "unit_rate", "is_restricted")
    search_fields = ("name",)
    readonly_fields = ("created_on", "modified_on", "created_by", "modified_by")


@admin.register(MasterChange)
class MasterChangeAdmin(admin.ModelAdmin):
    list_display = ("op", "model_label", "natural_key", "at")
    list_filter = ("op",)
    search_fields = ("model_label", "natural_key")
    readonly_fields = ("model_label", "natural_key", "op", "at")


@admin.register(CeleryTaskTracker)
class CeleryTaskTrackerAdmin(admin.ModelAdmin):
    list_display = ("task_name", "task_id", "status", "created_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("task_name", "task_id")
    readonly_fields = (
        "task_id",
        "task_name",
        "status",
        "args",
        "kwargs",
        "result",
        "traceback",
        "created_at",
        "started_at",
        "completed_at",
        "current",
        "total",
        "progress_message",
    )


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("username", "action", "module", "resource_id", "status_code", "timestamp")
    list_filter = ("action", "module")
    search_fields = ("username", "description", "module")
    readonly_fields = (
        "user",
        "username",
        "action",
        "module",
        "resource_id",
        "description",
        "endpoint",
        "method",
        "ip_address",
        "user_agent",
        "status_code",
        "extra",
        "timestamp",
    )
