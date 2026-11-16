# Backend Architecture Audit, Target Architecture and Proposal

Date 2026-11-16 · base `b68ec7fd` (feature/v5, pushed) · **Phase 1 audit only. No code changed.**
Evidence: [01 structure & coupling](01_STRUCTURE_AND_COUPLING.md) · [02 logic placement & financial safety](02_LOGIC_PLACEMENT_AND_FINANCIAL_SAFETY.md) · [03 queries, tests, migrations](03_QUERIES_TESTS_MIGRATIONS.md).

## 1. Audit summary

| Area | Finding | Severity |
|---|---|---|
| Size / ownership | `license` is 53.9k LOC (132 files, 33 models, 62 service modules), about 3× `core`. 21 production files are over 800 LOC. `LicenseDetailsModel` has about 80 methods | HIGH (maintainability) |
| Coupling | No module-level file cycles. App-level cycles: 7 module-level, 74 including function-local edges, from 9 app pairs (allotment↔license, license↔trade, license↔reconciliation, …) | MED |
| Logic in views | Allocation workflow (about 500 LOC) lives in `allotment/views_actions.py:1071-1570`; the existing `AllocationService` is unused by the views, so two paths can drift. Recalculate action is a multi-write in a view | HIGH |
| **Financial write safety** | BOE create/update (serializer → `MasterViewSet.perform_create/update`) is **not atomic**. `destroy_allotment` has no atomic and no audit. TradeLine/TradePayment CRUD and MasterViewSet deletes are non-atomic. `RowDetails.save` silently drops frozen-row writes. There is no `ATOMIC_REQUESTS` | **HIGH** |
| Audit history | No entity-level audit for RowDetails / AllotmentItems / import-item value / TradeLine / LicenseBalance edits. `allotment.AuditEvent` has no writer | MED |
| **Second sources of truth** | Billed-CIF-by-M2M (`item_usage.py`, `serializers/license.py:378-420`) vs. the calculator's allocation-driven exclusion; `condition_pool.py` raw sums feeding `available_value`; `planning_usage_reconciliation` gross−BOE−allotment; `canonical_ledger_service` running balance; matview SQL (`cif_inr`, no readers found); `LicenseBalance` cache not refreshed after reconciliation allocations | **HIGH (business rule)** |
| Queries | `/api/license-item-plans/` about 37 queries per row (1,848 at page 50); sion-classes and item-names N+1; activity-log list unpaginated; per-item `.exists()` in exporters | HIGH / MED |
| **Tests** | **CI and `quality-gate.sh` run only `tests/`, `apps/license`, `apps/core`.** About 280 tests (allotment, reconciliation, trade, BOE, accounts, tasks) are never run in CI. Run now: 265 pass, **2 fail, both pre-existing at `05b6a1b2`**: `test_16_pair_mismatch_rejected` (allocation pair mismatch accepted, **201 instead of 400**, which looks like a real defect) and a plan-mode query-count ceiling (17 > 16). 3 `tests.py` files are never collected. No factories | HIGH |
| Verified bug | `license/views/ledger.py:154,156`: `LicenseLedgerPackageJob` is not imported in `_enqueue_download_request`, so a NameError after `.delay()` means `root_task_id` / `dispatch_failed` are never recorded | HIGH |
| Lint | No Python linter in CI. pyflakes: 543 messages (271 unused imports, about 180 redefinitions, 3 undefined names: 2 real, see above) | MED |
| Dead code | About 5.2k LOC with no production users (e.g. `api_utils/`, `core/utils/pdf_helpers.py`, `license/item_report.py`, `license/tables.py`, unused `license/models/invoice.py` models). `core/signals_materialized_views.py` is never registered | LOW (needs approval to remove) |
| Migrations | Consistent (`makemigrations --check` clean). No `AddIndexConcurrently` anywhere. No squash recommended | OK |

**Correction to earlier reports today:** "all gates pass / 2,720 backend tests" covered only the paths CI collects. Including the uncollected suites, the true baseline is **2 pre-existing failures** (above).

## 2. Target architecture (Modular Monolith)

Keep the 8 existing apps and their tables. Changing app labels or moving models is out of scope without an ADR. Each app grows only the layers it actually needs:

