# PHASE 2 — Write-Side Consolidation Tracking

**Status:** INITIATED - Audit in progress  
**Date:** 2026-08-17  
**Mode:** Autonomous multi-agent execution

---

## PHASE 2 OBJECTIVE

Replace norm-specific runtime planners with single generic DB-driven engine.

```
CURRENT (To be replaced):
    SionPlanningExecutionService
        ↓ (dispatches to)
    E1_plan / E5_plan / E126_plan / E132_plan / A_plan / PP_plan

TARGET:
    SionPlanningExecutionService
        ↓ (uses)
    Generic Matcher
    Generic Pricer
    Generic Allocator
    Generic Splitter
        ↓ (driven by)
    DB SionPlanningRule (configuration)
        ↓ (persists to)
    LicenseItemPlan
```

---

## EXECUTION PHASES

### Phase 2A: Audit & Extraction (✅ COMPLETE)

**Audit Results:** COMPLETE  
- [x] Write-side caller inventory — 8 active callers identified
- [x] Current service chain — Hybrid adapter pattern with transitional dispatch
- [x] DB rule coverage — E1/E5 migrated; E126/E132/A3627/PP still hard-coded
- [x] Legacy planner references — 5 planners active (E1, E5, E126, E132, A3627)
- [x] Generic capabilities audit — Infrastructure complete; E126+ not yet using it
- [x] Test coverage — 16 test files; strong coverage on E1/E5; E126/E132 limited

**Key Finding:** E1/E5 already partially migrated to DB rules + adapters. E126/E132/A3627 still use PlannerFactory hard-coded dispatch. Generic infrastructure exists but underutilized.

**Semantic Extraction Agents:** LAUNCHED (2 agents, running in parallel)
- [ ] Agent E126/E132: E126/E132 semantics extraction
- [ ] Agent A/PP: A-series/PP semantics extraction

### Phase 2B: Semantic Extraction (PENDING)

Parallel agents:
- [ ] AGENT E1: E1 semantics extraction
- [ ] AGENT E5: E5 semantics extraction
- [ ] AGENT E126: E126/E132 semantics
- [ ] AGENT APP: A-series/PP semantics
- [ ] AGENT GENERIC: Generic architecture

### Phase 2C: Generic Architecture Build (PENDING)

- [ ] Matcher: HSN, Product, AND/OR/NOT conditions
- [ ] Pricer: Fixed, max, range, calculated strategies
- [ ] Allocator: Quantity/CIF allocation per rule
- [ ] Splitter: Multi-output split logic
- [ ] Executor: Waterfall, priority, remainder

### Phase 2D: DB Configuration Verification (PENDING)

- [ ] E1 rule coverage
- [ ] E5 rule coverage
- [ ] E126 rule coverage
- [ ] E132 rule coverage
- [ ] A-series rule coverage
- [ ] PP rule coverage

### Phase 2E: Write Callers Migration (PENDING)

- [ ] /planning endpoint
- [ ] /api/sion-planning-rules/plan-sion/
- [ ] /api/sion-planning-rules/plan-license/
- [ ] Auto Plan button
- [ ] Force Re-plan button
- [ ] python manage.py plan_norms

### Phase 2F: Golden Comparison (PENDING)

- [ ] E1 shadow test
- [ ] E5 shadow test
- [ ] E126 shadow test
- [ ] E132 shadow test
- [ ] A shadow test
- [ ] PP shadow test

### Phase 2G: Legacy Deletion (PENDING)

- [ ] E1 module delete
- [ ] E5 module delete
- [ ] E126 module delete
- [ ] E132 module delete
- [ ] A module delete
- [ ] PP module delete
- [ ] Forbidden-reference guard

### Phase 2H: Final Verification (PENDING)

- [ ] Backend tests
- [ ] Frontend tests
- [ ] Real-data reconciliation
- [ ] Django check
- [ ] Read-path regression
- [ ] Concurrency verification
- [ ] Permission verification

---

## BLOCKERS & RISKS

| Risk | Mitigation | Status |
|------|-----------|--------|
| Generic engine incomplete | Parallel semantic extraction | In progress |
| DB rules insufficient | Configuration audit + expansion | Pending |
| Golden comparison mismatch | Accept corrected behavior | Pending |
| Concurrent planning collision | Transaction/locking audit | Pending |
| Legacy caller isolation | Systematic migration | Pending |

---

## EXPECTED OUTCOMES

**Write-side architecture after Phase 2:**

```
Auto Plan / Force Re-plan / /planning / CLI
        ↓
    Generic Execution Service
        ↓ (reads)
    DB SionPlanningRule
        ↓ (executes)
    [Matcher → Pricer → Allocator → Splitter]
        ↓ (persists to)
    LicenseItemPlan
        ↓ (reads by)
    GET endpoints / UI / Reports / Exports (Phase 1 frozen)
```

**All norms:** E1, E5, E126, E132, A, PP use SAME engine, configured in DB.

**Legacy modules:** DELETED

**Forbidden:** E1_plan, E5_plan, E126_plan, E132_plan, A_plan, PP_plan in production code.

---

## FREEZE GATE CHECKLIST

**Only declare complete when ALL pass:**

- [ ] All norms use generic DB engine
- [ ] Auto Plan uses generic engine
- [ ] Force Re-plan uses generic engine
- [ ] /planning uses generic engine
- [ ] plan_norms uses generic engine
- [ ] No production legacy planner calls
- [ ] Legacy modules deleted
- [ ] No fallback planner logic
- [ ] Forbidden-reference guard passes
- [ ] Phase 1 read paths remain locked
- [ ] Item Pivot reads only LicenseItemPlan
- [ ] Reports read only LicenseItemPlan
- [ ] PDF/Excel read canonical data
- [ ] GET endpoints side-effect free
- [ ] Models/data preserved
- [ ] Golden tests pass
- [ ] Real-data reconciliation passes
- [ ] Backend tests pass
- [ ] Frontend tests pass
- [ ] Django check passes

---

## COMMITS (In Progress)

- `PHASE_2_AUDIT` — Write-side assessment
- `PHASE_2_SEMANTICS` — Extract all planner logic
- `PHASE_2_GENERIC_ENGINE` — Build DB-driven execution
- `PHASE_2_MIGRATION` — Cut over callers
- `PHASE_2_DELETION` — Remove legacy modules
- `PHASE_2_VERIFICATION` — Full test suite
- `PHASE_2_FREEZE` — Final sign-off

---

## NEXT STEP

Await audit completion.

Audit will inform parallel semantic extraction agents.
