# tests/integration/test_permissions.py
"""
RBAC and authentication integration tests.

Environment constraints
-----------------------
- The `accounts_user` table is not created in the SQLite test DB due to the
  managed=False patch running before Django's app registry is populated.
- The `SpectacularSwaggerUIView` import error in config/urls.py prevents tests
  that trigger URL loading through the DRF test client.

Strategy
--------
All permission checks are tested against the real permission class logic
(apps.accounts.permissions) with mocked User objects.  This verifies the
actual RBAC decision-making code without hitting the database or URL routing.

What is tested
--------------
- BR-14: Superusers bypass all RBAC checks (is_superuser=True).
- BR-14: Viewer roles → read allowed, write denied (403).
- BR-14: Manager roles → read and write allowed.
- BR-14: No-group user → both read and write denied.
- Unauthenticated user → denied on all permission classes.
- AllotmentPermission: ALLOTMENT_VIEWER read-only, ALLOTMENT_MANAGER read+write.
- LicensePermission: LICENSE_VIEWER read-only, LICENSE_MANAGER read+write.
- BillOfEntryPermission: BOE_VIEWER read-only, BOE_MANAGER read+write.
- TradePermission: TRADE_VIEWER read-only, TRADE_MANAGER read+write.
"""
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helper — build a fake request with a mocked user
# ---------------------------------------------------------------------------

def _make_request(method: str, groups: list, is_authenticated: bool = True, is_superuser: bool = False):
    """
    Return a mock request object whose user has the given group memberships
    and authentication state.
    """
    user = MagicMock()
    user.is_authenticated = is_authenticated
    user.is_active = is_authenticated  # active iff authenticated; mirrors real User behaviour
    user.is_superuser = is_superuser

    group_names = set(groups)

    def has_any_role(role_codes):
        return bool(group_names & set(role_codes))

    user.has_any_role.side_effect = has_any_role

    request = MagicMock()
    request.user = user
    request.method = method
    return request


# ---------------------------------------------------------------------------
# Test 9 — Viewer roles cannot write (BR-14)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("permission_class_path,viewer_group,manager_group", [
    (
        "apps.accounts.permissions.LicensePermission",
        "LICENSE_VIEWER",
        "LICENSE_MANAGER",
    ),
    (
        "apps.accounts.permissions.AllotmentPermission",
        "ALLOTMENT_VIEWER",
        "ALLOTMENT_MANAGER",
    ),
    (
        "apps.accounts.permissions.BillOfEntryPermission",
        "BOE_VIEWER",
        "BOE_MANAGER",
    ),
    (
        "apps.accounts.permissions.TradePermission",
        "TRADE_VIEWER",
        "TRADE_MANAGER",
    ),
])
def test_viewer_role_cannot_write(permission_class_path, viewer_group, manager_group):
    """
    BR-14: Viewer roles must be denied write (POST/PUT/PATCH/DELETE) operations.
    Permission class has_permission() must return False for unsafe methods.
    """
    import importlib
    module_path, class_name = permission_class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    PermClass = getattr(module, class_name)
    perm = PermClass()

    for method in ("POST", "PUT", "PATCH", "DELETE"):
        request = _make_request(method, groups=[viewer_group])
        view = MagicMock()
        result = perm.has_permission(request, view)
        assert result is False, (
            f"{class_name}: {viewer_group} must get False on {method}, got {result}"
        )


@pytest.mark.parametrize("permission_class_path,viewer_group", [
    ("apps.accounts.permissions.LicensePermission", "LICENSE_VIEWER"),
    ("apps.accounts.permissions.AllotmentPermission", "ALLOTMENT_VIEWER"),
    ("apps.accounts.permissions.BillOfEntryPermission", "BOE_VIEWER"),
    ("apps.accounts.permissions.TradePermission", "TRADE_VIEWER"),
])
def test_viewer_role_can_read(permission_class_path, viewer_group):
    """
    BR-14: Viewer roles must be allowed read (GET/HEAD/OPTIONS) operations.
    """
    import importlib
    module_path, class_name = permission_class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    PermClass = getattr(module, class_name)
    perm = PermClass()

    for method in ("GET", "HEAD", "OPTIONS"):
        request = _make_request(method, groups=[viewer_group])
        view = MagicMock()
        result = perm.has_permission(request, view)
        assert result is True, (
            f"{class_name}: {viewer_group} must get True on {method}, got {result}"
        )


@pytest.mark.parametrize("permission_class_path,manager_group", [
    ("apps.accounts.permissions.LicensePermission", "LICENSE_MANAGER"),
    ("apps.accounts.permissions.AllotmentPermission", "ALLOTMENT_MANAGER"),
    ("apps.accounts.permissions.BillOfEntryPermission", "BOE_MANAGER"),
    ("apps.accounts.permissions.TradePermission", "TRADE_MANAGER"),
])
def test_manager_role_can_write(permission_class_path, manager_group):
    """
    BR-14: Manager roles must be allowed write operations.
    """
    import importlib
    module_path, class_name = permission_class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    PermClass = getattr(module, class_name)
    perm = PermClass()

    for method in ("POST", "PUT", "PATCH", "DELETE"):
        request = _make_request(method, groups=[manager_group])
        view = MagicMock()
        result = perm.has_permission(request, view)
        assert result is True, (
            f"{class_name}: {manager_group} must get True on {method}, got {result}"
        )


