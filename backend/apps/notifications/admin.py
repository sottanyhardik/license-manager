from django.contrib import admin

from apps.notifications.models import LicenseBalanceNotification


@admin.register(LicenseBalanceNotification)
class LicenseBalanceNotificationAdmin(admin.ModelAdmin):
    list_display = ["license", "status", "balance_cif", "created_at", "acknowledged_by", "resolved_by"]
    list_filter = ["status"]
    search_fields = ["license__license_number"]
    readonly_fields = ["created_at", "updated_at"]
