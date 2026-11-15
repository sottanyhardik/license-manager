# 13 — Completion Checklist (live transformation dashboard)

_Last updated: 2026-11-15 · branch `feature/version5`_

## Phase Zero — discovery

| Doc | Status |
|---|---|
| 00 Executive assessment | ✅ |
| 01 System inventory · 02 Current architecture | ✅ (prior session, kept) |
| 03 Database architecture | ✅ (read-only probes, dev DB) |
| 04 Business-logic inventory · 05 Duplicate-logic register | ✅ (25 DUP entries) |
| 06 Dead-code register | ✅ (removals await OD-08) |
| 07 Performance baseline | ✅ (40 endpoints; scripts in Appendix A) |
| 08 Security · 09 UI/UX | ✅ (prior session, kept) |
| 10 Roadmap · 11 Risks · 12 Decisions · 13 Checklist | ✅ |

## Quality-gate baseline

| Gate | Before (gate-all) | Now (gate-all-2) |
|---|---|---|
| frontend lint | ❌ 3 errors | ✅ (9 pre-existing warnings) |
| frontend typecheck / build | ✅ / ✅ | ✅ / ✅ |
| frontend vitest | ❌ 1/544 | ✅ 544/544 |
| backend check / migrations | ✅ / ✅ | ✅ / ✅ |
| backend `tests/` | ❌ 5 failed / 232 | ✅ 237/237 |
| backend app-level | ❌ collection error (0 run) | ❌ 7 failed / 2,700 passed — triage |
| MDS pytest | ❌ (no local role) | ✅ |
| mds-client | ❌ (env leak) | ✅ 25/25 |

## Phases

| Phase | Status | Notes |
|---|---|---|
| P0 Baseline | 🟡 in progress | gate fixes `5c509493`; 7 failures in triage; characterization tests next |
| P1 Safe performance | ⏳ | ready to start (no owner input needed) |
| P2 Canonical balance engine | ⛔ blocked | OD-10, OD-01, OD-02 |
| P3 Allotment/BOE/Invoice | ⛔ blocked | OD-11..15 |
| P4 Security | ⏳ | AUTHZ-02 can start; secrets need OD-06 |
| P5 Frontend platform | ⏳ | dependency choices OD-09 |
| P6 Licence Workspace | ⏳ | after P2 |
| P7 Data & ops | ⛔ blocked | OD-16..19 |
| P8 Dead code & docs | ⛔ blocked | OD-08 |

## Module gates (per module: ✅ done · 🟡 partial · — not started)

| Module | Documented | Outputs captured | Dup logic id'd | Canonical reused | Tests | Perf | Security | Reviewed | Rollback |
|---|---|---|---|---|---|---|---|---|---|
| Licence ledger / balance | 🟡 | 🟡 | ✅ | — | 🟡 | ✅ | — | — | — |
| Allotments | 🟡 | — | ✅ | — | 🟡 | ✅ | — | — | — |
| BOE | 🟡 | — | ✅ | — | 🟡 | ✅ | — | — | — |
| Trades / invoices | 🟡 | — (no dev data) | ✅ | — | 🟡 | ❌ not measurable | — | — | — |
| Reconciliation | 🟡 | — | 🟡 | — | 🟡 | ✅ | — | — | — |
| Planning (SION) | 🟡 | — | 🟡 | — | 🟡 | 🟡 | — | — | — |
| Dashboard / reports / exports | 🟡 | 🟡 | ✅ | — | 🟡 | ✅ | — | — | — |
| Auth / permissions | ✅ | — | — | — | 🟡 | — | ✅ assessed | — | — |
| Frontend platform | ✅ | — | ✅ | — | ✅ vitest | ✅ bundle | — | — | — |
