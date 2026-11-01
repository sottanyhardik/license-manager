# Agent 5 report — security and permissions (static review)

Agent: Explore, read-only, 2026-11-01 (task a5bb1670258bf899e, 62 tool uses). Inventory: `inventories/permissions-inventory.md`. Status of this report: **agent output, partly verified by the lead** (column "Lead check"). Nothing here has been confirmed at runtime; no requests were made.

## Findings

| ID | Severity | Agent confidence | Lead check | Location | Summary |
|---|---|---|---|---|---|
| SEC-INV-01 | HIGH | VERIFIED | VERIFIED (read `user_management.py:32-74` and `permissions.py:109-112`) | `apps/accounts/views/user_management.py:34,61-74` | A USER_MANAGER can reset the password of, and delete, any user including superusers. The queryset does not exclude superusers, `reset_password` has no target check, and `destroy` is not overridden. |
| SEC-INV-02 | HIGH | VERIFIED | VERIFIED (read `serializers/models.py:39-62`, `master_view.py:700-756`, `permissions.py:188-237`) | `apps/core/views/master_view.py:709-756,673-674`; `apps/core/serializers/models.py:39-62` | PAN, GST, bank account, bank name, IFSC and account type are exported to 9 read-only roles via `/api/masters/companies/export/`. `CompanySerializer` redacts only in `to_representation`. The export resolves any column not declared on the serializer with raw `getattr`, which skips redaction. `pan` and `gst_number` are auto-generated fields, not declared ones, so they fall through. |
| SEC-INV-03 | MEDIUM | VERIFIED | not re-checked | `apps/core/authentication.py:67-75`; `apps/accounts/views/auth.py:39-55`; `apps/accounts/views/password.py:78-152`; `apps/accounts/views/user_management.py:61-74` | Logout blacklists only the submitted refresh token. `RevokedAccessToken` has no production writer. Password change, reset and admin reset do not revoke sessions, so 7-day refresh tokens stay valid. |
| SEC-INV-04 | MEDIUM | VERIFIED (acceptance); log exposure SUSPECTED | not re-checked | `apps/core/authentication.py:37-65`; `apps/core/middleware.py:42-49` | Bearer access tokens accepted in the URL query string on download paths. Access logs, history and Referer may capture them. |
| SEC-INV-05 | MEDIUM | VERIFIED | not re-checked | `apps/accounts/permissions.py:150-163`; `apps/bill_of_entry/views/boe.py:127-133,266-270` | BOE_VIEWER can POST `update-invoice-no`. The docstring says ACCOUNT_ACCESS or BOE_MANAGER only. |
| SEC-INV-06 | MEDIUM | SUSPECTED | not re-checked | `apps/core/views/media.py:76-99,127-134`; `apps/license/tasks.py:33-36`; `apps/license/views/ledger.py:61` | Unlisted media prefixes have no role gate. A user with a ledger package key could fetch another user's ZIP. Keys are a timestamp plus 8 hex characters. Exploitability is unconfirmed. |
| SEC-INV-07 | MEDIUM (CRITICAL if deployed without env vars) | VERIFIED | not re-checked | `lmanagement/settings.py:40-41,47,80-103,328-341` | Hard-coded fallback SECRET_KEY when `DJANGO_SECRET_KEY` is unset. The production guard runs only when `DJANGO_ENVIRONMENT` is production. SIMPLE_JWT signs with SECRET_KEY. A misconfigured production could allow JWT forgery. |
| SEC-INV-08 | MEDIUM | VERIFIED | not re-checked | `apps/license/views/license.py:1139-1143` | `merged_documents` returns the Python traceback in an HTTP 500 body, with no DEBUG gate. |
| SEC-INV-09 | LOW | VERIFIED | not re-checked | `apps/core/views/media.py:76-99`; `apps/accounts/models.py:87`; `apps/core/models.py:600,654,664-665`; `apps/core/views/views.py:478-488` | Avatars, logos, signatures, stamps and transfer-letter templates readable by any authenticated user. |
| SEC-INV-10 | LOW | VERIFIED | not re-checked | `lmanagement/settings.py:295-298,317`; `apps/license/views/ledger_upload.py:258` | The export throttle scope (100/h) is defined but unused. Heavy exports fall under the burst and user limits. LedgerTaskStatusView disables throttling. |
| SEC-INV-11 | LOW | VERIFIED | not re-checked | `apps/core/views/health.py:9`; `lmanagement/settings.py:295-298` | Documented 300/h anonymous throttle on health is not active. Anonymous callers use the per-IP user scope (3000/h). |
| SEC-INV-12 | LOW | VERIFIED | not re-checked | `apps/license/views/license_overview.py:101-102`; `apps/accounts/models.py:42-97` | Ownership check compares a `company_id` that `User` no longer has. Non-superusers get 404. Fails closed, but misrepresents the control. |
| SEC-INV-13 | LOW | VERIFIED | not re-checked | `lmanagement/settings.py:72-75,80-103` | Secure cookie and HSTS flags default off and apply only when production is declared. |
| SEC-INV-14 | INFORMATIONAL | VERIFIED | not re-checked | `apps/license/views/active_dfia_report.py:44-47`; `inventory_balance_viewset.py:23,30`; `settings.py:290` | Stale security comments: DFIA tenant scoping does not exist; inventory docstring says AllowAny but the class uses ReportPermission. |
| SEC-INV-15 | INFORMATIONAL | VERIFIED | not re-checked | `apps/core/views/master_view.py:43-52`; `apps/accounts/permissions.py:156,166-185,292` | Broad role coupling: USER_MANAGER writes all master data; viewer roles generate transfer letters; any manager role can ignore warnings. |
| SEC-INV-16 | INFORMATIONAL | VERIFIED | not re-checked | no `has_object_permission` in the codebase | Object access in licence, allotment, trade and BOE depends only on role. Matches DEC-05, but any reader can fetch any record. |
| SEC-INV-17 | INFORMATIONAL | VERIFIED | not re-checked | `apps/trade/views_invoice_documents.py:41,77-81`; `apps/trade/services/invoice_secure_links.py:32,115`; `apps/trade/models.py:731` | The AllowAny invoice-document endpoint is sound on the points inspected (256-bit token, SHA-256 digest, identity check, 2-view cap, expiry). Risk is URL leakage. |

## Verified-by-lead items: what was and was not checked

- SEC-INV-01 and SEC-INV-02 are the two HIGH findings. Their code paths were read directly, not taken from the agent summary. Both are now recorded as ISS-011 and ISS-012 in `execution/discovered-issues.md`.
- Other items were not re-read by the lead. Treat them as agent findings until a source check or runtime request is recorded.
- Runtime confirmation (a request as a USER_MANAGER against a superuser account, and a request to the companies export as LICENSE_VIEWER) has **not** been run. Doing so needs a disposable database and an authorised test user. It must not run against shared or production data.

## Scope limits

- No runtime tests, requests or migrations were run.
- The SECRET_KEY fallback value is a repository constant and is not reproduced here.
- Not inspected in depth: `apps/core/cache_utils.py:121` (`@api_view` inside a helper).
