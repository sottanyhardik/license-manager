# 08 — Security Assessment

**Scope:** `backend/` (Django 6.0.4, DRF 3.17.1, SimpleJWT 5.5.1), `frontend/`, `master-data-service/`, root nginx confs, git history.
**Mode:** read-only static review (security-auditor agent, 2026-11-15, branch `feature/version5`). No `.env*` contents were read; secrets are reported by path/commit only.
**Method:** claims in `docs/08-security.md` and `REMEDIATION_SUMMARY_P0_P1_IDOR.md` were verified against code (§11).

## 1. Executive summary

Solid core: `IsAuthenticated` default, role-based permission classes on business viewsets, peer-only sync auth, protected media (except one legacy conf), no injectable raw SQL, no `dangerouslySetInnerHTML`, production settings fail closed **when** `DJANGO_ENVIRONMENT=production`.

Gaps: **tracked `.env` files in git** (incl. `backend/.env_dgft`), **`USER_MANAGER` → superuser password-reset escalation**, **no tenant/company boundary or object-level permission**, JWTs in `localStorage`, opt-in production hardening.

## 2. Authentication

| Item | Finding | Evidence |
|---|---|---|
| Auth classes | `JWTAuthenticationFromQueryParam` then `SessionAuthentication` | `backend/lmanagement/settings.py:271-277` |
| Access token | 30 min (`ACCESS_TOKEN_MINUTES`) | `settings.py:334` |
| Refresh | 7 days; rotation + blacklist on | `settings.py:335,338-339` |
| Access-token revocation | `RevokedAccessToken` checked per request but **never written** → dead protection (AUTH-03) | `apps/core/authentication.py:72` |
| Query-param token | `?access_token=` on GET/HEAD when path *contains* download-ish keywords (AUTH-04) | `apps/core/authentication.py:14-57` |
| Login throttle | 10/min per IP only; no per-username throttle/lockout | `settings.py:311`, `apps/core/throttling.py:195-215` |
| Password policy | Django defaults (min length 8); enforced on reset/change | `settings.py:222-227` |
| Password reset | Generic response, 5/h throttle, single-use token | `apps/accounts/views/password.py:28-110` |
| Session invalidation | Change/reset do **not** revoke outstanding refresh/access tokens (AUTH-02) | `password.py:149-150` |
| `/me` PATCH | `is_active` writable by self (AUTHZ-08); no privilege escalation | `apps/accounts/serializers.py:40-55` |

## 3. Authorization

- `DEFAULT_PERMISSION_CLASSES = IsAuthenticated`. Roles via `BaseRolePermission` (`apps/accounts/permissions.py:5-30`); superuser bypass intentional.
- Only views lacking `permission_classes`: abstract `Cached*ViewSet` bases and sync `PeerSyncAPIView` family (peer-token auth).
- Bare `IsAuthenticated` (any logged-in user): `apps/license/views/dashboard.py:39`, `import_item_suggestion.py:21`, `apps/tasks/views.py:21`, `apps/core/views/throttle_status.py:56,81` (AUTHZ-06).

| Open endpoint | File:line | Assessment |
|---|---|---|
| `POST /api/auth/login/` | `apps/accounts/views/auth.py:17` | Intended, throttled |
| password-reset / confirm | `password.py:32,80` | Intended, throttled |
| `GET /api/health/` | `apps/core/views/health.py:20` | Intended |
| `GET /api/invoice-documents/<token>/` | `apps/trade/views_invoice_documents.py:41` | Capability URL (hashed, expiring, 2 views, audited) — AUTHZ-07 |
| schema/docs/redoc | `lmanagement/urls.py:22,34-36` | Open only if `DEBUG` |
| `/api/sync/*` | `apps/core/sync/views.py:55-60` | Peer-secret auth |

