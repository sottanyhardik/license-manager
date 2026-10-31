# DFIA/SION restriction-aware planning scope

## Current state (static evidence)

`LicenseItemPlan` and `SionPlanningRule` exist (`license/models/core.py:1267,1396`), with plans persisted and protected through `plan_enforcement.py:211-400` and `item_plan.py:103`. The condition pool in `services/condition_pool.py:46-128` treats same exact `condition_type` (for example `10%`) as one licence-level pool calculated from export CIF; it includes BOE debit, non-BOE allotment and SALE trade usage. AU is documented there as a transfer restriction, not a separate pool (`:15-20`). Import items retain free-text `condition_type`/derived `is_restricted` (`models/core.py:902-959`).

`SionPercentageCapacity` is a separate quantity/net-quantity restriction mechanism (`services/sion_percentage_capacity.py:25-266,348-460`). It must not be equated with the CIF condition pool without a business decision.

## Findings

| ID | Priority | Observation | Remedy |
|---|---|---|---|
| DFR-01 | P1 | Exact percentage text is the group key; two independent 10% pools cannot be represented. | Versioned Rule, Group and Member configuration; immutable usage/reservation records. |
| DFR-02 | P1 | Percentage-capacity branches duplicate loops and convert broad exceptions to zero usage. | Canonical resolver/consumption façade; error instead of silent unrestricted/zero result. |
| DFR-03 | P1 | Canonical planning locks licence/items but legacy and norm planners coexist. | Characterise outputs, migrate one caller class at a time, retain locks at shared-pool commit. |

## Required canonical behaviour

The resolver selects a versioned effective rule, declares its base/scope and pool membership, returns an explanation and precision policy, then commits reservation/usage atomically under row locks. It must aggregate historical BOE/allotment/trade consumption, existing reservations, quantity/CIF capacity and reversals. Conflicting/missing rules block or explicitly warn—never silently grant capacity. Frontend displays backend values only.

Required UI: restriction/AU badges, group summary, source/version, historical/planned/new usage, maximum/remaining CIF and quantity, warning/error explanation, preview/confirmation and audit export.

## Decisions and acceptance

Management must define the legal/business base and scope of 2/3/5/10%, whether same-percentage items share a pool, AU meaning, precedence, overrides and historical treatment. Test individual 2/3/5/10, independent and shared 10% pools, mixed rules, AU, absent/malformed configuration, existing BOE/allotment/trade/plans, exact/exceed/partial capacity, concurrent commits, reversal, rule/group changes, Decimal rounding and report/API parity. Acceptance: each result is explainable, identical across preview/commit/report, and concurrent requests cannot overspend.
