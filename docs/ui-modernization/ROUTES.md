# Route Tracker

**How to claim a route:**
1. Find a `TODO` route below
2. Change `TODO` → `IN_PROGRESS`
3. Fill in `Owner` (your session ID or name) and `Claimed` (timestamp)
4. When complete → `READY_FOR_REVIEW`, ask user to approve, then `FROZEN`

**Status key:**
- `TODO` — not started
- `IN_PROGRESS` — claimed, work underway (LOCKED — do not touch)
- `READY_FOR_REVIEW` — work done, awaiting user sign-off
- `USER_FEEDBACK` — user requested changes after review
- `FROZEN` — approved and complete (do not re-open without explicit reason)
- `NEEDS_REVIEW` — regression detected, needs fix

---

## Authentication & Errors

| Route | Component | Status | Owner | Claimed | Notes |
|-------|-----------|--------|-------|---------|-------|
| `/login` | `pages/Login.tsx` | READY_FOR_REVIEW | Session-1 | 2026-07-17 | Left panel, card form, bg-body-bg — see CHANGELOG |
| `/forgot-password` | `pages/auth/PasswordReset.tsx` | READY_FOR_REVIEW | Session-1 | 2026-07-17 | Gradient → Tailwind, inline styles removed |
| `/401` | `pages/errors/Unauthorized.tsx` | FROZEN | Session-3 | 2026-07-18 | Pure ErrorScreen delegate — already modern, no changes needed |
| `/403` | `pages/Forbidden.tsx` | FROZEN | Session-3 | 2026-07-18 | Pure ErrorScreen delegate — already modern, no changes needed |
| `*` (404) | `pages/errors/NotFound.tsx` | FROZEN | Session-3 | 2026-07-18 | Pure ErrorScreen delegate — already modern, no changes needed |

---

## Dashboard

| Route | Component | Status | Owner | Claimed | Notes |
|-------|-----------|--------|-------|---------|-------|
| `/dashboard` | `pages/Dashboard.tsx` | READY_FOR_REVIEW | Session-1 | 2026-07-17 | Recharts BOE trend, SkeletonStat, SectionTitle |

---

## Licenses

| Route | Component | Status | Owner | Claimed | Notes |
|-------|-----------|--------|-------|---------|-------|
| `/licenses` | `pages/masters/MasterList.tsx` | TODO | — | — | Shared with allotments/BOE/trades — complex |
| `/licenses/create` | `pages/masters/MasterForm.tsx` | TODO | — | — | 1954 lines, highest complexity |
| `/licenses/:id/edit` | `pages/masters/MasterForm.tsx` | TODO | — | — | Same as create |
| `/incentive-licenses` | `pages/masters/MasterList.tsx` | TODO | — | — | Shared component |
| `/incentive-licenses/create` | `pages/masters/MasterForm.tsx` | TODO | — | — | — |
| `/incentive-licenses/:id/edit` | `pages/masters/MasterForm.tsx` | TODO | — | — | — |

---

## Operations

| Route | Component | Status | Owner | Claimed | Notes |
|-------|-----------|--------|-------|---------|-------|
| `/allotments` | `pages/masters/MasterList.tsx` | TODO | — | — | Uses EntityCard/DetailTable/AccordionTable |
| `/allotments/create` | `pages/masters/MasterForm.tsx` | TODO | — | — | — |
| `/allotments/:id/edit` | `pages/masters/MasterForm.tsx` | TODO | — | — | — |
| `/allotments/:id/allocate` | `pages/AllotmentAction.tsx` | TODO | — | — | Complex form with filters |
| `/bill-of-entries` | `pages/masters/MasterList.tsx` | TODO | — | — | EntityCard layout |
| `/bill-of-entries/create` | `pages/masters/MasterForm.tsx` | TODO | — | — | — |
| `/bill-of-entries/:id/edit` | `pages/masters/MasterForm.tsx` | TODO | — | — | — |
| `/bill-of-entries/:id/generate-transfer-letter` | `pages/BOETransferLetter.tsx` | TODO | — | — | — |
| `/trades` | `pages/masters/MasterList.tsx` | TODO | — | — | — |
| `/trades/create` | `pages/TradeForm.tsx` + `TradeConfigCard.tsx` | TODO | — | — | Complex multi-section form |
| `/trades/:id/edit` | `pages/TradeForm.tsx` | TODO | — | — | — |

---

## Ledger

| Route | Component | Status | Owner | Claimed | Notes |
|-------|-----------|--------|-------|---------|-------|
| `/ledger-upload` | `pages/LedgerUpload.tsx` | FROZEN | Session-3 | 2026-07-18 | PageHeader; gradient inline style → Tailwind; template literals → cn(); inline maxWidth → Tailwind |
| `/license-ledger` | `pages/LicenseLedger.tsx` | FROZEN | Session-3 | 2026-07-18 | B007 done: LicenseWiseLedger 50+ inline styles → Tailwind; Bootstrap cards → shadcn Card; header → PageHeader; P/L inline → cn(); EmptyState; SummaryItem component; scope="col" |
| `/license-ledger/:id/:companyId?` | `pages/LicenseLedgerDetail.tsx` | FROZEN | Session-3 | 2026-07-18 | 80+ inline styles → Tailwind; container-fluid → div; toolbar → bg-foreground; scope="col" on all th; cn() for P/L colors; typed params |

