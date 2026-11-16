# Backup and Recovery — License Manager database

Status as of **2026-11-16** (Phase 1 discovery). Applies to the **local dev DB**; the
production procedure at the end is a proposal and has not been run.

## 1. Verified backup (local)

| Item | Value |
|---|---|
| Source DB | `lmanagement` @ `localhost:5432` (PostgreSQL 18.7 Homebrew, `inet_server_addr()=::1`, not in recovery) |
| Size | 290 MB on disk, 119 public tables, 743,007 rows, 3 materialized views |
| Full dump | `~/lm_backups/local_lmanagement_pre_modernization_20261116.dump` (pg_dump `-Fc -Z 6`, 14,102,055 bytes) |
| SHA-256 | `0902d8517a7ffbf010f2e08685c394e31f00f07d537444188be19cce38399bec` (stored in `.dump.sha256`) |
| Schema-only | `~/lm_backups/local_lmanagement_schema_20261116.sql` (431,825 bytes) |
| Balance baseline | `~/lm_backups/balance_baseline_20261116.csv`: per-licence output of every `LicenseBalanceCalculator` term (2,185 licences) |
| Location | `~/lm_backups/`, outside the repo (moved 2026-11-16). The repo `backups/` is gitignored (`.gitignore:52`) but `db-tools.sh` still writes there. **Never commit dumps.** |

### Verification performed (a successful `pg_dump` was not treated as proof)

1. `pg_restore --list`: 119 `TABLE DATA` entries and 1,031 constraint/index/matview entries.
2. Full restore into a **new** scratch DB, `lmanagement_restore_verify_20261116`, using `--no-owner --exit-on-error`.
3. Source vs. restored comparison, all of which matched:
   - 119 / 119 tables.
   - 743,007 / 743,007 rows.
   - **Per-table content hash** (`sum(hashtext(row::text))`): 0 mismatches.
   - Constraints by type: c 88, f 253, n 884, p 119, u 91.
   - Indexes: 772. Matviews: 3.

**Result: RECOVERABLE.** The scratch DB was kept as a production-like clone for migration
rehearsal (Phase 6). Drop it only with explicit approval.

### Pre-existing files (not created by this work)

`~/lm_backups/remote_db_backup_20261115_*.sql`: pg_dump custom-format files (despite `.sql`), written by `scripts/database/db-tools.sh`; two pairs of identical size
(6.6 MB and 14.0 MB). Their origin is "remote". They have **not** been opened or verified, and they may
contain production data. The owner should confirm their provenance and retention.

## 2. Restore procedure (local)

```bash
shasum -a 256 -c ~/lm_backups/<file>.dump.sha256           # 1. integrity
createdb -h localhost -U lmanagement <new_db_name>     # 2. NEW db, never over the live one
pg_restore -h localhost -U lmanagement -d <new_db_name> --no-owner --exit-on-error ~/lm_backups/<file>.dump
# 3. verify counts/hashes against the source (script pattern in DATA_INTEGRITY_REPORT.md §1)
# 4. only then repoint DB_NAME in backend/.env (human action) — never restore over `lmanagement` in place
```

Matviews are restored populated. After a restore, run `REFRESH MATERIALIZED VIEW` only through
the app's own refresh path (`apps/license` materialized_views helpers).

## 3. Rollback plan for future migrations

- Take a fresh verified dump **immediately before** each migration batch, using the same three-step verification as above.
- Rehearse every migration on a restored clone first. Compare row counts, PKs, FK validity and the balance baseline CSV before and after.
- Rollback order: (a) `manage.py migrate <app> <previous>` if the migration is reversible and was rehearsed; (b) otherwise restore the pre-migration dump into a new DB and repoint. Never drop the live DB.

## 4. Production (proposal — NOT executed, needs owner)

- Identify the production host and DB from server env files on the server (Claude has not read them and must not).
- Use `pg_dump -Fc` on the server, then copy the dump off-host and record its checksum. Do a monthly restore drill into a scratch DB with the same count/hash comparison.
- Consider WAL archiving / PITR (pgBackRest or managed snapshots) if RPO < 24h is required. Owner decision.
- Any production command needs explicit human approval in-session (`.claude/rules/safety.md`).
