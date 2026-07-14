from rest_framework.permissions import BasePermission


class IsAuthenticatedAndActive(BasePermission):
    """
    Base RBAC permission: user must be authenticated and active.
    Subclass this and override `has_permission` / `has_object_permission`
    for role-specific checks.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active)


class IsAdminUser(IsAuthenticatedAndActive):
    """Allow access only to admin/staff users."""

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_staff
