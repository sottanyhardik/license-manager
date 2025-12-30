# FILE: accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "get_user_count", "created_at")
    list_filter = ("is_active", "code")
    search_fields = ("name", "code", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)

    fieldsets = (
        (None, {"fields": ("code", "name", "description")}),
        (_("Status"), {"fields": ("is_active",)}),
        (_("Metadata"), {"fields": ("created_at", "updated_at")}),
    )

    def get_user_count(self, obj):
        return obj.users.filter(is_active=True).count()
    get_user_count.short_description = "Active Users"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ("username", "email", "first_name", "last_name", "get_roles_display", "is_active")
    list_filter = ("roles", "is_staff", "is_active", "is_superuser")
    ordering = ("username",)
    search_fields = ("username", "email", "first_name", "last_name")
    filter_horizontal = ("roles", "groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email")}),
        (_("Roles"), {"fields": ("roles",)}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2", "roles", "is_active", "is_staff"),
        }),
    )

    def get_roles_display(self, obj):
        if obj.is_superuser:
            return "Superuser (All Roles)"
        roles = obj.roles.filter(is_active=True)
        return ", ".join([role.name for role in roles]) if roles else "No roles"
    get_roles_display.short_description = "Roles"
