# Runtime verification: ISS-011, ISS-012, ISS-013, ISS-017, ISS-018

Agent G, 2026-11-01. Evidence only. No tracked file was changed. All data was synthetic (`TEST-PAN-0001`, `TEST-GST-0001`, `TEST-ACC-0001`, `g-*` usernames). Passwords used by the probes are not recorded.

## Environment and isolation

| Item | Value |
|---|---|
| Python / Django | `backend/.venv` Python 3.14, Django 6.0.4 |
| Test database | `test_audit_g_20261101`, set through `TEST_DB_NAME`. `backend/lmanagement/settings.py:213-217` copies it into `DATABASES["default"]["TEST"]["NAME"]`. pytest-django created it and dropped it at the end of each run. |
| Database server | The local PostgreSQL 17 server (`localhost:5432`) is shared with the developer. Only the test database was created and dropped. The non-test database was not touched. |
| Post-run check | `pg_database` lists no `test_audit%` database (psql exit 0, empty result). |
| Redis | Not used. The default `CACHES` location is `redis://127.0.0.1:6379/1`, which is a developer cache, so the probes used an overlay settings module outside the repository (`/tmp/lm-audit-probe/g_probe_settings.py`). It imports `lmanagement.settings` unchanged and swaps `CACHES` to `LocMemCache`. No `FLUSH*` command was run and the harness index 7 was not used. |
| Celery | No task was dispatched. The probes did not call any `.delay()` path and did not POST to download-request creation. |
| Activity log | `TESTING=true` was set. `apps/core/middleware.py:93` disables the audit-log threads under that flag. |
| Shared processes | Observed with `ps` before the runs and not signalled: Redis server (pid 1058), PostgreSQL server (pid 1067), Celery worker (pid 1068), `runserver 127.0.0.1:8000` (pid 36405). |

Command template (each probe file was run separately; `<file>` is one of the five probe files):

```
cd backend && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/lm-audit-probe TESTING=true \
  TEST_DB_NAME=test_audit_g_20261101 ../.venv/bin/python -m pytest /tmp/lm-audit-probe/<file> \
  -c pytest.ini -p no:cacheprovider --no-cov -q -s --ds=g_probe_settings --rootdir=<backend>
echo $?   # taken immediately after the command, from the redirected run
```

Deviations from the brief: `--ds=g_probe_settings` (overlay, see above) instead of `--ds=lmanagement.settings`, and `-c pytest.ini` because the probes live outside the rootdir. The `export` action reads `_export` or `export`, not `format`, so the export probe used `_export=xlsx|pdf`.

Pytest counts mean that the controls asserted in each probe held. Security verdicts come from the recorded observations (`OBS` lines), not from pass or fail. Policy-dependent cells are recorded and not asserted.

## Results

| Probe | Verdict | Exit | Pytest | Key HTTP status codes |
|---|---|---|---|---|
| ISS-011 USER_MANAGER over superusers | **CONFIRMED** | 0 | 24 passed | USER_MANAGER against a superuser: reset 200 (hash changed), delete 204 (row removed) |
| ISS-012 company export fields | **CONFIRMED** for PAN and GST in exports. The bank-field part of the claim is **REFUTED** for the export. | 0 | 1 passed | LICENSE_VIEWER list 200 with no PAN/GST/bank keys. Export xlsx 200 and pdf 200, both containing PAN and GST. Unauthorised 403 on all three |
| ISS-017 licence report export URL | **CONFIRMED** | 0 | 2 passed | `/api/license/reports/expiring-licenses/` 404 (JSON). `/api/reports/expiring-licenses/` 200, valid xlsx. Same pattern for active licences |
| ISS-018 readiness identifier | **CONFIRMED** for the readiness route. Adds a new finding (NEW-1). | 0 (final run; first run exit 1, probe defect) | 1 passed | Readiness with job key 200; with `request_key` 404; with public UUID 404. Detail with public UUID 200; with `request_key` 500; with job key 500 |
| ISS-013 session persistence | **CONFIRMED** for access tokens after logout, and for refresh and access tokens after password change and admin reset. Logout blacklisting of the submitted refresh token is **REFUTED** (it returns 401). | 0 | 1 passed | See the ISS-013 table |

## ISS-011: USER_MANAGER over superusers

Commands: the template above with `test_g_iss011.py`. Exit 0, 24 passed.

Each attempt used a fresh target and a fresh actor. Targets: LICENSE_VIEWER user, superuser, USER_MANAGER user.

