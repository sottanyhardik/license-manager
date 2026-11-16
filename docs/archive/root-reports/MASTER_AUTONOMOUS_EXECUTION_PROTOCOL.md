# LICENSE MANAGER — MASTER AUTONOMOUS ENGINEERING EXECUTION PROTOCOL

**Status:** OPERATIONAL (definitive, permanent)

**Authority:** Principal Engineer / Staff Architect / QA Lead / Security Engineer / UI/UX Lead

**Scope:** All module work, all future changes, all modernization cycles

---

## CORE MISSION

You are responsible for making the License Manager system:

* simpler;
* more maintainable;
* more secure;
* more testable;
* more consistent;
* more performant;
* more accessible;
* more polished;
* easier to extend;
* harder to misuse.

**Architectural principle:**

> **ONE SOURCE OF TRUTH FOR ONE FUNCTIONALITY**

---

## 33 ABSOLUTE OPERATING RULES

### RULE 1 — User controls module execution

The user will tell you which module to work on.

Example: "Fix Module 08"

Only that module becomes active.

Do not automatically start another module after completing it.

After the module is frozen, **STOP and wait for the user's next module**.

---

### RULE 2 — Audit before modifying

Never blindly edit code.

For the selected module:

```
DISCOVER → AUDIT → UNDERSTAND → PLAN → FIX → CONSOLIDATE → TEST
→ REGRESSION AUDIT → VERIFY → COMMIT → FREEZE
```

---

### RULE 3 — Fix completely, not partially

Within the selected module, identify and address all meaningful:

* bugs
* architectural problems
* duplicate implementations
* incorrect business logic
* validation problems
* security problems
* performance problems
* test gaps
* UI/UX problems
* accessibility problems
* dead code
* unnecessary complexity
* inconsistent behavior

Do not expand into unrelated modules unless required by a dependency.

---

### RULE 4 — One source of truth

Whenever similar functionality exists in multiple locations:

```
Implementation A
Implementation B
Implementation C
```

Find the correct canonical implementation.

Then:

```
SELECT CANONICAL → MIGRATE CONSUMERS → REMOVE DUPLICATES → UPDATE TESTS → VERIFY
```

Examples: business rules, calculations, validation, permissions, constants, status logic, API calls, serializers, components, hooks, forms, tables.

---

### RULE 5 — Code simplification rule

Continuously look for opportunities to reduce unnecessary:

* lines of code
* functions
* files
* components
* hooks
* state
* props
* conditionals
* queries
* validators
* serializers
* duplicated styles
* duplicated business rules

**However:** Never sacrifice clarity, correctness, type safety, testability, or maintainability merely to reduce LOC.

Target: **less code + better architecture + clearer ownership**

---

### RULE 6 — Questions to the user

Operate autonomously when the correct engineering decision is reasonably obvious.

Do NOT ask about: formatting, naming, obvious bugs, duplicate code, testing, accessibility, UI improvements, dead code, refactoring, standard architecture.

Ask ONLY when:

1. a business rule is genuinely ambiguous
2. two valid product behaviors are possible
3. production data could be materially changed
4. a destructive migration is required
5. a locked rule conflicts with another requirement
6. an external integration contract is unclear
7. a security/compliance decision requires explicit authorization

When asking: ask one focused question, explain the conflict, show evidence, provide recommended option.

If no genuine decision is required: **Proceed autonomously.**

---

### RULE 7 — D1: Company Boundary

Company boundary applies to: **Allotment**

NOT independently to: **Allotment Items**

Do not introduce per-item company-boundary behavior that contradicts this rule.

---

### RULE 8 — D2: CIF Validation

CIF must be derived from: **quantity × price**

Use: Decimal, ROUND_HALF_UP, no floating-point business calculation.

---

### RULE 9 — D3: Approval Gate

Approval gate is: **INFORMATIONAL ONLY**

It must not accidentally become a blocking authorization gate.

---

### RULE 10 — D4: Decimal Precision

Use:
* Quantity → 3 decimal places
* Price → 2 decimal places
* CIF → 2 decimal places

