# Rate Limiting & Throttling Guide

## Overview

The License Manager API implements comprehensive rate limiting and throttling to protect against API abuse, ensure fair resource allocation, and maintain system stability. This guide covers all throttling features, configuration, and best practices.

## Table of Contents

1. [What is Rate Limiting?](#what-is-rate-limiting)
2. [Throttle Classes](#throttle-classes)
3. [Configuration](#configuration)
4. [Applying Throttling](#applying-throttling)
5. [Monitoring & Management](#monitoring--management)
6. [API Reference](#api-reference)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## What is Rate Limiting?

Rate limiting (throttling) controls the number of requests a user can make to the API within a specific time window. This helps:

- **Prevent Abuse**: Protects against DDoS attacks and malicious usage
- **Fair Resource Allocation**: Ensures all users get equal access to resources
- **System Stability**: Prevents server overload from excessive requests
- **Cost Control**: Reduces infrastructure costs from unnecessary API calls

### How It Works

1. Each request is tracked based on user identity (user ID or IP address)
2. Request count is stored in Redis cache with TTL
3. If limit is exceeded, API returns `429 Too Many Requests`
4. Response headers indicate rate limit status

---

## Throttle Classes

### 1. AnonRateThrottle

**Purpose**: Throttle anonymous (unauthenticated) users
**Rate**: 100 requests per hour
**Scope**: `anon`

```python
from core.throttling import AnonRateThrottle

class MyView(APIView):
    throttle_classes = [AnonRateThrottle]
```

**Use Cases**:
- Public endpoints (no authentication required)
- Registration pages
- Public reports

---

### 2. UserRateThrottle

**Purpose**: General throttle for authenticated users
**Rate**: 1000 requests per hour
**Scope**: `user`

```python
from core.throttling import UserRateThrottle

class MyViewSet(viewsets.ModelViewSet):
    throttle_classes = [UserRateThrottle]
```

**Use Cases**:
- Default throttle for most authenticated endpoints
- CRUD operations
- General API access

---

### 3. StaffRateThrottle

**Purpose**: Higher limits for staff/admin users
**Rate**: 5000 requests per hour
**Scope**: `staff`

```python
from core.throttling import StaffRateThrottle

class AdminViewSet(viewsets.ModelViewSet):
    throttle_classes = [StaffRateThrottle]
```

**Use Cases**:
- Admin dashboards
- Bulk operations
- System management endpoints

---

### 4. BurstRateThrottle

**Purpose**: Short-term burst protection
**Rate**: 60 requests per minute
**Scope**: `burst`

```python
from core.throttling import BurstRateThrottle

class MyView(APIView):
    throttle_classes = [BurstRateThrottle, UserRateThrottle]
```

**Use Cases**:
- Prevents rapid-fire requests
- Protects against automated scripts
- Applied by default to all authenticated endpoints

**Note**: Can be combined with other throttles for multi-layer protection.

---

### 5. SustainedRateThrottle

**Purpose**: Long-term sustained usage limits
**Rate**: 10,000 requests per day
**Scope**: `sustained`

```python
from core.throttling import SustainedRateThrottle

class MyViewSet(viewsets.ModelViewSet):
    throttle_classes = [SustainedRateThrottle, UserRateThrottle]
```

**Use Cases**:
- Daily usage caps
- Subscription tier enforcement
- API quota management

---

### 6. UploadRateThrottle

**Purpose**: Throttle file upload endpoints
**Rate**: 20 requests per hour
**Scope**: `upload`

```python
from core.throttling import UploadRateThrottle

class LedgerUploadView(APIView):
    throttle_classes = [UploadRateThrottle]
```

**Use Cases**:
- File uploads (CSV, Excel, PDF)
- Image uploads
- Document processing endpoints

**Applied To**:
- `/api/licenses/upload-ledger/` - Ledger file uploads

---

### 7. ExportRateThrottle

**Purpose**: Throttle report export endpoints
**Rate**: 30 requests per hour
**Scope**: `export`

```python
from core.throttling import ExportRateThrottle

class ItemReportView(View):
    throttle_classes = [ExportRateThrottle]
```

**Use Cases**:
- Excel exports
- PDF generation
- Data exports

**Applied To**:
- `/api/reports/*` - All report export endpoints

---

### 8. LoginRateThrottle

**Purpose**: Protect authentication endpoints
**Rate**: 5 requests per minute
**Scope**: `login`

```python
from core.throttling import LoginRateThrottle

class LoginView(APIView):
    throttle_classes = [LoginRateThrottle]
```

**Use Cases**:
- Login endpoints
- Token generation
- Password reset requests

**Applied To**:
- `/api/auth/login/` - User login
- `/api/auth/password-reset/` - Password reset

**Protection**: Prevents brute-force attacks on authentication.

---

### 9. StrictRateThrottle

**Purpose**: Very strict limits for sensitive operations
**Rate**: 10 requests per hour
**Scope**: `strict`

```python
from core.throttling import StrictRateThrottle

class DangerousOperationView(APIView):
    throttle_classes = [StrictRateThrottle]
```

**Use Cases**:
- Delete operations
- Bulk updates/deletes
- Account deactivation
- Data export with sensitive information

---

### 10. PerViewRateThrottle

**Purpose**: Custom per-view throttling
**Rate**: Configurable per view
**Scope**: Custom

```python
from core.throttling import PerViewRateThrottle

class MyView(APIView):
    throttle_classes = [PerViewRateThrottle]
    throttle_scope = 'my_custom_scope'

# In settings.py:
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {
        'my_custom_scope': '100/hour',
    }
}
```

**Use Cases**:
- Endpoints with unique rate requirements
- A/B testing different limits
- Custom business logic throttling

---

## Configuration

### Settings

All throttle rates are configured in `backend/lmanagement/settings.py`:

```python
REST_FRAMEWORK = {
    # Default throttle classes applied to all views
    "DEFAULT_THROTTLE_CLASSES": [
        "core.throttling.BurstRateThrottle",
        "core.throttling.UserRateThrottle",
    ],

    # Rate limits for each scope
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "staff": "5000/hour",
        "burst": "60/minute",
        "sustained": "10000/day",
        "upload": "20/hour",
        "export": "30/hour",
        "login": "5/minute",
        "strict": "10/hour",
    },
}
```

### Time Units

Throttle rates can be specified with these time units:

- `second` or `sec` - Requests per second
- `minute` or `min` - Requests per minute
- `hour` - Requests per hour
- `day` - Requests per day

**Examples**:
```python
"anon": "10/sec"        # 10 requests per second
"user": "60/min"        # 60 requests per minute
"burst": "100/hour"     # 100 requests per hour
"sustained": "5000/day" # 5000 requests per day
```

### Environment-Specific Configuration

Adjust rates based on environment:

```python
# settings.py
if DEBUG:
    # Development: More lenient rates
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['user'] = '10000/hour'
else:
    # Production: Stricter rates
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['user'] = '1000/hour'
```

---

## Applying Throttling

### Method 1: Default Throttling (Global)

Applied automatically to all views:

```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "core.throttling.BurstRateThrottle",
        "core.throttling.UserRateThrottle",
    ],
}
```

**Result**: All authenticated endpoints have burst protection (60/min) and user limits (1000/hour).

---

### Method 2: View-Level Throttling

Override throttle for specific views:

```python
from rest_framework.views import APIView
from core.throttling import StrictRateThrottle

class DeleteAllDataView(APIView):
    throttle_classes = [StrictRateThrottle]  # Override default

    def delete(self, request):
        # Only 10 deletes per hour
        pass
```

---

### Method 3: ViewSet-Level Throttling

Apply to entire ViewSet:

```python
from rest_framework import viewsets
from core.throttling import UploadRateThrottle, UserRateThrottle

class LicenseViewSet(viewsets.ModelViewSet):
    throttle_classes = [UserRateThrottle, UploadRateThrottle]
```

---

### Method 4: Action-Specific Throttling

Different throttles for different actions:

```python
from rest_framework.decorators import action
from core.throttling import ExportRateThrottle, UserRateThrottle

class LicenseViewSet(viewsets.ModelViewSet):
    throttle_classes = [UserRateThrottle]  # Default for all actions

    @action(detail=False, methods=['get'], throttle_classes=[ExportRateThrottle])
    def export_excel(self, request):
        # This action has different throttle (30/hour)
        pass
```

---

### Method 5: Combining Multiple Throttles

Apply multiple throttles for layered protection:

```python
from core.throttling import (
    BurstRateThrottle,
    UserRateThrottle,
    SustainedRateThrottle
)

class MyViewSet(viewsets.ModelViewSet):
    throttle_classes = [
        BurstRateThrottle,      # 60/minute
        UserRateThrottle,        # 1000/hour
        SustainedRateThrottle,   # 10000/day
    ]
```

**Result**: Request must pass all three throttles. Most restrictive limit applies.

---

### Method 6: Conditional Throttling

Apply throttles based on conditions:

```python
class MyViewSet(viewsets.ModelViewSet):
    def get_throttles(self):
        if self.action in ['create', 'update', 'destroy']:
            # Strict throttle for write operations
            return [StrictRateThrottle()]
        else:
            # Lenient throttle for read operations
            return [UserRateThrottle()]
```

---

## Monitoring & Management

### API Endpoints

#### 1. Get All Throttle Status

```bash
GET /api/masters/throttle-status/
Authorization: Bearer <token>
```

**Response**:
```json
{
    "anon": {
        "allowed": true,
        "rate": "100/hour",
        "remaining": 95,
        "available_in": 0,
        "limit": 100,
        "duration": 3600
    },
    "user": {
        "allowed": true,
        "rate": "1000/hour",
        "remaining": 987,
        "available_in": 0,
        "limit": 1000,
        "duration": 3600
    },
    "burst": {
        "allowed": false,
        "rate": "60/minute",
        "remaining": 0,
        "available_in": 15,
        "limit": 60,
        "duration": 60
    }
}
```

---

#### 2. Get Specific Scope Status

```bash
GET /api/masters/throttle-status/user/
Authorization: Bearer <token>
```

**Response**:
```json
{
    "allowed": true,
    "rate": "1000/hour",
    "remaining": 987,
    "available_in": 0,
    "limit": 1000,
    "duration": 3600
}
```

---

#### 3. Reset Throttle (Admin Only)

```bash
POST /api/masters/throttle-reset/
Authorization: Bearer <admin-token>
Content-Type: application/json

{
    "user_id": 123,
    "scope": "user"
}
```

**Response**:
```json
{
    "message": "Throttle reset successfully",
    "user_id": 123,
    "scope": "user"
}
```

---

#### 4. Get Throttle Statistics (Admin Only)

```bash
GET /api/masters/throttle-stats/
Authorization: Bearer <admin-token>
```

**Response**:
```json
{
    "total_cache_keys": 1234,
    "scopes": {
        "anon": 45,
        "user": 890,
        "staff": 12,
        "burst": 1100,
        "sustained": 850,
        "upload": 23,
        "export": 67,
        "login": 156,
        "strict": 8
    }
}
```

---

#### 5. Check Throttle Health

```bash
GET /api/masters/throttle-health/
```

**Response**:
```json
{
    "status": "healthy",
    "cache_backend": "redis",
    "cache_available": true,
    "configured_scopes": [
        "anon", "user", "staff", "burst",
        "sustained", "upload", "export",
        "login", "strict"
    ],
    "rates": {
        "anon": "100/hour",
        "user": "1000/hour",
        ...
    },
    "default_throttle_classes": [
        "BurstRateThrottle",
        "UserRateThrottle"
    ]
}
```

---

### Response Headers

When throttled, API returns these headers:

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1704067200
Retry-After: 45

{
    "detail": "Request was throttled. Expected available in 45 seconds."
}
```

**Headers**:
- `X-RateLimit-Limit`: Maximum requests allowed in window
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Unix timestamp when limit resets
- `Retry-After`: Seconds to wait before retrying

---

### Programmatic Access

Use utility functions in code:

```python
from core.throttling import (
    get_throttle_status,
    get_all_throttle_status,
    reset_throttle
)

# Get status for specific throttle
status = get_throttle_status(request, UserRateThrottle)
print(f"Remaining: {status['remaining']}")

# Get all throttle statuses
all_status = get_all_throttle_status(request)

# Reset throttle for user
reset_throttle(user_id=123, scope='user')
```

---

## API Reference

### Throttle Response Format

When a request is throttled (429 Too Many Requests):

```json
{
    "detail": "Request was throttled. Expected available in 45 seconds."
}
```

### Throttle Status Format

```json
{
    "allowed": true,           // Whether request would be allowed
    "rate": "1000/hour",       // Configured rate limit
    "remaining": 987,          // Remaining requests in window
    "available_in": 0,         // Seconds until next request (0 if allowed)
    "limit": 1000,             // Maximum requests in window
    "duration": 3600           // Window duration in seconds
}
```

---

## Best Practices

### 1. Choose Appropriate Throttles

- **Read-heavy endpoints**: `UserRateThrottle` (1000/hour)
- **Write operations**: `StrictRateThrottle` (10/hour)
- **File uploads**: `UploadRateThrottle` (20/hour)
- **Exports**: `ExportRateThrottle` (30/hour)
- **Authentication**: `LoginRateThrottle` (5/minute)

### 2. Layer Multiple Throttles

Combine short-term and long-term throttles:

```python
throttle_classes = [
    BurstRateThrottle,       # 60/minute (prevents rapid-fire)
    UserRateThrottle,        # 1000/hour (hourly limit)
    SustainedRateThrottle,   # 10000/day (daily quota)
]
```

### 3. Handle Throttle Errors Gracefully

Frontend should handle 429 responses:

```javascript
async function fetchData() {
    try {
        const response = await fetch('/api/licenses/');
        if (response.status === 429) {
            const retryAfter = response.headers.get('Retry-After');
            console.warn(`Rate limited. Retry after ${retryAfter} seconds`);
            // Show user-friendly message
            // Implement exponential backoff
        }
    } catch (error) {
        console.error(error);
    }
}
```

### 4. Monitor Throttle Status

Check throttle status before expensive operations:

```javascript
// Check if export is allowed before generating
const status = await fetch('/api/masters/throttle-status/export/')
    .then(r => r.json());

if (status.remaining <= 0) {
    alert(`Export limit reached. Try again in ${status.available_in} seconds.`);
    return;
}

// Proceed with export
await generateExport();
```

### 5. Implement Exponential Backoff

When rate limited, use exponential backoff:

```javascript
async function fetchWithBackoff(url, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        const response = await fetch(url);

        if (response.status !== 429) {
            return response;
        }

        const retryAfter = parseInt(response.headers.get('Retry-After')) || 1;
        const backoff = retryAfter * Math.pow(2, i); // Exponential backoff

        console.log(`Throttled. Retrying in ${backoff}s...`);
        await sleep(backoff * 1000);
    }

    throw new Error('Max retries exceeded');
}
```

### 6. Cache Responses

Reduce API calls by caching:

```javascript
// Cache GET requests for 5 minutes
const cache = new Map();

async function cachedFetch(url) {
    if (cache.has(url)) {
        const { data, timestamp } = cache.get(url);
        if (Date.now() - timestamp < 5 * 60 * 1000) {
            return data;
        }
    }

    const response = await fetch(url);
    const data = await response.json();

    cache.set(url, { data, timestamp: Date.now() });
    return data;
}
```

### 7. Use Webhooks Instead of Polling

For long-running operations (file processing, reports), use webhooks or task status endpoints instead of polling:

```javascript
// ❌ Bad: Polling (wastes rate limit)
setInterval(async () => {
    const status = await fetch(`/api/tasks/${taskId}/`).then(r => r.json());
    if (status.complete) {
        // Handle completion
    }
}, 1000); // Polls every second

// ✅ Good: Check task status endpoint (designed for polling)
async function checkTaskStatus(taskId) {
    const response = await fetch(`/api/ledger-task-status/${taskId}/`);
    const status = await response.json();

    if (status.state === 'SUCCESS') {
        return status.result;
    } else if (status.state === 'PENDING') {
        // Wait and retry
        await sleep(2000);
        return checkTaskStatus(taskId);
    }
}
```

### 8. Batch Requests

Combine multiple requests into one:

```javascript
// ❌ Bad: 10 separate requests
for (const id of licenseIds) {
    await fetch(`/api/licenses/${id}/`);
}

// ✅ Good: Single batch request
await fetch(`/api/licenses/?id__in=${licenseIds.join(',')}`);
```

### 9. Request Only What You Need

Use field selection to reduce response size:

```javascript
// ❌ Bad: Fetches all fields
await fetch('/api/licenses/');

// ✅ Good: Fetches only needed fields
await fetch('/api/licenses/?fields=id,license_number,balance_cif');
```

### 10. Display Rate Limit Status

Show users their current rate limit status:

```javascript
// Fetch throttle status
const status = await fetch('/api/masters/throttle-status/')
    .then(r => r.json());

// Display to user
console.log(`API Requests: ${status.user.limit - status.user.remaining}/${status.user.limit}`);
console.log(`Remaining: ${status.user.remaining}`);
console.log(`Resets in: ${Math.ceil(status.user.duration - (Date.now() / 1000))}s`);
```

---

## Troubleshooting

### Issue: Getting 429 Too Many Requests

**Causes**:
1. Making too many requests in short time
2. Multiple browser tabs/windows
3. Automated scripts/tests
4. Shared IP address (multiple users)

**Solutions**:
1. Implement exponential backoff
2. Check `Retry-After` header and wait
3. Cache responses to reduce requests
4. Contact admin to increase your rate limit
5. Use batch endpoints instead of individual requests

---

### Issue: Throttle Limit Too Restrictive

**Solutions**:

1. **For Development**: Increase limits in settings:
```python
# settings.py (development only)
if DEBUG:
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['user'] = '10000/hour'
```

2. **For Staff Users**: Use StaffRateThrottle (5000/hour)

3. **For Production**: Request rate limit increase from admin

---

### Issue: Throttle Not Working

**Diagnosis**:

1. Check cache backend:
```bash
GET /api/masters/throttle-health/
```

2. Verify throttle is applied:
```python
# In view
print(self.throttle_classes)
```

3. Check Redis connection:
```bash
redis-cli ping
```

**Solutions**:
- Restart Redis: `sudo systemctl restart redis`
- Check cache settings in `settings.py`
- Verify `DEFAULT_THROTTLE_CLASSES` is set

---

### Issue: Rate Limit Not Resetting

**Causes**:
- Cache backend issue
- Time synchronization issue
- Multiple application instances

**Solutions**:
1. Check Redis TTL: `redis-cli ttl throttle_user_123`
2. Manually reset: `POST /api/masters/throttle-reset/`
3. Clear cache: `python manage.py cache:clear`

---

### Issue: Different Rate Limits on Different Servers

**Cause**: Cache not shared between servers

**Solution**: Use centralized Redis cache:
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis-server:6379/1',
    }
}
```

---

## Performance Considerations

### Redis Configuration

Optimize Redis for throttling:

```redis
# redis.conf
maxmemory 256mb
maxmemory-policy volatile-lru  # Evict least recently used keys with TTL
```

### Monitoring

Monitor throttle performance:

```python
# Log throttle events
import logging
logger = logging.getLogger('throttle')

# In custom throttle
def allow_request(self, request, view):
    allowed = super().allow_request(request, view)
    if not allowed:
        logger.warning(f"Throttled: {request.user} - {self.scope}")
    return allowed
```

### Scaling

For high-traffic applications:

1. **Use Redis Cluster**: Distribute throttle data
2. **Implement Rate Limit Queues**: Queue requests when throttled
3. **Add CDN**: Cache static responses at edge
4. **Load Balancing**: Distribute requests across servers

---

## Security Considerations

### 1. DDoS Protection

Throttling helps but isn't complete DDoS protection. Also use:
- Cloudflare or similar CDN
- WAF (Web Application Firewall)
- Network-level rate limiting

### 2. Brute Force Prevention

`LoginRateThrottle` (5/minute) protects against brute force, but also:
- Implement CAPTCHA after failed attempts
- Account lockout after N failures
- IP blacklisting for repeated violations

### 3. API Key Throttling

For API integrations, use token-based throttling:

```python
class APIKeyRateThrottle(SimpleRateThrottle):
    scope = 'api_key'

    def get_cache_key(self, request, view):
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            return None
        return f'throttle_api_key_{api_key}'
```

---

## Conclusion

The License Manager implements comprehensive rate limiting to ensure fair, secure, and stable API access. By following this guide, you can:

- ✅ Understand all available throttle classes
- ✅ Configure appropriate limits for your use case
- ✅ Monitor and manage throttle status
- ✅ Handle throttle errors gracefully
- ✅ Optimize API usage to avoid limits

For questions or rate limit adjustments, contact the development team.

**Documentation Version**: 1.0
**Last Updated**: 2026-02-02
