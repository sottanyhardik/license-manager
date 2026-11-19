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

## Automatic licence Item Name mapping (owner spec 2026-11-19, "FINAL IMPLEMENTATION — AUTOMATIC LICENCE ITEM NAME MAPPING")

| ID | Task | Status | Evidence |
|---|---|---|---|
| D1 | One saved mapping per unique strictly-normalised description, 1..20 existing Item Names | VERIFIED | `test_description_mapping.py` |
| D2 | Save applies to every existing licence import item with exactly that key (REPLACE), HSN / SION conflicts flagged + left unchanged | VERIFIED | backend tests |
| D3 | Future / re-described records mapped automatically (AUTO) after commit; other saves never touch links | VERIFIED | hook tests |
| D4 | New descriptions → Mapping Required (no guess by this feature) | VERIFIED | backend + vitest |
| D5 | Edit = REPLACE with version history (previous → new ids), `expected_version` required via API | VERIFIED | backend tests |
| D6 | Retry-safe re-apply; drift (manual re-link) shown as Partially applied | VERIFIED | backend tests |
| D7 | One-row UI: Description · HSN · SION · Select Item Name (multi-select chips) · Status · Action | VERIFIED | `DescriptionMapping.test.tsx` 7 |

**SCHEMA CHANGE (additive):** `license/0064_import_description_mapping` — tables `ImportDescriptionMapping` (unique `key_hash`,
M2M Item Names, version), `ImportDescriptionMappingVersion` (append-only history), `ImportItemDescriptionMapping` (one per
import item: mapping, applied version, APPLIED / AUTO / CONFLICT, links before first application); `MappingChange.kind`
gains `DESCRIPTION_MAPPING` (choices only). No backfill / RunPython. **Not applied to the local dev DB** (`migrate` needs
owner approval) — the Mapping tab's Licence Import Item view needs it.
**API (additive):** `GET …/item-name-mapping/import/descriptions/?q&status&sion&offset&limit` (ReportPermission),
`POST …/import/descriptions/save/` `{description, item_ids, expected_version}` and `POST …/import/descriptions/<id>/reapply/`
(LICENSE_MANAGER). All earlier APIs (matching, decide, approved / undo, BOE / allotment queues) are kept.
**Removed (frontend only):** the Licence Import Item two-table / suggestion / product-review UI (`ImportItemMapping`,
`ProductMatchingView`, `MultiProductSelection`). BOE / Allotment tabs unchanged.
**Financial:** classification only — `items` M2M + mapping tables; quantities / CIF / debits / balances never written
(test pins import-item description / qty / CIF / HSN and the financial balance). No business-rule change.
**Performance (real data, read-only):** 23,463 described import items → 3,239 unique keys; scan + key in 0.17 s.
**Reviews (/review-diff, 7 reviewers):** code-reviewer 4 blocking (hook re-applied on every save and could revert manual
links; serializer ordering; on_commit exception → 500; per-record plan archive on AUTO) → fixed (hook only on create /
description change, post_init stash, try/except + log, AUTO without plan archive, drift detection → Retry);
react-reviewer 1 blocking (stale edits over a newer version) → fixed (edit tied to base version, test); key normalisation
tightened (no gluing across "." "/", "1,000" kept, zero-width removed); `select_for_update(no_key=True)` (deadlock);
description ≤ 2000; reapply audited. Not changed: per-record `update_or_create` of application rows; listing recomputed
per request (0.2–0.4 s est.); rule-based auto-link signal kept (see decision below).

**Tests (real runs):** `test_description_mapping.py` 11 + `test_item_name_mapping.py` 20 passed; vitest mapping 17;
backend gate: `tests/` pass, manage.py check pass, migrations check pass, flake8 pass, app-level 3907 passed / 1 failed
(`test_product_matching_migrations` pinned LATEST = 0063 → extended to 0064, rerun 1 passed), ruff F401 FAIL pre-existing in
`apps/accounting/selectors/licence_bank_ledger.py` (not touched; `ruff check apps/license` clean); frontend gate exit 0
(lint, typecheck, 994 unit, build); Playwright navigation + licence overview 10/10.

