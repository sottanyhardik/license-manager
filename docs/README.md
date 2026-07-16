# Documentation Index

All project documentation lives under this `docs/` directory. Root is kept clean.

## Modernization (in-progress)

These are the deliverables from the May 2026 platform modernization effort. Read in order.

- [PHASE_1_REVIEW.md](./PHASE_1_REVIEW.md) — full architecture review, dependency map, risk register, performance audit, technical debt inventory.
- [PHASE_2_DESIGN.md](./PHASE_2_DESIGN.md) — target architecture, folder structure, signal redesign, service-layer template, DB safety analysis.
- [PHASE_3_MIGRATION_PLAN.md](./PHASE_3_MIGRATION_PLAN.md) — phased rollout, risk + rollback + validation per phase.

## Architecture references

- [architecture/BALANCE_CALCULATION_CONSOLIDATION.md](./architecture/BALANCE_CALCULATION_CONSOLIDATION.md) — single-source-of-truth design for license balance calculation.
- [architecture/MATERIALIZED_VIEWS_GUIDE.md](./architecture/MATERIALIZED_VIEWS_GUIDE.md) — materialized view + cache layer.
- [architecture/MODULARIZATION_MASTER_PLAN.md](./architecture/MODULARIZATION_MASTER_PLAN.md) — earlier modularization plan (predecessor to Phase 2 design).
- [architecture/NAVBAR_ROLE_MAPPING.md](./architecture/NAVBAR_ROLE_MAPPING.md) — RBAC-driven navigation.
- [architecture/RBAC_DOCUMENTATION.md](./architecture/RBAC_DOCUMENTATION.md) — 12-role permission system.
- [architecture/REDIS_CACHING_GUIDE.md](./architecture/REDIS_CACHING_GUIDE.md) — caching strategy.
- [architecture/CODE_SPLITTING_GUIDE.md](./architecture/CODE_SPLITTING_GUIDE.md) — frontend bundle layout.

## Developer guides

- [guides/API_PAGINATION_GUIDE.md](./guides/API_PAGINATION_GUIDE.md)
- [guides/COMMISSION_ACCOUNTING_GUIDE.md](./guides/COMMISSION_ACCOUNTING_GUIDE.md)
- [guides/FILTER_BACKENDS_GUIDE.md](./guides/FILTER_BACKENDS_GUIDE.md) + [implementation](./guides/FILTER_BACKENDS_IMPLEMENTATION.md)
- [guides/FRONTEND_DEBOUNCING_GUIDE.md](./guides/FRONTEND_DEBOUNCING_GUIDE.md)
- [guides/MANAGEMENT_COMMANDS.md](./guides/MANAGEMENT_COMMANDS.md)
- [guides/PDF_VIEWER_IMPLEMENTATION.md](./guides/PDF_VIEWER_IMPLEMENTATION.md)
- [guides/RATE_LIMITING_GUIDE.md](./guides/RATE_LIMITING_GUIDE.md) + [implementation](./guides/RATE_LIMITING_IMPLEMENTATION.md)
- [guides/SCRIPTS_README.md](./guides/SCRIPTS_README.md) — `backend/scripts/` tools.
- [guides/TESTING_GUIDE.md](./guides/TESTING_GUIDE.md) + [extra notes](./guides/README_TESTING.md)
- [guides/UI_UPGRADE_GUIDE.md](./guides/UI_UPGRADE_GUIDE.md)
- [guides/VALIDATION_IMPLEMENTATION.md](./guides/VALIDATION_IMPLEMENTATION.md)

## Operations

- [operations/RBAC_SETUP_INSTRUCTIONS.md](./operations/RBAC_SETUP_INSTRUCTIONS.md) — initial RBAC setup.
- [operations/TRACTOR_SERVER_165.232.185.220.md](./operations/TRACTOR_SERVER_165.232.185.220.md) — current tractor server.
- [operations/TRACTOR_SERVER_SETUP.md](./operations/TRACTOR_SERVER_SETUP.md) — original tractor setup notes (kept for historical IP `178.128.58.219`).
- [operations/PURCHASE_STATUS_FK_MIGRATION.md](./operations/PURCHASE_STATUS_FK_MIGRATION.md) — purchase status FK migration playbook.

## Frontend-internal docs

Live under `frontend/` (see `frontend/REFACTORING_GUIDE.md` etc.). Not duplicated here.

## Cleanup notes (May 2026)

The following stale one-shot implementation notes were removed during the modernization Phase 0 cleanup. Listed for historical traceability — `git log --diff-filter=D --summary -- '*.md'` recovers them if needed:

ADD_ORDERING_TO_MODELS, BUGFIX_THROTTLING, CRITICAL_UX_FIXES_COMPLETED, FIX_HTTPS_REDIRECT_BROWSER, FIX_TOKEN_BLACKLIST, FRONTEND_COMPONENTS_SUMMARY, IMPLEMENTATION_SUMMARY, PERMISSIONS_APPLIED, PURCHASE_STATUS_COMPLETE, PURCHASE_STATUS_COMPLETION_SUMMARY, PURCHASE_STATUS_FINAL_STATUS, QUICK_ROLE_TEST, SERVER_165.232.185.220_FIXED, SERVER_165.232.185.220_STATUS, UX_FIXES_VERIFICATION_CHECKLIST, VERIFICATION_REPORT, PDF_VIEWER_FIX, debug_401.
