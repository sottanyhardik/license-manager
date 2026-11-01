# Live schema and recovery evidence protocol

**Proposed V1 verification protocol.** No live, shared, or production database
was connected to for this audit, and this document records no live result. It
defines the evidence that a named, authorized operator must collect later in
an isolated production-like rehearsal environment. It is intentionally
read-only until a separately approved migration rehearsal begins.

This protocol implements the gaps in [current schema](current-schema.md),
[data integrity](data-integrity.md), [rollback and recovery](rollback-and-recovery.md)
and [backup and recovery](../07-quality-and-operations/backup-and-recovery.md).

## Authorization and safety preconditions

Before any command is run, record the environment identifier, database
owner/operator, approved change ticket, source commit, target migration
head, time window, and a redaction location for outputs. Never include DSNs,
passwords, bearer tokens, customer records, document contents, or raw PII in
`docs/v1/`.

| Allowed in evidence collection | Prohibited without a separate approved rehearsal plan |
| --- | --- |
| Read-only catalog/metadata queries; `showmigrations`; `pg_dump --schema-only`; `EXPLAIN (FORMAT JSON)` without `ANALYZE`; aggregated count/checksum reports; backup inventory inspection | `migrate`, `makemigrations`, repair/merge/backfill commands, `VACUUM FULL`, index creation/drop, DDL/DML, restore into a shared environment, disabling constraints/triggers, granting new privileges, copying production media or data into a developer machine |

Use a role restricted to the target database and read-only operations for the
schema/data phase. Stop immediately if a command requests a password in an
unapproved channel, emits sensitive rows, targets an unknown host, or cannot
be shown to be non-mutating. Read-only catalog queries still need an approved
environment because schema/table names and counts can be sensitive.

## Evidence run order

### E0 — manifest and scope

Record a redacted manifest before querying:

- application commit and container/image identifiers;
- PostgreSQL major version, database encoding/collation/time zone and extension
  list;
- Django settings profile name (not environment variables or secrets);
- migration-app list and expected migration heads from the checked-out source;
- the bounded entity scope: licence/header/items/plan/replan, allotment,
  BOE/rows, trade/documents, reconciliation allocations/logs, ledger jobs and
  sync events; and
- explicit exclusions, including any archive/replica or third-party database.

**Exit:** a reviewer can determine exactly which isolated database was
inspected and what it is intended to represent.

### E1 — migration graph and physical-schema capture

Collect Django migration status without applying it, then export schema only.
The authorized operator may use the following *templates*, with environment
names supplied outside this repository:

```sh
python backend/manage.py showmigrations --plan
pg_dump --schema-only --no-owner --no-privileges "$APPROVED_DATABASE" > schema.sql
```

For each in-scope relation, capture catalog metadata as aggregates/DDL, not
row data. The following SQL is a review template; replace the array with the
approved physical relation names discovered from `pg_catalog` first.

```sql
SELECT c.relname AS table_name,
       a.attname AS column_name,
       pg_catalog.format_type(a.atttypid, a.atttypmod) AS type,
       a.attnotnull,
       pg_get_expr(ad.adbin, ad.adrelid) AS default_expression
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
LEFT JOIN pg_attrdef ad ON ad.adrelid = c.oid AND ad.adnum = a.attnum
WHERE n.nspname = 'public'
  AND c.relkind IN ('r', 'p')
ORDER BY c.relname, a.attnum;

SELECT conrelid::regclass AS table_name, conname, contype,
       pg_get_constraintdef(oid, true) AS definition,
       convalidated
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
ORDER BY 1, conname;

SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
```

Compare this capture to model/migration declarations, especially the declared
identities: BOE number/date and BOE-row tuple, licence-item serial, package
job/item, sync inbox/delivery, allocation current/supersession, plan/replan
and ownership side tables. Classify each difference as expected historical
compatibility, stale migration, operator-installed object, or unexplained.

**Exit:** every in-scope model has a physical-table mapping, column/FK/check/
unique/index disposition, and an applied-migration state. Source declaration
alone does not satisfy this exit.

### E2 — data-quality and integrity aggregates

Run only aggregated, parameterized checks after the physical names and
business owner are confirmed. Do not substitute display fields for the
declared identities. Examples:

