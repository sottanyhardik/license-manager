# Phase 05 - Master Data Audit Report

Phase 5 starts from frozen Authentication, Authorization, Users, and Roles & Permissions phases. This report is appended batch-by-batch as Master Data files are completed. The first batch audits the standalone `master-data-service` package.

## Verification History

| Check | Result |
|---|---|
| `../.venv/bin/python -m pytest masters/tests -q` from `master-data-service` | 25 passed |
| `../.venv/bin/ruff check masters/views.py masters/signals.py masters/management/commands/load_masters.py masters/tests --select F401,F821,F811,E741,F841,S324` | Clean |
| `bash -n deploy/deploy-mds.sh` | Passed |
| `../.venv/bin/python -m py_compile manage.py mds/asgi.py mds/wsgi.py mds/urls.py mds/settings.py masters/admin.py masters/apps.py masters/models.py masters/pagination.py masters/serializers.py masters/signals.py masters/urls.py masters/views.py masters/management/commands/load_masters.py` | Passed |

## Batch 1 - Master Data Service

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `master-data-service/masters/models.py` | 362 | 362 | 18 | 20 | None | None | None | Existing `uuid`, `Decimal`, Django validators retained | Existing `MASTER_REGISTRY` confirmed as single source | None | None | Registry-driven model/view/admin generation retained | Validators and natural-key constraints reviewed | MDS tests, py_compile | No model removal recommended; all registry models are API/sync referenced | COMPLETED |
| `master-data-service/masters/views.py` | 155 | 155 | 8 | 2 | None | None | None | Replaced `hashlib.md5` ETag fingerprint with `hashlib.sha256` | None | None | None | No runtime query expansion; metadata aggregation remains O(1) aggregate | Removed weak-hash finding potential for generated ETags | MDS tests, Ruff, py_compile | Bulk upsert remains row-by-row for validation and signal behavior | COMPLETED |
| `master-data-service/masters/serializers.py` | 56 | 56 | 2 | 1 | None | None | None | None | Existing dynamic natural-key FK field generation retained | None | Existing FK serializer tests reviewed | Avoids per-master serializer boilerplate | Natural-key FK write/read contract reviewed | MDS tests, py_compile | Dynamic serializers should get focused tests when new FK masters are added | COMPLETED |
| `master-data-service/masters/pagination.py` | 21 | 21 | 0 | 2 | None | None | None | None | None | None | None | Cursor pagination retained for stable delta reads | No security issue | MDS tests, py_compile | None | COMPLETED |
| `master-data-service/masters/signals.py` | 31 | 31 | 3 | 0 | None | None | None | None | None | None | None | No query broadening | Added explicit `dispatch_uid`s to prevent duplicate receiver registration | MDS tests, Ruff, py_compile | Change feed still records every save, including bulk hydration updates | COMPLETED |
| `master-data-service/masters/apps.py` | 10 | 10 | 1 | 1 | None | None | None | None | None | None | None | No change | Signal registration path reviewed | py_compile | None | COMPLETED |
| `master-data-service/masters/admin.py` | 17 | 17 | 0 | 1 | None | None | None | None | Existing registry-driven admin registration retained | None | None | No change | Already guards `AlreadyRegistered` | py_compile | Generic admin remains intentionally simple | COMPLETED |
| `master-data-service/masters/urls.py` | 10 | 10 | 0 | 0 | None | None | None | None | Existing registry-driven router retained | None | None | No change | No issue | py_compile | None | COMPLETED |
| `master-data-service/masters/management/commands/load_masters.py` | 444 | 444 | 22 | 1 | None | None | None | Added explicit UTF-8 file loading | Existing topological loader retained | None | Existing load command tests reviewed | Per-model transactions retained | Error paths for unreadable/invalid JSON reviewed | MDS tests, Ruff, py_compile | Loader has repeated upsert patterns; deeper consolidation deferred until broader backend core import/export pass to avoid changing hydration semantics | COMPLETED |
| `master-data-service/masters/migrations/0001_initial.py` | 303 | 303 | 0 | 1 | None | None | None | None | None | None | None | No change | Schema constraints and validators reviewed against models | MDS tests | Migration should remain immutable except corrective follow-up migrations | COMPLETED |
| `master-data-service/masters/tests/test_api.py` | 183 | 183 | 19 | 2 | None | None | None | None | None | None | Existing coverage reviewed | No change | Covers auth scopes, upsert, delete feed, ETag, meta, delta | MDS tests | Does not assert exact ETag algorithm, which is desirable | COMPLETED |
| `master-data-service/masters/tests/test_fk_serialization.py` | 52 | 52 | 3 | 0 | None | None | None | None | None | None | Existing coverage reviewed | No change | Locks natural-key FK contract | MDS tests | None | COMPLETED |
| `master-data-service/masters/tests/test_load_masters.py` | 204 | 204 | 7 | 0 | None | None | None | None | None | None | Existing coverage reviewed | No change | Covers orphan handling and idempotency | MDS tests | Does not cover every master field variant; acceptable for current contract scope | COMPLETED |
| `master-data-service/mds/settings.py` | 194 | 194 | 2 | 0 | None | None | None | None | Existing `_env_bool` and `_parse_tokens` retained | None | Existing auth/config tests reviewed | No change | Production SSL/cookie/HSTS gating reviewed | py_compile, MDS tests | Default dev secret remains documented as dev-only; production env template requires replacement | COMPLETED |
| `master-data-service/mds/urls.py` | 15 | 15 | 1 | 0 | None | None | None | None | None | None | None | No change | Health probe reviewed | py_compile | None | COMPLETED |
| `master-data-service/mds/asgi.py` | 6 | 6 | 0 | 0 | None | None | None | None | None | None | None | No change | No issue | py_compile | None | COMPLETED |
| `master-data-service/mds/wsgi.py` | 6 | 6 | 0 | 0 | None | None | None | None | None | None | None | No change | No issue | py_compile | None | COMPLETED |
| `master-data-service/manage.py` | 20 | 20 | 1 | 0 | None | None | None | None | None | None | None | No change | No issue | py_compile | None | COMPLETED |
| `master-data-service/pytest.ini` | 7 | 7 | 0 | 0 | None | None | None | None | None | None | None | No change | No issue | MDS tests | None | COMPLETED |
| `master-data-service/README.md` | 62 | 62 | 0 | 0 | Removed stale adding-master instructions | Removed manual serializer/view/router/admin checklist duplication | None | None | Documented registry-driven extension path | None | None | No runtime impact | Reduces operational drift | Documentation review | Keep in sync with ADR-001 and registry changes | COMPLETED |
| `master-data-service/deploy/deploy-mds.sh` | 155 | 155 | 4 shell functions | 0 | None | None | None | Existing Bash built-ins retained | None | None | None | Dry-run default retained | Secrets are not printed; health check and rollback path reviewed | bash -n | ShellCheck not available/run in this environment | COMPLETED |
| `master-data-service/deploy/gunicorn.conf.py` | 66 | 66 | 0 | 0 | None | None | None | Existing `multiprocessing`/`os` retained | None | None | None | Worker cap and max-request recycling reviewed | Access log format avoids authorization headers | py_compile | Log directory creation is deployment-owned | COMPLETED |
| `master-data-service/deploy/nginx-mds.conf` | 81 | 81 | 0 | 0 | None | None | None | None | None | None | None | Static alias and timeouts reviewed | TLS redirect and security headers reviewed | Configuration review | Domain/path placeholders must be replaced per host | COMPLETED |
| `master-data-service/deploy/mds.service` | 68 | 68 | 0 | 0 | None | None | None | None | None | None | None | Restart policy and runtime dir reviewed | Systemd hardening reviewed | Configuration review | Paths/user/group are host-specific placeholders | COMPLETED |
| `master-data-service/.env.example` | 17 | 17 | 0 | 0 | None | None | None | None | None | None | None | No runtime impact | Dev template reviewed | Configuration review | Example tokens/passwords must never be reused outside local/dev | COMPLETED |
| `master-data-service/.env.production.example` | 56 | 56 | 0 | 0 | None | None | None | None | None | None | None | No runtime impact | Production secret/token guidance reviewed | Configuration review | Template intentionally contains placeholders | COMPLETED |
| `master-data-service/.gitignore` | 9 | 9 | 0 | 0 | None | None | None | None | None | None | None | No runtime impact | Ignores env, media, static, coverage/cache artifacts | Configuration review | None | COMPLETED |

## Batch 1 Issues Fixed

- Replaced MD5 ETag fingerprinting in the MDS API with SHA-256.
- Added explicit `dispatch_uid`s to MDS change-feed signal receivers.
- Made `load_masters` read JSON exports with explicit UTF-8 encoding.
- Updated MDS README extension guidance to match `MASTER_REGISTRY`-driven serializers, viewsets, routes, signals, and admin registration.
- Added `.service` files to the audit source inventory so systemd units are tracked.

## Phase 5 Remaining Scope

- Backend `backend/apps/core` master models, serializers, views, filters, migrations, management commands, utilities, templates, and tests.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 2 - MDS Client

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `mds-client/mds_client/keys.py` | 134 | 134 | 9 | 0 | None | None | None | Existing `uuid5`, `datetime`, and `Decimal` handling retained | Existing deterministic signature helpers retained | None | Existing key tests reviewed | No change | Deterministic UID recipe reviewed as migration-safe | mds-client tests, Ruff, py_compile | Recipe is intentionally frozen; changes would require migration planning | COMPLETED |
| `mds-client/mds_client/model_map.py` | 139 | 139 | 0 | 0 | None | None | None | None | Existing default 17-master map retained | None | Existing mapping tests reviewed | No change | Natural-key and MDS label map reviewed | mds-client tests, py_compile | Must stay synchronized with MDS `MASTER_REGISTRY` | COMPLETED |
| `mds-client/mds_client/sync.py` | 405 | 405 | 14 | 1 | Removed unused `timezone` import | None | None | None | Existing sync/write/delete helpers retained | None | Existing sync tests reviewed | Topological ordering and client reuse retained | Write/delete outage handling reviewed | mds-client tests, Ruff, py_compile | Required-FK missing-parent behavior intentionally fails loud and rolls back; no silent wrong link | COMPLETED |
| `mds-client/mds_client/client.py` | 281 | 281 | 18 | 5 | None | None | None | Existing `requests`/`urllib3.Retry` usage retained | Existing single request choke point retained | None | Existing client tests reviewed | Session pooling and GET-only retries retained | Authorization header handling and timeout mapping reviewed | mds-client tests | POST retries intentionally avoided | COMPLETED |
| `mds-client/mds_client/models.py` | 43 | 43 | 2 | 1 | None | None | None | None | Existing `MDSSyncState` model retained | None | Existing sync tests reviewed | No change | Cursor/etag state reviewed | mds-client tests, py_compile | None | COMPLETED |
| `mds-client/mds_client/tasks.py` | 48 | 48 | 3 | 0 | None | None | None | None | Optional Celery shim retained | None | None | No change | No required Celery dependency; import degrades safely | py_compile | None | COMPLETED |
| `mds-client/mds_client/management/commands/mds_sync.py` | 41 | 41 | 2 | 1 | None | None | None | None | Existing command wrapper retained | None | Existing sync tests indirectly cover core behavior | No change | Unreachable MDS exits non-zero via `CommandError` | py_compile | Direct management command test could be added later | COMPLETED |
| `mds-client/mds_client/__init__.py` | 29 | 29 | 0 | 0 | None | None | None | None | Public exports reviewed | None | None | No change | No issue | py_compile | `default_app_config` is legacy-compatible and harmless; removal deferred | COMPLETED |
| `mds-client/mds_client/admin.py` | 10 | 10 | 0 | 1 | None | None | None | None | None | None | None | No change | Sync-state admin is read-oriented | py_compile | None | COMPLETED |
| `mds-client/mds_client/apps.py` | 9 | 9 | 0 | 1 | None | None | None | None | None | None | None | No change | No issue | py_compile | None | COMPLETED |
| `mds-client/mds_client/settings.py` | 109 | 109 | 7 | 0 | None | None | None | None | Existing config helpers retained | None | Existing config tests reviewed | No change | Missing settings fail loudly | mds-client tests, py_compile | Previously completed in auth/config pass; no code change in Phase 5 | COMPLETED |
| `mds-client/mds_client/migrations/0001_initial.py` | 28 | 28 | 0 | 1 | None | None | None | None | None | None | None | No change | Sync-state schema reviewed | mds-client tests | Migration should remain immutable except corrective follow-up migrations | COMPLETED |
| `mds-client/runtests.py` | 33 | 33 | 1 | 0 | None | None | None | Existing Django test runner retained | None | None | None | No change | No issue | py_compile | None | COMPLETED |
| `mds-client/pyproject.toml` | 38 | 38 | 0 | 0 | None | None | None | None | Packaging metadata reviewed | None | None | No runtime impact | Optional Celery dependency remains opt-in | Configuration review | Package version is still `0.1.0` | COMPLETED |
| `mds-client/pytest.ini` | 4 | 4 | 0 | 0 | None | None | None | None | None | None | None | No runtime impact | No issue | mds-client tests | None | COMPLETED |
| `mds-client/.gitignore` | 25 | 25 | 0 | 0 | None | None | None | None | None | None | None | No runtime impact | Ignores build/cache/env artifacts | Configuration review | None | COMPLETED |
| `mds-client/README.md` | 149 | 149 | 0 | 0 | None | None | None | None | Documentation matches client architecture | None | None | No runtime impact | Degradation contract documented | Documentation review | ADR phase wording is historical and retained | COMPLETED |
| `mds-client/tests/test_sync.py` | 281 | 281 | 21 | 1 | None | None | None | None | Existing fake client/session utilities used | None | Existing coverage reviewed | No change | Covers outage, delete order, 304 delete handling, FK resolution | mds-client tests | Management command wrapper remains indirectly covered | COMPLETED |
| `mds-client/tests/test_client.py` | 206 | 206 | 26 | 0 | None | None | None | None | Existing support utilities retained | None | Existing coverage reviewed | No change | Transport failure/error handling covered | mds-client tests | Previously completed; no code change in Phase 5 | COMPLETED |
| `mds-client/tests/test_model_map.py` | 51 | 51 | 5 | 0 | None | None | None | None | Existing mapping checks retained | None | Existing coverage reviewed | No change | Validates required model mapping entries | mds-client tests | Previously completed; no code change in Phase 5 | COMPLETED |
| `mds-client/tests/support.py` | 55 | 55 | 5 | 1 | None | None | None | None | Existing fake HTTP session retained | None | Existing coverage reviewed | No change | No issue | mds-client tests | Previously completed; no code change in Phase 5 | COMPLETED |
| `mds-client/tests/settings.py` | 64 | 64 | 0 | 0 | None | None | None | None | Test settings reviewed | None | None | No change | Test-only secret is not production config | py_compile, mds-client tests | None | COMPLETED |
| `mds-client/tests/conftest.py` | 10 | 10 | 1 | 0 | None | None | None | None | None | None | None | No change | No issue | py_compile, mds-client tests | None | COMPLETED |
| `mds-client/tests/mirror_app/models.py` | 47 | 47 | 0 | 4 | None | None | None | None | Mirror fixtures retained | None | None | No change | No issue | py_compile, mds-client tests | None | COMPLETED |
| `mds-client/tests/mirror_app/apps.py` | 7 | 7 | 0 | 1 | None | None | None | None | None | None | None | No change | No issue | py_compile, mds-client tests | None | COMPLETED |
| `mds-client/mds_client/management/__init__.py` | 0 | 0 | 0 | 0 | None | None | None | None | Package marker reviewed | None | None | No change | No issue | py_compile | None | COMPLETED |
| `mds-client/mds_client/management/commands/__init__.py` | 0 | 0 | 0 | 0 | None | None | None | None | Package marker reviewed | None | None | No change | No issue | py_compile | None | COMPLETED |
| `mds-client/mds_client/migrations/__init__.py` | 0 | 0 | 0 | 0 | None | None | None | None | Package marker reviewed | None | None | No change | No issue | py_compile | None | COMPLETED |
| `mds-client/tests/__init__.py` | 0 | 0 | 0 | 0 | None | None | None | None | Package marker reviewed | None | None | No change | No issue | mds-client tests | None | COMPLETED |
| `mds-client/tests/mirror_app/__init__.py` | 0 | 0 | 0 | 0 | None | None | None | None | Package marker reviewed | None | None | No change | No issue | mds-client tests | None | COMPLETED |

