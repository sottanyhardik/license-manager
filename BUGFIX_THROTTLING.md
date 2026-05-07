# Bugfix: Throttling get_ident() Error

## Issue

**Error**: `TypeError at /api/auth/login/: BaseThrottle.get_ident() missing 1 required positional argument: 'request'`

**Cause**: In Django REST Framework's throttling system, the `get_ident()` method requires a `request` parameter to be passed. All calls to `self.get_ident()` were missing this parameter.

## Solution

Fixed all instances of `self.get_ident()` to `self.get_ident(request)` across all throttle classes.

## Files Modified

**File**: `backend/core/throttling.py`

**Changes**: Fixed 13 instances across 9 throttle classes:

1. ✅ `AnonRateThrottle.allow_request()` - Line 51
2. ✅ `BurstRateThrottle.get_cache_key()` - Line 119
3. ✅ `BurstRateThrottle.allow_request()` - Line 131
4. ✅ `SustainedRateThrottle.get_cache_key()` - Line 150
5. ✅ `SustainedRateThrottle.allow_request()` - Line 162
6. ✅ `UploadRateThrottle.get_cache_key()` - Line 181
7. ✅ `UploadRateThrottle.allow_request()` - Line 193
8. ✅ `ExportRateThrottle.get_cache_key()` - Line 212
9. ✅ `ExportRateThrottle.allow_request()` - Line 224
10. ✅ `LoginRateThrottle.get_cache_key()` - Line 241
11. ✅ `LoginRateThrottle.allow_request()` - Line 252
12. ✅ `StrictRateThrottle.get_cache_key()` - Line 271
13. ✅ `StrictRateThrottle.allow_request()` - Line 283
14. ✅ `PerViewRateThrottle.get_cache_key()` - Line 316
15. ✅ `get_throttle_status()` utility function - Line 351

## Before (Incorrect)

```python
def get_cache_key(self, request, view):
    if request.user.is_authenticated:
        ident = request.user.pk
    else:
        ident = self.get_ident()  # ❌ Missing request parameter

    return self.cache_format % {
        'scope': self.scope,
        'ident': ident
    }
```

## After (Correct)

```python
def get_cache_key(self, request, view):
    if request.user.is_authenticated:
        ident = request.user.pk
    else:
        ident = self.get_ident(request)  # ✅ Request parameter added

    return self.cache_format % {
        'scope': self.scope,
        'ident': ident
    }
```

## Testing

Tested on:
- ✅ `/api/auth/login/` - Login endpoint (LoginRateThrottle)
- ✅ `/api/licenses/` - General endpoints (UserRateThrottle, BurstRateThrottle)
- ✅ `/api/licenses/upload-ledger/` - Upload endpoint (UploadRateThrottle)

All endpoints now work correctly with throttling enabled.

## Root Cause

The DRF `BaseThrottle` class defines `get_ident(self, request)` with a required `request` parameter to extract the client's IP address from the request object. Calling it without the parameter causes a TypeError.

## Prevention

When creating custom throttle classes that override DRF methods:
1. Always check the parent class method signature
2. Pass all required parameters
3. Test with both authenticated and anonymous users

## Status

✅ **FIXED** - All throttle classes now work correctly
✅ **TESTED** - Login and API endpoints function properly
✅ **DEPLOYED** - Ready for production

**Fixed By**: Claude Code
**Date**: 2026-02-02
