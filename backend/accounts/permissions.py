# accounts/permissions.py
from rest_framework import permissions


class BaseRolePermission(permissions.BasePermission):
    """Base class for role-based permissions"""

    required_roles_for_read = []
    required_roles_for_write = []

    def has_permission(self, request, view):
        # Superusers have all permissions
        if request.user and request.user.is_superuser:
            return True

        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Read permissions (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            if not self.required_roles_for_read:
                return True
            return request.user.has_any_role(self.required_roles_for_read)

        # Write permissions (POST, PUT, PATCH, DELETE)
        if not self.required_roles_for_write:
            return False
        return request.user.has_any_role(self.required_roles_for_write)


class LicensePermission(BaseRolePermission):
    """Permission class for License operations"""
    required_roles_for_read = ['LICENSE_MANAGER', 'LICENSE_VIEWER', 'TRADE_VIEWER', 'TRADE_MANAGER']
    required_roles_for_write = ['LICENSE_MANAGER']


class AllotmentPermission(BaseRolePermission):
    """Permission class for Allotment operations"""
    required_roles_for_read = ['ALLOTMENT_MANAGER', 'ALLOTMENT_VIEWER']
    required_roles_for_write = ['ALLOTMENT_MANAGER']


class BillOfEntryPermission(BaseRolePermission):
    """Permission class for Bill of Entry operations"""
    required_roles_for_read = ['BOE_MANAGER', 'BOE_VIEWER']
    required_roles_for_write = ['BOE_MANAGER']


class TradePermission(BaseRolePermission):
    """Permission class for Trade operations"""
    required_roles_for_read = ['TRADE_MANAGER', 'TRADE_VIEWER']
    required_roles_for_write = ['TRADE_MANAGER']


class IncentiveLicensePermission(BaseRolePermission):
    """Permission class for Incentive License operations"""
    required_roles_for_read = ['INCENTIVE_LICENSE_MANAGER', 'INCENTIVE_LICENSE_VIEWER']
    required_roles_for_write = ['INCENTIVE_LICENSE_MANAGER']


class UserManagementPermission(BaseRolePermission):
    """Permission class for User Management operations"""
    required_roles_for_read = ['USER_MANAGER']
    required_roles_for_write = ['USER_MANAGER']


class ReportPermission(BaseRolePermission):
    """Permission class for Report viewing"""
    required_roles_for_read = ['REPORT_VIEWER', 'LICENSE_MANAGER', 'TRADE_MANAGER', 'ALLOTMENT_MANAGER', 'BOE_MANAGER', 'INCENTIVE_LICENSE_MANAGER']
    required_roles_for_write = []


class LedgerUploadPermission(permissions.BasePermission):
    """Special permission for ledger upload - only LICENSE_MANAGER"""

    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.has_role('LICENSE_MANAGER')


class LicenseLedgerViewPermission(permissions.BasePermission):
    """Permission for viewing license ledger - TRADE_VIEWER and TRADE_MANAGER"""

    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.has_any_role(['TRADE_VIEWER', 'TRADE_MANAGER', 'LICENSE_MANAGER'])
