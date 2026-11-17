# Current blockers (owner / CA decisions)

Only items that need a human. Source of truth for workstream detail: `docs/ERP_AUTONOMOUS_EXECUTION_STATUS.md`.

| ID | Blocker | Needs | Impact |
|---|---|---|---|
| B1 | Customer, Supplier, Country, Currency, Product category, Unit-of-measure and Bank masters do **not** exist as models (Company is the single party master; banks are accounting `BankAccount`). Re-checked 2026-11-17 for the Masters workspace request | Owner: new models (schema change) and their fields, or keep Company as the party master | Not created — would invent schema/requirements (CLAUDE.md §2a). Each is one `create_viewset` + one `masterEntities` line once a model exists |
| B2 | A-2 stored quantity; T5–T9 | Owner approval (frozen 2026-11-17) | Not implemented |
| B3 | GST on licence trades, TDS sections/rates, inventory costing | CA | Accounting incomplete |
| B4 | BOE list perf (~818 queries / 100 rows, per-row available CIF) | Owner: touches protected balance code | Deferred |
| B5 | System of record / Tally cut-over (D6/AD-02) | Owner + CA | Tally connector deferred |
| B6 | `git push` of `feature/v5` | Owner approval | Local-only commits |
| B7 | Master audit history / active-inactive for masters without the fields | Owner: which masters need `is_active`/history (schema) | Shown where the model has them (`PurchaseStatus.is_active`, `ActivityLog`); not added elsewhere |
