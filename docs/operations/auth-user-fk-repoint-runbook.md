# Runbook: re-point legacy `auth_user` foreign keys (accounts migration 0006)

**Migration:** `accounts.0006_repoint_legacy_user_fks`
**Hotfix branch:** `hotfix/auth-user-fk-repoint`
**Symptom fixed:** `POST /api/allotments/` returns HTTP 500 (`IntegrityError`, `created_by_id` not present in `auth_user`) for any user whose id is not also an id in the legacy `auth_user` table.

This runbook is preparation only. Nothing in it has been run against production. Production facts below are **assumptions taken from a local copy of the production-like dump** (`~/Developer/db-backups/lmanagement-before-auth-user-fk-fix-20261028-155937.dump`). Every assumption must be checked in the preflight section before anything changes.

---

## 1. What the migration does

- Finds every foreign key whose referenced table is `auth_user`, using `pg_constraint`.
- Excludes four tables (see §6). Everything else is repointed.
- Fails closed before any DDL if any of these hold:
  - a referencing row holds an id that does not exist in `accounts_user`;
  - a legacy constraint is multi-column, or has an `ON UPDATE` action other than `NO ACTION`, or an `ON DELETE` action other than `NO ACTION` / `SET NULL`;
  - `ON DELETE SET NULL` would apply to a `NOT NULL` column.
- Otherwise, per affected column: drops every legacy FK on that column and adds exactly one `FOREIGN KEY (col) REFERENCES accounts_user(id) [ON DELETE SET NULL] DEFERRABLE INITIALLY DEFERRED NOT VALID`, then `VALIDATE CONSTRAINT`.
- `ON DELETE SET NULL` is kept only where a legacy duplicate already had it (four `bill_of_entry` columns). All other columns get `NO ACTION`.
- Runs in one transaction. A failure rolls everything back.
- `SET LOCAL lock_timeout = '10s'`: if a lock cannot be acquired within 10 seconds, the migration fails and changes nothing.
- Reverse is a **no-op**. Reversing does not restore `auth_user` references, because those would be wrong for every user id that is not in `auth_user`. Recovery is by database restore (§9), not by reversing.
- Fresh databases already reference `accounts_user`, so the migration is a no-op there.

### Locks

- `DROP CONSTRAINT` takes `ACCESS EXCLUSIVE` on the referencing table.
- `ADD CONSTRAINT` takes `SHARE ROW EXCLUSIVE` on the referencing table and on `accounts_user`.
- `VALIDATE CONSTRAINT` takes `SHARE UPDATE EXCLUSIVE` on the referencing table. It does not block normal reads or writes.
- Because the migration is one transaction, the `ACCESS EXCLUSIVE` locks on all affected tables are held **until commit**. Reads and writes to those tables (about 35 tables, including `allotment_allotmentmodel`, `core_*` masters, `bill_of_entry_*`, `trade_licensetrade`) will block for the whole migration.
- The duration is not known yet. Measure it on a restored copy of production (§4). Do not guess.

---

## 2. Expected production state (assumptions to verify)

Taken from the local copy of the dump. Production must match **exactly**, or stop (§8).

### 2.1 Legacy constraints that reference `auth_user` (43 total)

Migrated (39 constraints on 35 columns):

```
allotment_allotmentitems.created_by_id
allotment_allotmentitems.modified_by_id
allotment_allotmentmodel.created_by_id
allotment_allotmentmodel.modified_by_id
bill_of_entry_billofentrymodel.created_by_id      (2 constraints: one ON DELETE SET NULL, one plain)
bill_of_entry_billofentrymodel.modified_by_id     (2 constraints)
bill_of_entry_rowdetails.created_by_id            (2 constraints)
bill_of_entry_rowdetails.modified_by_id           (2 constraints)
core_companymodel.created_by_id / modified_by_id
core_hscodemodel.created_by_id / modified_by_id
core_itemgroupmodel.created_by_id / modified_by_id
core_itemheadmodel.created_by_id / modified_by_id
core_itemnamemodel.created_by_id / modified_by_id
core_portmodel.created_by_id / modified_by_id
core_productdescriptionmodel.created_by_id / modified_by_id
core_sionnormclassmodel.created_by_id / modified_by_id
core_sionnormcondition.created_by_id / modified_by_id
core_sionnormnote.created_by_id / modified_by_id
core_transferlettermodel.created_by_id / modified_by_id
core_unitpricemodel.created_by_id / modified_by_id
django_admin_log.user_id                          (NOT NULL)
trade_licensetrade.created_by_id / modified_by_id
```

