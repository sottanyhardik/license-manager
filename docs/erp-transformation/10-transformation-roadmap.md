# 10 — Transformation Roadmap

Principle: **understand → measure → design → implement → verify**, one module at a time. Each step is
small, reversible and gated by `scripts/dev/quality-gate.sh all` + output-equality checks against the
baselines in 04/07. Anything that changes a user-visible number waits for an owner decision (12 §B).

## Target architecture (modular monolith; adapt, don't impose)

```
backend/apps/
  core/            leaf: base models, audit, permissions primitives, money/qty value helpers
  masters/         (OD-05) companies, ports, HS, SION, item names
  license/         domain + services/ledger/  ← ONE balance engine (calculations/*.py, pure functions over a snapshot)
  allotment/  bill_of_entry/  trade/          depend on license services via explicit service APIs only
  reconciliation/  reports/ (exports reuse the same calculation outputs)
```

Rules: views = parse → service → serialize; balance numbers produced only by `license.services.ledger`;
exports/PDF/Excel/dashboard/Celery consume its dataclass output; React never recomputes financial values
(previews explicitly labelled and test-compared). Import contracts enforced in CI (import-linter, OD-09).

## Phases and order (dependency-driven)

| Phase | Scope | Exit criteria | Blocked by |
|---|---|---|---|
| **P0 Baseline** (in progress) | Green gate; characterization tests for balance/ledger/export outputs on real-shape fixtures; perf baseline (07) | Gate green; DUP-01..12 pinned by tests | — |
| **P1 Safe performance** | BOE list/detail + trade serializer per-request balance memo; active-licences prefetch; licence detail `nested_items` prefetch; GZip; drop 16 duplicate indexes (migration, reversible) | ≥10× fewer queries on top 5 endpoints, byte-identical JSON vs baseline | — |
| **P2 Canonical balance engine** | One `LedgerSnapshot` loader + pure calculation functions; existing engines delegate to it; components exposed separately (BOE / allotment / billed-without-BOE / utilised / available / raw_available / over_utilised flag) | All 4 engines return identical values to today (or the approved new values) | OD-10, OD-01, OD-02 |
| **P3 Allotment / BOE / Invoice** | Move allocation orchestration out of `views_actions.py`; single outstanding-allotment rule; invoice totals from stored values | Domain auditors sign off | OD-11, OD-12, OD-13..15 |
| **P4 Security** | AUTHZ-02 fix, fail-closed settings, media default-deny, upload validation, token revocation; secrets rotation | security-auditor pass | OD-06, OD-07 |
| **P5 Frontend platform** | `DataTable` list engine (TanStack Table + server pagination) → migrate lowest-risk lists first; `FormField`/form engine; typed API layer (generated types); TanStack Query everywhere; strict TS per folder | No raw `<table>` in migrated modules; no client-side financial maths | OD-09 (deps) |
| **P6 Licence Workspace** | One workspace (summary, CIF components, ledger, BOE, allotments, invoices, reconciliation, audit) replacing 4 balance views | UX sign-off; old routes redirect | P2 |
| **P7 Data & ops** | CASCADE→PROTECT on financial FKs, CHECK constraints, activity-log retention, MV retire/fix, settings split, beat-task fixes | DB integrity probes clean | OD-16..19 |
| **P8 Dead code & docs** | Remove 06 §A batch; archive root reports/scripts; update docs/ | References verified, gate green | OD-08 |

## Module order (from discovered dependencies)

core/auth → licence ledger (balance engine) → allotments → BOE → invoices/trades → reconciliation →
planning (SION) → dashboard → reports/exports → masters/MDS → admin/settings. Customers/suppliers are
`CompanyModel` masters (no separate module exists) and travel with masters.
