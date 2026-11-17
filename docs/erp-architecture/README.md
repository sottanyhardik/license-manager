# ERP architecture — index (BOE modernization)

This folder holds the **working notes for the BOE ERP modernization**. It does **not** define a new architecture.
Line references point to base commit `9fc44ad3` (feature/v5) unless stated otherwise. Files that a concurrent
workstream is editing are marked *verify after WSn*.

## Which standard wins (precedence)

| Rank | Source | What it is |
|---|---|---|
| 1 | `.claude/rules/{business-rules,backend,frontend,safety}.md` | Project rules. Canonical CIF rule and protected areas. |
| 2 | `docs/decisions/ADR-003-backend-modular-monolith.md` | Backend layering. Status: Proposed, Batch C approved 2026-11-16. |
| 3 | `docs/modernization/ARCHITECTURE_RULES.md` (rules 1-9) | How ADR-003 is enforced. AST ratchets: `backend/tests/architecture/test_architecture.py`. |
| 4 | `docs/modernization/DECISION_REGISTER.md`, `docs/ui-modernization/DESIGN_SYSTEM.md`, `COMPONENT_STATUS.md`, `docs/modernization/frontend-audit/05_REUSABLE_COMPONENT_SPEC.md` | Workspace/UI decisions and component specs. |
| 5 | `.claude/rules/ecc/{common,python,typescript,react,web}` | **Vendored Everything-Claude-Code (ECC) rule set.** Generic style, patterns, security and testing guidance. No project ADRs. Lowest precedence. |

"ECC" in file names here means "decisions recorded under this workflow". It does not mean the vendored rules are the architecture.

## Documents

| File | Content |
|---|---|
| [ecc-architecture-decisions.md](ecc-architecture-decisions.md) | Index of existing ADRs/decisions + this session's decision records (DR-BOE-1..4). |
| [module-architecture-map.md](module-architecture-map.md) | BOE operation ownership (file:line, transaction, audit) + Licence/Allotment module map. |
| [shared-service-registry.md](shared-service-registry.md) | Reusable backend services and frontend shared modules. |
| [api-contract-standards.md](api-contract-standards.md) | Pagination, envelopes, error shapes (frozen), permissions. |
| [generic-component-registry.md](generic-component-registry.md) | Generic / refactor / new / module-specific / deprecated components with consumer counts. |
| [shared-ui-standards.md](shared-ui-standards.md) | Tokens, layout, density, register toolbar, tabs, states as implemented in Licence. |
| [boe-modernization-progress.md](boe-modernization-progress.md) | Agents, workstream status, owner escalations, deferred backlog. |
