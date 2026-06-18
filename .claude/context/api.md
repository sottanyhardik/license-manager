# Context — API

Orientation only. Authoritative endpoint reference: `docs/04-api.md`.

## Shape

- All endpoints under `/api/*`, JWT-authenticated (`Authorization: Bearer <access>`).
- Auth: `POST /api/auth/login/`, `POST /api/auth/refresh/` (refresh rotation + blacklist).
- CRUD resources are `MasterViewSet`-based and share consistent behavior:
  - **Filtering / search / ordering** via query params (django-filter backends).
  - **Pagination**: structured paginated responses (`docs/guides/API_PAGINATION_GUIDE.md`).
  - **Inline edit**: `PATCH` a single field on a detail route.
  - **Bulk export**: CSV/Excel export actions on list routes.
- Throttling/rate limiting is active (`docs/guides/RATE_LIMITING_GUIDE.md`).

## Client side

- Single axios instance `frontend/src/api/axios.js`:
  - request interceptor attaches the bearer token,
  - concurrent identical GETs dedupe to one in-flight call,
  - 401 → queue + silent refresh (logout if refresh fails), 403 → `/403`, 5xx → toast.
- Don't create a second axios instance or call `fetch()` directly.

## Deep dives

| Topic | File |
|---|---|
| Endpoint catalog | `docs/04-api.md` |
| Pagination | `docs/guides/API_PAGINATION_GUIDE.md` |
| Filter backends | `docs/guides/FILTER_BACKENDS_GUIDE.md` |
| Rate limiting | `docs/guides/RATE_LIMITING_GUIDE.md` |
| Frontend debouncing | `docs/guides/FRONTEND_DEBOUNCING_GUIDE.md` |
