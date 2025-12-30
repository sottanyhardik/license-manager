# Role-Based Access Control (RBAC) System Documentation

## Overview

The License Manager application implements a comprehensive Role-Based Access Control (RBAC) system with 12 predefined roles. Superusers automatically have all permissions.

## Predefined Roles

| # | Role Code | Role Name | Permissions |
|---|-----------|-----------|-------------|
| 1 | `LICENSE_MANAGER` | License Manager | Manage all license CRUD operations and access ledger upload |
| 2 | `LICENSE_VIEWER` | License Viewer | View all licenses (read-only) |
| 3 | `ALLOTMENT_VIEWER` | Allotment Viewer | View all allotments (read-only) |
| 4 | `ALLOTMENT_MANAGER` | Allotment Manager | Manage all allotment CRUD operations |
| 5 | `BOE_VIEWER` | Bill of Entry Viewer | View all bill of entries (read-only) |
| 6 | `BOE_MANAGER` | Bill of Entry Manager | Manage all bill of entry CRUD operations |
| 7 | `TRADE_VIEWER` | Trade Viewer | View all trades and license ledger (read-only) |
| 8 | `TRADE_MANAGER` | Trade Manager | Manage all trade CRUD operations and view license ledger |
| 9 | `INCENTIVE_LICENSE_MANAGER` | Incentive License Manager | Manage all incentive license CRUD operations |
| 10 | `INCENTIVE_LICENSE_VIEWER` | Incentive License Viewer | View all incentive licenses (read-only) |
| 11 | `USER_MANAGER` | User Manager | Access all user CRUD operations and role assignment |
| 12 | `REPORT_VIEWER` | Report Viewer | View all reports |

**Note:** Superusers have all roles assigned by default and bypass all permission checks.

## Architecture

### Models

#### Role Model (`accounts/models.py`)
```python
class Role(models.Model):
    code = models.CharField(max_length=50, unique=True, choices=ROLE_CODES)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

#### User Model Updates
- Removed old `role` CharField
- Added `roles` ManyToManyField to Role model
- Added helper methods:
  - `has_role(role_code)` - Check if user has a specific role
  - `has_any_role(role_codes)` - Check if user has any of the specified roles
  - `get_role_codes()` - Get list of all role codes assigned to the user

### Permission Classes (`accounts/permissions.py`)

All permission classes inherit from `BaseRolePermission`:
- `LicensePermission` - For license CRUD operations
- `AllotmentPermission` - For allotment CRUD operations
- `BillOfEntryPermission` - For BOE CRUD operations
- `TradePermission` - For trade CRUD operations
- `IncentiveLicensePermission` - For incentive license CRUD operations
- `UserManagementPermission` - For user management
- `ReportPermission` - For report viewing
- `LedgerUploadPermission` - Special permission for ledger upload (LICENSE_MANAGER only)
- `LicenseLedgerViewPermission` - For viewing license ledger

### API Endpoints

#### Role Management
```
GET    /api/accounts/roles/           - List all active roles
GET    /api/accounts/roles/{id}/      - Get role details
GET    /api/accounts/roles/all_codes/ - Get all role codes and names
```

#### User Management
```
GET    /api/accounts/users/                  - List all users
POST   /api/accounts/users/                  - Create new user
GET    /api/accounts/users/{id}/             - Get user details
PUT    /api/accounts/users/{id}/             - Update user
PATCH  /api/accounts/users/{id}/             - Partial update user
DELETE /api/accounts/users/{id}/             - Delete user
POST   /api/accounts/users/{id}/assign-roles/  - Assign roles to user
POST   /api/accounts/users/{id}/remove-roles/  - Remove roles from user
POST   /api/accounts/users/{id}/reset_password/ - Reset user password
```

#### User Authentication
```
GET    /api/accounts/me/  - Get current user info (includes role_codes)
```

## Usage Examples

### 1. Creating a User with Roles (API)

```bash
# Create user with LICENSE_MANAGER and REPORT_VIEWER roles
POST /api/accounts/users/
{
  "username": "john_doe",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "password": "secure_password",
  "role_ids": [1, 12],  # IDs of LICENSE_MANAGER and REPORT_VIEWER
  "is_active": true
}
```

### 2. Assigning Roles to Existing User

```bash
# Assign multiple roles to user
POST /api/accounts/users/5/assign-roles/
{
  "role_ids": [1, 7, 12]  # LICENSE_MANAGER, TRADE_VIEWER, REPORT_VIEWER
}
```

### 3. Removing Roles from User

```bash
# Remove specific roles
POST /api/accounts/users/5/remove-roles/
{
  "role_ids": [7]  # Remove TRADE_VIEWER
}
```

### 4. Checking User Roles in Code

```python
# In views or serializers
user = request.user

# Check for specific role
if user.has_role('LICENSE_MANAGER'):
    # User can manage licenses
    pass

