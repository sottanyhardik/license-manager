# Permissions inventory

Source: static read-only review by an Explore agent (2026-11-01), saved verbatim in substance. Root: `backend/`. No requests were made and no tests were run. `.env_dgft` was not opened. Findings are in `agents/agent-05-security-report.md`.

Re-read by the lead (VERIFIED): `apps/accounts/permissions.py:105-237`, `apps/accounts/views/user_management.py:32-74`, `apps/core/serializers/models.py:39-62`, `apps/core/views/master_view.py:700-756`.

## 1. Permission classes (`apps/accounts/permissions.py` unless noted)

No class in `backend/apps` implements `has_object_permission`. DRF's default (`True`) therefore applies everywhere. Every role class has a superuser bypass.

| Class | Location | Read roles | Write roles |
|---|---|---|---|
| MasterDataPermission | `apps/core/views/master_view.py:43` | any authenticated user (SAFE methods) | superuser or USER_MANAGER |
| BaseRolePermission | `:5` | superuser bypass; empty read list means any authenticated user; empty write list denies | — |
| LicensePermission | `:32` | LICENSE_MANAGER, LICENSE_VIEWER, TRADE_VIEWER, TRADE_MANAGER | LICENSE_MANAGER |
| LicenseReadOnlyPermission | `:38` | same as LicensePermission; treats POST as read (used by bulk-balance-excel only) | — |
| AllotmentPermission | `:54` | ALLOTMENT_MANAGER, ALLOTMENT_VIEWER | ALLOTMENT_MANAGER |
| BillOfEntryPermission | `:60` | BOE_MANAGER, BOE_VIEWER, ACCOUNT_ACCESS, TL_GENERATE | BOE_MANAGER |
| TradePermission | `:66` | TRADE_MANAGER, TRADE_VIEWER | TRADE_MANAGER |
| ReconciliationPermission | `:72` | trade, BOE, ACCOUNT_ACCESS, TL_GENERATE roles | TRADE_MANAGER AND BOE_MANAGER |
| IncentiveLicensePermission | `:103` | INCENTIVE_LICENSE_MANAGER, INCENTIVE_LICENSE_VIEWER | INCENTIVE_LICENSE_MANAGER |
| UserManagementPermission | `:109` | USER_MANAGER | USER_MANAGER |
| ReportPermission | `:115` | REPORT_VIEWER, LICENSE_MANAGER, TRADE_MANAGER, ALLOTMENT_MANAGER, BOE_MANAGER, INCENTIVE_LICENSE_MANAGER | superuser only |
| LedgerUploadPermission | `:121` | LICENSE_MANAGER, LEDGER_MANAGER (any method) | same |
| LicenseLedgerViewPermission | `:132` | TRADE_VIEWER, TRADE_MANAGER, LICENSE_MANAGER, LEDGER_MANAGER (any method) | same |
| AccountAccessPermission | `:150` | ACCOUNT_ACCESS, BOE_MANAGER, BOE_VIEWER (HTTP method not checked) | — |
| TransferLetterPermission | `:166` | TL_GENERATE, BOE/ALLOTMENT/TRADE manager or viewer, LICENSE_MANAGER (method not checked) | — |
| CompanyPermission | `:188` | 14 roles (`:209-219`) | USER_MANAGER |
| LicenseBalanceLedgerPermission | `:240` | 7 roles; per-action write map (`:284-302`); unmapped write actions denied (`:313-317`) | per-action |

Non-permission auth classes: `JWTAuthenticationFromQueryParam` (`apps/core/authentication.py:27`), `PeerTokenAuthentication` (`apps/core/sync/authentication.py:40`).

## 2. Default settings (`backend/lmanagement/settings.py`)

