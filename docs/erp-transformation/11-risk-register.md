# 11 — Risk Register

Severity = impact × likelihood (H/M/L). Owner decisions referenced from 12 §B.

| ID | Risk | Sev | Evidence | Mitigation | Status |
|---|---|---|---|---|---|
| R-BL-01 | Financial Ledger shows trade-only running total as "Current Balance" | **H** | `license_balance_ledger_builder.py:666-672`; id 2603: 190,992.45 vs engine 3,962.32; 2,036/2,185 dev licences | Fixed per OD-10 (`ea029f1d`), cif-balance-auditor APPROVE WITH NOTES | **Closed** (follow-ups R-BL-07) |
| R-BL-07 | Trade-only total still labelled as a balance elsewhere (LicensesTable, canonicalLedgerAdapter, deprecated `available_balance` alias, ItemReport); balance Excel calls canonical service without try/except | M | cif audit L1/L2 | Resolve with OD-03 | Open |
| R-BL-02 | Negative balances floored → over-utilisation invisible | H | 13 floors in `balance_calculator.py`; 35 dev licences (−6.96M) | Additive `raw_available` + flag; OD-01 | Open — owner decision |
| R-BL-03 | 4 balance engines diverge (screen vs bulk Excel vs overview cards) | H | 05 DUP-02/07/17/18 | P2 canonical engine | Open |
| R-BL-04 | Invoice PDF total ≠ stored total (rounding mode) | H | 05 DUP-11 | OD-11 | Open |
| R-BL-05 | ARO allotment filter never matches (`'ARO'` vs stored `'AR'`) | M | `core/scripts/calculate_balance.py:55-56` | OD-12 (fix changes stored numbers) | Open |
| R-BL-06 | Allotment write-path validates against stale float/truncated stored qty | M | `allotment/views_actions.py:1341`; 5,996 items differ | P3 after OD-13 | Open |
| R-QA-01 | App-level suite not collected in CI since 2026-10-08 | H | collection ImportError | Fixed `5c509493` | **Closed** |
| R-QA-02 | 7 hidden failures in item-pivot/plan outputs may be real regressions | M | gate-all-2 log | Triage (stale vs regression) | In progress |
| R-QA-03 | No test runs `build()` on a licence with BOEs/allotments | H | 04 | Characterization tests (P0) | Open |
| R-QA-04 | Local DB has 0 trades / 0 allocations → trade & allocation paths unmeasured | M | 03, 07 | Sanitised snapshot (OD-17) or factories | Open |
| R-DB-01 | ORM CASCADE can delete BOE rows/allotments when masters are deleted | H | 03 §1/§8 | `PROTECT` migration (OD-16) | Open — owner decision |
| R-DB-02 | No CHECK constraints on CIF/qty; float money in `ebrc_*`/`eScrap_*` | M | 03 §4 | Constraints after data probe clean | Open |
| R-DB-03 | Activity log unbounded (334k rows, ~55k/month, 11 unused indexes) | M | 03 §2 | Retention policy (OD-18) | Open |
| R-DB-04 | Materialized views stale, wrong (`'DEBIT'`, mixed INR/USD) and unused | L | 03 §6, 05 DUP-16 | Retire (OD-19) | Open |
| R-PERF-01 | Active-licences report 5.8 s / 7,034 queries | M | 07 | P1 prefetch + memo | Open |
| R-PERF-02 | BOE list 1,208 queries/page; per-row balance recompute | M | 07 | P1 memo | Open |
| R-PERF-03 | Item report 61 MB payload, 219 MiB peak | M | 07 | Pagination/GZip | Open |
| R-SEC-01 | Env files tracked in git | H | 08 SEC-01 | Rotate + untrack (OD-06) | Open — owner |
| R-SEC-02 | USER_MANAGER can modify superusers | H | 08 AUTHZ-02 | P4 (no business-rule impact) | Open |
| R-SEC-03 | No tenant/company boundary | H (design) | 08 AUTHZ-01 | OD-04 | Open — owner |
| R-ARCH-01 | Signal-driven balance writes with multiple receivers | M | 02 §12 #2 | Explicit services in P2/P3 | Open |
| R-ARCH-02 | 4/9 Celery beat entries reference missing tasks | M | 02 §12 #4 | CI test + fix | Open |
| R-DOC-01 | Prior autonomous docs claim approvals/freezes that did not happen | M | ED-000 | Treat as leads; archive (OD-08) | Mitigated |
| R-ENV-01 | INSTALLATION.md says bootstrap creates DBs; script doesn't | L | ED-007 | Fix doc or script | Open |
| R-FE-01 | Financial maths duplicated in React (4 rounding policies) | H | 09 §6, 05 DUP-10 | P5 + backend-provided values | Open |