| Actor \ target | Ordinary (reset / delete) | Superuser (reset / delete) | USER_MANAGER (reset / delete) |
|---|---|---|---|
| USER_MANAGER | 200 / 204 | **200 / 204** | 200 / 204 |
| Superuser (control) | 200 / 204 | 200 / 204 | 200 / 204 |
| LICENSE_VIEWER | 403 / 403 | 403 / 403 | 403 / 403 |
| No roles | 403 / 403 | 403 / 403 | 403 / 403 |

- Every 200 reset changed the stored password hash. Every 204 delete removed the row.
- The 403 rows show no change to the row or its hash.
- Cause, from code: `UserManagementPermission` grants USER_MANAGER read and write with no object check (`backend/apps/accounts/permissions.py:109-112`). `reset_password` has no target check (`backend/apps/accounts/views/user_management.py:62-74`).
- Not exercised: logging in as the target after the reset. The takeover consequence is inferred from the hash change.
- Owner decision Q-002 is still PENDING. The superuser cells are therefore recorded, not judged.

## ISS-012: company export fields

Commands: `test_g_iss012.py`. Exit 0, 1 passed.

| Actor | List `/api/masters/companies/` | Export xlsx `?_export=xlsx` | Export pdf `?_export=pdf` |
|---|---|---|---|
| LICENSE_VIEWER | 200. No `pan`, `gst_number`, bank or `account_type` keys. | 200. Header `Pan`, `Gst Number`. PAN and GST values present. | 200. PAN and GST present in extracted text (pypdf). |
| LICENSE_MANAGER | 200. All sensitive keys present. | 200. PAN and GST present. | 200. PAN and GST present. |
| USER_MANAGER | 200. All sensitive keys present. | 200. PAN and GST present. | 200. PAN and GST present. |
| No roles | 403 | 403 | 403 |

- The xlsx header was `Modified On, Iec, Name, Pan, Gst Number, Address Line 1, Address Line 2`. **Bank fields are not among the export columns**, so the bank part of the ISS-012 title is not supported for the export. Bank fields do appear in the list JSON for LICENSE_MANAGER and USER_MANAGER, which is the intended full-access set.
- Cause, from code: `list_display` (`backend/apps/core/views/views.py`, company config) includes `pan` and `gst_number`. `_resolve_export_column` (`backend/apps/core/views/master_view.py:709-756`) reads undeclared fields with `getattr`, which bypasses `CompanySerializer.to_representation` (`backend/apps/core/serializers/models.py:39-62`). The list path is redacted for LICENSE_VIEWER, so the leak is export-only.
- Not checked: the other eight read-only roles listed in ISS-012. One role (LICENSE_VIEWER) was sampled.

## ISS-017: licence report export URL

Commands: `test_g_iss017.py`. Exit 0, 2 passed.

Resolution without a database:

| Path | Result |
|---|---|
| `/api/license/reports/expiring-licenses/` | Resolved to `lmanagement.urls._api_404` (route `^api/`). No `Resolver404` raised, because the JSON catch-all matches first. |
| `/api/reports/expiring-licenses/` | `license:expiring-licenses-report` |
| `/api/license/reports/active-licenses/` | Resolved to `_api_404` |
| `/api/reports/active-licenses/` | `license:active-licenses-report` |

HTTP as LICENSE_MANAGER with `format=excel&days=30`:

| Path | Status | Content type | Result |
|---|---|---|---|
| `/api/license/reports/expiring-licenses/` | 404 | application/json | `{"detail": "Not found."}` |
| `/api/reports/expiring-licenses/` | 200 | xlsx | Valid workbook (openpyxl), 5049 bytes, sheet "No Data" |
| `/api/license/reports/active-licenses/` | 404 | application/json | Same as above |
| `/api/reports/active-licenses/` | 200 | xlsx | Valid workbook, 5044 bytes |

- The frontend path was confirmed by grep: `frontend/src/pages/reports/ExpiringLicenses.tsx:12` and `ActiveLicenses.tsx:12`. `DownloadLicense.tsx` uses the working prefix.
- Limitation: the test database had no licence rows, so the workbook contents with data were not checked. Only the route and workbook validity were checked.

## ISS-018: readiness identifier

Commands: `test_g_iss018.py`. Run 1 exited 1. That was a probe defect: the test client re-raised the 500 described below. The probe was changed to `APIClient(raise_request_exception=False)`, and run 2 (`iss018b.log`) exited 0, 1 passed. Run 1's log was deleted in cleanup and is cited here only for its exit code and cause.

