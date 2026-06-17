# Component Inventory

> Update as primitives are added/changed. Reuse before building new.

## shadcn/ui primitives — `src/components/ui/`
badge · button · card · checkbox · dialog · input · label · select · separator ·
skeleton · sonner · switch · tabs · textarea · tooltip
(barrel: `components/ui/index.js`)

## Feature/composite components
`src/components/` (non-ui) — fill in as catalogued per area.

## Conventions
- Variants via `class-variance-authority` (cva); merge classes with
  `cn()` from `@/lib/utils` (clsx + tailwind-merge).
- Import primitives from `@/components/ui/<name>`.
- Icons: `lucide-react` only.
- Toasts: `sonner` (target). Avoid new `react-toastify`.
- Tables/exports use `exceljs` / `jspdf` — lazy-load (see performance.md).

## Known duplication / debt to resolve
- `bootstrap-icons` dependency — remove once zero usages confirmed.
- `react-toastify` ↔ `sonner` — migrate to one.
- Audit `styles/designSystem.js` vs Tailwind tokens for overlap.