| Setting | Value | Line |
|---|---|---|
| DEFAULT_AUTHENTICATION_CLASSES | JWTAuthenticationFromQueryParam, SessionAuthentication | 271-277 |
| DEFAULT_PERMISSION_CLASSES | IsAuthenticated | 281-283 |
| DEFAULT_THROTTLE_CLASSES | BurstRateThrottle, UserRateThrottle. AnonRateThrottle is not listed | 295-298 |
| Throttle rates | anon 300/h, user 3000/h, staff 10000/h, burst 180/min, sustained 20000/day, upload 2000/h, export 100/h, login 10/min, strict 30/h, password_reset 5/h | 299-323 |
| Pagination | StandardPagination, page size 25 | 284-285 |
| Renderers | JSON only | 291-293 |
| NUM_PROXIES | 1 | 325 |
| SIMPLE_JWT | access 30 min (env `ACCESS_TOKEN_MINUTES`), refresh 7 days, rotate and blacklist after rotation. No SIGNING_KEY, so SECRET_KEY signs | 328-341 |
| Middleware | DisableCSRFForAPIMiddleware (163), ActivityLogMiddleware (169) | 150-170 |
| DEBUG | env, default False | 45 |
| ALLOWED_HOSTS | env, default `127.0.0.1,localhost` | 61-65 |
| Secure cookie / HSTS | SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE default False; HSTS seconds default 0 | 72-75 |
| Production guard | runs only when DJANGO_ENVIRONMENT is production or prod | 47, 80-103 |
| SECRET_KEY | env `DJANGO_SECRET_KEY`, falls back to a hard-coded development constant (value not reproduced) | 40-41 |
| CORS | allow-all False, credentials True | 418-439 |

## 3. Views without an explicit `permission_classes`

| View group | Effective permission | Explicit? |
|---|---|---|
| 16 master viewsets (Port, HSCode, HeadSIONNorms, SionNormClass, SIONExport, SIONImport, ProductDescription, UnitPrice, Group, ItemHead, ItemName, TransferLetter, ExchangeRate, PurchaseStatus, SchemeCode, NotificationNumber) | MasterDataPermission, inherited from the factory (`master_view.py:97`) | no |
| Peer sync APIViews (`apps/core/sync/views.py:56` and 6 subclasses) | global IsAuthenticated, with authentication restricted to PeerTokenAuthentication | no |
| CachedModelViewSet, CachedReadOnlyModelViewSet (`apps/core/cached_views.py:107,120`) | none; no subclass found, dead code | no |

## 4. AllowAny, auth bypass, CSRF

| Location | Construct | Effect |
|---|---|---|
| `apps/core/views/health.py:20-21` | AllowAny, `authentication_classes = []` | public health endpoint |
| `apps/accounts/views/auth.py:16-18` | LoginView AllowAny | public login, 10/min throttle |
| `apps/accounts/views/password.py:31-33` | PasswordResetRequestView AllowAny | public; generic response; 5/h |
| `apps/accounts/views/password.py:79-81` | PasswordResetConfirmView AllowAny | token checked by default_token_generator |
| `apps/trade/views_invoice_documents.py:41` | InvoiceDocumentView AllowAny | capability URL: 256-bit token, SHA-256 digest, max_views default 2 (`apps/trade/models.py:731`) |
| `lmanagement/urls.py:21,37-39` | schema and docs permission `[]` when DEBUG | API docs open in DEBUG only |
| `csrf_exempt` | none found in `apps` or `lmanagement` | |
| `apps/core/middleware.py:16-19,42-49`; `settings.py:163` | DisableCSRFForAPIMiddleware | any `/api/` request with an `Authorization` header skips CSRF, and so do GET download paths carrying `access_token` |
| `apps/core/authentication.py:37-65` | accepts bearer token in `access_token` query parameter on GET/HEAD download paths | token may appear in logs and history |

## 5. File and export endpoints

