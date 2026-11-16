# LICENSE MANAGER — MASTER 30-MODULE ENGINEERING AUDIT, DOCUMENTATION CLEANUP & IMPLEMENTATION

**Status:** MASTER EXECUTION FRAMEWORK (ready to activate)

**Audience:** Claude Code / Senior Engineering Mode

**Authority:** Principal Architect / 30+ years enterprise systems experience

**Purpose:** Systematic, controlled audit and modernization of entire License Manager system across all 30 business modules.

---

## PHILOSOPHY

This is NOT a rewrite. This is a controlled **audit-first, evidence-based, documentation-verified, single-module-at-a-time engineering program**.

**Key principles:**

1. **Audit documentation before application code** — the audit/review layer itself may be stale or contradictory.
2. **Evidence before conclusions** — never assume code is correct or wrong.
3. **One module at a time** — no combining, no parallel work, no "while I'm here" refactoring.
4. **Freeze gates between modules** — each module must pass adversarial review before proceeding.
5. **Preserve audit evidence** — historical findings remain even after fixes.
6. **Cross-module dependencies are explicit** — refactoring shared code requires all-consumer analysis.
7. **Business semantics are sacred** — never silently reconcile financial/license/inventory data.
8. **Backend is authoritative** — frontend validation is convenience, not security.

---

## EXECUTION SEQUENCE

### PHASE A — Repository + Documentation Audit

Before touching any application code:

1. Find all `.md`, audit, architecture, design, plan, TODO, evidence, review, migration, specification documents.
2. Determine status: CURRENT, OUTDATED, DUPLICATE, CONTRADICTORY, PARTIALLY_VALID, ARCHIVAL, UNUSED, UNKNOWN.
3. For every document: verify it against current code.
4. Record all contradictions, obsolete references, unresolved TODOs.
5. Identify documents that are outdated, misleading, or now unnecessary.

**Deliverable:** `audit_evidence/documentation_inventory.md`

### PHASE B — Documentation Cleanup & Canonicalization

1. Merge overlapping documentation.
2. Remove contradictions.
3. Update references to match current code.
4. Establish one canonical source of truth per topic (architecture, business rules, API, etc.).
5. Separate CURRENT documentation from HISTORICAL evidence.
6. Delete ONLY documentation proven to be unnecessary.

**Deliverable:** `audit_evidence/CANONICAL_DOCUMENTATION_MAP.md`

### PHASE C — Create Module Register

Create: `audit_evidence/MODULE_REGISTER.md`

Track all 30 modules through their lifecycle: NOT_STARTED → INVESTIGATING → AUDITED → FIX_PLAN_READY → IMPLEMENTING → TESTING → VERIFYING → FROZEN

### PHASE D–AG — Process Modules 01–30 One At A Time

For EACH module:

**STEP 1 — Full Module Audit**
- Repository context (files, models, views, services, APIs, hooks, components, tests)
- End-to-end trace (UI → API → Service → Database)
- Business logic audit (every rule, every edge case)
- Database audit (fields, FKs, constraints, indexes, race conditions)
- API audit (endpoints, auth, validation, IDOR, permissions)
- Security audit (auth, JWT, CSRF, XSS, privilege escalation)
- Frontend audit (components, hooks, forms, validation, stale data)
- Testing audit (coverage, false-confidence tests, missing cases)
- Performance audit (N+1, indexes, caching)
- Architecture audit (duplication, bloat, inconsistencies)

**STEP 2 — Adversarial Testing**
- Try to break the module
- Test invalid input, concurrent requests, stale data, deleted objects
- Test API bypass, unauthorized access, partial failures

**STEP 3 — Find & Classify**
- Document every finding with: ID, Severity, Area, Evidence, Root Cause, Impact, Recommended Fix

**STEP 4 — Create Fix Plan**
- For every fix: WHY, WHAT, FILES, RISK, EXPECTED BEHAVIOR, TEST REQUIRED
- Record in: `audit_evidence/module-XX/11_fix_plan.md`

**STEP 5 — Implement Justified Fixes**
- Smallest safe changes
- Preserve valid business behavior
- Add regression tests
- No opportunistic refactoring of unrelated modules
- Update only affected canonical documentation

**STEP 6 — Test & Verify**
- Run formatter, linter, type checks, backend tests, API tests, frontend tests
- Review git diff
- Verify no unrelated behavior changed

