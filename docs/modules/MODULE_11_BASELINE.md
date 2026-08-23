# MODULE 11 BASELINE: ADMINISTRATION & SETTINGS

**Date:** 2026-08-10  
**Status:** Read-only forensic audit  
**Scope:** User & role management, master data administration, system monitoring

---

## 1. SCOPE

### Module Purpose
Administration & Settings provides:
- User account lifecycle management (create, read, update, deactivate, delete)
- Role-based access control (16 roles mapped to Django Groups)
- Master data CRUD (17 entities: companies, ports, HS codes, exchange rates, etc.)
- Activity audit logging (all authenticated API requests + explicit login/logout)
- System health monitoring (MDS sync status, throttle metrics)

### Business Entities
1. **User** — authentication subject with profile (username, email, name, avatar)
2. **Group** — role container (Django's built-in model, used for permission grouping)
3. **Master Data Records** (17 types):
   - Company, Port, HSCode, ExchangeRate, PurchaseStatus
   - HeadSIONNorms, SIONClass, SIONExportItem, SIONImportItem
   - SionNormNote, SionNormCondition, ProductDescription, UnitPrice
   - ItemName, SchemeCode, NotificationNumber, TransferLetter
4. **ActivityLog** — audit trail of all actions (login, view, create, update, delete, download, upload, export, search)

### Key Workflows
1. **User Creation** → validation (weak password rejection) → save to DB → optional role assignment
2. **User Modification** → edit username/email/name/status/roles → save → no role sync if roles not provided
3. **Password Reset** → validation (Django password rules) → hash update → no token-based flow
4. **Master Data CRUD** → permission gate (superuser write, any-authenticated read for most) → optionally route through MDS when enabled
5. **Activity Logging** → middleware captures every authenticated API request → async write to DB

### Integration Points
- **Auth System:** Uses Django's built-in authentication + custom User model
- **Permissions:** Role-based gates on every module (License, Allotment, BOE, Trade, etc.)
- **Master Data Service (MDS):** Optional bidirectional sync for 17 master-data models
- **Audit Trail:** ActivityLogMiddleware hooks all API requests
- **Frontend:** React Settings page (Users & Roles tab + MDS status card)

---

## 2. FINANCIAL CALCULATIONS

**No financial calculations occur in this module.**

- Master data (exchange rates, HS codes, prices) are *reference* values, not calculated.
- ActivityLog records actions but does not compute balances, debits, credits.
- User/role management is administrative, not transactional.

---

## 3. DATA MODELS

### User Model
**File:** `backend/apps/accounts/models.py::User`

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `username` | CharField(150) | UNIQUE, NOT NULL | Django USERNAME_FIELD |
| `email` | EmailField(255) | UNIQUE, NULL | Can be blank; normalized on save |
| `first_name` | CharField(30) | BLANK | Optional profile field |
| `last_name` | CharField(150) | BLANK | Optional profile field |
| `password` | (via AbstractBaseUser) | Hashed | bcrypt/PBKDF2 depending on settings |
| `is_active` | BooleanField | default=True | Controls login eligibility |
| `is_staff` | BooleanField | default=False | Django admin access flag (unused in this app) |
| `is_superuser` | BooleanField | default=False | Global admin (unrestricted) |
| `avatar` | ImageField | NULL, BLANK | Stored in `avatars/` directory; PNG/JPG/JPEG only |
| `date_joined` | DateTimeField | auto_now_add | Read-only audit timestamp |
| `groups` (M2M) | → Group | blank=True | Role assignments; custom related_name |
| `user_permissions` (M2M) | → Permission | blank=True | Granular Django permissions (unused) |

**Indexes:** username, email (implicit in UNIQUE)

**Cascades:**
- User deleted → avatar file deleted (signal `delete_avatar_on_user_delete`)
- User avatar changed → old file deleted (signal `delete_old_avatar_on_change`)
- User deleted → ActivityLog.user = NULL (ON DELETE SET_NULL)

---

### ActivityLog Model
**File:** `backend/apps/core/models.py::ActivityLog`

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `user` | ForeignKey(User) | NULL, BLANK | SET_NULL when user deleted |
| `username` | CharField(150) | db_index | Denormalized for performance |
| `action` | CharField(20, choices) | db_index | LOGIN, LOGOUT, VIEW, CREATE, UPDATE, DELETE, DOWNLOAD, UPLOAD, EXPORT, SEARCH |
| `module` | CharField(60) | db_index, BLANK | e.g., "license", "allotment", "auth" |
| `resource_id` | CharField(60) | BLANK | e.g., license number, BOE ID |
| `description` | CharField(500) | BLANK | Human-readable summary |
| `endpoint` | CharField(500) | BLANK | Request path (e.g., `/api/auth/users/42/`) |
| `method` | CharField(10) | BLANK | HTTP verb (GET, POST, PUT, DELETE) |
| `ip_address` | GenericIPAddressField | NULL, BLANK | v4 or v6 |
| `user_agent` | CharField(400) | BLANK | Browser/client identity |
| `status_code` | PositiveSmallIntegerField | NULL, BLANK | HTTP response code |
| `extra` | JSONField | default={}, BLANK | Ad-hoc metadata |
| `timestamp` | DateTimeField | auto_now_add, db_index | UTC, read-only |

**Indexes:** user, username, action, module, timestamp

**Write Sources:**
- ActivityLogMiddleware (async thread for all authenticated API requests)
- Explicit log_login() / log_logout() helpers (sync from auth views)

---

### Master Data Models (Generic)
**File:** `backend/apps/core/models.py`

17 master-data models share a common pattern:
- **created_by** / **modified_by** (ForeignKey(User), SET_NULL, BLANK)
- **created_on** / **modified_on** (DateTimeField, auto_now_add / auto_now)
- **uid** (CharField, unique) — for MDS sync convergence (ADR-001 Decision 6)
- Model-specific fields (e.g., CompanyModel: name, address, PAN, GST, bank details)

**MDS Sync:** When `MDS_ENABLED=true`, these models are also mirrored locally from a central Master Data Service. Writes go through the API cutover (`apps.core.mds_write.save_through_mds`), not Django ORM directly.

---

## 4. BUSINESS RULES

### Authentication & Authorization

| Rule | Enforcement | Impact |
|------|------------|--------|
| Password policy | `validate_password()` via Django's default validators | MIN_LENGTH=8, no simple numbers, no user-attribute overlap |
| Superuser can do anything | BaseRolePermission checks `is_superuser` first | Bypasses all role checks |
| USER_MANAGER role required for user management | UserManagementViewSet.permission_classes=[UserManagementPermission] | Non-superusers cannot list/edit/delete users without the role |
| Username immutable | Form disabled on edit; serializer doesn't accept `username` updates | Preserves identity across password resets |
| Email unique within active users | Model constraint + serializer normalization | Blank email → None (avoids unique collision) |
| Only one active exchange rate | ExchangeRateModel.get_active_rate() | Latest by date |

### Role Definitions
**File:** `backend/apps/accounts/views/user_management.py::ROLE_CODES`

16 defined roles (Django Groups):
1. **USER_MANAGER** — Manage users & roles, view audit log
2. **LICENSE_MANAGER** — License read/write, related calculations
3. **LICENSE_VIEWER** — License read-only
4. **ALLOTMENT_MANAGER** — Allotment CUD
5. **ALLOTMENT_VIEWER** — Allotment read-only
6. **BOE_MANAGER** — Bill of Entry CUD, invoice reconciliation
7. **BOE_VIEWER** — Bill of Entry read-only
8. **TRADE_MANAGER** — Trade/invoice CUD
9. **TRADE_VIEWER** — Trade/invoice read-only
10. **INCENTIVE_LICENSE_MANAGER** — Incentive license CUD
11. **INCENTIVE_LICENSE_VIEWER** — Incentive license read-only
12. **REPORT_VIEWER** — Report viewing (read-only dashboard)
13. **TL_GENERATE** — Transfer letter generation
14. **LEDGER_MANAGER** — Ledger file upload/management
15. **ACCOUNT_ACCESS** — Accounts team: BOE read + invoice update
16. **LEDGER_VIEWER** (implied) — Ledger read-only (not explicitly in ROLE_CODES but referenced in permissions)

**Permission Granularity:**
- Each module (license, allotment, trade, BOE, etc.) has a permission class defining read/write role requirements.
- Company data is additionally filtered by role (sensitive fields like PAN/GST hidden from non-financial roles).
- Activity log visible only to USER_MANAGER or superuser.

### Master Data Admin Safety (MDS Cutover)

| Scenario | Behavior |
|----------|----------|
| MDS_ENABLED=false (default) | Masters writable via Django ORM; admin is fully functional |
| MDS_ENABLED=true | Masters read-only via Django admin; all writes must go through API (`/api/masters/*/`) which routes to MDS first |
| MDS cutover failure (503) | Local write rolled back; error returned to client |
| Model not in MDS registry | Local-only behavior (unchanged) |

---

## 5. DEPENDENCIES

### Modules This Module Depends On
- **core.models** — ActivityLog, CompanyModel, PortModel, HSCodeModel, etc.
- **core.middleware.ActivityLogMiddleware** — Auto-logging
- **core.permissions.MasterDataPermission** — Generic master-data gate
- **django.contrib.auth** — User, Group, Permission (built-in)
- **rest_framework** — ViewSet, Serializer, APIView

### Modules Depending on This Module
- **License, Allotment, BOE, Trade, Incentive** — All use `accounts.permissions` role checks
- **Core** — MDS sync uses User.created_by/modified_by
- **All API endpoints** — All check UserManagementPermission or module-specific role permissions

### API Contracts

**Users Endpoint** (`/api/auth/users/`)
- GET: List users (USER_MANAGER or superuser)
- POST: Create user (USER_MANAGER or superuser, password validation required)
- PUT/PATCH: Update user (USER_MANAGER or superuser; username immutable)
- DELETE: Delete user (USER_MANAGER or superuser)
- Subaction: `POST /api/auth/users/{id}/reset-password/` — password reset

**Available Roles** (`/api/auth/users/available-roles/`)
- GET: Returns array of 16 role codes (no permission check)

**Activity Log** (`/api/masters/activity-logs/`)
- GET: List activities (USER_MANAGER or superuser; max 1000 rows, default 100)
- Filters: username, action, module, date_from, date_to, search

**Masters** (`/api/masters/{entity}/`)
- All entities (companies, ports, HS codes, etc.) follow MasterViewSet pattern
- GET: Read (authenticated)
- POST/PUT/DELETE: Write (superuser only, or MDS if enabled)

**MDS Status** (`/api/mds/status/`)
- GET: Mirror sync status (USER_MANAGER or superuser)
- Returns: enabled flag, base URL, model counts, last sync times, health flag

---

## 6. TESTS EXISTING

### Test Locations
**File:** `backend/apps/accounts/tests.py`

**Test Classes:**
1. **AccountsAPITestCase** (7 tests)
   - `test_get_profile_me` — Auth token flow
   - `test_logout_rejects_invalid_refresh_token` — Token validation
   - `test_user_management_denied_without_role` — Permission gate
   - `test_user_management_create_rejects_weak_password` — Password validation
   - `test_user_management_reset_password_rejects_weak_password` — Password validation on reset
   - `test_account_avatar_cleanup_signals_are_registered` — Signal registration

2. **MigrateAuthCommandTests** (2 tests)
   - `test_migrate_users_creates_missing_user_with_username` — User migration from legacy schema
   - `test_redact_dsn_masks_url_and_keyword_passwords` — DSN sanitization

3. **RepairUserFKConstraintsCommandTests** (1 test)
   - `test_quote_identifier_path_handles_schema_qualified_table_names` — Identifier quoting

**Coverage Estimate:** ~30% of user/role/auth code; gaps include:
- Email uniqueness constraint
- Avatar upload/delete flow (signals only)
- Role sync edge cases (partial updates, empty role list)
- Master data permission gates (CompanyPermission, LicenseBalanceLedgerPermission)
- ActivityLog query filters (complex date range, search combos)
- MDS sync status endpoint (mocked in codebase; no live test)

---

## 7. LEGACY CODE

### Unused Exports & Deprecated Patterns

| Item | Location | Status | Notes |
|------|----------|--------|-------|
| `accounts.tasks` | backend/apps/accounts/tasks.py | Empty | Placeholder for async tasks; no queue configured |
| `UserSerializer.is_staff` | serializers.py | Used but read-only | Prevents frontend-side privilege escalation |
| Django admin (UserAdmin) | accounts/admin.py | Available but not primary | API is the authoritative write path |
| `user_permissions` M2M | User model | Unused | Django permissions not employed; roles (groups) are the gate |
| `is_staff` field | User model | Unused | Vestigial from Django; `is_superuser` is the real gate |

### Legacy Services
- **accounts.services.create_user** — Thin wrapper around ORM; used only by RegisterSerializer
- **accounts.management.commands.migrate_auth** — One-time user migration from legacy schema (run once)
- **accounts.management.commands.check_user_roles** — Utility for ops; not called by app
- **accounts.management.commands.repair_user_fk_constraints** — Repair FK after failed migrations; manual tool

---

## 8. RISK REGISTER

### Financial Accuracy Risks
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Master data inconsistency (local vs. MDS) | Medium | High | MDS sync with 15-min freshness check; converges via uid (ADR-001) |
| Stale exchange rates used in calculations | Low | Medium | ExchangeRateModel.get_active_rate() always fetches latest; flagged in status UI |
| Wrong user assigned to audit trail | Low | Medium | User deleted → ActivityLog.user=NULL (never reused FK); username denormalized |

### Data Integrity Risks
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| User deleted mid-transaction | Low | Low | Foreign keys SET_NULL; no transactional guarantees needed for audit |
| Master record deleted while referenced | Low | High | ProtectedError raised; user must reassign first; surfaces as DRF 400 |
| Avatar file orphaned on failed save | Low | Low | Django's FileField auto-cleanup on model delete; pre_save signal handles replacement |
| Email collision (null vs. blank) | Low | Low | Serializer normalizes empty email → None; avoids unique constraint clash |

### Concurrency Risks
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Race: role assignment and immediate login | Low | Low | Role check is query-time (no cached state); latest groups always consulted |
| Race: password reset mid-login attempt | Low | Low | Password hash is atomic update; old hash rejected immediately |
| Concurrent ActivityLog writes | Medium | Low | Django ORM handles concurrent INSERTs; no index contention |
| MDS sync race with local write | Medium | High | MDS is write authority when enabled; cutover gates local ORM path (save_through_mds) |

### Security Risks
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Privilege escalation (non-superuser → superuser) | Very Low | Critical | is_superuser read-only in non-superuser serializers; Django enforces at DB constraint level |
| Password exposure in logs/audit | Low | High | Password never stored in ActivityLog; only user action recorded |
| Weak password accepted | Low | Medium | validate_password() enforced on create/reset; Django default validators |
| Company sensitive fields visible to unauth users | Low | High | CompanyPermission restricts read to business roles; CompanySerializer.to_representation filters sensitive fields per role |
| ActivityLog tampering | Very Low | High | Append-only model; no update/delete allowed; only superuser can bulk-delete |
| JWT token hijacking | Low | High | Covered by auth system; not Module 11 scope |

### Performance Risks
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ActivityLog table unbounded growth | Medium | High | No automatic cleanup; ops must set retention policy or archive |
| MDS status check slow (17 model syncs) | Low | Medium | Single query for all states; read-only (no lock contention) |
| User.groups prefetch missing on list | Low | Medium | UserManagementViewSet uses prefetch_related('groups'); serializer calls get_role_codes() (cached per-request) |
| Avatar upload without size limit | Low | Medium | FileExtensionValidator on upload; no file-size validation (Django default is ~2.5GB) |

---

## 9. SCHEMA & CONSTRAINTS SUMMARY

### Key Tables
| Table | Rows (typical) | Growth | Indexed Columns | Notes |
|-------|-------|--------|---|---|
| accounts_user | 10–100 | Slow (manual creation) | username, email | Custom User model |
| core_activitylog | 100K–1M+ | Fast (1 per request) | user_id, username, action, module, timestamp | Append-only audit trail |
| django_contrib_auth_group | 16 | None | name | Role definitions (seeded) |
| core_companymodel | 500–2K | Slow (MDS sync) | uid | Master data; company names/banking |
| core_exchangeratemodel | 100 | Slow (daily) | date | Active rate lookup; indexed on date |
| core_portmodel | 50–100 | Very slow | uid | Customs ports; static |

### Constraints Summary
- **User.username** UNIQUE, NOT NULL
- **User.email** UNIQUE, NULL (allows multiple null when users have no email)
- **ActivityLog.action** CHOICE (10 options enforced at DB level)
- **Master models** ProtectedError on FK delete (prevent orphaning)
- **Exchange rate** Implicit ordering by date (no DB constraint; handled in app)

---

## END OF BASELINE

**Prepared for:** Module 11 Autonomous Implementation Phase  
**Next Steps:** Code review, test gaps analysis, financial-calculation audit (no-op for this module)