**Owner decision needed:** the pre-existing rule-based auto-link (`update_license_on_import_item_change` →
`item_matcher`) still links Item Names on a new import item without a saved mapping. Spec §5 says new descriptions must not
be guessed; Auto Plan currently relies on those links. Keep it, or disable it so unmapped descriptions stay empty?

## Rule auto-link replaced (owner decision 2026-11-19 "replace") — committed 7146a616

`item_matcher.RULE_AUTO_LINK = False`: new import items get Item Names only from an exact saved description mapping; bulk /
licence saves apply saved mappings (`apply_for_licence`). Backend gate app-level 3909 passed. Local dev DB already at 0064.

## Advanced filters & bulk update (owner spec 2026-11-19, "MASTER IMPLEMENTATION PROMPT — … ADVANCED FILTERS & BULK UPDATE")

| ID | Task | Status | Evidence |
|---|---|---|---|
| F1 | Filter Conditions (description / HSN / SION × 10 operators, ALL / ANY), one server-side evaluator | VERIFIED | `test_description_filters.py` 44; vitest |
| F2 | Matching description + record counts, Select All Matching (= table criteria), Clear, per-row + per-page selection across pages | VERIFIED | vitest `DescriptionMappingBulk.test.tsx` 7 |
| F3 | Bulk update: preview (exact set + fingerprint) → confirm (counts, Item Names, REPLACE) → apply; one mapping per description; per-description succeeded / skipped / failed; Retry failed | VERIFIED | `test_description_bulk.py` 10; vitest |
| F4 | Safety: fingerprint guard, one bulk at a time (cache lock), ≤ 150 descriptions per request, batch audit + summary event, catch-all per description | VERIFIED | backend tests |
| F5 | HSN check per selected Item Name; own records excluded from the reference chapters; unverifiable context noted ("Not verified …"), shown per row | VERIFIED | backend tests |
| F6 | "Automatically Mapped" status (all records AUTO) | VERIFIED | backend + vitest |

**API (additive):** listing `?filters=` JSON (≤ 8 KB) + `total_records`, status `AUTO`; `POST …/import/descriptions/bulk/preview/` and
`…/bulk/apply/` `{mode: filter|keys, filters?, status?, q?, sion?, keys?, item_ids, fingerprint}` (LICENSE_MANAGER; 201 when
something was written, else 200). No migration.
**Reviews (6 passes: code, React/TS, Django/Python, security, performance, cif-balance-auditor):** no blocking backend findings;
React 4 blocking (TS `.at` in a test; Retry-failed lost on preview error; Select All Matching during placeholder data; bulk Item
Names pre-filled after apply) → fixed; financial: **no canonical figure can change or be multiplied** (APPROVE); HSN/SION:
4 MEDIUM → per-Item-Name HSN check, self-exclusion of mapped records from reference chapters, "Not verified" notes instead of
silent passes, conflict details per description in bulk results. Security / perf: batch audit, lock, input caps, MAX_BULK 150
(measured preview 0.24 s; est. 50–100 ms per description), batched application upsert.
**Not changed (reported):** unverifiable context is noted, not blocked (≈ 3,000 import items have no HSN — blocking would
prevent mapping them; owner may decide otherwise); reference HSN chapters still include pre-existing rule-based links of other
records; bulk is synchronous (≤ 150) — a Celery job would be needed for larger single updates; reports that label a record
with each of its Item Names (`purchase_profit_report`, unused `get_item_group_data`) pre-date this work (auditor LOW-3).

## Nested filter groups + licence references (owner specs 2026-11-19 "NESTED FILTER CONDITION GROUPS" and "MASTER … LICENCE REFERENCES")

