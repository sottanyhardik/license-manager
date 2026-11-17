# Architecture decisions — index and BOE session records

Precedence: project `.claude/rules` > ADR-003 + `ARCHITECTURE_RULES.md` > vendored `.claude/rules/ecc` (see [README](README.md)).
This file links to existing decisions. It does not copy them.

## 1. Existing decisions (index)

| ID | File | Status | Scope |
|---|---|---|---|
| ADR-001 | `docs/architecture/ADR-001-master-data-service.md` | see file | Master-data service (MDS) |
| ADR-002 | `docs/architecture/ADR-002-auto-plan-representative-selection.md` | see file | Auto-plan representative selection |
| ADR-003 | `docs/decisions/ADR-003-backend-modular-monolith.md` | Proposed; Batch C approved 2026-11-16 | Backend layering: `api/ services/ selectors/ domain/`, one balance engine, atomic+audited financial writes, frozen API |
| Rules 1-9 | `docs/modernization/ARCHITECTURE_RULES.md` | Enforced (ratchets) | `backend/tests/architecture/test_architecture.py` |
| LEDGER_* | `docs/decisions/LEDGER_APPROVED_SEMANTICS.md`, `LEDGER_BALANCE_CONVENTION_DECISION.md` | see files | Ledger semantics and balance sign convention |
| 2026-11-17 | `docs/decisions/2026-11-17-trade-line-pricing-and-m2m-consumption.md` | Approved (M2M) | Trade-line pricing, M2M consumption. **Present in the main checkout only (untracked); not in this worktree's base.** |
| D1-D9 | `docs/modernization/DECISION_REGISTER.md` | D1-D4 approved 2026-11-16; D5-D9 proposed | Unified Licence / BOE / Allotment workspace |
| OD-BA-a/b/c, OD-QTY, OD-MAP | `DECISION_REGISTER.md` | Open | Supplier source, normalisation, product key, quantity, mapping |
| Owner 2026-11-17 | project memory | A-1, T1-T4, M2M approved; **A-2 and T5-T9 frozen** | Do not implement frozen items. |
| Business rule | `.claude/rules/business-rules.md` | Canonical | CIF buckets; Decimal only; no double counting |

## 2. Decision records for this session

Status of all four: **Accepted for this session by the lead plan**. None changes business rules, API shapes or schema.

### DR-BOE-1 — BOE reuses the shared workspace components

| Field | Content |
|---|---|
| Problem | BOE UI drifted from Licence: own spinner/empty markup, legacy `primitives/EntityCard`, routes on generic `MasterList`/`MasterForm` (`frontend/src/routes/AppRoutes.tsx:175-189`). |
| Existing implementation | `components/workspace/{ModuleWorkspace,DetailTabs,ModuleAccordion}.tsx`; `components/shared/*`. `DetailTabs` is used by Licence, Allotment and BOE record workspaces. **`ModuleWorkspace` has 0 production consumers today** (only `workspace.test.tsx`). |
| Proposed solution | BOE uses `DetailTabs` (already), shared `LoadingState`/`EmptyState`/`InlineError`/`ActionMenu`, the Licence compact register branch of `MasterList` (WS1), and `ModuleWorkspace` only when the dedicated BOE route lands (deferred). |
| Alternatives | (a) BOE-specific components — rejected, duplicates. (b) Move BOE to `ModuleWorkspace` now — deferred until data-layer hooks exist. |
| Business impact | Same records, fields and actions. Viewers stop seeing write buttons that return 403 (WS2). |
| Technical impact | Fewer duplicates; snapshot updates for BOE are deliberate; Licence snapshot must not change. |
| Data-integrity impact | None. Presentation only. Endpoints and payloads unchanged. |
| Testing requirements | `npx vitest run src/pages/masters src/features/bill-of-entry`; Licence snapshot unchanged; typecheck + lint. |

### DR-BOE-2 — Reference implementations

