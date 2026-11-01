# Continuation checkpoint — system audit

Date: 2026-11-01. Branch `version-v1`, HEAD `d78c8b1d`, 3 stashes (unchanged). No commits. The audit did not change application code, configuration or data.

## Completed in this session

- Audit repository skeleton: `docs/v1/system-audit/` with `inventories/`, `diagrams/`, `agents/`, `evidence/`, `execution/`.
- Master audit register: `execution/master-audit-register.md` (25 tasks; statuses explicit).
- Verified issues: `execution/discovered-issues.md` (ISS-001 to ISS-010).
- Business decisions: `execution/unresolved-decisions.md` (DEC-01 to DEC-05; DEC-05 resolved).
- Test evidence: `evidence/test-results.md` (exit codes and counts for commands actually run).

## In progress (background, read-only)

Three parallel Explore agents were launched to produce the backend app/model inventory, the frontend route and API inventory, and the permissions/security inventory. Their results must be reviewed and saved into `inventories/` and `agents/` before the corresponding tasks are marked complete. Do not mark them complete on launch.

## Not started

Architecture report, API audit, database audit (beyond the stored-flag finding), UI/UX screen-by-screen audit (needs a running stack), performance measurement, infrastructure review, dependency audit, documentation audit, risk register, roadmap, independent review, final verification.

## Blockers

- Full isolated Playwright run: interrupted by the user. Do not re-run without authorisation.
- Browser-based UI/UX audit requires a running backend and an authenticated session. Static inventory only so far.

## Resume instructions

1. Read this checkpoint, then `execution/master-audit-register.md` and `execution/discovered-issues.md`.
2. Check for the three background agent results. Save each into the file named in the register, review it against the source (do not accept it unverified), then update the register.
3. Next tasks in priority order:
   - A-05 API audit: start from `docs/v1/09-traceability/api-operation-register.tsv` (354 operations) and the permissions inventory. Verify a sample of list, detail and export endpoints by request.
   - A-06 database audit: start from `docs/v1/06-data-and-migrations/current-schema.md`. Focus on LicenseFlags, LicenseBalance, BOE, billing and allocation tables.
   - A-07 financial audit: confirm D2 (unbilled versus billed utilisation) against the actual model and the characterization tests before writing the report.
4. Expected output of each: a file under `docs/v1/system-audit/` listed in the register, with evidence and a completion status.

## Session 2 — new-chat recovery (2026-11-01)

Branch `version-v1`, HEAD `d78c8b1d`, 3 stashes (confirmed). Uncommitted: 22 modified tracked files and the untracked set listed in `execution/new-chat-recovery-report.md` §2. No application code, configuration or data changed in this session. No commits.

Completed:

- Recovery report: `execution/new-chat-recovery-report.md`.
- Created missing registers: `execution/user-questions-register.md`, `execution/user-decisions.md`, `execution/approved-business-requirements.md`, `execution/parallel-work-board.md`, `execution/agent-execution-log.md`.
- Re-verified ISS-014 to ISS-018 against source (ISS-014 corrected: four beat entries name three undefined tasks). ISS-016 has no importer, confirmed.
- New evidence: five balance cut-offs for "Null DFIA" (₹100, ₹200, ₹500, ₹1,000, ₹20,000), and a dashboard card that labels the stored flag "Missing DGFT — Require data entry". Extends ISS-003.
- Label conflict: the owner's D1 and D2 are not the repo's D1 and D2. Owner D2 (available-balance formula) is not written in the repo. Repo D2 (Customs vs Financial) is still open.

Agent 06 (owner D2 formula vs code) COMPLETED. Report saved to `agents/agent-06-d2-formula-verification.md` by the lead. Key lines spot-checked. Findings ISS-019 to ISS-025: the owner's worked example passes on all engines when billing is at full BOE amount; the principle fails in the financial engine for unlinked sales (double deduction), partial billing and unbilled sibling rows. This is new evidence against approved UD-002, so Q-016 (reconsider or not) is queued.

Running (background, read-only; results not yet received):

- Agent 05b: ISS-011, ISS-012, ISS-013 re-verification → `agents/agent-05b-security-verification.md`.

