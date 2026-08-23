# License Manager Modularization Plan

**Status:** Active, audit-aligned plan
**Last reviewed:** Phase 5 Master Data audit

This document replaces the stale historical plan that referenced non-existent
`/backend/core/...`, `.jsx`, and `frontend/src/components/common/...` paths.
Use this plan as the current modularization map.

## Current Shared Modules

Backend shared modules live under `backend/apps/core/`:

| Area | Current module | Purpose |
|---|---|---|
| Serializer normalization | `backend/apps/core/serializers/mixins.py` | Form-data/nested payload normalization helpers |
| Serializer fields | `backend/apps/core/serializers/fields.py` | Safe/flexible date and model field helpers |
| Model serializers | `backend/apps/core/serializers/models.py` | Master-data serializers |
| Validation | `backend/apps/core/utils/validation.py` | Shared validation helpers |
| Date/decimal utilities | `backend/apps/core/utils/date_utils.py`, `decimal_utils.py` | Typed parsing, quantization, and formatting helpers |
| PDF helpers | `backend/apps/core/utils/pdf_helpers.py`, `pdf_utils.py` | ReportLab/PDF rendering support |
| Exporters | `backend/apps/core/exporters/` | Excel/PDF exporter base classes and builders |
| Master payload sync | `backend/apps/core/mds_payload.py`, `mds_write.py` | MDS-compatible payload/write helpers |
| Management command reuse | `backend/apps/core/management/commands/_item_linking.py` | Shared commodity item-linking command base |

Frontend shared modules currently live under existing TypeScript/React paths:

| Area | Current module | Purpose |
|---|---|---|
| UI primitives | `frontend/src/components/ui/`, `frontend/src/components/primitives/` | Shared buttons, cards, tabs, badges, surfaces |
| Master form helpers | `frontend/src/pages/masters/masterFormHelpers.ts` | Pure API-base/payload helpers for master forms |
| Master list config | `frontend/src/pages/masters/masterListConfig.ts` | Default list filters by entity |
| Master display formatting | `frontend/src/pages/masters/masterDisplayFormatters.ts` | Indian number/currency/date display helpers |
| Generic cards | `frontend/src/pages/masters/tables/GenericMasterCards.tsx` | Generic card list rendering |
| Extracted master tables | `AllotmentsTable.tsx`, `IncentiveLicensesTable.tsx` | Entity-specific master list slices |
| Trade form helpers | `frontend/src/pages/tradeFormHelpers.ts` | Pure TradeForm payload helpers |

## Completed Modularization Work

- Authentication and Authorization phases are frozen and tracked in
  `docs/audit/phase-01-authentication-report.md` and
  `docs/audit/phase-02-authorization-report.md`.
- Users and Roles & Permissions phases are frozen in the Phase 3/4 reports.
- MDS and `mds-client` packages are audited for Phase 5 and should not be
  reopened unless dependency analysis marks them `REQUIRES_RECHECK`.
- Backend `backend/apps/core` Phase 5 subsections are complete through tests.
- Frontend master form/list decomposition has extracted pure helpers, smoke
  coverage, generic cards, table slices, parse panels, and display formatting.
- Master-data shell scripts now share maintenance/MDS helper libraries.

## Remaining Refactoring Principles

1. Prefer existing shared modules before adding a new abstraction.
2. Keep historical migrations self-contained; do not import mutable runtime
   helpers into old migration files.
3. Split large files only when cohesion improves and tests cover the behavior.
4. For frontend master pages, keep behavior in pure helpers first, then extract
   UI slices with smoke tests.
5. Preserve local SQL joins for hot reports; do not replace `select_related` or
   `prefetch_related` master reads with per-row network calls.
6. Require explicit operator confirmation for scripts that can write production
   data.

## Active Follow-Up Queue

These are architecture tasks for later phases, not Phase 5 blockers:

| Priority | Task | Target phase |
|---:|---|---|
| 1 | Type master DTOs used by `NestedFieldArray`, parse panels, and table rows | Frontend Pages |
| 2 | Continue decomposing `NestedFieldArray.tsx` into typed field renderers after DTOs stabilize | Frontend Pages |
| 3 | Move remaining report-specific duplicate number formatting into shared utilities when each report phase is active | Reports |
| 4 | Evaluate whether `scripts/maintenance/sync-masters.sh` should adopt `_master_sync_lib.sh` after cron quiet-mode behavior is covered by tests | Scripts |
| 5 | Remove legacy maintenance password fallback after operators confirm env/SSH-key rollout | Security hardening |

## Verification Gates

Every modularization batch must run the relevant subset of:

- Python: Ruff, `py_compile`, focused pytest.
- Frontend: Vitest, ESLint, TypeScript.
- Shell: `bash -n`, offline `--help` paths where available.
- Security/dependency: `npm audit --audit-level=high`; Python dependency audit
  remains blocked in this environment until `pip_audit` is installed.

Track completed files, verification history, and remaining queue state in
`docs/audit/audit-database.json`, `docs/audit/dashboard.md`, and
`docs/audit/work-queue.md`.