Maintain consistently across database, backend, API, frontend, calculations, validation, display.

---

### RULE 11 — D5: Allotment Quantity Constraints

Both constraints are mandatory and independent:

1. **per-line maximum quantity**
2. **total maximum quantity**

Never remove, merge, weaken, or bypass either constraint.

---

### RULE 12 — Frozen baseline

Respect existing frozen work:

* **Phase A.1** — Completed/frozen (commit 9364d0f0)
* **Allotment Quantity Constraints** — Locked (commit 5c660a31)
* **Master 30-Module Program** — Locked (commit 55d551a4)

Do not casually rewrite frozen work.

If current code differs from frozen baseline: investigate, determine legitimacy, preserve locked behavior unless necessary correction is proven.

---

### RULE 13 — Module execution protocol: Identify scope

Determine:

* module name
* module boundaries
* backend files
* frontend files
* models
* services
* APIs
* routes
* permissions
* tests
* documentation
* dependencies
* existing frozen status

---

### RULE 14 — Module execution protocol: Full module audit

Audit backend: models, services, serializers, views, permissions, validators, transactions, database operations.

Audit frontend: routes, pages, components, hooks, API layer, forms, state, loading, errors, accessibility.

Audit architecture: duplicated functionality, competing sources of truth, dead code, stale code, unnecessary abstractions, hidden business logic.

---

### RULE 15 — Source-of-truth audit

For every major functionality ask: "Where is the authoritative implementation?"

Build a mental map:

```
Business Rule
    ↓
Canonical Domain Service
    ↓
API
    ↓
Canonical Frontend Data Layer
    ↓
Canonical UI Component
```

Consolidate competing implementations.

---

### RULE 16 — Backend rules

Business logic must have clear ownership.

Prefer:

```
API → Application/Service Layer → Domain Logic → Query/Data Layer → Database
```

Audit: transactions, race conditions, N+1 queries, indexes, constraints, permissions, validation, Decimal handling, error handling, concurrency, atomicity.

---

### RULE 17 — Financial/Quantity Calculation Rule

Search for `float` and `round(` in business calculations.

Use Decimal consistently.

Verify: quantity precision, price precision, CIF precision, rounding, serialization, database storage, frontend display.

Never silently introduce floating-point business calculations.

---

### RULE 18 — API rules

Audit every API used by the module.

Check: authentication, authorization, validation, serialization, status codes, errors, pagination, filtering, sorting, performance, naming, consistency.

If two endpoints provide substantially the same functionality, determine whether one should become canonical.

---

### RULE 19 — Frontend rules

Look for duplicated: components, hooks, API calls, forms, schemas, validation, tables, loading states, error states, empty states, formatting, permissions, state management.

Consolidate when appropriate.

Do not create another component when an existing canonical component should be reused.

---

### RULE 20 — Login UI/UX rule

When Login is the active module, treat it as a flagship UI/UX surface.

Target: **Linear / Stripe / Vercel quality**

Audit and improve: visual hierarchy, spacing, typography, branding, form layout, input states, focus states, password visibility, validation, errors, loading, duplicate submission prevention, keyboard navigation, accessibility, responsive layout, mobile behavior, authentication redirects, expired sessions, logout, unauthorized states.

Do not merely change colors. Make the complete experience polished and production-grade.

---

### RULE 21 — Design system rule

Create or strengthen canonical UI primitives.

Prefer reusable components: Button, Input, Select, Combobox, FormField, Badge, Dialog, Drawer, Dropdown, Tabs, Table, Pagination, EmptyState, LoadingState, ErrorState, PageHeader, Card, Stat, Toast.

If multiple versions exist without legitimate semantic difference: consolidate them.

---

### RULE 22 — Table rule

Tables are important enterprise UI infrastructure.

Standardize: columns, sorting, filtering, pagination, selection, actions, loading, empty states, errors, formatting, responsive behavior.

Do not build every table independently if shared infrastructure is appropriate.

---

### RULE 23 — Form rule

Use one canonical form architecture.

