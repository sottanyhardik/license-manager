# Backend Permissions Applied

## Summary
All ViewSets now have role-based permission classes applied. The 401 errors should be resolved after restarting the Django server.

## Applied Permission Classes

### 1. License Module
**File:** `backend/license/views/license.py`
- **ViewSet:** `LicenseDetailsViewSet`
- **Permission:** `LicensePermission`
- **Allows:**
  - Read: `LICENSE_MANAGER`, `LICENSE_VIEWER`
  - Write: `LICENSE_MANAGER` only

### 2. Incentive License Module
**File:** `backend/license/views_incentive.py`
- **ViewSet:** `IncentiveLicenseViewSetClass` → `IncentiveLicenseViewSet`
- **Permission:** `IncentiveLicensePermission`
- **Allows:**
  - Read: `INCENTIVE_LICENSE_MANAGER`, `INCENTIVE_LICENSE_VIEWER`
  - Write: `INCENTIVE_LICENSE_MANAGER` only

### 3. Allotment Module
**File:** `backend/allotment/views.py`
- **ViewSet:** `AllotmentViewSet`
- **Permission:** `AllotmentPermission`
- **Allows:**
  - Read: `ALLOTMENT_MANAGER`, `ALLOTMENT_VIEWER`
  - Write: `ALLOTMENT_MANAGER` only

### 4. Bill of Entry Module
**File:** `backend/bill_of_entry/views/boe.py`
- **ViewSet:** `BillOfEntryViewSet`
- **Permission:** `BillOfEntryPermission`
- **Allows:**
  - Read: `BOE_MANAGER`, `BOE_VIEWER`
  - Write: `BOE_MANAGER` only

### 5. Trade Module
**File:** `backend/trade/views.py`
- **ViewSet:** `LicenseTradeViewSet`
- **Permission:** `TradePermission`
- **Allows:**
  - Read: `TRADE_MANAGER`, `TRADE_VIEWER`
  - Write: `TRADE_MANAGER` only

## How Permissions Work

### Permission Class Structure
```python
class LicensePermission(BaseRolePermission):
    required_roles_for_read = ['LICENSE_MANAGER', 'LICENSE_VIEWER']
    required_roles_for_write = ['LICENSE_MANAGER']
```

### Permission Flow
1. **Request comes in** → ViewSet receives request
2. **Check authentication** → User must be logged in
3. **Check superuser** → If `is_superuser=True`, allow everything
4. **Check method** → GET/HEAD/OPTIONS = read, POST/PUT/PATCH/DELETE = write
5. **Check roles** → User must have ANY of the required roles
6. **Allow or deny** → Return 200 or 401/403

### Read vs Write Permissions
- **Read (Safe Methods):** GET, HEAD, OPTIONS
  - Allows both Manager and Viewer roles
  - Example: `LICENSE_MANAGER` or `LICENSE_VIEWER` can view licenses

- **Write (Unsafe Methods):** POST, PUT, PATCH, DELETE
  - Allows only Manager roles
  - Example: Only `LICENSE_MANAGER` can create/update/delete licenses

## Testing After Restart

### Step 1: Restart Django Server
```bash
# Kill the current server
pkill -f "python.*manage.py runserver"

# Start the server again
cd backend
python manage.py runserver
```

### Step 2: Test with Different Roles

#### Test License Viewer (Read-Only)
```bash
# Assign LICENSE_VIEWER role to user
# Expected: Can GET but cannot POST/PUT/DELETE

# Should work
curl http://localhost:8000/api/licenses/ \
  -H "Authorization: Bearer $TOKEN"

# Should fail with 403
curl -X POST http://localhost:8000/api/licenses/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

#### Test License Manager (Full Access)
```bash
# Assign LICENSE_MANAGER role to user
# Expected: Can do everything

# Should work
curl http://localhost:8000/api/licenses/ \
  -H "Authorization: Bearer $TOKEN"

# Should work
curl -X POST http://localhost:8000/api/licenses/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

#### Test No Role (No Access)
```bash
# User with no roles assigned
# Expected: 401 or 403 for all requests

# Should fail
curl http://localhost:8000/api/licenses/ \
  -H "Authorization: Bearer $TOKEN"
```

#### Test Superuser (All Access)
```bash
# User with is_superuser=true
# Expected: Can access everything regardless of assigned roles

# Should work for all endpoints
curl http://localhost:8000/api/licenses/ \
  -H "Authorization: Bearer $TOKEN"

curl http://localhost:8000/api/allotments/ \
  -H "Authorization: Bearer $TOKEN"

curl http://localhost:8000/api/trades/ \
  -H "Authorization: Bearer $TOKEN"
```

## Common Issues & Solutions

### Issue: Still getting 401 after adding permission classes
**Solution:**
1. Restart Django server (permissions are loaded at startup)
2. Clear user's JWT token and re-login
3. Check user has the required role assigned

### Issue: Superuser getting 401
**Solution:**
1. Verify `is_superuser=True` in database
2. Check permission class has superuser bypass:
   ```python
   def has_permission(self, request, view):
       if request.user and request.user.is_superuser:
           return True
   ```
3. Re-login to get fresh token

### Issue: Manager can't create/update
**Solution:**
1. Check user has MANAGER role, not just VIEWER role
2. Verify `required_roles_for_write` includes the manager role
3. Check request method is POST/PUT/PATCH, not GET

### Issue: Different error code (403 vs 401)
**Explanation:**
- **401 Unauthorized** = Not authenticated (no token or invalid token)
- **403 Forbidden** = Authenticated but lacks permission (wrong role)

## Verify Permissions Are Active

### Check Permission Class Is Loaded
```python
# Django shell: python manage.py shell
from license.views.license import LicenseDetailsViewSet
print(LicenseDetailsViewSet.permission_classes)
# Should show: [<class 'accounts.permissions.LicensePermission'>]
```

### Check User Roles
```python
# Django shell
from accounts.models import User
user = User.objects.get(username='testuser')
print(user.get_role_codes())
# Should show: ['LICENSE_VIEWER', ...]
```

### Check Permission Logic
```python
# Django shell
from accounts.models import User
from accounts.permissions import LicensePermission

user = User.objects.get(username='testuser')
perm = LicensePermission()

# Create mock request
class MockRequest:
    def __init__(self, user, method):
        self.user = user
        self.method = method

# Test read permission
req = MockRequest(user, 'GET')
result = perm.has_permission(req, None)
print(f"Read permission: {result}")

# Test write permission
req = MockRequest(user, 'POST')
result = perm.has_permission(req, None)
print(f"Write permission: {result}")
```

## Next Steps

1. **Restart Django server** to load new permission classes
2. **Assign roles to test users** via Settings page
3. **Test each module** with different roles
4. **Verify frontend** shows correct menus based on roles
5. **Check API responses** return proper status codes

---

**Important:** All changes are backward compatible. Superusers retain full access, and the permission system only applies to non-superuser accounts.

**Last Updated:** December 26, 2025
