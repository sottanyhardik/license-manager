# API Architecture

Surface inventory (URL roots, viewsets, auth/permission classes, pagination): [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) §API.

- **Contract policy:** existing URLs, methods, request/response shapes, auth and permissions are frozen. Changes are additive only. No versioning was introduced, because `/api/` is consumed by the SPA through a single axios instance (`frontend/src/api/axios.js`).
- **Changes made (2026-11-16):**
  - Additive `is_over_utilised` boolean beside licence-level `balance_cif` in licence list/detail, overview summary, balance snapshot, balance ledger summaries, recalculate response, and planning balance.
  - `balance_cif` values can now be **negative** (owner-approved rule). The filter `balance_cif_min=0` now excludes over-utilised licences; use `has_balance=false` (≤ 0) to list them.
- **Performance:** the licence list query count no longer grows with page size (21 queries at page_size 50). BOE list 2116 → 1112 queries at 50 rows; per-row authoritative available CIF still costs about 22 queries per BOE. See [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md).
- **Frontend client:** wrappers unified and typed in `src/api/` (`src/types/api/`), with shims at `src/services/api/*`.
- **Security items** (query-param JWT, CSRF-exempt middleware with SessionAuthentication, anonymous invoice document view): [SECURITY_REPORT.md](SECURITY_REPORT.md). Changes to any of these alter auth behaviour, so they need owner approval.