Synthetic job created by ORM: `key = 20261101-120000_0a1b2c3d`, owner LICENSE_MANAGER.

| Request | Status |
|---|---|
| `GET /api/license-ledger/download-package/<job key>/readiness/` | **200** |
| `GET /api/license-ledger/download-package/<request_key>/readiness/` (first UUID segment) | **404** |
| `GET /api/license-ledger/download-package/<public UUID>/readiness/` | **404** |
| `GET /api/license-ledger/download-requests/<public UUID>/` | **200**. `request_key` equals the first UUID segment. |
| `GET /api/license-ledger/download-requests/<request_key>/` | **500** |
| `GET /api/license-ledger/download-requests/<job key>/` | **500** |

- Cause for the readiness 404s: `package_readiness` filters on `key` only (`backend/apps/license/views/ledger.py:275-283`, with `_owned_package_job` at about line 367).
- **NEW-1 (not in the register):** `_owned_download_request` (`backend/apps/license/views/ledger.py:143-147`) uses `Q(public_id=...) | Q(key=...)`. A non-UUID value makes Django's UUID field raise `ValidationError` for the whole query. DRF does not catch it, so the response is HTTP 500 (server log: `Internal Server Error: /api/license-ledger/download-requests/<id>/`). The `key` branch is therefore never reached. The static reading that the detail route accepts job keys was wrong. Only public UUIDs work.
- The frontend readiness page's own API call was not inspected in this run. The probe used the value the link supplies (`request_key`), which returns 404.

## ISS-013: session persistence

Commands: `test_g_iss013.py`. Exit 0, 1 passed.

| Step | Status | Meaning |
|---|---|---|
| A login | 200 | |
| A `/me` baseline | 200 | |
| A logout (submits A refresh) | 205 | |
| A access token on `/me` after logout | **200** | Access tokens are stateless and survive logout until expiry. |
| A refresh token after logout | **401** | Logout does blacklist the submitted refresh token. |
| B login, then B refresh (rotation) | 200, 200 | |
| B change password (with B2 access) | 200 | |
| B2 refresh, issued before the change | **200** | Password change does not revoke sessions. |
| B2 access, issued before the change, on `/me` | **200** | |
| C login after the change | 200 | |
| Admin reset by USER_MANAGER | 200 | |
| C refresh after admin reset | **200** | Admin reset does not revoke sessions. |
| C access after admin reset, on `/me` | **200** | |

- DB state: `RevokedAccessToken` 0 before and 0 after. `BlacklistedToken` 0 to 4. `OutstandingToken` 0 to 7. The blacklist rows come from logout and rotation only.
- No writer of `RevokedAccessToken` was hit. The model is read in `apps/core/authentication.py:72-73`. `ChangePasswordView` and the admin reset do not call `blacklist`.
- Not exercised: the public password-reset confirm path, and the access-token lifetime (30 minutes by default, `ACCESS_TOKEN_MINUTES`). Expiry was not waited for.

## Inconclusive and next steps

| Item | Reason | Next step |
|---|---|---|
| ISS-011 consequence | Only the hash change and the delete were observed. Login as the reset superuser was not tested. | Add a login probe after the reset. Still gated on Q-002. |
| ISS-012 other roles | One read-only role was sampled. The other eight were not. | Extend the role list in the probe. |
| ISS-012 PDF layout | Text extracted with pypdf. Visual layout was not inspected. | Render a page and check if the owner requires it. |
| ISS-017 data rows | Empty test database. The workbook has only a "No Data" sheet. | Seed one licence in a test database and re-check. |
| ISS-018 frontend page | The page's own readiness call was not inspected. | Check the call in `frontend/src` and cover it with a browser probe. |
| ISS-013 token lifetime | Access-token expiry not waited for. | Freeze time or set `ACCESS_TOKEN_MINUTES` to 1 in a test run. |

## Cleanup

- Probe directory `/tmp/lm-audit-probe/` (overlay settings, five probe files, logs) and the two git-status snapshot files were deleted after this evidence was written. Only the evidence file in `docs/v1/system-audit/evidence/` remains from this run.
- Test database `test_audit_g_20261101` was dropped by pytest-django. A `pg_database` query returned no `test_audit%` database.
- `git status --short` was captured at the start of the run and again at the end. The two outputs were identical. The only addition from this run is this evidence file, which sits in the untracked `docs/v1/` tree.
