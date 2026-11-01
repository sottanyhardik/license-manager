# Legacy documentation disposition register

No legacy document is deleted, archived, moved, rewritten or treated as
authoritative V1 behavior by this audit. This register is a preservation and
traceability control, not a cleanup authorization.

## Category-to-V1 disposition

The exact-path register currently has **nine** classifications (not ten): the
previous grouping of “audit/discovery” and the common root category accounts
for the apparent tenth bucket in earlier high-level descriptions. One
representative was read from every classification to validate the category's
meaning. The table names the V1 destination where the information belongs; it
does **not** claim that all 645 documents have had their content transferred.

| Exact-register classification | Count | Representative reviewed | What was verified from the representative | V1 destination / preservation treatment | Review status |
| --- | ---: | --- | --- | --- | --- |
| Active predecessor evidence | 40 | `docs/enterprise-rebuild/00-programme/decision-log.md` | Contains proposed/required programme decisions, including company ownership, restriction policy, accounting scope and cutover. | [Decisions required](00-executive-overview/decisions-required.md), [decision log](09-traceability/decision-log.md), [migration plan](06-data-and-migrations/migration-plan.md). Retain as provenance; do not promote historical proposals to approved decisions. | Category sampled; individual transfer **not complete**. |
| Architecture evidence | 28 | `docs/architecture/ADR-001-master-data-service.md` | Contains an MDS/mirror architectural proposal, cross-DB-FK analysis and operational topology assumptions. | [Architecture overview](05-target-architecture/architecture-overview.md), [background processing](05-target-architecture/background-processing.md), [integration inventory](01-discovery/integration-inventory.md). Retain; reconcile its stated decisions against current code before adoption. | Category sampled; individual transfer **not complete**. |
| Assessment evidence | 15 | `docs/assessment/ACCOUNTING_SCOPE_AND_GAP_ANALYSIS.md` | Distinguishes commercial trade evidence from unproven GL/bank capability. | [Scope and non-goals](00-executive-overview/scope-and-non-goals.md), [functional requirements](02-product-requirements/functional-requirements.md), D5 in [decisions required](00-executive-overview/decisions-required.md). Retain as a scope input. | Category sampled; individual transfer **not complete**. |
| Audit/discovery evidence | 25 | `docs/audit/README.md` | Describes the prior audit state, generated knowledge graph and safe recheck workflow. | [Repository inventory](01-discovery/repository-inventory.md), [execution log](execution-log.md), [completion audit](09-traceability/completion-audit.md). Retain; a prior audit state is not current proof. | Category sampled; individual transfer **not complete**. |
| Documentation retained | 44 | `docs/01-project-overview.md` | Describes the product, roles, topology and legacy capability assumptions. | [Product vision](00-executive-overview/product-vision.md), [domain model](04-domain-and-business-rules/domain-model.md), [user roles](02-product-requirements/user-roles-and-personas.md). Retain as historical narrative; source/test evidence governs contradictions. | Category sampled; individual transfer **not complete**. |
| Module forensic evidence | 73 | `docs/modules/.variants/FORENSIC_AUDIT_MODULE2_PLANNING.md` | Provides endpoint, transaction and planning/allocation flow claims useful for locating evidence. | [Backend critical workflow map](09-traceability/backend-critical-workflow-map.md), [balance/allocation contracts](09-traceability/balance-allocation-function-contracts.md), [state machines](04-domain-and-business-rules/state-machines.md). Retain; confirm each claim against current code/tests before use. | Category sampled; individual transfer **not complete**. |
| Operational evidence | 7 | `docs/operations/PURCHASE_STATUS_FK_MIGRATION.md` | Is a historical migration guide with serializer/query caller impact. | [Migration plan](06-data-and-migrations/migration-plan.md), [rollback and recovery](06-data-and-migrations/rollback-and-recovery.md), [deployment readiness](07-quality-and-operations/deployment-readiness.md). Retain for history; do not execute old migration steps. | Category sampled; individual transfer **not complete**. |
| Root-level historical/evidence artifact | 405 | `.claude/agents/README.md` | Is repository tooling/agent guidance, not a product-behavior source. This class also contains agent notes, graphs, memory and one-off records. | Keep tooling under its current path. Only product/operational claims discovered during individual review transfer to the matching V1 document; agent instructions do not need a product-document replacement. | Category sampled; 405 individual paths **not reconciled**. |
| UI history | 8 | `docs/ui-modernization/BACKLOG.md` | Records historical UI debt and deferred tasks, including accessibility and shared-component concerns. | [Current-state UI audit](03-ui-ux/current-state-audit.md), [design system](03-ui-ux/design-system.md), [route-by-route redesign](03-ui-ux/route-by-route-redesign.md). Retain until each item is revalidated against current UI source or runtime evidence. | Category sampled; individual transfer **not complete**. |

## Measurable preservation and transfer state

| Measure | Result | Meaning |
| --- | ---: | --- |
| Exact legacy Markdown paths preserved | 645 / 645 | Every registered path remains `Retain`; no deletion or archival action has been executed. |
| Classifications present in the exact register | 9 / 9 | Every observed classification has a representative review and a V1 destination above. |
| Individually content-reconciled legacy documents | 0 / 645 | The exact register's `information_transferred` field remains `Not yet individually reconciled`; category review cannot be substituted for individual transfer. |
| Exact-path deletion proposals | 0 | A cleanup proposal is out of scope until individual information transfer and owner approval are complete. |

## Historical-content cautions

The reviewed predecessor and module documents contain proposals, historical
line references and operational instructions. They may disagree with current
code, tests or owner policy. V1 documentation therefore uses them as
provenance only and labels an assertion as verified only after current source,
test, runtime or owner evidence is recorded. In particular, the predecessor's
company, accounting and restriction decisions remain open D1, D5 and D3
respectively; they were not silently adopted.

No legacy documentation is deleted in this audit. A post-coverage cleanup proposal must name exact paths, transferred information, retention horizon and approval owner.

The [exact-path legacy register](legacy-documentation-register.tsv) inventories all **645 tracked Markdown artifacts** outside `docs/v1/`; its 646th line is the header. Every item is currently `Retain` with `No deletion proposed`. The register provides the required preservation denominator while individual content-transfer review proceeds; no generic category statement is used as authorization to delete a file.
