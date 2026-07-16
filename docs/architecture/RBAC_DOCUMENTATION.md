# Role-Based Access Control (RBAC)

## Overview

License Manager uses Django's built-in `Group` model as the role store. A role code is the group name, and the custom `accounts.User` model keeps the standard `groups` many-to-many relationship with a non-conflicting related name.

Superusers bypass all role checks. For regular users, backend permission classes are the security boundary; frontend route and navigation guards only control visibility.

## Role Codes

| Role Code | Purpose |
|---|---|
| `USER_MANAGER` | Manage users and assign roles |
| `LICENSE_MANAGER` | Create, update, delete, and view licenses |
| `LICENSE_VIEWER` | View licenses |
| `ALLOTMENT_MANAGER` | Create, update, delete, and view allotments |
| `ALLOTMENT_VIEWER` | View allotments |
| `BOE_MANAGER` | Create, update, delete, and view bills of entry |
| `BOE_VIEWER` | View bills of entry |
| `TRADE_MANAGER` | Create, update, delete, and view trades |
| `TRADE_VIEWER` | View trades |
| `INCENTIVE_LICENSE_MANAGER` | Create, update, delete, and view incentive licenses |
| `INCENTIVE_LICENSE_VIEWER` | View incentive licenses |
| `REPORT_VIEWER` | View reports |
| `TL_GENERATE` | Generate transfer letters |
| `LEDGER_MANAGER` | Upload/manage ledger files and view license ledger |
| `ACCOUNT_ACCESS` | Accounts-team BOE access, including invoice-number workflows |

The available role-code list is exposed by `GET /api/auth/users/available-roles/`.

## User Model Helpers

`backend/apps/accounts/models.py` exposes helpers backed by `User.groups`:

```python
user.has_role("LICENSE_MANAGER")
user.has_any_role(["TRADE_VIEWER", "TRADE_MANAGER"])
user.get_role_codes()
```

These helpers query Django group names. There is no custom `Role` model, no role ID assignment API, and no active/inactive flag on roles in the current implementation.

## Permission Classes

All permission classes live in `backend/apps/accounts/permissions.py`.

| Class | Read Access | Write Access |
|---|---|---|
| `LicensePermission` | `LICENSE_MANAGER`, `LICENSE_VIEWER`, `TRADE_VIEWER`, `TRADE_MANAGER` | `LICENSE_MANAGER` |
| `LicenseReadOnlyPermission` | Same as `LicensePermission`; treats every method as read | Same as read |
| `AllotmentPermission` | `ALLOTMENT_MANAGER`, `ALLOTMENT_VIEWER` | `ALLOTMENT_MANAGER` |
| `BillOfEntryPermission` | `BOE_MANAGER`, `BOE_VIEWER`, `ACCOUNT_ACCESS`, `TL_GENERATE` | `BOE_MANAGER` |
| `TradePermission` | `TRADE_MANAGER`, `TRADE_VIEWER` | `TRADE_MANAGER` |
| `IncentiveLicensePermission` | `INCENTIVE_LICENSE_MANAGER`, `INCENTIVE_LICENSE_VIEWER` | `INCENTIVE_LICENSE_MANAGER` |
| `UserManagementPermission` | `USER_MANAGER` | `USER_MANAGER` |
| `ReportPermission` | `REPORT_VIEWER` and manager roles | None |
| `LedgerUploadPermission` | `LICENSE_MANAGER`, `LEDGER_MANAGER` | `LICENSE_MANAGER`, `LEDGER_MANAGER` |
| `LicenseLedgerViewPermission` | `TRADE_VIEWER`, `TRADE_MANAGER`, `LICENSE_MANAGER`, `LEDGER_MANAGER` | Same as read |
| `AccountAccessPermission` | `ACCOUNT_ACCESS`, `BOE_MANAGER`, `BOE_VIEWER` | Dedicated action-level handling |
| `TransferLetterPermission` | `TL_GENERATE` plus BOE, allotment, trade, and license roles | Same as read |

## API Endpoints

All endpoints are prefixed with `/api/`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/auth/me/` | Current user snapshot, including `roles` as role-code strings |
| `GET` | `/api/auth/users/` | List users |
| `POST` | `/api/auth/users/` | Create user |
| `GET` | `/api/auth/users/:id/` | Retrieve user |
| `PUT/PATCH` | `/api/auth/users/:id/` | Update user and role-code list |
| `DELETE` | `/api/auth/users/:id/` | Delete user |
| `POST` | `/api/auth/users/:id/reset-password/` | Reset a user's password |
| `GET` | `/api/auth/users/available-roles/` | Return supported role codes |

User-management endpoints require `USER_MANAGER` or superuser access.

## Request and Response Shape

User create/update accepts role codes, not role IDs:

```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure_password",
  "roles": ["LICENSE_MANAGER", "REPORT_VIEWER"],
  "is_active": true
}
```

The current-user endpoint returns `roles` as strings:

```json
{
  "id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "roles": ["LICENSE_MANAGER", "REPORT_VIEWER"],
  "is_active": true,
  "is_superuser": false,
  "date_joined": "2026-01-01T00:00:00Z"
}
```

## Frontend Integration

`AuthContext` reads the `roles` array from `/api/auth/me/` and exposes:

```ts
hasRole("LICENSE_MANAGER")
hasAnyRole(["TRADE_VIEWER", "TRADE_MANAGER"])
isSuperAdmin()
canManageUsers()
```

`ProtectedRoute`, `TopNav`, `CommandPalette`, and `PermissionGate` use these helpers for UI gating. Backend DRF permissions remain authoritative.

## Operational Notes

- Groups should be created with names that exactly match the role codes above.
- Assign roles through Django admin group membership, shell, or the `/api/auth/users/` management API.
- Use `python manage.py check_user_roles` to inspect users and group assignments.
- Use `python manage.py migrate_auth` for migration/repair workflows in environments that need auth data normalization.

## Troubleshooting

| Symptom | Checks |
|---|---|
| User cannot access a resource | Verify the user is active, the access token is valid, the expected group exists, and the user belongs to that group. |
| Frontend link is hidden | Verify `/api/auth/me/` returns the expected role code in `roles`, then check `TopNav`/route role mapping. |
| API returns 403 despite visible UI | Trust the backend result; compare the endpoint's DRF permission class with frontend route roles. |
| Superuser cannot access a resource | Verify `is_superuser=True`, token freshness, and that the endpoint uses the standard permission classes. |
