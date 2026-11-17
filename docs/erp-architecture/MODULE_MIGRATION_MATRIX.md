# Module migration matrix (generic CRUD coverage)

Masters hub: `/masters` (`pages/masters/MastersHub.tsx`) lists every `masterEntities` entry by category with live counts;
the Masters menu and command palette read the same registry. Adding a simple master = backend `create_viewset(config)` +
one `masterEntities` line. Every registered master gets the licence register toolbar, licence-style rows and the
generic record page `/masters/:entity/:id` (fields, audit timestamps, real change history).

Facts from code @ `b099789c`. "Generic BE" = built by `MasterViewSet.create_viewset`. "Generic FE" = rendered by
`pages/masters/MasterList`/`MasterForm`. Extends (does not replace) `docs/MODULE_EXECUTION_MATRIX.md`.

| Module | Model / endpoint | Generic BE | Generic FE | Domain logic kept separate | Status |
|---|---|---|---|---|---|
| Company (customer/supplier/exporter party) | `companies` (`CompanyViewSetClass`) | ✅ | ✅ `/masters/:entity` | MDS write-through | Done |
| Port | `ports` | ✅ | ✅ | delete protection | Done |
| HS code | `hs-codes` | ✅ | ✅ | — | Done |
| Head SION norm / SION class / export / import | `head-norms`, `sion-classes` (+SION export/import viewsets) | ✅ | ✅ | SION rule engine | Done |
| Product description | `product-descriptions` | ✅ | nested under HS Codes only (needs `hs_code`; standalone form would 400) | — | Done (nested) |
| Unit price | `unit-prices` | ✅ | ✅ (registered 2026-11-17; form gains `unit_price`) | — | Done |
| Group / Item head / Item name | `groups`, `item-names` (+item head) | ✅ | ✅ | — | Done |
| Exchange rate | `exchange-rates` | ✅ | ✅ | — | Done |
| Transfer letter / Purchase status / Scheme code / Notification no. | `transfer-letters`, `purchase-statuses`, `scheme-codes`, `notification-numbers` | ✅ | ✅ (registered in `masterEntities` 2026-11-17; before that API-only, no UI) | code-keyed lookup for scheme/notification (`getMasterRecordKey`) | Done |
| Licence | `license/api/views/license.py` | ✅ | ✅ `/licenses` + record workspace | balance engine (protected) | Done |
| Incentive licence | `views_incentive.py` | ✅ | ✅ | — | Done |
| Allotment | `allotment/api/views.py` | ✅ | ✅ + record workspace | allocation service | Done |
| BOE | `bill_of_entry/api/views.py` | ✅ | ✅ + record workspace | frozen ledger, reconciliation | Done |
| Trade (3 viewsets) | `trade/api/views.py` | ✅ | ✅ `TradesListView` | T1–T4 pricing service | Done |
| Accounting masters (books, CoA, cost centre, bank account, TDS) | `apps/accounting` | ❌ own `AccountingView` | ❌ `AccountingWorkspace` | posting engine (ADR-004) | Intentionally separate |
| Customer / Supplier (separate) | — no model — | — | — | — | Owner decision (B1); `Company` covers parties |
| Country / Currency / Category / Unit | — no model — | — | — | — | Owner decision (B1) |
| Bank (master) | `BankAccount` in accounting | — | — | — | Accounting-owned |
| Users / roles / permissions | `apps/accounts` | not generic | own pages | RBAC | Out of generic scope |
