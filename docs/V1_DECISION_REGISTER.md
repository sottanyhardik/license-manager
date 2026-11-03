# V1 Decision Register

Companion to [V1_MASTER_TRACKER.md](./V1_MASTER_TRACKER.md). Every decision that changes scope, approach, data or sequencing is recorded here.

Status: `PROPOSED` · `APPROVED` · `APPROVED (with controls)` · `DECIDED (autonomous)` · `BLOCKED (business decision)` · `SUPERSEDED`.

| ID | Date | Decision | Reason | Status | Approved by |
|---|---|---|---|---|---|
| DEC-001 | 2026-11-01 | V1 work happens on `feature/version-4`, created from `develop` (the PR target). | `develop` is the integration branch; `master` is released code. | APPROVED | User |
| DEC-002 | 2026-11-01 | Phases run in the V1 brief's order. Findings are documented before implementation. | Brief requires Explore and Critique before implementation. | APPROVED | User |
| DEC-003 | 2026-11-01 | **Unified Company Master.** Customer, buyer, supplier, exporter, importer, broker, agent and service provider are roles on one `Company`. No separate Customer master. Internal legal entities (e.g. Labdhi Global LLP, Labdhi Mercantile LLP) stay distinguishable from external counterparties. Uncertain duplicates are reported, never auto-merged. | One company = one master record = many roles. | APPROVED (revised) | User |
| DEC-004 | 2026-11-01 | Repository cleanup with safety controls: classify, check references (imports, scripts, CI, deployment, docs), archive useful material, remove only with evidence. Never remove migrations, production config, operational scripts or user data. Each action is recorded in the cleanup register. | Clutter hides real code, but deletions are costly to reverse. | APPROVED (with controls) | User |
| DEC-005 | 2026-11-01 | Documentation is modernized and kept accurate. Existing docs are audited before replacement; useful content is migrated or archived before removal. New V1 documents record only implemented behaviour. | Brief rule: no deletion until audited and migrated. | APPROVED (with controls) | User |
| DEC-006 | 2026-11-01 | Phase 2 starts with Licence Management, including the canonical balance engine and the Company Master. | Licence is the foundation; other modules consume its balances. | APPROVED | User |
| DEC-007 | 2026-11-01 | The balance engine must be single-source. Correct it in place rather than building a second one. Before any change to a balance formula, produce a before/after reconciliation on real data, because the change moves reported numbers. | Brief §4.3. The data run (ISS-016) shows the single-source rule is currently violated. | DECIDED (autonomous) — the principle is the brief's; the in-place choice is this pass's call | — |
| DEC-008 | 2026-11-01 | Known engine gaps are recorded as `xfail(strict=True)` with the issue ID, not silenced. The xfail is removed when the issue is fixed. Scenario F is `skip` until the operation exists. | Keeps the gap visible and makes the fix verifiable. | DECIDED (autonomous) | — |
| DEC-009 | 2026-11-01 | Allotment cancellation (ISS-010): replace hard delete with reversal. Requires a data-retention and rollback plan before implementation. | Hard delete of financial rows is destructive to production data. | PROPOSED — needs rollback plan first | — |
| DEC-010 | 2026-11-01 | **Which balance is "available" CIF for allotment and reporting.** Blocked until the business answers the questions below. Recommended shape, once answered: one named figure per concept (e.g. Customs balance for the regulatory ledger, Financial available balance for allotment), each defined by one function. Other variants are retired or renamed. | ISS-016: five functions disagree on most licences. The brief does not define the hidden-BOE, purchased-CIF and trade rules the code uses. | BLOCKED (business decision) | — |

## DEC-010 — questions for the business

These are needed before the balance engine can be consolidated. Answers should cite the rule's source (regulation, DGFT notice, or internal policy).

1. **Allotment capacity.** When an allotment checks available CIF, which figure must it use: the financial available balance, the customs balance, or another one?
2. **Unused reservation (ISS-008).** When a BOE draws part of an allotment, does the unused remainder stay reserved for that customer until the allotment is cancelled or expires? Or is it released to the licence pool?
3. **Previous-owner utilisation.** Do hidden BOEs and purchased CIF (the code calls this "Previous Owner Utilisation") reduce what is available to our allotments? If yes, is it the same reduction for allotments and for reporting?
4. **Trade-linked BOEs.** Should BOEs already invoiced through a SALE trade count as utilised, as the trade-exclusion logic assumes?
5. **Over-utilisation (ISS-009).** Should the system reject a BOE that would push utilisation above credit, or allow an explicit exception with a recorded reason?

Until these are answered, no balance formula will be changed. Work continues on items that do not depend on them: Company Master design and the quantity-scenario tests. Cancellation work is gated separately by DEC-009 (rollback plan).
