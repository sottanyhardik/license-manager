# Decision implementation plan — approved 2026-11-01

Source of decisions: `docs/v1/system-audit/execution/consolidated-decision-register.md` (approved by the owner, R2-10 = A). Items marked Deferred are not in scope. Source changes follow the scope amendment in `CLAUDE.md`: focused regression tests with real exit codes, approved semantics only, no destructive operations, and `docs/v1/` kept current.

## Status

- **Slice 1 (superuser protection): COMPLETE, verified 2026-11-01.** Backend change in `user_management.py`; 15 new tests; 49 passed in the accounts and authorization run (exit 0). Evidence: `docs/v1/system-audit/evidence/iss-011-013-verification.md`. Residual risks recorded there (role-grant escalation, superuser count display, Django admin).
- Slices 2 to 9: not started. Slice 2 waits for owner approval.

## Gates for every slice

1. Focused regression tests written first and shown to fail on the current code where the behaviour changes.
2. Run the focused tests; record the real exit code and counts in `docs/v1/system-audit/evidence/test-results.md`.
3. No data change (including flag recalculation) without a separate owner go-ahead.
4. No commit unless the owner asks (Q-028 = A: review first, then grouped commits).
5. Update this plan's status and `docs/v1/execution-log.md` after each slice.

## Slices in order