**STEP 7 — Adversarial Post-Fix Review**
- Act as second independent engineer
- Ask: "Did the fix itself introduce a new bug?"
- Check regression, race conditions, permissions, backwards compatibility

**STEP 8 — Update Documentation**
- Update canonical docs affected by changes
- Preserve historical evidence
- Remove ONLY proven-unnecessary documentation

**STEP 9 — Freeze Module**
- Audit complete
- Findings classified
- Justified fixes implemented
- Regression tests added
- Tests passed
- Adversarial review complete
- Documentation updated
- Git diff reviewed
- No known CRITICAL issues remain
- No unresolved HIGH issues remain (unless explicitly accepted risk)

Update: `audit_evidence/MODULE_REGISTER.md`

### PHASE FINAL — System-Wide Verification

After MODULE 30 is frozen:

1. Verify all 30 modules frozen
2. Cross-module dependencies resolved
3. No contradictory documentation
4. No obsolete critical code
5. No unresolved critical/security findings
6. All tests passing
7. Builds passing
8. No accidental changes

Create: `audit_evidence/FINAL_SYSTEM_VERIFICATION.md`

Create: `audit_evidence/FINAL_AUDIT_REPORT.md`

Answer: **Would a 30-year principal engineer approve this for production?**

---

## THE 30 MODULES

Process in order. Do not skip. Do not combine.

| # | Module | Scope |
|---|--------|-------|
| 01 | Login / Authentication | Auth flow, JWT, refresh tokens, logout, token revocation |
| 02 | User & Permission Management | User roles, permissions, RBAC, login history |
| 03 | Company / Organization | Company master, multi-tenancy, company isolation |
| 04 | Dashboard | Summary views, card aggregation, metrics |
| 05 | License Master | License creation, import, master data |
| 06 | License Ledger / Balance | Balance calculation, available qty, CIF tracking |
| 07 | License Items | Import item lines, HS codes, quantities per item |
| 08 | Plan Management | Auto-planning, priority logic, planning rules |
| 09 | Allotment | Allotment creation, company allocation, lifecycle |
| 10 | Allotment Items | Line-item allocation, quantity constraints, versioning |
| 11 | Invoice | Invoice creation, flow, status |
| 12 | Invoice Items | Invoice line items, quantities, mapping |
| 13 | BOE | Bill of Entry, usage tracking, reconciliation |
| 14 | BOE Allocation | BOE-to-allotment linkage, auto-increase, shortfall |
| 15 | Shipping Bill | Shipping bill creation, export flow |
| 16 | Export / Shipping Bill Allocation | Export item allocation, SB tracking |
| 17 | DFIA Transfer | Inter-company transfer of entitlements |
| 18 | Import / Purchase | Purchase order flow, receipt, integration |
| 19 | SION / Norms | Norms master, item norms, calculations |
| 20 | E1 Planning | E1-specific planning rules, norms application |
| 21 | E5 Planning | E5-specific planning rules, validity |
| 22 | E132 Planning | E132-specific planning rules |
| 23 | Reports | General reporting infrastructure |
| 24 | Item Pivot | Cross-item pivot view, balance aggregation |
| 25 | License Ledger Reports | Ledger detail, balance history, drill-down |
| 26 | Document Management | File upload, storage, retrieval, permissions |
| 27 | Notifications | Email, SMS, in-app notifications |
| 28 | Background Jobs / Celery | Async tasks, scheduling, retry logic |
| 29 | Audit Logs | System audit trail, mutation history |
| 30 | Settings / Configuration | Feature flags, configuration parameters |

---

## ABSOLUTE RULES

1. **Evidence before conclusions.** Never assume without proof.
2. **Code before documentation.** If they conflict, investigate the code.
3. **Business behavior before refactoring.** Preserve correctness.
4. **Security before convenience.** Never weaken auth/permissions.
5. **Data integrity before performance.** License/financial data is sacred.
6. **Backend is authoritative.** Frontend validation is convenience only.
7. **Never silently reconcile financial/license/inventory data.** Manual fixes visible, not automatic.
8. **Never fabricate verification.** If a test didn't run, say so.
9. **Never delete without proof.** Deletion requires evidence the code is unused.
10. **Never modify unrelated modules.** Document cross-module dependencies instead.
11. **Never change public API contracts casually.** All consumers must be updated.
12. **Never remove audit evidence.** Preserve historical findings even after fixes.
13. **Never assume documentation is correct.** Verify against code.
14. **Never assume code is wrong.** Prove it before fixing.
15. **Do not optimize prematurely.** Measure before optimizing.
16. **Do not introduce architecture for architecture's sake.** Prefer smallest safe improvement.
17. **Every bug fix should have regression coverage.** Add tests.
18. **Review git diff after every module.** Verify no accidental changes.
19. **Freeze each module before proceeding.** No module combines with the next.
20. **Do not skip modules.** Process all 30 sequentially.
21. **Do not combine multiple modules into one batch.** One at a time.
22. **Do not proceed if the current module has an unresolved blocker.** Document and stop.
23. **If uncertain, STOP and document the uncertainty.** Never guess.

