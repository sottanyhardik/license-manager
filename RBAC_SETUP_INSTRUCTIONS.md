# RBAC System - Setup Instructions

## ✅ What Has Been Implemented

A complete Role-Based Access Control (RBAC) system with:
- 12 predefined roles
- User-role many-to-many relationship
- 9 custom permission classes
- Complete REST API for role management
- Django admin integration
- Helper methods for permission checks

## 🚀 How to Apply to Your Database

### Step 1: Run Migrations

```bash
cd /Users/hardiksottany/PycharmProjects/license-manager/backend

# Activate your virtual environment (if using one)
# source venv/bin/activate

# Run migrations
python manage.py migrate accounts
```

This will:
1. Create the `Role` table
2. Remove the old `role` CharField from User
3. Add the `roles` ManyToMany relationship
4. Populate all 12 predefined roles

### Step 2: Verify Roles Were Created

```bash
python manage.py shell
```

```python
from accounts.models import Role

# Check all roles
roles = Role.objects.all()
for role in roles:
    print(f"{role.code}: {role.name}")

# Should show 12 roles
print(f"\nTotal roles: {roles.count()}")
```

### Step 3: Assign Roles to Existing Users (Optional)

If you have existing users, you can assign roles via Django admin or shell:

**Via Shell:**
```python
from accounts.models import User, Role

# Get a user
user = User.objects.get(username='your_username')

# Get roles
license_manager = Role.objects.get(code='LICENSE_MANAGER')
trade_viewer = Role.objects.get(code='TRADE_VIEWER')

# Assign roles
user.roles.add(license_manager, trade_viewer)

# Verify
print(user.get_role_codes())  # ['LICENSE_MANAGER', 'TRADE_VIEWER']
```

**Via Django Admin:**
1. Go to http://localhost:8000/admin/accounts/user/
2. Click on a user
3. In the "Roles" section, use the horizontal filter to select roles
4. Save

### Step 4: Test the API

```bash
# Get your JWT token first
curl -X POST http://localhost:8000/api/accounts/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"your_username","password":"your_password"}'

# Use the access token from response
export TOKEN="your_access_token_here"

# Check your roles
curl http://localhost:8000/api/accounts/me/ \
  -H "Authorization: Bearer $TOKEN"

# List all roles (requires USER_MANAGER role)
curl http://localhost:8000/api/accounts/roles/ \
  -H "Authorization: Bearer $TOKEN"
```

## 📋 12 Roles Quick Reference

| Role Code | Access |
|-----------|--------|
| `LICENSE_MANAGER` | Manage licenses + ledger upload |
| `LICENSE_VIEWER` | View licenses only |
| `ALLOTMENT_MANAGER` | Manage allotments |
| `ALLOTMENT_VIEWER` | View allotments only |
| `BOE_MANAGER` | Manage bill of entries |
| `BOE_VIEWER` | View bill of entries only |
| `TRADE_MANAGER` | Manage trades + view ledger |
| `TRADE_VIEWER` | View trades + ledger only |
| `INCENTIVE_LICENSE_MANAGER` | Manage incentive licenses |
| `INCENTIVE_LICENSE_VIEWER` | View incentive licenses only |
| `USER_MANAGER` | Manage users & assign roles |
| `REPORT_VIEWER` | View all reports |

## ⚠️ Important Notes

### Superusers
- Superusers (`is_superuser=True`) **automatically have ALL permissions**
- They bypass all role checks
- They get all 12 role codes when calling `user.get_role_codes()`

### Backwards Compatibility
- The old `role` field (CharField with 'admin', 'manager', 'accounts') has been **removed**
- Migration handles this automatically
- If you have code referencing `user.role`, you need to update it to use `user.roles` or `user.get_role_codes()`

### API Authentication
- All RBAC endpoints require JWT authentication
- Only users with `USER_MANAGER` role can manage users and roles
- Superusers can always manage users and roles

## 🔧 Next Steps - Apply Permissions to ViewSets

You need to add permission classes to your existing ViewSets. Here's how:

### Example: License ViewSet

**Before:**
```python
# license/views.py
from rest_framework import viewsets

class LicenseViewSet(viewsets.ModelViewSet):
    queryset = LicenseDetailsModel.objects.all()
    serializer_class = LicenseSerializer
    # No permission class - uses default IsAuthenticated
```

**After:**
```python
# license/views.py
from rest_framework import viewsets
from accounts.permissions import LicensePermission

class LicenseViewSet(viewsets.ModelViewSet):
    queryset = LicenseDetailsModel.objects.all()
    serializer_class = LicenseSerializer
    permission_classes = [LicensePermission]  # ✅ Added
```

