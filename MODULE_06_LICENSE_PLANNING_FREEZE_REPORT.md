# Module 06 — License Planning Freeze Report

Date: 2026-08-17
Status: implementation complete; freeze withheld pending the repository-wide regression gate

## Module 05 boundary

Module 05 remains on the canonical ledger/export architecture committed in `c180ed61`. Module 06 does not change ledger accounting, invoice document resolution, PDF/Excel financial rendering, purchase/sale/P&L, balance, SION reporting, or license-type filtering. The focused Module 05 parity, export-security, and secure-invoice regression suite passes 25/25.

## Authoritative planning definitions

- Scope: one company-owned license and one physical planning group. A group is the canonical HSN/description identity plus unit.
- Planned quantity: the immutable lifetime utilization-plan cap saved in `LicenseItemPlan`.
- Allocated/consumed quantity: all live qualifying allocation quantity for the complete physical group.
- Available quantity: current stored availability summed across every sibling import row in that same physical group.
- Remaining quantity: `max(planned quantity - all-time allocated quantity, 0)`.
- Shortage quantity: `max(remaining quantity - current available quantity, 0)`.
- Excess quantity: `max(current available quantity - remaining quantity, 0)`.
- Status: `UNPLANNED`, `FEASIBLE`, `SHORT`, or defensive `BLOCKED_UNIT_MISMATCH`.
- Quantity precision remains Decimal with three decimal places. CIF/value precision and existing planning writes remain Decimal with two decimal places.

The legacy `used_quantity` and `remaining_quantity` fields retain their since-replan/baseline meaning for backward compatibility. New consumers use the explicit canonical Module 06 fields.

## Root cause

The production symptom compared current availability with the original lifetime plan. That ignores allocation already consumed from both quantities. Some screens also compared one raw import row with a plan pooled across sibling rows.

The correct comparison is group scoped:

`remaining lifetime plan = original planned quantity - all-time allocated quantity`

and then:

`shortage = max(remaining lifetime plan - current group availability, 0)`

No planned or available value is clamped or artificially changed.

## Real-data reconciliation

- Raw rows where available was below original planned: 12.
- Canonical physical groups represented: 10.
- Prior-utilization cases: 10 raw rows.
- Sibling-pooling cases: 2 raw rows.
- True shortages after canonical reconciliation: 0.
- Mixed-unit real groups: 0.

Examples:

- License `0311051322`: planned 26,208; allocated 11,933; remaining 14,275; available 14,275; `FEASIBLE`.
- License `0311055317`: planned 9,362; allocated 3,159; remaining 6,203; available 6,203; `FEASIBLE`.

## Unit integrity

There is no approved unit-conversion registry in the current schema. Canonical grouping therefore preserves historical KG keys and separates every non-KG unit (`MT`, `PCS`, etc.) before aggregation. Quantities with different units are never numerically pooled or compared.

## API and UI

The license overview API now emits source/planning unit, conversion, available, planned, allocated, consumed, remaining, shortage, excess, feasibility, status, and source-record identifiers from the shared planning result.

Planning Overview renders those canonical fields directly. It no longer aliases remaining quantity as available quantity. True shortages use visible text as well as color. Saved Planning Editor status consumes the backend status; arithmetic retained in the editor is limited to unsaved draft validation.

Planning by SION is now explicit and atomic. `POST /api/license-item-plans/plan-norm/`
accepts exactly one active canonical `sion_id` and an explicit, duplicate-free
license-id list. Every license must be authorized and carry that exact SION FK
before any planner runs or plan row changes. Multi-SION licenses therefore use
the selected master id rather than an arbitrary first export row. Repeating
identical input preserves plan row ids and reports `UNCHANGED`. The former
multi-norm `auto-plan-all` endpoint and its duplicate implementation were removed.
The implicit `norm-prefill`, `e1-auto-plan`, and detected-norm `auto-plan`
routes were also retired; automated writes now require an explicit SION row.

`GET /api/license-item-plans/planning-norms/` exposes canonical selected-SION
rows and backend totals, including license-level planned counts and
`UNPLANNED`/`PARTIALLY_PLANNED`/`FEASIBLE`/`SHORT`/`CONFLICT` status. HSN and
product filters are applied in this canonical read layer with explicit AND/OR
logic; the frontend does not aggregate planning amounts.

## License entry and planning workspace

- Canonical route: `/planning`, protected by the `LICENSE_MANAGER` role.
- License list and license overview expose a permission-gated **Plan Norms**
  action using the stable license id and an encoded origin.
- `?license_id=<id>` survives refresh, seeds the reusable multi-license select,
  and immediately loads authorized common applicable norms and canonical
  snapshots. Users may add more authorized licenses afterward.