## Batch 2 Issues Fixed

- Removed an unused `django.utils.timezone` import from `mds-client/mds_client/sync.py`.

## Phase 5 Remaining Scope After Batch 2

- Backend `backend/apps/core` master models, serializers, views, filters, migrations, management commands, utilities, templates, and tests.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 3 - Backend Core Scaffolding

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/__init__.py` | 1 | 1 | 0 | 0 | None | None | None | None | Package marker/comment retained | None | None | No change | No issue | Ruff, py_compile | None | COMPLETED |
| `backend/apps/core/apps.py` | 14 | 14 | 1 | 1 | None | None | None | None | Existing cache signal registration retained | None | None | No change | No immediate issue | Ruff, py_compile | `ready()` currently catches broad `ImportError`; deeper cache-signal audit deferred to backend core cache batch | COMPLETED |
| `backend/apps/core/constants.py` | 112 | 112 | 0 | 0 | None | None | None | Existing `Decimal` constants retained | Project-wide choices retained | None | None | No change | No issue | Ruff, py_compile | Some constants are legacy and will be cross-checked during model audit | COMPLETED |
| `backend/apps/core/serializers/__init__.py` | 81 | 81 | 0 | 0 | None | None | None | None | Serializer barrel exports retained | None | None | No change | No issue | Ruff, py_compile | Export list must be revisited after serializer model audit | COMPLETED |
| `backend/apps/core/management/__init__.py` | 0 | 0 | 0 | 0 | None | None | None | None | Package marker reviewed | None | None | No change | No issue | Package marker | None | COMPLETED |
| `backend/apps/core/management/commands/__init__.py` | 0 | 0 | 0 | 0 | None | None | None | None | Package marker reviewed | None | None | No change | No issue | Package marker | None | COMPLETED |
| `backend/apps/core/migrations/__init__.py` | 0 | 0 | 0 | 0 | None | None | None | None | Package marker reviewed | None | None | No change | No issue | Package marker | None | COMPLETED |
| `backend/apps/core/scripts/__init__.py` | 0 | 0 | 0 | 0 | None | None | None | None | Package marker reviewed | None | None | No change | No issue | Package marker | None | COMPLETED |
| `backend/apps/core/templatetags/__init__.py` | 0 | 0 | 0 | 0 | None | None | None | None | Package marker reviewed | None | None | No change | No issue | Package marker | None | COMPLETED |

## Phase 5 Remaining Scope After Batch 3

- Backend `backend/apps/core` master models, serializers, views, filters, cache utilities/signals, migrations, management commands, utilities, templates, and tests.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 4 - Backend Core Models

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/models.py` | 812 | 812 | 52 | 44 | Removed unused module-level `alpha` validator and no-op `ExchangeRateModel.save()` override | None | None | Existing Django model fields, validators, indexes, `uuid5`, `threading.local`, and `Decimal` constants retained | Existing deterministic MDS UID fallback retained | None | Existing model/MDS tests reviewed; no new tests required for no-op cleanup | Removed one redundant method dispatch from exchange-rate saves; existing queryset indexes retained | Master model references, natural keys, audit thread-local hooks, upload paths, MDS synthetic UID fallback, and activity logging fields reviewed | Ruff, py_compile, makemigrations dry-run, targeted pytest; `pip_audit` blocked because unavailable | `HSCodeModel.search_fields` retained for dynamic metadata compatibility; broad `SyntheticUidMixin.save()` exception retained to preserve save behavior; `ItemHeadModel` remains deprecated but live through migrations/sync | COMPLETED |

### Batch 4 Issues Fixed

- Removed the unused `alpha` `RegexValidator` constant from `backend/apps/core/models.py` after confirming it had no live references outside its own definition.
- Removed `ExchangeRateModel.save()` because it only called `super().save()` and duplicated Django's inherited model behavior without enforcing additional validation.
- Confirmed model cleanup generated no Django migration changes.

### Phase 5 Remaining Scope After Batch 4

- Backend `backend/apps/core` Managers and QuerySets confirmation, then serializers, services, ViewSets, views, permissions, validators, signals, cache, middleware, utilities, management commands, scripts, migrations, and tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 5 - Backend Core Managers, QuerySets, and Serializers

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core` Managers subsection | 0 | 0 | 0 | 0 | None | None | None | Existing Django default model managers retained | None | None | None | No custom manager overhead present | No issue | Repository search for `Manager`, `objects =`, `as_manager` in `backend/apps/core` | No dedicated manager files or custom managers exist | COMPLETED |
| `backend/apps/core` QuerySets subsection | 0 | 0 | 0 | 0 | None | None | None | Existing Django default querysets retained | None | None | None | No custom queryset overhead present | No issue | Repository search for `QuerySet` in `backend/apps/core` | Query optimization continues in ViewSets/Views batches where querysets are built | COMPLETED |
| `backend/apps/core/serializers/models.py` | 313 | 313 | 6 | 20 | Removed redundant local `ExchangeRateModel` import from `get_is_active()` | None | None | Existing DRF `ModelSerializer`/`SerializerMethodField` usage retained | Existing `_sync_nested` integration retained | None | Existing core API and MDS write tests reviewed; no new tests required | Avoided one repeated import per `ExchangeRateSerializer.get_is_active()` call | Serializer field exposure, nested SION writes, active exchange-rate labeling, FK display labels, and deprecated ItemHead compatibility reviewed | Ruff, py_compile, targeted pytest | `SionNormClassNestedSerializer.to_internal_value()` has permissive JSON parsing semantics distinct from shared mixins and is intentionally retained for compatibility | COMPLETED |
| `backend/apps/core/serializers/mixins.py` | 366 | 366 | 4 | 5 | None | None | None | Replaced deprecated `typing.List`/`typing.Dict`/`typing.Optional` annotations with built-in generics and `Callable` | Existing exported mixins retained | None | Existing core API tests reviewed | No runtime change | FormData parsing, nested object ID extraction, empty-string normalization, and nested validation exception paths reviewed | Ruff, py_compile, targeted pytest | Mixins are exported but not broadly adopted yet; broader migration deferred until owning serializer phases to avoid behavior drift | COMPLETED |

### Batch 5 Issues Fixed

- Confirmed `backend/apps/core` has no dedicated custom Manager or QuerySet implementations; models use Django defaults.
- Removed a redundant local import from `ExchangeRateSerializer.get_is_active()`.
- Modernized serializer mixin annotations to current Python collection generics and `collections.abc.Callable`.

### Phase 5 Remaining Scope After Batch 5

- Backend `backend/apps/core` Services, ViewSets, Views, Permissions, Validators, Signals, Cache, Middleware, Utilities, Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 6 - Backend Core Services

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/mds_payload.py` | 236 | 236 | 7 | 0 | None | None | None | Replaced deprecated `typing.Dict`/`typing.Tuple` annotations with built-in generics | Existing shared row builder retained as single source for online writes and offline export | None | Existing export and write-cutover tests reviewed | FK parent natural-key access avoids id portability issues; concrete-field iteration retained | Server-managed fields, audit-user FKs, media path serialization, natural-key mapping, keyless uid payloads, and fallback client map reviewed | Ruff, py_compile, targeted pytest | Inline fallback MDS map must remain synchronized with `mds-client` mapping | COMPLETED |
| `backend/apps/core/mds_write.py` | 187 | 187 | 6 | 1 | None | None | None | Existing lazy imports and DRF exception types retained | Existing MDS write/delete service retained | None | Existing cutover tests reviewed | Local transaction rollback and post-commit mirror refresh behavior retained | MDS outage/rejection paths, 503/400 mapping, lazy client import, and local partial-write prevention reviewed | Ruff, py_compile, targeted pytest | Mirror refresh failure is intentionally logged and deferred to periodic sync | COMPLETED |

### Batch 6 Issues Fixed

- Modernized `mds_payload.py` type annotations to built-in collection generics.
- Confirmed MDS write service rollback, validation translation, delete ordering, and id-free payload contracts through existing regression tests.

### Phase 5 Remaining Scope After Batch 6

- Backend `backend/apps/core` ViewSets, Views, Permissions, Validators, Signals, Cache, Middleware, Utilities, Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 7 - Backend Core ViewSets

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/views/views.py` | 604 | 604 | 2 | 0 | Removed unused top-level `to_kebab()` and `build_endpoint_candidates()` helpers | Removed duplicate endpoint-candidate builder that was superseded by `enhance_config_with_fk()`'s nested `build_candidates_for_rel()` | None | Existing Django/DRF viewset factory usage retained | Existing `enhance_config_with_fk()` retained as the active FK metadata builder | None | Existing route/API tests reviewed; no new tests required for dead-helper removal | Route registration and lookup overrides retained; no query broadening | Master route registrations, FK endpoint metadata, filter config, nested SION field metadata, scheme/notification code lookup behavior, and MDS-enabled write paths reviewed | Ruff, py_compile, targeted pytest | `master_view.py` remains previously completed and was not reopened; unregistered deprecated child ViewSet variables remain for compatibility until a deeper public-export decision | COMPLETED |

### Batch 7 Issues Fixed

- Removed two unused endpoint helper functions from `backend/apps/core/views/views.py`.
- Confirmed registered master routes and URL routing remain intact via targeted API and routing tests.

### Phase 5 Remaining Scope After Batch 7

- Backend `backend/apps/core` Views, Permissions, Validators, Signals, Cache, Middleware, Utilities, Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 8 - Backend Core Views

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/views/__init__.py` | 32 | 32 | 0 | 0 | None | None | None | None | Export barrel aligned with concrete master ViewSet definitions | None | Existing route tests reviewed | No runtime query impact | Public import surface reviewed; no auth behavior changed | Ruff, py_compile, targeted pytest | `activity_log`, health/media/status/throttle views were already completed and not reopened | COMPLETED |

### Batch 8 Issues Fixed

- Expanded `backend/apps/core/views/__init__.py` to export all concrete core master ViewSets defined in `views.py`, not just the older subset.

### Phase 5 Remaining Scope After Batch 8

