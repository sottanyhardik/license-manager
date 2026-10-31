# Database-first forensic audit - initial evidence baseline

**Repository baseline:** `develop` at `d2cb2446ba01e0e23e6ef3570f6449bdd001cf65` (verified 31 October 2026).  
**Database access:** no authorised direct database/schema query or restore environment was available in this audit step.  
**Evidence levels:** model/migration statements below derive from existing repository documentation and earlier model-audit evidence; they are not a claim that the live production schema has been inspected.

## Confirmed database architecture evidence

- PostgreSQL is documented as the application datastore; `psycopg` v3 is recorded in existing documentation.
- Most concrete models are documented as inheriting `AuditModel`, which records created/modified fields and nullable `created_by`/`modified_by` references.
- The documented central business entities are Company, Port, HS Code, SION Norm, Licence, Licence Import/Export Item, Licence Balance/Flags/Ownership/Notes/Document/Transfer, Allotment, BOE/Row Detail, Trade/Line, allocation ledgers, payments and reconciliation records.
- Existing integrity documentation reports a mixture of `PROTECT`, `CASCADE`, `SET_NULL` and unique-together controls. It also reports no explicit model-level check constraints for certain over-allocation and plan-cap rules, leaving service/concurrency enforcement critical.

## P0/P1 database findings

| ID | Finding | Evidence status | Impact | Required action before rebuild schema design |
|---|---|---|---|---|
| DB-001 | Company/server-side tenant scope is not demonstrated across all records, queries, exports and jobs. | INFERRED_RISK | Cross-company access/migration misclassification risk. | Obtain model/query inventory and approve company/master-data policy. |
| DB-002 | Licence `available_quantity` is documented as stored/materialised while multiple live calculations are documented with different component sets. | CONFIRMED from earlier code audit | Stored/displayed/report values can diverge. | Freeze approved ledger semantics and golden examples before target schema/backfill. |
| DB-003 | Important allocation/cap validations are reported as service-layer checks, not DB check constraints. | PARTIALLY_CONFIRMED | Direct/parallel writes may bypass or race the intended rule. | Define atomic service transactions, locks/idempotency and only justified DB constraints. |
| DB-004 | Licence deletion cascades into business history; transfer/purchase and line-item cascades have historical-impact risk. | CONFIRMED from prior model relationship audit | A seemingly valid delete can erase evidence or balances. | Replace destructive operational correction with state/reversal policy; preserve legacy data. |
| DB-005 | `IncentiveLicense` company/port cascade relationships were previously flagged as P1-001. | REPORTED_NOT_VERIFIED against current branch | Master deletion can remove incentive history. | Reconfirm current model/migration and approve a backward-compatible remediation. |
| DB-006 | `invoice_no = "OTH"` plus latest reconciliation action is documented as hidden-BOE logic. | PARTIALLY_CONFIRMED | Migration/report reconciliation could count different record populations. | Treat visibility state/history as a first-class migration rule; test historical presentation. |

## Database-first rebuild principles

1. Do not regenerate historical balance, accounting or usage records to make target reports look clean.
2. Map source identifiers and raw evidence separately from target calculated read models.
3. Migrate operational facts first; derive caches/read models only from approved facts and compare them to legacy presentation.
4. For every field/table, record authoritative source, company ownership, lifecycle, deletion policy, historical-retention rule and reconciliation query.
5. No production schema change is allowed until backup restoration, two dry migrations and reconciliation gates are accepted.

## Discovery still required

- Exact current model fields, migration graph, constraints, indexes and database-specific features from source/migration inspection.
- `makemigrations --check`/migration-plan evidence from an isolated environment.
- Live schema/catalog, row counts, constraints, extensions and source data quality evidence.
- Uploaded file/storage inventory, retention obligations and actual deletion paths.