Questions:

- Asked: Q-001 (Null DFIA meaning and threshold). Awaiting answer.
- Answered: none.
- Confirmed decisions: UD-001 (owner D1, company access), UD-002 (owner D2, available balance). See `execution/user-decisions.md`.

Next actions:

1. Wait for Q-001 answer; record in `user-decisions.md`; update `approved-business-requirements.md`, `user-questions-register.md`, `unresolved-decisions.md` (DEC-01, DEC-04).
2. When Agent 06 and Agent 05b report: spot-check cited file:line; record verdicts in `discovered-issues.md` and `master-audit-register.md`; then ask Q-002 and Q-003, one at a time.
3. Ask Q-004 and Q-005 after Agent 06 reports.
4. Read older records (R-03): `docs/v1/execution-log.md`, `docs/v1/08-implementation/checkpoint-2026-10-31-*.md`.
5. Start A-05 (API audit) and A-06 (database audit) as independent workstreams.

## Session 3 — consolidated questionnaire round 1 returned (2026-11-01)

- Round 1 answers read from `Project_User_Decisions_Questionnaire_2026-11-01.docx` (Downloads): 26 answer panels.
- Register: `execution/consolidated-decision-register.md` (draft). 17 Confirmed, 9 Clarification Needed, 3 Deferred.
- Conflicts raised, nothing changed: Q-016 (approved rule UD-002 for unlinked sales), Q-007 (waives DEC-03 safeguards), Q-003 (on-screen restriction scope), Q-005 formula (incomplete; unlinked sale still double-deducted), Q-020 (remainder of allotment).
- Round 2 questionnaire: `Project_User_Decisions_Questionnaire_Round2_2026-11-01.docx` (Downloads), 10 items (R2-01 to R2-10), including approval of the register.
- Security re-check of ISS-011 to ISS-013 (agent) stopped before writing `agents/agent-05b-security-verification.md`. ISS-011 and ISS-012 were read directly; ISS-013 is still unverified. Q-009 must not be implemented until ISS-013 is verified.
- Scratch tooling in /tmp was cleared between sessions; the questionnaire generators are not in the repository.

## Session 4 — round 2 answered in chat; register approved (2026-11-01)

- All 10 round 2 items answered one at a time. Register approved: R2-10 = A.
- Decisions: R2-01 B (exports show PAN, GST and bank details to company readers; screen restriction stays); R2-02 A (entitlement = total export CIF); R2-03 B (billed = all sales; unlinked sales deducted, corrected manually); R2-04 A (UD-002 amended for unlinked sales; overview shows financial-versus-customs difference); R2-05 other (linked BOE replaces its allotment; unused part recredited); R2-06 B (DEC-03 waived for flag recalculation; the data run still needs a separate go-ahead); R2-07 one daily job (licence update and cleanup together); R2-07a A; R2-08 D (accounting scope in V1, implementation deferred for finance requirements); R2-09 A (US$2.70 per kilogram).
- Plan: `docs/v1/08-implementation/decision-implementation-plan-2026-11-01.md` (slices 1–9, gates, deferred items).
- No code changed. Next: the owner chooses whether to start slice 1 (superuser protection).
- Open before slice 8: ISS-013 verification (the security re-check stopped before writing its report).

## Session 5 — Slice 1 complete (superuser protection), 2026-11-01

- ISS-013 verified: CONFIRMED (static plus two runtime runs). Record: `evidence/iss-011-013-verification.md`.
- ISS-011 fixed: `backend/apps/accounts/views/user_management.py` (queryset excludes superusers for non-superuser callers). New tests: `backend/apps/accounts/test_superuser_protection.py`.
- Verification: pre-fix 8 failed, 7 passed (exit 1); post-fix 49 passed (exit 0) across accounts and authorization tests; flake8 and py_compile exit 0.
- No financial, balance, flag or database change. No commit.
- Remaining risks: USER_MANAGER can grant any non-superuser role, including to self (owner decision needed); superuser count shows 0 to USER_MANAGER; Django admin not exercised.
- Next eligible slice: Slice 2 (company export check, R2-01 B). Waiting for owner approval before starting it.