Excluded (4 constraints, untouched by design):

| Table | Why it stays on `auth_user` |
|---|---|
| `auth_user_groups` | Join table for the legacy `auth.User` model. Not the app's user. |
| `auth_user_user_permissions` | Join table for the legacy `auth.User` model. |
| `ebrc_fileuploaddetails` | Legacy table. No model in this codebase. |
| `shipping_bill_fileuploaddetails` | Legacy table. No model in this codebase. |

### 2.2 Other facts that must hold

- `django_migrations` has `accounts.0005_revokedaccesstoken` applied and `accounts.0006_repoint_legacy_user_fks` **not** applied.
- Every `*_fk_acct` constraint reports `convalidated = true` after migration.
- The migration only touches `accounts` and the listed tables; no other app's migrations are pending. Check with `python manage.py showmigrations --plan | grep "\[ \]"` and expect **no output**.

---

## 3. Preflight (read-only; run on production before any change)

Run these with a read-only role where possible. None of them change data. Replace `$PROD_DB_*` with the production connection values from the server's environment; do not paste credentials into tickets.

### 3.1 Inventory of legacy FKs

```sql
SELECT c.conrelid::regclass AS referencing_table,
       a.attname AS column_name,
       c.conname,
       c.confdeltype AS on_delete,   -- a = NO ACTION, n = SET NULL
       c.confupdtype AS on_update,
       c.condeferrable,
       c.condeferred,
       c.convalidated,
       a.attnotnull AS not_null,
       pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
WHERE c.contype = 'f' AND c.confrelid = 'auth_user'::regclass
ORDER BY 1, 2, 3;
```

**Compare with §2.1.** Stop if:
- any table or column appears that is not listed;
- any listed column is missing;
- any `on_update` is not `a`, any `on_delete` is not `a` or `n`, or any constraint is multi-column;
- `on_delete = n` on a `not_null = t` column.

### 3.2 Orphan counts (read-only)

```sql
SELECT t.tbl, t.col,
       (xpath('/row/c/text()', query_to_xml(format(
          'SELECT count(*) AS c FROM %s WHERE %I IS NOT NULL AND %I NOT IN (SELECT id FROM accounts_user)',
          t.tbl, t.col, t.col), false, true, '')))[1]::text::int AS orphans
FROM (
  SELECT c.conrelid::regclass::text AS tbl, a.attname::text AS col
  FROM pg_constraint c
  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
  WHERE c.contype = 'f' AND c.confrelid = 'auth_user'::regclass
) t
WHERE t.tbl NOT IN ('auth_user_groups','auth_user_user_permissions',
                    'ebrc_fileuploaddetails','shipping_bill_fileuploaddetails')
ORDER BY orphans DESC, tbl, col;
```

**Stop if any `orphans` value is greater than 0.** The migration would refuse, and the rows must be reconciled by a person first:

- Decide, per table, whether the orphaned id should be remapped to a real `accounts_user` id, or set to `NULL` (audit attribution lost). This is a business decision, not a technical one.
- Record the affected rows (`SELECT id, created_by_id ... WHERE ...`) and keep the list with the change ticket.
- Apply the agreed fix as a separate, reviewed change, then rerun 3.2 until every value is 0.

The local copy showed zero orphans in every column sampled, including `core_portmodel` and `allotment_allotmentmodel`. Production is **not** verified.

### 3.3 Migration state

```bash
cd backend
python manage.py showmigrations accounts          # 0005 [X], 0006 [ ]
python manage.py showmigrations --plan | grep "\[ \]"   # expect no output
python manage.py makemigrations --check --dry-run       # expect "No changes detected"
```

### 3.4 Size and lock exposure

