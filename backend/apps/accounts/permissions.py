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


class CompanyPermission(BaseRolePermission):
    """
    Permission class for the Company master-data endpoint
    (`apps/core/views/views.py::CompanyViewSet`).

    Company records double as counterparty master data (name/address) *and*
    sensitive banking/PAN/GST fields, so — unlike the other master-data
    entities that share `MasterDataPermission` (ports, HS codes, item
    names, ...) — read access here is scoped to the roles that actually
    consume company data elsewhere in the app: license and ledger views,
    trade invoicing, bill-of-entry/accounts work, allotments, incentive
    licenses, reporting filters, and transfer-letter generation. This
    closes read access for accounts with no matching business role (e.g. a
    newly created user with no group assigned yet) while leaving every
    existing legitimate lookup (dropdowns, filters, the masters admin page)
    working exactly as before for the roles that already use it.

    Write access remains superuser-only, matching the existing behavior for
    every other master-data entity.
    """

    required_roles_for_read = [
        'LICENSE_MANAGER', 'LICENSE_VIEWER',
        'TRADE_MANAGER', 'TRADE_VIEWER',
        'BOE_MANAGER', 'BOE_VIEWER',
        'ALLOTMENT_MANAGER', 'ALLOTMENT_VIEWER',
        'INCENTIVE_LICENSE_MANAGER', 'INCENTIVE_LICENSE_VIEWER',
        'REPORT_VIEWER',
        'ACCOUNT_ACCESS',
        'TL_GENERATE',
    ]
    required_roles_for_write = []

    # SEC-02: of the roles above, only these four have a legitimate business
    # need to see banking/PAN/GST data (they manage the money/compliance side
    # of licenses, trade invoicing, and BOE/accounts work). Every other role
    # in `required_roles_for_read` can still read companies for id/name/
    # address lookups (dropdowns, filters, master-data listing) but must not
    # receive the sensitive fields — see
    # `CompanySerializer.SENSITIVE_FIELDS`/`to_representation` in
    # `apps/core/serializers/models.py`, which is the single enforcement
    # point for this narrowing.
    full_access_roles_for_sensitive_fields = [
        'LICENSE_MANAGER',
        'TRADE_MANAGER',
        'BOE_MANAGER',
        'ACCOUNT_ACCESS',
    ]


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
      - hiding/restoring a BOE (previous-owner utilisation, see
        `OTH_INVOICE_MARKER`) is a REAL financial mutation — unlike
        ignore/restore-warning, it changes what counts toward Balance CIF
        for every licence the BOE touches — so it follows the "require the
        write role for BOTH sides" convention above: touches the BOE
        itself AND recomputes every affected licence's own `LicenseBalance`
        /item caches (`update_license_flags`) — requires BOE_MANAGER *and*
        LICENSE_MANAGER.

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
        'recalculate': (['LICENSE_MANAGER'],),
        # Ignoring/restoring a warning is pure workflow bookkeeping (never
        # touches allocations/invoices/BOEs/allotments/balances — see
        # `IgnoredWarning`'s docstring), so it's gated more loosely than the
        # financial-mutation actions above: ANY manager role that already
        # has write access somewhere in this workspace ("Manage
        # Reconciliation" in product terms), not a specific AND-of-two.
        'ignore_warning': (['LICENSE_MANAGER', 'BOE_MANAGER', 'TRADE_MANAGER', 'ALLOTMENT_MANAGER'],),
        'restore_warning': (['LICENSE_MANAGER', 'BOE_MANAGER', 'TRADE_MANAGER', 'ALLOTMENT_MANAGER'],),
        # Hiding/restoring a BOE is a real financial mutation (changes
        # Balance CIF), unlike the pure-bookkeeping warning actions above —
        # gated as an explicit AND-of-two, same convention as the
        # allocation actions.
        'hide_boe': (['BOE_MANAGER'], ['LICENSE_MANAGER']),
        'restore_boe': (['BOE_MANAGER'], ['LICENSE_MANAGER']),
        'hide_boe_bulk': (['BOE_MANAGER'], ['LICENSE_MANAGER']),
        'restore_boe_bulk': (['BOE_MANAGER'], ['LICENSE_MANAGER']),
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
