# Architecture decisions (hub)

Index of record: [ecc-architecture-decisions.md](ecc-architecture-decisions.md) (ADR-001..004, rules 1-9,
LEDGER_*, D1-D9, DR-BOE-1..4, owner decisions). ADR files: `docs/decisions/`, `docs/architecture/`.

## DR-GEN-1 — Generic ERP layer = existing `MasterViewSet` + `MasterList` (2026-11-17)

| Field | Content |
|---|---|
| Problem | The ECC brief asks to "build the generic backend and frontend once". |
| Finding | Both exist and serve 17 core masters + Licence, Allotment, BOE, Trade, Incentive ([matrix](MODULE_MIGRATION_MATRIX.md)). |
| Decision | Reuse. No second CRUD framework. New modules register through `create_viewset(config)` and `masterListConfig`. |
| Alternatives | New generic framework — rejected (duplicate, breaks contracts). |
| Business / data impact | None. Docs only. |
| Status | Accepted (routine, reversible; no code change). |

## DR-GEN-2 — Accounting stays on its own views

Accounting uses `AccountingView` + `AccountingWorkspace` with the posting engine (ADR-004). Moving it to generic CRUD
would bypass document lifecycle and audit. Status: Accepted (records existing state).
