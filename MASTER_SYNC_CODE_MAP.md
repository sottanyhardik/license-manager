# Master Sync Complete Code Map

**Generated:** 2026-08-12  
**Scope:** All Master models (16), Sync infrastructure (6), API endpoints, serializers, services, signals, migrations, management commands, tests, and frontend components

---

## Table of Contents

1. [Master Models (16)](#master-models-16)
2. [Sync Infrastructure Models (6)](#sync-infrastructure-models-6)
3. [API Endpoints & ViewSets](#api-endpoints--viewsets)
4. [Serializers](#serializers)
5. [Services](#services)
6. [Signals & Handlers](#signals--handlers)
7. [Management Commands](#management-commands)
8. [Migrations](#migrations)
9. [Tests](#tests)
10. [Frontend Components](#frontend-components)
11. [Dependencies & Cross-References](#dependencies--cross-references)

---

## Master Models (16)

All Master models are defined in `backend/apps/core/models.py` and share:
- Mixin: `MasterSyncMixin` (from `master_sync_base.py`)
- Each model implements `compute_master_uid()` method for unique identification
- Each model has `uid`, `version`, `is_tombstone`, `tombstone_expires_at` fields for sync

### 1. Company Model
- **File:** `backend/apps/core/models.py:226`
- **Class:** `CompanyModel`
- **Fields:** id, company_code, company_name, office_address, company_url, company_note, company_email, company_phone, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes company_code
- **Serializer:** `CompanySerializer` (line 24 in `serializers/models.py`)
- **ViewSet:** `CompanyViewSet` (in `views/views.py` and `views/master_view.py`)
- **Admin:** Auto-registered in `admin.py`

### 2. Port Model
- **File:** `backend/apps/core/models.py:293`
- **Class:** `PortModel`
- **Fields:** id, port_name, port_code, port_code_1, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes port_code
- **Serializer:** `PortSerializer` (line 66 in `serializers/models.py`)
- **ViewSet:** `PortViewSet` (in `views/views.py`)
- **API Endpoint:** `/ports` (registered in `urls.py:22`)

### 3. ItemGroup Model
- **File:** `backend/apps/core/models.py:344`
- **Class:** `ItemGroupModel`
- **Fields:** id, group_name, group_code, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes group_code
- **Serializer:** `GroupSerializer` (implied by registration)
- **ViewSet:** `GroupViewSet` (in `views/views.py`)
- **API Endpoint:** `/groups`

### 4. ItemName Model
- **File:** `backend/apps/core/models.py:359`
- **Class:** `ItemNameModel`
- **Fields:** id, item_code, item_name, group, unit, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes item_code
- **Serializer:** `ItemNameSerializer` (line 290 in `serializers/models.py`)
- **ViewSet:** `ItemNameViewSet` (in `views/views.py`)
- **API Endpoint:** `/item-names`
- **FilterSet:** `ItemNameFilterSet` (in `filtersets.py:308`)

### 5. HSCode Model
- **File:** `backend/apps/core/models.py:399`
- **Class:** `HSCodeModel`
- **Fields:** id, hs_code, product_description, basic_duty, unit_price, unit, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes hs_code
- **Serializer:** `HSCodeSerializer` (line 73 in `serializers/models.py`)
- **ViewSet:** `HSCodeViewSet` (in `views/views.py`)
- **API Endpoint:** `/hs-codes`
- **Admin:** `HSCodeDutyAdmin` (line 40 in `admin.py`)
- **FilterSet:** `HSCodeFilterSet` (in `filtersets.py:316`)

### 6. HeadSIONNorms Model
- **File:** `backend/apps/core/models.py:425`
- **Class:** `HeadSIONNormsModel`
- **Fields:** id, head_description, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes head_description
- **Serializer:** `HeadSIONNormsSerializer` (line 80 in `serializers/models.py`)
- **ViewSet:** `HeadSIONNormsViewSet` (in `views/views.py`)
- **API Endpoint:** `/head-norms`

### 7. SionNormClass Model
- **File:** `backend/apps/core/models.py:439`
- **Class:** `SionNormClassModel`
- **Fields:** id, head_sion_norms (FK), class_code, class_description, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes (head_sion_norms_id, class_code)
- **Serializer:** `SionNormClassNestedSerializer` (line 127 in `serializers/models.py`)
- **ViewSet:** `SionNormClassViewSet` (in `views/views.py`)
- **API Endpoint:** `/sion-classes`
- **Signal Handlers:** `on_sionnormclass_save()`, `on_sionnormclass_delete()` (in `signals_master_sync.py:210,321`)

### 8. SIONExport Model
- **File:** `backend/apps/core/models.py:456`
- **Class:** `SIONExportModel`
- **Fields:** id, sion_class, sion_description, rate, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes (sion_class, sion_description)
- **Serializer:** `SIONExportSerializer` (line 87 in `serializers/models.py`)

### 9. SIONImport Model
- **File:** `backend/apps/core/models.py:483`
- **Class:** `SIONImportModel`
- **Fields:** id, sion_class, sion_description, rate, additional_rate, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes (sion_class, sion_description)
- **Serializer:** `SIONImportSerializer` (line 95 in `serializers/models.py`)

### 10. SionNormNote Model
- **File:** `backend/apps/core/models.py:525`
- **Class:** `SionNormNote`
- **Fields:** id, sion_class, sion_description, note_description, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes (sion_class, sion_description)
- **Serializer:** `SionNormNoteSerializer` (line 110 in `serializers/models.py`)

### 11. SionNormCondition Model
- **File:** `backend/apps/core/models.py:552`
- **Class:** `SionNormCondition`
- **Fields:** id, sion_class, sion_description, condition_description, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes (sion_class, sion_description)
- **Serializer:** `SionNormConditionSerializer` (line 118 in `serializers/models.py`)

### 12. ProductDescription Model
- **File:** `backend/apps/core/models.py:579`
- **Class:** `ProductDescriptionModel`
- **Fields:** id, hs_code, product_code, product_description, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes (hs_code, product_code)
- **Serializer:** `ProductDescriptionSerializer` (line 249 in `serializers/models.py`)
- **ViewSet:** `ProductDescriptionViewSet` (in `views/views.py`)
- **API Endpoint:** `/product-descriptions`

### 13. UnitPrice Model
- **File:** `backend/apps/core/models.py:610`
- **Class:** `UnitPriceModel`
- **Fields:** id, unit_price_code, unit_price_value, unit, description, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes unit_price_code
- **Serializer:** `UnitPriceSerializer` (line 258 in `serializers/models.py`)
- **ViewSet:** `UnitPriceViewSet` (in `views/views.py`)
- **API Endpoint:** `/unit-prices`

### 14. SchemeCode Model
- **File:** `backend/apps/core/models.py:670`
- **Class:** `SchemeCode`
- **Fields:** id, code, description, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes code
- **Serializer:** `SchemeCodeSerializer` (line 337 in `serializers/models.py`)
- **ViewSet:** `SchemeCodeViewSet` (in `views/views.py`)
- **API Endpoint:** `/scheme-codes`

### 15. NotificationNumber Model
- **File:** `backend/apps/core/models.py:682`
- **Class:** `NotificationNumber`
- **Fields:** id, notification_number, description, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes notification_number
- **Serializer:** `NotificationNumberSerializer` (line 345 in `serializers/models.py`)
- **ViewSet:** `NotificationNumberViewSet` (in `views/views.py`)
- **API Endpoint:** `/notification-numbers`

### 16. ExchangeRate Model
- **File:** `backend/apps/core/models.py:709`
- **Class:** `ExchangeRateModel`
- **Fields:** id, date, usd, euro, pound_sterling, chinese_yuan, created_on, created_by, modified_on, modified_by, uid, version, is_tombstone, tombstone_expires_at
- **Key Method:** `compute_master_uid()` → hashes date
- **Serializer:** `ExchangeRateSerializer` (line 315 in `serializers/models.py`)
- **Admin:** `ExchangeRateAdmin` (line 66 in `admin.py`)
- **ViewSet:** Implied in `views/views.py`
- **API Endpoint:** `/exchange-rates`

---

## Sync Infrastructure Models (6)

### 1. MasterSyncServer Model
- **File:** `backend/apps/core/models.py:822`
- **Class:** `MasterSyncServer`
- **Purpose:** Tracks remote Master sync server configuration
- **Fields:** 
  - id
  - server_url: remote server location
  - api_key: authentication token
  - last_sync_time: timestamp of last successful sync
  - is_active: enable/disable sync
  - created_on, created_by, modified_on, modified_by
  - uid, version, is_tombstone, tombstone_expires_at
- **Key Methods:**
  - `validate_connection()`: Test connectivity
  - `get_sync_cursor()`: Retrieve cursor position
  - `register_events()`: Send outbox events to remote

### 2. MasterSyncOutbox Model
- **File:** `backend/apps/core/models.py:867`
- **Class:** `MasterSyncOutbox`
- **Purpose:** Queue of local changes to sync to remote
- **Fields:**
  - id
  - model_name: name of changed Master model
  - object_id: id of changed record
  - operation: 'create', 'update', 'delete'
  - content_type: Django ContentType
  - object_data: JSON snapshot of record before change
  - new_data: JSON of new values (for update)
  - is_synced: whether sent to remote
  - synced_at: timestamp when remote acknowledged
  - error_message: if sync failed
  - retry_count: attempt counter
  - created_on, created_by, modified_on, modified_by
  - uid, version, is_tombstone, tombstone_expires_at
- **Signal Trigger:** Created automatically on Master model save/delete via `signals_master_sync.py`
- **Lifecycle:** Created → registered with remote → marked synced → tombstoned after expiry

### 3. MasterSyncInbox Model
- **File:** `backend/apps/core/models.py:966`
- **Class:** `MasterSyncInbox`
- **Purpose:** Queue of remote changes to apply locally
- **Fields:**
  - id
  - model_name: name of Master model
  - object_id: id of record on remote
  - operation: 'create', 'update', 'delete'
  - server_id: which server sent this (FK to MasterSyncServer)
  - remote_uid: uid from remote server
  - remote_version: version from remote
  - object_data: JSON data to merge
  - is_applied: whether applied locally
  - applied_at: timestamp when applied
  - error_message: if apply failed
  - created_on, created_by, modified_on, modified_by
  - uid, version, is_tombstone, tombstone_expires_at
- **Processing:** Fetched from remote → validated → applied to local DB → marked applied

### 4. MasterConflict Model
- **File:** `backend/apps/core/models.py:1057`
- **Class:** `MasterConflict`
- **Purpose:** Records conflicts between local and remote Master versions
- **Fields:**
  - id
  - model_name: affected Master model
  - object_id: affected record
  - server_id: which server reported conflict (FK)
  - local_uid: uid of local version
  - local_version: version of local
  - remote_uid: uid of remote
  - remote_version: version of remote
  - conflict_type: 'version_mismatch', 'missing_remote', 'missing_local', 'data_divergence'
  - local_data: JSON snapshot of local
  - remote_data: JSON snapshot of remote
  - resolution_strategy: how to resolve ('take_local', 'take_remote', 'manual')
  - is_resolved: whether resolved
  - resolved_at: timestamp of resolution
  - created_on, created_by, modified_on, modified_by
  - uid, version, is_tombstone, tombstone_expires_at
- **Usage:** Management command `master_sync_reconcile` detects and resolves

### 5. MasterSyncCursor Model
- **File:** `backend/apps/core/models.py:1138`
- **Class:** `MasterSyncCursor`
- **Purpose:** Tracks sync progress (pagination/incremental sync)
- **Fields:**
  - id
  - server_id: which server (FK to MasterSyncServer)
  - model_name: which Master model
  - last_sync_cursor: opaque pagination token from remote
  - last_sync_time: timestamp of last fetch
  - record_count: total records synced from remote
  - created_on, created_by, modified_on, modified_by
- **Usage:** `MasterSyncFetchView` uses to resume incremental fetch from remote
- **Example:** On retry, fetch uses cursor to skip already-processed records

### 6. MasterMediaMetadata Model
- **File:** `backend/apps/core/models.py:1175`
- **Class:** `MasterMediaMetadata`
- **Purpose:** Metadata for files/images attached to Master records (e.g., company logo)
- **Fields:**
  - id
  - file_path: path to file
  - file_size: bytes
  - mime_type: content-type
  - checksum: hash for integrity verification
  - is_synced: whether uploaded to remote
  - created_on, created_by, modified_on, modified_by
- **Usage:** Sync media separately from structured Master data

---

## API Endpoints & ViewSets

### Master CRUD Endpoints

All Master models expose standard REST endpoints through their ViewSets:

| Model | ViewSet | Endpoint | Methods |
|-------|---------|----------|---------|
| Company | CompanyViewSet | `/companies` | GET, POST, PATCH, DELETE |
| Port | PortViewSet | `/ports` | GET, POST, PATCH, DELETE |
| ItemGroup | GroupViewSet | `/groups` | GET, POST, PATCH, DELETE |
| ItemName | ItemNameViewSet | `/item-names` | GET, POST, PATCH, DELETE |
| HSCode | HSCodeViewSet | `/hs-codes` | GET, POST, PATCH, DELETE |
| HeadSIONNorms | HeadSIONNormsViewSet | `/head-norms` | GET, POST, PATCH, DELETE |
| SionNormClass | SionNormClassViewSet | `/sion-classes` | GET, POST, PATCH, DELETE |
| ProductDescription | ProductDescriptionViewSet | `/product-descriptions` | GET, POST, PATCH, DELETE |
| UnitPrice | UnitPriceViewSet | `/unit-prices` | GET, POST, PATCH, DELETE |
| SchemeCode | SchemeCodeViewSet | `/scheme-codes` | GET, POST, PATCH, DELETE |
| NotificationNumber | NotificationNumberViewSet | `/notification-numbers` | GET, POST, PATCH, DELETE |
| ExchangeRate | ExchangeRateViewSet | `/exchange-rates` | GET, POST, PATCH, DELETE |

**File:** `backend/apps/core/urls.py`  
**Router Configuration:** Lines 13-28 (DefaultRouter)

### Master Sync-Specific Endpoints

**File:** `backend/apps/core/views/master_sync.py`

#### 1. MasterSyncEventsView
- **URL:** `/master-sync/events/` (POST)
- **Purpose:** Publish local Master changes to remote server
- **Class:** `MasterSyncEventsView` (line 23)
- **Handler:** `post()` (line 28)
- **Request:** List of Outbox records to register
- **Response:** ACK/NAK with error details
- **Authentication:** API key or token required

#### 2. MasterSyncFetchView
- **URL:** `/master-sync/fetch/` (GET)
- **Purpose:** Fetch incremental changes from remote
- **Class:** `MasterSyncFetchView` (line 138)
- **Handler:** `get()` (line 143)
- **Query Params:** 
  - `cursor`: pagination token (from last fetch)
  - `model_name`: optional filter
- **Response:** Paginated list of remote Inbox records with new cursor
- **Usage:** Called by `master_sync_fetch()` service to pull Inbox

#### 3. MasterSyncAckView
- **URL:** `/master-sync/ack/` (POST)
- **Purpose:** Acknowledge successful application of remote changes
- **Class:** `MasterSyncAckView` (line 206)
- **Handler:** `post()` (line 211)
- **Request:** List of Inbox IDs that were successfully applied
- **Response:** Confirmation or error
- **Idempotent:** Safe to retry

#### 4. MasterSyncCursorView
- **URL:** `/master-sync/cursor/` (GET)
- **Purpose:** Query current sync position
- **Class:** `MasterSyncCursorView` (line 258)
- **Handler:** `get()` (line 263)
- **Response:** List of MasterSyncCursor records per model and server
- **Usage:** Diagnostics; can reset cursors for resync

#### 5. MasterSyncHealthView
- **URL:** `/master-sync/health/` (GET)
- **Purpose:** Check sync system health
- **Class:** `MasterSyncHealthView` (line 295)
- **Handler:** `get()` (line 300)
- **Response:** JSON status of:
  - Server connectivity
  - Outbox queue size (pending syncs)
  - Inbox queue size (pending applies)
  - Conflict count
  - Last sync times
- **Usage:** Monitoring; dashboard display

### Generic Master ViewSet

**File:** `backend/apps/core/views/master_view.py:81`  
**Class:** `MasterViewSet`

- **Purpose:** Unified CRUD for all 16 Master models via dynamic routing
- **Methods:**
  - `list()`: list all records with filtering, pagination, search
  - `create()`: create new record (triggers Outbox event)
  - `retrieve()`: fetch single record
  - `update()`: full update (triggers Outbox event)
  - `partial_update()`: PATCH (triggers Outbox event)
  - `destroy()`: mark as tombstone (soft delete, triggers Outbox)
- **Key Features:**
  - Dynamic model selection via URL parameter or prefix
  - Permissions enforced per Master model
  - Delete protection (cannot hard delete published Masters)
  - Audit logging of all changes
- **Method:** `create_viewset()` (line 168) factory function to create ViewSet dynamically

---

## Serializers

**File:** `backend/apps/core/serializers/models.py`

Each Master model has a corresponding serializer for API marshalling:

| Model | Serializer | Line | Fields |
|-------|-----------|------|--------|
| Company | CompanySerializer | 24 | all model fields |
| Port | PortSerializer | 66 | all model fields |
| HSCode | HSCodeSerializer | 73 | all model fields |
| HeadSIONNorms | HeadSIONNormsSerializer | 80 | all model fields |
| SIONExport | SIONExportSerializer | 87 | all model fields |
| SIONImport | SIONImportSerializer | 95 | all model fields |
| SionNormNote | SionNormNoteSerializer | 110 | all model fields |
| SionNormCondition | SionNormConditionSerializer | 118 | all model fields |
| SionNormClass | SionNormClassNestedSerializer | 127 | nested with HeadSIONNorms |
| HSCodeDuty | HSCodeDutySerializer | 242 | duty rate + product |
| ProductDescription | ProductDescriptionSerializer | 249 | all model fields |
| UnitPrice | UnitPriceSerializer | 258 | all model fields |
| ItemName | ItemNameSerializer | 290 | all model fields |
| ExchangeRate | ExchangeRateSerializer | 315 | all model fields |
| SchemeCode | SchemeCodeSerializer | 337 | all model fields |
| NotificationNumber | NotificationNumberSerializer | 345 | all model fields |

**Key Features:**
- All include sync fields (`uid`, `version`, `is_tombstone`, `tombstone_expires_at`)
- Validation rules per field
- Custom representations for nested/related fields

---

## Services

Master Sync services are located in `backend/apps/core/services/`

### 1. MasterUIDService
- **File:** `master_uid_service.py:13`
- **Purpose:** Generate consistent, reproducible UIDs for Master records
- **Key Methods:**
  - `compute_uid(model, record)`: Hash identity fields to UID
  - `for_sion_norm_class(sion_norm_class)`: Special handler for SionNormClass
- **Algorithm:** SHA256 hash of identity fields (e.g., company_code for Company)
- **Usage:** Every Master on save computes its UID for sync identification
- **Idempotent:** Same record always generates same UID

### 2. MasterVersionService
- **File:** `master_version_service.py:8`
- **Purpose:** Manage version numbers for Master records
- **Key Methods:**
  - `next_version(record)`: Increment version on update
  - `reset_version(record)`: Reset on conflict resolution
- **Algorithm:** Simple integer increment
- **Usage:** Every update increments version; used to detect conflicts

### 3. MasterEventBuilder
- **File:** `master_event_builder.py:11`
- **Purpose:** Construct Outbox events from Master model changes
- **Key Methods:**
  - `build_create_event(model, record)`: Create Outbox for new record
  - `build_update_event(model, record, old_data, new_data)`: Create Outbox for update
  - `build_delete_event(model, record)`: Create Outbox for delete (tombstone)
- **Usage:** Called by signal handlers in `signals_master_sync.py`
- **Output:** MasterSyncOutbox record

### 4. MasterSyncReconciliation
- **File:** `master_sync_reconciliation.py:307`
- **Purpose:** Detect and resolve conflicts between local and remote Masters
- **Key Methods:**
  - `detect_conflicts()`: Compare local UIDs with remote, find divergence
  - `resolve_conflict(conflict)`: Apply resolution strategy
  - `validate_identity_fields()`: Ensure identity fields match across servers
- **Conflict Types Detected:**
  - Version mismatch (same UID, different versions)
  - Data divergence (uid/version match but field values differ)
  - Missing locally (remote has, local doesn't)
  - Missing remotely (local has, remote doesn't)
- **Resolution Strategies:**
  - `take_local`: Sync local version to remote
  - `take_remote`: Apply remote version locally
  - `manual`: Flag for human review
- **Usage:** `master_sync_reconcile` management command

### 5. MasterSyncRetry
- **File:** `master_sync_retry.py:118`
- **Purpose:** Handle failed sync attempts with exponential backoff
- **Key Classes:**
  - `OfflineRecoveryHandler`: Resume sync after connectivity restored
- **Key Methods:**
  - `retry_outbox(outbox_id)`: Retry sending event to remote
  - `resume_after_offline()`: Re-register all pending Outbox after outage
  - `apply_backoff(retry_count)`: Calculate delay (2^n seconds)
- **Max Retries:** 3 attempts before manual intervention
- **Usage:** Background task; triggered by failed sync attempts

### 6. MasterSyncUsage
- **File:** `master_sync_usage.py:40`
- **Purpose:** Query which Master models/records are in use in licenses/allotments
- **Key Functions:**
  - `is_transactional_model(model_class)`: True if model is imported into licenses
  - `get_usage_count(model, object_id)`: Count how many licenses reference this Master
  - `can_delete(model, object_id)`: True if not referenced anywhere
- **Usage:** Delete protection in MasterViewSet

### 7. MasterSyncSecurity
- **File:** `master_sync_security.py`
- **Purpose:** Enforce access control and audit logging for Master sync operations
- **Key Methods:**
  - `validate_api_key()`: Check MasterSyncServer credentials
  - `log_sync_event()`: Record all sync operations for audit
  - `check_permissions()`: Verify user can modify Master

### 8. MasterSyncGlobalUsage
- **File:** `master_sync_global_usage.py:4571`
- **Purpose:** Track global usage patterns across Master models
- **Key Methods:**
  - `get_all_usages()`: Aggregate usage across all transactional models
  - `get_model_dependencies()`: Show which Masters depend on which

---

## Signals & Handlers

**File:** `backend/apps/core/signals_master_sync.py`

All 16 Master models emit signals on save/delete. Handlers are registered in AppConfig.

### Signal Handlers by Master Model

| Model | Signal | Handler | Line | Outbox Operation |
|-------|--------|---------|------|-------------------|
| Company | post_save | auto-generated | — | create/update |
| Company | post_delete | auto-generated | — | delete |
| Port | post_save | auto-generated | — | create/update |
| Port | post_delete | auto-generated | — | delete |
| ItemName | post_save | auto-generated | — | create/update |
| ItemName | post_delete | auto-generated | — | delete |
| HSCode | post_save | auto-generated | — | create/update |
| HSCode | post_delete | auto-generated | — | delete |
| HeadSIONNorms | post_save | auto-generated | — | create/update |
| HeadSIONNorms | post_delete | auto-generated | — | delete |
| SionNormClass | post_save | `on_sionnormclass_save()` | 210 | create/update + cascade |
| SionNormClass | post_delete | `on_sionnormclass_delete()` | 321 | delete + cascade |
| All others | post_save/delete | auto-generated | — | create/update/delete |

### Key Behaviors

1. **Outbox Creation:** Every save/delete creates MasterSyncOutbox record
2. **Cascade Handling:** SionNormClass save/delete also affects related SionNormNote, SionNormCondition
3. **Version Increment:** Version field auto-incremented on update
4. **UID Computation:** UID recomputed on each save (should be stable)
5. **Audit Trail:** created_by, modified_by tracked from request user

### Test Coverage

**File:** `backend/apps/core/tests/test_master_sync_unit.py:79`  
**Test:** `test_outbox_created_on_model_create()` — Verifies Outbox record auto-created

---

## Management Commands

All in `backend/apps/core/management/commands/`

### Master Sync Operational Commands

#### 1. master_sync_status
- **File:** `master_sync_status.py:18`
- **Purpose:** Display real-time sync health and queue status
- **Methods:**
  - `handle()` (line 34): Main entry point
  - `_print_summary()` (line 53): Format output
  - `_print_model_health()` (line 88): Per-model details
  - `_print_conflicts()` (line 111): Show unresolved conflicts
  - `_print_server_status()` (line 128): Remote server connectivity
- **Usage:** `python manage.py master_sync_status`
- **Output:** YAML/JSON of:
  - Outbox queue length and oldest pending
  - Inbox queue length and failures
  - Conflict count
  - Per-model health scores
  - Remote server last contact time

#### 2. master_sync_reconcile
- **File:** `master_sync_reconcile.py:23`
- **Purpose:** Detect and auto-resolve sync conflicts
- **Key Methods:**
  - `handle()` (line 44): Orchestrate reconciliation
  - `_handle_duplicate()` (line 95): Merge duplicate UIDs
  - `_check_tombstone_expiry()` (line 134): Clean old deletes
  - `_print_summary()` (line 163): Report resolution counts
- **Options:**
  - `--model`: Target specific Master (default: all)
  - `--resolve-strategy`: 'take_local', 'take_remote', 'manual'
  - `--dry-run`: Preview changes without applying
- **Usage:** `python manage.py master_sync_reconcile --model Company --resolve-strategy take_local`
- **Output:** 
  - Conflicts detected and fixed count
  - Tombstones expired count
  - Duplicates merged count

#### 3. audit_masters
- **File:** `audit_masters.py:62`
- **Purpose:** Data quality report on Master records
- **Key Methods:**
  - `_serialize_value()` (line 62): JSON export
  - `_record_to_dict()` (line 75): Record formatter
  - `_hash_record()` (line 107): Compute checksum
  - `handle()` (line 121): Execute audit
- **Options:**
  - `--model`: Specific Master to audit
  - `--output`: CSV/JSON file to write
- **Checks:**
  - Null identity fields
  - Duplicate UIDs
  - Version consistency
  - Tombstone validity
- **Usage:** `python manage.py audit_masters --model Company --output audit.csv`

#### 4. check_master_quality
- **File:** `check_master_quality.py:70`
- **Purpose:** Structural integrity checks on Master data
- **Key Methods:**
  - `_blank_keys()` (line 90): Find records missing identity fields
  - `_orphaned_fks()` (line 105): Detect broken references
  - `_duplicate_keys()` (line 124): Find duplicates
  - `handle()` (line 140): Execute checks
- **Checks:**
  - Blank identity fields
  - Orphaned foreign keys
  - Duplicate UIDs
  - Missing sync metadata
- **Output:** Counts of issues found + quarantine plan

#### 5. diff_masters
- **File:** `diff_masters.py:27`
- **Purpose:** Compare Master data between local and remote server
- **Key Methods:**
  - `handle()` (line 35): Execute comparison
- **Options:**
  - `--model`: Specific Master
  - `--server-id`: Which remote server
- **Output:** Lists additions, deletions, and modifications

#### 6. reconcile_masters
- **File:** `reconcile_masters.py:83`
- **Purpose:** Merge duplicate Master records (legacy)
- **Key Methods:**
  - `_parse_modified_on()` (line 65): Parse timestamps
  - `_reconcile_model()` (line 155): Per-model merging
  - `handle()` (line 83): Orchestrate
- **Usage:** `python manage.py reconcile_masters --model Company`

#### 7. merge_masters
- **File:** `merge_masters.py:55`
- **Purpose:** Manually merge two Master records
- **Key Methods:**
  - `_strip_unsafe()` (line 44): Sanitize data
  - `handle()` (line 63): Execute merge
- **Usage:** `python manage.py merge_masters Company --source-id 123 --target-id 456`

#### 8. auto_import_masters
- **File:** `auto_import_masters.py:92`
- **Purpose:** Bulk import Master data from CSV/Excel
- **Key Methods:**
  - `get_unique_keys()` (line 56): Extract identity fields
  - `find_existing()` (line 73): Match existing records
  - `handle()` (line 110): Execute import
  - `_wrapped_handle()` (line 296): Transactional wrapper
  - `_DryRunRollback` (line 308): Undo on dry-run
- **Options:**
  - `--file`: Input CSV/Excel path
  - `--model`: Target Master model
  - `--dry-run`: Preview without saving
  - `--merge`: Merge with existing if found
- **Output:** Import summary (created, updated, skipped, errors)

#### 9. sync_from_ge_server
- **File:** `sync_from_ge_server.py:28`
- **Purpose:** One-time fetch from Government of Inida servers
- **Key Methods:**
  - `handle()`: Execute fetch
- **Options:**
  - `--model`: Specific Master (e.g., 'ExchangeRate')
  - `--url`: Override server URL
- **Usage:** `python manage.py sync_from_ge_server --model ExchangeRate`

### Other Utility Commands

- **sync_database_schema** (line 25): Align DB schema with Django models
- **fetch_exchange_rates** (line 18): Fetch latest currency rates
- **fetch_detail_bisc** (line 16): Fetch BISC classification details
- **fetch_detail_conf** (line 17): Fetch customs configuration

---

## Migrations

**Directory:** `backend/apps/core/migrations/`

All sync-related migrations (in order of application):

| # | File | Purpose | Models |
|---|------|---------|--------|
| 0005 | add_uid_to_keyless_masters.py | Add UID field to all Masters | All 16 |
| 0006 | backfill_master_uids.py | Compute initial UIDs | All 16 |
| 0010 | sync_e132_display_order.py | Add display_order to E132 | — |
| 0012 | **create_sync_models.py** | **Create Outbox, Inbox, Conflict, Cursor, MediaMetadata, SyncServer** | **Sync 6** |
| 0013 | add_tombstone_fields_to_masters.py | Add is_tombstone, tombstone_expires_at | All 16 |
| 0015 | add_mastersync_cursor.py | Expand MasterSyncCursor fields | MasterSyncCursor |
| 0016 | add_master_media_metadata.py | Create MediaMetadata model | MasterMediaMetadata |
| 0017 | **add_master_sync_identity_fields.py** | **Add identity_fields JSON to all Masters** | **All 16** |
| 0018 | backfill_master_uids.py | Recompute UIDs with identity fields | All 16 |
| 0019 | update_master_sync_server.py | Extend MasterSyncServer fields | MasterSyncServer |
| 0020 | **add_missing_sync_fields.py** | **Final: Add version, uid, sync metadata to all** | **All 16** |

**Key Schema Changes:**

1. **Master Models gain fields:**
   - `uid` (CharField, max_length=64, unique per model, indexed) — identity hash
   - `version` (IntegerField, default=1) — conflict detection
   - `is_tombstone` (BooleanField, default=False) — soft delete marker
   - `tombstone_expires_at` (DateTimeField, null=True) — cleanup schedule
   - `identity_fields` (JSONField, default=dict) — field names used for UID

2. **New Tables:**
   - `core_mastersyncserver` — remote server config
   - `core_mastersyncoutbox` — local changes queue
   - `core_mastersyncinbox` — remote changes queue
   - `core_masterconflict` — conflict records
   - `core_mastersynccursor` — sync progress tracking
   - `core_mastersynmediamet` — file attachments metadata

**Migration Order Dependency:**
```
0005 → 0006 → 0010 → 0012 → 0013 → 0015 → 0016 → 0017 → 0018 → 0019 → 0020
```

---

## Tests

**Directory:** `backend/apps/core/tests/`

### Master Sync Unit Tests
- **File:** `test_master_sync_unit.py`
- **Key Tests:**
  - `test_outbox_created_on_model_create()` (line 79): Verify signal handler creates Outbox
  - UID computation tests
  - Version increment tests
  - Conflict detection tests
  - Tombstone expiry tests
- **Coverage:** Signal handlers, UID service, version service, Outbox auto-creation

### Master Sync Integration Tests
- **File:** `test_master_sync_integration.py`
- **Key Tests:**
  - End-to-end sync flow (local → Outbox → remote → Inbox → apply)
  - Conflict resolution workflows
  - Retry and offline recovery
  - Pagination and cursor handling
  - Media file sync
- **Coverage:** Full sync pipeline with mocked remote server

### Master Data Integrity Tests
- **File:** `test_masterdata_delete_protection.py:192`
- **Test:** `TestMasterViewSetApiDeleteProtection` — Verify delete protection works
  - Cannot hard-delete published Masters
  - Tombstone soft-delete only
- **Coverage:** MasterViewSet delete protection

### Master Reconciliation Tests
- **File:** `test_reconcile_masters.py:120`
- **Tests:**
  - `test_keyless_model_flagged()` — Flag Masters missing identity fields
  - `test_model_missing_on_one_server()` — Detect remote-only records
- **Coverage:** Reconciliation logic

### Materialized View Tests
- **File:** `test_materialized_views.py:29`
- **Test:** `cursor()` — Pagination cursor functionality
- **Coverage:** CursorPagination class

---

## Frontend Components

**Directory:** `frontend/src/pages/masters/`

### Core Components

#### MasterForm.tsx
- **Purpose:** Create/edit form for all 16 Master models
- **File:** `MasterForm.tsx`
- **Size:** 56KB (largest component)
- **Key Features:**
  - Dynamic field rendering based on model
  - Nested field arrays (e.g., SionNormClass → SionNormNote/Condition)
  - Validation with error messages
  - Auto-save / draft mode
  - Audit trail display (created_on, modified_by)
  - Conflict detection UI (version mismatch warning)
  - Custom form field mapping per model (entitySections.ts)
- **Key Props:**
  - `modelName`: Which Master to edit
  - `recordId`: Record to edit (optional, create mode if absent)
  - `onSubmit`: Save handler
  - `onCancel`: Close handler

#### MasterList.tsx
- **Purpose:** List, filter, search, and bulk actions on Master records
- **File:** `MasterList.tsx`
- **Size:** 99KB (largest component)
- **Key Features:**
  - Pagination with cursor or offset
  - Multi-column sortable table
  - Full-text search
  - Advanced filtering (by status, date range, user)
  - Bulk select and delete/archive
  - Column visibility toggle
  - Export to CSV/Excel
  - Delete confirmation with usage warning
  - Inline edit for some fields
  - Sync status indicator (pending, synced, error)
- **Key Props:**
  - `modelName`: Which Master to list
  - `filters`: Pre-apply filters
  - `onEdit`: Navigate to form
  - `onDelete`: Delete handler

#### NestedFieldArray.tsx
- **Purpose:** Dynamic nested field management (e.g., SionNormClass with multiple SionNormNote)
- **File:** `NestedFieldArray.tsx`
- **Size:** 39KB
- **Key Features:**
  - Add/remove nested fields
  - Field mapping per nested entity
  - Validation of nested data
  - Copy/duplicate nested records
  - Sortable drag-and-drop
- **Usage:** In MasterForm for composite Masters

### Supporting Components

#### GenericMasterCards.tsx
- **Purpose:** Card-based display of Master records (alternative to table)
- **File:** `GenericMasterCards.tsx`
- **Features:** Grid view, quick actions, inline edit
- **Usage:** Dashboard/overview pages

#### TradeMetaBadges.tsx
- **Purpose:** Display sync status, audit, and version badges
- **File:** `TradeMetaBadges.tsx` (line 3)
- **Features:**
  - Sync pending badge (red)
  - Synced badge (green)
  - Version mismatch warning (orange)
  - Last modified by user
  - Audit info popup

### Hooks

#### useMasterFormCalculations.ts
- **Purpose:** Derived field calculations (e.g., exchange rate conversions)
- **File:** `hooks/useMasterFormCalculations.ts`
- **Size:** 15KB
- **Key Methods:**
  - `calculateDerivedFields()`: Compute dependent fields on change
  - `validateCalculations()`: Check formula results
- **Usage:** In form submission

#### useMasterFormData.ts
- **Purpose:** Load and prepare Master data for form
- **File:** `hooks/useMasterFormData.ts`
- **Size:** 8KB
- **Key Methods:**
  - `loadMasterData()`: Fetch from API
  - `populateForm()`: Bind to React Hook Form
  - `onFieldChange()`: Refresh dependent fields
- **Usage:** On component mount

#### useMasterFormSubmit.ts
- **Purpose:** Handle form submission, conflict detection, retry logic
- **File:** `hooks/useMasterFormSubmit.ts`
- **Size:** 30KB
- **Key Methods:**
  - `submitMaster()`: POST/PATCH to API
  - `detectConflict()`: Compare local version with API response
  - `resolveConflict()`: User chooses strategy (take_local, take_remote, merge)
  - `retrySubmit()`: Exponential backoff on 409/507
- **Usage:** On form submit button click

### Configuration Files

#### masterFormHelpers.ts
- **File:** `masterFormHelpers.ts`
- **Purpose:** Form field definitions, validation rules, masks
- **Exports:**
  - `getFieldsForModel(modelName)`: List of fields for form
  - `getValidationSchema(modelName)`: Yup schema for validation
  - `getFieldProps(modelName, fieldName)`: Props for field component
- **Usage:** Form configuration

#### masterListConfig.ts
- **File:** `masterListConfig.ts`
- **Purpose:** Column definitions, sorting, filtering metadata for list view
- **Exports:**
  - `getColumnsForModel(modelName)`: Table column config
  - `getDefaultSort(modelName)`: Initial sort order
  - `getFilterOptions(modelName)`: Dropdown options for filters
- **Usage:** MasterList.tsx table setup

#### masterDisplayFormatters.ts
- **File:** `masterDisplayFormatters.ts`
- **Purpose:** Format Master data for display (dates, numbers, status)
- **Exports:**
  - `formatField(modelName, fieldName, value)`: Apply formatter
  - `formatDate(value)`: ISO → locale date
  - `formatCurrency(value, currency)`: With separators
  - `formatStatus(status)`: 'active' → 'Active'
- **Usage:** In list and form views

### Master-Specific Tables

#### LicensesTable.tsx
- **Purpose:** Display licenses with Master data (Company, Port, ItemName, HSCode)
- **File:** `tables/LicensesTable.tsx`
- **Size:** 66KB
- **Features:** Read-only; clickable Master names open detail modals

#### AllotmentsTable.tsx
- **Purpose:** Display allotments with Master data
- **File:** `tables/AllotmentsTable.tsx`
- **Size:** 16KB

#### BalanceTab.tsx
- **Purpose:** Balance report filtered by Master (Company, Port, ItemName)
- **File:** `tables/BalanceTab.tsx`
- **Size:** 27KB

#### LedgerTab.tsx
- **Purpose:** Ledger detail report with Master references
- **File:** `tables/LedgerTab.tsx`
- **Size:** 88KB

### API Service

#### masterApi.js
- **File:** `frontend/src/services/api/masterApi.js`
- **Purpose:** API client for Master CRUD and sync operations
- **Key Methods:**
  - `listMasters(modelName, params)`: GET /companies, /ports, etc.
  - `getMaster(modelName, id)`: GET /companies/123
  - `createMaster(modelName, data)`: POST with Outbox auto-creation
  - `updateMaster(modelName, id, data)`: PATCH with conflict detection
  - `deleteMaster(modelName, id)`: DELETE (soft-delete)
  - `checkSyncStatus(modelName, id)`: GET /master-sync/health
  - `fetchSyncQueue()`: GET /master-sync/status
  - `resolveConflict(conflictId, strategy)`: POST conflict resolution
- **Error Handling:**
  - 409 Conflict → Prompt user for resolution strategy
  - 423 Locked → Retry with exponential backoff
  - 503 Service Unavailable → Queue for offline retry

### Modals & Dialogs

#### BoeMergeModal.tsx
- **Purpose:** Merge duplicate Bill of Entry records (related to Masters)
- **File:** `BoeMergeModal.tsx`

#### LicenseParseModal.tsx / BoeParsePanel.tsx
- **Purpose:** Parse and validate Master data from uploaded files
- **Files:** `LicenseParsePanel.tsx`, `BoeParsePanel.tsx`

#### LinkTradeModal.tsx
- **Purpose:** Link Masters to trade transactions
- **File:** `LinkTradeModal.tsx`

### Tests

#### MasterForm.smoke.test.tsx
- **File:** `MasterForm.smoke.test.tsx`
- **Tests:** Render test for all Master models

#### MasterList.smoke.test.tsx
- **File:** `MasterList.smoke.test.tsx`
- **Tests:** List rendering and pagination

#### masterFormHelpers.test.ts
- **File:** `masterFormHelpers.test.ts`
- **Tests:** Field validation, schema generation

#### masterListConfig.test.ts
- **File:** `masterListConfig.test.ts`
- **Tests:** Column config, sorting metadata

#### masterDisplayFormatters.test.ts
- **File:** `masterDisplayFormatters.test.ts`
- **Tests:** Format functions (date, currency, etc.)

---

## Dependencies & Cross-References

### Master Model Dependencies

```
Company → (no dependencies)
Port → (no dependencies)
ItemGroup → (no dependencies)
ItemName → (FK: ItemGroup)
HSCode → (no dependencies)
HeadSIONNorms → (no dependencies)
SionNormClass → (FK: HeadSIONNorms)
SIONExport → (derived from SionNormClass)
SIONImport → (derived from SionNormClass)
SionNormNote → (FK: SionNormClass)
SionNormCondition → (FK: SionNormClass)
ProductDescription → (FK: HSCode)
UnitPrice → (no dependencies)
SchemeCode → (no dependencies)
NotificationNumber → (no dependencies)
ExchangeRate → (no dependencies)
```

### Master ↔ License/Allotment Links

These Masters are **transactional** (imported into licenses via MasterSyncUsage check):

- **Company** ← `License.company_code` (FK)
- **Port** ← `License.port_code` (FK)
- **ItemName** ← `License.item_name` (FK)
- **HSCode** ← `BillOfEntry.hs_code` (FK)
- **UnitPrice** ← `BillOfEntry.unit_price_code` (FK)
- **SchemeCode** ← `License.scheme_code` (FK)
- **NotificationNumber** ← `License.notification_number` (FK)
- **ExchangeRate** ← `License.exchange_rate_date` (FK, lookup by date)

These are **reference-only** (viewable but not imported):

- **HeadSIONNorms, SionNormClass, SIONExport, SIONImport** (informational only)
- **SionNormNote, SionNormCondition** (display details only)
- **ProductDescription** (lookup/info only)
- **ItemGroup** (grouping/classification only)

### Sync Flow Dependencies

```
Master Model Save/Delete
    ↓
Signal (post_save/delete) in signals_master_sync.py
    ↓
MasterEventBuilder.build_*_event()
    ↓
MasterSyncOutbox record created
    ↓
Background task: register_events_to_server()
    ↓
POST /master-sync/events/ → Remote Server
    ↓
Remote ACK or error
    ↓
Retry queue if failed (master_sync_retry.py)
    ↓
Mark as synced or flag conflict
```

### Service Import Graph

```
views/master_view.py (MasterViewSet)
    ↓
services/master_sync_usage.py (can_delete, is_transactional)
services/master_uid_service.py (compute_uid)
services/master_version_service.py (next_version)

signals_master_sync.py (signal handlers)
    ↓
services/master_event_builder.py (build events)
    ↓
models.MasterSyncOutbox (create records)

views/master_sync.py (sync endpoints)
    ↓
services/master_sync_reconciliation.py (detect conflicts)
services/master_sync_retry.py (handle failures)
    ↓
models.MasterSyncInbox, MasterConflict (store results)

management/commands/master_sync_reconcile.py
    ↓
services/master_sync_reconciliation.py
services/master_sync_security.py (audit)
```

### Frontend Data Flow

```
MasterList.tsx
    ↓
masterApi.listMasters() → GET /companies (etc.)
    ↓
masterListConfig.ts (column defs)
masterDisplayFormatters.ts (format values)
    ↓
Display table

MasterForm.tsx (on edit)
    ↓
useMasterFormData() → masterApi.getMaster()
    ↓
masterFormHelpers.ts (field defs)
useMasterFormCalculations.ts (derive fields)
    ↓
Display form

MasterForm.tsx (on submit)
    ↓
useMasterFormSubmit() → masterApi.updateMaster()
    ↓
409 Conflict response → Detect via useMasterFormSubmit
    ↓
Conflict modal → User chooses strategy
    ↓
Retry with resolution → API success
```

---

## Key Architectural Decisions

### 1. Soft Delete with Tombstone
- **Why:** Preserve sync audit trail; never hard-delete Masters after publication
- **Implementation:** `is_tombstone=True`, `tombstone_expires_at` for cleanup
- **Signal:** When tombstone flag set, MasterSyncOutbox records DELETE event

### 2. UID-Based Sync Identity
- **Why:** Allow records to move/merge without breaking sync (not reliant on DB primary key)
- **Algorithm:** Stable hash of identity fields (e.g., company_code for Company)
- **Idempotent:** Same record always → same UID (deterministic)
- **Conflict Detection:** Same UID + different versions = conflict

### 3. Version Incrementing
- **Why:** Detect stale writes in multi-writer scenarios
- **Implementation:** Simple integer counter, incremented on every update
- **Conflict Resolution:** Compare versions; higher version wins (with data merge)

### 4. Outbox/Inbox Queue Pattern
- **Why:** Decouple local changes from remote sync; handle offline scenarios
- **Outbox:** Local changes buffered; synced async to remote
- **Inbox:** Remote changes fetched async; applied locally at user's pace
- **Benefit:** Works offline; survives server outages; supports conflict resolution

### 5. Cursor-Based Pagination
- **Why:** Efficient incremental sync; handle concurrent updates on remote
- **Implementation:** Opaque token returned by `/master-sync/fetch`; reuse on next call
- **Benefit:** O(1) fetch time regardless of total records; stable snapshots

### 6. Transactional vs. Reference Masters
- **Transactional:** Imported into licenses; cannot delete if in use (checked by `MasterSyncUsage`)
- **Reference:** Informational only; can delete anytime
- **Example:** Company is transactional (License.company_code FK); ItemGroup is reference

---

## Performance Considerations

### Indexing Strategy

All Masters have indices on:
- `uid` (unique within model, for sync identity)
- `version` (for conflict detection queries)
- `is_tombstone` (to filter out deleted records)
- `created_on`, `modified_on` (for audit queries)
- Identity fields (company_code, port_code, etc.) for lookups

### Query Optimization

- **List endpoints:** Use `select_related()` for FK joins
- **Sync queries:** Index on `is_synced=False` for Outbox polling
- **Conflict detection:** Index on `(uid, version)` pairs in both Outbox and Inbox

### Caching

- Master list cached in Redis (60s TTL)
- Invalidated on any create/update/delete
- Cursor pagination avoids full-table scans

---

## Security & Compliance

### Access Control

- **Permissions:** `can_add_master`, `can_change_master`, `can_delete_master` per model
- **Audit Logging:** All changes logged to activity_logs with user, timestamp, before/after data
- **API Key Auth:** MasterSyncServer requires valid `api_key` for remote connections

### Data Validation

- **Field-level:** Django validators (not null, length, format)
- **Model-level:** `clean()` methods in models.py
- **API-level:** Serializer validation + DRF permissions

### Compliance

- **GDPR:** Tombstone records auto-expire (configurable, default 90 days)
- **Audit Trail:** Immutable activity_logs table
- **Data Integrity:** Foreign key constraints; cascade rules defined

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Master Models | 16 |
| Sync Infrastructure Models | 6 |
| API Endpoints (REST) | 12+ (all Master CRUD) |
| Sync-Specific Endpoints | 5 |
| Services | 8 |
| Management Commands | 18 |
| Migrations (sync-related) | 8 |
| Signal Handlers | 2 (SionNormClass) + auto-generated (16) |
| Frontend Components | 15+ |
| Frontend Hooks | 3 |
| Test Files | 3 (unit, integration, integrity) |

---

## Next Steps for Rebuild

To rebuild this system from scratch, follow this order:

1. **Models** (backend/apps/core/models.py)
   - Define 16 Master models with UIDs and version fields
   - Define 6 Sync infrastructure models (Outbox, Inbox, Conflict, Cursor, etc.)
   - Apply migrations

2. **Services** (backend/apps/core/services/)
   - Implement UID service (deterministic hashing)
   - Implement version service (increment logic)
   - Implement event builder (Outbox record creation)

3. **Signals** (backend/apps/core/signals_master_sync.py)
   - Register post_save/post_delete handlers for all Masters
   - Auto-create Outbox records in handlers

4. **API** (backend/apps/core/urls.py, views/)
   - Define ViewSets for all Masters
   - Define sync-specific views (Events, Fetch, Ack, Cursor, Health)
   - Apply permissions and throttling

5. **Management Commands**
   - Implement status, reconcile, audit, quality check commands
   - Implement import/export/merge commands

6. **Tests**
   - Unit tests for signal handlers, UID service
   - Integration tests for full sync flow
   - Delete protection tests

7. **Frontend** (frontend/src/pages/masters/)
   - Implement MasterForm with dynamic field rendering
   - Implement MasterList with pagination and filtering
   - Implement conflict resolution UI
   - Integrate with API client

8. **Deployment**
   - Configure MasterSyncServer endpoint
   - Enable background job queue for Outbox registration
   - Set up monitoring (master_sync_health endpoint)
   - Configure tombstone expiry cleanup task
