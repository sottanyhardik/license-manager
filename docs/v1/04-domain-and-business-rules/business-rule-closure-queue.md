# Business-rule closure queue

**Purpose:** turn the V1 audit's consequential calculations and state rules
into an implementation-safe, reproducible closure program. This is a
documentation/planning artefact. It does not select a business policy, alter a
formula, or promote a calculated output to a universal source of truth.

## Evidence language

- **Verified current behavior** means the cited implementation/test establishes
  the bounded current rule.
- **Proposed V1 evidence** is a golden-data, transition, regression or
  provenance gate to add before changing behavior.
- **Owner decision required** identifies policy that code and tests cannot
  legitimately supply.

The detailed rule/function evidence remains in the
[balance/allocation/replan register](../09-traceability/balance-allocation-function-contracts.md),
[SION/planning register](../09-traceability/sion-planning-function-contracts.md),
[reconciliation register](../09-traceability/reconciliation-function-contracts.md),
[ledger/report register](../09-traceability/ledger-report-function-contracts.md),
and [P0 regression-test contracts](../09-traceability/p0-regression-test-contracts.md).

## Golden-data packet required for every queue

Each queue closes only with a small, versioned fixture pack containing:

1. source records, event order and as-of timestamp;
2. Decimal input values, units, currency/rate basis and expected quantized
   output (no floating-point comparison);
3. visible/hidden, cancelled/reversed/restored and excluded-record state;
4. actor/role and D1-approved company/object scope when the rule is invoked
   through an API or job;
5. expected persisted effects, ledger/audit rows, report/API/UI labels, and
   a cleanup/replay procedure; and
6. exact named tests and a trace to the affected `API-*`, `UI-*`, `WF-*` and
   `BAC-*`/`RCF-*`/planning contract IDs.

The fixture may be synthetic; no production business data belongs in this
documentation or golden suite.

## Ordered rule queues