**Object level / tenancy:** no `has_object_permission` in non-test code; user↔company link removed (`accounts/migrations/0004_remove_user_company`). Any `LICENSE_VIEWER` can read every company's data by id. `ProtectedMediaView` (`apps/core/views/media.py`) re-applies roles for `licenses/ boe_copies/ trade/ license_purchases/ companies/` only; `tl/ exports/ entity_* avatars/` fall through to any authenticated user. `UserManagementViewSet` (`apps/accounts/views/user_management.py:36,62-75`): a `USER_MANAGER` can edit, role-assign and **reset the password of superusers** (AUTHZ-02).

## 4. Settings hardening

| Setting | State |
|---|---|
| `DEBUG` | env, default False |
| `SECRET_KEY` | hard-coded dev fallback `settings.py:40`, rejected only if `IS_PRODUCTION` |
| `IS_PRODUCTION` | `DJANGO_ENVIRONMENT in {production,prod}`, default development → **fail-open** (SET-01) |
| SSL redirect / secure cookies / HSTS | env, default off; enforced by production validator (HSTS preload forced) |
| `SECURE_PROXY_SSL_HEADER` | trusts `X-Forwarded-Proto` — OK only behind nginx |
| CORS | allow-all off; production explicit origins only |
| CSRF | `DisableCSRFForAPIMiddleware` skips CSRF only for token-auth requests (`apps/core/middleware.py:7-19`) |
| CSP | none in any nginx conf |
| `DATA_UPLOAD_MAX_NUMBER_FIELDS` | 50000 (`:570`) |
| `django_extensions` | in `INSTALLED_APPS` — ensure dev-only |

## 5. Injection
No `.extra()/RawSQL/.raw(` outside migrations/tests. `cursor.execute` f-string identifiers in `apps/core/materialized_views.py:284,304` and `audit_database_integrity.py:240,251` — internal constants, not exploitable (INJ-01). Sync media download (`apps/core/sync/views.py:301-310`) blocks `..` but no `realpath` containment.

## 6. File upload / media
- `nginx-http-only.conf:25-26` still has **public `location /media/`** (MED-01). Other confs use `internal;`.
- `MEDIA_X_ACCEL_REDIRECT` default empty, not required in production (`settings.py:255`).
- Only `User.avatar` has `FileExtensionValidator`. Licence docs, BOE copies, trade invoices (`bill_of_entry/models.py:221`, `license/models/core.py:1869,2245`, `trade/models.py:228,706`) have no type/size validation and are served `inline` with extension-guessed type → stored XSS on app origin (UP-01).
- 322 PDFs tracked in git, incl. real-looking customs docs at repo root (SEC-02).

## 7. Frontend
No `dangerouslySetInnerHTML`. Access/refresh/user in `localStorage` (`frontend/src/context/AuthContext.tsx:30-35,79,123-134,195-227`) (FE-01). PDF/Excel URLs carry `?access_token=` → history/logs/Referer.

## 8. Secrets in git (paths/commits only)
Tracked at HEAD: root `.env` (`23f72f84`), `backend/.env_dgft` (`79a08ac2`, DGFT session cookies per `settings.py:53-60`), `frontend/.env` (`132072d0`), `frontend/.env.production`. Root `.gitignore` has no `.env` rule (only `backend/.gitignore`). No RSA private keys or AWS keys in history. `Release.key` once added (`c0e365ca`), not tracked now.

## 9. Dependencies
`pip-audit` not installed; `npm audit` not run (network). `pypdf>=6.0.0` unpinned upper bound. → add both audits to CI.

## 10. Celery / Redis / admin / logging
JSON-only serialization (no pickle RCE). One Redis for broker+results+cache, no password by default; validator doesn't enforce auth/TLS (INFRA-01). `/admin/` default path, no 2FA/IP restriction (ADMIN-01). Activity log middleware exists; manager-initiated user/role/password changes not verified as audited.

## 11. Prior-claim verification

