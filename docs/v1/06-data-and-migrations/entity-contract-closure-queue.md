# Entity-contract closure queue

**Inferred from static source inventory; proposed for V1 audit execution.**
This queue converts the current **90 model declarations or model-like mixins**
and **127 Django migration modules** into a safe, repeatable data-contract
review programme. The denominator comes from the static discovery method in
[data-model inventory](../01-discovery/data-model-inventory.md). It is not a
live-table count, because abstract models, mixins, proxy/model-like index hits
and migration history cannot establish the deployed physical schema.

No entity is promoted to `Verified` by appearing in this queue. The 12
high-risk lifecycle families remain the bounded source evidence in
[high-risk entity lifecycle contracts](high-risk-entity-lifecycle-contracts.md).

## Closure unit and reproducible record

The review unit is one **concrete Django model/table**, plus its owning
aggregate where the table is a ledger, side table, audit table or sync record.
For each static candidate, first classify it as concrete model, abstract base,
mix-in, serializer/view false-positive, historical migration operation, or
external/proxy representation. This classification step prevents a regex
index row from being misreported as a deployed table.

Record this evidence card for every concrete unit:

```text
Entity ID / app / source symbol / migration origin:
Classification: concrete table | abstract base | mixin | non-table index hit:
Owning aggregate and source-of-truth role:
Columns, precision/null/default and derived/cache/snapshot fields:
Relations: FK/M2M/one-to-one target and declared on_delete semantics:
Declared DB constraints, indexes, uniqueness and model-only validation:
Lifecycle: create/update/cancel/hide/reverse/supersede/delete/retention:
Writers/readers: API/service/task/signal/command/report/export consumers:
Authorization/company/object scope and decision dependency:
Migration/backfill/compatibility origin and forward-recovery requirement:
Live-schema/data proof: catalog result, migration state, row count,
  duplicate/null/orphan result, backup/restore result (when safely collected):
Existing exact tests and required missing tests:
Status/evidence class/recommended action:
```

`Declared` fields and constraints are source evidence only. A row can leave
`Partial` only after the scoped live-schema/recovery evidence protocol records
physical confirmation and relevant data-quality evidence.

## Disjoint source ownership lanes

The following lanes are derived from the persistent entity families explicitly
listed in the data-model inventory. They cover the inventory's complete source
scope; where a base/mix-in is shared, review it once in **E0** and cross-link
it rather than duplicating its constraint claim in every child lane.

| Queue | Persistent ownership family | Representative entities / source scope | Closure emphasis | Priority/dependencies |
| --- | --- | --- | --- | --- |
| E0 — bases and classification | identity/audit/sync base types and all model-like index hits | `User`, `AuditModel`, sync timestamp/UID mixins and any abstract/proxy candidates | Decide concrete-table denominator; inherited creator/modifier/UID and migration implications | P1; prerequisite for every lane |
| E1 — access and company masters | accounts plus company/reference masters | `User`, revoked tokens, Company, Port, scheme/notification/purchase-status and shared reference entities | Retention/role/company relationship, redaction, master deletion and D1 scope | P0/P1; D1/D4 |
| E2 — SION and core master graph | SION/master/reference data in `apps/core/models.py` | item/head/group/name/HS, norm/class/export/import/note/condition, unit-price, exchange rate, transfer letter | Natural/synthetic identity, MDS sync ownership, merge/de-duplication, delete protection and D3 source semantics | P1; D3 and sync policy |
| E3 — sync and asynchronous core records | `apps/core/sync/models.py` plus activity/task-tracker records | peers, cursors, outbox/inbox/delivery, media tasks, conflicts, activity and Celery tracking | Idempotency keys, peer/event uniqueness, replay/retention, restore ordering and D6 audit distinction | P1; D4/D6, recovery drill |
| E4 — licence header, items and planning | `apps/license/models/core.py` licence/planning/document portions | licence, export/import item, plan/rule/profile/action/run, documents, transfer/purchase/incentive records | entitlement identity, D2/D3 engines, planned capacity, document lifecycle and migration compatibility | P0; D2/D3 |
| E5 — licence side tables and ledger package | licence balance/flags/notes/ownership, invoice and package records | one-to-one subtables, invoice/items, package job/item/artifact/audit/recovery records | signal-created row completeness, cache versus live values, job/idempotency/owner scope and storage recovery | P0/P1; D1/D2/D4/D6 |
| E6 — allotment and import evidence | allotment and BOE applications | allotment/item/version/audit/shortfall; BOE/row details | live-capacity ledger, correction/freeze/hide behavior, cascades/M2M, duplicate BOE identity and replan coupling | P0; D1/D2/D3 |
| E7 — trade and commercial documents | `apps/trade/models.py` | trade/pair/classification/lines/payments/document/access-token/audit records | correction/reversal, company links, document capability/expiry, total/payment meaning and D5 boundary | P1; D1/D4/D5/D6 |
| E8 — reconciliation ledgers | `apps/reconciliation/models.py` | notes/logs, invoice/BOE and BOE/allotment allocations, external links, ignored warnings | immutable/superseding lineage, independent consumption tracks, model-only validation bypass and reconciliation parity | P0; D1/D2/D5/D6 |
| E9 — operational task records | `apps/tasks/models.py` | task and remarks | state transitions, object lookup, comments/retention and execution identity | P1; D1/D6 |

