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

## Still open until this cutover ships

- nginx still serves `location /media/` publicly.
- The frontend still links documents directly to `/media/...` and uses one
  `?access_token=` export link.
- `JWTAuthenticationFromQueryParam` is still a global default auth class.

---

## Step 1 — Frontend migration (replace public/token URLs with authed fetches)

Replace every browser-native document/export link with the authed helper.

Known sites (grep `?access_token=` and `.file` / `/media/` before shipping):
- `frontend/src/components/LicenseBalanceModal.tsx:360` — `balance-excel/?access_token=${token}`
  → `openAuthedFile(\`/licenses/${licenseId}/balance-excel/\`, \`${licenseNumber}-summary.xlsx\`)`
- `frontend/src/pages/masters/LicenseParsePanel.tsx` (`href={existingLicenseCopy.file}`)
  and `MasterForm.tsx`, `LedgerUpload.tsx` — replace `href={doc.file}` anchors with a
  button/onClick calling `openDocument(doc.file, filename)`.

Re-grep to confirm zero remaining `?access_token=` and zero direct `/media/` links:
```
grep -rnE "access_token=|[\"'/]media/" frontend/src
```
Build + smoke-test that documents open and exports download while logged in.

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

## Step 4 — Remove query-param JWT (after Steps 1–3 verified)

Once no browser flow depends on `?access_token=`, drop the query-param auth from the
global default in `backend/lmanagement/settings.py`:
```python
"DEFAULT_AUTHENTICATION_CLASSES": (
    "rest_framework.authentication.SessionAuthentication",
    "rest_framework_simplejwt.authentication.JWTAuthentication",  # header-only
),
```
(Deleting `apps.core.authentication.JWTAuthenticationFromQueryParam`.) Ensure nginx
`log_format` does not record query strings in the meantime.

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