| # | Endpoint | Output | Permission |
|---|---|---|---|
| 1 | BOE export (GET), `apps/bill_of_entry/views_export.py:61-62` | PDF, XLSX | BillOfEntryPermission read set |
| 2 | Allotment download (GET), `apps/allotment/views_export.py:58-59` | PDF, XLSX | AllotmentPermission |
| 3 | Allotment generate_pdf (GET), `views_actions.py:1639-1640` | PDF | AllotmentPermission |
| 4 | Allotment generate_transfer_letter (POST), `views_actions.py:1665-1666` | PDF, ZIP | TransferLetterPermission |
| 5 | BOE generate_transfer_letter (POST), `boe.py:225-226` | PDF, ZIP | TransferLetterPermission |
| 6 | Trade export_sales_classification_review (GET), `apps/trade/views.py:282-283` | CSV | TradePermission |
| 7 | Trade generate_bill_of_supply (GET), `views.py:402-403` | PDF | TradePermission |
| 8 | Trade generate_purchase_invoice (GET), `views.py:444-445` | PDF | TradePermission |
| 9 | Trade generate_transfer_letter (POST), `views.py:617-618` | PDF, ZIP | TransferLetterPermission |
| 10 | Master export_data (GET), `master_view.py:673-674` | XLSX, PDF | viewset's own class; CompanyPermission for companies |
| 11 | Licence balance_pdf (GET), `license.py:861-862` | PDF | LicensePermission |
| 12 | Licence balance_excel (GET), `license.py:898-899`; balance_excel_unused, `:910-911` | XLSX | LicensePermission |
| 13 | Licence bulk_balance_excel (POST), `license.py:892-893` | XLSX | LicenseReadOnlyPermission |
| 14 | Licence merged_documents (GET), `license.py:965-966` | PDF; traceback on 500 (`:1139-1143`) | LicensePermission |
| 15 | Ledger download-request and package actions, `ledger.py:99,112,250,259,315` | ZIP, CSV | LicenseLedgerViewPermission plus requester scoping (`:143-149`, `:365-372`) |
| 16 | Ledger download_package_pdf, custom_ledger_pdf, financial_ledger_pdf, export, `ledger.py:414-450,643-644` | PDF, XLSX | LicenseLedgerViewPermission, role only |
| 17 | Item report export, `apps/license/views/item_report.py:461-499,733-737` | XLSX | ReportPermission |
| 18 | Active licences report export, `active_licenses_report.py:300-347,650-651` | XLSX | ReportPermission |
| 19 | Planned report, `planned_report.py:473-477` | XLSX | ReportPermission |
| 20 | Licence purchase profit report, `license_purchase_profit_report.py:519-523,760-762` | XLSX, PDF | ReportPermission |
| 21 | Expiring licences report, `expiring_licenses_report.py:331-339,654-655` | XLSX | ReportPermission |
| 22 | Item pivot report and export, `item_pivot_report.py:1967-1968,2261-2265` | XLSX (streaming) | ReportPermission |
| 23 | Inventory balance report, `inventory_balance_report.py:331-335` | XLSX | ReportPermission |
| 24 | InvoiceDocumentView, `views_invoice_documents.py:109` | file | AllowAny plus token |
| 25 | ProtectedMediaView, `apps/core/views/media.py:141-149` | file | IsAuthenticated plus prefix role gate (`:39-99`, `:127-134`) |
| 26 | MediaDownloadView (sync), `apps/core/sync/views.py:314` | file | IsAuthenticated plus PeerTokenAuthentication |
| 27 | Django admin CSV, `apps/core/admin.py:108-109` | CSV | Django admin session (not DRF) |

Not endpoints: `apps/core/utils/pdf_utils.py:112` (`BusinessPDFExporter.create_pdf_response`) has no callers.

## 6. Object-level checks

| Area | Scoping in code | Object-level check |
|---|---|---|
| Licence (`LicenseDetailsViewSet`) | `license.py:512-620` (get_object and get_queryset: lookup and annotations only) | none; any licence read role sees any licence |
| Licence overview | `license_overview.py:101-102` compares `license_obj.exporter_id` with `user.company_id` | inoperative: `User` has no `company_id` (`apps/accounts/models.py:42-97`), so non-superusers get 404 |
| Licence ledger | `ledger.py:67,145,367` filter by `requested_by` | requester ownership (the only licence area with it) |
| Active DFIA report | `active_dfia_report.py:44-63` | none; comment describes tenant scoping that does not exist |
| Incentive licences | `views_incentive.py:33-38` | none |
| Item plans | `views/item_plan.py:118-124` | active and non-deleted only |
| Allotment | `views.py:172-296`; `views_actions.py:261,1679` | none |
| Trade | `views.py:361-383`; `:414,:456` | none |
| BOE | `boe.py:135-160`; `:267-270` | none |
| Masters and companies | `master_view.py:288-320` | none |
| Tasks | `apps/tasks/views.py:14-40` | per-user (created_by, assigned_to; superuser sees all) |

No company or tenant filtering exists in the licence, allotment, trade or BOE querysets. This matches DEC-05 (resolved: role-based access only, cross-company access for appropriate roles).

## Limits

Static review only. SUSPECTED items in the security report are unconfirmed. The `.venv` copy of DRF was read for throttle behaviour.
