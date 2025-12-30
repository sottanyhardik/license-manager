# Quick Role Testing Guide

## Test the Role-Based Navigation

### Step 1: Assign Roles to Test User

Go to Settings → User Management → Click "Manage Roles" button

Or via API:
```bash
# Get your auth token
TOKEN="your_jwt_token"

# Assign specific roles to a user (example: user ID 2)
curl -X POST http://localhost:8000/api/auth/users/2/assign-roles/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role_ids": [2, 4, 6]
  }'

# Role IDs:
# 1 = LICENSE_MANAGER
# 2 = LICENSE_VIEWER
# 3 = ALLOTMENT_VIEWER
# 4 = ALLOTMENT_MANAGER
# 5 = BOE_VIEWER
# 6 = BOE_MANAGER
# 7 = TRADE_VIEWER
# 8 = TRADE_MANAGER
# 9 = INCENTIVE_LICENSE_MANAGER
# 10 = INCENTIVE_LICENSE_VIEWER
# 11 = USER_MANAGER
# 12 = REPORT_VIEWER
```

### Step 2: Test Navigation Visibility

#### Test Case 1: Viewer Only
**Assign:** `LICENSE_VIEWER` (ID: 2)

**Expected Sidebar:**
- ✅ Dashboard
- ✅ Licenses
- ❌ Allotments
- ❌ Bill of Entry
- ❌ Trades
- ❌ Incentive Licenses
- ❌ License Ledger
- ❌ Reports (dropdown)
- ❌ Masters (dropdown)
- ❌ Settings

#### Test Case 2: Trade Manager
**Assign:** `TRADE_MANAGER` + `TRADE_VIEWER` (IDs: 7, 8)

**Expected Sidebar:**
- ✅ Dashboard
- ❌ Licenses
- ❌ Allotments
- ❌ Bill of Entry
- ✅ Trade In & Out
- ❌ Incentive Licenses
- ✅ License Ledger
- ✅ Reports (dropdown)
- ✅ Masters (dropdown)
- ❌ Settings

#### Test Case 3: User Manager
**Assign:** `USER_MANAGER` (ID: 11)

**Expected Sidebar:**
- ✅ Dashboard
- ❌ Licenses
- ❌ Allotments
- ❌ Bill of Entry
- ❌ Trades
- ❌ Incentive Licenses
- ❌ License Ledger
- ❌ Reports
- ✅ Masters (dropdown)
- ✅ Settings

#### Test Case 4: All Manager Roles
**Assign:** All 5 manager roles (IDs: 1, 4, 6, 8, 9)

**Expected Sidebar:**
- ✅ Dashboard
- ✅ Licenses
- ✅ Allotments
- ✅ Bill of Entry
- ✅ Trade In & Out
- ✅ Incentive Licenses
- ✅ License Ledger
- ✅ Reports (dropdown)
- ✅ Masters (dropdown)
- ❌ Settings (unless also USER_MANAGER)

#### Test Case 5: Superuser
**Status:** `is_superuser=true`

**Expected Sidebar:**
- ✅ Everything visible

### Step 3: Test Route Protection

Try accessing URLs directly:

```bash
# Should work if user has LICENSE_VIEWER or LICENSE_MANAGER
http://localhost:5173/licenses

# Should redirect to /401 if user doesn't have role
http://localhost:5173/settings  # Requires USER_MANAGER

# Should work for everyone
http://localhost:5173/dashboard
```

### Step 4: Test Backend Permissions

#### Viewer Role (Read-Only)
```bash
# Should work - GET request
curl http://localhost:8000/api/licenses/ \
  -H "Authorization: Bearer $TOKEN"

# Should fail - POST request (403 Forbidden)
curl -X POST http://localhost:8000/api/licenses/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

#### Manager Role (Full CRUD)
```bash
# All operations should work
GET    /api/licenses/      ✅
POST   /api/licenses/      ✅
PUT    /api/licenses/1/    ✅
DELETE /api/licenses/1/    ✅
```

## Quick Assign All Roles Script

Create a test user with all roles:

```python
# Django shell: python manage.py shell
from accounts.models import User, Role

user = User.objects.get(username='testuser')
all_roles = Role.objects.filter(is_active=True)
user.roles.set(all_roles)

print(f"Assigned {all_roles.count()} roles to {user.username}")
print(f"Role codes: {user.get_role_codes()}")
```

## Common Issues

### Issue: Menu items not appearing after role assignment
**Solution:**
- Log out and log in again
- Clear browser localStorage
- Check `/api/accounts/me/` response includes new `role_codes`

### Issue: Can see menu but get 401 error
**Solution:**
- Backend permission class is more restrictive
- Check ViewSet has correct permission class applied
- Verify JWT token hasn't expired

### Issue: Superuser not seeing all menus
**Solution:**
- Verify `is_superuser=true` in database
- Check `hasRole()` function handles superusers correctly
- Re-login to refresh token

## Visual Confirmation

After logging in, check:

1. **Profile page** → Shows all assigned roles as badges
2. **Sidebar** → Only shows allowed menu items
3. **Settings page** → Shows roles in user table
4. **Browser console** → No permission errors

## Role Assignment via UI

1. Go to **Settings** (requires USER_MANAGER role)
2. Click **Manage Roles** icon (person-badge) on user row
3. Check/uncheck roles in modal
4. Click **Save Changes**
5. Ask user to log out and log in again
6. Verify sidebar changes

---

**Pro Tip:** Use incognito/private window for testing different user roles without logging out your admin session!
