# Frontend code audit

React/Vite routes, protected wrapper, shared list/form components and Axios-mocked tests exist. Risks: route/navigation metadata drift, dense duplicated filter patterns, inconsistent errors, stale route test/contract mismatch and lint errors. Target: one route manifest, shared data-grid/filter/form/error primitives; frontend displays backend authoritative values.