# Check for any of multiple roles
if user.has_any_role(['TRADE_VIEWER', 'TRADE_MANAGER']):
    # User can view trades
    pass

# Get all role codes
role_codes = user.get_role_codes()
# For superuser: returns all 12 role codes
# For regular user: returns only assigned role codes
```

### 5. Using Permission Classes in ViewSets

```python
from accounts.permissions import LicensePermission

class LicenseViewSet(viewsets.ModelViewSet):
    queryset = LicenseDetailsModel.objects.all()
    serializer_class = LicenseSerializer
    permission_classes = [LicensePermission]
```

## Database Migrations

Three migrations have been created:

1. **0002_role_user_roles.py** - Creates Role model and updates User model
2. **0003_populate_roles.py** - Populates the 12 predefined roles

To apply migrations:
```bash
cd backend
source venv/bin/activate  # or activate your virtual environment
python manage.py migrate accounts
```

## Django Admin Interface

### Role Administration
- View all roles at `/admin/accounts/role/`
- See user count for each role
- Filter by code and active status
- Search by name, code, or description
- Cannot delete predefined roles (only deactivate)

### User Administration
- View/edit users at `/admin/accounts/user/`
- Assign multiple roles using horizontal filter widget
- See roles summary in user list
- Superusers automatically shown as having all roles

## Security Considerations

1. **Superuser Bypass**: Superusers automatically have all permissions regardless of assigned roles
2. **Role Hierarchy**: No role hierarchy is implemented - each role is independent
3. **Multiple Roles**: Users can have multiple roles simultaneously
4. **Inactive Roles**: Deactivated roles are not checked in permission validation
5. **API Security**: All endpoints require authentication via JWT tokens

## Permission Matrix

| Resource | Viewer Roles | Manager Roles |
|----------|-------------|---------------|
| Licenses | LICENSE_VIEWER, TRADE_VIEWER, TRADE_MANAGER | LICENSE_MANAGER |
| Allotments | ALLOTMENT_VIEWER | ALLOTMENT_MANAGER |
| Bill of Entry | BOE_VIEWER | BOE_MANAGER |
| Trades | TRADE_VIEWER, TRADE_MANAGER | TRADE_MANAGER |
| Incentive Licenses | INCENTIVE_LICENSE_VIEWER | INCENTIVE_LICENSE_MANAGER |
| Users & Roles | USER_MANAGER (read) | USER_MANAGER (write) |
| Reports | REPORT_VIEWER + All Manager Roles | - |
| Ledger Upload | - | LICENSE_MANAGER only |
| License Ledger | TRADE_VIEWER, TRADE_MANAGER, LICENSE_MANAGER | - |

## Frontend Integration

The `/api/accounts/me/` endpoint returns the current user's information including:
```json
{
  "id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "roles": [
    {
      "id": 1,
      "code": "LICENSE_MANAGER",
      "name": "License Manager",
      "description": "...",
      "is_active": true
    }
  ],
  "role_codes": ["LICENSE_MANAGER", "REPORT_VIEWER"],
  "is_active": true,
  "is_superuser": false,
  "date_joined": "2024-12-26T00:00:00Z"
}
```

Use `role_codes` array to control UI visibility:
```javascript
const userRoles = userData.role_codes;

// Show "Manage Licenses" button only for LICENSE_MANAGER
if (userRoles.includes('LICENSE_MANAGER')) {
  // Show button
}

// Show "View Trades" section for TRADE_VIEWER or TRADE_MANAGER
if (userRoles.includes('TRADE_VIEWER') || userRoles.includes('TRADE_MANAGER')) {
  // Show section
}
```

## Troubleshooting

### Issue: User can't access resources despite having role
**Solution**:
1. Check if role is active: `Role.objects.filter(code='ROLE_CODE', is_active=True)`
2. Check if user is active: `User.objects.filter(id=X, is_active=True)`
3. Verify permission class is applied to the ViewSet
4. Check if JWT token is being sent in Authorization header

### Issue: Migrations fail
**Solution**:
1. Backup database first
2. Run migrations in order: `python manage.py migrate accounts`
3. If migration conflict, use `--fake` flag carefully
4. Check for custom User model conflicts

### Issue: Superuser doesn't have access
**Solution**:
- Superusers should always have access. Check:
  1. `is_superuser=True` in database
  2. Permission classes use `request.user.is_superuser` check
  3. JWT token is valid and not expired

## Next Steps

1. **Apply Permissions to ViewSets**: Update all ViewSets in license, allotment, bill_of_entry, trade apps to use appropriate permission classes
2. **Frontend Role Management UI**: Create React components for role assignment interface
3. **Audit Logging**: Add logging for role changes and permission denials
4. **Role-based Dashboard**: Customize dashboard based on user roles
5. **Notification System**: Notify users when roles are assigned/removed

## Support

For questions or issues with the RBAC system, contact the development team or refer to the Django REST Framework permissions documentation.