```sql
SELECT c.relname, pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size, c.reltuples::bigint AS est_rows
FROM pg_class c
WHERE c.relname IN (
  'allotment_allotmentitems','allotment_allotmentmodel','bill_of_entry_billofentrymodel',
  'bill_of_entry_rowdetails','core_companymodel','core_hscodemodel','core_itemgroupmodel',
  'core_itemheadmodel','core_itemnamemodel','core_portmodel','core_productdescriptionmodel',
  'core_sionnormclassmodel','core_sionnormcondition','core_sionnormnote','core_transferlettermodel',
  'core_unitpricemodel','django_admin_log','trade_licensetrade','accounts_user')
ORDER BY pg_total_relation_size(c.oid) DESC;
```

Record the sizes. These drive the window estimate (§5).

### 3.5 Long-running transactions

```sql
SELECT pid, state, now() - xact_start AS xact_age, left(query, 120) AS query
FROM pg_stat_activity
WHERE xact_start IS NOT NULL AND datname = current_database()
ORDER BY xact_start;
```

Any transaction older than a few minutes on an affected table will make `lock_timeout` fire. Wait for it to finish, or schedule around it.

---

## 4. Backup and rehearsal

### 4.1 Full backup (custom format, before any change)

```bash
export PGPASSWORD="$PROD_DB_PASS"
TS=$(date +%Y%m%d-%H%M%S)
pg_dump -h "$PROD_DB_HOST" -p "${PROD_DB_PORT:-5432}" -U "$PROD_DB_USER" \
  -Fc -Z9 --no-owner --no-privileges \
  -f "$HOME/db-backups/lmanagement-prod-pre-0006-$TS.dump" "$PROD_DB_NAME"
unset PGPASSWORD
```

Store a second copy off the server.

### 4.2 Verify the backup

```bash
pg_restore --list "$HOME/db-backups/lmanagement-prod-pre-0006-$TS.dump" > /tmp/toc.txt
grep -c "TABLE DATA" /tmp/toc.txt     # sanity: should be > 0
sha256sum "$HOME/db-backups/lmanagement-prod-pre-0006-$TS.dump" > "$HOME/db-backups/lmanagement-prod-pre-0006-$TS.dump.sha256"
```

Do not proceed unless `pg_restore --list` succeeds and the checksum file exists.

### 4.3 Rehearsal on a restored copy (required)

1. Restore the production backup into a **new** database, never over an existing one:

   ```bash
   createdb -h localhost -U <role> lmanagement_rehearsal
   pg_restore -h localhost -U <role> --no-owner --no-privileges -d lmanagement_rehearsal <dump>
   ```

2. Run preflight §3.1 to §3.3 against it. Results must match production.
3. Apply the migration and time it:

   ```bash
   cd backend
   time DB_NAME=lmanagement_rehearsal python manage.py migrate accounts
   ```

4. Run the post-verification queries (§7) against `lmanagement_rehearsal`.
5. Drop the rehearsal database when finished.

The rehearsal duration is the basis for the maintenance window. Do not use the local copy's timing; it is much smaller than production.

---

## 5. Maintenance window

- Schedule outside business hours, with the app stopped for the migration. Stopping the app avoids lock waits and failures from concurrent writes, and avoids new sessions holding locks.
- Window length = rehearsal migration time × 3, plus time for backup, verification and smoke tests. Use at least 30 minutes unless the rehearsal shows much less.
- Have the restore procedure (§9) ready and rehearsed before starting.

---

## 6. Deployment

**Do not run `scripts/deployment/auto-deploy.sh` for this change.** It runs `python manage.py migrate --no-input` on the server with no database backup and no preflight. Use the manual steps below, or only run the script after §3 and §4 have passed and the backup exists.

```bash
# 1. Stop application workers (gunicorn / celery per the server's service setup)

# 2. Confirm the backup from §4.1 and §4.2 exists and has a valid checksum.

# 3. Deploy the code (merged hotfix on master)
cd /path/to/license-manager
git fetch origin
git checkout master && git pull --ff-only origin master
cd backend
../venv/bin/pip install -r requirements.txt     # or the server's venv path

# 4. Re-run preflight §3.1 to §3.3 immediately before migrating. Stop if anything differs.

# 5. Apply only the accounts migration
python manage.py migrate accounts 0006_repoint_legacy_user_fks

# 6. Start application workers
```

