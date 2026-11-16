# Database Safety — identification, guardrails, forbidden operations

Policy source: `.claude/rules/safety.md` (enforced by `.claude/hooks/guard_bash.py`).
This document records how DB targets are identified and what modernization work may do.

## 1. Environments

| Env | Identification | Verified by Claude? |
|---|---|---|
| Local dev | `backend/.env` → Django settings resolve `HOST=localhost PORT=5432 NAME=lmanagement`; server PG 18.7 Homebrew, `inet_server_addr()=::1`, `pg_is_in_recovery()=false` | **Yes** (2026-11-16, via `django.conf.settings`; secret values not read) |
| Local restore clone | `lmanagement_restore_verify_20261116` @ localhost | Yes (created 2026-11-16) |
| CI | `.github/workflows/ci.yml` service container Postgres 16, ephemeral | Config only |
| Test runs | Django `test_<name>` DB, or `TEST_DB_NAME` (settings.py:215) | n/a |
| Staging / production | Server env files (see `docs/operations/TRACTOR_SERVER_*.md`, nginx confs) | **No.** Not identified; must not be connected to |

`settings.py:201-210`: credentials come only from env vars (`DB_NAME/DB_USER/DB_HOST/DB_PORT`, password).
Local auth works without a password (trust), so pg tools need no secret.

## 2. Pre-flight before ANY write

1. Resolve the target through Django settings (never `cat .env`) and assert `HOST in {localhost, 127.0.0.1, ::1}`.
2. Query `select current_database(), inet_server_addr(), pg_is_in_recovery()` and record the output.
3. Make sure a verified dump less than 24h old exists (`docs/modernization/BACKUP_AND_RECOVERY.md`).
4. Rehearse on the restore clone first.
5. Read-only inspection runs inside `BEGIN READ ONLY` / `SET TRANSACTION READ ONLY`. All discovery queries in this phase did.

If the target cannot be positively identified: **do not write.**

## 3. Forbidden without explicit, in-conversation human authorization

`DROP DATABASE/TABLE/SCHEMA`, `TRUNCATE`, `manage.py flush`, `migrate --fake`, `RemoveField` /
`DeleteModel` / column narrowing, PK changes or regeneration, bulk deletes or updates of historical
records, rewriting migration history (squash or delete of applied migrations), any production
connection, and dropping legacy tables (see §4).

## 4. Legacy tables — DO NOT DROP

These tables exist in the DB, but **no app in the repo owns them**. They hold real data and have
live FKs into current tables:

| Table group | Rows | FKs |
|---|---|---|
| `eScrap_companylistmodel`, `_port`, `eScrap_companylicensemodel` | 663 / 29,239 / 715 | `eScrap_companylistmodel_port → core_portmodel` (blocks deleting ports) |
| `ebrc_shippingdetails`, `ebrc_fileuploaddetails`, `ebrc_ebrcdetails`, `ebrc_exchangeratemodel` | 27,524 / 138 / 0 / 0 | `ebrc_fileuploaddetails → auth_user` |
| `shipping_bill_*` (3 tables) | 268 / 2 / 0 | `shipping_bill_fileuploaddetails → auth_user` |
| `license_movement_licensemovementmodel` | 0 | migration row present, app removed |
| `auth_user` (+ groups/perms) | 2 | referenced by the legacy ebrc/shipping_bill tables; current user model is `accounts_user` (re-pointed in commit `f20cf325`) |

Any change here is an owner decision: archive to a separate schema, export, or keep.

## 5. Credentials

- Never print, copy or commit `.env*`, `backend/.env_dgft`, keys or tokens. `deploy-secrets.env.example` is a template only.
- Backups are gitignored. Pre-existing `~/lm_backups/remote_db_backup_*.sql` may contain production data and should be stored encrypted or off-repo-tree. Owner decision.
- `core.authentication.JWTAuthenticationFromQueryParam` accepts JWT in the query string, so tokens can leak into logs. Flagged for `security-auditor` (see PROJECT_ARCHITECTURE.md).
