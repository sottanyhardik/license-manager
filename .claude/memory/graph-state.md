# Graph State — Scan #1 (2026-06-17)

> Incremental graph memory. Update affected nodes per edit; do not rebuild.
> Numbers from grep/find over `frontend/src` (106 `.tsx`, ~24.9k LOC).

## Module map (tsx files / LOC)
| node        | files | LOC   | notes |
|-------------|------:|------:|-------|
| pages       |   33  | 15571 | bulk of the weight |
| components  |   63  |  8195 | incl. `components/ui/*` primitives |
| routes      |    2  |   336 | 36 routes, single `AppRoutes.tsx` |
| hooks       |    2  |   356 | |
| context     |    2  |   228 | |
| layout      |    2  |   226 | |
| lib/services/theme/utils/api/types | — | — | no `.tsx` (ts/js only) |

## Routes (36) — refactor targets, by surface
auth(login) · dashboard · licenses(list/create/edit) · allotments(list/create/edit/allocate)
· bill-of-entries(list/create/edit/transfer-letter) · trades(list/create/edit)
· incentive-licenses(list/create/edit) · ledger-upload · license-ledger(+detail)
· pdf-viewer · settings · profile · masters/:entity(list/create/edit) ·
admin/users(list/create/edit) · admin/activity-log · errors(401/403/*)

## Hotspots (largest — decompose + dedupe first)
MasterForm 2455 · MasterList 2153 · TradeForm 1758 · ItemPivotReport 1610 ·
AllotmentAction 1453 · ItemReport 1191 · LicenseBalanceModal 1049 · TaskDrawer 807 ·
NestedFieldArray 758 · LicenseLedger 582 · AccordionTable 557 · AllotmentFormModal 524

## Debt ledger (concrete, measured)
| smell                       | scope            | priority | risk |
|-----------------------------|------------------|----------|------|
| `react-toastify` callers    | ✅ 0 (was 25)    | P1 DONE  | migrated to sonner; gates green |
| `react-toastify` mount      | App.tsx only     | P1 final | remove `<ToastContainer>` + dep when ready |
| `sonner` primitive          | ✅ 25 callers    | P1 DONE  | — |
| inline `style={{…}}`        | **49 files**     | P2       | low |
| hardcoded hex colors        | 19 files / 113   | P2       | low |
| raw `<table>` (vs DataTable)| 18 files         | P3       | med |
| raw `<form>`                | 8 files          | P3       | med |
| `bootstrap-icons` dep       | package.json only| P1       | none (0 tsx imports) |
| leftover Bootstrap classes  | **0**            | —        | done |

## Design tokens — UNIFIED, two layers (verified Scan #2)
**Single source of truth = `--tb-*` (Tabler)** in `theme/tabler.css` (+ `App.css`,
`index.css`), with full light + dark values: brand, body-bg, card-bg, text(+secondary/
tertiary/muted), border(+soft/strong), success/danger/warning/info(+soft/text/border),
radius (r-sm..xl/pill), spacing (sp-*), type (fs-*/fw-*), ring, shadow, easing.
758 refs across 32 tsx files.

**shadcn tokens are ALIASES of `--tb-*`** — `styles/tailwind.css` bridges them:
`--background: var(--tb-body-bg)`, `--primary: var(--tb-brand)`,
`--destructive: var(--tb-danger)`, etc. (94 bridge refs). So the two systems are
already reconciled; NOT fragmentation, NO "which system wins" decision needed.

**Status-tinted UI canonical map = `theme/tokens.js`** — `TONE_MAP`/`CHIP_TONE_MAP`/
`ACTION_TONE_MAP` (all `var(--tb-*)`-based). Rule in its header: "Components must
import from here instead of redefining their own maps."

→ Real P2 debt (reframed): components that **hardcode hex badge palettes** instead
  of importing `theme/tokens.js`. Hotspots: MasterList (22), ItemPivotReport (18),
  TransferLetterForm (8), ConditionBadge (6). Neutral hex (#fff/#000/#e2e8f0) used
  for bg/border are dark-mode-broken (hardcoded light) → map to `--tb-*`.
→ `styles/designSystem.js` (330 LOC): audit for overlap with tokens.js (possible dup).

## ui primitives (consume these — don't duplicate)
badge button card checkbox dialog input label select separator skeleton sonner
switch tabs textarea tooltip

## Recommended sequence (lowest-risk → highest)
P1  toastify→sonner (25) · drop bootstrap-icons dep
P2  inline-style + hex→token sweep (token-driven, mechanical)
P3  shared DataTable adoption (18 tables) · shared form layer (8 forms)
P4  decompose hotspot pages (MasterForm/List, TradeForm, report pages)
Each step: lint + typecheck + build green; behavior unchanged; one PR-sized diff.