The lane table is an ownership programme, not a new row-count claim. The
actual concrete-table count is deliberately deferred to E0 plus a scoped
catalog query, because the static inventory includes model-like mixins and
the audit must not manufacture physical-schema certainty.

## Execution order and dependencies

1. **E0 and safe catalog baseline:** establish the concrete-table list from
   migration state and database catalog in an approved environment. Do not run
   DDL, data repair, `migrate`, or backfill while collecting evidence.
2. **P0 financial integrity lanes:** E4–E6 and E8 use a frozen dual-balance,
   allocation, BOE hide/restore and reconciliation fixture set. D1–D3 must be
   approved before any policy-changing proposal is implemented.
3. **P1 security/durable-work lanes:** E1, E3, E5, E7 and E9 establish owner,
   token, document, peer, job and audit behavior. D4–D6 decide retention and
   assurance obligations.
4. **Master/reference lane:** E2 validates master identity, MDS transport,
   historical merge/correction and import policy after peer restore/replay is
   characterized.
5. **Migration readiness:** only after each changed entity has an evidence
   card, catalog/data-quality result, backup identifier and forward-recovery
   plan may a migration task enter M4.

E1–E3 can be characterized in parallel with E4–E9, but no shared FK,
constraint, deletion or company-scoping change may be approved from one lane
without reviewing the other lanes that reference it.

## Required live evidence and safety boundary

Run the exact E0–E4 evidence sequence in the
[live-schema and recovery evidence protocol](live-schema-and-recovery-evidence-protocol.md):

- export migration/canonical catalog metadata and compare it with model source;
- inspect FK target/action, checks/uniques/indexes and row counts read-only;
- report null, duplicate and orphan candidates before proposing constraints;
- rehearse backup/restore only in an approved isolated environment; and
- reconcile balances, allocations, sync identities and package/replan state
  after restore.

The audit does **not** authorize querying an unknown database, accessing
production credentials, applying migrations, modifying backups, running a
repair command, or deleting a table/field/record. Any migration is additive
first and needs a named forward-recovery path; rollback is not assumed safe
once an irreversible data transform has started.

## Closure reporting

For each lane report separately:

| Metric | Meaning |
| --- | --- |
| Static candidates classified | Index rows assigned concrete/abstract/mixin/non-table status; not a live-table proof. |
| Concrete tables source-mapped | Model, migration origin, relationships, constraints and lifecycle documented. |
| Live-schema confirmed | Approved catalog/migration evidence matches the intended representation. |
| Data-quality checked | Scoped row-count/null/duplicate/orphan results reviewed with an owner policy. |
| Restore/recovery exercised | Isolated restore plus domain reconciliation and forward-recovery evidence. |
| Fully closed | All applicable evidence-card fields, owner decisions and acceptance tests complete. |

Do not add these metrics across overlapping aggregates. The current truthful
position is **90 static model/model-like declarations inventoried; 12
high-risk entity families source-traced; 0 live-schema, data-quality or
restore-complete entity contracts claimed**.
