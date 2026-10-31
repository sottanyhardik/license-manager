# Page-by-page browser audit - authenticated local session

**Method:** Existing authenticated session `hardik`; navigation/read-only only on 31 October 2026. No form submitted, record created, edit saved, delete/merge/allocate/recalculate action executed. “INSPECTED” means rendered in browser; “ROUTE INVENTORIED” means present in `AppRoutes.tsx`, but was not opened in this safe audit.

| Page ID | Route(s) | Browser status | What it does / observed findings | Required scope |
|---|---|---|---|---|
| P01 | `/dashboard` | INSPECTED | Alerts: Missing DGFT 109, Pending invoices 6; snapshots and recent expiry/BOE/allotment tables. | Owner action queue: owner, age, impact, definition, drill-down, next step. |
| P02 | `/licenses` | INSPECTED | 50-record list; preselected purchase statuses; long filters; cards show CIF balance. Text defects: “Exclude exclude exporter”, “Balance Balance Cif Range”. | Saved views, visible defaults, compact sortable table, filter reset, canonical balance explanation. |
| P03 | `/licenses/create`, `/licenses/:id/edit` | ROUTE INVENTORIED | High-impact create/edit form not opened to avoid mutation risk. | field validation, duplicate/document/role controls, review of downstream effects. |
| P04 | `/licenses/:id/overview`, `/licenses/:id/balance` | ROUTE INVENTORIED | Balance legacy redirect exists in router; no specific record opened. | traceable movement/balance and API/PDF/Excel parity. |
| P05 | `/planning` | INSPECTED | E1 rule workbench: 8 active rules, 2 validation issues; selected rule reports last update/modifier unavailable. | actionable validation issues, version/source/effective date/audit, preview/commit explanation and locking. |
| P06 | `/allotments` | INSPECTED | 5 cards; records expose Edit, Copy, Allocate, PDF/download, Delete. Displayed zero balanced quantities and no-invoice rows. | allocation impact preview, reason/audit/reversal and capacity/plan/restriction validation. |
| P07 | `/allotments/create`, `/:id/edit`, `/:id/allocate` | ROUTE INVENTORIED | Not opened to avoid creating/changing allocation. | safe create/reverse/reallocate UX and concurrency E2E. |
| P08 | `/bill-of-entries` | INSPECTED | Six records; actions Add Invoice No, Transfer Letter, Merge, Edit, Delete; multi-licence BOE visible. | dependency preview, source document, merge/delete confirmation, reason/reversal and audit. |
| P09 | `/bill-of-entries/create`, `/:id/edit`, `/:id/generate-transfer-letter` | ROUTE INVENTORIED | Not opened to avoid state changes or generated document. | validation/import/recovery, linkage and document access tests. |
| P10 | `/trades` | INSPECTED | 561 records; purchase/sale, due/paid/received amounts, multiple licences and linked purchase/sale actions; direct edit/delete controls. | capture-once, payment/allocation semantics, safe linked trade/reversal and company scope. |
| P11 | `/trades/create`, `/:id/edit` | ROUTE INVENTORIED | Not opened to avoid record mutation. | form contract/duplicate/paired-trade validation and role tests. |
| P12 | `/reconciliation` | INSPECTED | BOE/invoice reconciliation with direct Attach/Create/Ignore/Pending actions. Displayed 1,043 BOE, 317 invoices, 2 matched, 53 unmatched invoices, 1,699 duplicate-debit candidates. | reproduce count semantics; candidate evidence, owner/priority, dry run, safe action/audit. |
| P13 | `/reconciliation-issues` | INSPECTED | Read-only portfolio view links issue rows to licence searches; repeated invoice references and zero quantities appear. | source comparison, classification, record-level evidence; do not treat candidate totals as errors. |
| P14 | `/incentive-licenses`, `/create`, `/:id/edit` | ROUTE INVENTORIED | Direct navigation began loading; no settled rendered screen captured. | isolate it in full E2E suite and apply same balance/security controls. |
| P15 | `/license-ledger`, ledger detail, upload, download requests, package readiness | ROUTE INVENTORIED | Direct navigation began loading; no settled screen captured. | job state/recovery, access, download security, ledger package parity. |
| P16 | 11 `/reports/*` routes | ROUTE INVENTORIED | Item report direct navigation began loading; report content not captured. | each report: source/filter/company/date/export/PDF-Excel parity/performance test. |
| P17 | `/masters/:entity`, create/edit | ROUTE INVENTORIED | Companies direct navigation began loading; no settled content captured. | master sharing vs company policy, duplicate merge, effective dates, validation/audit. |
| P18 | `/profile` | ROUTE INVENTORIED | Not opened. | session/profile/role visibility and self-service security. |
| P19 | `/settings` | INSPECTED | Current session redirected to SPA `/403`, expected for non-superuser. | test authorised superuser path and role matrix; do not weaken guard. |
| P20 | `/admin/users`, `/create`, `/:id/edit` | INSPECTED direct URL | `/admin/users` resolved to Django admin login, not SPA user management. | **P1 route collision investigation:** change client SPA admin namespace or server routing; add route smoke test. |
| P21 | `/admin/activity-log` | ROUTE INVENTORIED | Not opened because admin route collision makes reachability uncertain. | resolve collision, paginate/filter/audit event integrity tests. |
| P22 | `/login`, `/forgot-password`, `/401`, `/403`, `*` | ROUTE INVENTORIED; `/403` INSPECTED | 403 gives clear access-denied and dashboard return link. | auth/reset/unauthorised/error-flow tests, no session leakage. |

## Page-level cross-cutting findings

1. High-impact BOE/allotment/trade actions are visually adjacent to live records; each needs dependency/financial impact preview, confirmation/reason, permission and audit/reversal policy.
2. List pages consistently need active-filter explanations, clean labels, table-density controls and export scope parity.
3. Reconciliation is operational and valuable but its displayed counters need source-query validation before financial conclusions.
4. Browser audit did not test responsive layouts, keyboard flow, error recovery, actual mutation, imports or role variants; these are required isolated E2E/UAT work.
