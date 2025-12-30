# Debug 401 Error for jaymota

## Issue
User has roles assigned (visible in profile) but still getting 401 on `/licenses`

## Root Causes

### 1. Django Server Not Restarted
Permission classes are loaded at server startup. If you added `permission_classes` but didn't restart, they won't be active.

**Fix:**
```bash
# Kill Django server
pkill -f "python.*manage.py runserver"

# Start again
cd backend
python manage.py runserver
```

### 2. JWT Token Doesn't Include role_codes
The old JWT token in localStorage doesn't have the `role_codes` field that was added.

**Check:**
Open browser console and run:
```javascript
console.log(JSON.parse(localStorage.getItem('user')))
```

If `role_codes` is missing or empty, the user needs to log out and log in again.

**Fix:**
```javascript
// Clear localStorage
localStorage.clear()
// Then log in again
```

### 3. API /me/ Endpoint Not Updated
The `/api/auth/me/` endpoint needs to return `role_codes` in the response.

**Verify:**
```bash
# Check what /me/ returns
curl http://localhost:8000/api/auth/me/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Should include:
```json
{
  "role_codes": ["LICENSE_MANAGER", "LICENSE_VIEWER", ...]
}
```

## Quick Fix Steps

### Step 1: Restart Django Server
```bash
cd /Users/hardiksottany/PycharmProjects/license-manager/backend
pkill -f "python.*manage.py runserver"
python manage.py runserver
```

### Step 2: User Must Re-Login
1. Log out from frontend
2. Clear browser cache/localStorage (or use Incognito)
3. Log in again

### Step 3: Verify Token Has role_codes
After login, check browser console:
```javascript
JSON.parse(localStorage.getItem('user'))
```

Should show:
```json
{
  "id": 4,
  "username": "jaymota",
  "roles": [...],
  "role_codes": ["LICENSE_MANAGER", "LICENSE_VIEWER", ...]
}
```

## Testing

After restart and re-login, test:

```bash
# Get token from localStorage
TOKEN="your_token_here"

# Should work now
curl http://localhost:8000/api/licenses/ \
  -H "Authorization: Bearer $TOKEN"
```

## If Still Getting 401

Check if permission class is actually applied:

```python
# Django shell: python manage.py shell
from license.views.license import LicenseDetailsViewSet
print(LicenseDetailsViewSet.permission_classes)
# Should show: [<class 'accounts.permissions.LicensePermission'>]
```

Check if user's token is valid:

```python
from rest_framework_simplejwt.tokens import AccessToken
token = AccessToken("your_token_here")
print(token.payload)
```

Check if hasRole() function works:

```javascript
// Browser console
const user = JSON.parse(localStorage.getItem('user'))
console.log(user.role_codes)
// Should include: ["LICENSE_MANAGER", "LICENSE_VIEWER", ...]
```