---

## Reports

| Route | Component | Status | Owner | Claimed | Notes |
|-------|-----------|--------|-------|---------|-------|
| `/reports/parle/sion-e1` | `pages/reports/SionE1.tsx` | FROZEN | Session-3 | 2026-07-18 | Pure SionNormReport delegate — already modern |
| `/reports/parle/sion-e5` | `pages/reports/SionE5.tsx` | FROZEN | Session-3 | 2026-07-18 | Pure SionNormReport delegate — already modern |
| `/reports/parle/sion-e126` | `pages/reports/SionE126.tsx` | FROZEN | Session-3 | 2026-07-18 | Pure SionNormReport delegate — already modern |
| `/reports/parle/sion-e132` | `pages/reports/SionE132.tsx` | FROZEN | Session-3 | 2026-07-18 | Pure SionNormReport delegate — already modern |
| `/reports/expiring-licenses` | `pages/reports/ExpiringLicenses.tsx` | FROZEN | Session-3 | 2026-07-18 | Pure LicenseExportPanel delegate — already modern |
| `/reports/active-licenses` | `pages/reports/ActiveLicenses.tsx` | FROZEN | Session-3 | 2026-07-18 | Pure LicenseExportPanel delegate — already modern |
| `/reports/download-license` | `pages/reports/DownloadLicense.tsx` | FROZEN | Session-3 | 2026-07-18 | Already modern — shadcn, typed, aria-pressed toggles, useId |
| `/reports/item-pivot` | `pages/reports/ItemPivotReport.tsx` | TODO | — | — | — |
| `/reports/item-report` | `pages/reports/ItemReport.tsx` | TODO | — | — | — |

---

## Masters (generic entity pages)

| Route | Component | Status | Owner | Claimed | Notes |
|-------|-----------|--------|-------|---------|-------|
| `/masters/:entity` | `pages/masters/MasterList.tsx` | TODO | — | — | Companies, ports, HS codes, etc. |
| `/masters/:entity/create` | `pages/masters/MasterForm.tsx` | TODO | — | — | — |
| `/masters/:entity/:id/edit` | `pages/masters/MasterForm.tsx` | TODO | — | — | — |

---

## Admin

| Route | Component | Status | Owner | Claimed | Notes |
|-------|-----------|--------|-------|---------|-------|
| `/settings` | `pages/Settings.tsx` | FROZEN | Session-3 | 2026-07-18 | Bootstrap card/badge/modal → shadcn; window.confirm → ConfirmDialog; types added; scope="col" |
| `/profile` | `pages/Profile.tsx` | FROZEN | Session-3 | 2026-07-18 | Inline gradient → Tailwind; roles show human-readable labels; alert banners: role/type attrs, dismiss on success; flex-row CardHeader fixed |
| `/admin/users` | `pages/admin/UserList.tsx` | FROZEN | Session-3 | 2026-07-18 | UserRecord type; BOOTSTRAP_TO_BADGE map; getRoleBadgeProps → shadcn Badge; skeleton loading; EmptyState; th scope; typed catches |
| `/admin/users/create` | `pages/admin/UserForm.tsx` | FROZEN | Session-3 | 2026-07-18 | UserFormData type; typed params (handleChange/setFlag/toggleRole/handleSubmit); cn() role picker; typed catches |
| `/admin/users/:id/edit` | `pages/admin/UserForm.tsx` | FROZEN | Session-3 | 2026-07-18 | Same as create |
| `/admin/activity-log` | `pages/admin/ActivityLog.tsx` | FROZEN | Session-3 | 2026-07-18 | ACTION_META CSS vars → Tailwind chipClass; types added; th scope; avatar inline style → Tailwind; EmptyState; cn() for conditionals |

---

## Special

| Route | Component | Status | Owner | Claimed | Notes |
|-------|-----------|--------|-------|---------|-------|
| `/pdf-viewer` | `pages/PDFViewer.tsx` | FROZEN | Session-3 | 2026-07-18 | State typed string|null; catch typed; FAB → shadcn Button |

---

## Route complexity guide

Pick according to available session budget:

**Low complexity (< 200 lines, minimal state):**
`/401`, `/403`, `*`, `/forgot-password`, `/profile`, `/pdf-viewer`,
`/reports/expiring-licenses`, `/reports/active-licenses`,
`/reports/parle/sion-*` (wrappers)

**Medium complexity (200–600 lines):**
`/dashboard`, `/settings`, `/admin/users`, `/admin/activity-log`,
`/license-ledger`, `/ledger-upload`, `/reports/item-*`

**High complexity (600+ lines, shared components):**
`/licenses`, `/allotments`, `/bill-of-entries`, `/trades`,
`/masters/:entity` — all use shared MasterList + MasterForm

**Very high complexity (1000+ lines):**
`/licenses/create` and all `*/create` and `*/:id/edit` routes — all render MasterForm (1954 lines)
`/allotments/:id/allocate` — AllotmentAction (complex filter + allocation logic)
