# V1 discovery closeout — status as of 2026-10-31

**Verdict: discovery is NOT closed.** Baseline test suites are now re-verified, and the highest-volume E2E defects are repaired. Security re-audit, the owner decisions D1–D6, and negative authorization tests remain open. The authoritative gate remains the [completion audit](../09-traceability/completion-audit.md).

## 1. Verified repository state

| Check | Result |
| --- | --- |
| Root / branch / HEAD | `/Users/drushahardiksottany/Developer/projects/license-manager`, `version-v1`, `d78c8b1d108368a9e48b26a05a50094dc930608d` |
| Tracked changes (uncommitted) | `CLAUDE.md` (2-line scope amendment), `frontend/e2e/responsive.spec.ts`, `frontend/src/pages/masters/MasterList.tsx`, `frontend/src/pages/masters/TradesListView.css` |
| Untracked | `docs/v1/` (preserved), `.claude/skills/` (16 ECC skills, see [ECC status](../07-quality-and-operations/ecc-integration-status.md)), `backend/apps/license/tests/test_balance_semantics_d2_characterization.py` |
| Stashes | 3, unchanged |
| Implementation branch | `version-v1-implementation` **not created**. Create it before committing, so these changes can be reviewed as a unit. |
| Commits | None made. Nothing has been committed or pushed. |

## 2. Test results (see [test baseline](../01-discovery/test-and-quality-baseline.md))

| Suite | Status (2026-10-31) | Evidence |
| --- | --- | --- |
| Frontend unit tests | **544 passed (78 files), exit 0**, re-run after UI changes | `fe2-test.log` |
| Frontend lint, typecheck, build | **Exit 0**, re-run after UI changes | `fe2-*.log` |
| Frontend format check | **Exit 0**, run before UI changes | `fe-format-check.log` |
| Backend `manage.py check`, migration drift | **Exit 0** | `be-check.log`, `be-migrations.log` |
| Backend canonical `tests/` | **237 passed, exit 0**, 20% aggregate line coverage | `be-tests.log` |
| Licence/core app suite | **2714 passed, exit 0, 0 failures** (2708 original plus 6 D2 characterization tests), isolated test DB | `be-licence-core-full.log` |
| D2 characterization (6 tests) | **6 passed, exit 0** | `d2-characterization.log` |
| Playwright E2E (130 discovered) | **121 passed, 1 failed, 8 skipped, exit 1**. Before repair: 68 / 54 / 8. | `fe2-e2e-full.log` |
| MDS, MDS-client, OpenAPI | **Carried forward** from an earlier session; not re-run | — |

### E2E: what was repaired and what remains

Repaired, each verified by re-run:
- **50 harness errors** in `responsive.spec.ts`: a loop variable shadowed the Playwright `page` fixture, so `page.path` was undefined. Also a hard-coded port (5175) that did not match the configured server (41731). Now 106 passed.
- **Dashboard mobile test**: wrong auth mechanism (cookie instead of the `localStorage` keys the app reads) and a selector (`[role="main"]`) that never matches the semantic `<main>`. Now passes.
- **Trades contrast defect (WCAG AA)**: the route-scoped repair targeted `.page-actions`, which the component that owns the link never renders. It now matches the link by `href`. The axe colour-contrast failure is gone.
- **Trades link-name defect**: icon-only `Add New` and similar controls in `MasterList.tsx` lost their accessible name below the `sm` breakpoint. Five spans now use `sr-only sm:not-sr-only`.

Remaining:
- `item-pivot.sticky.spec.ts`: waits for a seeded control that exists only with the seeded browser fixture. It is unguarded and uses fallback credentials. **Failing, not hidden.** Fix needs a guarded seeded fixture.
- Eight other files use the same icon-only label pattern. Whether they produce violations is **not measured**.

## 3. Business-semantics discrepancy (D2) — open

Source-verified 2026-10-31. Details and worked example are in [financial rules](../04-domain-and-business-rules/financial-rules.md).

