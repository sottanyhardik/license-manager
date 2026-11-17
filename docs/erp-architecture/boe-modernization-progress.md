# BOE modernization — progress

Lead updates the status column. Line refs at base `9fc44ad3` unless marked post-change. Worktree: `.claude/worktrees/boe-erp` (branch target `feature/v5`).

## Agent assignments

| Phase | Agents | Output |
|---|---|---|
| Discovery | 6 read-only auditors (solutions-architect: architecture; backend-engineer: backend; product-designer: UI/UX; refactor-specialist: reuse; boe-reconciliation-auditor: QA/data integrity; security-auditor: security/perf) + solutions-architect synthesis | Plan with `docs_facts`, `arch_summary`, `escalations`, `deferred`, `ws.*` |
| Implementation | WS1..WS6 (table below), disjoint file ownership | Code, tests and docs |
| Review | react-reviewer (frontend), cif-balance-auditor (financial integrity), django-reviewer (Django/security/concurrency), independent of implementers; lead verified every claim against code | 3x approve_with_fixes; all actionable minors fixed (see log) |

## Workstreams

| WS | Goal | Owner | Depends on | Risk | Status |
|---|---|---|---|---|---|
| WS1 | Give the BOE list the same compact register UI as Licence by widening the licence-only branches in MasterList, and fix the Add New target. No API or behaviour change for Licence. | frontend-engineer (sonnet) | — | low (presentation only; the licence branch is byte-identical; the BOE snapshot changes deliberately) | done — verified by lead (code read, vitest, Playwright) |
| WS2 | Bring BoeCardList up to the shared-component standard: shared loading/empty states, an accessible inline invoice editor, consistent write gating, formatters reused from masterDisplayFormatters, and actions built in one place. No endpoint or payload change. | frontend-engineer (sonnet) | — | low (UI only; the snapshot changes are deliberate) | done — verified by lead |
| WS3 | Remove genuine BOE/allotment duplicates, each with at least two consumers migrated (LicenceCopiesSection, QueryBoundary), move the BOE detail query onto the qk factory, and apply small workspace parity fixes. | frontend-engineer (sonnet) | WS2 (fmtFc2 export for OverviewTab; soft dependency) | low (allotment DOM unchanged; the shared components carry the markup over verbatim) | done — verified by lead |
| WS4 | Pin the current BOE API and service behaviour with tests only, so WS5 and the owner decisions are made deliberately. No production code change. | backend-test-engineer (sonnet) | — | low (tests only) | done — 56 new tests, verified |
| WS5 | Hardening that changes no business semantics or success response shape: ProtectedError returns 400 on update, the BOE-side merge is audited and locked, export drops its per-BOE SUM queries, retrieve no longer loads the object twice, and bulk hide/restore normalises ids. | backend-engineer (sonnet), reviewed by cif-balance-auditor | WS4 | medium (merge audit path changes in two endpoints; the reconciliation tests at test_reconciliation.py:465-564 must stay green) | done — reviewed by cif-balance-auditor + django-reviewer |
| WS6 | Write the docs in `docs/erp-architecture/` (this folder). Docs only. | technical-writer | WS3/WS5 for the *verify after* items | low | done — lead refreshed WS3/WS5 items |
| B1 | BOE detail page at `/bill-of-entries/:id`; shared `buildBoeRecordTabs`; card number links to detail. Deferred item 3. | frontend | Phase A | low | implemented, pending lead verification/final gate |
| B2 | BOE-only dirty guard, sticky header/footer, save wrapper in MasterForm (gated on `isBoeForm`). Deferred item 4. | frontend | Phase A | low | implemented, pending lead verification/final gate (review: 2 medium open) |
| B3 | Move BOE create/update into `boe_service.save_boe_with_rows`; serializer 878 to 418 lines; architecture baseline 4 to 0. Deferred item 8. | backend | Phase A | medium | implemented, pending lead verification/final gate (Opus review requested) |
| B4 | Move export to `services/exporters/` with 20 golden tests and 14 snapshots; views_export thin. Deferred item 9. | backend | Phase A | low | implemented, pending lead verification/final gate |

## Owner escalations (verbatim — FORBIDDEN to implement until decided)

