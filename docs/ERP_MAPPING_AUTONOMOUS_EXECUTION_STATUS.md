# Mapping workspace — autonomous execution tracker

Owner specs: "Master autonomous execution prompt — Mapping workspace" and "Final UI simplification — Mapping workspace"
(2026-11-19). Branch `feature/v5`. **Correction (rebase round):** the work below was NOT committed — it was found uncommitted in the tree; it is committed together with the rebase round. Not pushed. WIP that was in the tree before this task was backed up to
`~/lm_backups/wip-mapping-workspace-2026-11-19/` (tracked diff + untracked files).

## Status by task

| ID | Task | Status | Evidence |
|---|---|---|---|
| A | Inspection (nav, routes, Item Pivot, matching, mapping, planning propagation) | VERIFIED | findings below |
| B1 | Remove the Item Pivot Intelligence workspace (frontend) | VERIFIED | files deleted; vitest classic-only test; no references left |
| B2 | Remove the standalone Licence Overview | VERIFIED (see note) | it was the Intelligence "Overview" tab — removed with B1; no other global overview route/nav existed |
| B3 | Keep `/licenses/:id/overview` | VERIFIED | route untouched; new route test `/licenses/312/overview?tab=transactions`; Playwright overview a11y spec passes |
| C | Mapping nav entry + `/mapping` with exactly three tabs | VERIFIED | navConfig + tests; MappingWorkspace tests; Playwright navigation spec visits every menu item |
| C1 | Licence Import Item tab (existing Product Matching review, per SION) | VERIFIED | ProductMatchingView tests |
| C2/C3 | BOE / Allotment tabs (queue, suggestion, conflicts, approve, bulk, history, pagination) | VERIFIED | backend 14 + vitest |
| D | Matching: approved cross-source evidence, HSN / SION / multi-product flags, no auto-approval | VERIFIED | `test_cross_source_approval_improves_suggestion_but_never_approves_another_source` |
| E | Approval engine: atomic, all-or-nothing, idempotent, audited, one mapping version per approval, per-entry bulk | VERIFIED | backend tests; reviewer approve |
| F | Item Pivot Classic Mode only | VERIFIED | ItemPivotReport render test |
| G | Planning integration (existing propagation → re-plan) | VERIFIED (existing engine) | `test_mapping_is_idempotent_and_versioned_for_replanning`, status-only test |
| G2 | Mark obsolete plans SUPERSEDED | CLOSED — owner: keep REPLACE | owner 2026-11-19 (final UI spec §8); history stays in `MappingChange.before` |
| H | Backend intelligence / matching APIs | KEPT — owner | owner 2026-11-19 (final UI spec §7): keep all backend APIs and capabilities |
| U1 | Simplify all three tabs to one table (Description · HSN · SION · Suggested · Select · Status · Action) | VERIFIED | `MappingTable.tsx`; vitest |
| U2 | Suggestion never pre-selects / approves / counts; bulk needs an explicit pick per row (FE + BE) | VERIFIED | vitest + `test_import_item_bulk_needs_an_explicit_valid_item_name_per_row` |
| P1 | Queue performance on real data | VERIFIED | BOE page 11.3 s / 9000+ queries → 1.0 s / 50; allotment 7.2 s → 0.64 s (local DB, read-only) |

## What was built

**Backend** (no migration; no balance code touched)
- `apps/license/services/product_intelligence/item_name_mapping.py` — shared mapping service for BOE / allotment:
  `queue()` (paged distinct normalised descriptions, split by legitimate-target set; BOE no/date, licence numbers, HSN,
  SION, quantity + unit, occurrences, suggestion + confidence + explanation, similar Item Names, conflicts),
  `apply_entries()` (per-entry Item Name; status guard: only pending or same-target records; validation memoised via
  `validate_explicit_target`; header + debit rows locked; ONE `MappingChange` recorded before writes, per-record
  signal suppressed, each licence re-planned once; audit event with source, record, description, Item Name id,
  previous target/status, HSN, SION, licences, mapping version, validation result; ≤ 2000 records per call),
  `history()`, `counts()` (cached 60 s, dropped on approval).
