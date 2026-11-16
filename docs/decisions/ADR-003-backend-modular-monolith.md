# ADR-003: Backend modular monolith with enforced boundaries

Status: Proposed (Batch C approved 2026-11-16) · Source: `docs/modernization/backend-audit/00_AUDIT_SUMMARY_AND_PROPOSAL.md` §2-§3

## Context
The backend is one Django project with 8 apps (`accounts, core, license, allotment, bill_of_entry, trade, reconciliation, tasks`). The audit found fat views, financial writes outside atomic services, several balance computations beside `LicenseBalanceCalculator`, and a dense cross-app import graph. It is a live product with frozen API contracts and production data.

## Decision
1. Keep the 8 apps and all tables. No app splits, no table renames.
2. Add layers per app only when needed: `api/` (views, serializers, filters), `services/` (writes), `selectors/` (reads), `domain/` (pure rules), `tasks`, `tests/`. Old module paths stay as re-export shims.
3. One balance engine: `LicenseBalanceCalculator` in `apps/license/services/`.
4. Every financial write goes through a service using `transaction.atomic` (+ `select_for_update` where concurrent) and an audit record.
5. API contracts are frozen; changes are additive only.
6. Schema changes are expand-and-contract, rehearsed on a clone, never destructive without approval.
7. Rules are enforced by `backend/tests/architecture/` (AST, no DB) plus review/CI; see `docs/modernization/ARCHITECTURE_RULES.md`.

## Consequences
- Positive: smaller blast radius for `license/models`, `core/models`; regressions in boundaries fail CI; migration is incremental and reversible.
- Negative: shims add temporary indirection; the import-edge baseline is a ratchet that must be maintained (edges may only be removed).
- Existing debt is baselined, not fixed: 28 cross-app edges, core management commands importing domain models.

## Alternatives rejected
- Microservices / separate deployables: operational cost, no scaling need, cross-app transactions required for financial writes.
- Splitting apps or renaming tables: high-risk migrations on live data for no behavioural gain.
- Big-bang re-layering of all apps: unreviewable; pilot on reconciliation/trade first (Batch E).
- Adding import-linter/new tooling: new dependency; stdlib `ast` tests suffice.
