# 14 — Programme Deliverables A–J (index + gap fill)

_Last updated 2026-11-15, branch `feature/version5`._ Each deliverable points to its authoritative document. Only E and J are written in full here; the others already exist.

| # | Deliverable | Authoritative document | Status |
|---|---|---|---|
| A | Current architecture report | `02-current-architecture.md` (+ `01-system-inventory.md`, `03-database-architecture.md`) | ✅ |
| B | Decision implementation matrix | `12-decisions-register.md` §B0 (approved) + §B (open) | ✅ live |
| C | Approved vs unresolved decisions | `12-decisions-register.md` §A (engineering), §B0 (owner approved), §B (OD-11…OD-20 open) | ✅ live |
| D | Canonical business-logic ownership matrix | `04-business-logic-inventory.md` + `.claude/rules/business-rules.md` (binding rules) + `05-duplicate-logic-register.md` (proposed canonical owner per DUP) | ✅ (D-refresh after P3) |
| E | Regression coverage matrix | **§E below** | ✅ new |
| F | Duplicate-logic and dead-code plan | `05-duplicate-logic-register.md`, `06-dead-code-register.md`, `OD-08-removal-manifest.md` | ✅ manifest ready |
| G | Module execution roadmap | `10-transformation-roadmap.md` (+ `13-completion-checklist.md` live dashboard) | ✅ |
| H | Risk register | `11-risk-register.md`, `docs/security/OD-06-exposure-assessment.md` | ✅ |
| I | Dependency implementation plan | `dependency-register.md` (OD-09) | ✅ |
| J | Performance optimisation plan | `07-performance-baseline.md` + **§J below** | ✅ new |

## E. Regression coverage matrix (financial / business critical)

| Rule / behaviour | Authoritative code | Pinning tests | Gap |
|---|---|---|---|
| Available CIF = Original − (BOE + outstanding allotment + billed-without-BOE), signed (OD-01/02) | `balance_calculator.py::_calculate_financial_balance`, `…_for_licenses` | `test_balance_calculator.py`, `test_financial_ledger_current_balance.py`, `test_financial_ledger_parity_od10.py::test_over_utilisation_is_flagged_with_signed_balance` | Golden master over real licences (needs OD-17 data) |
| Ledger Current Balance = engine (OD-10) | `license_balance_ledger_builder.py::build_financial_ledger` | `test_financial_ledger_current_balance.py` (2) | — |
| `trade_running_balance` separate; COMMISSION excluded (OD-03) | `canonical_ledger_service.py:276-345` | `test_financial_ledger_parity_od10.py` (acquisition once, commission) | Per-company views (OD-03 forbids authoritative per-company, so a test asserting none exist is still to add) |
| Screen = Excel = PDF balance | exporters `license_balance_excel.py`, `license_balance_pdf.py` | `test_financial_ledger_parity_od10.py::test_excel_and_pdf_match_screen`, `test_balance_excel_export.py` | Trade-ledger PDF/Excel vs screen parity (`test_license_ledger_export_parity.py` exists; extend to signed values) |
| Planning capacity never negative (OD-01 companion) | `planning_tolerances.plannable_capacity_cif` + 7 planner entry points | indirect (planner suites) | **Direct unit test for `plannable_capacity_cif` and one planner fed a negative balance** (to add) |
| BOE duplicate exclusion (BOE already billed) | `calculate_debit()` allocation-aware | `test_balance_ledger_views.py` reconciliation classes, `test_boe_invoice_representation.py` | — |
| Outstanding allotment | `calculate_allotment()` | `test_balance_calculator.py` | AR vs AT semantics untestable until OD-12 |
| Item pivot planned/unplanned separation (OD-21) | `item_pivot_service.py` | `test_item_pivot_planned_import_item.py` (2), `test_item_pivot_planned_unplanned_separation.py` (7) | in review |
| Ledger CSV ingestion (ICEGATE quirks) | `scripts/parse_ledger.py` | `tests/test_ledger_parser.py` (8) + synthetic fixtures | — |
| Frontend never recomputes financial values (rule 8) | — | `FinancialSummarySection.test.tsx` | Item Report totals, LedgerTab item-sum (D-2/D-3, decisions pending) |
| API contract | drf-spectacular schema | `scripts/dev/openapi_gate.sh` (0 errors / 22 warnings ratchet) | Schema snapshot diff test (to add with OD-07) |

## J. Performance optimisation plan (measure → fix → re-measure, outputs must be identical)

Baseline: `07-performance-baseline.md`, scripts in its Appendix A (re-run for "after" numbers).

| Order | Target | Baseline | Fix | Output guard |
|---|---|---|---|---|
| 1 | BOE list/detail | 1,208 q/page; 849 q detail | per-request balance memo (`financial_balance_memo()` already exists) + bulk `calculate_financial_balance_for_licenses` in serializer context | byte-identical JSON vs baseline + `assertNumQueries` ceiling |
| 2 | Active licences report | 5.8 s / 7,034 q | prefetch item names (`active_licenses_report.py:225`); bulk balances | identical rows/totals |
| 3 | Licence detail / nested_items | 289 / 771 q | prefetch at `serializers/license.py:382,417,451` | identical JSON |
| 4 | Balance PDF/Excel (largest licence) | 701 / 423 q | prefetch in per-item loops (`license_balance_pdf.py:784-828`, `license_balance_excel.py:837-860`) | parity tests above |
| 5 | Item report payload | 61 MB / 219 MiB | `GZipMiddleware` + pagination (pagination = API change → OD-07 v1 only) | identical data |
| 6 | Item pivot | 856 ms, 169× `latest_transfer` | prefetch at `models/core.py:846` | pivot tests |
| 7 | Frontend | 92 files raw axios | TanStack Query migration per module (P11) | vitest + e2e |

No fix may change a business number; each lands with a query-count test and a before/after table in the phase report.