- Backend `backend/apps/core` Permissions, Validators, Signals, Cache, Middleware, Utilities, Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 9 - Backend Core Permissions

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core` Permissions subsection | 0 | 0 | 0 | 0 | None | None | None | Existing DRF permission classes retained | None | None | Existing Phase 2 authorization tests retained | No runtime change | Confirmed no dedicated `backend/apps/core/*permission*.py`; master data permissions remain in completed `master_view.py`, `mds_status.py`, `activity_log.py`, and `accounts/permissions.py` | Audit database status check and permission reference search | Permission logic is frozen from Phase 2 unless dependency graph marks it for recheck | COMPLETED |

### Batch 9 Issues Fixed

- No code changes. Confirmed no remaining pending backend/core permission files in Phase 5 scope.

### Phase 5 Remaining Scope After Batch 9

- Backend `backend/apps/core` Validators, Signals, Cache, Middleware, Utilities, Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 10 - Backend Core Validators

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/utils/validation.py` | 674 | 674 | 17 | 0 | None in this batch | None in this batch | None | Existing Django `ValidationError`, `Decimal`, `datetime`, `Path`, and regex validation retained | Existing shared validation utility retained | None | Existing validation tests deferred to Tests subsection by audit order | No runtime change | IEC/GST/PAN/file-extension/date/choice/required-field validation previously completed and not reopened | Audit database status check; validator reference search | `backend/apps/core/tests/test_validation.py` remains for the Tests subsection | COMPLETED |

### Batch 10 Issues Fixed

- No code changes. Confirmed validator implementation is already completed and only validator tests remain pending for the later Tests subsection.

### Phase 5 Remaining Scope After Batch 10

- Backend `backend/apps/core` Signals, Cache, Middleware, Utilities, Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 11 - Backend Core Signals

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/signals_materialized_views.py` | 152 | 152 | 7 | 1 | None | Added stable `dispatch_uid` values to materialized-view receivers to prevent duplicate registration on repeated imports | None | Existing Django `transaction.on_commit` and Celery task scheduling retained | None | None | Existing MDS cutover regression reviewed | Lazy logging avoids eager f-string formatting on disabled debug logs; refresh scheduling remains post-commit and debounced | Exception logging now preserves traceback with `exc_info=True`; `auto_refresh_context` now restores the prior refresh state instead of always disabling | Ruff, py_compile, targeted pytest | Automatic materialized refresh remains disabled by default for performance; no dedicated materialized-view task test exists yet | COMPLETED |
| `backend/apps/core/cache_signals.py` | 429 | 429 | 13 | 1 | Removed unused `invalidate_model_caches` import | Consolidated cache receiver metadata into `CACHE_INVALIDATION_RECEIVERS`; added stable `dispatch_uid` values to all cache invalidation receivers | None | Existing Django `post_save`/`post_delete`/`m2m_changed` signal APIs retained | Created a shared receiver registry for deterministic disable/reconnect behavior | None | `backend/apps/core/tests/test_cache_signals.py` | Lazy logging avoids eager f-string formatting on disabled debug logs; static literal cache patterns avoid unnecessary f-string construction | Fixed broken `disable_cache_invalidation` path that previously relied on nonexistent `receiver_func.sender`; M2M connection failure logging now retains traceback | Ruff, py_compile, targeted pytest | Context manager does not suppress the M2M invalidation receiver, matching previous behavior; broader cache utility audit is next subsection | COMPLETED |
| `backend/apps/core/tests/test_cache_signals.py` | 39 | 39 | 1 | 0 | None | None | None | Existing pytest/Django signal testing retained | None | None | Added regression coverage for cache invalidation receiver disconnect/reconnect behavior | Confirms reconnect does not duplicate the tested Company receiver path | Verifies bulk-import/testing disable context suppresses cache invalidation while active | Ruff, py_compile, targeted pytest | Covers representative master-data signal path; license/BOE/allotment signal behavior remains covered indirectly until broader domain phases | COMPLETED |

### Batch 11 Issues Fixed

- Added stable `dispatch_uid` values for cache and materialized-view signal receivers to avoid duplicate receiver registration on repeated imports.
- Fixed `disable_cache_invalidation()` by replacing the invalid `receiver_func.sender` lookup with an explicit receiver registry used for both disconnect and reconnect.
- Converted signal logging to lazy formatting and preserved exception tracebacks for failed materialized refresh scheduling and M2M signal connection failures.
- Added focused regression coverage for the cache-invalidation disable/reconnect context manager.

### Phase 5 Remaining Scope After Batch 11

- Backend `backend/apps/core` Cache, Middleware, Utilities, Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 12 - Backend Core Cache

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/cache_utils.py` | 432 | 432 | 10 | 1 | Removed unused `Any`/`Union` imports | Centralized cache-key MD5 hashing in `_cache_key_hash()` | None | Replaced legacy `typing.Callable`/`Optional` usage with `collections.abc.Callable` and `str | None`/`int | None` | `_cache_key_hash()` documents and isolates non-security cache hashing | None | `backend/apps/core/tests/test_cache_utils.py` | Lazy logging avoids eager string interpolation; `cache_disabled.__enter__()` now returns the context manager | Marked cache-key MD5 as `usedforsecurity=False`; cache stats failures now retain traceback through `logger.exception()` | Ruff, py_compile, targeted pytest | `cache_view()` still returns raw cached bytes for successful `JsonResponse` branches; no live usages found, so deeper behavior change deferred until a consumer adopts it | COMPLETED |
| `backend/apps/core/cached_views.py` | 146 | 146 | 3 | 5 | Removed unused `Optional`, `method_decorator`, and `cache_page` imports | None | None | Existing DRF `viewsets`, `Response`, and `PageNumberPagination` retained | None | None | Existing cache utility tests cover shared key/decorator behavior | Lazy logging avoids eager formatting; pagination import moved to module top | Retrieve cache keys now use `generate_view_cache_key()`, making detail caches user/query scoped like list caches and reducing cross-user cache-leak risk if the mixin is used for permissioned data | Ruff, py_compile, targeted pytest | Cached view mixins are currently documented infrastructure with no active runtime consumers found in backend imports | COMPLETED |
| `backend/apps/core/tests/test_cache_utils.py` | 68 | 68 | 4 | 0 | None | None | None | Existing Django `RequestFactory`, cache backend, and DRF `Response` retained | None | None | Added focused tests for stable cache keys, `cache_query`, `cache_view` GET caching, and non-GET bypass | Confirms cache decorator avoids repeat execution on cached GET responses | Confirms user/query-scoped view cache path is exercised | Ruff, py_compile, targeted pytest | Does not cover `JsonResponse` branch because it has no current consumer | COMPLETED |

### Batch 12 Issues Fixed

- Removed unused cache-module imports and modernized cache utility type annotations.
- Isolated cache-key MD5 hashing with `usedforsecurity=False`, resolving the static security finding while preserving existing short cache-key behavior.
- Converted cache utility and cached-view logging to lazy formatting.
- Changed cached retrieve mixin keys to reuse the existing user/query-aware key generator, preventing unsafe cross-user detail cache reuse if these mixins are adopted by permissioned endpoints.
- Added focused cache utility regression tests.

### Phase 5 Remaining Scope After Batch 12

- Backend `backend/apps/core` Middleware, Utilities, Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 13 - Backend Core Middleware

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/middleware.py` | 175 | 175 | 10 | 2 | None in this batch | None in this batch | None | Existing Django middleware contract and thread-based activity logging retained | Existing login/logout explicit logging helpers retained | None | Existing authentication query-param tests reviewed | No runtime change; no dependency impact from Cache/Signals edits | Token-auth CSRF bypass remains restricted to bearer tokens and approved GET/HEAD download token URLs; session CSRF behavior retained | Ruff, py_compile, targeted pytest | File was already marked COMPLETE in audit database; not reopened for refactor because dependency analysis did not mark it `REQUIRES_RECHECK` | COMPLETED |

### Batch 13 Issues Fixed

- No code changes. Confirmed `backend/apps/core/middleware.py` remained complete and unaffected by the current Phase 5 Cache/Signals changes.
- Re-verified middleware import safety, syntax, and authentication query-token behavior.

### Phase 5 Remaining Scope After Batch 13

- Backend `backend/apps/core` Utilities, Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.
- Master data maintenance scripts and master-data architecture/operations docs.

## Batch 14 - Backend Core Utilities: Date, Decimal, Exceptions

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/utils/__init__.py` | 43 | 43 | 0 | 0 | None | None | None | Existing package exports retained | None | None | Existing date/decimal/validation import coverage reviewed | No runtime change | No issue | Ruff, py_compile, targeted pytest | Exports remain intentionally small; broader utility adoption deferred to owning phases | COMPLETED |
| `backend/apps/core/utils/date_utils.py` | 450 | 450 | 18 | 0 | None | None | None | Replaced legacy `typing.Optional`/`Union`/`Tuple` with built-in union types; replaced manual month-length list with `calendar.monthrange()` | Added local `DateInput` and `DateRangeValue` aliases for readable signatures | None | Added tests for future/past `is_date_within_days()` windows and `add_months()` end-of-month behavior | Standard-library month calculation removes manual leap-year branch; no query/runtime coupling | Fixed `is_date_within_days()` positive-window calculation, which previously compared future dates against a past threshold | Ruff, py_compile, targeted pytest | Timezone-aware datetime normalization remains date-only by design to preserve existing utility semantics | COMPLETED |
| `backend/apps/core/utils/decimal_utils.py` | 268 | 268 | 8 | 1 | Removed unused `ROUND_DOWN` import and eliminated `math` import | None | None | Replaced legacy `typing.Union`/`Callable` with built-in unions and `collections.abc.Callable` | Added `DecimalInput` and `DecimalRoundInput` aliases | None | Added precision regression for `round_decimal_down()` | `round_decimal_down()` now uses Decimal `quantize(..., ROUND_FLOOR)` instead of float conversion, preserving large-number precision | Decimal conversion remains string-based to avoid float precision surprises | Ruff, py_compile, targeted pytest | `format_decimal()` still coerces invalid input to `0.00`, matching existing behavior | COMPLETED |
| `backend/apps/core/utils/exceptions.py` | 32 | 32 | 2 | 0 | None | None | None | Existing `logging` and safe integer parsing retained | None | None | Existing call-site coverage reviewed | No runtime change | API error helper still logs full traceback server-side and returns caller-supplied safe message | Ruff, py_compile, targeted pytest | `_safe_int` is also duplicated locally in some license report views; consolidation deferred to License phase ownership | COMPLETED |
| `backend/apps/core/tests/test_date_utils.py` | 483 | 483 | 0 | 15 | None | None | None | Existing unittest-style test classes retained | None | None | Added 5 focused test methods for date-window and month-addition edge cases | Regression coverage for standard-library month handling | Regression coverage for corrected future-date window behavior | Ruff, py_compile, targeted pytest | Remaining untested helpers such as `format_date_range()` and `get_date_range_from_filter()` retained for later expansion if consumers change | COMPLETED |
| `backend/apps/core/tests/test_decimal_utils.py` | 282 | 282 | 0 | 9 | None | None | None | Existing unittest-style test classes retained | None | None | Added 1 precision regression for large Decimal round-down | Confirms large Decimal values avoid float precision loss | No issue | Ruff, py_compile, targeted pytest | None for audited decimal helpers | COMPLETED |

### Batch 14 Issues Fixed

- Corrected `is_date_within_days()` for positive future windows.
- Replaced manual leap-year/month-length logic in `add_months()` with `calendar.monthrange()`.
- Removed float conversion from `round_decimal_down()` and used Decimal quantization with `ROUND_FLOOR`.
- Modernized date/decimal utility annotations and removed unused imports.
- Added focused regression tests for the corrected date and decimal utility behavior.

### Phase 5 Remaining Scope After Batch 14

- Continue Backend `backend/apps/core` Utilities for PDF helpers, filters/filtersets, pagination, throttling, exporters, materialized-view helpers, tasks, templates, and remaining support utilities.
- Then Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.

## Batch 15 - Backend Core Utilities: Filtering, Pagination, Throttling, Nested Sync Helper

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/filters.py` | 564 | 564 | 2 | 7 | Removed unused `django_filters.rest_framework` and legacy typing imports | None | None | Replaced `typing.List` with `list[str]` | None | None | Existing API/MDS tests reviewed | No runtime change | Filter validation continues to ignore invalid numeric values rather than erroring, preserving API compatibility | Ruff, py_compile, targeted pytest | Custom filter backends are shared by License/BOE/Allotment; deeper semantic changes deferred to owning phases | COMPLETED |
| `backend/apps/core/filtersets.py` | 404 | 404 | 4 | 9 | Removed unused `django_filters` and `models` imports | Consolidated repeated comma-separated value parsing, integer-ID parsing, ID filtering, and recent-day filtering into local helpers | None | Moved `date`/`timedelta` imports to module level | `_csv_values()`, `_csv_ints()`, `_filter_csv_ids()`, `_filter_recent_days()` | None | Existing API/MDS tests reviewed | Avoids repeated local imports and repeated parsing implementations | No authorization behavior changed; invalid ID fragments remain ignored as before | Ruff, py_compile, targeted pytest | Some report-specific filtersets remain domain-owned and will be revisited in their later phases | COMPLETED |
| `backend/apps/core/pagination.py` | 243 | 243 | 5 | 7 | None | None | None | Import ordering normalized; existing `OrderedDict` response shape retained | None | None | Existing API tests reviewed | No runtime change | No issue | Ruff, py_compile, targeted pytest | `StandardPagination` duplication with `views/master_view.py` remains intentionally frozen until that completed view is dependency-marked for recheck | COMPLETED |
| `backend/apps/core/throttling.py` | 370 | 370 | 7 | 10 | None | Consolidated repeated throttle ident/cache-key construction and rate-limit warning logging into private helpers | None | Existing DRF throttle base classes and Django cache retained | `_request_ident()`, `_request_label()`, `_cache_key()`, `_warn_rate_limited()` | None | Existing auth/API tests reviewed | Reduces repeated cache-key construction per throttle class | Throttle status error logging now preserves traceback via `logger.exception()`; rate-limit logs use lazy formatting | Ruff, py_compile, targeted pytest | No new throttle behavior tests added in this batch; existing login/query-token regression covers configured login throttle import path | COMPLETED |
| `backend/apps/core/helpers.py` | 107 | 107 | 1 | 0 | Removed unused `rest_framework.serializers` import and stale placeholder comments | None | None | Existing Django transaction handling retained | Existing `_sync_nested()` remains the shared nested-relation sync helper | None | Existing MDS write and API tests reviewed | No runtime change | Transactional nested sync behavior retained | Ruff, py_compile, targeted pytest | `_sync_nested()` remains private by name but is intentionally imported by core/trade serializers for compatibility | COMPLETED |

### Batch 15 Issues Fixed

- Removed unused imports in filtering/helper modules.
- Centralized repeated comma-separated ID parsing in `filtersets.py`.
- Consolidated repeated throttle cache-key and warning-log construction.
- Preserved existing pagination response shape and nested sync semantics.

### Phase 5 Remaining Scope After Batch 15

- Continue Backend `backend/apps/core` Utilities for PDF helpers, exporters, materialized-view helpers, tasks, templates, and remaining support utilities.
- Then Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.

## Batch 16 - Backend Core Utilities: PDF Helpers

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/utils/pdf_helpers.py` | 686 | 686 | 19 | 2 | Removed legacy typing imports no longer required by built-in generics | None | None | Replaced legacy `typing.Optional`/`List`/`Tuple`/`Union` annotations with built-in union and collection generics | Existing PDF helper surface retained for logo/signature/stamp loading, styles, amount words, and invoice generation | None | Existing BOE/license/allotment PDF/API regressions reviewed | PIL images now open through context managers, preventing leaked file handles during repeated PDF generation | Exception paths now preserve tracebacks through lazy logging; `num_to_words_indian()` no longer raises a second conversion exception when invalid input reaches its fallback | Ruff, py_compile, targeted pytest | `format_currency()` still coerces through `float()` for display compatibility; deeper currency formatting normalization deferred until owning PDF consumers are audited | COMPLETED |
| `backend/apps/core/utils/pdf_utils.py` | 436 | 436 | 15 | 1 | Removed unused `BytesIO`, `TA_RIGHT`, `canvas`, `pdfmetrics`, and `TTFont` imports | None | None | Existing ReportLab primitives retained; no dependency changes | Existing `BusinessPDFExporter` abstraction retained as shared report PDF utility | None | Existing BOE/license/allotment PDF/API regressions reviewed | Import cleanup reduces module import overhead and static-analysis noise; no PDF rendering behavior changed | No issue; response creation and table rendering behavior preserved | Ruff, py_compile, targeted pytest | The broader core exporter package remains pending in the Utilities subsection | COMPLETED |

### Batch 16 Issues Fixed

- Removed unused PDF utility imports and modernized PDF helper annotations.
- Converted image-dimension reads to `with PILImage.open(...)` context managers.
- Converted PDF helper logging to lazy formatting and traceback-preserving exception paths.
- Hardened `num_to_words_indian()` invalid-input fallback so its exception handler cannot re-raise while logging the original conversion failure.

### Phase 5 Remaining Scope After Batch 16

- Continue Backend `backend/apps/core` Utilities for exporters, materialized-view helpers, tasks, templates, and remaining support utilities.
- Then Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.

## Batch 17 - Backend Core Utilities: Exporter Package

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/exporters/__init__.py` | 21 | 21 | 0 | 0 | None | None | None | Existing package barrel retained | Public exporter import surface verified | None | Existing API/export regressions reviewed | No runtime change | No issue | Ruff, py_compile, exporter smoke, targeted pytest | No active domain consumers found; retained as shared infrastructure | COMPLETED |
| `backend/apps/core/exporters/base.py` | 95 | 95 | 6 | 2 | None | None | None | Existing `abc`, `enum`, and `BytesIO` usage retained | Existing abstract exporter contract retained | None | Existing API/export regressions reviewed | No runtime change | No issue | Ruff, py_compile, exporter smoke, targeted pytest | Abstract methods still use `pass`; behavior preserved | COMPLETED |
| `backend/apps/core/exporters/excel/__init__.py` | 13 | 13 | 0 | 0 | None | None | None | Existing package barrel retained | Excel exporter public import surface verified | None | Existing API/export regressions reviewed | No runtime change | No issue | Ruff, py_compile, exporter smoke, targeted pytest | No active domain consumers found; retained for future shared exports | COMPLETED |
| `backend/apps/core/exporters/excel/base_excel.py` | 235 | 235 | 14 | 2 | Removed legacy `typing.Optional` usage | None | None | Added postponed annotations and built-in union types for workbook/worksheet/config state | Existing openpyxl workbook exporter base retained | None | Existing API/export regressions reviewed | No runtime behavior change; import/type cleanup reduces static-analysis noise | No issue | Ruff, py_compile, exporter smoke, targeted pytest | `BaseExcelExporter.config` still intentionally shadows base dict config with `ExcelConfig` for compatibility | COMPLETED |
| `backend/apps/core/exporters/excel/workbook_builder.py` | 376 | 376 | 13 | 2 | Removed legacy `typing.List`/`Optional`/`Dict` imports | None | None | Added postponed annotations and built-in collection/union generics | Existing fluent Excel workbook builder retained | None | Existing API/export regressions reviewed | No runtime behavior change; annotations no longer require quoted self-type strings | No issue | Ruff, py_compile, exporter smoke, targeted pytest | Formatting style objects remain per-config defaults to preserve openpyxl behavior | COMPLETED |
| `backend/apps/core/exporters/pdf/__init__.py` | 16 | 16 | 0 | 0 | None | None | None | Existing package barrel retained | PDF exporter public import surface verified | None | Existing API/export regressions reviewed | No runtime change | No issue | Ruff, py_compile, exporter smoke, targeted pytest | No active domain consumers found; retained for future shared exports | COMPLETED |
| `backend/apps/core/exporters/pdf/base_pdf.py` | 211 | 211 | 14 | 2 | Removed legacy `typing.Optional`/`Tuple` usage | None | None | Added postponed annotations and built-in tuple/union types | Existing ReportLab PDF exporter base retained | None | Existing API/export regressions reviewed | No runtime behavior change | No issue | Ruff, py_compile, exporter smoke, targeted pytest | Orientation validation remains permissive and defaults non-landscape values to portrait, preserving prior behavior | COMPLETED |
| `backend/apps/core/exporters/pdf/styles.py` | 295 | 295 | 9 | 1 | None | None | None | Existing ReportLab style APIs retained | Existing style factory functions retained | None | Existing API/export regressions reviewed | No runtime change | No issue | Ruff, py_compile, exporter smoke, targeted pytest | Direct access to `TableStyle._cmds` retained for behavior compatibility | COMPLETED |
| `backend/apps/core/exporters/pdf/table_builder.py` | 315 | 315 | 12 | 2 | Removed legacy `typing.List`/`Optional`/`Dict` imports | Consolidated currency and quantity cell decimal formatting through `_format_decimal_cell()` | None | Added postponed annotations and built-in collection/union generics | `_format_decimal_cell()` | None | Existing API/export regressions reviewed | Reduces duplicated conversion/formatting path while preserving output | No issue | Ruff, py_compile, exporter smoke, targeted pytest | `calculate_column_widths()` still raises on zero total proportion as before | COMPLETED |

### Batch 17 Issues Fixed

- Modernized exporter package annotations without changing public imports or rendering behavior.
- Removed legacy typing imports from Excel/PDF exporter helpers.
- Consolidated duplicated decimal-cell formatting in `pdf/table_builder.py`.
- Verified exporter import barrels, Excel table creation, PDF table creation, decimal formatting, and column-width calculation through a focused smoke check.

### Phase 5 Remaining Scope After Batch 17

- Continue Backend `backend/apps/core` Utilities for materialized-view helpers, tasks, templates, template tags, and remaining support utilities.
- Then Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.

## Batch 18 - Backend Core Utilities: Materialized Views, Tasks, Template Tags

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/materialized_views.py` | 469 | 469 | 14 | 0 | Removed legacy typing imports | Consolidated repeated materialized-view name lists and related-view refresh loops | None | Replaced legacy `typing.List`/`Optional` with built-in generics and unions | `MATERIALIZED_VIEW_SQL`, `MATERIALIZED_VIEW_NAMES`, `RELATED_MATERIALIZED_VIEW_NAMES`, `_validate_materialized_view_name()`, `_refresh_related_views()` | None | `backend/apps/core/tests/test_materialized_views.py` | Valid stats query now uses `relname` and `pg_total_relation_size(relid)`, avoiding broken catalog lookups | Added allowlist validation before interpolating materialized-view identifiers into SQL refresh/freshness paths; exception logging now preserves tracebacks | Ruff, py_compile, focused pytest, adjacent regression pytest | Materialized-view SQL still reflects legacy balance formulas and remains intentionally deferred to License/Inventory phases for semantic review | COMPLETED |
| `backend/apps/core/tasks.py` | 27 | 27 | 1 | 0 | None | None | None | Existing Celery and Django `call_command` usage retained | Existing scheduled exchange-rate task retained | None | Existing API/core regressions reviewed | No runtime change | Exception path already traceback-preserving through `logger.exception()` | Ruff, py_compile, adjacent regression pytest | Direct command behavior is deferred to Management Commands subsection | COMPLETED |
| `backend/apps/core/tasks_materialized_views.py` | 90 | 90 | 5 | 0 | None | None | None | Existing Celery task wrappers retained | Existing materialized-view task surface retained | None | `backend/apps/core/tests/test_materialized_views.py` indirectly covers underlying allowlist/stats behavior | Lazy logging avoids eager f-string formatting in scheduled health logs | Task failure logs now preserve tracebacks through `logger.exception()` | Ruff, py_compile, focused pytest, adjacent regression pytest | Task scheduling cadence and Celery beat configuration remain outside this utility subsection | COMPLETED |
| `backend/apps/core/templatetags/core_tag.py` | 33 | 33 | 4 | 0 | Removed unnecessary `else` branch in `calculate_required_value()` | None | None | Existing Django template tag APIs retained | Existing template tag names retained for legacy templates | None | Existing API/core regressions reviewed | No runtime change | No issue | Ruff, py_compile, adjacent regression pytest | `relative_url()` still uses legacy query-string splitting to preserve template output compatibility | COMPLETED |
| `backend/apps/core/tests/test_materialized_views.py` | 86 | 86 | 8 | 2 | None | None | None | Existing pytest monkeypatching retained | Fake cursor/connection helpers for SQL construction regression coverage | None | Added 3 focused tests | Confirms stats query uses valid PostgreSQL catalog columns | Confirms unknown materialized-view names are rejected before any SQL executes | Ruff, py_compile, focused pytest, adjacent regression pytest | Tests avoid live PostgreSQL materialized views by design; live DB behavior remains command/integration territory | COMPLETED |

### Batch 18 Issues Fixed

- Added materialized-view identifier allowlisting before SQL interpolation in refresh/freshness paths.
- Fixed `get_materialized_view_stats()` to query valid `pg_stat_user_tables` columns (`relname`, `relid`) instead of nonexistent `matviewname`.
- Consolidated repeated related-view refresh loops and materialized-view name constants.
- Converted materialized-view and task logging to lazy, traceback-preserving logging.
- Added focused tests proving SQL allowlisting and stats-query construction.

### Phase 5 Remaining Scope After Batch 18

- Continue Backend `backend/apps/core` Utilities for templates and remaining support documentation such as `MDS_SYNC.md`.
- Then Management Commands, Scripts, Migrations, and Tests in the required order.
- Frontend master pages, tables, parse panels, modal helpers, API clients, and tests.

## Batch 19 - Backend Core Utilities: Legacy Templates and MDS Sync Doc

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/MDS_SYNC.md` | 100 | 100 | 0 | 0 | None | None | None | Existing Markdown retained | Existing MDS operations guide retained | None | Existing MDS/core regressions reviewed | No runtime impact | No secrets present; documents `MDS_TOKEN` only as environment variable name | Reference search, Django check, targeted pytest | ADR link points to architecture documentation outside this subsection | COMPLETED |
| `backend/apps/core/templates/base.html` | 369 | 369 | 0 | 0 | None | None | None | Existing Django template/static tags retained | Existing base layout retained for legacy backend-rendered pages | None | Existing route/core regressions reviewed | No runtime behavior change | Added `rel="noopener noreferrer"` to the external `target="_blank"` footer link | Django check, targeted pytest | Inline JavaScript still uses legacy global-event/global-variable patterns; behavior-preserving modernization deferred until legacy template owners are audited | COMPLETED |
| `backend/apps/core/templates/core/add.html` | 283 | 283 | 0 | 0 | None | None | None | Existing Django form/formset template tags retained | Existing generic add/edit form template retained | None | Existing route/core regressions reviewed | No runtime change | CSRF token present on multipart form | Django check, targeted pytest | Inline currency helpers remain legacy JavaScript; no safe behavior-neutral extraction made in this batch | COMPLETED |
| `backend/apps/core/templates/core/ledger.html` | 32 | 32 | 0 | 0 | None | None | None | Existing Django template tags retained | Existing ledger upload form retained | None | Existing route/core regressions reviewed | No runtime change | CSRF token present on upload form | Django check, targeted pytest | Upload handling itself remains covered by earlier authentication/upload batches | COMPLETED |
| `backend/apps/core/templates/core/list.html` | 145 | 145 | 0 | 0 | Removed one duplicated `django_select2.js` include | One duplicate frontend asset include removed | None | Existing django-tables2/querystring tags retained | Existing generic list/export template retained | None | Existing route/core regressions reviewed | Avoids loading the same Select2 integration script twice on legacy list pages | No issue | Django check, duplicate script search, targeted pytest | Add-link branching remains path-substring based to preserve existing legacy route behavior | COMPLETED |
| `backend/apps/core/templates/core/message.html` | 27 | 27 | 0 | 0 | None | None | None | Existing Django messages rendering retained | Existing message display template retained | None | Existing route/core regressions reviewed | No runtime change | Message output remains Django autoescaped | Django check, targeted pytest | No issue | COMPLETED |
| `backend/apps/core/templates/dashboard.html` | 68 | 68 | 0 | 0 | None | None | None | Existing static dashboard template retained | Legacy dashboard cards retained | None | Existing route/core regressions reviewed | No runtime change | No issue | Django check, targeted pytest | Empty dashboard card bodies appear intentionally placeholder legacy UI; no deletion without product confirmation | COMPLETED |
| `backend/apps/core/templates/pdf_base.html` | 58 | 58 | 0 | 0 | None | None | None | Existing xhtml2pdf template constructs retained | PDF base layout retained for report templates in other domains | None | Existing route/core regressions reviewed | No runtime change | No issue | Django check, targeted pytest | PDF consumers are domain-owned and remain for later License/BOE/Allotment phases | COMPLETED |
| `backend/apps/core/templates/sion/detail.html` | 106 | 106 | 0 | 0 | None | None | None | Existing Django table rendering retained | Existing SION detail legacy template retained | None | Existing route/core regressions reviewed | No runtime change | Autoescaped variable output retained | Django check, targeted pytest | SION semantics remain tied to master data models; no UI redesign in this batch | COMPLETED |
| `backend/apps/core/templates/upload.html` | 48 | 48 | 0 | 0 | None | None | None | Existing Django template tags retained | Existing transfer-letter upload/generate template retained | None | Existing route/core regressions reviewed | No runtime change | CSRF token present on upload form | Django check, targeted pytest | Linked `generate_tl` workflow belongs to document/upload phases | COMPLETED |
| `backend/apps/core/templates/widgets/multiwidget.html` | 3 | 3 | 0 | 0 | None | None | None | Existing widget include retained | Existing multiwidget renderer retained | None | Existing route/core regressions reviewed | No runtime change | Uses Django widget template inclusion, no raw unsafe output added | Django check, targeted pytest | No issue | COMPLETED |

### Batch 19 Issues Fixed

- Removed a duplicated `django_select2.js` include from the legacy core list template.
- Added `rel="noopener noreferrer"` to the external footer link opened with `target="_blank"`.
- Verified the MDS sync guide contains environment-variable names only, not secret values.

### Phase 5 Remaining Scope After Batch 19

- Backend `backend/apps/core` Utilities are complete for the active `REQUIRES_RECHECK` set.
- Continue to Backend `backend/apps/core` Management Commands in the required Phase 5 order.
- Then Scripts, Migrations, Tests, frontend master pages/tests, deployment configuration, and documentation.

## Batch 20 - Backend Core Management Commands: Audit/Import/Cache Commands

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/management/commands/audit_database_integrity.py` | 283 | 283 | 15 | 1 | None | None | None | Replaced deprecated naive UTC timestamp generation with `datetime.now(UTC)` while preserving trailing `Z`; added explicit UTF-8 snapshot read/write | Existing read-only integrity audit command retained | None | Existing core regressions reviewed | No query-shape change | Snapshot file I/O now uses explicit encoding; raw SQL table names remain quoted through `connection.ops.quote_name()` | Ruff, py_compile, command help, targeted pytest | Full checksum mode still scans whole tables by design and can be expensive on production-sized databases | COMPLETED |
| `backend/apps/core/management/commands/audit_masters.py` | 163 | 163 | 5 | 1 | Removed unused `seen_keys` tracking | None | None | Replaced raw `open()` output write with `Path.write_text(..., encoding="utf-8")` | Existing cross-server master snapshot command retained | None | Existing core regressions reviewed | Removes unused per-record set mutation | Output path writes now close deterministically with explicit encoding | Ruff, py_compile, command help, targeted pytest | Snapshot generation still serializes all configured master rows; acceptable for operational audit use | COMPLETED |
| `backend/apps/core/management/commands/auto_import_masters.py` | 312 | 312 | 4 | 2 | None | Moved model field lookup construction outside the per-record update branch | None | Replaced raw `open()` JSON/CSV operations with `Path.read_text()` and encoded `Path.open()` | Existing dry-run/apply import command retained | None | Existing core regressions reviewed | Avoids rebuilding `field_by_key` for every existing record update path | File reads/writes now use explicit UTF-8 encoding; dry-run transactional rollback behavior preserved | Ruff, py_compile, command help, targeted pytest | The command still monkey-patches `Command.handle` to implement dry-run rollback; behavior retained, deeper structural rewrite deferred until command-specific tests exist | COMPLETED |
| `backend/apps/core/management/commands/cache_stats.py` | 112 | 112 | 2 | 1 | None | None | None | Existing Django cache APIs retained | Existing cache stats/clear command retained | None | Existing core regressions reviewed | Uses Redis `scan_iter()` when available instead of blocking `KEYS *`, falling back for non-Redis clients | No issue; destructive `--clear` remains explicit command-line behavior | Ruff, py_compile, command help, targeted pytest | Listing all keys still materializes the key list to preserve total-count output | COMPLETED |

### Batch 20 Issues Fixed

- Removed unused duplicate-key tracking in `audit_masters.py`.
- Replaced raw `open()` calls with `Path` APIs and explicit UTF-8 encoding in the audited file-based commands.
- Moved `auto_import_masters.py` field lookup construction out of the per-record update loop.
- Replaced Redis `KEYS *` usage in `cache_stats --keys` with `scan_iter()` when the backend supports it.

### Phase 5 Remaining Scope After Batch 20

- Continue Backend `backend/apps/core` Management Commands from `check_db_structure.py` onward.
- Then Scripts, Migrations, Tests, frontend master pages/tests, deployment configuration, and documentation.

## Batch 21 - Backend Core Management Commands: Database Checks, Cleanup, Conversion Commands

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/management/commands/check_db_structure.py` | 248 | 248 | 5 | 1 | Removed unused legacy `typing` imports and unused `Model` import | None | None | Modernized annotations to built-in generics | Existing database structure inspection command retained | None | Existing command-help coverage reviewed | No query behavior changed | Read-only database inspection path retained | Ruff, py_compile, command help | The command still prints detailed model/table diagnostics directly for operator use | COMPLETED |
| `backend/apps/core/management/commands/check_master_quality.py` | 237 | 237 | 5 | 1 | Removed unused `sys` import | None | None | Replaced raw `open()` export write with `Path.write_text(..., encoding="utf-8")` | Existing master quality audit command retained | None | Existing `test_check_master_quality.py` regression suite reviewed | File output closes deterministically with explicit encoding | No issue; command is read-only except requested report output | Ruff, py_compile, command help, targeted pytest | Data-quality thresholds remain command-owned policy values | COMPLETED |
| `backend/apps/core/management/commands/clean_duplicate_rowdetails.py` | 83 | 83 | 1 | 1 | Avoided unused grouped-key variable | None | None | Existing Django aggregation APIs retained | Existing duplicate RowDetail cleanup command retained | None | Command help reviewed | No query shape change | Added `--dry-run` so duplicate cleanup can be inspected before destructive deletion | Ruff, py_compile, command help | Actual deletion path remains intentionally explicit when `--dry-run` is omitted | COMPLETED |
| `backend/apps/core/management/commands/clean_item_names.py` | 66 | 66 | 2 | 1 | None | None | None | Existing Django ORM APIs retained | Existing preview/update item-name cleanup command retained | None | Command help reviewed | Uses `select_related("group")` for preview/update output to avoid repeated group lookups | No issue; destructive update already requires command invocation | Ruff, py_compile, command help | Normalization rules remain fixed in-command to preserve current data-cleaning behavior | COMPLETED |
| `backend/apps/core/management/commands/clearcache.py` | 10 | 10 | 1 | 1 | None | None | None | Existing Django cache API retained | Existing cache clear command retained | None | Command help reviewed | No runtime change | Added explicit command help and styled success output; destructive operation remains explicit command invocation | Ruff, py_compile, command help | No issue | COMPLETED |
| `backend/apps/core/management/commands/convert_docx_to_pdf.py` | 84 | 84 | 2 | 1 | None | None | None | Replaced `os` path handling with `pathlib.Path`; handles uppercase `.DOCX` suffixes | Existing DOCX-to-PDF conversion command retained | None | Command help reviewed | Path operations are simpler and avoid repeated string path joins | Temporary input cleanup now uses `Path.unlink()` through the same safe exception path | Ruff, py_compile, command help | External LibreOffice availability remains an environment prerequisite | COMPLETED |
| `backend/apps/core/management/commands/convert_license_table.py` | 43 | 43 | 2 | 1 | None | None | None | Replaced `os.path.exists()` and raw `open()` with `Path.exists()` and encoded reads | Existing license-table conversion command retained | None | Existing command-help coverage reviewed | No runtime change | Explicit UTF-8 reads avoid platform-default encoding drift | Ruff, py_compile | Conversion parsing remains intentionally narrow to the legacy license table input format | COMPLETED |

### Batch 21 Issues Fixed

- Removed unused imports in database-quality and structure commands.
- Replaced raw file handling with `Path` APIs and explicit UTF-8 encoding in the audited conversion/report commands.
- Added `--dry-run` to the duplicate `RowDetail` cleanup command, reducing operational risk without changing the explicit deletion path.
- Improved item cleanup preview/update query efficiency with `select_related("group")`.
- Added command metadata and styled output for the cache clear command.

### Phase 5 Remaining Scope After Batch 21

- Continue Backend `backend/apps/core` Management Commands from `diff_masters.py` onward.
- Then Scripts, Migrations, Tests, frontend master pages/tests, deployment configuration, and documentation.

## Batch 22 - Backend Core Management Commands: Snapshot Diff, MDS Export, Legacy Fetch, Exchange Rates

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/management/commands/diff_masters.py` | 118 | 118 | 2 | 1 | None | Replaced repeated per-key scans of each other snapshot with an indexed table/key lookup | None | Replaced raw `open()` calls with `Path.read_text()` and encoded CSV output | Existing merge-plan CSV contract retained | None | Existing MDS export regression reviewed | Avoids repeatedly walking all other records for every key while preserving duplicate-key output semantics | Explicit UTF-8 file reads/writes reduce platform-default encoding drift | Ruff, py_compile, command help | Snapshot schema validation remains implicit and will raise standard key errors for malformed audit files | COMPLETED |
| `backend/apps/core/management/commands/export_masters_mds.py` | 326 | 326 | 20 | 1 | None | None | None | Replaced raw JSON output file handle with `Path.write_text(json.dumps(...), encoding="utf-8")` | Existing shared `build_export_record()` path retained for offline export parity with online MDS writes | None | Existing `test_export_masters_mds.py` and MDS write cutover regressions reviewed | No query-shape change; existing `select_related()`/`.values()` safeguards retained | Export remains read-only and id-free; explicit UTF-8 output prevents platform-default encoding drift | Ruff, py_compile, command help, targeted pytest | Fallback synthetic UID recipe remains duplicated intentionally so the exporter can run without `mds-client` installed | COMPLETED |
| `backend/apps/core/management/commands/fetch_detail_conf.py` | 11 | 11 | 1 | 1 | Removed unused `CommandError`, `Q`, and `LicenseDetailsModel` imports | None | None | Existing Django management command base retained | Existing legacy provider invocation retained | None | Command help reviewed | No runtime query behavior changed | No issue in repo-local code path | Ruff, py_compile, command help | Runtime still depends on external `item_fetch_conf` module outside this repository, matching the legacy command design | COMPLETED |
| `backend/apps/core/management/commands/fetch_exchange_rates.py` | 219 | 219 | 3 | 1 | None | Consolidated duplicated HTTP response decompression/decoding into `_decode_response_body()` | None | Added standard-library `gzip`/`zlib` decompression handling for DGFT responses | `_decode_response_body()` | None | Command help reviewed | Deflate/gzip handling is centralized and avoids duplicated response parsing branches | Brotli-compressed responses now fail explicitly if `brotli` is unavailable instead of attempting to decode compressed bytes as UTF-8 | Ruff, py_compile, command help | Live DGFT network fetch was not executed in the restricted audit environment; behavior is verified through syntax/static/help checks | COMPLETED |

### Batch 22 Issues Fixed

- Replaced raw snapshot/export file I/O with `Path` APIs and explicit UTF-8 handling.
- Indexed `diff_masters.py` other-server records by table/key to avoid repeated nested scans during merge-plan generation.
- Removed dead imports and stale poll-oriented help text from `fetch_detail_conf.py`.
- Consolidated DGFT HTTP response decoding and added explicit handling for gzip, deflate, and missing Brotli support.

### Phase 5 Remaining Scope After Batch 22

- Continue Backend `backend/apps/core` Management Commands from `merge_masters.py` onward.
- Then Scripts, Migrations, Tests, frontend master pages/tests, deployment configuration, and documentation.

## Batch 23 - Backend Core Management Commands: Merge/Reconcile, Migration Operations, Materialized Refresh, RQ Worker

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/management/commands/merge_masters.py` | 153 | 153 | 2 | 1 | None | None | None | Replaced raw JSON/CSV `open()` calls with encoded `Path` reads | Existing reviewed-plan merge command retained | None | Existing reconciliation/MDS regressions reviewed | No runtime query behavior changed | Explicit UTF-8 input reads reduce platform-default encoding drift; dry-run default preserved | Ruff, py_compile, command help | Limited table map intentionally covers the legacy `audit_masters` merge scope only | COMPLETED |
| `backend/apps/core/management/commands/rebuild_migrations.py` | 224 | 224 | 4 | 1 | Removed unused `os` import and unused private `_check_database_consistency()` helper | None | None | Replaced legacy `typing.List` with `list[str]`; chained `CommandError` exceptions with original causes | Existing destructive migration rebuild command retained behind explicit flags and dry-run option | None | Command help reviewed | Removing unused helper eliminates dead cursor/introspection path | Exception paths now retain causes for operator diagnostics | Ruff, py_compile, command help | Command remains high-risk operational tooling and should only be used after database backup, as documented | COMPLETED |
| `backend/apps/core/management/commands/reconcile_masters.py` | 420 | 420 | 7 | 1 | Removed unused `os` dependency | None | None | Replaced raw JSON file reads/writes with `Path.read_text()`/`Path.write_text()` and explicit UTF-8 encoding; chained command errors | Existing ADR-001 reconciliation logic retained | None | Existing `test_reconcile_masters.py` coverage reviewed | No reconciliation bucket behavior changed | Malformed input/write failures now preserve original exception cause | Ruff, py_compile, command help, targeted pytest | Test fixture still writes via raw `open()` inside tests; production command path is now encoded `Path` I/O | COMPLETED |
| `backend/apps/core/management/commands/refresh_materialized_views.py` | 118 | 118 | 2 | 1 | None | Replaced hardcoded materialized-view lists with shared `MATERIALIZED_VIEW_NAMES` | None | Existing Django management command APIs retained | Reuses materialized-view module allowlist for available-view output and freshness loops | None | Existing materialized-view tests reviewed | Avoids stale duplicated view lists when shared materialized-view constants change | Uses the same allowlisted names as the refresh/freshness helpers | Ruff, py_compile, command help, targeted pytest | Live PostgreSQL refresh was not executed in the restricted audit environment | COMPLETED |
| `backend/apps/core/management/commands/reset_migration_history.py` | 122 | 122 | 3 | 1 | None | None | None | Existing Django migration loader and transaction APIs retained | Existing idempotent migration-history reset command retained | None | Command help reviewed | No runtime behavior changed | SQL remains parameterized for app list writes | Ruff, py_compile, command help | PostgreSQL-specific `ANY(%s)` SQL remains intentional for this deployment stack | COMPLETED |
| `backend/apps/core/management/commands/rqworker.py` | 101 | 101 | 2 | 1 | Removed obsolete `distutils.LooseVersion`/Django-version gate and top-level optional RQ imports | None | None | Replaced raw PID `open()` write with `Path.write_text(..., encoding="utf-8")`; runtime missing-dependency failures now raise `CommandError` | Existing RQ worker command interface retained | None | Command help reviewed | Command discovery/help no longer imports optional RQ dependencies | Missing `django_rq`/`rq` now fails as a controlled command error at execution time instead of breaking command import/help | Ruff, py_compile, command help | Docs still expose `rqworker`; runtime execution remains blocked unless optional RQ dependencies are installed | COMPLETED |

### Batch 23 Issues Fixed

- Replaced raw JSON/CSV file handling in merge/reconcile commands with explicit encoded `Path` APIs.
- Removed dead migration-consistency helper code from `rebuild_migrations.py`.
- Consolidated duplicated materialized-view name lists with the shared materialized-view allowlist.
- Fixed `rqworker --help` so command discovery no longer requires optional RQ dependencies.
- Preserved high-risk operational command behavior behind existing explicit flags and dry-run defaults.

### Phase 5 Remaining Scope After Batch 23

- Continue Backend `backend/apps/core` Management Commands from `seed_e132_plan_items.py` onward.
- Then Scripts, Migrations, Tests, frontend master pages/tests, deployment configuration, and documentation.

## Batch 24 - Backend Core Management Commands: Seed, Schema Sync, Commodity Item Linking, DGFT Updates, Field Validation

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/management/commands/_item_linking.py` | 216 | 216 | 10 | 1 | None | Centralized duplicated Aluminium Foil/Sugar item-linking workflow | None | Existing Django ORM/transaction APIs retained | `CommodityItemLinkCommand` | Extracted from duplicated commodity-linking commands | Existing E132/core regressions reviewed | Uses prefetched export items via `.all()` list instead of `.first()` to avoid repeated per-item norm queries; prefetches sample clear-list relations | Runtime update errors are logged with traceback and re-raised | Ruff, py_compile, command help through concrete commands, targeted pytest | Shared helper still clears links from nonmatching import items to preserve original command behavior | COMPLETED |
| `backend/apps/core/management/commands/seed_e132_plan_items.py` | 79 | 79 | 1 | 1 | None | None | None | Existing Django transaction APIs retained | Existing E132 planning seed command retained | None | Existing E132 plan tests reviewed | No runtime behavior changed | Dry-run behavior preserved | Ruff, py_compile, command help, targeted pytest | Command intentionally depends on License E132 planning constants; License semantics remain for Phase 6 | COMPLETED |
| `backend/apps/core/management/commands/sync_database_schema.py` | 366 | 366 | 9 | 1 | Removed unused `Decimal` import and `sys` process-exit dependency | None | None | Operator cancellation now returns from the command instead of calling `sys.exit(0)` | Existing schema sync command retained | None | Existing core API regressions reviewed | No schema-analysis behavior changed | Operator cancellation remains non-destructive; backup warning still blocks unless confirmed | Ruff, py_compile, command help, targeted pytest | Backup implementation remains a warning/confirmation placeholder and should not be used as a real backup mechanism | COMPLETED |
| `backend/apps/core/management/commands/update_aluminium_foil_items.py` | 11 | 11 | 0 | 1 | Removed duplicated command implementation body | Shared commodity helper replaces duplicate Aluminium Foil workflow | None | Existing Django command discovery retained | Uses `CommodityItemLinkCommand` | Collapsed to configuration-only command | Existing core/E132 regressions reviewed | Inherits prefetched norm/sample behavior from shared helper | Destructive update remains behind existing confirmation and supports dry-run | Ruff, py_compile, command help, targeted pytest | Command still clears links from all non-Aluminium Foil import items, matching prior behavior | COMPLETED |
| `backend/apps/core/management/commands/update_dgft_descriptions.py` | 339 | 339 | 5 | 1 | Removed unused `SIONImportModel` import and local `re` import inside parser | None | None | Moved `json`, `re`, and `time` imports to module level | Existing DGFT SION update command retained | None | Command help reviewed | No network/runtime fetch behavior changed | No secrets; live DGFT call not executed in restricted audit environment | Ruff, py_compile, command help | Uses external DGFT network and `requests`/BeautifulSoup paths; live behavior requires network and dependency availability | COMPLETED |
| `backend/apps/core/management/commands/update_sugar_items.py` | 11 | 11 | 0 | 1 | Removed duplicated command implementation body | Shared commodity helper replaces duplicate Sugar workflow | None | Existing Django command discovery retained | Uses `CommodityItemLinkCommand` | Collapsed to configuration-only command | Existing core/E132 regressions reviewed | Inherits prefetched norm/sample behavior from shared helper | Destructive update remains behind existing confirmation and supports dry-run | Ruff, py_compile, command help, targeted pytest | Command still clears links from all non-Sugar import items, matching prior behavior | COMPLETED |
| `backend/apps/core/management/commands/validate_db_fields.py` | 374 | 374 | 8 | 1 | Removed unused legacy `typing` imports | None | None | Replaced `typing.Dict`/`List` annotations with built-in generics | Existing field validation command retained | None | Existing core API regressions reviewed | No validation behavior changed | Read-only validation path retained | Ruff, py_compile, command help, targeted pytest | PostgreSQL information_schema assumptions remain intentional for current deployment stack | COMPLETED |

### Batch 24 Issues Fixed

- Extracted the duplicated Sugar/Aluminium Foil item-linking workflow into a shared private command helper.
- Reduced both commodity update commands to declarative configuration while preserving names, options, confirmation behavior, and dry-run support.
- Improved commodity-linking query behavior by using prefetched export items and prefetching sample clear-list relations.
- Removed unused imports from schema sync, DGFT update, and DB field validation commands.
- Replaced `sys.exit(0)` cancellation in schema sync with a clean command return.

### Phase 5 Remaining Scope After Batch 24

- Backend `backend/apps/core` Management Commands are complete for the active Phase 5 scope.
- Continue to Backend `backend/apps/core` Scripts, then Migrations, Tests, frontend master pages/tests, deployment configuration, and documentation.

## Batch 25 - Backend Core Scripts

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/scripts/aro_letters.py` | 41 | 41 | 3 | 0 | Deleted obsolete unreferenced DOCX letter-generation script | Removed dead script-only workflow from active source inventory | None | None | None | File deleted | Existing core regressions reviewed | Removes unused import/runtime dependency path from source tree | No live behavior path removed; no references found outside generated audit metadata | Reference scan, remaining script compile, targeted pytest | Historical DOCX templates are not represented by an active CLI or documented workflow | DELETED |
| `backend/apps/core/scripts/script.py` | 15 | 15 | 1 | 0 | Deleted obsolete unreferenced xhtml2pdf helper script | Removes duplicate PDF rendering helper superseded by audited PDF utilities/exporters | None | None | None | File deleted | Existing core regressions reviewed | Removes unused import/runtime dependency path from source tree | No live behavior path removed; no references found outside generated audit metadata | Reference scan, remaining script compile, targeted pytest | None | DELETED |
| `backend/apps/core/scripts/sion.py` | 138 | 138 | 4 | 0 | Deleted obsolete unreferenced legacy SION scraper | Removes stale scraper path superseded by audited DGFT update management command | None | None | None | File deleted | Existing core regressions reviewed | Removes unused external scraping path from source tree | No live behavior path removed; no references found outside generated audit metadata | Reference scan, remaining script compile, targeted pytest | Live SION synchronization remains in `update_dgft_descriptions.py` and requires network/dependencies | DELETED |
| `backend/apps/core/scripts/__init__.py` | 0 | 0 | 0 | 0 | None | None | None | None | Package marker retained for remaining script imports | None | Existing core regressions reviewed | No runtime change | No issue | py_compile, targeted pytest | No issue | COMPLETED |
| `backend/apps/core/scripts/calculate_balance.py` | 204 | 204 | 4 | 0 | Previously completed; recompiled after sibling script deletions | None | None | Existing script behavior retained | Existing balance calculation script retained | None | Existing core regressions reviewed | No runtime change in this batch | No issue | py_compile, targeted pytest | Domain-specific balance behavior remains deferred to License/Inventory phases | COMPLETED |
| `backend/apps/core/scripts/calculation.py` | 154 | 154 | 2 | 0 | Previously completed; recompiled after sibling script deletions | None | None | Existing script behavior retained | Existing calculation script retained | None | Existing core regressions reviewed | No runtime change in this batch | No issue | py_compile, targeted pytest | Domain-specific balance behavior remains deferred to License/Inventory phases | COMPLETED |
| `backend/apps/core/scripts/company_names.py` | 125 | 125 | 2 | 0 | Previously completed; recompiled after sibling script deletions | None | None | Existing script behavior retained | Existing company-name script retained | None | Existing core regressions reviewed | No runtime change in this batch | No issue | py_compile, targeted pytest | No issue for Phase 5 scope | COMPLETED |
| `backend/apps/core/scripts/ledger.py` | 322 | 322 | 4 | 0 | Previously completed; recompiled after sibling script deletions | None | None | Existing script behavior retained | Existing ledger script retained | None | Existing core regressions reviewed | No runtime change in this batch | No issue | py_compile, targeted pytest | Ledger semantics remain for License phase ownership | COMPLETED |
| `backend/apps/core/scripts/license_script.py` | 111 | 111 | 2 | 0 | Previously completed; recompiled after sibling script deletions | None | None | Existing script behavior retained | Existing license script retained | None | Existing core regressions reviewed | No runtime change in this batch | No issue | py_compile, targeted pytest | License semantics remain for License phase ownership | COMPLETED |

### Batch 25 Issues Fixed

- Deleted three unreferenced obsolete scripts from `backend/apps/core/scripts`.
- Removed a dead xhtml2pdf helper script that duplicated audited PDF helper/exporter responsibility.
- Removed a stale SION scraper path superseded by the DGFT update management command.
- Verified no live backend/docs/tests references remain outside generated audit metadata.
- Recompiled all remaining core scripts and ran focused core regressions.

### Phase 5 Remaining Scope After Batch 25

- Backend `backend/apps/core` Scripts are complete for the active Phase 5 scope.
- Continue to Backend `backend/apps/core` Migrations, then Tests, frontend master pages/tests, deployment configuration, and documentation.

## Batch 26 - Backend Core Migrations

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/migrations/__init__.py` | 0 | 0 | 0 | 0 | None | None | None | None | Migration package marker retained | None | Existing migration checks reviewed | No runtime change | No issue | Ruff, py_compile, makemigrations check, targeted pytest | No issue | COMPLETED |
| `backend/apps/core/migrations/0001_initial.py` | 389 | 389 | 0 | 1 | None | None | None | Generated Django migration primitives retained | Initial core schema migration retained unchanged | None | Existing keyless/E132 regressions reviewed | Historical schema contract preserved | No issue | Ruff, py_compile, makemigrations check, targeted pytest | Generated migration remains large by nature | COMPLETED |
| `backend/apps/core/migrations/0002_remove_companymodel_address.py` | 48 | 48 | 2 | 1 | None | None | None | Existing data-preserving backfill retained | Company address-column removal migration retained unchanged | None | Existing core regressions reviewed | Iterator backfill retained | Data-preserving copy before column removal verified by review | Ruff, py_compile, makemigrations check, targeted pytest | Uses `print()` inside migration for operator visibility; retained to avoid changing migration output | COMPLETED |
| `backend/apps/core/migrations/0003_create_materialized_views.py` | 38 | 38 | 2 | 1 | None | None | None | Existing migration `RunPython` retained | Materialized-view recreation migration retained unchanged | None | Existing materialized/keyless regressions reviewed | No runtime change | View SQL helper allowlisting was audited earlier | Ruff, py_compile, makemigrations check, targeted pytest | Migration imports current helper code by design; historical SQL is not embedded in this migration | COMPLETED |
| `backend/apps/core/migrations/0004_headsionnormsmodel_created_on_and_more.py` | 68 | 68 | 1 | 1 | None | None | None | Existing Django `F()` set-based backfill retained | Timestamp/MasterChange migration retained unchanged | None | Existing keyless regressions reviewed | Set-based timestamp backfill retained | No issue | Ruff, py_compile, makemigrations check, targeted pytest | No issue | COMPLETED |
| `backend/apps/core/migrations/0005_add_uid_to_keyless_masters.py` | 48 | 48 | 0 | 1 | None | None | None | Existing UUIDField migration retained | Keyless UID field migration retained unchanged | None | Existing keyless regressions reviewed | No runtime change | No issue | Ruff, py_compile, makemigrations check, targeted pytest | No issue | COMPLETED |
| `backend/apps/core/migrations/0006_backfill_master_uids.py` | 198 | 198 | 10 | 1 | None | None | None | Existing uuid/date/datetime/Decimal fallback retained | Deterministic UID backfill migration retained unchanged | None | Existing keyless regressions reviewed | Bulk UID updates and `.values()` FK joins retained | Deterministic UID recipe remains byte-compatible with MDS client/exporter fallback | Ruff, py_compile, makemigrations check, targeted pytest | Fallback recipe is intentionally duplicated inside migration to avoid mutable runtime dependency | COMPLETED |
| `backend/apps/core/migrations/0007_seed_e132_plan_items.py` | 55 | 55 | 2 | 1 | None | Duplicate seed pattern reviewed but retained as frozen migration data | None | Existing ORM migration APIs retained | Frozen E132 initial planning-item seed retained unchanged | None | Existing E132 regressions reviewed | No runtime change | No issue | Ruff, py_compile, makemigrations check, targeted pytest | Similar seed/update logic appears in later E132 migrations; retained to keep migrations self-contained | COMPLETED |
| `backend/apps/core/migrations/0008_seed_e132_extra_plan_items.py` | 54 | 54 | 2 | 1 | None | Duplicate seed pattern reviewed but retained as frozen migration data | None | Existing ORM migration APIs retained | Frozen E132 extra planning-item seed retained unchanged | None | Existing E132 regressions reviewed | No runtime change | No issue | Ruff, py_compile, makemigrations check, targeted pytest | Similar seed/update logic appears in adjacent E132 migrations; retained to keep migrations self-contained | COMPLETED |
| `backend/apps/core/migrations/0009_seed_e132_cmc_plan_item.py` | 46 | 46 | 2 | 1 | None | Duplicate seed pattern reviewed but retained as frozen migration data | None | Existing ORM migration APIs retained | Frozen E132 CMC seed retained unchanged | None | Existing E132 regressions reviewed | No runtime change | No issue | Ruff, py_compile, makemigrations check, targeted pytest | Similar seed/update logic appears in adjacent E132 migrations; retained to keep migrations self-contained | COMPLETED |
| `backend/apps/core/migrations/0010_sync_e132_display_order.py` | 49 | 49 | 2 | 1 | None | None | None | Existing ORM migration APIs retained | Frozen E132 display-order sync retained unchanged | None | Existing E132 regressions reviewed | No runtime change | No issue | Ruff, py_compile, makemigrations check, targeted pytest | Reverse remains no-op by design to avoid destructive data restoration | COMPLETED |
| `backend/apps/core/migrations/0011_split_milk_into_swp_dwp_wpc.py` | 74 | 74 | 2 | 1 | None | Duplicate seed/update pattern reviewed but retained as frozen migration data | None | Existing ORM migration APIs retained | Frozen E132 milk split retained unchanged | None | Existing E132 regressions reviewed | No runtime change | No issue | Ruff, py_compile, makemigrations check, targeted pytest | Similar seed/update logic appears in adjacent E132 migrations; retained to keep migrations self-contained | COMPLETED |

### Batch 26 Issues Fixed

- No migration code was changed; historical migration contracts were preserved.
- Verified all core migrations line-by-line for import safety, dependencies, data migration behavior, reverse paths, and frozen E132 data values.
- Confirmed migration state matches models with `makemigrations core --check --dry-run`.
- Documented intentionally retained duplication in E132 data migrations because extracting runtime helpers into historical migrations would reduce migration stability.

### Phase 5 Remaining Scope After Batch 26

- Backend `backend/apps/core` Migrations are complete for the active Phase 5 scope.
- Continue to Backend `backend/apps/core` Tests, then frontend master pages/tests, deployment configuration, and documentation.

## Batch 27 - Backend Core Tests

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/apps/core/tests.py` | 3 | 3 | 0 | 0 | Deleted unused Django starter test stub | None | None | None | None | File deleted | Existing package tests retained | Removes unused test discovery noise | No issue | Reference scan, Ruff, py_compile, targeted pytest | None | DELETED |
| `backend/apps/core/tests/__init__.py` | 3 | 3 | 0 | 0 | None | None | None | None | Test package marker retained | None | Existing tests retained | No runtime change | No issue | Ruff, py_compile, targeted pytest | No issue | COMPLETED |
| `backend/apps/core/tests/test_check_master_quality.py` | 96 | 96 | 6 | 0 | None | None | None | Added explicit UTF-8 read for JSON report fixture output | Existing management-command regression coverage retained | None | Existing tests updated in place | No runtime change | No issue | Ruff, py_compile, targeted pytest | Duplicate-key path is skipped when DB uniqueness enforcement prevents reproducing legacy duplicate data | COMPLETED |
| `backend/apps/core/tests/test_keyless_uid.py` | 103 | 103 | 7 | 0 | None | None | None | Added explicit UTF-8 read for MDS export JSON fixture output | Existing keyless UID regression coverage retained | None | Existing tests updated in place | No runtime change | No issue | Ruff, py_compile, targeted pytest | No issue | COMPLETED |
| `backend/apps/core/tests/test_reconcile_masters.py` | 257 | 257 | 20 | 3 | Removed `os` dependency and raw file writes | None | None | Replaced raw temporary JSON writes with `Path.write_text(..., encoding="utf-8")` | Existing reconciliation unit coverage retained | None | Existing tests updated in place | No runtime change | No issue | Ruff, py_compile, targeted pytest | Tests remain unittest-style to match existing file structure | COMPLETED |
| `backend/apps/core/tests/test_validation.py` | 546 | 546 | 87 | 14 | Removed unused `timedelta` import and local pytest shim | None | Replaced custom `pytest.raises` shim with real pytest | Existing unittest-style validation test cases retained | Existing validation coverage retained | None | Existing tests updated in place | No runtime change | No issue | Ruff, py_compile, targeted pytest | Tests remain class-heavy; broader restructuring deferred because coverage is stable and behavior-focused | COMPLETED |

### Batch 27 Issues Fixed

- Deleted the unused legacy `backend/apps/core/tests.py` starter stub.
- Replaced a custom pytest shim in validation tests with real `pytest.raises`.
- Added explicit UTF-8 fixture reads/writes in JSON-based tests.
- Removed unused imports from pending core tests.
- Verified the focused core test suite remains green.

### Phase 5 Remaining Scope After Batch 27

- Backend `backend/apps/core` Tests are complete for the active Phase 5 scope.
- Continue to frontend master pages/tests, deployment configuration, and documentation before freezing Phase 5.

## Batch 28 - Frontend Master Display Components, Nested Arrays, Config, and API Helper

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `frontend/src/components/MasterFormModal.tsx` | 30 | 30 | 1 | 0 | Deleted unused modal component after repository reference scan found no imports | Removed obsolete modal wrapper superseded by current master routing/forms | None | None | None | File deleted | Existing master form/list tests retained | Removes unused bundle surface | No active behavior path removed; no references found in `frontend/src` | `rg MasterFormModal frontend/src`, frontend focused tests/lint/typecheck | None | DELETED |
| `frontend/src/pages/masters/masterDisplayFormatters.ts` | 36 | 36 | 4 | 0 | None | Centralized repeated Indian currency/number/date display formatting for pending master UI files | None | Existing `Intl.NumberFormat`/`toLocaleString` path retained | `formatTruthyIndianNumber`, `formatTruthyInr`, `formatInr`, `parseMasterDisplayDate` | New cohesive display helper | `masterDisplayFormatters.test.ts` | Reduces per-row formatter recreation and duplicated locale options | No security-sensitive behavior | focused Vitest, ESLint, TypeScript | Falsey row values intentionally continue displaying as empty/dash to preserve existing UI behavior | COMPLETED |
| `frontend/src/pages/masters/masterDisplayFormatters.test.ts` | 31 | 31 | 4 | 0 | None | None | None | Vitest assertions retained | Regression coverage for display helper edge cases | None | Added 4 focused tests | No runtime impact | No issue | focused Vitest, ESLint, TypeScript | No issue | COMPLETED |
| `frontend/src/pages/masters/BoeMergeModal.tsx` | 117 | 117 | 1 | 0 | None | Replaced inline BOE INR formatting with shared master display helper | None | Existing locale formatting retained through helper | Uses `formatTruthyInr` | None | Covered by focused helper regression and typecheck | Removes duplicated formatter allocation from candidate rows | Merge confirmation behavior unchanged; destructive action remains parent-controlled | focused Vitest, ESLint, TypeScript | Props remain broadly typed as `any` because parent state shape is still untyped in completed `MasterList` | COMPLETED |
| `frontend/src/pages/masters/BoeParsePanel.tsx` | 128 | 128 | 1 | 0 | None | None | None | Existing file input and optional chaining retained | Existing BOE parse panel retained unchanged | None | Existing master form smoke coverage retained | No runtime change | PDF upload surface reviewed; file type accept remains client-side UX only and server validation remains authoritative | focused Vitest, ESLint, TypeScript | Summary/licence rows remain `any` until backend parse DTOs are formalized | COMPLETED |
| `frontend/src/pages/masters/LicenseParsePanel.tsx` | 179 | 179 | 1 | 0 | None | None | None | Existing `openDocument` helper retained for saved copy access | Existing licence parse panel retained unchanged | None | Existing master form smoke coverage retained | No runtime change | Download/open path stays centralized through `openDocument`; no raw HTML injection | focused Vitest, ESLint, TypeScript | Summary/items and saved-copy props remain `any` pending typed master DTOs | COMPLETED |
| `frontend/src/pages/masters/LinkTradeModal.tsx` | 66 | 66 | 1 | 0 | None | Replaced inline trade amount formatting with shared master display helper | None | Existing locale formatting retained through helper | Uses `formatTruthyInr` | None | Covered by focused helper regression and typecheck | Removes duplicated formatter allocation from result rows | Link confirmation remains parent-controlled; clickable helper retained for keyboard behavior | focused Vitest, ESLint, TypeScript | Props remain broadly typed as `any` because trade search result DTO is not yet formalized | COMPLETED |
| `frontend/src/pages/masters/NestedFieldArray.tsx` | 759 | 759 | 11 | 0 | None | Replaced repeated INR aggregate footer formatting with shared master display helper | None | Existing date formatter and `Intl` locale formatting retained | Uses `formatInr` | Not split; file is large but cohesive around nested master row editing/rendering | Covered by focused helper regression and typecheck | Reduces duplicate aggregate formatter calls and keeps calculation paths unchanged | Frozen ledger rows, file inputs, async description lookup, and API fetch paths reviewed; no security behavior changed | focused Vitest, ESLint, TypeScript | Large component remains a future candidate for typed field-renderer extraction after parent DTOs are stabilized | COMPLETED |
| `frontend/src/pages/masters/TradeMetaBadges.tsx` | 25 | 25 | 1 | 0 | None | None | None | Existing static lookup maps retained | Existing badge component retained unchanged | None | Existing master form smoke coverage retained | No runtime change | No issue | focused Vitest, ESLint, TypeScript | Unknown direction/license values render undefined labels/colors as before; parent currently supplies known choices | COMPLETED |
| `frontend/src/pages/masters/entitySections.ts` | 133 | 133 | 0 | 0 | None | None | None | Static configuration retained | Existing entity section config retained unchanged | None | Existing master form smoke coverage retained | No runtime change | No issue | focused Vitest, ESLint, TypeScript | Config remains untyped because backend metadata field names are still dynamic | COMPLETED |
| `frontend/src/pages/masters/masterListConfig.ts` | 22 | 22 | 1 | 0 | None | None | None | Existing switch retained for stable defaults | Existing list default-filter helper retained | None | Existing `masterListConfig.test.ts` retained | No runtime change | No issue | focused Vitest, ESLint, TypeScript | No issue | COMPLETED |
| `frontend/src/pages/masters/masterListConfig.test.ts` | 26 | 26 | 4 | 0 | None | None | None | Existing Vitest coverage retained | Existing default-filter regression tests retained | None | Existing tests reviewed | No runtime impact | No issue | focused Vitest, ESLint, TypeScript | No issue | COMPLETED |
| `frontend/src/pages/masters/tables/AllotmentsTable.tsx` | 148 | 148 | 1 | 0 | None | Replaced duplicated INR/quantity row formatters with shared master display helper | None | Existing locale formatting retained through helper | Uses `formatTruthyInr` and `formatTruthyIndianNumber` | None | Covered by focused helper regression and typecheck | Reduces per-row locale option duplication; PDF preview/download calls unchanged | Existing authenticated API blob calls retained; object URL revocation reviewed | focused Vitest, ESLint, TypeScript | PDF download still manually creates anchors; acceptable for current browser-only flow | COMPLETED |
| `frontend/src/pages/masters/tables/IncentiveLicensesTable.tsx` | 104 | 104 | 1 | 0 | None | Replaced duplicated INR/date parsing helpers with shared master display helper | None | Existing shared date parser retained via helper | Uses `formatTruthyInr` and `parseMasterDisplayDate` | None | Covered by focused helper regression and typecheck | Removes per-row custom date parser closure and duplicated INR formatter | No security-sensitive behavior | focused Vitest, ESLint, TypeScript | Broad `any` row shape remains until incentive-license list DTOs are typed | COMPLETED |
| `frontend/src/services/api/masterApi.js` | 131 | 131 | 12 | 0 | None | None | None | Existing Axios service wrapper retained | Existing master CRUD/export/file helper API retained unchanged | None | Existing frontend typecheck/lint reviewed | No runtime change | Endpoint strings remain caller-provided; Axios auth/error handling stays centralized | focused Vitest, ESLint, TypeScript | JavaScript service remains untyped until API client migration to TypeScript | COMPLETED |

### Batch 28 Issues Fixed

- Deleted unused `MasterFormModal.tsx` after confirming it had no imports in `frontend/src`.
- Extracted repeated master-display INR/number/date formatting into `masterDisplayFormatters.ts`.
- Added focused regression tests proving falsey row values still render as the existing dash/empty display and aggregate totals still preserve zero.
- Replaced duplicated formatter logic in pending BOE merge, trade link, allotment, incentive-license, and nested-array footer files.
- Kept parse panels, static section config, list config, and master API service behavior unchanged after line-by-line review.

### Phase 5 Remaining Scope After Batch 28

- Frontend master pending display/config/API files from the active queue are complete.
- Continue Phase 5 with remaining backend master-data scripts/tests outside `backend/apps/core`, master-data shell scripts, deployment configuration, and documentation.

## Batch 29 - Backend Golden-Master Scripts and MDS Export Regression

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `backend/scripts/golden_master_balance_exporters.py` | 327 | 327 | 10 | 0 | None | None | None | Replaced path string joins/raw JSON `open()` calls with `pathlib.Path` and explicit UTF-8 JSON reads/writes | Existing balance-exporter golden-master harness retained | None | Existing characterization harness retained | No endpoint invocation or fingerprint semantics changed | Read-only DB harness retained; no credential or write paths introduced | Ruff, py_compile, no-arg usage path, focused pytest | Runtime `record`/`check` still requires live dev DB, superuser, `openpyxl`, and `pypdf` | COMPLETED |
| `backend/scripts/golden_master_ledger_pdf.py` | 142 | 142 | 5 | 0 | None | None | None | Replaced path string joins/raw JSON `open()` calls with `pathlib.Path` and explicit UTF-8 JSON reads/writes | Existing ledger-PDF golden-master harness retained | None | Existing characterization harness retained | No PDF fingerprint semantics changed | Fixed no-argument usage path so it validates mode and prints usage before any DB access | Ruff, py_compile, no-arg usage path, focused pytest | Runtime `record`/`check` still requires live dev DB and `pypdf`; `check` now fails fast if baseline is missing | COMPLETED |
| `backend/tests/test_export_masters_mds.py` | 128 | 128 | 12 | 0 | None | None | None | Added explicit UTF-8 read for exported JSON fixture | Existing MDS export regression retained | None | Existing 9 tests retained | No runtime change | No issue | Ruff, py_compile, pytest `9 passed` | No issue | COMPLETED |

### Batch 29 Issues Fixed

- Standardized golden-master baseline path handling with `pathlib.Path`.
- Added explicit UTF-8 JSON reads/writes in golden-master scripts and the MDS export regression.
- Fixed `golden_master_ledger_pdf.py` so no-argument usage/help no longer attempts to connect to PostgreSQL.
- Verified the MDS export focused regression remains green and removed generated coverage artifacts afterward.

### Phase 5 Remaining Scope After Batch 29

- Backend golden-master scripts and `test_export_masters_mds.py` are complete for Phase 5.
- Continue Phase 5 with master-data shell scripts, deployment/configuration, and documentation.

## Batch 30 - Master Data Shell Scripts

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `scripts/maintenance/_master_sync_lib.sh` | 39 | 39 | 5 | 0 | None | Centralized duplicated legacy maintenance logging, server inventory, and SSH/SCP wrapper setup | None | Existing POSIX/Bash utilities retained | `master_sync_setup_ssh` and shared server config | New shared maintenance shell library | None | Reduces duplicated command setup work across three scripts | Password can now be supplied by `MASTER_SYNC_PASSWORD`/`SYNC_PASSWORD`; legacy fallback preserved for behavior compatibility | `bash -n` | Legacy fallback password remains for compatibility and should be removed in a future operator-approved hardening pass | COMPLETED |
| `scripts/maintenance/apply-master-merge.sh` | 83 | 83 | 0 | 0 | Removed local duplicate color/log/SSH/server setup | Uses `_master_sync_lib.sh` for winner host, credentials, logging, and SSH/SCP wrappers | None | Existing Bash behavior retained | Uses `master_sync_setup_ssh` | None | None | No remote merge behavior changed | Env override support added for credentials/hosts while keeping legacy defaults | `bash -n` | Remote execution not run in audit because it would SSH into production-like hosts and can apply changes after confirmation | COMPLETED |
| `scripts/maintenance/audit-and-diff-masters.sh` | 101 | 101 | 0 | 0 | Removed local duplicate color/log/SSH/server setup | Uses `_master_sync_lib.sh` for server inventory and SSH/SCP wrappers | None | Existing Bash behavior retained | Uses shared maintenance config | None | None | No audit/diff behavior changed | Env override support added for credentials/hosts while keeping legacy defaults | `bash -n` | Remote audit/diff not run in audit because it would SSH into configured servers | COMPLETED |
| `scripts/maintenance/audit-and-merge-masters.sh` | 111 | 111 | 0 | 0 | Removed local duplicate color/log/SSH/server setup | Uses `_master_sync_lib.sh` for server inventory, winner host, and SSH/SCP wrappers | None | Existing Bash behavior retained | Uses shared maintenance config | None | None | No auto-import behavior changed | Env override support added for credentials/hosts while keeping legacy defaults | `bash -n` | Remote auto-import not run in audit because it would SSH into configured servers and can apply changes after confirmation | COMPLETED |
| `scripts/maintenance/sync-masters.sh` | 107 | 107 | 4 | 0 | None | Reviewed against new maintenance helper; kept independent because it has quiet-mode cron semantics and already requires env-only `SYNC_PASSWORD` | None | Existing Bash behavior retained | Existing cron sync script retained | None | None | No runtime change | Existing hard requirement for `SYNC_PASSWORD` and `sshpass` retained; no hardcoded password | `bash -n` | Could later be adapted to `_master_sync_lib.sh` with a quiet-mode-aware wrapper, but not needed for safe Phase 5 behavior | COMPLETED |
| `scripts/mds/_lib.sh` | 173 | 173 | 17 | 0 | None | Added shared `mds_usage` to replace repeated help extraction in all MDS scripts | None | Added explicit UTF-8 handling in embedded Python JSON readers | `mds_usage` | Existing shared library retained | None | No remote behavior changed | Secrets remain env-only; JSON helpers no longer rely on locale-default decoding | `bash -n`, MDS help commands | SSH helper still supports `sshpass` fallback when `SYNC_PASSWORD` is set; SSH keys remain preferred | COMPLETED |
| `scripts/mds/export-master-data.sh` | 114 | 114 | 1 | 0 | None | Replaced local duplicated usage function body with shared `mds_usage` | None | Existing Bash behavior retained | Uses `mds_usage` | None | None | Help path no longer scans internal comments | Read-only export contract preserved | `bash -n`, `--help` | Remote/local export not executed because it would require configured DB/SSH targets | COMPLETED |
| `scripts/mds/load-master-data.sh` | 190 | 190 | 1 | 0 | None | Replaced local duplicated usage function body with shared `mds_usage` | None | Existing Bash behavior retained | Uses `mds_usage` | None | None | Help path no longer scans internal comments | Backup-before-load and `--confirm` gates preserved | `bash -n`, `--help` | Load path not executed because it requires target MDS PostgreSQL and can write with `--confirm` | COMPLETED |
| `scripts/mds/migrate-all-servers.sh` | 206 | 206 | 2 | 0 | None | Replaced local duplicated usage function body with shared `mds_usage` | None | Existing Bash behavior retained | Uses `mds_usage` | None | None | Help path no longer scans internal comments | Dry-run default and conflict gate preserved | `bash -n`, `--help` | Full migration not executed because it requires SSH targets and MDS DB | COMPLETED |
| `scripts/mds/onboard-server.sh` | 213 | 213 | 2 | 0 | None | Replaced local duplicated usage function body with shared `mds_usage` | None | Existing Bash behavior retained | Uses `mds_usage` | None | None | Help path no longer scans internal comments | Token masking, env-only secret input, dry-run default, and `--confirm` gate preserved | `bash -n`, `--help` | Onboarding not executed because it writes env/migrations with `--confirm` | COMPLETED |

### Batch 30 Issues Fixed

- Extracted shared legacy maintenance SSH/logging/server configuration into `scripts/maintenance/_master_sync_lib.sh`.
- Removed duplicated host/credential/SSH wrapper setup from three master maintenance scripts.
- Added env override support for legacy maintenance credentials and hosts while preserving existing fallback behavior.
- Added shared `mds_usage` so MDS `--help` output no longer includes internal implementation comments.
- Added explicit UTF-8 JSON reads in the MDS shell helper embedded Python snippets.

### Phase 5 Remaining Scope After Batch 30

- Master-data shell scripts are complete for Phase 5.
- Continue Phase 5 with documentation/deployment configuration files only.

## Batch 31 - Master Data Documentation and Deployment Notes

| File path | Total LOC | Lines reviewed | Functions reviewed | Classes reviewed | Dead code removed | Duplicate logic removed | Package replacements | Standard library replacements | Shared utilities extracted | Files split | Tests added | Performance improvements | Security improvements | Verification | Remaining technical debt | Status |
|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| `docs/architecture/ADR-001-master-data-service.md` | 233 | 233 | 0 | 0 | None | None | None | None | Existing ADR retained | None | None | No runtime impact | Status updated from proposed to accepted/in progress; legacy sync fallback and shared maintenance helper documented | Stale-reference scan | ADR still contains implementation roadmap/open questions by design | COMPLETED |
| `docs/architecture/MODULARIZATION_MASTER_PLAN.md` | 88 | 88 | 0 | 0 | Removed stale historical plan content referencing non-existent `/backend/core`, `.jsx`, and `components/common` paths | Replaced old duplicate checklist with current module map and audit-aligned queue | None | None | Current audited module map documented | File rewritten for accuracy | None | Reduces future rework caused by stale instructions | Documents operator-approved removal of legacy password fallback as future security task | Stale-reference scan | Later phases must continue updating this plan as module ownership changes | COMPLETED |
| `docs/operations/master-consolidation.md` | 190 | 190 | 0 | 0 | None | None | None | None | Existing runbook retained | None | None | No runtime impact | Added script write/no-write table, confirmation gates, and env override guidance | Stale-reference scan | Remote scripts are documented but not executed in audit due SSH/production-write risk | COMPLETED |

### Batch 31 Issues Fixed

- Updated ADR status to accepted/in-progress and documented the legacy sync fallback/helper context.
- Replaced the stale modularization plan with a current audited map of backend/frontend/shared modules.
- Added runbook coverage for maintenance and MDS wrapper scripts, including write gates and credential override guidance.
- Verified no actionable stale old-path references remain in these Phase 5 docs.

### Phase 5 Remaining Scope After Batch 31

- Phase 5 Master Data source, scripts, tests, and documentation are complete for the active audit queue.
- Regenerate audit artifacts and freeze Phase 5 before moving to Phase 6.