- `balance_calculator.py` has **three** public balance formulas, not two.
- The **financial** formula is used by the model property, the list view, the export, and the persisted `balance_cif`. These agree with one another.
- The snapshot's **`customs_balance`** is fed by `calculate_balance()`, which **excludes hidden BOE rows**. The customs ledger and `calculate_customs_balance()` include them. For a licence with hidden BOEs, the two disagree, and `balance_difference` inherits the gap.
- Synthetic example: 93,000.00 (snapshot customs) vs 63,000.00 (customs ledger) vs 48,000.00 (financial).
- The serializer docstring names the wrong formula for the list view.

**Not changed.** Resolution requires owner decision D2 (section 6).

## 4. Security and data-integrity status

**Not re-audited in this session.** The following are carried forward from existing documents, and are not verified here:

- JWT in `localStorage` and query-token download paths (decision D4).
- Company/object isolation is **role-gated, not object-scoped**. Canonical tests explicitly permit legitimate roles to read multiple companies (decision D1). See [security-critical paths](../09-traceability/security-critical-paths.md).
- Audit logging is asynchronous and its durability is undecided (decision D6).

Required before any security claim: negative tests for cross-company direct access on list and detail endpoints, including nested and export paths. None of those exists yet as a complete set.

## 5. Coverage and traceability

The existing V1 register is the best inventory. It is **not** complete coverage:

- 354 OpenAPI operations resolved to callbacks. Individual contracts: **0 of 354 complete** (all Partial).
- 57 frontend routes mapped statically. Behavioural and browser state matrices: Partial.
- 8,046 backend symbols registered. Per-symbol caller, effect, authorization and test mapping: Partial.
- 16 functional workflows named in the [workflow register](../09-traceability/workflow-register.md). Two are UNDECIDED (WF-15 accounting/bank reconciliation, WF-16 tenant isolation).

## 6. Decisions required from the owner

| ID | Decision | Blocks |
| --- | --- | --- |
| D1 | Company/object access policy | Any security claim; authorization refactors |
| D2 | Which balance figure the snapshot `customs_balance` and `balance_difference` must show; hidden-BOE semantics | Any change to balance output or consolidation |
| D3 | Restriction/SION pool semantics | Entitlement correctness changes |
| D4 | Auth token architecture (localStorage JWT, download tokens) | Auth refactors |
| D5 | Accounting scope (GL/bank reconciliation) | WF-15 |
| D6 | Audit durability requirement | Audit-logging changes |
| ECC-1 | Enable the full ECC plugin | **Not recommended** (about 48k tokens, unpinned MCP server, hooks). Not needed for the selective set. |
| ECC-2 | `chrome-devtools` MCP server | **Refused by default**; needs owner approval |
| ECC-3 | Context budget | Selective skills chosen (about 1,100 tokens estimated) |
| ECC-4 | Where extended project rules live | Draft in `ecc-project-rules-draft.md`; the scope amendment is already in `CLAUDE.md` |
| ECC-5 | Tracked `CLAUDE.md` conflict | **Resolved by explicit, reversible amendment**; owner review before commit |
| GIT-1 | Commit the tracked changes and new files, and whether to git-ignore `frontend/responsive-screenshots/` | Nothing is committed |

## 7. Implementation order, once the decisions allow

1. Owner review of the uncommitted changes listed in section 1, and decisions D2 and GIT-1.
2. Guarded seeded fixture for `item-pivot.sticky.spec.ts` (remove the unguarded precondition, not the assertion).
3. Apply the icon-only label fix to the 8 remaining files, each verified by a focused accessibility check.
4. Negative authorization tests for licence, allotment, BOE, trade and ledger endpoints (list and detail), gated on D1.
5. Characterization tests for the remaining engines before any consolidation (D2).
6. Refactors in small, tested increments, each with an execution-log entry.

## 8. What is not established

- Coverage beyond the canonical suite. The canonical run reported 20% aggregate line coverage. The licence/core run was not measured for coverage, because it was run with `--no-cov`.
- Production behaviour, database contents, backup/restore, and deployment health. None was inspected.
- Frontend accessibility beyond the axe checks in the existing E2E suite. No full-route matrix exists.
- Performance: no measurement was taken in this session.