```
backend/apps/<app>/
  models/            persistence + DB constraints (existing)
  api/               HTTP layer — introduced per app when its views are touched
    views/  serializers/  filters/   (old module paths kept as re-export shims)
  services/          business operations; owns transaction.atomic + select_for_update + audit writes
  selectors/         reusable read queries (only when ≥2 callers share a query)
  domain/            pure, ORM-free rules/calculations (Decimal in, Decimal out)
  tasks.py           Celery entry points → call services only
  tests/             unit (domain), integration (services/selectors), API, regression
```

**Licence balance stays single-sourced:** `license/services/balance_calculator.py` (`LicenseBalanceCalculator`) is the only engine. Anything that needs a balance calls it, or its `*_for_licenses` batch siblings. A future `license/domain/balance.py` may hold its pure arithmetic, but only behind the same public API and with a cif-balance-auditor review.

## 3. Architecture rules (proposed; to become `docs/decisions/ADR-003-backend-modular-monolith.md`)

1. Views orchestrate HTTP only: parse/validate (serializer), then call a service or selector, then respond.
2. Serializers validate and represent. They never write to other models or compute balances.
3. Every financial write (BOE rows, allotment items, import-item values, trades/lines/payments, allocations, LicenseBalance, ledger/recon rows) goes through a service that uses `transaction.atomic`, `select_for_update` where concurrent, and an audit record.
4. Balances come only from `LicenseBalanceCalculator`. Re-deriving balance math elsewhere is a defect.
5. `core` is the kernel and imports no domain app at module level (enforced by a test). Cross-app access goes through the target app's `services` / `selectors` / models, never its `views`.
6. Read endpoints have query-count regression tests. N+1 is a defect.
7. API contracts are frozen: changes are additive only.
8. Schema changes are expand-and-contract, rehearsed on a clone, and never destructive without approval.
9. CI runs every app's tests, and Python lint (undefined names at minimum) gates merges.

## 4. Proposed implementation batches (approval requested)

| Batch | Content | Behaviour change | Risk |
|---|---|---|---|
| **A. Verified defects + CI coverage** | Fix the `ledger.py` NameError import. Make CI + `quality-gate.sh` collect all app tests. Rename the 3 uncollected `tests.py` files. Add pyflakes undefined-name gate (flake8 `F821/F822/F823`, already pinned). Root-cause `test_16_pair_mismatch_rejected` and the query-count test, and report before fixing (allocation validation is business logic) | Fixes broken dispatch-status recording; none otherwise | Low |
| **B. Transaction safety** | Wrap BOE create/update, `destroy_allotment`, TradeLine/TradePayment CRUD and MasterViewSet deletes in `transaction.atomic`. The success path is identical; a partial failure now rolls back instead of leaving half-written rows | Rollback on failure only | Low |
| **C. Architecture guardrails** | ADR-003 + `ARCHITECTURE_RULES.md`. AST-based pytest architecture tests: no module-level core→domain imports, no new app cycles (ratchet on today's edge count), views never import other apps' views | None | Low |
| **D. N+1 fixes** | license-item-plans, sion-classes, item-names, activity-log pagination (paginating changes response shape, so that item needs approval), exporter `.exists()` loops. Byte-identical JSON proof on a clone | None (except pagination) | Low–Med |
| **E. Layering pilot** | `api/` + `selectors/` in **reconciliation** and **trade** (small, already cohesive), with shims at old paths | None | Low |
| **F. Allocation consolidation** | Move the allotment allocation workflow from `views_actions.py` into `AllocationService` (characterization tests first, cif-balance-auditor + boe-reconciliation-auditor) | None intended | **High** (financial) |
| **G. Second-source-of-truth consolidation** | Route billed-CIF / condition_pool / planning reconciliation / canonical ledger through the calculator, or prove equivalence with tests | Possibly numeric, so a **BUSINESS-RULE** decision per item | **High** |
| **H. Entity audit history** | Write audit events for financial edits/deletes | New audit rows (new behaviour) | Med |
| **I. Dead-code removal** | About 5.2k LOC listed in 01 §7 | Removes code | Low (needs approval) |
| **J. Big-file splits** | `item_pivot_report.py`, `license/models/core.py`, exporters, behind re-exporting packages | None | Med |

Recommended order: **A → B → C → D → E**, then F/G/H only after owner decisions. I and J can run whenever approved.
