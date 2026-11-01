# Owner decision packets

**Requires owner approval.** These packets turn D1–D6 into approvable
business-policy decisions. They do not choose policy, authorize a production
change, or override the evidence in [decisions required](decisions-required.md).
The accountable person is deliberately recorded as a *role* until the
organisation assigns a named owner.

## Decision protocol

For every packet, the designated owner must record: selected option, effective
date, applicable companies/entities/users, exceptions, examples, retention or
transition period, approver and review date. A decision remains open if any of
those items is omitted. A later implementation must attach the decision ID to
its API, migration, UI and regression-test evidence.

| ID | Decision and problem/goal | Approval role (not a named owner) | Priority | Blocks |
| --- | --- | --- | --- | --- |
| D1 | Define permitted company/entity/object visibility and mutation scope. | Business data owner with security owner | P0 | Authorization, exports/downloads, jobs and data migrations |
| D2 | Define the meaning and presentation of Customs and Financial balances. | Trade/compliance finance owner | P0 | Entitlement, allocation, ledger and report changes |
| D3 | Define SION/restriction pool and priority semantics. | DGFT/SION domain owner | P0 | Planning, allocation and source-item changes |
| D4 | Define browser-token, download-token and capability-link posture. | Security owner with product owner | P1 | Credential/media/download migration |
| D5 | Define V1 accounting scope. | Finance/accounting product owner | P1 | Trade/report terminology and any accounting expansion |
| D6 | Define required audit assurance/durability. | Compliance/audit owner with security owner | P2 | Activity/audit logging design and operational claims |

## D1 — company/entity/object access policy

**Problem and goal.** Current evidence supports role-based access and selected
legitimate cross-company reads, but not one universal company-membership rule.
The owner must define whether the product remains an internal multi-company
workspace, introduces scoped membership for selected capabilities, or becomes
a tenant-isolated system.

- **Current evidence:** `LicenseLedgerViewPermission` is explicitly
  role-based; protected-media and invoice-link tests demonstrate selected
  cross-company behavior. See [security-critical paths](../09-traceability/security-critical-paths.md)
  and the D1 brief in [decisions required](decisions-required.md).
- **Options:** A — formally retain role-authorised internal multi-company
  visibility; B — scope selected records/capabilities to approved memberships;
  C — establish tenant isolation throughout. Recommended default: A until a
  business policy and exception list exists.
- **User story:** As an authorised operational user, I need the records I am
  permitted to work with, while confidential records outside the approved
  policy are unavailable through UI, API, files, exports and jobs.
- **Decision inputs:** company/entity ownership model; user membership source;
  allowed cross-company exceptions; superuser/auditor treatment; historical
  data treatment; export/download/audit visibility.
- **Acceptance:** Given each approved role and same/cross-company fixture,
  when it retrieves, mutates, exports, downloads or starts an asynchronous
  job, then the direct API and worker behavior matches the signed policy;
  UI hiding is not used as proof.
- **Rollback/review:** retain compatible role behavior until data/query/job
  migration and negative tests pass; review after the first scoped workflow
  rollout and after any new company relationship.
- **Affected evidence:** SCP-03/04/07, UI/API closure Q1–Q5, WF-16, D1 tests
  in the P0 register.

## D2 — Customs and Financial balance semantics

**Problem and goal.** Code and tests establish intentionally different
Customs and Financial engines with different debit/hidden-record treatment.
The owner must approve labels, consumers and governing source of truth rather
than allowing a refactor to select one formula implicitly.

- **Current evidence:** [balance/allocation contracts](../09-traceability/balance-allocation-function-contracts.md),
  [financial rules](../04-domain-and-business-rules/financial-rules.md), and
  WF-03 demonstrate separate quantized/floored outputs.
- **Options:** A — show only Customs; B — show only Financial; C — retain both
  named/provenanced outputs. Recommended default: C pending approved examples.
- **User story:** As a licence/allotment manager or compliance reviewer, I
  need every displayed balance to identify its engine, as-of point and source
  records so I do not spend or report against the wrong entitlement.
- **Decision inputs:** governing regulatory/commercial use for each screen,
  report and API; hidden/cancelled/restored/merged BOE treatment; trade sale/
  purchase treatment; rounding; correction/reversal timing; authoritative
  examples.
- **Acceptance:** Given approved golden examples including hidden, restored,
  reversed and partially consumed records, when balance/ledger/report/export
  paths run, then every labelled output equals its approved engine and no UI
  presents one output as the other.
- **Rollback/review:** retain current dual outputs during any migration;
  compare old/new outputs before changing a label or consumer. Review after a
  regulatory/business policy update.
- **Affected evidence:** BAC-01–06, RCF-01–03/15–16, WF-03/05/08/09, Q2–Q4.

## D3 — SION/restriction pool semantics

**Problem and goal.** Existing planning has percentage pools, AU/restriction
bases, free-text grouping, priorities and exceptions. The owner must define
the policy table and edge-case precedence before engineering consolidates it.

- **Current evidence:** [SION/planning contracts](../09-traceability/sion-planning-function-contracts.md)
  and WF-04 establish code/test behavior but not an approved business policy.
- **Options:** A — preserve current behavior; B — approve a formal policy
  table; C — replace after output parity. Recommended default: freeze current
  output and approve B before considering C.
- **User story:** As a planner, I need allocation eligibility and remaining
  capacity to be determined consistently from the approved norm/restriction
  policy, including competing items and partial consumption.
