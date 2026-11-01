# Data-model inventory

## Evidence and scope

**Verified by static code inspection.** The index identifies 90 model declarations or model-like mixins in application model modules, alongside serializer/view classes that are intentionally excluded from this inventory. Django migration modules total 127 across the application apps. This inventory describes declared source relationships, not the live database: inspect `information_schema`, deployed migration state, and data cardinality before any DDL conclusion.

| Ownership family | Declared persistent entities | Primary source |
| --- | --- | --- |
| Identity and access | `User`, `RevokedAccessToken` | `apps/accounts/models.py` |
| Core masters and audit | `MasterChange`, `CompanyModel`, `PortModel`, `ItemHeadModel`, `ItemGroupModel`, `ItemNameModel`, `HSCodeModel`, `HeadSIONNormsModel`, `SionNormClassModel`, `SIONExportModel`, `SIONImportModel`, `SionNormNote`, `SionNormCondition`, `ProductDescriptionModel`, `TransferLetterModel`, `UnitPriceModel`, `InvoiceEntity`, `SchemeCode`, `NotificationNumber`, `PurchaseStatus`, `ExchangeRateModel`, `CeleryTaskTracker`, `ActivityLog` | `apps/core/models.py` |
| Master-data synchronization | `SyncConflictLog`, `SyncPeer`, `SyncCursor`, `SyncEvent`, `SyncInboxEvent`, `SyncPeerDelivery`, `MediaSyncTask` | `apps/core/sync/models.py` |
| Licence and planning | `LicenseDetailsModel`, `LicenseExportItemModel`, `LicenseImportItemsModel`, `LicenseReplanRequest`, `LicenseItemPlan`, `SionPlanningRule`, `SionPlanningUnitValueRow`, `SionPlanningPercentageRow`, `SionInputAliasConfig`, `SionPlanningProfile`, `SionPlanningAction`, `SionPlanningOutputMapping`, `SionPlanningRun`, `LicenseDocumentModel`, `StatusModel`, `OfficeModel`, `AlongWithModel`, `DateModel`, `LicenseInwardOutwardModel`, `LicenseTransferModel`, `IncentiveLicense`, `LicensePurchase`, `LicenseNotes`, `LicenseBalance`, `LicenseFlags`, `LicenseOwnership`, `LicenseLedgerPackageJob`, `LicenseLedgerPackageItem`, `LicensePackageArtifact`, `LicensePackageAuditEvent`, `LicenseLedgerRecoveryAudit`, `Invoice`, `InvoiceItem` | `apps/license/models/` |
| Allotment | `AllotmentModel`, `AllotmentItems`, `AllocationVersion`, `AuditEvent`, `Shortfall` | `apps/allotment/models/` |
| Import evidence | `BillOfEntryModel`, `RowDetails` | `apps/bill_of_entry/models.py` |
| Commercial trade | `LicenseTrade`, `SaleClassificationDecision`, `LicenseTradeLine`, `IncentiveTradeLine`, `LicenseTradePayment`, `TradePairAudit`, `TradeInvoiceDocument`, `InvoiceDocumentAccessToken`, `InvoiceDocumentAuditEvent` | `apps/trade/models.py` |
| Reconciliation | `ReconciliationNote`, `ReconciliationLog`, `InvoiceBOEAllocation`, `BOEAllotmentAllocation`, `ExternalInvoiceLink`, `IgnoredWarning` | `apps/reconciliation/models.py` |
| Operational tasking | `Task`, `TaskRemark` | `apps/tasks/models.py` |

## Declared relationship and lifecycle map

The following is **verified by source declaration**. Deletion meanings are relational mechanics, not a business authorization policy.

| Aggregate / record | Declared relationships and lifecycle mechanics | Integrity relevance |
| --- | --- | --- |
| Licence | `LicenseDetailsModel` refers to master purchase status, scheme, notification, exporter and port; export/import items, documents, transfers, purchases, plans and package items descend from or refer to it. Several child records use `CASCADE`; ledger-package items use `PROTECT`. | A licence delete/correction may traverse operational records. Do not infer that UI deletion is supported merely because a database cascade exists. |
| Licence import item | One licence has import items; an import item refers to HS code and can relate to multiple item names. BOE rows, allotment items, trade lines, invoice items and planning objects use it or its derived identity. | `(license, serial_number)` is declared unique; it is a central traceability key. |
| BOE | `BillOfEntryModel` refers to company, port and optional planning target and has an allotment M2M; `RowDetails` belongs to a BOE and an import item. | `(bill_of_entry_number, bill_of_entry_date)` and `(bill_of_entry, sr_number, transaction_type)` are declared unique tuples. Hidden/correction fields must be treated as history, not silently removed. |
| Allotment | `AllotmentModel` refers to company, port, related company and optional planning target; `AllotmentItems` joins allotment to licence import item, plan line and predecessor version. | Allocations have declared constraints/indexes and separate version/audit/shortfall records; live balance validation cannot be replaced by a plain FK check. |
| Trade | `LicenseTrade` has incentive licence, from/to company, related BOEs, pairing/copy links and a counterpart one-to-one; trade lines/payments/documents descend from it. | Trade pairs and document tokens/audit events create recovery and access-history dependencies. Exact check/unique semantics require migration/live-schema verification. |
| Reconciliation | Invoice-to-BOE and BOE-to-allotment allocation records refer to trade line/BOE row or BOE row/allotment item, can point to a superseding allocation, and carry audit lineage. | Supersession means a row’s presence alone is not authoritative current allocation state. Preserve lineage in all migrations. |
| SION/planning | Norm class feeds export/import/note/condition masters; licence plan/rule/profile/action/output/run entities bind SIONs, import items and output items. | Planning identity and rule priority are constrained in source. Owner decision D3 governs semantic changes. |
| Sync | A peer owns one cursor and deliveries; events, inbox events and delivery joins provide deduplication/replay evidence. | Inbox `(source_server, event_id)` and peer/event uniqueness are declared; any migration must preserve idempotency keys. |
| Audit/activity | `AuditModel` has creator/modifier; activity and domain-specific audit tables retain actor and sometimes before/after company context. | Activity middleware is asynchronous, so source declaration does not prove compliance-grade durability. |

## Physical-schema completion gate

The model source plus migrations is sufficient to identify what must be reconciled, but insufficient to prove database state. Before a V1 migration, record for **every concrete table**: table name, columns/types/nullability/defaults, FK target/on-delete, check/unique constraints, indexes, row count, orphan/duplicate scan result, migration origin, and owning domain. That live-schema register is deliberately outstanding; see [current schema](../06-data-and-migrations/current-schema.md) and [migration plan](../06-data-and-migrations/migration-plan.md).