### Permission Classes to Apply

Update these ViewSets in your codebase:

1. **License ViewSets** → `LicensePermission`
   - Files: `license/views*.py`
   - Import: `from accounts.permissions import LicensePermission`

2. **Allotment ViewSets** → `AllotmentPermission`
   - Files: `allotment/views*.py`
   - Import: `from accounts.permissions import AllotmentPermission`

3. **Bill of Entry ViewSets** → `BillOfEntryPermission`
   - Files: `bill_of_entry/views*.py`
   - Import: `from accounts.permissions import BillOfEntryPermission`

4. **Trade ViewSets** → `TradePermission`
   - Files: `trade/views*.py`
   - Import: `from accounts.permissions import TradePermission`

5. **Incentive License ViewSets** → `IncentiveLicensePermission`
   - Files: `license/views_incentive.py`
   - Import: `from accounts.permissions import IncentiveLicensePermission`

6. **Ledger Upload Endpoints** → `LedgerUploadPermission`
   - Special permission for ledger upload actions
   - Import: `from accounts.permissions import LedgerUploadPermission`

7. **License Ledger View** → `LicenseLedgerViewPermission`
   - Files: `license/views_actions.py` (download-ledger action)
   - Import: `from accounts.permissions import LicenseLedgerViewPermission`

### Example: Custom Action with Different Permission

```python
from rest_framework.decorators import action
from accounts.permissions import LedgerUploadPermission

class LicenseViewSet(viewsets.ModelViewSet):
    queryset = LicenseDetailsModel.objects.all()
    serializer_class = LicenseSerializer
    permission_classes = [LicensePermission]

    @action(detail=False, methods=['post'], url_path='upload-ledger',
            permission_classes=[LedgerUploadPermission])  # ✅ Override for this action
    def upload_ledger(self, request):
        # Only LICENSE_MANAGER can access this
        pass
```

## 🐛 Troubleshooting

### "Permission denied" for all requests
- Check if user has any roles assigned: `user.roles.all()`
- Verify roles are active: `user.roles.filter(is_active=True)`
- Check JWT token is valid and not expired
- Verify permission class is imported correctly

### Migrations fail
- Make sure you're in the backend directory
- Check virtual environment is activated
- Run: `python manage.py migrate accounts --fake-initial` (if needed)
- If still failing, check database connection

### Can't see roles in admin
- Clear browser cache
- Run: `python manage.py collectstatic`
- Restart Django server

### User has role but still can't access
- Check if role is active in database
- Verify ViewSet has correct permission class
- Check if there's a typo in role code
- Ensure JWT token is being sent in header

## 📚 Documentation

Full documentation available in `RBAC_DOCUMENTATION.md` including:
- Complete API reference
- Permission matrix
- Usage examples
- Frontend integration guide
- Security considerations

## ✨ Features

### Helper Methods on User Model

```python
# Check single role
if user.has_role('LICENSE_MANAGER'):
    print("User can manage licenses")

# Check multiple roles
if user.has_any_role(['TRADE_VIEWER', 'TRADE_MANAGER']):
    print("User can view trades")

# Get all role codes
role_codes = user.get_role_codes()
# Superuser: ['LICENSE_MANAGER', 'LICENSE_VIEWER', ..., 'REPORT_VIEWER']
# Regular user: ['LICENSE_MANAGER', 'REPORT_VIEWER']
```

### API Response Format

```json
{
  "id": 1,
  "username": "john_doe",
  "roles": [
    {
      "id": 1,
      "code": "LICENSE_MANAGER",
      "name": "License Manager",
      "description": "Can manage all license CRUD operations"
    }
  ],
  "role_codes": ["LICENSE_MANAGER", "REPORT_VIEWER"],
  "is_superuser": false
}
```

## 🎯 Quick Start Checklist

- [ ] Run migrations: `python manage.py migrate accounts`
- [ ] Verify 12 roles created in database
- [ ] Assign roles to existing users (via admin or shell)
- [ ] Test API endpoints with JWT token
- [ ] Update ViewSets to use permission classes
- [ ] Test permissions with different user roles
- [ ] Build frontend role management UI (optional)

## 💡 Tips

1. **Start with superuser** to test the system
2. **Assign USER_MANAGER** role to trusted admins first
3. **Test each role** before deploying to production
4. **Document role assignments** for your organization
5. **Use role_codes array** in frontend for UI visibility control

---

**Need Help?** Check `RBAC_DOCUMENTATION.md` for detailed examples and troubleshooting.
