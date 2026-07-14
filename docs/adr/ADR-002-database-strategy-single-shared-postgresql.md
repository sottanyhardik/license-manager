# ADR-002 — Database Strategy: Single Shared PostgreSQL

**Status:** Accepted
**Date:** 2026-07-14

## Context

The hybrid parallel-run strategy (ADR-001) requires both the legacy app and the
new app to operate against live production data simultaneously. The critical
question is whether they share one database or maintain separate databases with
some synchronisation mechanism.

License records, BOE entries, allotments, and DGFT data have complex
referential integrity constraints. IDs and foreign keys are embedded in
documents, audit logs, and reports. Any mechanism that copies or transforms
data between two stores introduces drift, sync lag, and reconciliation burden.

The legacy Django ORM manages the schema via migrations. The new app's Django
ORM will also run migrations. Both must coexist safely.

## Decision

Use **one PostgreSQL instance** shared by both the legacy app and the new app
throughout the entire transition period.

Rules that must hold during transition:

1. **All migrations from the new app are additive only.** No `DROP TABLE`, no
   `DROP COLUMN`, no destructive `ALTER TABLE` is permitted until after
   production cutover and the rollback window closes.
2. **New columns added by the new app's migrations must be nullable or carry a
   DEFAULT**, so the legacy ORM can INSERT and UPDATE rows without supplying
   the new columns.
3. **Primary keys and foreign key values are never reassigned.** Both apps read
   and write using the same integer/UUID PKs.
4. **No ETL, no data sync, no duplicate tables.** The DB is the single source
   of truth at all times.
5. **django-simple-history** audit tables are written only by the new app;
   legacy app writes are not audited at the row level (this is an accepted gap
   during transition).

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Separate DB with ETL at cutover | ETL introduces transformation risk; any bug means data loss or corruption at the moment of cutover. Sync lag during transition creates stale-read windows. |
| Dual-write (both apps write to both DBs) | Race conditions on concurrent writes; conflict resolution is complex; double the write latency; extremely hard to test correctly. |
| Separate DB with bidirectional sync (e.g. Debezium CDC) | Operational complexity; lag is unavoidable; CDC misses application-level computed fields; heavy infrastructure addition for a time-limited transition. |

## Consequences

**Positive:**
- Zero data migration risk at cutover: the DB is already in the correct state.
- Referential integrity is always enforced by PostgreSQL (no cross-DB FK gaps).
- Developers can write Django queries against real production-volume data from
  day one of the new app's development.
- Rollback is instant: flip nginx upstream; both apps still point to the same
  authoritative data.

**Negative:**
- New app migrations must be reviewed for destructive statements on every PR.
  A CI check (`grep -E 'DROP TABLE|DROP COLUMN|TRUNCATE'` in migration files)
  is recommended.
- The new app's models must accommodate any column added by legacy migrations
  (rare, since legacy is read-only per ADR-010, but the possibility exists for
  emergency hotfixes).
- Nullable-column discipline requires developer awareness; a non-nullable
  column without a DEFAULT will break legacy INSERTs immediately.
- django-simple-history audit coverage has a gap for rows written by legacy
  during the transition period.

## Related ADRs

- ADR-001 — Migration Strategy: Hybrid Parallel-Run
- ADR-010 — Legacy Read-Only Rule
