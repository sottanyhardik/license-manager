# Single source of truth and duplication audit

| ID | Rule | Known locations | Risk / canonical owner / migration |
|---|---|---|---|
| DUP-01 | Restriction availability | `models/core.py:1033`; `condition_pool.py:250-289`; `validation_service.py:118-225` | P1. Similar logic can diverge. Make condition/restriction service the sole calculation contract; migrate property/API/validator after characterisation tests. |
| DUP-02 | SION percentage consumption | `sion_percentage_capacity.py:57-266` and `:319-460` | P1. Generic/enumerated branches repeat cap/usage loops. Consolidate only after confirming semantic equivalence. |
| DUP-03 | Decimal policy | `balance_calculator.py:39-42`; `canonical_planning_service.py:47-64,127-134`; `sion_percentage_capacity.py:79-82,306-308` | P2. Central Decimal/currency/quantity policy with named rounding contexts. |
| DUP-04 | Balance/report values | `balance_calculator.py:1315-1846`, model properties, ledger/report views | P1/P2 pending output comparison. Backend balance service should publish DTOs consumed by views/exports; frontend must not calculate entitlements. |

Safe sequence: enumerate callers → golden/characterisation tests → decide business semantics → version service interface → migrate one API/report/workflow class → compare outputs and monitor → deprecate/remove only after callers and regressions are proven. Do not combine financial/restriction consolidation with tenant or accounting schema migrations.
