# RBAC Setup Instructions

## Current Implementation

RBAC is implemented with Django `Group` records. A group name is the role code, and user role assignment is stored in `accounts.User.groups`.

There is no custom `Role` model in the current codebase.

## Role Codes

Create groups with these exact names:

```text
USER_MANAGER
LICENSE_MANAGER
LICENSE_VIEWER
ALLOTMENT_MANAGER
ALLOTMENT_VIEWER
BOE_MANAGER
BOE_VIEWER
TRADE_MANAGER
TRADE_VIEWER
INCENTIVE_LICENSE_MANAGER
INCENTIVE_LICENSE_VIEWER
REPORT_VIEWER
TL_GENERATE
LEDGER_MANAGER
ACCOUNT_ACCESS
ACCOUNTS_VIEWER      # Accounting workspace (created by migration accounting/0003)
ACCOUNTS_MANAGER
ACCOUNTS_APPROVER
```

## Database Setup

Run migrations from the backend directory:

```bash
cd /Users/drushahardiksottany/PycharmProjects/license-manager/backend
python manage.py migrate
```

Create missing groups with Django shell if an environment does not already have them:

```python
from django.contrib.auth.models import Group

ROLE_CODES = [
    "USER_MANAGER",
    "LICENSE_MANAGER",
    "LICENSE_VIEWER",
    "ALLOTMENT_MANAGER",
    "ALLOTMENT_VIEWER",
    "BOE_MANAGER",
    "BOE_VIEWER",
    "TRADE_MANAGER",
    "TRADE_VIEWER",
    "INCENTIVE_LICENSE_MANAGER",
    "INCENTIVE_LICENSE_VIEWER",
    "REPORT_VIEWER",
    "TL_GENERATE",
    "LEDGER_MANAGER",
    "ACCOUNT_ACCESS",
]

for code in ROLE_CODES:
    Group.objects.get_or_create(name=code)
```

## Assign Roles

Assign roles through Django admin or shell:

```python
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()
user = User.objects.get(username="your_username")
groups = Group.objects.filter(name__in=["LICENSE_MANAGER", "REPORT_VIEWER"])
user.groups.set(groups)
print(user.get_role_codes())
```

Superusers bypass role checks **and** automatically belong to every role (2026-11-17):

- every existing superuser receives every existing role on each `migrate` (`post_migrate`);
- a newly created role is granted to every superuser;
- a newly created or promoted superuser receives every role;
- removing a role from a superuser (Django Admin, the user-management API, `groups.set()`) is re-granted on commit.

Only `is_superuser=True` users are affected. Ordinary users and `is_staff` admins keep exactly
the roles assigned to them, so give accounting users the `ACCOUNTS_*` role they need through
Users & Roles. Demoting a superuser does not strip their roles; remove them explicitly.
Paths that bypass model signals (`QuerySet.update(is_superuser=True)`, raw SQL, `loaddata`)
need `python manage.py sync_superuser_roles` (idempotent). Code: `apps/accounts/superuser_roles.py`,
`apps/accounts/signals.py`; tests: `apps/accounts/tests/test_superuser_role_automation.py`.

## Verify API Access

Get a token:

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"your_username","password":"your_password"}'
```

Check the current user snapshot:

```bash
curl http://localhost:8000/api/auth/me/ \
  -H "Authorization: Bearer $TOKEN"
```

List available role codes:

```bash
curl http://localhost:8000/api/auth/users/available-roles/ \
  -H "Authorization: Bearer $TOKEN"
```

`/api/auth/users/` requires `USER_MANAGER` or superuser access.

## Permission Classes

Use the existing permission classes from `apps.accounts.permissions`:

| Domain | Permission class |
|---|---|
| Licenses | `LicensePermission` |
| Read-only license POST exports | `LicenseReadOnlyPermission` |
| Allotments | `AllotmentPermission` |
| Bills of Entry | `BillOfEntryPermission` |
| Trades | `TradePermission` |
| Incentive Licenses | `IncentiveLicensePermission` |
| Users | `UserManagementPermission` |
| Reports | `ReportPermission` |
| Ledger Upload | `LedgerUploadPermission` |
| License Ledger | `LicenseLedgerViewPermission` |
| Accounts BOE workflows | `AccountAccessPermission` |
| Transfer Letters | `TransferLetterPermission` |

Example:

```python
from apps.accounts.permissions import LicensePermission

class LicenseViewSet(viewsets.ModelViewSet):
    permission_classes = [LicensePermission]
```

## Troubleshooting

| Problem | Check |
|---|---|
| Permission denied for a regular user | Confirm `user.is_active`, group names, group membership, and endpoint permission class. |
| User-management API denied | Assign `USER_MANAGER` or use a superuser. |
| Frontend menu item hidden | Confirm `/api/auth/me/` returns the role code in `roles`. |
| Role code not shown in UI | Confirm the code exists in `frontend/src/utils/roleConstants.js` and backend `/api/auth/users/available-roles/`. |
| Superuser denied | Confirm the token belongs to a user with `is_superuser=True`. |

## Checklist

- [ ] Run `python manage.py migrate`.
- [ ] Ensure all role-code groups exist.
- [ ] Assign `USER_MANAGER` to trusted administrators.
- [ ] Verify `/api/auth/me/` returns expected role codes.
- [ ] Verify protected API endpoints with representative viewer and manager users.
