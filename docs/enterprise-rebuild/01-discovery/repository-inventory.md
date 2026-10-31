# Repository inventory - preliminary evidence register

## Confirmed baseline

| Item | Evidence | Status |
|---|---|---|
| Branch | `develop` | CONFIRMED from prior local baseline |
| Commit | `d2cb2446ba01e0e23e6ef3570f6449bdd001cf65` | CONFIRMED from prior local baseline |
| Backend stack | Django / Django REST Framework applications including accounts, core, license, allotment, BOE, trade, reconciliation and tasks | CONFIRMED from prior audit |
| Frontend stack | React/Vite/TypeScript | CONFIRMED from prior audit |
| Background capability | tasks application; exact broker/schedule deployment remains unverified | PARTIALLY_CONFIRMED |
| Production version | unknown | NOT_ASSESSED |

## Audit coverage rules

This register is not a claim that every repository file has been understood. The required source index `.Codex/index/` is absent, so exact file/symbol/caller coverage must remain `not inspected` until the index is rebuilt or an approved replacement inventory is captured.

## Discovery work remaining

1. Record tracked-file count and classify every path as production, test, configuration, generated, documentation or operational.
2. Reconcile Django app configuration, URL registration, admin, signals, management commands and Celery registration.
3. Reconcile React router, navigation, dynamic imports and role-protected/deep-link routes.
4. Inventory dependency manifests, lockfiles, containers, CI, deployment scripts, environment references and integration clients.
5. Capture exact framework versions from manifests in the baseline evidence.

