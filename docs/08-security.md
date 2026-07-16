# 08 — Security

---

## Authentication

### JWT (SimpleJWT)

- **Access token lifetime**: 60 minutes
- **Refresh token lifetime**: 7 days
- **Rotation**: Refresh tokens rotate on each use (ROTATE_REFRESH_TOKENS = True)
- **Blacklisting**: Used refresh tokens are blacklisted (token_blacklist app) — prevents reuse after rotation
- **Storage**: Both tokens stored in `localStorage` (not HTTP-only cookies)

### Token Refresh Strategy

1. Frontend proactively refreshes the access token 5 minutes before expiry (schedule-based; no unnecessary round-trips)
2. On any 401 response, all in-flight requests are queued, a single refresh request is sent, and all queued requests are replayed with the new token

### Logout

`POST /api/auth/logout/` blacklists the refresh token. The access token cannot be invalidated (it is short-lived and self-expiring).

---

## Authorisation

### Permission Classes

| Class | Used By | Rule |
|---|---|---|
| `IsAuthenticated` | Tasks, Me endpoint | Any logged-in user |
| `LicensePermission` | LicenseDetailsViewSet | Read: LICENSE_VIEWER/MANAGER; Write: LICENSE_MANAGER |
| `AllotmentPermission` | AllotmentViewSet | Read: ALLOTMENT_VIEWER/MANAGER; Write: ALLOTMENT_MANAGER |
| `BillOfEntryPermission` | BOEViewSet | Read: BOE_VIEWER/MANAGER; Write: BOE_MANAGER |
| `TradePermission` | LicenseTradeViewSet | Read: TRADE_VIEWER/MANAGER; Write: TRADE_MANAGER |
| `UserManagementPermission` | UserManagementViewSet | USER_MANAGER or superuser only |
| `LicenseLedgerViewPermission` | LicenseLedgerViewSet | REPORT_VIEWER or any write role |

All permission classes follow the pattern: superusers bypass everything.

### Role-Based Access in Frontend

`ProtectedRoute` component checks roles before rendering:

```tsx
<ProtectedRoute requiredRole="LICENSE_MANAGER">
  <MasterForm entity="licenses" />
</ProtectedRoute>
```

Navigation links in `TopNav.tsx` and command entries in `CommandPalette.tsx` are also filtered by role — unauthorized options are not rendered.

---

## CSRF Protection

- CSRF middleware is **disabled for `/api/` paths** via `DisableCSRFForAPIMiddleware`
- CSRF protection applies to Django admin and template-based views
- API protection relies entirely on JWT (stateless)
- `CSRF_COOKIE_SECURE=True` in production

---

## HTTPS Enforcement

Production settings:
- `SECURE_SSL_REDIRECT=True` — all HTTP requests redirected to HTTPS
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_HSTS_SECONDS=31536000` — 1-year HSTS
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`
- `SECURE_HSTS_PRELOAD=True`
- `SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https')` — reverse-proxy aware

---

## Rate Limiting (Throttling)

Django REST Framework throttle classes:

| Scope | Rate | Applied To |
|---|---|---|
| `login` | 5/minute | `POST /api/auth/login/` |
| `upload` | 10/minute | `POST /api/upload-ledger/` |
| Default DRF anon | 100/day | Unauthenticated requests |
| Default DRF user | 1000/day | Authenticated requests |

Throttle status and management endpoints available to superusers at `/api/masters/throttle-status/`.

---

## Activity Logging

`ActivityLogMiddleware` captures every HTTP request:

```python
ActivityLog(
    user      = request.user,
    method    = request.method,
    path      = request.path,
    status_code = response.status_code,
    ip_address  = get_client_ip(request),
    user_agent  = request.META.get('HTTP_USER_AGENT'),
    response_time_ms = elapsed,
    request_body = truncated_body,
)
```

- Captures 4xx and 5xx responses
- Body captured only for non-GET requests; sensitive fields (password) are masked
- Queryable via admin at `/admin/activity-log` (superuser only)

---

## Input Validation

### Backend
- DRF serializer validation for all API inputs
- Model-level `clean()` validators for business rules
- File uploads: extension whitelist (CSV, HTM, HTML for ledger; PDF, PNG, JPG for documents)
- Maximum file size: 50 MB for ledger uploads

### Frontend
- `formValidation.ts` utility with `ValidationRules` (REQUIRED, DATE, POSITIVE_NUMBER, etc.)
- Inline field error display on form submission
- Client-side checks are redundant with server-side — server is authoritative

---

## Sensitive Data Handling

- User passwords are hashed with PBKDF2 (Django default)
- JWT tokens stored in `localStorage` — accessible to JavaScript (XSS risk; acceptable trade-off for this deployment model)
- Bank account details, company KYC fields (PAN, IEC, GST) stored in plaintext in the database
- No credit card or payment data processed

---

## CORS Configuration

```python
CORS_ALLOWED_ORIGINS or CORS_ALLOW_ALL_ORIGINS
```

In development: `CORS_ALLOW_ALL_ORIGINS=True` (expected from env).
In production: configured to the specific frontend domains.

---

## Django Admin

- Available at `/admin/` for superusers
- Protected by standard Django session authentication
- Not exposed to regular application users
- Used for emergency data corrections and debugging

---

## File Upload Security

- Upload destination: `MEDIA_ROOT` (server filesystem)
- File type validated by extension and MIME type (via `FileExtensionValidator`)
- Served at `/media/:path` — not executable by the server
- Avatar uploads restricted to `png`, `jpg`, `jpeg`

---

## Known Limitations / Trade-offs

| Concern | Status |
|---|---|
| JWT stored in localStorage (XSS risk) | Accepted — no user-facing XSS vectors identified; app is internal |
| No field-level encryption for PAN/GST/IEC | Accepted — internal network deployment; DB access is restricted |
| Refresh token lifetime 7 days | Mitigated by blacklisting on logout and idle timeout |
| No 2FA | Not implemented — single-factor auth only |
| No API versioning | Single version `/api/`; breaking changes require careful migration |
