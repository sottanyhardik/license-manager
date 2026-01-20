# Server 165.232.185.220 - FIXED ✅

## Issue Resolution Summary

### Problem
- Login API was returning **400 Bad Request** when accessed externally
- API worked on `http://165.232.185.220:8080/` but not on `http://165.232.185.220/`

### Root Cause
Django was running on **port 8080**, but nginx was configured to proxy to **port 8000**.

### Solution
Updated nginx configuration to proxy to the correct port (8080 instead of 8000).

---

## ✅ Current Working Configuration

### Server Details
- **IP:** 165.232.185.220
- **Domain:** license-tractor.duckdns.org
- **Protocol:** HTTP only (no SSL)
- **Django Port:** 8080
- **Nginx Port:** 80 (proxies to 8080)

### Login Credentials
- **Username:** `admin`
- **Password:** `admin@123`

### Working Endpoints
```bash
# Homepage
✅ http://165.232.185.220/

# Login API
✅ http://165.232.185.220/api/auth/login/
   POST with: {"username":"admin","password":"admin@123"}

# Admin Panel
✅ http://165.232.185.220/admin/

# Licenses API
✅ http://165.232.185.220/api/licenses/
   (requires authentication)
```

---

## Test Results

### Login API Test ✅
```bash
$ curl -s -X POST http://165.232.185.220/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin@123"}'

Response:
{
  "access": "eyJhbGc...",
  "refresh": "eyJhbGc...",
  "user": {
    "id": 1,
    "username": "admin",
    "email": null,
    "is_active": true,
    "is_superuser": true
  }
}
```

### Homepage Test ✅
```bash
$ curl -I http://165.232.185.220/

HTTP/1.1 200 OK
Server: nginx/1.24.0 (Ubuntu)
Content-Type: text/html
```

---

## Configuration Changes Made

### 1. Nginx Configuration Updated
**File:** `/etc/nginx/sites-available/license-manager`

**Changed:**
```nginx
# Before
proxy_pass http://127.0.0.1:8000;

# After
proxy_pass http://127.0.0.1:8080;
```

### 2. Django Environment (.env)
```bash
DEBUG=False
ALLOWED_HOSTS=127.0.0.1,localhost,165.232.185.220,license-tractor.duckdns.org
DB_NAME=lmanagement
DB_USER=lmanagement
DB_PASS=lmanagement
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
```

---

## Service Status

```bash
✅ license-manager           RUNNING
✅ license-manager-celery    RUNNING
✅ license-manager-celery-beat RUNNING
✅ nginx                     ACTIVE
✅ postgresql                ACTIVE
✅ redis                     ACTIVE
```

---

## Usage Examples

### Login and Get Token
```bash
curl -X POST http://165.232.185.220/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin@123"}'
```

### Access Protected API with Token
```bash
# Get token first
TOKEN=$(curl -s -X POST http://165.232.185.220/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin@123"}' | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['access'])")

# Use token to access API
curl http://165.232.185.220/api/licenses/ \
  -H "Authorization: Bearer $TOKEN"
```

### Access from Browser
```
1. Navigate to: http://165.232.185.220/
2. Login with: admin / admin@123
3. Access all features
```

---

## Verification Commands

### Check Nginx Configuration
```bash
ssh django@165.232.185.220
echo 'admin' | sudo -S nginx -t
echo 'admin' | sudo -S systemctl status nginx
```

### Check Application Status
```bash
ssh django@165.232.185.220
echo 'admin' | sudo -S supervisorctl status
```

### Check Django Port
```bash
ssh django@165.232.185.220
echo 'admin' | sudo -S ss -tlnp | grep python
# Should show port 8080
```

### Test Login Locally
```bash
ssh django@165.232.185.220
curl -s -X POST http://localhost:8080/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin@123"}' | grep access
```

---

## Troubleshooting

### If Login Stops Working

1. **Check Django is running on port 8080:**
```bash
ssh django@165.232.185.220
echo 'admin' | sudo -S ss -tlnp | grep :8080
```

2. **Check nginx is proxying to 8080:**
```bash
ssh django@165.232.185.220
echo 'admin' | sudo -S cat /etc/nginx/sites-available/license-manager | grep proxy_pass
# Should show: proxy_pass http://127.0.0.1:8080;
```

3. **Restart services:**
```bash
ssh django@165.232.185.220
echo 'admin' | sudo -S supervisorctl restart license-manager
echo 'admin' | sudo -S systemctl reload nginx
```

### If Port 8080 Changes to 8000

If Django switches back to port 8000, update nginx:
```bash
ssh django@165.232.185.220
echo 'admin' | sudo -S sed -i 's/127\.0\.0\.1:8080/127.0.0.1:8000/g' /etc/nginx/sites-available/license-manager
echo 'admin' | sudo -S nginx -t
echo 'admin' | sudo -S systemctl reload nginx
```

---

## Summary

✅ **Server:** 165.232.185.220
✅ **Status:** Fully operational
✅ **Protocol:** HTTP (port 80)
✅ **Django:** Running on port 8080
✅ **Nginx:** Proxying 80 → 8080
✅ **Login API:** Working
✅ **Frontend:** Loading
✅ **All Services:** Running

**Access the application at:** http://165.232.185.220/
**Login with:** admin / admin@123