```sql
-- Duplicate-key template: use only after the physical table/columns are confirmed.
SELECT key_1, key_2, COUNT(*) AS duplicate_count
FROM approved_relation
GROUP BY key_1, key_2
HAVING COUNT(*) > 1;

-- FK/orphan template: use the actual FK and target key from E1.
SELECT COUNT(*) AS orphan_count
FROM child_relation c
LEFT JOIN parent_relation p ON p.id = c.parent_id
WHERE c.parent_id IS NOT NULL AND p.id IS NULL;

-- Nullability/backfill template: report count only, never row identities.
SELECT COUNT(*) AS null_count
FROM approved_relation
WHERE proposed_required_column IS NULL;
```

The evidence report must separately record counts for: BOE and row identity
duplicates; licence-item serial duplicates/nulls; active allocation capacity
and supersession-chain anomalies; current replan request duplicates; package
idempotency/key anomalies; sync source/event and peer/event duplicates;
one-to-one licence side-table orphans; and document/file database references
whose storage existence can be checked through an approved, redacted
inventory.

For balance-sensitive records, compare aggregate and selected golden-fixture
outputs under both named engines. Do not use a cleanup query to force the
numbers to agree: D2 and D3 determine the intended semantics.

**Exit:** every non-zero anomaly has an owner-approved disposition: preserve,
repair via reversible/resumable plan, accept as legacy compatibility, or block
the migration. Raw affected-record lists stay in the approved secure evidence
location, not this repository.

### E3 — plan and query-performance evidence

For hot list/report/ledger paths, capture parameter-redacted query shape and
read-only `EXPLAIN (FORMAT JSON)` before and after an approved rehearsal. Do
not run `EXPLAIN ANALYZE` on an unknown busy database. Associate each plan
with a route/API ID, representative cardinality band and required index.

Review filters/joins including licence, company/owner, BOE date/hidden state,
allotment/plan identity, trade/reconciliation, ledger package request and
sync cursor/event. An index recommendation is not approved solely because a
model declares an index; capture actual physical indexes and an agreed
workload rationale.

**Exit:** query-plan findings identify a measured problematic plan or state
that no measured issue was observed for the approved scenario. Speculation is
not a performance finding.

### E4 — isolated backup and restore rehearsal

This is a separate approved write operation, performed only against an empty,
isolated target controlled by the operator. The rehearsal plan must specify:

1. source backup identifier, encryption/retention owner and checksum;
2. isolated restore target, access controls and deletion deadline;
3. exact restore commands and expected commit/migration state;
4. post-restore E1/E2 comparison, critical row-count/checksum summaries and
   D2/D3 golden balance/allocation/reconciliation samples;
5. document/media inventory and protected-media authorization checks without
   placing files or tokens in the audit repository;
6. sync inbox/outbox, ledger job and replan recovery/replay scenarios; and
7. a forward-recovery decision for a failed additive migration.

**Exit:** restore elapsed time, result, discrepancies, integrity/balance
checks, application health, worker/sync recovery results and approval owner
are captured. An application rollback alone is not accepted as database
rollback proof.

## Evidence ledger and acceptance

For E0–E4, write one redacted evidence record outside source-controlled V1
documents containing: execution date/time, environment class, operator,
command/query hash, aggregate result/checksum, failures, remediation ticket,
and approver. Link only the identifier and conclusion in `docs/v1/`.

The data/migration gate is **Verified** only when all of the following are
available: scoped authorization; E1 physical comparison; E2 approved anomaly
dispositions; E3 measured plans where a performance assertion is made; and
E4 successful isolated recovery rehearsal. Until then, the status in the
[completion audit](../09-traceability/completion-audit.md) remains Partial.

## Migration and rollback ownership

| Event | Required owner action | V1 guardrail |
| --- | --- | --- |
| Schema mismatch or invalid constraint | Stop the migration design; classify the difference and obtain data-owner disposition. | Never apply a repair command merely to make the graph look clean. |
| Non-zero duplicate/orphan result | Preserve evidence; define a reviewed, resumable repair or compatibility path. | No broad delete/merge/cascade action from the audit. |
| Backfill discrepancy | Halt the batch, retain before/after counts and old representation, and choose forward correction or isolated restore. | Do not silently rerun against shared data. |
| Restore/replay failure | Preserve the failed target for diagnosis if policy permits; record exact stage and recovery decision. | Do not retry into the same ambiguous target without an operator plan. |
| New migration proposal | Attach E1/E2 results, affected data, batch/resume key, validation query, compatibility window and forward-recovery plan. | Additive/compatible changes first; destructive cleanup is separately owner-approved. |

## Explicit non-claims

This protocol does not establish production access, authorize a database
connection, prescribe a tenant policy, approve a migration, validate backup
tooling, or prove a restore. It makes each missing evidence item concrete and
safe to collect once an approved environment is supplied.