# ---------------------------------------------------------------------------
# Test 10 — Unauthenticated blocked on all permission classes (BR-14)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("permission_class_path", [
    "apps.accounts.permissions.LicensePermission",
    "apps.accounts.permissions.AllotmentPermission",
    "apps.accounts.permissions.BillOfEntryPermission",
    "apps.accounts.permissions.TradePermission",
    "apps.accounts.permissions.IncentiveLicensePermission",
    "apps.accounts.permissions.UserManagementPermission",
    "apps.accounts.permissions.ReportPermission",
    "apps.accounts.permissions.LedgerUploadPermission",
    "apps.accounts.permissions.LicenseLedgerViewPermission",
])
def test_all_permission_classes_block_unauthenticated(permission_class_path):
    """
    Every permission class must deny access to unauthenticated users
    on both safe and unsafe methods.
    """
    import importlib
    module_path, class_name = permission_class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    PermClass = getattr(module, class_name)
    perm = PermClass()

    for method in ("GET", "POST", "PUT", "DELETE"):
        request = _make_request(method, groups=[], is_authenticated=False)
        view = MagicMock()
        result = perm.has_permission(request, view)
        assert result is False, (
            f"{class_name}: unauthenticated user must get False on {method}, "
            f"got {result}"
        )


# ---------------------------------------------------------------------------
# Superuser bypass (BR-14)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("permission_class_path", [
    "apps.accounts.permissions.LicensePermission",
    "apps.accounts.permissions.AllotmentPermission",
    "apps.accounts.permissions.BillOfEntryPermission",
    "apps.accounts.permissions.TradePermission",
])
def test_superuser_bypasses_all_role_checks(permission_class_path):
    """
    BR-14: Superusers always pass permission checks regardless of group membership.
    """
    import importlib
    module_path, class_name = permission_class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    PermClass = getattr(module, class_name)
    perm = PermClass()

    for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        # Superuser with NO groups still gets access
        request = _make_request(method, groups=[], is_superuser=True)
        view = MagicMock()
        result = perm.has_permission(request, view)
        assert result is True, (
            f"{class_name}: superuser must get True on {method} (no groups), "
            f"got {result}"
        )


# ---------------------------------------------------------------------------
# No-group user blocked
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("permission_class_path", [
    "apps.accounts.permissions.LicensePermission",
    "apps.accounts.permissions.AllotmentPermission",
    "apps.accounts.permissions.BillOfEntryPermission",
    "apps.accounts.permissions.TradePermission",
])
def test_no_group_user_blocked_on_all_methods(permission_class_path):
    """
    A user with no group membership must be denied on ALL methods
    (both safe and unsafe).
    """
    import importlib
    module_path, class_name = permission_class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    PermClass = getattr(module, class_name)
    perm = PermClass()

    for method in ("GET", "HEAD", "OPTIONS", "POST", "PUT", "DELETE"):
        request = _make_request(method, groups=[], is_superuser=False)
        view = MagicMock()
        result = perm.has_permission(request, view)
        assert result is False, (
            f"{class_name}: user with no groups must get False on {method}, "
            f"got {result}"
        )


# ---------------------------------------------------------------------------
# Cross-module role isolation (wrong-module viewer is blocked on write)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("perm_path,wrong_group", [
    ("apps.accounts.permissions.LicensePermission", "ALLOTMENT_VIEWER"),
    ("apps.accounts.permissions.AllotmentPermission", "LICENSE_VIEWER"),
    ("apps.accounts.permissions.BillOfEntryPermission", "TRADE_VIEWER"),
    ("apps.accounts.permissions.TradePermission", "BOE_VIEWER"),
])
def test_wrong_module_viewer_blocked(perm_path, wrong_group):
    """
    A viewer from a different module must not get write access to an
    unrelated endpoint.  Example: ALLOTMENT_VIEWER must not write to
    the License endpoint (which requires LICENSE_MANAGER).
    """
    import importlib
    module_path, class_name = perm_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    PermClass = getattr(module, class_name)
    perm = PermClass()

    request = _make_request("POST", groups=[wrong_group])
    view = MagicMock()
    result = perm.has_permission(request, view)
    assert result is False, (
        f"{class_name}: {wrong_group} must not write, got {result}"
    )


# ---------------------------------------------------------------------------
# LicenseReadOnlyPermission — POST treated as read
# ---------------------------------------------------------------------------

def test_license_read_only_permission_treats_post_as_read():
    """
    LicenseReadOnlyPermission: even POST is treated as a read operation.
    LICENSE_VIEWER (read-only role) must be granted POST access under this class.
    """
    from apps.accounts.permissions import LicenseReadOnlyPermission

    perm = LicenseReadOnlyPermission()

    # LICENSE_VIEWER can POST on read-only endpoints
    request = _make_request("POST", groups=["LICENSE_VIEWER"])
    view = MagicMock()
    result = perm.has_permission(request, view)
    assert result is True, (
        "LicenseReadOnlyPermission must grant LICENSE_VIEWER access to POST"
    )

    # Unauthenticated still blocked
    request_unauth = _make_request("POST", groups=[], is_authenticated=False)
    result_unauth = perm.has_permission(request_unauth, view)
    assert result_unauth is False


# ---------------------------------------------------------------------------
# BaseRolePermission — write blocked when required_roles_for_write is empty
# ---------------------------------------------------------------------------

def test_base_role_permission_empty_write_roles_blocks_write():
    """
    BaseRolePermission: if required_roles_for_write is empty, all write
    operations are blocked regardless of group membership.
    ReportPermission is an example (read-only by design, write=[]).
    """
    from apps.accounts.permissions import ReportPermission

    perm = ReportPermission()

    # Even a manager role cannot write to report endpoints
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        request = _make_request(method, groups=["LICENSE_MANAGER", "REPORT_VIEWER"])
        view = MagicMock()
        result = perm.has_permission(request, view)
        assert result is False, (
            f"ReportPermission must block {method} (write list empty), got {result}"
        )