| Field | Content |
|---|---|
| Problem | No agreed "copy this" pattern for BOE. |
| Existing implementation | UI: `features/licenses` (`useLicenceRowActions.ts:35`, `licenceActionItems.ts:29`, `LicenceCard.tsx`, `LicenseRecordWorkspace.tsx`). Backend writes: `apps/reconciliation/services/allocation_service.py:224-416` (`transaction.atomic` + `select_for_update` + `ReconciliationLog` in the same transaction). |
| Proposed solution | **Licence = UI reference. `allocation_service` = backend write reference.** Licence is *not* the backend reference: it writes from serializers (`apps/license/api/serializers/_license_write.py`). |
| Alternatives | Use licence backend as reference — rejected for the reason above. |
| Business impact | None directly. |
| Technical impact | BOE create/update should move to a service (`boe_service.save_boe_with_rows`) later; baseline `('bill_of_entry','serializers','RowDetails'): 4` (`test_architecture.py:229`) goes to 0. Deferred. |
| Data-integrity impact | Positive once applied (locks + audit). Not applied this session. |
| Testing requirements | WS4 characterization tests before any move. |

### DR-BOE-3 — Extract `LicenceCopiesSection` and `QueryBoundary`

| Field | Content |
|---|---|
| Problem | Allotment and BOE `DocumentsTab` duplicate the licence-copy dedup + section markup. BOE tabs hand-roll the loading/error/data switch that `features/allotment/DetailQueryBoundary.tsx` already has. |
| Existing implementation | `features/allotment/tabs/DocumentsTab.tsx:19-51`; `features/allotment/DetailQueryBoundary.tsx` (allotment-only, 3 consumers). |
| Proposed solution | `components/workspace/LicenceCopiesSection.tsx` and generic `components/shared/QueryBoundary.tsx`; `DetailQueryBoundary` becomes a thin wrapper. Markup moved verbatim (WS3). |
| Alternatives | Leave duplicates — rejected (two consumers each). Generic `LicenceCopyLink` cell — deferred (DOM change). |
| Business impact | None. |
| Technical impact | Two new shared components; allotment DOM unchanged. |
| Data-integrity impact | None. No requests until a button is pressed (unchanged). |
| Testing requirements | Unit tests for dedup/empty and pending/error-retry/data; `AllotmentRecordWorkspace` and `BoeRecordWorkspace` tests incl. "each tab requests only its own endpoint". **Verified** — QueryBoundary: 4 consumers; LicenceCopiesSection: 2; allotment snapshots unchanged. |

### DR-BOE-4 — Unify BOE merge audit and locking

| Field | Content |
|---|---|
| Problem | Two merge endpoints. Reconciliation `/reconciliation/merge-boe/` writes a `MERGE_BOE` log in the view (`apps/reconciliation/api/views.py:183-189`). BOE `/bill-of-entries/{id}/merge/` writes none (`apps/bill_of_entry/api/views.py:257-270`). `merge_boe` takes no row locks (`boe_service.py:203-318`). Violates ARCHITECTURE_RULES rule 3. |
| Existing implementation | `boe_service.merge_boe` atomic block at `boe_service.py:244`; `ReconciliationLog.ACTION_MERGE_BOE` exists (`apps/reconciliation/models.py:107`). |
| Proposed solution | `merge_boe(..., *, user=None)` writes the log inside the service, re-fetches target/source with `select_for_update` ordered by id; reconciliation view drops its own log write. Error shapes stay (`{'error'}` vs `{'detail'}`). (WS5) |
| Alternatives | Add a log write in the BOE view too — rejected (rule 1/3: audit belongs in the service). |
| Business impact | BOE-side merges become auditable. Merge semantics unchanged. |
| Technical impact | One existing action value reused; no schema change. |
| Data-integrity impact | Locks remove a concurrent-merge race. **Not in scope:** `exchange_rate` persistence (`update_fields=["port"]`, `boe_service.py:301`) and licence refresh after `.update()` — owner escalation. |
| Testing requirements | WS4 pins 0 BOE-side logs / 1 reconciliation log; WS5 flips BOE-side to 1; `reconciliation/tests/test_reconciliation.py` stays green; `cif-balance-auditor` reviews the diff. **Verified** — BOE-side merge writes 1 log, reconciliation 1 (single writer, no double write); BOE + reconciliation tests pass; reviewers approved. |
