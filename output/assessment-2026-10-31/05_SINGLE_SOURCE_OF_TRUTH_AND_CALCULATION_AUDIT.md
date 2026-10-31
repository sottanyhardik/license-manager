# Single source of truth and calculation audit

| Metric | Current concern | Canonical owner | Consumers / acceptance |
|---|---|---|---|
| Licence/item balance | calculators, properties/reports can diverge | Backend Balance Service | API/UI/PDF/Excel agree on golden examples. |
| Restriction usage | condition pools and SION capacity differ | Restriction Resolver + immutable usage ledger | preview/commit/report same rule/base/group/rounding. |
| Allotment/BOE capacity | multi-path mutation risk | Allocation Service | atomic locks/idempotency/reversal tests. |
| Reconciliation difference | counting semantics unverified | Reconciliation Query Service | source links/match basis/tolerance explicit. |
| Dashboard/export totals | derived display risk | approved read model sourced by services | scope/filter/export parity tests. |

Frontend never independently determines financial entitlement. Central Decimal/rounding policy, cancellation/hidden/merge policy and tenant context are mandatory.
