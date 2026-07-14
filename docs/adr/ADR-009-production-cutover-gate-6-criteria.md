# ADR-009 — Production Cutover Gate: 6 Simultaneous Criteria

**Status:** Accepted
**Date:** 2026-07-14

## Context

The hybrid parallel-run strategy (ADR-001) defers the production traffic
switch until the new app is demonstrably production-ready. Without explicit,
measurable criteria, "ready" becomes a judgment call subject to schedule
pressure — the most common cause of premature cutovers that introduce
production incidents.

A time-based cutover ("we go live on date X") is rejected in favour of a
quality-based cutover. All criteria must be met simultaneously, not serially.

## Decision

Production traffic switches to the new app only when **all 6 of the following
criteria are true at the same time**:

### Criterion 1 — Feature Parity (100%)

Every feature in the legacy app is implemented and manually verified in the
new app. A feature parity matrix (maintained in `docs/03-features.md`) tracks
each feature's status. No feature may be marked "deferred" or "not ported".

### Criterion 2 — Zero Data Loss

A data migration validation script compares record counts, key field values,
and computed balances between legacy-written rows and new-app-written rows for
a representative sample (minimum 30 days of production traffic). Zero
discrepancies permitted for financial fields (balances, allotment quantities,
duty amounts). Non-financial metadata discrepancies require PM sign-off.

### Criterion 3 — All Test Suites Green

All of the following pass with zero failures on the release commit:
- Backend unit tests (pytest, `apps/*/tests/unit/`)
- Backend integration tests (pytest, `apps/*/tests/integration/`)
- API regression tests (pytest, `backendv1/tests/`)
- Frontend component tests (Vitest)
- End-to-end tests (Playwright, covering the 10 critical user flows in
  `docs/07-user-flows.md`)

Coverage threshold: backend ≥ 80% line coverage, frontend ≥ 70%.

### Criterion 4 — Performance Benchmarks Met

All three of the following must hold on production-equivalent load:
- Backend API p95 latency ≤ legacy p95 latency (measured on the same endpoints
  with the same dataset)
- Frontend initial load time (LCP) improved vs legacy (target: ≤ 2.5 s on a
  standard enterprise network)
- Zero N+1 queries detected by `django-silk` or `nplusone` on any endpoint
  that serves list data

### Criterion 5 — Security Checklist Complete

- All items in `docs/08-security.md` security checklist are ticked.
- OWASP Top 10 reviewed against the new app's API surface.
- Penetration test or automated DAST scan (OWASP ZAP) run and findings
  remediated or accepted.
- JWT key management reviewed (SECRET_KEY not in git, rotation procedure
  documented, RS256 transition plan confirmed — see ADR-006).

### Criterion 6 — UAT Accepted

A minimum of 3 business users (licence officers who perform the critical
workflows daily) complete UAT covering:
- License creation, amendment, closure
- BOE submission and balance deduction
- Allotment creation and approval
- DGFT report generation
- Excel/PDF export

UAT sign-off is captured in writing (email or ticket) from each participant.

### Cutover Mechanism

When all 6 criteria are confirmed by the tech lead and PM:
1. Enable maintenance mode on legacy app (read-only banner).
2. Wait for all in-flight Celery tasks to drain.
3. Flip nginx upstream: comment out legacy upstream block, uncomment new-app
   upstream block.
4. Reload nginx (zero-downtime: `nginx -s reload`).
5. Monitor error rates for 30 minutes.
6. If error rate > 1%: flip nginx back (rollback takes < 60 seconds).

Rollback window: 30 days after cutover. After 30 days + business acceptance,
execute `rm -rf legacy/` (see ADR-010).

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Time-based cutover (fixed calendar date) | Schedule pressure routinely overrides quality gates; a fixed date has caused premature production incidents in previous projects. Quality must gate the cutover, not time. |
| Gradual traffic split (10% → 50% → 100%) | Adds canary-routing infrastructure (nginx split_clients or a load balancer with weighted upstreams); both apps must handle any user's session at any time, complicating JWT state; the added complexity is not warranted for a monolithic internal tool. |
| Partial parity cutover (migrate modules one at a time to production) | Each partial cutover creates a new nginx routing rule and a new integration point; multiplies the risk surface by the number of modules. Simpler to do one binary flip when everything is ready. |
| PM-discretion cutover (no fixed criteria) | Criteria are the mechanism that prevents "just ship it" pressure from bypassing quality. Without measurable gates, the criteria are meaningless. |

## Consequences

**Positive:**
- Teams have a clear, shared definition of "done". No ambiguity about whether
  the new app is ready.
- Binary nginx flip means rollback is always available and always fast (< 60 s).
- The 6-criteria framework is reusable for any future major migration.
- UAT by real users catches UX regressions that automated tests miss.

**Negative:**
- All 6 criteria must be met simultaneously. If Criterion 5 (security) is
  satisfied but Criterion 3 (tests) has one flaky test, the cutover is blocked.
  Teams must coordinate to close the last gaps together, which can create
  end-of-project bottleneck pressure.
- The zero-N+1 requirement (Criterion 4) is strict and may require significant
  query optimisation work to meet on endpoints that touch large related sets.
- UAT requires scheduling time with business users, who may be unavailable
  during peak licence processing periods (end of quarter). Plan UAT windows
  in advance.

## Related ADRs

- ADR-001 — Migration Strategy: Hybrid Parallel-Run
- ADR-005 — API Versioning: /api/v1/ prefix
- ADR-006 — Authentication: SimpleJWT with shared signing key
- ADR-010 — Legacy Read-Only Rule