| ID | Task | Status | Evidence |
|---|---|---|---|
| N1 | Nested ALL / ANY groups in the Licence Planning rule shape (`{operator: AND\|OR, conditions: [condition\|group]}`; ALL/ANY + `groups` accepted; flat form accepted), ≤ 12 levels / 128 nodes like `sion_rule_engine`, empty nested groups pruned, strict node classification | VERIFIED | `test_description_filters.py` 52 (examples A–D, 3+ levels, validation) |
| N2 | Tree editor with the Planning `ExpressionTreeEditor` layout/interaction (Planning code untouched): + Condition / + Group per group, remove (populated group confirms), stable keys, unapplied-changes hint | VERIFIED | vitest (Example A, 3 levels, sibling removal) |
| N3 | Nested filters drive the listing, Select All Matching and bulk (same server evaluator) | VERIFIED | `test_licence_references_counts_and_nested_filter_bulk` |
| L1 | Per description: records, distinct licences, every licence as a chip → `/licenses/:id/overview` (real id), first 3 + "+ N more" | VERIFIED | backend + `LicenceRefs.test.tsx` |
| L2 | Bulk confirmation: descriptions, records, distinct licences, affected licence chips (new tab); conflict licences reported uncapped | VERIFIED | backend + vitest |

**Reviews (4 agents for 8 passes):** code (identity / recursion / bulk / future import): 1 BLOCKING (ambiguous nodes silently pruned → wider
filter) → strict classification + tests; React (nested UI / licence refs): 1 BLOCKING (index keys in the recursive editor) → stable
client ids stripped before apply + test; financial + HSN/SION (Opus): **APPROVE — no figure can change or be multiplied**; MEDIUM
bulk order-dependence → HSN reference computed once per batch before any write + test; LOW stale notes refreshed, conflict licences
uncapped. Performance: listing 0.25 s / 6 queries, nested filter 0.30 s, preview 0.23 s; licence refs built for the returned page only.
**Tests (real runs):** description filters 52 + bulk 13 + mapping 12 = 77 passed; vitest mapping 29; backend gate: app-level
3974 passed / 1 xfailed, tests/ 246 passed, check + migrations check + flake8 pass, ruff F401 FAIL pre-existing in
`apps/accounting/selectors/licence_bank_ledger.py` (untouched; `ruff check apps/license` clean); frontend gate exit 0 (lint,
typecheck, 1006 unit, build); Playwright navigation + licence overview 10/10.
**Owner to confirm (policy):** records whose HSN / SION context cannot be verified are mapped with a visible "Not verified" note
rather than blocked (the auditor considers this acceptable).

## Licence chip navigation (owner spec 2026-11-19 "LICENCE NUMBER CHIP OPENS LICENCE LIST AND SELECTED LICENCE")

- Chips (row references, "+ N more" and the bulk confirmation) navigate to exactly
  `/licenses?flags__is_null=False&is_expired=False&page=1&purchase_status=11%2C10%2C1%2C2%2C4%2C5%2C7` and hand over the real licence
  id + number (`features/licenses/openLicenceTarget.ts`, sessionStorage — the list rebuilds its URL from filter state and drops
  router state / unknown params). Plain clicks only (a modified click opens a plain list in a new tab).
- Licence List (`MasterList`): reads the target once (StrictMode-safe), waits until the list is loaded and not refetching, then
  opens that licence's existing card workspace (Overview tab inside) via `LicensesTable.openRequest` (set, never toggle → no
  duplicate workspace; scrolls to it). Not on the page → the existing exact licence-number lookup with the active filters kept.
  Excluded by the filters (e.g. expired) → notice with "Show it without filters". A user filter / page change or a failed load
  drops a pending target. No backend change; no direct `/licenses/:id/overview` navigation.
- Tests: vitest `MasterList.openLicence.test.tsx` 5, `LicensesTable.openRequest.test.tsx` 1, `LicenceRefs.test.tsx` 5; existing
  MasterList deep-link / filters / smoke suites pass; frontend gate exit 0 (1015 unit, lint, typecheck, build); Playwright navigation +
  licence overview + licence register 15/15. Review (react-reviewer): no blocking; fixed — target dropped on user change / failed
  load, plain-click hand-off only, always-mounted live region for the notice.

## Completion round (owner "CONTINUE AND COMPLETE", 2026-11-19)

