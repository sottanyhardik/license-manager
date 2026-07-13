from django.contrib import admin

from .models import MDSSyncState


@admin.register(MDSSyncState)
class MDSSyncStateAdmin(admin.ModelAdmin):
    list_display = ("model_label", "cursor", "etag", "changes_cursor", "last_synced_at")
    readonly_fields = ("updated_at",)
    search_fields = ("model_label",)
