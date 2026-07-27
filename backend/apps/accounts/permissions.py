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


class ReconciliationPermission(permissions.BasePermission):
    """
    Permission class for the BOE / Invoice Reconciliation panel.

    Reads span both trade and BOE data, so any role with view access to
    EITHER is sufficient. Writes (link/merge-boe/note/recalculate) mutate
    both trade records (boes M2M) and BOE records, so they require the
    write role for BOTH `TradePermission` and `BillOfEntryPermission`
    (TRADE_MANAGER *and* BOE_MANAGER) — matching the "reuse whichever
    permission classes already gate LicenseTradeViewSet/BillOfEntryViewSet"
    convention rather than inventing a new role.
    """
    read_roles = ['TRADE_MANAGER', 'TRADE_VIEWER', 'BOE_MANAGER', 'BOE_VIEWER', 'ACCOUNT_ACCESS', 'TL_GENERATE']
    write_roles_trade = ['TRADE_MANAGER']
    write_roles_boe = ['BOE_MANAGER']

    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return request.user.has_any_role(self.read_roles)

        return (
            request.user.has_any_role(self.write_roles_trade)
            and request.user.has_any_role(self.write_roles_boe)
        )


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


class LicenseBalanceLedgerPermission(permissions.BasePermission):
    """
    Permission class for the per-licence Balance & Financial Reconciliation
    Workspace (`apps/license/views/license_balance_ledger.py`).

    Read actions (view the ledger, download PDF/Excel, view audit log) accept
    any role with view access to license/BOE data — consistent with
    `LicensePermission`/`BillOfEntryPermission`'s read sets.

    Write actions are split by which two record types they mutate, mirroring
    `ReconciliationPermission`'s "require the write role for BOTH sides"
    convention rather than inventing a new role:
      - invoice<->BOE allocation (create/edit/reverse) touches a
        `LicenseTradeLine` (trade) and a `RowDetails` (BOE) — requires
        TRADE_MANAGER *and* BOE_MANAGER.
      - BOE<->allotment allocation touches a `RowDetails` (BOE) and an
        `AllotmentItems` (allotment) — requires BOE_MANAGER *and*
        ALLOTMENT_MANAGER.
      - marking/reversing an external (out-of-system) invoice link only
        touches the BOE side — requires BOE_MANAGER alone.
      - recalculation is licence-level — requires LICENSE_MANAGER.

    Backend enforcement is authoritative regardless of what the frontend
    hides — every `has_permission` check below runs independent of UI state.
    """

    read_roles = [
        'LICENSE_MANAGER', 'LICENSE_VIEWER',
        'BOE_MANAGER', 'BOE_VIEWER',
        'TRADE_MANAGER', 'TRADE_VIEWER',
        'ACCOUNT_ACCESS',
    ]

    # view.action -> required role set(s). A tuple of role-lists means ALL
    # lists must each be satisfied (AND-of-ORs); a single list means ANY
    # role in it is sufficient.
    write_action_roles = {
        'allocate_invoice_boe': (['TRADE_MANAGER'], ['BOE_MANAGER']),
        'edit_invoice_boe_allocation': (['TRADE_MANAGER'], ['BOE_MANAGER']),
        'reverse_invoice_boe_allocation': (['TRADE_MANAGER'], ['BOE_MANAGER']),
        'allocate_boe_allotment': (['BOE_MANAGER'], ['ALLOTMENT_MANAGER']),
        'edit_boe_allotment_allocation': (['BOE_MANAGER'], ['ALLOTMENT_MANAGER']),
        'reverse_boe_allotment_allocation': (['BOE_MANAGER'], ['ALLOTMENT_MANAGER']),
        'mark_external_invoice': (['BOE_MANAGER'],),
        'reverse_external_invoice': (['BOE_MANAGER'],),
        'recalculate': (['LICENSE_MANAGER'],),
    }

    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return request.user.has_any_role(self.read_roles)

        role_sets = self.write_action_roles.get(getattr(view, 'action', None))
        if role_sets is None:
            # Unknown/unmapped write action — deny by default rather than
            # silently allowing a new action nobody has gated yet.
            return False
        return all(request.user.has_any_role(roles) for roles in role_sets)