- Re-verified the committed deep link (e3f13ca6) on the final tree; fixes: a pending target is cancelled only by a REAL filter
  change (the filter panel's config re-sync is ignored — new test with a real filter config), and by page-size changes too;
  notice uses theme warning tokens; mapping rows show "<status> · Not verified" when HSN / SION context could not be checked
  (real conflicts stay "Conflict", records unchanged).
- Tests (final tree): backend description filters / bulk / mapping / item-name mapping / balance calculator 147 passed (backend
  unchanged since 84af5605, whose full gate passed); frontend gate exit 0 (lint, typecheck, 1017 unit, build); Playwright navigation +
  licence overview + licence register 15/15. Final independent review: approve-with-nits (no blocking) → nits fixed.

## Owner decision 2026-11-19 — HSN / SION verification policy (confirmed)

1. Records whose HSN or SION is missing / cannot be verified are NOT blocked: the mapping is applied and the row shows
   "Applied · Not verified" (note kept on the application row).
2. Actually detected HSN / SION conflicts stay blocked (records unchanged, flagged, licences reported).
3. Audit history is preserved; compatibility is re-validated when the mapping is saved or re-applied (Retry / bulk) or a
   record is created / re-described — at that point a "Not verified" note is refreshed or cleared.
4. No financial change; commits stay local on `feature/v5`; push only after separate owner approval.

## BOE & Allotment → Planning Target Item mapping (owner spec 2026-11-19, "BOE & ALLOTMENT ITEM TO PLANNING TARGET MAPPING")

- Destination = the existing canonical planning target master (`core.ItemNameModel`, the single `planning_target_item`
  FK of `BillOfEntryModel` / `AllotmentModel`) → single select. No new master, no duplicates.
- Models (migration `license/0065_source_name_mapping`, additive): `SourceNameMapping` (kind BOE / ALLOTMENT +
  strict key, unique per kind), `SourceNameMappingVersion` (CREATE / REPLACE history), `SourceNameMappingRecord`
  (per header: mapping version, APPLIED / AUTO / CONFLICT, verified, pre-mapping target / status / source).
- Service `services/product_intelligence/source_name_mapping.py`; API `item-pivot/matching/item-name-mapping/<boe|allotment>/names/`
  (+ `save/`, `<id>/reapply/`, `bulk/preview|apply/`), writes LICENSE_MANAGER. Hooks in `license/signals.py`: header
  create / rename, debit row create / re-point / delete → after-commit `auto_apply` (one per header per transaction).
- Verification = existing contract `resolve_targets_for_source` for every debited import item: legitimate → applied
  (`MAPPED_EXPLICIT` / `NAME_MAPPING`); configured rules exclude it → CONFLICT (record unchanged / restored);
  not verifiable (no debit yet, or no rule for the licence) → target stored, `UNMAPPED_NO_TARGET` (planning keeps it
  unmapped), shown "Applied · Not verified", re-checked on debit / Save / Retry / bulk. A valid target written elsewhere
  is never downgraded, and automatic re-checks never replace it (explicit Save / Retry / bulk do — REPLACE).
- Header writes: queryset `update` of the planning-target fields only (no `save()`; money never recomputed).
- Frontend: the import-description table is configurable (`mappingSources.ts`); BOE (Product Name) and Allotment
  (Item Name*) tabs use it with the nested filter builder (name field only), bulk update, licence chips. The old
  per-record BOE / allotment queue UI (MappingTable, mappingRow, ItemNameSelect) was removed; its APIs are kept.
- Counts (`item-name-mapping/counts/`): BOE / allotment now = names / records without a saved name mapping
  (semantic change, same shape).
- Review (opus code-reviewer): B1 unverifiable downgrade, B2 auto-recheck overwrite, B3 lock-order inversion, N1 re-point /
  delete not re-checked, N3 per-row re-check cost, N4 count gap — all fixed + tests. Open: N2 renaming a record away from a
  mapped name keeps the old target (same as import descriptions); ledger-import bulk-created rows are not re-checked
  (Retry); local dev DB not migrated to 0065 yet (needs owner approval).
- Tests: backend `test_source_name_mapping.py` 11 passed (exit 0); frontend gate exit 0 (lint, typecheck, 1017 vitest, build).

## Next action

Push: waits for separate owner approval. Optional: a real-data Playwright run of `/mapping`.