Standardize: validation, field rendering, errors, submission, loading, server errors, schemas, mutation handling.

Avoid duplicated form logic.

---

### RULE 24 — Security rules

Audit: authentication, authorization, object-level access, CSRF, CORS, sessions/tokens, sensitive data, error leakage, secrets, file handling, injection risks, logging.

Security issues take priority over cosmetic refactoring.

---

### RULE 25 — Performance rules

Check backend: N+1, unnecessary queries, expensive serialization, inefficient aggregation, missing indexes, duplicate queries.

Check frontend: duplicate requests, request waterfalls, unnecessary renders, excessive state, unnecessary effects, unstable query keys, oversized components.

Do not add premature optimization. Fix measured or clearly identifiable problems.

---

### RULE 26 — Dead code rule

Search for: unused imports, unused functions, unused components, unused hooks, unreachable code, obsolete routes, dead endpoints, stale files, commented-out code, obsolete compatibility layers.

Remove dead code when its status is established.

Never delete uncertain production functionality without investigation.

---

### RULE 27 — Testing rule

Every meaningful change must be tested.

Run relevant backend: unit tests, domain/service tests, API tests, permission tests, validation tests, transaction tests.

Run relevant frontend: component tests, route tests, form tests, hook tests, lint, typecheck, build.

Test important real user flows.

Never claim PASS unless the test/check was actually executed successfully.

---

### RULE 28 — Regression rule

After fixing the module:

```
RUN TESTS → SEARCH FOR OLD IMPLEMENTATIONS → SEARCH FOR BROKEN REFERENCES
→ CHECK DEPENDENCIES → RUN TESTS AGAIN
```

The second audit is mandatory.

---

### RULE 29 — Cross-module change rule

If fixing the active module requires another module to change:

1. identify the dependency
2. explain why it is necessary
3. make the smallest necessary change
4. do not perform unrelated cleanup
5. test the dependency
6. test the active module
7. record the cross-module change

Do not turn a dependency into a broad refactoring opportunity.

---

### RULE 30 — Freeze rule

After the selected module is completely fixed and verified, mark it: **🔒 FROZEN**

Record: Module, Status, Commit, Date, Scope, Major fixes, Canonical sources, Code consolidated, Tests, Dependencies, Known limitations.

A frozen module must be treated as a protected boundary.

---

### RULE 31 — Frozen module rule

After freezing:

DO NOT modify the module for: stylistic preference, optional refactoring, cosmetic cleanup, naming preference, unrelated improvements, personal architectural preference.

Only reopen for: bug, regression, security issue, data correctness, new requirement, required dependency, serious performance problem, unavoidable architectural correction.

---

### RULE 32 — Reopen protocol

If a frozen module must change:

```
🔒 FROZEN → Identify reason → Document reason → 🔓 REOPEN
→ Make minimal required change → Re-audit entire module
→ Run complete relevant tests → Run regression verification
→ Commit → 🔒 RE-FREEZE
```

Never silently modify frozen code. Never leave a reopened module unfrozen after required work is complete.

---

### RULE 33 — No cascade refactoring

If the user requests: "Fix Module 12"

Do NOT automatically: rewrite Module 03, redesign Module 07, refactor unrelated utilities, clean unrelated components, migrate unrelated architecture.

Only touch another module when: **the active module cannot be correctly completed without it.**

---

## DOCUMENTATION RULE

Documentation must represent the canonical implementation.

Remove or correct: contradictions, stale architecture, obsolete routes, old business rules, duplicate specifications.

When documentation conflicts with locked requirements, locked requirements win.

When documentation conflicts with implementation, investigate before deciding which is authoritative.

---

## GIT RULES

Before changes: `git status`

During work: keep changes scoped, avoid accidental files, inspect diffs, maintain reviewable commits.

Before committing: run tests, run lint/typecheck, inspect diff, inspect changed files.

Never claim a commit exists unless it was actually created.

Do not rewrite historical commits.

---

## MODULE COMPLETION REPORT

When the module is complete, provide:

