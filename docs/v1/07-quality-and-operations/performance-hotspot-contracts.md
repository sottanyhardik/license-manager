# Performance hotspot contracts

**Bounded source/test audit; not a production benchmark.** This register
captures existing query-count and response-time guards along with directly
observed code risks. Query counts are fixture/database/backend dependent; an
assertion below proves only its named test scenario. No load, browser timing,
query plan, data-volume, worker or production result is claimed.

Evidence labels: **C** = code, **T** = named test, **S** = static-risk
evidence, **P** = proposed V1 gate. Every contract is **Partial** until its
production-like data distribution, authorization path and measurable budget
are established.

| ID / workload boundary | Current query/performance evidence | What it proves and does not prove | V1 measurement / acceptance needed | Status |
| --- | --- | --- | --- | --- |
| PH-01 Allotment list | **T** `test_allotment_list_performance_contract.py:138` records a cold nine-row list and asserts at most 6 queries; one-row versus nine-row differs by at most 1. | Bounded fixture serialization/filter/list behavior; not index selectivity, result-size, cache or browser time. | Run `EXPLAIN (ANALYZE, BUFFERS)` on approved representative filters; define p95 API and page-size budget. | P1 / Partial |
| PH-02 Plan availability candidates | **T** `test_available_licenses_plan_mode.py:113` asserts an 8-row plan page uses at most 17 queries and grows by at most 2 versus one row. | Protects against a per-plan-line query in fixture data. It does not test concurrent allocation or large restriction pools. | Measure candidate count/page/filter cardinalities and p95 under a disposable production-shaped DB. | P0/P1 / Partial |
| PH-03 Active DFIA report | **T** `test_active_dfia_report_view.py:347` compares five and fifteen licences after batching live balance. **C** report view explicitly owns cross-company report filtering. | Captures a specific batched balance regression. Its own test documents two remaining per-licence queries (`total_cif` aggregate and `get_item_by_head`). | Resolve or budget the two known N+1 follow-ups; compare JSON/XLSX parity and report latency with a representative exporter. | P1 / Partial |
| PH-04 Bulk item available value | **T** `test_balance_cif_single_source.py:253` asserts `available_value_bulk_map` has identical query count for one and multiple items/licences. | Batch helper parity in a small fixture; no live balance/end-user endpoint timing. | Add mixed condition-pool, hidden/correction and high-cardinality cardinality cases plus query plan evidence. | P0 / Partial |
| PH-05 Canonical ledger dataset | **T** `test_canonical_ledger_performance.py:73,99,126` bounds small ledger below 15 queries and large fixture below 25 while comparing low/high transaction sets for N+1. | Service-level query protection. **C** it is read-only and assumes authorization was already applied. | Define ledger transaction/company scale, database/index plan and p95 package/report latency; do not use service test as download authorization proof. | P0/P1 / Partial |
| PH-06 Canonical ledger PDF path | **T** `test_ledger_pdf_live_balance.py:266,320` sets fixture ceilings of <50 simple and <100 moderate queries. | Basic data-build budget only; renderer CPU/PDF size/storage time are not measured. | Measure end-to-end render bytes, pages, latency/memory and package worker throughput with controlled documents. | P1 / Partial |
| PH-07 Overview allotments tab | **T** `test_license_overview_allotments_view.py:90` asserts exactly 5 queries for ten and fifty allocation rows. | Read-only endpoint batch behavior with fixture objects; not permission/object policy or real DB plan. | Preserve this invariant when fields/actions change; add pagination/large-document/role paths if applicable. | P1 / Partial |
| PH-08 Overview BOEs tab | **T** `test_license_overview_boes_view.py:101` asserts exactly 4 queries for ten and fifty BOE rows. | Prevents fixture N+1 across BOE rows; not export/download or hidden/correction-scale timing. | Include hidden/frozen/dispute rows, production-shaped BOE counts and index-plan evidence. | P1 / Partial |
| PH-09 Licence plan presentation/utilization | **T** `test_license_plan_presentation_service.py:733` and `test_plan_utilization.py:314` contain query-count guards; the latter explicitly tests batched item status. | Bounded plan-read batching, not planner execution/replan worker throughput. | Measure licence/item/plan-line scale, materialized/live interaction and p95 planning-workspace response. | P0/P1 / Partial |
| PH-10 Parle licence report | **T** `test_license_report_view.py:321` compares small/larger report fixtures after financial-balance batching. | Protects the named live-balance batching change; report body/file size and aggregate/report index plan remain unmeasured. | Add report output volume, exporter filter selectivity, XLSX generation and D2-labelled output budgets. | P1 / Partial |
| PH-11 Planned report | **T** `test_planned_report_view.py:301` compares five and fifteen licence/plan rows after batched financial balance. | Detects per-row financial balance query growth for this fixture. | Test active filters, zero/large results, export rendering and cache behavior with a controlled DB. | P1 / Partial |
| PH-12 Trade list with payments | **T** `test_trade_list_query_budget.py:15` caps a four-row list at 10 queries; `test_trades_contract_parity.py:217` caps nine at 14. | Preserves prefetched payment totals/paired trade behavior. It does not characterize document joins, user scope or browser rendering. | Add high-cardinality payment/document/trade cases, query plans and pagination p95 budget. | P1 / Partial |
| PH-13 Generic API response time smoke | **T** `backend/tests/test_api_integration.py:389` has <5 second licence-list and dashboard wall-clock checks. | A permissive test-environment smoke bound only; timing is not stable enough for a release SLO or production capacity statement. | Replace/add controlled p50/p95/p99 load methodology, data size, hardware, cache state and error-rate threshold. | P2 / Partial |
| PH-14 Frontend/browser performance assets | **S** `frontend/e2e/trades.performance.spec.ts` and `tests/e2e/qa_phase21_performance.py` expose performance-oriented assets; the documented Playwright run is 68 pass/54 fail/8 skip. | Assets exist but are not a passing or production performance result; known harness failures invalidate broad browser conclusions. | Repair deterministic E2E defects, then collect route-specific navigation/render/network budgets in seeded, disposable environments. | P1 / Partial |
| PH-15 Static centrality/cache risk | **S** [performance baseline](performance-baseline.md) lists high-dependent modules; cache signals and materialized views are dynamic correctness/performance boundaries. | Import count is blast radius, not latency. Cache hit rate/invalidation delay/eviction behavior is not measured. | Instrument cache hit/miss/invalidation and materialized-view freshness; define read-after-write and stale-display acceptance separately from authorization. | P1 / Partial |

## Measurement protocol and guardrails

1. Use only a disposable or explicitly approved non-production database with
   documented schema/data shape. Do not collect business-record timings from
   the deployed application.
2. Record query count, SQL plan, row estimates/actual rows, duration, cache
   state, response/file bytes, worker/storage duration and error rate as
   separate measurements. One cannot substitute for another.
3. Establish budgets from a baseline before setting regression thresholds.
   The numerical ceilings in existing fixture tests are regression guards,
   not approved service-level objectives.
4. For financial/entitlement reads, retain D2/D3 golden-output checks beside
   performance checks. A faster result with a changed engine or stale data is
   not an acceptable optimization.

## Recommended implementation order

Start with PH-02, PH-04, PH-05, PH-09 and PH-15 because they feed allocation,
balance, planning and authorization-adjacent high-frequency reads. Follow
with reports/exports (PH-03, PH-06, PH-10–12), then browser/load work after
the E2E harness is repaired. This is a proposed V1 sequence, not a measured
impact ranking.
