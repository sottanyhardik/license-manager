# 🔒 Security Role

**Purpose:** keep the auth, authorization, input-validation, and secrets boundaries
intact on every change that touches them.

## Routing

| Concern | File |
|---|---|
| Security do/avoid rules | `rules/security.md` |
| Pre-merge gate | `checklists/security.md` |
| RBAC roles → routes | `docs/architecture/RBAC_DOCUMENTATION.md`, `docs/architecture/NAVBAR_ROLE_MAPPING.md` |
| Deep dive | `docs/08-security.md` |

## Mandate
- **AuthN**: SimpleJWT access + refresh with rotation + blacklist. Refresh is centralized in
  the frontend axios interceptor — never re-implement per request.
- **AuthZ**: role-based, enforced server-side via DRF permission classes. The frontend
  `ProtectedRoute` is UX, not the boundary. Every endpoint declares permissions.
- **Input**: validate in DRF serializers (and again on the form layer for UX). Sanitize any
  data-driven HTML with `dompurify`. Parameterize all queries — never string-format SQL/shell.
- **Secrets**: env vars only (`DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `ALLOWED_HOSTS`,
  `DEBUG`, `SECURE_SSL_REDIRECT`). Never hardcode/commit; `.env*` stays untracked.
- **Audit / throttle**: keep `ActivityLogMiddleware` and DRF throttling enabled. Don't widen
  `DisableCSRFForAPIMiddleware` beyond `/api/`.

## Checklist
- [ ] New/changed endpoint has the correct role-based permission class
- [ ] All inputs validated in serializers; no unsanitized HTML render
- [ ] No secret hardcoded; no query built by string formatting
- [ ] Audit logging + throttling untouched (or change reviewed)
- [ ] `checklists/security.md` walked for auth/permission/upload/secret changes

## Exit criteria
No unauthorized path; unauthorized roles → 403; secrets externalized; security checklist clean.