1. BUSINESS-RULE / API CONTRACT: changing invoice_no on a genuinely hidden BOE, via update-invoice-no (boe_service.py:321-339) or PATCH (serializers.py:335-337), un-hides it with no RESTORE_BOE log and no `_refresh_licenses`. Setting it back to 'OTH' silently re-hides it. Options: (a) reject with 400 and point to restore-boe, or (b) send the change through restore_boe/hide_boe. Legacy free-text 'OTH' on never-hidden BOEs must stay editable. WS4 pins the current behaviour.
2. PERMISSION / API CONTRACT: AccountAccessPermission._roles (backend/apps/accounts/permissions.py:156) lets the read-only BOE_VIEWER POST update-invoice-no. This contradicts the docstrings and the frontend canEditInvoice. Remove BOE_VIEWER? Confirm no viewer user relies on it.
3. BUSINESS-RULE: the nested BOE update (serializers.py:455-459) deletes frozen ledger rows the client leaves out of the payload. Should frozen rows be immune to form edits (`.exclude(is_frozen=True)`)?
4. BUSINESS-RULE (stored balances): merge_boe moves rows with queryset .update(), so no signals fire and no licence is recomputed. Persist exchange_rate (update_fields currently has only 'port', boe_service.py:301) and refresh touched licences on_commit? Reject merges where exactly one BOE is genuinely hidden?
5. BUSINESS-RULE (stored caches): moving a RowDetails row to another item/licence refreshes only the new licence and item (license/signals.py:533-545, models.py:464-479), so the old licence's balance_cif stays stale. Approve refreshing the old licence/item too? This needs cif-balance-auditor review, is calculate_balance-adjacent, and does not touch A-2.
6. BUSINESS-RULE (data loss): `_apply_restore` checks the raw invoice_no=='OTH' (boe_service.py:438), so restoring a collision BOE that has a real 'OTH' invoice and no HIDE log sets invoice_no to None. Approve guarding restore with `genuinely_hidden_boe_ids`?
7. API CONTRACT: BOE POST is an `update_or_create` upsert keyed on (number, date, port), but the DB constraint is (number, date) (serializers.py:296-326, models.py:234). Null-date BOEs can be silently overwritten or duplicated. Keep the upsert or return 400 with the existing id? A partial unique constraint would be a SCHEMA change and needs duplicates cleaned up first.
8. API CONTRACT: fetch-allotment-details maps every error to 500 (views.py:228-234). Approve 404 for an unknown allotment and 400 for a non-integer id (same {'error'} shape)?
9. SECURITY / BEHAVIOUR: parse-pdf creates CompanyModel by default (views_parse_pdf.py:41-60), which skips CompanyPermission and the MDS write gate. It also echoes exception text (:216) and has no size or page cap. Change the create_company default to false?
10. SECURITY: boe_pdf_copy has no type or size validation and is served inline from the app origin (core/views/media.py:139-151), so stored XSS by an insider is possible. Approve PDF-only validation and Content-Disposition: attachment for anything that is not a PDF or image?
11. UX: drop the BOE Edit Options tab (it duplicates the card actions) and move the card actions into a shared ActionMenu, which renames labels? Should the BOE workspace open on Overview like Licence does, instead of Import Items?
12. Unconfirmed, characterization test first: the BOE-allotment M2M link/unlink has no m2m_changed recompute, and the nested INDIVIDUAL_ITEM CIF ceiling may not add back the row's own debit on edit (serializers.py:82-111). WS4 pins both; any fix needs owner approval and cif-balance-auditor review.

## Deferred backlog