If the migration reports an error, it has changed nothing (single transaction). Read the message, fix the cause, and rerun step 4 before retrying. Do not edit the migration file on the server.

---

## 7. Post-migration verification (read-only)

Each query should return the stated result.

```sql
-- 7.1 Only the four excluded constraints still reference auth_user (expect 4 rows)
SELECT conrelid::regclass, conname
FROM pg_constraint WHERE contype = 'f' AND confrelid = 'auth_user'::regclass
ORDER BY 1;

-- 7.2 Exactly one FK per migrated column (expect 0 rows)
SELECT c.conrelid::regclass, a.attname, count(*)
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
WHERE c.contype = 'f' AND c.confrelid = 'accounts_user'::regclass
  AND a.attname IN ('created_by_id','modified_by_id','user_id')
GROUP BY 1, 2 HAVING count(*) <> 1;

-- 7.3 Every new constraint is validated (expect 0)
SELECT count(*) FROM pg_constraint WHERE conname LIKE '%fk_acct' AND NOT convalidated;

-- 7.4 SET NULL kept only on the four bill_of_entry columns (expect 4 rows)
SELECT conrelid::regclass, conname FROM pg_constraint
WHERE contype = 'f' AND confrelid = 'accounts_user'::regclass AND confdeltype = 'n'
ORDER BY 1;

-- 7.5 No orphans left (rerun §3.2; expect every orphans value = 0)
```

Application checks:

- `python manage.py makemigrations --check --dry-run` → "No changes detected".
- Log in as a real user whose id is **not** in `auth_user`, then create an allotment through the UI or the API. Expect HTTP 201. Delete the test row afterwards, using the normal delete path, and record its id.
- Check the backend log for `IntegrityError` or `violates foreign key constraint` for the next 30 minutes.

---

## 8. Stop conditions

Stop and do not migrate if any of the following is true:

- Preflight §3.1 differs from §2.1 in any way.
- Any orphan count in §3.2 is greater than 0.
- Any legacy constraint has an unexpected action (§3.1).
- The rehearsal migration fails, or takes longer than the window allows.
- `pg_restore --list` fails, or the checksum is missing.
- A long-running transaction is holding a lock on an affected table (§3.5) and cannot be cleared.
- `showmigrations --plan` shows other pending migrations that have not been reviewed.

---

## 9. Failure, rollback and recovery

- **Migration fails with `lock timeout`:** the transaction rolled back. Nothing changed. Wait for the blocking transaction to end (§3.5), then retry in the window.
- **Migration fails with `Legacy auth_user FK repoint stopped before changing anything`:** nothing changed. Read the message and follow §3.2 or §8.
- **Post-migration problem that needs the old schema back:** the migration has no usable reverse (see §1). Restore from the backup taken in §4.1:
  1. Stop application workers.
  2. Restore into a new database first, verify it, then switch the application's `DB_NAME`. Restoring over the live database with `pg_restore --clean` loses every write made since the backup. Only do that after explicit approval.
  3. Restart the application.
- **Reverting the code alone does not restore the old behaviour.** The legacy constraints are what cause the 500, so reverting only the code leaves the bug in place.

---

## 10. Known differences and open items

- **Local development database:** this copy was migrated by an earlier revision of 0006 that did not keep `ON DELETE SET NULL` on the four `bill_of_entry` columns. Those four columns are `NO ACTION` locally, and `SET NULL` in the migration as reviewed. Re-running the migration does not correct them, because the migration is already recorded as applied. Align them manually if needed before relying on the local schema for delete-behaviour testing.
- **Production:** none of §2 or §3 has been run against production. The orphan counts and the constraint set there are unknown until preflight.
- **Lock duration:** unknown until measured on a production-sized rehearsal (§4.3).
- **Deletion behaviour:** the migration keeps the legacy `ON DELETE` action. Django's ORM also enforces `on_delete=SET_NULL` for `AuditModel` audit columns and `CASCADE` for `django_admin_log.user`, so raw-SQL deletes of `accounts_user` rows are the only path where the database action matters. Confirm with the team that raw-SQL user deletes are not used.
