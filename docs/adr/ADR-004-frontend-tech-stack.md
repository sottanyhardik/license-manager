# ADR-004 — Frontend Tech Stack

**Status:** Accepted
**Date:** 2026-07-14

## Context

The legacy frontend is a mature React SPA. Its `package.json` (at
`legacy/frontend/package.json`) was audited during Phase 0 to identify which
libraries are load-bearing and which should be replaced. The new SPA must
handle complex data tables (hundreds of rows with sorting, filtering,
pagination), multi-step forms, file upload/download (Excel, PDF), and
data-heavy dashboards — all common in trade-license management workflows.

## Decision

The new frontend uses the following stack:

**Core:**
- React 19 (concurrent features, use() hook, server components ready)
- TypeScript with strict mode enabled (`"strict": true` in tsconfig.json)
- Vite — build tool and dev server

**Server state and data fetching:**
- TanStack Query v5 — server state, caching, background refetch, pagination,
  optimistic updates. Replaces ad-hoc fetch/useEffect patterns.
- Axios — HTTP client (interceptors for JWT refresh, base URL config)

**Tables:**
- TanStack Table v8 — headless, virtualisation-ready, column pinning,
  multi-sort, row selection

**Forms and validation:**
- React Hook Form — uncontrolled form performance at scale
- Zod — schema validation, shared type inference between form and API types

**UI and styling:**
- Tailwind CSS v4 — CSS-first config (no `tailwind.config.js`; config lives in
  CSS via `@theme` directive)
- shadcn/ui — copy-owned component library built on Radix UI primitives
- Radix UI — accessible, unstyled headless primitives (Dialog, Popover,
  DropdownMenu, etc.)
- Framer Motion — page transitions and micro-animations
- Lucide React — icon set (consistent with shadcn defaults)

**Specialised UI:**
- Recharts — data visualisation (dashboards, balance charts)
- Sonner — toast notifications (preferred over React Hot Toast for seamless
  shadcn/ui integration)
- React Dropzone — file upload with drag-and-drop
- React Day Picker — date/date-range selection
- React Virtuoso — virtualised lists and tables for very large datasets
- React Error Boundary — granular error containment per page/section

**Export:**
- ExcelJS — client-side Excel (.xlsx) generation
- jsPDF — client-side PDF generation

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Redux Toolkit | Overkill for server-state management; TanStack Query handles the dominant state category (server data). Redux would duplicate cache logic. |
| Material UI (MUI) | Heavy bundle; theming system conflicts with Tailwind v4; shadcn is preferred for Radix-based accessible components. |
| Bootstrap | Not composable with Tailwind v4; dated design system. |
| React Hot Toast | React Hot Toast works but Sonner integrates more cleanly with shadcn/ui's existing Toaster pattern. |
| Webpack | Vite's ESM-first dev server is 10-40x faster for HMR on large TypeScript projects. |
| CSS Modules / styled-components | Tailwind v4 utility-first approach is already established in the legacy frontend; consistency preferred. |

## Consequences

**Positive:**
- TanStack Query eliminates the most common performance class of bugs (stale
  data, redundant fetches, missing loading states) with minimal boilerplate.
- Zod schemas serve as a single source of type truth for both form validation
  and API response parsing, reducing runtime type errors.
- shadcn/ui components are copied into `frontend/src/components/ui/` and are
  fully owned — no breaking upstream changes.
- Tailwind v4 CSS-first config removes the build-step dependency on Node for
  config; CSS variables drive the design token system.
- ExcelJS + jsPDF keep export logic client-side, avoiding server-side rendering
  complexity for report generation.

**Negative:**
- React 19 is very recent; some third-party libraries may lag in compatibility.
  Audit `package.json` peer-dep warnings at every dependency update.
- shadcn/ui components being copy-owned means upstream improvements must be
  manually backported.
- Tailwind v4 CSS-first is a new paradigm; developers familiar with v3
  `tailwind.config.js` need to learn `@theme` directive syntax.
- Client-side PDF/Excel generation has memory limits for very large exports
  (>10k rows). A server-side fallback path should be planned for bulk exports.

## Related ADRs

- ADR-005 — API Versioning: /api/v1/ prefix
- ADR-006 — Authentication: SimpleJWT with shared signing key
