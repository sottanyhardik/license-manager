# Implementation roadmap and estimate

These are planning ranges based on static evidence, not commitments. One experienced developer with AI assistance is assumed; a small team reduces elapsed time only after contracts and integration gates are in place.

| Phase | Deliverable/dependencies | One developer (low/likely/high person-days) | QA/domain | Confidence |
|---|---|---:|---|---|
| 0 | Baseline, deployed-version confirmation, characterisation, route/API/defect register | 10/18/30 | 5/8/15 QA | Medium |
| 1 | Tenant decision, containment/isolation tests, critical correction contracts | 25/45/75 | 15/30/50 QA + business | Low-medium |
| 2 | SSOT balance/restriction façade and caller migration | 35/65/110 | 25/45/75 QA + DFIA review | Low |
| 3 | UI foundation/high-risk workflow redesign | 25/45/80 | 15/30/50 QA/UX | Medium |
| 4 | Versioned restriction pools, explainable planning, concurrency | 35/70/120 | 30/55/90 QA + policy review | Low |
| 5 | Double-entry accounting foundation/subledgers | 70/120/200 | 45/80/140 QA + CA/tax | Low |
| 6 | Bank statement import/matching/reconciliation | 45/80/140 | 30/55/95 QA + banking | Low |
| 7 | Advanced accounting/tax/Tally scope selected by management | 60/130/260 | 45/100/200 QA + CA | Low |
| 8 | SaaS hardening/release readiness | 35/65/110 | 30/60/100 QA/SRE/security | Medium |

Likely total for phases 0–6: **443 developer days**, **278 QA days**, excluding selected phase 7 and external domain decisions. A small 3–4 person delivery team can parallelise UI, test harness and bounded implementation after phases 0–2, but should budget 15–25% integration/review overhead; critical path remains tenant decision → authoritative restriction behaviour → ledger foundation → bank reconciliation.

## Work-package acceptance

- Tenant: negative cross-tenant API/query tests pass, historical records classified, scoped writes enforced.
- SSOT/restrictions: golden and concurrency results match preview/commit/report; unresolved configuration blocks visibly.
- UI: keyboard/a11y/responsive E2E and state/error behaviour meet agreed design system.
- Accounting: posted journals immutable and balanced; subledger/trial balance reconciles.
- Bank: import duplicate controls, deterministic explainable matching, reviewed completion/reopen audit and book/statement difference are tested.

## Management decisions

1. Internal multi-company or external tenant-isolated SaaS? Which legal entities/users/scale?
2. Authoritative base/scope/group/precedence/override/AU meaning for every restriction.
3. Required first-release accounting, tax review, Tally migration and statement formats.
4. Approval/audit/period-lock policy and production release authority.
5. Investment capacity, timeline and acceptance/risk tolerance.