| # | Slice | Decisions | Current code (verified 2026-11-01) | Change | Blocked by |
|---|---|---|---|---|---|
| 1 | Superuser protection | Q-002 = A | `backend/apps/accounts/views/user_management.py`: queryset includes all users; `reset_password` has no target check; default delete is not overridden. No `is_superuser` guard found. | USER_MANAGER cannot list, view, reset or delete superusers. Tests: each action against a superuser is denied at the API; non-superuser management still works. | None |
| 2 | Company export check | R2-01 = B | Export already writes PAN and GST via `getattr` for all company readers (`backend/apps/core/views/master_view.py` ~709–756). On-screen restriction stays. | No behaviour change expected. Tests pin: export shows PAN, GST and bank fields to company readers; screen still hides them from roles outside the sensitive list. | None |
| 3 | Null DFIA threshold (balance below US$200) | UD-003, UD-004, Q-017 = A, Q-018 = A, Q-019 = B | Thresholds in code: `backend/apps/license/signals.py:316` (500); `backend/apps/license/services/validation_service.py:48, 322` (500); `backend/apps/core/scripts/calculate_balance.py:210` (100); `backend/apps/license/management/commands/sync_licenses.py` ~193 (500); DFIA report split at 1,000 and 20,000 (`report_service.py` ~196–255); expiring-soon at 100 (`dashboard.py` ~119–135); dashboard "Missing DGFT" card (`frontend/src/pages/Dashboard.tsx` ~415–425). | Single named constant for 200 in USD. Replace each threshold. Remove the DFIA 1,000/20,000 split. Rename the dashboard card to "Null DFIA — balance under US$200" and count the balance rule. Expiring-soon uses US$200 and 30 days. Tests: boundary at 199.99, 200, 200.01 in list, flag, dashboard, report, export. | Stored-flag recomputation on data needs a separate go-ahead (slice 3b). |
| 3b | Stored flag recalculation (data) | R2-06 = B (waiver of DEC-03 for this change) | Stored flags disagree with live balances (ISS-001). | Run only after go-ahead. Recalculate with a before/after count, the list of changed licences, and an audit record per change. Rollback is the saved before-state. | Separate owner go-ahead. |
| 4 | Dashboard uses live balance | Q-006 = A | `backend/apps/license/views/dashboard.py` `_get_license_stats` counts stored flags (`flags__is_null`, `flags__is_expired`). | Counts use the same live balance as the licence list. Tests: dashboard count equals list count for each filter. | Slice 3 (threshold); slice 5 for final balance figure. |
| 5 | Balance: single source of truth | R2-02 = A (total export CIF); R2-03 = B; R2-04 = A; R2-05 = other; Q-004 = A; Q-021 = B; Q-023 = C; Q-025 = B; Q-026 = B; UD-002 amended for unlinked sales | Three figures today: `calculate_balance`, `calculate_customs_balance`, `calculate_financial_balance` (`backend/apps/license/services/balance_calculator.py`); snapshot (`balance_snapshot.py`); ledger (`license_balance_ledger_builder.py`). | One balance figure in the licence model: balance CIF = total export CIF − allotments not linked to a BOE (linked allotment ignored) − BOEs not linked to a bill (hidden / OTH BOEs count as unlinked) − all sales ("billed", linked or not). Unused part of a linked allotment is recredited. Commission is a separate metric. Negative balances are shown. Overview shows the financial-versus-customs difference for unlinked sales. Tests: golden fixtures for the owner's examples (100/50 → 50; linked BOE 40 → 60; unlinked sale 500/100/100); hidden-BOE fixture; commission-only licence; negative balance. | Golden fixture pack and before/after reconciliation report on live licences before any change in output (see slice 3b gate). |
| 6 | Protected Nut Products reserve | Q-024 (B), R2-09 = A | `backend/apps/license/services/split_by_percentage_planner.py` ~286–287: amount hard-coded to 0. | Live reserve of US$2.70 per kilogram. Needs the kilogram quantity for each Nut Products item in the planner input. Tests: reserve deducted before allocation; zero-quantity and missing-quantity cases. | Confirm the planner has kilogram quantities before implementation (engineering check, no decision). |
| 7 | Single daily job | Q-010 = A (round 1), R2-07 = one daily job, R2-07a = A | Beat entries name three tasks that do not exist (`backend/lmanagement/celery.py` lines 47, 59, 67, 83). | One task, run once a day, that updates licences and cleans up task records. Remove the separate licence-update check and the duplicate entries. Tests: task runs once per schedule; cleanup removes only records past the approved retention (retention period not yet specified; see note). | Retention period for task records: engineering default is to keep the current retention in code until the owner states one. |
| 8 | Session rule | Q-009 = A | Logout blacklists only the submitted refresh token. Password change and reset do not end sessions (ISS-013, agent-reported). | Password change or reset ends all other sessions of that user; logout ends only the current one. | ISS-013 must be verified first (the earlier security re-check stopped before writing its report). |
| 9 | Repository and API hygiene | Q-008 = A, Q-012 = A, Q-029 = A, Q-028 = A | Dead default-filter lookup (`views/license.py`); tokens in local storage; screenshot folder not ignored. | Correct the dead lookup without changing responses. Record the accepted token risk in `docs/v1/05-target-architecture/security-and-auditability.md`. Git-ignore `frontend/responsive-screenshots/` (tracked change; owner approved). | None for the ignore rule. Review before any commit. |

## Deferred (not in this plan)

| Decision | Reason | What unblocks it |
|---|---|---|
| Q-013 full SION policy table | Interim freeze (Q-013 = A). Table needs owner rules. | Owner supplies the policy table. |
| Q-015 durable audit per event type | Owner chose "per event type", but the list is not written. | Engineering proposes an event list for owner approval. |
| R2-08 accounting scope (D) | Full accounting needs finance requirements. | Chart of accounts, posting events, tax, periods and locks, reversals, bank source, reconciliation authority. |
| Task-record retention period | Not stated. | Owner states the retention period (slice 7). |

## Order and dependencies

1 → 2 → 3 → 5 → 4 → 3b (with go-ahead) → 6 → 7 → 8 (after ISS-013 verified) → 9.

Slice 3 changes thresholds on today's balance figure. Its final numbers change again in slice 5, so slice 3 tests must be re-run after slice 5.

## Verification status

- Plan written from the register and from code checks made on 2026-11-01. No code changed yet.
- The security re-check (ISS-011 to ISS-013) did not complete. ISS-011 and ISS-012 were read directly. ISS-013 needs verification before slice 8.