- The backend returns applicable norms, export/input metadata, summary counts,
  quantities and statuses in one envelope. React does not derive planning
  accounting or probe every SION master.
- Each row retains one row-local **PLAN** mutation. There are no SION
  checkboxes, Plan All or Plan Selected actions.
- The workspace provides canonical summary cards, text HSN/product filters,
  AND/OR logic, direct SION selection, empty/loading/error states, textual
  shortage/status feedback, mutation counts, and origin-aware Back navigation.

## SION-first item-rule architecture

The authoritative workflow is now SION-first. The user selects exactly one
canonical SION norm, loads or authors its item rules, tests the rules against
current items, reviews price and availability results, and explicitly plans.
Licenses are resolved afterward as applicable allocation targets; an optional
license URL context only narrows that downstream set and is no longer the
primary planning control.

- `SionPlanningRule` persists one SION's structured JSON expression, Decimal
  maximum unit-price ceiling, unit, priority, active flag, and immutable
  version/audit metadata. Editing appends a version; retirement preserves
  history.
- The bounded backend evaluator supports nested ALL/ANY (`AND`/`OR`), explicit
  `NOT`, `CONTAINS`, `NOT_CONTAINS`, `EQUALS`, and `STARTS_WITH`. It rejects
  empty, oversized, duplicate, conflicting, or unsupported expressions and
  never evaluates source text or raw SQL.
- HSN and product-description predicates are field-specific. HSN remains text
  with leading zeroes preserved; descriptions use case-insensitive,
  whitespace-normalized matching.
- Current prices resolve from the existing HS-code and unit-price masters.
  `max_unit_price` is only an eligibility ceiling: equal/below is eligible;
  missing or above-ceiling prices block the write. The ceiling is never copied
  over the current price and prices are never clamped.
- Equal-priority overlapping rules produce `RULE CONFLICT`; lower numeric
  priority wins otherwise. This prevents an item from being planned twice.
- `POST /api/sion-planning-rules/<id>/test/` is preview-only. It returns the
  matched items, price source/status, applicable licenses and canonical
  quantities without planning writes.
- `POST /api/sion-planning-rules/<id>/plan/` is the only rule execution path.
  It writes eligible matches through `CanonicalPlanningService`, uses the
  actual current price, locks deterministically, and treats identical retries
  as `UNCHANGED` without replacing plan-row identities.
- React only builds structured rule JSON and renders backend results. The
  matched-item table displays HSN, product, unit, current/max price, eligibility,
  available/planned/shortage status and applicable license. It does not evaluate
  rules, prices, quantities, or feasibility.

## Security

`LicenseItemPlanViewSet` is tenant scoped for list, retrieve, create, update, and delete. `LicenseDetailsViewSet` now applies the same company scope centrally, closing the URL-selected `plan-utilization` IDOR and protecting detail/overview actions used during planning preselection. Single-SION planning validates the complete requested license set before computation and locks license rows in deterministic order. A missing, inapplicable, inactive, unsupported, or cross-company selection rolls back the entire request. Cross-company identifiers do not expose or mutate planning data; superuser behavior remains explicit.

## Performance

Planning utilization status is batch-loaded. The regression test holds status resolution to four queries for ten groups, eliminating the former per-group aggregate growth.

SION-rule preview bulk-prefetches export/import relations, item masters and
prices, and batch-loads financial balances for the applicable license set.

## Verification

- SION rule engine/API/security/idempotency suite: 21 passed.
- Broader canonical planning, single-SION, security, grouping, utilization and
  plan CRUD regression: 120 passed.
- SION-first workspace focused tests: 4 passed.
- Integrated focused backend planning/security suite: 49 passed.
- Explicit single-SION contract/workspace envelope: 13 passed.
- Combined single-SION, planning-security and detail target: 17 passed.
- Tenant/detail authorization audit: 19 passed.
- Planning workspace/UI acceptance: 16 passed.
- Focused Module 05 regression suite: 25 passed.
- Frontend full regression: 398 passed across 54 files.
- Frontend typecheck: passed.
- Frontend production build: passed.
- Migration drift check: no changes detected.
- Django system check: passed with zero issues.
- Full backend regression: 1,027 passed and 37 skipped before an unrelated pre-existing stale test failed in `test_idor_fixes_p0_p1.py`. Its fixture supplies removed `BillOfEntryModel` fields (`boe_number`, `boe_date`, `exporter_id`) and an invalid `port_id=1`, so the repository-wide regression gate is not green.

## Freeze decision

All Module 06 implementation, real-data, security, performance, frontend, and Module 05 isolation gates pass. The formal `MODULE 06 — LICENSE PLANNING — FROZEN` declaration is intentionally withheld because the mandated full-backend regression gate is not fully passing for the unrelated stale fixture described above.
