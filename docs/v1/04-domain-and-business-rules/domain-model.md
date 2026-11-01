# Domain model

**Verified by code/static inspection.** Principal entities: licences and licence items; BOEs and rows; allotments, allotment items, allocation versions and shortfalls; trade documents, lines and payments; reconciliation allocations; core masters/sync state; task/replan/ledger-package state; users/roles; audit/activity records; and SION planning state.

```mermaid
erDiagram
  LICENCE ||--o{ LICENCE_ITEM : contains
  LICENCE ||--o{ BOE_ROW : debited_by
  LICENCE ||--o{ ALLOTMENT_ITEM : allocated_by
  ALLOTMENT ||--o{ ALLOTMENT_ITEM : contains
  BOE ||--o{ BOE_ROW : contains
  TRADE ||--o{ TRADE_LINE : contains
  BOE_ROW }o--o{ RECONCILIATION_ALLOCATION : reconciled_by
```

This is conceptual, not a migration-ready physical ERD. FK deletion behaviour, exact constraints and indexes remain covered by the existing enterprise-rebuild schema evidence and must be revalidated against migrations before DDL changes.
