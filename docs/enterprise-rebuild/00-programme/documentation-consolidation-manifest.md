# Documentation inventory, consolidation manifest and cleanup record

**Baseline:** repository root `license-manager`; branch `develop`; commit `d2cb2446ba01e0e23e6ef3570f6449bdd001cf65`; 860 tracked documentation candidates and 98 untracked documentation candidates were counted on 31 October 2026. Working tree contains untracked `docs/assessment/`, `docs/enterprise-rebuild/`, `output/`, and `tmp/`; these are protected from deletion or relocation by this cleanup.

## Inventory and comparison by evidence set

| Paths / count | Purpose and unique content | Status | Canonical destination / decision | Rationale |
|---|---|---|---|---|
| `docs/01-*` through `docs/10-*` (10 core docs) | Earlier general application overview, architecture, API, database, business rules, user flow, security, integrations and rebuild specification. | PARTIALLY_CURRENT | Keep as historical/source evidence; consolidate current conclusions in this pack. | Broad baseline and code references remain useful, but do not reflect the new database-first decision system. |
| `docs/assessment/` (15 untracked reports) | 2026 management assessment: confirmed/static evidence, risk register, Option A/B gap analysis and limitations. | CURRENT EVIDENCE | Keep untouched; cite from canonical documents. | User/other-tool untracked work; contains direct evidence and classifications. |
| `docs/audit/` (22 reports plus audit data) | Phase-specific auth, authorization, licence, master data, BOE, reports, document and dashboard audits. | PARTIALLY_CURRENT | Keep as evidence; no bulk merge/delete. | Large detailed material has unique route/module provenance not yet revalidated. |
| `docs/architecture/` (28 documents) | Balance contracts, calculation ownership, ledger design, migration strategies, ADRs, RBAC and caching. | PARTIALLY_CURRENT | Keep as technical source; canonical rules are summarized in `01-database`, `02-business-rules`, `04-target-architecture`. | Includes important verified source paths and historic decisions; conflicts must be resolved through decision log. |
| `docs/discovery/` (6 documents) | Module map, dependency graph, critical findings and integrity rules. | PARTIALLY_CURRENT | Keep as source evidence. | Useful system map; dates and live/deployed status require revalidation. |
| `docs/modules/` (74 visible plus `.variants/`) | Module audits, baselines, implementation/verification reports and variants. | MIXED/HISTORICAL | Retain pending per-file provenance review; do not use as active requirements. | High unique-detail risk; variants/reports cannot be bulk-deleted safely. |
| `docs/frontend-migration/` (3 inventories) and `docs/ui-modernization/` (8 docs) | Route/API callsite and UI modernization evidence. | PARTIALLY_CURRENT | Keep as source evidence for current-system/target frontend work. | Exact inventories may be valuable but need source-index refresh. |
| `docs/guides/` (14 docs), `docs/operations/` (7 docs) | Implementation/runbook guidance, deployment and operational history. | MIXED/HISTORICAL | Keep; cite only after current-environment revalidation. | May contain deployment-sensitive/historical information. |
| Root phase/orchestrator/planning docs (28) | Earlier modernization plans, status, prompts and orchestration records. | SUPERSEDED AS ACTIVE PLAN | Keep untouched pending review; current plan is `07-implementation/implementation-roadmap.md`. | Tracked history/provenance and existing references must be preserved. |
| Existing `docs/enterprise-rebuild/01-discovery`, `02-functionality`, `03-business-rules`, `04-database`, `05-architecture`, `06-accounting`, `07-exceptions`, `10-testing`, `11-roadmap`, `12-delivery` (untracked) | Earlier generated preliminary rebuild work. | SUPERSEDED AS ACTIVE NAVIGATION | Retain temporarily; canonical navigation is this README and `00-07` structure. | Untracked artifacts may be user/other-agent work. Do not delete before provenance approval. |
| `output/assessment-2026-10-31/`, `output/enterprise-modernization-assessment/` and PDFs | Management deliverables, detailed reports and exported PDFs. | HISTORICAL DELIVERABLES | Keep untouched, cite as evidence where needed. | PDFs/exports may contain unique presentation or referenced provenance. |
| `tmp/` (untracked) | PDF generation intermediates/scripts. | UNKNOWN | No deletion in this pass. | Could be actively used by another tool/user. |

## Critical consolidation decisions implemented

1. **One active entry point:** `docs/enterprise-rebuild/README.md` now identifies authoritative documents.
2. **One active database-first baseline:** `01-database/database-audit.md` with inventories, deletion matrix, balance analysis and open questions.
3. **One active business-rule statement:** `02-business-rules/business-rules-catalogue.md`; source evidence remains linked instead of copied as competing formulas.
4. **One active target direction:** `04-target-architecture/target-architecture.md`, with dedicated accounting and company-isolation documents.
5. **One active migration/recovery direction:** `05-data-migration/`.
6. **One active release-quality statement:** `06-quality-and-testing/`.
7. **One active implementation sequence:** `07-implementation/implementation-roadmap.md`; prior roadmaps remain historical evidence.

## Cleanup actions in this pass

**Created/updated canonical documentation only. No existing file was archived, moved or deleted.** This is deliberate: all likely duplicates are tracked history or untracked work whose origin cannot be safely attributed in the current working tree.

## Required approval before archival/removal

1. Per-file content/provenance comparison for `docs/modules/` and hidden `docs/modules/.variants/`.
2. Reference search and owner confirmation for root phase/orchestrator records.
3. Explicit confirmation that untracked `docs/assessment/`, `output/`, and `tmp/` artifacts are no longer required by their creator.
4. Verification that a candidate is neither deployment/runbook evidence nor a referenced financial/migration decision.

