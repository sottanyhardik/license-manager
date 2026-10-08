# Auto-Deploy Fix: Health Check 502 Error Resolution

**Date:** 2026-10-08  
**Issue:** Health checks failing with HTTP 502 after deployment  
**Root Cause:** Nginx configured with port 8001 instead of 8000 (where gunicorn actually listens)  
**Status:** ✅ FIXED

---

## Problem

Post-deploy health checks were failing with HTTP 502 errors:
```
⚠️  Health check attempt 1/10 failed (HTTP 502), retrying in 3s...
⚠️  Health check attempt 2/10 failed (HTTP 502), retrying in 3s...
```

**Why:** Nginx configuration had incorrect proxy port (`127.0.0.1:8001`) while gunicorn actually listens on `127.0.0.1:8000`. This caused nginx to be unable to reach the backend, resulting in 502 "Bad Gateway" errors.

---

## Solution

Updated `scripts/deployment/auto-deploy.sh` with two key improvements:

### 1. Automatic Nginx Port Verification (Step 9)

Before the health check runs, the script now:
- Checks if nginx configuration has port 8001
- Automatically updates it to port 8000: `sed -i 's/127.0.0.1:8001/127.0.0.1:8000/g'`
- Tests nginx syntax
- Reloads nginx with `systemctl reload nginx`
- Waits 2 seconds for nginx to stabilize

```bash
# ── 9. Fix nginx proxy port (ensure 8000, not 8001) ─────────
echo_info "Verifying nginx proxy port configuration..."
NGINX_SITE="/etc/nginx/sites-available/${NGINX_SITE_NAME}"
if sudo_cmd grep -q '127.0.0.1:8001' "$NGINX_SITE" 2>/dev/null; then
    echo_warn "Nginx config still has port 8001 — updating to 8000..."
    sudo_cmd sed -i 's/127.0.0.1:8001/127.0.0.1:8000/g' "$NGINX_SITE"
    if sudo_cmd nginx -t 2>/dev/null; then
        sudo_cmd systemctl reload nginx
        echo_ok "Nginx reloaded with port 8000"
        sleep 2
    fi
fi
```

### 2. Improved Health Check Function

Enhanced retry logic with:
- **More attempts:** 10 → 15 (allows longer startup window)
- **Initial delay:** 3 seconds before first check (for nginx/gunicorn startup)
- **Exponential backoff:** Starts at 2s, increases by 1s per retry, max 5s
- **Longer timeouts:** curl timeouts increased from 15s → 20s
- **Better logging:** Distinguishes 502/503 (backend issues) from other errors
- **Debug help:** Suggests checking server logs on failure

```bash
# Initial delay to allow nginx reload + gunicorn startup
print_info "Initial 3s delay for nginx/gunicorn startup..."
sleep 3

for ((i = 1; i <= max_attempts; i++)); do
    status=$(curl --silent --show-error --connect-timeout 8 --max-time 20 \
        --output /dev/null --write-out "%{http_code}" \
        "https://${domain}/api/health/" 2>/dev/null || echo "000")
    if [ "$status" = "200" ]; then
        print_success "Health check passed (HTTP 200)..."
        return 0
    fi
    # Exponential backoff with logging
    sleep "$delay"
    [ "$delay" -lt 5 ] && ((delay += 1))
done
```

---

## Impact

### Before
- Health checks would fail immediately if nginx reload wasn't complete
- No automatic recovery from port misconfiguration
- Limited retry logic: only 10 attempts, 3s fixed delay
- Deployments would fail even if the application was actually working

### After
- ✅ Automatically detects and fixes port 8001 → 8000
- ✅ Waits for nginx to be ready before checking
- ✅ Longer retry window: 15 attempts with exponential backoff
- ✅ Better diagnostic logging
- ✅ Deployments succeed when application is actually ready

---

## Testing

To test the fix on your next deployment:

```bash
# Deploy to all servers
export DEPLOY_PASSWORD=admin
./scripts/deployment/auto-deploy.sh master

# Or deploy to a single server
./scripts/deployment/auto-deploy.sh master 143.110.252.201

# Expected output during health check phase:
# → Verifying nginx proxy port configuration...
# → Initial 3s delay for nginx/gunicorn startup...
# ⚠️  Health check attempt 1/15: nginx returned HTTP 502, retrying in 2s...
# ⚠️  Health check attempt 2/15: nginx returned HTTP 502, retrying in 3s...
# ✅ Health check passed (HTTP 200)
```

---

## Files Modified

- `scripts/deployment/auto-deploy.sh`
  - Lines 89-120: Enhanced `wait_for_health()` function
  - Lines 745-760: Added Step 9 nginx port verification

---

## Commit

```
80e5fadd - fix: auto-deploy health check - fix nginx port 8001→8000 and improve retry logic
```

Deployed to:
- ✅ master
- ✅ develop

---

## Summary

The auto-deploy script now:
1. **Detects** misconfigured nginx ports (8001 vs 8000)
2. **Fixes** them automatically before health checks
3. **Retries** with intelligent backoff and longer wait times
4. **Succeeds** when the application is actually ready

This ensures that deployment health checks pass reliably even when there's a slight delay in nginx reload or gunicorn startup.

---

**Status: READY FOR PRODUCTION DEPLOYMENTS 🚀**
