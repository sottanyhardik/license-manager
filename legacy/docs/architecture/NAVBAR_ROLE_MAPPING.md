# Navigation Role-Based Access Control

## Overview
The sidebar navigation now shows/hides menu items based on the user's assigned roles. Superusers see all menu items automatically.

## Menu Item Visibility Rules

### Main Navigation Items

| Menu Item | Required Roles | Description |
|-----------|---------------|-------------|
| **Dashboard** | All authenticated users | Always visible for any logged-in user |
| **Licenses** | `LICENSE_MANAGER`, `LICENSE_VIEWER` | View/manage DFIA licenses |
| **Allotments** | `ALLOTMENT_MANAGER`, `ALLOTMENT_VIEWER` | View/manage license allotments |
| **Bill of Entry** | `BOE_MANAGER`, `BOE_VIEWER` | View/manage bill of entries |
| **Trade In & Out** | `TRADE_MANAGER`, `TRADE_VIEWER` | View/manage trades |
| **Incentive Licenses** | `INCENTIVE_LICENSE_MANAGER`, `INCENTIVE_LICENSE_VIEWER` | View/manage RODTEP/ROSTL/MEIS licenses |
| **License Ledger** | `TRADE_VIEWER`, `TRADE_MANAGER`, `LICENSE_MANAGER` | View license ledger |
| **Settings** | `USER_MANAGER` | User management and role assignment |

### Dropdown Sections

#### Reports Dropdown
**Visible to:** `REPORT_VIEWER`, `LICENSE_MANAGER`, `TRADE_MANAGER`, `ALLOTMENT_MANAGER`, `BOE_MANAGER`, `INCENTIVE_LICENSE_MANAGER`

Contains:
- Item Pivot Report
- Item Report

#### Masters Dropdown
**Visible to:** `USER_MANAGER`, `LICENSE_MANAGER`, `TRADE_MANAGER`, `ALLOTMENT_MANAGER`, `BOE_MANAGER`, `INCENTIVE_LICENSE_MANAGER`

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

1. **AuthContext** provides `hasRole(roleCodes)` function
   - Checks if user has any of the specified role codes
   - Superusers automatically return `true` for any role check
   - Uses `user.role_codes` array from API

2. **Sidebar Component** filters menu items
   - Each route has a `roles` array defining required roles
   - `hasRole()` is called to check if user can see the menu item
   - Menu items are dynamically shown/hidden based on user roles

3. **Route Protection** (RoleRoute component)
   - Redirects to `/login` if not authenticated
   - Redirects to `/401` if user lacks required roles
   - Uses the same `hasRole()` logic as navigation

### Example User Scenarios

#### Scenario 1: License Viewer
**Assigned Roles:** `LICENSE_VIEWER`

**Can See:**
- Dashboard
- Licenses (view only - backend enforces read-only)

**Cannot See:**
- Allotments, BOE, Trades, Incentive Licenses
- Reports, Masters, Settings

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
Roles: TRADE_VIEWER, LICENSE_MANAGER (or LICENSE_VIEWER with special permission)
Result: Can view license ledger and related trade data
```

### System Administrator
```
Roles: USER_MANAGER + all other roles OR is_superuser=true
Result: Full system access including user management
```

## Testing Navigation Visibility

1. **Log in as user**
2. **Check sidebar** - only relevant menu items should be visible
3. **Try accessing restricted routes** - should redirect to 401
4. **Log in as superuser** - all menu items visible

## Updating Role Access

To change which roles can see a menu item:

1. **Edit `/frontend/src/routes/config.js`**
2. **Update the `roles` array** for the route
3. **Frontend automatically updates** based on user's role_codes

Example:
```javascript
{
    path: "/licenses",
    label: "Licenses",
    roles: ["LICENSE_MANAGER", "LICENSE_VIEWER"], // ← Edit this array
    icon: "file-earmark-text",
}
```

## Backend Permission Enforcement

**Important:** Navigation visibility is only UI-level access control. Backend still enforces permissions:

- ViewSets use permission classes (e.g., `LicensePermission`)
- READ operations: Check viewer OR manager roles
- WRITE operations: Check only manager roles
- Superusers bypass all checks

See `RBAC_DOCUMENTATION.md` for complete permission matrix.

## Troubleshooting

### Menu item not showing up
1. Check user has required role: `/api/accounts/me/` → `role_codes`
2. Check role is active in database
3. Check `routes/config.js` for correct role codes
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

**Last Updated:** December 26, 2025
**Related Docs:** `RBAC_DOCUMENTATION.md`, `RBAC_SETUP_INSTRUCTIONS.md`
