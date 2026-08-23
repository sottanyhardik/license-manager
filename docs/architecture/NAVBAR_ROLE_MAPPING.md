# Navigation Role-Based Access Control

## Overview
The primary `TopNav` and protected routes show or hide menu items based on the user's assigned roles. Superusers pass every frontend role check automatically. UI visibility is not the security boundary; backend DRF permission classes remain the source of truth for API access.

## Menu Item Visibility Rules

### Main Navigation Items

| Menu Item | Required Roles | Description |
|-----------|---------------|-------------|
| **Dashboard** | All authenticated users | Always visible for any logged-in user |
| **Licenses** | `LICENSE_MANAGER`, `LICENSE_VIEWER` | View/manage DFIA licenses |
| **Allotments** | `ALLOTMENT_MANAGER`, `ALLOTMENT_VIEWER` | View/manage license allotments |
| **Bill of Entry** | `BOE_MANAGER`, `BOE_VIEWER`, `TL_GENERATE`, `ACCOUNT_ACCESS` | View/manage bill of entries and role-specific BOE actions |
| **Trade In & Out** | `TRADE_MANAGER`, `TRADE_VIEWER` | View/manage trades |
| **Incentive Licenses** | `INCENTIVE_LICENSE_MANAGER`, `INCENTIVE_LICENSE_VIEWER` | View/manage RODTEP/ROSTL/MEIS licenses |
| **License Ledger** | `LICENSE_MANAGER`, `TRADE_MANAGER`, `TRADE_VIEWER`, `LEDGER_MANAGER` | View license ledger |
| **Ledger Upload** | `LICENSE_MANAGER`, `LEDGER_MANAGER` | Upload ledger files |
| **Settings** | Superuser only | User and role settings |
| **User Management** | `USER_MANAGER` | User CRUD and activity log |

### Dropdown Sections

#### Reports Dropdown
**Visible to:** `REPORT_VIEWER`, `LICENSE_MANAGER`, `LICENSE_VIEWER`, `TRADE_MANAGER`, `TRADE_VIEWER`, `ALLOTMENT_MANAGER`, `BOE_MANAGER`, `INCENTIVE_LICENSE_MANAGER`

Contains:
- SION reports
- Expiring and active license reports
- Download license report
- Item pivot and item reports

#### Masters Dropdown
**Visible to:** all authenticated users for read-only access.

Create, update, and delete routes are superuser-only in the frontend and are enforced by `MasterDataPermission` on the backend.

Contains:
- Companies
- Ports
- HS Codes
- Head Norms
- SION Classes
- Groups
- Item Names
- Exchange Rates

## How It Works

### Frontend Implementation

1. **AuthContext** provides `hasRole(roleCode)` and `hasAnyRole(roleCodes)` functions
   - Checks the user's `roles` array
   - Superusers automatically return `true` for any role check
   - Uses the `roles` array from `/api/auth/me/`

2. **TopNav Component** filters menu items
   - Domain navigation groups define allowed roles per item
   - Reports reuse `REPORT_ROLES` from `frontend/src/routes/authorizationRoles.ts`
   - Menu items are dynamically shown/hidden based on `hasAnyRole()`

3. **Route Protection** (`ProtectedRoute`)
   - Redirects to `/login` if not authenticated
   - Redirects to `/403` if user lacks required roles
   - Supports `requiredRole`, `requiredAnyRole`, and `requireSuperuser`

### Example User Scenarios

#### Scenario 1: License Viewer
**Assigned Roles:** `LICENSE_VIEWER`

**Can See:**
- Dashboard
- Licenses (view only - backend enforces read-only)
- Reports that include license data

**Cannot See:**
- Allotments, BOE, Trades, Incentive Licenses
- Settings and user management

#### Scenario 2: Trade Manager
**Assigned Roles:** `TRADE_MANAGER`, `TRADE_VIEWER`

**Can See:**
- Dashboard
- Trade In & Out (full CRUD access)
- License Ledger
- Reports dropdown
- Masters dropdown

**Cannot See:**
- Licenses, Allotments, BOE, Incentive Licenses (unless also assigned those roles)
- Settings (unless also `USER_MANAGER`)

#### Scenario 3: Full Manager
**Assigned Roles:** `LICENSE_MANAGER`, `ALLOTMENT_MANAGER`, `BOE_MANAGER`, `TRADE_MANAGER`, `INCENTIVE_LICENSE_MANAGER`, `REPORT_VIEWER`, `USER_MANAGER`

**Can See:**
- Everything in the navigation

#### Scenario 4: Superuser
**Status:** `is_superuser = true`

**Can See:**
- Everything (regardless of assigned roles)
- All permissions automatically granted

## Role Combinations for Common Use Cases

### Data Entry Clerk
```
Roles: LICENSE_VIEWER, BOE_VIEWER, ALLOTMENT_VIEWER, TRADE_VIEWER
Result: Can view all data but cannot modify
```

### Operations Manager
```
Roles: LICENSE_MANAGER, ALLOTMENT_MANAGER, BOE_MANAGER, TRADE_MANAGER, REPORT_VIEWER
Result: Full access to licenses, allotments, BOE, trades, and reports
```

### Accounts User (License Ledger Only)
```
Roles: ACCOUNT_ACCESS
Result: Can view BOE records and update BOE invoice numbers through the dedicated account-access API path
```

### Ledger User
```
Roles: LEDGER_MANAGER
Result: Can upload ledgers and view license ledger data
```

### System Administrator
```
Roles: USER_MANAGER + all other roles OR is_superuser=true
Result: Full system access including user management
```

## Testing Navigation Visibility

1. **Log in as user**
2. **Check TopNav** - only relevant menu items should be visible
3. **Try accessing restricted routes** - should redirect to 403
4. **Log in as superuser** - all menu items visible

## Updating Role Access

To change which roles can see a menu item:

1. Update route guards in `/frontend/src/routes/AppRoutes.tsx`.
2. Update matching navigation roles in `/frontend/src/components/TopNav.tsx`.
3. If the route is a report route, update `/frontend/src/routes/authorizationRoles.ts`.
4. Verify the backend permission class allows the same or stricter access.

Example:
```javascript
{
    path: "/licenses",
    label: "Licenses",
    roles: ["LICENSE_MANAGER", "LICENSE_VIEWER"],
    icon: "file-earmark-text",
}
```

## Backend Permission Enforcement

**Important:** Navigation visibility is only UI-level access control. Backend still enforces permissions:

- ViewSets use permission classes (e.g., `LicensePermission`)
- READ operations: Check viewer OR manager roles
- WRITE operations: Check only manager roles
- Superusers bypass all checks
- Generic master-data APIs use `MasterDataPermission`: authenticated users may read, only superusers may write

See `RBAC_DOCUMENTATION.md` for complete permission matrix.

## Troubleshooting

### Menu item not showing up
1. Check user has required role: `/api/auth/me/` → `roles`
2. Check role is active in database
3. Check `AppRoutes.tsx`, `TopNav.tsx`, and `authorizationRoles.ts` for correct role codes
4. Clear browser cache and re-login

### Menu item showing but getting 401/403
1. Backend permission class may be more restrictive
2. Check ViewSet permission classes match route roles
3. Verify JWT token is valid

### Superuser not seeing everything
1. Check `is_superuser=true` in database
2. Check `hasRole()` in AuthContext handles superusers
3. Clear localStorage and re-login

---

**Last Updated:** July 16, 2026
**Related Docs:** `RBAC_DOCUMENTATION.md`, `RBAC_SETUP_INSTRUCTIONS.md`