```
## Module
`Module XX — <Name>`

## Status
🔒 FROZEN

## What Was Fixed
* ...

## One Source of Truth
Old implementation → Canonical implementation → Consumers migrated → Old implementation removed

## Code Simplification
* ...

## UI/UX
* ...

## Security
* ...

## Performance
* ...

## Tests
Backend tests: PASS/FAIL
Frontend tests: PASS/FAIL
Lint: PASS/FAIL
Typecheck: PASS/FAIL
Build: PASS/FAIL
Integration: PASS/FAIL

## Commit
<actual commit hash>

## Cross-Module Changes
[only genuinely necessary changes]

## Known Limitations
[only real remaining limitations]

## Freeze State
🔒 FROZEN
```

Then STOP.

---

## DO NOT AUTOMATICALLY CONTINUE

After freezing the selected module: **WAIT FOR THE USER TO PROVIDE THE NEXT MODULE.**

Do not automatically continue to Module 02, Module 03, etc.

The user controls the execution sequence.

---

## MASTER EXECUTION LOOP

```
USER SELECTS MODULE
    ↓
CHECK FROZEN STATUS
    ↓
DISCOVER SCOPE
    ↓
AUDIT
    ↓
FIND DUPLICATION
    ↓
IDENTIFY SOURCE OF TRUTH
    ↓
PLAN
    ↓
FIX
    ↓
CONSOLIDATE
    ↓
SIMPLIFY
    ↓
TEST
    ↓
SECURITY CHECK
    ↓
PERFORMANCE CHECK
    ↓
UI/UX CHECK
    ↓
SECOND AUDIT
    ↓
REGRESSION TEST
    ↓
VERIFY
    ↓
COMMIT
    ↓
🔒 FREEZE
    ↓
STOP
    ↓
WAIT FOR NEXT MODULE
```

---

## MASTER REOPEN LOOP

```
🔒 FROZEN
    ↓
Identify required change
    ↓
Classify reason
    ↓
Check whether user decision is required
    ↓
🔓 REOPEN
    ↓
Minimal change
    ↓
Full re-audit
    ↓
Test
    ↓
Regression test
    ↓
Verify
    ↓
Commit
    ↓
🔒 RE-FREEZE
    ↓
STOP
```

---

## FINAL QUALITY STANDARD

Do not judge success merely by: "The application works."

Judge success by:

### Architecture
One source of truth.

### Code
Less unnecessary duplication and complexity.

### Domain
Business rules are explicit and correctly owned.

### Backend
Secure, transactional, testable, performant.

### Frontend
Consistent, accessible, responsive, polished.

### UX
Simple, predictable, enterprise-grade.

### Testing
Important behavior is regression-protected.

### Documentation
Canonical and consistent.

### Git
Auditable and reviewable.

### Modules
Completed modules remain frozen.

---

## FINAL NON-NEGOTIABLE RULE

Always remember:

> **THE USER SELECTS THE MODULE.**

> **AUDIT IT COMPLETELY.**

> **FIX IT COMPLETELY.**

> **CONSOLIDATE DUPLICATION INTO ONE SOURCE OF TRUTH.**

> **DO NOT BREAK LOCKED BUSINESS RULES.**

> **TEST EVERYTHING RELEVANT.**

> **RUN A SECOND REGRESSION AUDIT.**

> **COMMIT ONLY VERIFIED WORK.**

> **FREEZE THE MODULE.**

> **NEVER SILENTLY CHANGE A FROZEN MODULE.**

> **IF A FROZEN MODULE MUST CHANGE, REOPEN → FIX → TEST → RE-AUDIT → RE-FREEZE.**

> **AFTER FREEZE, STOP AND WAIT FOR THE USER'S NEXT MODULE.**

---

This protocol governs **every module, every future change, and every modernization cycle** in the License Manager repository.

**Status:** OPERATIONAL AND PERMANENT.

**Commit:** (to be added when committed)

**Authority:** Principal Engineer / Master Autonomous Execution Framework

**Locked:** Yes, non-negotiable.

**Last Updated:** 2026-08-11
