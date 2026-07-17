# Media Security Cutover Runbook

Closing the CRITICAL: **`/media/` is served publicly by nginx**, so every BOE PDF,
licence copy, ledger file and generated transfer letter (customs documents + PII)
is downloadable by anyone who can guess the URL — bypassing all DRF permissions.
Paths are highly predictable (e.g. `TL_<bill_of_entry_number>_<name>/`).

The backend fix is **already merged** (additive, nothing broken yet). This runbook
covers the coordinated steps that actually **close the hole**. Do them together in
one deploy window, in this order, and test before removing the public path.

---

## What's already in place (merged)

- `ProtectedMediaView` (`backend/apps/core/views/media.py`) at `GET /api/media/<path>`:
  authenticated (unauth → 403), path-traversal-safe (→ 404), serves via
  `X-Accel-Redirect` in prod (setting `MEDIA_X_ACCEL_REDIRECT`) or `FileResponse`
  in dev. Verified in dev.
- `nginx-protected-media.conf` — the internal `location /protected-media/` block.
- Frontend helpers `frontend/src/utils/documentDownload.ts`
  (`openDocument`, `openAuthedFile`).

## Current cutover state

- nginx still serves `location /media/` publicly.
- Frontend document/export flows use authenticated blob helpers instead of direct
  browser-native media links or `?access_token=` URLs.
- `JWTAuthenticationFromQueryParam` remains configured, but query-string tokens are
  restricted to `GET`/`HEAD` download/export-style paths only.

---

## Step 1 — Frontend migration check (keep public/token URLs out)

Browser-native document/export links must stay on the authed helper path because
plain anchors, images and `window.open()` cannot attach the Bearer header.

Known helper sites:
- `frontend/src/utils/documentDownload.ts` normalizes stored media paths and opens
  files through the authenticated API client.
- `frontend/src/pages/masters/LicenseParsePanel.tsx`, `MasterForm.tsx`,
  `LicenseBalanceModal.tsx`, report pages and export panels call `openDocument()`
  or `openAuthedFile()` instead of browser-native public media links.

Before shipping nginx Step 3, re-grep to confirm zero remaining token links and no
direct browser-native media anchors in frontend source:
```
rg -n "access_token=|href=\\{.*\\.file|window\\.open\\([^)]*media|[\"']/?media/" frontend/src
```
Expected hits should be limited to the authenticated helper implementation,
comments, tests, and `AuthedImage`-style authenticated media consumers. Build and
smoke-test that documents open and exports download while logged in.

## Step 2 — Backend env (turn on X-Accel-Redirect)

On each server's `backend/.env` (or via auto-deploy `SECURE_MEDIA=true`):
```
MEDIA_X_ACCEL_REDIRECT=/protected-media/
```
Without nginx Step 3, this makes `/api/media/<path>` 404 at nginx — so do Step 3 in
the same window.

## Step 3 — nginx (make media internal-only)

In each server's active config (`nginx-license-manager.conf`, `nginx-labdhi.conf`,
`nginx-license-tractor.conf`): **delete** the public `location /media/ { alias …;
add_header Cache-Control "public"; }` block and **add** the internal block from
`nginx-protected-media.conf` (set `alias` to that server's `MEDIA_ROOT`). The
authed `/api/media/<path>` route is already proxied by the existing `location /api/`.
Then: `nginx -t && systemctl reload nginx`.

## Step 4 — Remove query-param JWT fallback (after Steps 1–3 verified)

Once no browser flow depends on `?access_token=` and production logs confirm no
valid clients are sending it, drop the restricted query-param auth fallback from
the global default in `backend/lmanagement/settings.py`:
```python
"DEFAULT_AUTHENTICATION_CLASSES": (
    "rest_framework.authentication.SessionAuthentication",
    "rest_framework_simplejwt.authentication.JWTAuthentication",  # header-only
),
```
Then delete `apps.core.authentication.JWTAuthenticationFromQueryParam` and its
tests. Until that cleanup ships, ensure nginx `log_format` does not record query
strings.

## Rollback

Each step is independently reversible:
- Step 4: restore the query-param auth class.
- Step 3: restore the public `location /media/` block + reload.
- Step 2: unset `MEDIA_X_ACCEL_REDIRECT` (dev-style `FileResponse` path).
- Step 1: revert the frontend commit.
Because Steps 2–3 are what close the hole, keep the public block only until Step 1
is confirmed working, then remove it.

## Verification checklist

- [ ] Logged-in user can open/download every document type + exports (Step 1).
- [ ] `curl https://host/media/<known-path>` returns 404/403 (not the file) after Step 3.
- [ ] `curl https://host/api/media/<path>` without a token → 401/403; with a valid
      Bearer token → the file.
- [ ] Path traversal `GET /api/media/../settings.py` → 404.
- [ ] No `?access_token=` or direct `/media/` references remain in `frontend/src`.