---

## HOW TO START

When ready to begin, invoke Claude Code with:

**"Start the License Manager 30-module engineering program now.**

**First perform Phase A and Phase B only:**

1. Audit all repository documentation.
2. Find all existing audit/review/design/architecture/plan/TODO/evidence documents.
3. Determine what is current, obsolete, duplicated, contradictory, archival, or unnecessary.
4. Cross-check documentation against actual code.
5. Update/merge documentation where required.
6. Remove only documentation proven to be unnecessary.
7. Establish canonical documentation structure.
8. Create/update the master module register.
9. Create the cross-module dependency register.

**Do NOT start application-code fixes yet.**

Report:
- documents reviewed
- documents updated
- documents merged
- documents archived
- documents deleted
- contradictions found
- canonical sources established
- important risks discovered

Then stop and wait for authorization to begin MODULE 01."

---

## RECURRING COMMAND (after Phase A/B)

For each subsequent module:

**"Proceed with the next module in MODULE_REGISTER.md.**

**Follow the complete controlled lifecycle:**

**AUDIT → EVIDENCE → FINDINGS → FIX PLAN → IMPLEMENT → TEST → ADVERSARIAL REVIEW → DOCUMENTATION UPDATE → GIT DIFF REVIEW → FREEZE**

**Do not skip any phase.**

**Do not combine modules.**

**Do not modify unrelated functionality.**

**Do not silently change business semantics.**

**Do not silently reconcile license, financial, inventory, balance, planned, or allocated quantities.**

**Use existing canonical documentation and previous module evidence.**

**If a cross-module dependency is discovered, document it in CROSS_MODULE_DEPENDENCIES.md rather than opportunistically refactoring another module.**

**Do not mark the module FROZEN until required tests and post-fix verification actually pass.**

**Begin with the next NOT_STARTED module and continue only until that single module is FROZEN."**

---

## DELIVERABLES

After Phase A/B:
- `audit_evidence/documentation_inventory.md`
- `audit_evidence/CANONICAL_DOCUMENTATION_MAP.md`
- `audit_evidence/MODULE_REGISTER.md` (empty, ready to populate)
- `audit_evidence/CROSS_MODULE_DEPENDENCIES.md` (empty, ready to populate)

After each module:
- `audit_evidence/module-XX/01_audit_summary.md`
- `audit_evidence/module-XX/02_findings.md`
- `audit_evidence/module-XX/03_fix_plan.md`
- `audit_evidence/module-XX/04_implementation.md`
- `audit_evidence/module-XX/05_test_results.md`
- `audit_evidence/module-XX/06_adversarial_review.md`
- Updated canonical documentation files
- `audit_evidence/MODULE_REGISTER.md` (module marked FROZEN)

After Module 30:
- `audit_evidence/FINAL_SYSTEM_VERIFICATION.md`
- `audit_evidence/FINAL_AUDIT_REPORT.md`

---

## PRODUCTION READINESS QUESTION

At the end of all 30 modules, answer:

**WOULD A 30-YEAR PRINCIPAL ENGINEER APPROVE THIS SYSTEM FOR PRODUCTION?**

Options:
- **YES** — system is production-ready
- **NO** — system has unresolved critical or security issues
- **YES WITH CONDITIONS** — system is ready with documented caveats

Provide exact reasoning.

---

## THIS IS A CONTROLLED ENGINEERING PROGRAM

This is not a rewrite.

This is not a quick fix.

This is a disciplined, auditable, evidence-based modernization of a mission-critical financial/license/inventory system.

**Each module must be frozen before the next begins.**

**No uncontrolled scope creep.**

**No "while I'm here" refactoring.**

**Evidence preserved throughout.**

**Audit trail maintained.**

---

**Status:** Ready to activate when user authorizes.

**Next step:** Invoke Phase A when ready.