- API on `ItemPivotViewSet` (`item_pivot_intelligence.py` `ItemPivotItemNameMappingMixin`): GET
  `item-pivot/matching/item-name-mapping/counts/`, `…/<import|boe|allotment>/history/`, `…/<boe|allotment>/?q&offset&limit`
  (ReportPermission); POST `…/<boe|allotment>/apply/` `{record_ids,item_id}` or `{entries:[…]}` (LICENSE_MANAGER).
- **API CONTRACT CHANGE:** `POST item-pivot/matching/decide/` with `APPROVED` now requires an explicit `item_id` (one
  key) or `item_ids` `{source_key: id}` (bulk); multi-product rows cannot be bulk-approved. `decide()` gained `item_ids`.

**Frontend**
- `src/pages/mapping/` — `MappingWorkspace.tsx` (three tabs + approved history + "Mapping versions & re-planning
  status" disclosure), `ItemNameSelect.tsx` (searchable, server search), `invalidate.ts`; moved from
  `reports/item-pivot/`: `ProductMatchingView`, `MultiProductSelection`, `matchingShared`, `MappingChanges`.
- Licence Import Item tab: suggestion is never pre-selected; "Use suggestion" sets it explicitly; bulk needs a pick per row.
- `ItemPivotReport.tsx` — Classic Mode only. Deleted: `ItemPivotIntelligence`, `ProductAnalysisView`,
  `intelligenceShared`, `BulkConsolidation`, `ProductIntelligenceAdmin` (+ tests), `e2e/item-pivot-intelligence.visual.spec.ts`.
- Nav: top-level "Mapping" → `/mapping` (REPORT_ROLES); route in `AppRoutes.tsx`.

## Financial integrity

Mapping writes only `planning_target_item`, `planning_mapping_status`, `planning_mapping_source`, `modified_by/on`
(`update_fields`). `planning_target_item` is not referenced by `balance_calculator.py`. Tests pin import-item
description/qty/CIF, BOE debit rows, allotment rows, header money fields and licence debit / allotment / financial
balance byte-identical after mapping. Reviewer (cif-balance-auditor, Opus): no financial figure can change.

## Reviews

- Backend + financial (cif-balance-auditor, Opus): round 1 REQUEST-CHANGES (1 HIGH bulk cost, 3 MEDIUM, 3 LOW) → all
  fixed → round 2 APPROVE. Remaining LOW: header-then-rows lock order (Postgres deadlock detection → retryable, nothing
  partial); evidence reads all user-selected targets per page (small set).
- Frontend (react-reviewer, Sonnet): 1 HIGH (import tab pre-selected / bulk-approved suggestions) + 5 MEDIUM → fixed
  (explicit picks + per-row `item_ids`, state reset on page/search, combined search/offset state, keepPreviousData,
  shared invalidation, row headers, aria-describedby). LOW not changed: per-keystroke remote master search (cached).

## Tests (real runs)

- Backend targeted: `test_item_name_mapping.py` 14 passed; with `test_product_matching.py` + `test_multi_product_selection.py` 98 passed (before final fix round);
  pivot / matching / balance / propagation / replan regression set 320 passed (exit 0).
- Frontend targeted: mapping suites 27 passed; nav / routes / Item Pivot / licence overview suites passed; tsc exit 0; ESLint 0.
- Playwright (API-mocked): `navigation.spec.ts` + `license-overview.accessibility.spec.ts` 10/10.
- Full gates: see "Gate results" below.

## Final UI simplification round (2026-11-19)

- One shared `MappingTable` for Licence Import Item, BOE and Allotment; source context under the description
  (import: source records + licences; BOE: number, date, qty; allotment: licence, qty). Statuses: Pending · Ready to
  approve · Conflict · Review required; approved rows live in "Approved history". Removed from the UI (backend kept):
  engine / worker panel, semantic job controls, band counters, reject / distinct / alias buttons, decision-history panel.
- Selectors empty by default; the suggestion is labelled "Suggestion only". Approve is enabled only after an explicit
  selection. Bulk "Approve selected" stays disabled, with a live explanation, while any selected row has no selection;
  multi-product rows go through the inline product review (import) or are approved individually (BOE / allotment).
- Backend: `decide()` accepts per-row `item_ids`. An explicitly picked row is validated like a single approval (it
  was limited to HIGH-band suggestions before). Inactive Item Names are refused. Body must be a JSON object; `item_id`
  must be a positive int.
- Performance (perf review, measured): `resolve_targets_for_source(source, cache=None)` + `prime_target_cache()` load
  each licence's SION and each SION's rules / targets / norm memberships once per request (same rules, same result);
  `_sources` reads id pairs and loads each import item once. History is paged by record.
- `/review-diff`: code, django, python, typescript, react, security and performance reviewers, with no blocking
  findings. All non-blocking findings were fixed except: per-record `save()` in `apply_entries` (signal suppressed;
  ≤ 2000 records); `approved_evidence` reads all user-selected targets per page (small set); `window.confirm` for
  ambiguous replacements (unchanged from before).

## Not done / limitations

- No real-data Playwright run for `/mapping` (needs the backend + local DB); unit + mocked e2e only.
- Licence Import Item pending queue is per SION (the existing review engine works per norm); counts are global.

## Rebase round — final Licence Import Item spec (2026-11-19, "STOP CURRENT WORK AND REBASE…")

Inspection: branch `feature/v5`; no other session or agent running; only the user's Vite dev server (left alone); 36 uncommitted
files = the previous round (kept). Classification: **KEEP** all backend (APIs, decide(), versioning, REPLACE, Item Pivot,
planning propagation, BOE / allotment queues); **REPLACE** the Licence Import Item tab UI (Pending | Approved-history toggle,
row checkboxes); **REMOVE** nothing else (no obsolete components left — MultiProductSelection stays for multi-product rows).

| ID | Task | Status | Evidence |
|---|---|---|---|
| R1 | Backend Undo for import approvals (additive, no migration) | VERIFIED | `ImportItemUndoTests` 3 tests; file 18 passed |
| R2 | Approved Mappings table (top): Description · HSN · SION · Approved Item Name · Status · Action (Undo) | VERIFIED | vitest workspace tests |
| R3 | Pending Mappings table (below): exactly 7 columns, no checkboxes, selector empty | VERIFIED | vitest column test |
| R4 | Bulk = "Approve N ready rows" (own explicit pick each) + dialog naming rows that stay Pending | VERIFIED | vitest |
| R5 | Approved rows leave Pending immediately; undone rows leave Approved immediately | VERIFIED | vitest (refetch held open) |
| R6 | BOE / Allotment unchanged (`MappingTable bulk` default true) | VERIFIED | existing BOE tests unchanged, pass |

**API (additive):** `GET item-pivot/matching/item-name-mapping/import/approved/?q&offset&limit` (ReportPermission; active
approvals = APPROVED, not undone, no later approval of the same source key) and
`POST …/import/approved/<decision_id>/undo/` (LICENSE_MANAGER). `…/import/history/` rows gain `undone` (additive).
**Undo semantics:** decision row locked (`select_for_update`) → repeated / concurrent Undo returns `already_undone` (200);
refused (400, nothing changed) if a later approval exists or any record's links differ from the approval's `new_links`;
otherwise restores `previous_links`, one `MappingChange` (MATCH_DECISION, `detail.undo_of`), re-plan per licence, deactivates
the alias created by that approval, audit event `import_item_mapping_undone` (user + timestamp). The approval row, masters,
versions and history are never changed or deleted. `suggest()` no longer reuses an undone approval (row is Pending, no
pre-filled Item Name); undone approvals are not cross-source evidence nor training labels.

## Next action

Push needs owner approval. Optional: a real-data Playwright run of `/mapping` (backend + local DB).
