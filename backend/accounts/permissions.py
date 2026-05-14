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


class LicenseReadOnlyPermission(LicensePermission):
    """Same role set as LicensePermission, but every method (including POST)
    is treated as a read.

    Used for licence endpoints that are read-only by intent but require POST
    for payload-size reasons — e.g. bulk-balance-excel, which accepts a list
    of licence numbers in the request body."""

    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_any_role(self.required_roles_for_read)


class AllotmentPermission(BaseRolePermission):
    """Permission class for Allotment operations"""
    required_roles_for_read = ['ALLOTMENT_MANAGER', 'ALLOTMENT_VIEWER']
    required_roles_for_write = ['ALLOTMENT_MANAGER']


class BillOfEntryPermission(BaseRolePermission):
    """Permission class for Bill of Entry operations"""
    required_roles_for_read = ['BOE_MANAGER', 'BOE_VIEWER', 'ACCOUNT_ACCESS', 'TL_GENERATE']
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
    """Upload and manage ledger files — LICENSE_MANAGER or LEDGER_MANAGER."""

    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_any_role(['LICENSE_MANAGER', 'LEDGER_MANAGER'])


class LicenseLedgerViewPermission(permissions.BasePermission):
    """View license ledger — trade/license roles or LEDGER_MANAGER."""

    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_any_role([
            'TRADE_VIEWER', 'TRADE_MANAGER',
            'LICENSE_MANAGER', 'LEDGER_MANAGER',
        ])


class AccountAccessPermission(permissions.BasePermission):
    """
    Accounts team: read BOE list + update invoice_no only.
    All safe methods (GET) AND the dedicated update-invoice-no action are allowed.
    Full BOE create/edit/delete requires BOE_MANAGER.
    """
    _roles = ['ACCOUNT_ACCESS', 'BOE_MANAGER', 'BOE_VIEWER']

    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_any_role(self._roles)


class TransferLetterPermission(permissions.BasePermission):
    """
    Allows users who can generate transfer letters.
    Granted to: TL_GENERATE role, plus any entity manager/viewer role
    (since managers can already do everything, including generating TLs).
    """
    _allowed = [
        'TL_GENERATE',
        'BOE_MANAGER', 'BOE_VIEWER',
        'ALLOTMENT_MANAGER', 'ALLOTMENT_VIEWER',
        'TRADE_MANAGER', 'TRADE_VIEWER',
        'LICENSE_MANAGER',
    ]

    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_any_role(self._allowed)
