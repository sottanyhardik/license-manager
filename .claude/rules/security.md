# Rule — Security

Deep dive: `docs/08-security.md`, `docs/architecture/RBAC_DOCUMENTATION.md`,
`docs/guides/RATE_LIMITING_GUIDE.md`, `docs/guides/VALIDATION_IMPLEMENTATION.md`.

## Authentication

- SimpleJWT access + refresh, with **refresh rotation and token blacklisting**.
- Refresh is handled centrally by the frontend axios interceptor
  (`frontend/src/api/axios.js`) — concurrent 401s queue behind one silent refresh; failed
  refresh → logout. Don't re-implement per request. Idle 30 min → auto logout.

## Authorization

- **Role-based access** enforced server-side via DRF permission classes — the frontend
  `ProtectedRoute` gate is UX, not the security boundary. Every endpoint declares permissions.
- Map roles → routes per `docs/architecture/NAVBAR_ROLE_MAPPING.md` and
  `docs/architecture/RBAC_DOCUMENTATION.md`. Setup: `docs/operations/RBAC_SETUP_INSTRUCTIONS.md`.

## Validation & input

- Validate every input in DRF serializers; validate again on the form layer for UX.
- Sanitize any HTML rendered from data with `dompurify`.
- Parameterize all queries (ORM does this; never string-format SQL or shell args).

## Secrets & config

- All secrets via env vars: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`,
  `ALLOWED_HOSTS`, `DEBUG`, `SECURE_SSL_REDIRECT`. Never hardcode or commit; `.env*` untracked.
- `DisableCSRFForAPIMiddleware` intentionally exempts `/api/` (JWT-protected). Don't widen it.

## Audit & rate limiting

- `ActivityLogMiddleware` logs every HTTP request — keep it enabled.
- Throttling is configured (DRF + `throttle_status` view). Don't remove without review.

## Checklist

Run `.claude/checklists/security.md` before merging anything touching auth, permissions,
input handling, file upload, or secrets.
