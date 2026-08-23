# Script Inventory And Consolidation

This directory is the canonical home for repository-level standalone scripts.
Run paths below from the repository root unless a script says otherwise.

## Directory Layout

- `database/`: database backup, restore, sync, and integrity checks.
- `deployment/`: production deployment, SSL setup, deployment verification, and index deployment.
- `development/`: local development process runners.
- `diagnostics/`: operational checks and media sync tooling.
- `imports/`: DGFT/SION/rate/license-copy import and push jobs.
- `maintenance/`: master-data audit, merge, and legacy sync jobs.
- `mds/`: Master-Data Service migration and onboarding orchestration.
- `migration/`: local database/schema migration helpers.
- `testing/`: repository test runners.
- `utilities/`: reserved for future cross-cutting helpers.

## Consolidation Report

- Total tracked shell scripts before: 37.
- Total shell scripts after: 36.
- Shell scripts centralized under `scripts/`: 33.
- Duplicate scripts removed: 1 (`backend/sync-media.sh`, identical to root `sync-media.sh`).
- Scripts moved: 27.
- Scripts merged: 1 duplicate media-sync launcher removed by consolidation.
- Scripts renamed: no basenames were changed; paths changed by category.
- Shared modules created: none in this pass; existing `scripts/mds/_lib.sh` remains the shared MDS shell library.
- Estimated maintenance reduction: one duplicate script removed, zero root/backend shell launcher sprawl, and all repository-level shell entry points now have one discoverable tree.

## Moved Scripts

- `apply-master-merge.sh` -> `scripts/maintenance/apply-master-merge.sh`
- `audit-and-diff-masters.sh` -> `scripts/maintenance/audit-and-diff-masters.sh`
- `audit-and-merge-masters.sh` -> `scripts/maintenance/audit-and-merge-masters.sh`
- `audit-db-integrity.sh` -> `scripts/database/audit-db-integrity.sh`
- `auto-deploy.sh` -> `scripts/deployment/auto-deploy.sh`
- `db-tools.sh` -> `scripts/database/db-tools.sh`
- `deploy-indexes.sh` -> `scripts/deployment/deploy-indexes.sh`
- `deploy-license-manager.sh` -> `scripts/deployment/deploy-license-manager.sh`
- `fetch-all-sion-from-dgft.sh` -> `scripts/imports/fetch-all-sion-from-dgft.sh`
- `fetch-and-push-rates.sh` -> `scripts/imports/fetch-and-push-rates.sh`
- `fetch-and-push-sion-norms.sh` -> `scripts/imports/fetch-and-push-sion-norms.sh`
- `run-deploy.sh` -> `scripts/deployment/run-deploy.sh`
- `run-dev.sh` -> `scripts/development/run-dev.sh`
- `run-parse-license-copies.sh` -> `scripts/imports/run-parse-license-copies.sh`
- `run-tests.sh` -> `scripts/testing/run-tests.sh`
- `server-health.sh` -> `scripts/diagnostics/server-health.sh`
- `setup-labdhi-server.sh` -> `scripts/deployment/setup-labdhi-server.sh`
- `setup-ssl-labdhi.sh` -> `scripts/deployment/setup-ssl-labdhi.sh`
- `setup-ssl-tractor.sh` -> `scripts/deployment/setup-ssl-tractor.sh`
- `start-server.sh` -> `scripts/development/start-server.sh`
- `sync-masters.sh` -> `scripts/maintenance/sync-masters.sh`
- `sync-media.sh` -> `scripts/diagnostics/sync-media.sh`
- `verify-deployment.sh` -> `scripts/deployment/verify-deployment.sh`
- `backend/run-celery-dev.sh` -> `scripts/development/run-celery-dev.sh`
- `backend/run_sync.sh` -> `scripts/development/run_sync.sh`
- `backend/setup/migrate_old_db.sh` -> `scripts/migration/migrate_old_db.sh`
- `backend/setup/update_db_from_server.sh` -> `scripts/migration/update_db_from_server.sh`
- `backend/setup/upgrade-all-packages.sh` -> `scripts/migration/upgrade-all-packages.sh`

## Deleted As Duplicate

- `backend/sync-media.sh`: identical to the former root `sync-media.sh`; replaced by `scripts/diagnostics/sync-media.sh`.

## Intentionally Not Moved

- `.claude/index/hook_postedit.sh` and `.claude/index/hook_session.sh`: tool integration hooks; moving them would break the owning tool's lookup path.
- `master-data-service/deploy/deploy-mds.sh`: service-local deployment script documented to run from the MDS checkout; its path is part of the service deployment contract.
- Django management commands under `*/management/commands/`: framework-discovered commands; moving them would break `python manage.py <command>`.
- Django migrations under `*/migrations/`: framework-managed migration history; moving them would corrupt migration loading.
- Application modules under `backend/apps/**`, `frontend/src/**`, `mds-client/**`, and `master-data-service/**`: importable product code, not standalone repository scripts.
- `mds-client/runtests.py`: package-local test runner; kept with the package so it can be run from the package checkout.
- `frontend/package.json` scripts: npm entry points remain in `package.json` because npm discovers them there.

## Remaining Consolidation Opportunities

- The master-data maintenance scripts (`maintenance/`) still duplicate some SSH/logging patterns with `mds/_lib.sh`; they are legacy scripts retained for rollback and should only be merged after the MDS cutover is complete.
- The import scripts (`imports/`) share remote-execution patterns but perform different DGFT/rate/SION workflows. They can become subcommands of one importer after their external API behavior is covered by tests or fixtures.
- Django management commands already provide the right CLI boundary for database-affecting operations; shell wrappers should stay thin and eventually delegate to management commands.
