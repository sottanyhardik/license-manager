# Financial regression test report (Phase 6, 2026-11-17)

Baseline before changes (from prior gate logs): backend app-level 3027 passed / 1 xfailed (`/tmp/lm_be_gate3.log`);
frontend 722 passed (`/tmp/lm_fe_gate4.log`). No pre-existing failures.

## New / changed tests

| Test | What it pins |
|---|---|
| `backend/apps/license/tests/test_license_overview_allotments_view.py::OverviewAllotmentsOutstandingCifScenarioTests` (5) | Scenarios A, B, C (current M2M zeroing), C′ (partial allocation → 25), D (mixed): Σ `outstanding_cif_fc` == `calculate_allotment`; gross `cif_fc` kept |
| same file: shape test (+`outstanding_cif_fc`), query count 5 → 6 (constant at 10 and 50 allotments) | additive contract; no N+1 |
| `backend/apps/trade/tests/test_trade_line_delete_recomputes_totals.py` (5) | API DELETE, last-line delete, queryset delete, incentive line delete recompute header; trade cascade delete does not recompute |
| `frontend/src/pages/license-overview/AllotmentsTab.test.tsx` (footer test rewritten) | headline = Σ outstanding (excludes BOE-linked); gross shown separately |

Independent verification: `cif-balance-auditor` (APPROVE WITH NOTES; ran 138 passed / 1 xfailed) and `code-reviewer`
(approve with nits; ruff + vitest 34 passed). Review notes applied: visible gross/outstanding labels (a11y), cascade
skip, incentive + cascade tests.

## Gate results (after changes)

| Gate | Command | Result |
|---|---|---|
| Area regression | pytest `apps/license/tests apps/trade/tests apps/reconciliation apps/allotment apps/bill_of_entry` (-n 4) | **2315 passed, 1 xfailed** |
| Backend gate | `scripts/dev/quality-gate.sh backend` (log `/tmp/lm_erp_be_gate.log`) | **EXIT 0** — manage.py check, migrations check, `tests/` 246 passed, flake8, ruff, app-level **3041 passed, 1 xfailed** |
| Frontend gate | `scripts/dev/quality-gate.sh frontend` (log `/tmp/lm_erp_fe_gate.log`) | **EXIT 0** — lint, typecheck, 726 tests passed, build |

New failures: none. Pre-existing failures: none. The 1 xfail is the pre-existing strict xfail
`test_post_payment_creates` (nested-only payment serializer).

## Not run / not covered

- Concurrency tests for trade line writes: none exist; not added (no locking change made).
- Decimal-precision tests for `compute_amount` with 3dp rates, mode switch, `''` amount: deferred until T1–T3 decisions
  (adding them now would pin behaviour the owner may change).
- Frontend `TradeForm` float-arithmetic tests: deferred with T8.
- Performance: only the overview-allotments query count was measured (+1 constant). Ledger expand path not re-measured
  (unchanged; doc 09).
- Local DB reconciliation before/after: the fix is display-only; stored values unchanged, so the DB-level "after" equals
  "before" for stored data; the tab footer after-value equals the engine ALLOTMENT CIF by construction (854,817.95 total
  on the 2026-11-17T02:22 snapshot — computed via the engine, the tab endpoint itself was not re-queried on the DB).
