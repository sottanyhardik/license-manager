# Enterprise rebuild documentation system

This is the authoritative active documentation layer for the controlled restructure and parallel rebuild. It does not authorize code, schema, data, production or deployment changes.

## Start here

1. [Restructure blueprint](00-programme/restructure-blueprint.md) - current scope, evidence posture and governing architecture.
2. [Scope and non-negotiable requirements](00-programme/scope-and-non-negotiable-requirements.md).
3. [Audit status](audit-status.json) - unknown is never complete.
4. [Decision log](00-programme/decision-log.md) - implementation-blocking owner decisions.
5. [Documentation consolidation manifest](00-programme/documentation-consolidation-manifest.md) - provenance and cleanup decisions.

## Authoritative active documents

| Subject | Canonical location |
|---|---|
| Database/balances | [01-database](01-database/) |
| DFIA/SION/AU, restrictions and exceptions | [02-business-rules](02-business-rules/) |
| Current system evidence and code-cleanup policy | [03-current-system](03-current-system/) |
| Target architecture/security/accounting | [04-target-architecture](04-target-architecture/) and [architecture findings register](04-target-architecture/architecture-findings-register.md) |
| Data preservation, reconciliation and recovery | [05-data-migration](05-data-migration/) |
| Quality, reliability and release gates | [06-quality-and-testing](06-quality-and-testing/) |
| Assignable implementation work | [07-implementation](07-implementation/) |

## Evidence and historical material

Earlier documents under `docs/assessment/`, `docs/audit/`, `docs/architecture/`, `docs/discovery/`, `docs/modules/`, `docs/frontend-migration/`, `docs/ui-modernization/`, `docs/guides/`, `docs/operations/`, and `output/` are source evidence or historical work products unless this README declares them canonical. They must not be treated as competing current requirements.

The repository baseline evidenced `develop` at `d2cb2446ba01e0e23e6ef3570f6449bdd001cf65`. Production deployment/schema/data/recovery remain unverified. The repository-supported `.claude/index/` static inventory is rebuilt and reproducible; its documented static-analysis limits still apply.

