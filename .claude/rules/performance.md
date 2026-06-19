# Rule — Performance

Scope: frontend bundle/render cost and backend query cost. Role brief: `graph/performance.md`.
Backend query specifics: `rules/database.md`. Deep dives: `docs/architecture/REDIS_CACHING_GUIDE.md`,
`docs/architecture/MATERIALIZED_VIEWS_GUIDE.md`.

## Must (frontend)

- **Code-split heavy deps** — load on demand, keep them out of the main chunk:
  `exceljs`, `jspdf`, `jspdf-autotable`, `react-select`, `react-datepicker`.
- **Lazy-load routes/pages** via the existing `lazyLoadWithRetry` wrapper.
- **Memoize where it pays** (`React.memo` / `useMemo` / `useCallback`) for hot or expensive
  renders — not blanket-applied (React 19 compiler-friendly code first).
- **Named imports / tree-shaking** — avoid barrel re-exports that pull the world.
- Stable list keys; avoid unnecessary re-renders in tables/lists.

## Must (backend)

- **No N+1** — `select_related` (FK) / `prefetch_related` (reverse/M2M) on list endpoints.
- **Read materialised balances**, never recompute on read; rely on the indexed signal-maintained columns.
- **Add composite indexes** for common filter/order combinations — check existing first.
- **Heavy work → Celery**, never in the request path.

## Avoid

- Duplicate component/util/CSS logic — extract to `@/lib` or `@/hooks`.
- Premature optimization without a measured cost.
- Dead imports/files and unused deps (`bootstrap-icons` is a removal target).
- Regressing bundle size — compare `vite build` output before/after.

## Exit criteria

`npm run build` succeeds with no bundle regression; no obvious duplicate work;
list endpoints free of N+1.