- **Decision inputs:** pools/groups, matching keys, priority/tie breaking,
  percentage basis, AU rules, expiry, manual override authority, correction
  and replan behavior, representative positive/negative examples.
- **Acceptance:** Given the approved policy examples and competing/allotted/
  partially consumed items, when planning or allocation runs concurrently,
  then it selects/rejects the stated candidate and records a traceable reason;
  stale candidates cannot exceed approved capacity.
- **Rollback/review:** preserve existing planner and compare golden outputs
  before cutover; review for each new SION/restriction exception.
- **Affected evidence:** SPC-01–15, BAC-06/09/10–13, WF-04/05, Q2/Q3.

## D4 — credential and protected-document posture

**Problem and goal.** The SPA uses browser-readable JWT storage; limited
query-token downloads and intentionally anonymous invoice capability links
also exist. The owner must choose the risk/compatibility posture and not infer
it solely from technical convenience.

- **Current evidence:** SCP-01–06 in [security-critical paths](../09-traceability/security-critical-paths.md);
  protected-media, query-token and invoice-link tests.
- **Options:** A — retain localStorage JWT plus scoped query-token compatibility;
  B — move to HTTP-only cookies; C — retain JWT with documented CSP/XSS
  hardening and complete authenticated blob-download cutover. Recommended
  default: complete consumer inventory, then choose A/B/C with explicit
  capability-link policy.
- **User story:** As an authenticated user, I need to access authorised
  documents without exposing credentials or making approved downloads fail.
- **Decision inputs:** browser/platform constraints; CSP/XSS assurance;
  allowed query-token routes and expiry; invoice-link recipient/expiry/view
  policy; CSRF posture; proxy/log/referrer controls; logout/revocation needs.
- **Acceptance:** Given valid, expired, revoked, malformed, wrong-role and
  cross-object cases, when a credential or document route is used, then the
  outcome matches policy, no token appears in app-generated URLs where
  prohibited, and all allowed flows have a tested consumer.
- **Rollback/review:** run dual-compatible consumers until usage is proven;
  preserve a recovery path for approved downloads. Review following security
  incidents, browser/platform changes or new public-document capability.
- **Affected evidence:** SCP-01–06, WF-01/09/10, UI-047, API Q1/Q3/Q4.

## D5 — accounting domain scope

**Problem and goal.** Trade invoices, payments and reconciliation-adjacent
records are implemented, but no verified general-ledger or bank-reconciliation
domain exists. The owner must prevent commercial evidence from being marketed
or built as unapproved accounting capability.

- **Current evidence:** WF-07/08 and [reconciliation contracts](../09-traceability/reconciliation-function-contracts.md)
  demonstrate commercial flows; WF-15 records no verified GL/bank model.
- **Options:** A — V1 covers commercial invoice/payment evidence only; B — add
  double-entry accounting; C — add bank matching. Recommended default: A
  unless finance supplies formal requirements for B/C.
- **User story:** As a trade/finance user, I need the system to label the
  commercial evidence it supports accurately, so operational reconciliation
  is not mistaken for statutory accounting.
- **Decision inputs:** chart of accounts, posting events, tax, periods/locks,
  correction/reversal rules, bank source/feed, reconciliation authority,
  reporting/audit obligations and migration/retention requirements.
- **Acceptance:** Given a trade/payment/reconciliation record, when a user
  views or exports it, then labels and totals match the approved scope; no
  unsupported GL/bank claim or workflow is exposed.
- **Rollback/review:** keep current commercial terminology and data model
  until an approved accounting design/migration exists. Review at finance
  policy change or any external-accounting integration proposal.
- **Affected evidence:** WF-07/08/15, RCF-09/16, report/API Q2/Q4.

## D6 — audit-event durability and assurance

**Problem and goal.** Generic activity logging is asynchronous/best-effort,
whereas selected reconciliation logs are transaction-scoped. The owner must
set the assurance required before either is called a complete audit trail.

- **Current evidence:** [task/activity contracts](../09-traceability/task-activity-function-contracts.md)
  distinguishes the two logging paths; D6 is not resolved by existing tests.
- **Options:** A — best-effort operational activity history; B — compliance-
  grade durable audit events. Recommended default: explicitly choose A or B
  per record class and retention need.
- **User story:** As a compliance/audit reviewer, I need an agreed level of
  evidence for consequential changes so I can determine what history is
  reliable and how long it is available.
- **Decision inputs:** regulated event classes, delivery/durability target,
  ordering, actor/impersonation, immutable fields, retention/legal hold,
  query/export access, outage/retry alerting and incident evidence.
- **Acceptance:** Given a consequential approved event and a process/broker
  interruption, when the selected assurance level applies, then the recorded
  result, loss disclosure, retry/alert and retention behavior match policy.
- **Rollback/review:** do not remove current history; label it accurately
  while durable capability is introduced. Review annually and on compliance/
  retention-policy change.
- **Affected evidence:** task/activity contracts, reconciliation logs,
  maintenance/sync jobs, WF-13, API Q1/Q2/Q5.

## Handoff and sequencing

These packets are product requirements, not implementation design. The
technical lead uses signed packets to schedule T01/T02, then attaches the
chosen decision to affected milestones, API/route contracts and test fixtures.
Until then, the recommended defaults are only preservation-safe interim
postures, not approved policy.