1. boeApi.ts typed mutations plus a useBoeRowActions hook, replacing the raw api.post calls in BoeCardList, MasterList:334/907/1442, MasterForm:299 and useMasterFormCalculations:77. Deferred because it conflicts with WS1/WS2 file ownership; do it next session after they land.
2. Full LicenceCard-style card chrome (StatusBadge for disputes, ActionMenu per record) and removing the Edit Options tab: needs the UX owner decision. Blocked by ConfirmProvider not being mounted.
3. Dedicated /bill-of-entries route on ModuleWorkspace in place of MasterList, and form routes off MasterForm. Wait until the data-layer hooks exist; rollback would be a one-line route swap.
4. MasterForm sticky header/footer for BOE (an isWorkspaceForm gate) and the Button replacements in the BOE copy block: MasterForm is a load-bearing shared file. Do it after WS1 as its own small PR.
5. BOETransferLetter shared states and filter-preserving Back; BoesTab colour tokens and shared states. BoesTab sits next to the user's uncommitted license-overview files (AllotmentsTab, types.ts), so avoid it this session.
6. LicenceCopyLink cell extraction (AllotmentItemsTab and BoeItemsTable): low value, and adopting it in LicenceMappingTab/AllotmentsTable would change the DOM.
7. AllotmentsTable legacy loading/empty migration: a visible allotment UI change outside BOE scope.
8. Moving BOE create/update into boe_service.save_boe_with_rows (ADR-003 rules 2/3, baseline 4 to 0): M-sized, medium risk. Do it after WS4 characterization and the owner decisions on upsert and frozen rows.
9. Moving the BOE exporter to services/exporters, and the shared export_helpers for allotment and BOE: modest value; needs golden export tests first.
10. P7 LEGACY short-circuit in effective_cif_mode.py: protected balance code, and balance_calculator-adjacent files have uncommitted user changes. Needs cif-balance-auditor review.
11. Retiring the legacy apps/core/scripts/ledger.py, and an ADR on the parse_ledger signal disconnect (not thread-safe).
12. Consolidating components/data-table and shared ConfirmDialog (mounting ConfirmProvider): cross-app change outside BOE scope.
13. boe_pdf_copy and parse-pdf file validation: escalated as security behaviour changes; implement once approved.
14. docs/erp-architecture/* files: the content is in docs_facts. Writing them belongs to a docs workstream, not this implementation session.

Item 14 is done by WS6.

## Iteration log (lead)

| # | Iteration | Result / evidence |
|---|---|---|
| 1 | Discovery workflow (7 agents) | 48 findings; plan with 5 file-owned workstreams, 12 owner escalations, 14 deferred items |
| 2 | Implementation workflow (6 WS + 3 reviewers) | All WS done; reviews 3x approve_with_fixes, 0 blocker/major |
| 3 | Lead verification against code | MasterList compact branch, formatter parity, verbatim action move; QueryBoundary (4 consumers) and LicenceCopiesSection (2) confirmed as genuine reuse |
| 4 | BOE Playwright workflow spec (`frontend/e2e/boe-workflow.spec.ts`, 8 tests) | Found 3 real defects, fixed at the shared source: (a) Add New link rendered dark text on blue in **all** registers — the unlayered `a[class*="text-"]` reset in `styles/tailwind.css` beat `text-white`; (b) legacy `.entity-card-stat-label` used `--tb-text-tertiary` (3.6:1, fails AA) instead of the Licence label token; (c) icon-only Add New below `sm` had no accessible name (also failed `trades.accessibility.spec`) |
| 5 | Review fixes | Edit Options Merge gated on `canWrite` (matches card); dead `boeRecordKeys` removed; Overview shows INR to paise (`fmtInrExact`) and unit price at the backend's 0.001 scale; ProtectedError 400 no longer leaks model labels (logged server-side); reconciliation merge with non-integer ids returns 400 (+test) |
| 6 | Gates | see "Verification evidence" |
| 7 | Phase A (D1-D15) | commit `f202cedb`; backend 3339 passed / 1 xfail; frontend 814/814; Playwright 29/29 mocked; 0 false 400s on 1044 local BOEs; no pending migrations |
| 8 | Phase B (B1-B4) | Implemented in working tree; targeted tests only; reviews: B3 approve (read-only), others approve_with_fixes. Pending lead verification, final gate and Opus review. Merge not done. See `docs/boe-modernization/final-audit.md` |

## Verification evidence (post-change)

| Gate | Result |
|---|---|
| Frontend `scripts/dev/quality-gate.sh frontend` | lint PASS (0 errors; 13 pre-existing warnings, none in changed files), typecheck PASS, unit 110 files / 801 tests PASS, build PASS |
| Backend targeted (BOE + reconciliation) | 161 passed |
| Backend `scripts/dev/quality-gate.sh backend` | PASS (exit 0): manage.py check, makemigrations --check, pytest tests/, flake8, ruff F401, app-level tests 3083 passed / 1 pre-existing xfail (includes Licence balance-calculator, ledger and export suites) |
| Playwright mocked suite | boe-workflow 8/8; navigation, license-overview a11y, authenticated shell, login a11y/visual, trades a11y PASS |
| Playwright live/real specs (`*.live`, `*.real`, `item-pivot.sticky`) | NOT RUN — need a seeded live backend + credentials |
| Migrations | none added; `makemigrations --check` clean; no data touched |

## Additional owner items found during implementation

13. BUSINESS-RULE (WS4): re-saving an unchanged INDIVIDUAL_ITEM row is checked against a ceiling that does not add back the row's own debit (pinned in `test_boe_write_edge_cases.py`).
14. API CONTRACT (WS4): `planning_target_item` sent on PATCH is dropped by the nested update (pinned).
15. Behaviour note (WS5): bulk hide/restore now accepts numeric-string ids (previously reported as failed); the frontend already sends ints.

## Next tasks (after this session lands)

| # | Task | Gate |
|---|---|---|
| 1 | Owner decides escalations 1-12, then cif-balance-auditor reviews any balance-adjacent fix | Owner |
| 2 | `boeApi.ts` typed mutations + `useBoeRowActions` (deferred 1) | WS1/WS2 merged |
| 5 | Move BOE create/update into `boe_service.save_boe_with_rows`, ratchet baseline 4 → 0 (deferred 8) | WS4 + owner decisions on upsert/frozen rows |
| 6 | Dedicated BOE route on `ModuleWorkspace` (deferred 3) | Task 2 |
| 7 | Mount `ConfirmProvider`; consolidate the DataTable/ConfirmDialog/EmptyState pairs (deferred 12) | Cross-app approval |