| Claim | Verdict |
|---|---|
| Public `/media/` replaced | Mostly — `nginx-http-only.conf` still exposes it |
| Roles re-applied to downloads | Five prefixes only |
| Reset no-enumeration + validators | True |
| Sync rejects user JWT | True |
| Swagger gated in prod | True |
| Prod fails closed | Only with `DJANGO_ENVIRONMENT=production` |
| IDOR remediated | Media layer only; no object/company scoping elsewhere |

## 12. Findings

| ID | Sev | Location | Issue | Fix |
|---|---|---|---|---|
| SEC-01 | High | root `.env`, `backend/.env_dgft`, `frontend/.env`, `frontend/.env.production` | Env files tracked in git | Rotate, `git rm --cached`, root `.env*` ignore (`!*.example`), history purge **(human approval)** |
| AUTHZ-02 | High | `accounts/views/user_management.py:62-75`, `serializers.py:57-123` | USER_MANAGER can reset/edit superusers, grant USER_MANAGER | Block ops on superusers/higher roles unless caller is superuser; audit log |
| AUTHZ-01 | High (design) | no `has_object_permission`; `accounts/0004_remove_user_company` | No tenant/company boundary | **Decision:** single-tenant (document) vs multi-company scoping mixin |
| SET-01 | Med | `settings.py:40-47,72-77` | Hardening opt-in | Fail closed unless explicitly development; refuse dev key when `DEBUG=False` |
| FE-01 | Med | `AuthContext.tsx` | Tokens in localStorage, no CSP | HttpOnly refresh cookie + strict CSP |
| UP-01 | Med | FileFields listed §6; `core/views/media.py:108-130` | No upload validation; inline serving | Allowlist + sniff; `attachment` + `nosniff` |
| MED-01 | Med | `nginx-http-only.conf:25-26` | Public media alias | Remove block/file |
| MED-02 | Med | `core/views/media.py:_required_read_roles` | Unmapped prefixes served to any user | Default-deny mapping |
| SEC-02 | Med | 322 tracked PDFs | Real customs docs in repo | Confirm; remove + purge **(human)** |
| AUTH-02 | Med | `password.py:149-150,75-80` | No token revocation on password change | Blacklist user's tokens |
| AUTH-01 | Med | `settings.py:311` | IP-only login throttle | Per-username throttle/lockout |
| AUTH-03 | Low | `core/authentication.py:72` | Deny-list never populated | Write `jti` on logout/password change |
| AUTH-04 | Low | `core/authentication.py:14-57` | Query-param token on keyword paths | Signed single-purpose download URLs |
| AUTHZ-07 | Low | `views_invoice_documents.py:41` | Anonymous capability URL | Accepted; keep short-lived, log IP |
| AUTHZ-06 | Low | dashboard/import_item_suggestion/tasks/throttle_status | Bare IsAuthenticated | Attach role classes |
| AUTHZ-08 | Low | `accounts/serializers.py:40-55` | Self `is_active` writable | read-only |
| ADMIN-01 | Low | `lmanagement/urls.py:25` | Default admin path | IP restrict / 2FA |
| INFRA-01 | Low | `settings.py:346-347,392` | Redis unauthenticated, shared | `rediss://` + auth in prod; split cache |
| INJ-01 | Low | `materialized_views.py:284,304` | f-string identifiers | `psycopg.sql.Identifier` / allowlist |
| DEP-01 | Info | `requirements.txt` | No dependency audit | pip-audit + npm audit in CI, pin pypdf |
| DOC-01 | Info | `inventory_balance_viewset.py:20` | Stale "AllowAny" docstring | Fix comment |

## 13. Top 5 priorities
1. SEC-01 — treat tracked env files as exposed; rotate, untrack, ignore, purge (approval).
2. AUTHZ-02 — close USER_MANAGER→superuser path; audit user/role changes.
3. AUTHZ-01 — decide tenant model before new modules.
4. SET-01 + MED-01 — fail-closed production; remove public `/media/`; require X-Accel in prod.
5. FE-01 + UP-01 — move refresh token out of localStorage, sandbox uploads, add CSP.