| Queue | Verified current behavior and source boundaries | Owner decision / policy boundary | Proposed V1 golden/transition proof | Dependencies and exit evidence |
| --- | --- | --- | --- | --- |
| BR-01 Customs, live and Financial licence balance | **Verified by code:** `BAC-01` live balance excludes hidden BOE debit; `BAC-02` Customs includes visible and hidden BOE debit; `BAC-03/04` opening/Financial balance include trade/allocation treatment. Each floors zero and quantizes to two decimals at its documented boundary. **Verified by test:** current precision, hidden-row and expected Financial-vs-Customs divergence cases are mapped by RTC-04/05. | **D2:** which named output is authoritative for each user/report/action; cancellation/reversal and presentation meaning. | One licence fixture covers credit, purchase, sale, matched/unmatched and hidden BOE, allotment, restore and reversal. Assert each named engine separately, batch-vs-single parity, and every output's engine/as-of/source disclosure. | P0. Requires D2 or an approved preserve-current limitation. Exit only when report/API/PDF/XLSX/card mappings preserve labelled outputs; never close by asserting the engines equal. |
| BR-02 Item quantity, CIF and allocation capacity | **Verified by code:** `BAC-05/06` derive item credit/debit, available quantity and allocation value from import/item/BOE/allotment/direct-sale inputs; `BAC-09` performs locked live validation before allocation. | **D2/D3:** CIF basis and any shared-pool/restriction treatment. | Decimal quantity/CIF boundary pack: zero, exact-cap, fractional, stale-low/stale-high cache, sibling item, hidden BOE, partial allocation, unpaired sale and concurrent contenders. Assert advisory calculations cannot authorize a spend. | P0. Existing live-balance/stale-cache tests are starting evidence, not race proof. Exit requires lock/race, rollback and UI stale-data recovery tests. |
| BR-03 Allotment release, correction and replan | **Verified by code:** `BAC-08` rejects deallocation once BOE-converted; `BAC-10–13` coalesce durable replan requests, dispatch after commit and use state/revision/idempotency recovery paths. | **D1/D3:** object scope and plan/pool semantics; operational retry ownership is not a user-policy substitute. | Allocate → release/delete → BOE conversion/rejection → source revision → queued/running/retry/succeeded/failed/superseded replay. Assert exactly one durable request for each committed source mutation and no request after rollback. | P0/P1. Requires broker/worker failure drill in addition to mocked test evidence. Exit includes operator retry/status contract and no stale projection used to authorize debit. |
| BR-04 SION/restriction/plan rules | **Verified by code/test:** planning contracts cover rule priority, safe expression validation, declarative/database planners, restricted percentage caps, plan-line isolation and durable replan. `LicenseItemPlan` remaining fields are documented legacy snapshots, not allocation authority. | **D3:** restriction basis, shared pool/AU treatment, priority policy, exception process and cancellation/re-plan semantics. | Synthetic rule data for standard, split-percentage and unit-value strategies, overlapping source candidates, exact 100%/decimal boundaries, priority waterfall, scarce CIF/quantity, expired/ineligible inputs, manual review and repeated idempotent plan runs. | P0. D3 approval or preserve-current policy must name expected examples. Exit requires API/action role/object tests plus planner/report/ledger parity and worker recovery. |
| BR-05 BOE debit visibility, hide/restore and correction | **Verified by code/test:** `RCF-15` uses hidden marker/history and refreshes touched licences; repeat hide/restore has documented idempotent behavior. BOE row lifecycle schedules relevant recalculation on commit. | **D1/D2/D6:** object scope, balance/report meaning and audit durability/retention. | BOE attached to multiple licences: hide, repeated hide, restore, repeated restore, correction, parser failure and reconciliation link. Assert balance engines, report output, immutable/history evidence and no partial mutation/audit loss on injected failure. | P0. Exit requires direct endpoint role/object tests, concurrent transition characterization and UI explanation/confirmation/recovery evidence. |
| BR-06 Trade, payment, invoice and commercial totals | **Verified by code:** Financial balance consumes trade purchase/sale effects; trade totals/lines/payments and versioned invoice documents have separate model/service contracts. **Verified by test:** direction/missing-company validation and selected ledger/document scenarios are mapped in RTC-16 and workflow tests. | **D5:** V1 commercial-evidence scope versus a GL/bank domain; **D2** output labels; **D4/D6** public-document sharing/audit retention. | Purchase/sale/pair/correction/reversal/payment and generated invoice version fixture. Assert Decimal total/sequence and Financial engine effect, document version/access expiry, and that no result is labelled GL/bank reconciliation. | P1. Exit requires transaction/reversal, sequence race, authorised document access and report/PDF parity tests. |
| BR-07 Reconciliation consumption tracks and immutable history | **Verified by code:** `RCF-01–09` keep invoice-to-BOE and allotment-to-BOE capacity independent; create/edit/reverse use locks and version/supersede/reverse rather than destructive overwrite. `RCF-12/13` link/merge actions are atomic and protect referenced duplicates. | **D1/D2/D5/D6:** scope, balance interpretation, accounting scope and audit assurance. | Split/many-to-many allocation, cross-licence rejection, over-cap rejection, edit, reversal, external invoice, merge-protection and competing-write pack. Assert before/after snapshots and no orphaned active allocation/history on failure. | P0. Exit requires direct anonymous/wrong/partial-dual-role/object tests and public response/error/retry contracts. |
| BR-08 Report, ledger and export aggregate provenance | **Verified by code/test:** canonical ledger/report contracts and renderer parity tests distinguish DTO construction from PDF/XLSX rendering; report filters/pagination and export authorization are bounded in existing registers. | **D1/D2/D4/D5:** visibility, engine label, protected download, and accounting wording. | Reuse BR-01–07 fixture data to compare API JSON, page value, canonical DTO, PDF/XLSX/CSV totals, filter/date/page boundaries and empty/no-result output. Assert no hidden recalculation or engine substitution occurs during export. | P1. Exit requires content type/file name, denied download, worker/storage error and as-of/filter provenance evidence. |

## State-transition evidence form

For each mutation rule, retain a transition table with these fields rather
than a prose-only conclusion:

| Field | Required evidence |
| --- | --- |
| Actor / entry point | `API-*`, command, task, signal or service caller; role/execution identity. |
| Precondition | Record state, source revision, related records, lock scope and policy assumption. |
| Event/input | Typed request/event, Decimal/quantity precision and idempotency identity. |
| Persisted transition | Old/new state, created/superseded/reversed rows and audit/provenance entries. |
| Derived outputs | Named engine/rule output, rounding point, filters and as-of time. |
| Failure/recovery | Validation, transaction rollback, retry/compensation/operator action and observable API/UI state. |
| Test/fixture | Exact test identifier plus synthetic fixture version. |

## Closure ordering and non-negotiable guardrails

1. Close BR-01, BR-02, BR-04 and BR-07 before any formula, pool, allocation
   or reconciliation redesign. Their affected behavior is financially or
   entitlement consequential.
2. BR-03 and BR-05 may characterise in parallel but cannot approve a stale
   cache, job projection or history record as an alternative source of truth.
3. BR-06 and BR-08 must preserve the verified commercial scope and labelled
   data provenance until D5 decides whether broader accounting is required.
4. A successful unit test does not close a transition that also requires
   endpoint authorization, storage, broker, browser or report evidence.
5. No rule may be merged, removed or called obsolete because two current
   formulas share inputs. The D2/D3 examples and golden outputs are the
   deciding evidence.

## Reporting metrics

Report, separately for BR-01 through BR-08: rules enumerated; source/test
characterised; golden packs implemented; role/object-negative cases passing;
report/export parity passing; runtime/recovery drills passing; and rules still
awaiting owner decision. A family count must never be reported as final
business-rule closure.
