# New-chat recovery report — License Manager V1 system audit

Date: 2026-11-01. Branch `version-v1`, HEAD `d78c8b1d`. Working tree has uncommitted changes (see §2). This report was produced without changing application code, configuration, data or git state. Only files under `docs/v1/system-audit/` were written.

## 1. Recovered project context

- Django/DRF backend (`backend/`), React SPA (`frontend/`), PostgreSQL, Redis, Celery beat (`backend/lmanagement/celery.py`).
- Scope rule: `CLAUDE.md` (root) — documentation-only role, with the V1 implementation-mission amendment (source changes only with focused regression tests, owner-approved semantics, no destructive operations, and `docs/v1/` kept current).
- Code index exists at `.claude/index/` (`symbols.tsv`, `dependents.tsv`, `imports.tsv`, `CODE_MAP.md`). Source must be looked up in the index before it is read.
- The existing audit is a continuation: tasks A-01 to A-25 in `execution/master-audit-register.md`. Checkpoint from the prior session: `execution/continuation-checkpoint.md`.

## 2. Repository state

- Branch `version-v1`. HEAD `d78c8b1d feat(assessments): add comprehensive modernization and risk audits`.
- Modified (uncommitted, 22 tracked files), including `CLAUDE.md`, `backend/apps/license/management/commands/seed_browser_2509.py`, several `frontend/e2e/*.spec.ts`, `frontend/src/components/AdvancedFilter.tsx`, `frontend/src/pages/LicenseLedger.tsx`, `frontend/src/pages/reports/*`, `frontend/package.json`, `scripts/test/run_data_bearing_browser_e2e.sh`.
- Untracked: `.claude/skills/`, four new backend test modules (`test_balance_semantics_d2_characterization.py`, `test_critical_api_anonymous_access.py`, `test_item_pivot_authorization.py`, `test_license_default_active_filter.py`), `docs/v1/`, `frontend/e2e/shell-and-filter.accessibility.spec.ts`, `frontend/e2e/tsconfig.json`, `frontend/responsive-screenshots/`.
- Not verified in this session: whether the uncommitted application changes were reviewed or tested after the last audit run. The prior evidence file says frontend lint, typecheck, unit tests and build must be re-run before any current-health claim.

## 3. Files that exist and were read

| File | Status |
|---|---|
| `docs/v1/system-audit/execution/continuation-checkpoint.md` | Read. Last session: audit skeleton, 25-task register, ISS-001 to ISS-010, DEC-01 to DEC-05. |
| `docs/v1/system-audit/execution/master-audit-register.md` | Read. A-01 and A-03/A-04/A-07/A-08/A-10/A-16/A-17 IN_PROGRESS. No task COMPLETE. |
| `docs/v1/system-audit/execution/discovered-issues.md` | Read. ISS-001 to ISS-018. ISS-016 appears after ISS-018 in the file; the numbering is otherwise contiguous. |
| `docs/v1/system-audit/execution/unresolved-decisions.md` | Read. DEC-01 to DEC-05. |
| `docs/v1/system-audit/evidence/test-results.md` | Read. Real exit codes recorded. Full Playwright run NOT RUN. Full backend suite NOT RUN. |
| `docs/v1/00-executive-overview/decisions-required.md` | Read. Repo D1–D6 (see §4 for label conflict). |
| `docs/v1/00-executive-overview/owner-decision-packets.md` | Read. |
| `docs/v1/04-domain-and-business-rules/license-balance-rules.md`, `unresolved-business-decisions.md` | Read. Short pointer documents only. |
| `docs/v1/system-audit/agents/agent-01-backend-report.md`, `agent-02-frontend-report.md`, `agent-05-security-report.md` | Exist. Not re-read in full this session. Only the findings cited in §5 were re-checked against source. |
| `docs/v1/system-audit/inventories/*.md` (backend-app, frontend-route, permissions) | Exist. Not re-read in full this session. |
| `docs/v1/09-traceability/api-operation-register.tsv` (354 operations) | Exists. Not read. |
| `docs/v1/06-data-and-migrations/current-schema.md` | Exists. Not read. |
| `docs/v1/07-quality-and-operations/*`, `docs/v1/08-implementation/*`, `docs/v1/09-traceability/*` | Exist (about 60 files). Not read in full. Listed for later audit tasks. |

## 4. Files that were requested but are MISSING

| Requested file | Status |
|---|---|
| `execution/parallel-work-board.md` | Missing. Created in this session. |
| `execution/agent-execution-log.md` | Missing. Created in this session. |
| `execution/user-questions-register.md` | Missing. Created in this session. |
| `execution/user-decisions.md` | Missing. Created in this session. |
| `execution/approved-business-requirements.md` | Requested as a maintained file; created in this session with only the approved items. |

Files that exist but are NOT in the requested list and were not reviewed as a whole: `docs/v1/execution-log.md`, `docs/v1/legacy-documentation-disposition.md`, `docs/v1/08-implementation/checkpoint-2026-10-31-*.md`. Their content may hold earlier product decisions. Reviewing them is task R-03 below.

## 5. Recorded findings — verification status

Verified in this session (static, by reading the cited lines):

| ID | Claim | Verification in this session | Status |
|---|---|---|---|
| ISS-011 | USER_MANAGER can reset passwords of, and delete, superusers | `user_management.py` queryset covers all users; `reset_password` calls `get_object()` with no superuser check; `destroy` not overridden; `UserManagementPermission` grants USER_MANAGER read and write (`accounts/permissions.py` around lines 109–112). A separate read-only verification agent is re-checking this, including any layer that might block it. | Source verified. Runtime NOT RUN. Agent re-check pending. |
| ISS-012 | Company export exposes PAN/GST/bank fields | As recorded. A separate agent is checking the export path and role list. | Source verified. Runtime NOT RUN. Agent re-check pending. |
| ISS-013 | Sessions survive logout/password change/reset | Not re-checked here. A separate agent is checking it. | Agent-reported. Pending. |
| ISS-014 | Celery beat names undefined tasks | Confirmed by grep. Four beat entries (`celery.py:47, 59, 67, 83`) name three tasks: `license.tasks.sync_all_licenses`, `identify_licenses_needing_update` (used twice, lines 59 and 67), and `cleanup_old_task_records`. No definition exists anywhere in `backend/` outside tests. **Correction to the register:** it says "three beat entries"; the actual count is four entries naming three undefined tasks. | VERIFIED (correction recorded). Runtime effect not observed. |
| ISS-015 | `rqworker` imports `rq`/`django_rq`, which are not in requirements | Confirmed: `backend/apps/core/management/commands/rqworker.py:66–68` imports them; no `rq` entry in `backend/requirements.txt`, `requirements_python314.txt` or `requirements-test.txt`. A `pyproject`/other manifest was not checked. | VERIFIED imports. Runtime SUSPECTED. |
| ISS-016 | Materialized-view signal module has no importer | Confirmed: no reference to `signals_materialized_views` anywhere in `backend/`. | VERIFIED. Runtime effect not checked. |
| ISS-017 | Expiring/active licence Excel exports call a non-existent prefix | Confirmed: `frontend/src/pages/reports/ExpiringLicenses.tsx:12` and `ActiveLicenses.tsx:12` build `license/reports/...`; backend registers `reports/expiring-licenses/` and `reports/active-licenses/` without a `license/` prefix (`backend/apps/license/urls.py:56–57`). | VERIFIED static. Runtime SUSPECTED (404 expected). |
| ISS-018 | "Data Readiness" link uses the wrong identifier | Confirmed: `frontend/src/pages/LicenseDownloadRequestDetail.tsx:7` links with `r.request_key`; `ledger.py:181` sets `request_key` to the first UUID segment of `public_id` (8 hex). The readiness query at `ledger.py:366` matches `key=` and the job key is `YYYYMMDD-HHMMSS_<8 hex>` (`ledger.py:61`). The two formats cannot match. | VERIFIED static. Runtime SUSPECTED. |
| ISS-001 to ISS-010 | As in `discovered-issues.md` | Not re-checked this session. | As recorded. |

New finding from this session (register update required):

- **ISS-003 extended.** The discovered-issues entry lists 200 (live list), 500 (signals, validation), and "$100" (dashboard expiring-soon). The code also contains: `backend/apps/core/scripts/calculate_balance.py:210` sets `is_null` below ₹100; `backend/apps/license/services/report_service.py:196–255` splits DFIA reports at ₹1,000 (active) and ₹20,000 (expired). This makes five balance cut-offs for one concept. See Q-001 in `user-questions-register.md`.

## 6. Label conflict — repo D1–D6 versus owner's D1 and D2

The owner's D1 and D2 are not the same as the repo's `decisions-required.md` D1 and D2. This must be resolved before any document cites a decision number.

| Owner label | Owner meaning (as stated in this session) | Repo label | Repo meaning | Mapping |
|---|---|---|---|---|
| D1 | No company-only isolation. Role-based access, authentication and object-level security still apply. | D1 (`decisions-required.md`), DEC-05 (`unresolved-decisions.md`) | Company/entity isolation policy; DEC-05 records the owner as resolved | Same topic. Owner's text is more specific: it keeps object-level security. The repo has not recorded this as approved. Record needed. |
| D2 | Available balance = allotted − unbilled BOE − billed utilisation; billed BOE not deducted twice. | D2 (`decisions-required.md`), `owner-decision-packets.md` D2 | Customs vs Financial balance engines (labels and presentation) | **Different question.** The owner's formula is not written anywhere in the repo. The repo's D2 is still open. Clarification needed: does the owner's formula replace, or sit under, the two-engine model? Queued as Q-005. |
| — | Null DFIA threshold 200 vs 500 | DEC-01 | Same, plus three more cut-offs (§5) | Open. Queued as Q-001 (the owner asked for this to be asked). |

## 7. Approved decisions (treated as established)

- **Owner D1** (company access): no company-only data isolation; role-based permissions, authentication and object-level security remain. Recorded in `approved-business-requirements.md` as BR-001.
- **Owner D2** (available balance formula and billed-BOE rule): recorded as BR-002. The code has not been verified against it yet; a verification agent is checking. Any divergence is new evidence and must be raised with the owner, not silently changed.

Neither of these is repeated as a question.

## 8. Pending questions

Listed in `user-questions-register.md`. In priority order:

1. Q-001 — Null DFIA meaning and threshold (ASKED in this session; waiting).
2. Q-002 — Whether USER_MANAGER may ever act on superuser accounts (ISS-011).
3. Q-003 — Which roles may see company PAN, GST and bank details, including in exports (ISS-012).
4. Q-004 — Treatment of hidden (OTH / previous-owner) BOEs in the balance (the 93,000 versus 63,000 gap in the D2 characterization test).
5. Q-005 — Relationship between the owner's D2 formula and the two-engine model.
6. Q-006 — Dashboard counts: live balance or stored flag (DEC-02). Depends on Q-001.
7. Q-007 — Correction of historical stored flags (DEC-03). Depends on Q-001 and Q-006.
8. Q-008 — Default filter applied on the server for the licence list (DEC-04). Depends on Q-001.
9. Q-009 — Session revocation after logout, password change and reset (ISS-013).
10. Q-010 — Scheduled licence sync and other Celery beat jobs: keep, remove or re-implement (ISS-014).
11. Q-011 — Currency wording. Code comments say `$`; the owner's wording uses `₹`. Confirm before rule text is finalised.
12. D3 to D6 from `decisions-required.md` (SION/restriction semantics, token posture, accounting scope, audit assurance). Asked after the financial and security items.
13. Broad interview by module (§9 of the master prompt). Not started.

## 9. Incomplete audit tasks (from `master-audit-register.md`)

- Still NOT_STARTED: A-02 architecture, A-05 API audit (354 operations to sample), A-06 database audit, A-09 UI/UX screen-by-screen (needs a running stack and authenticated session), A-11 performance measurement, A-12 infrastructure, A-13 dependencies, A-14 integrations and background jobs, A-15 documentation, A-18 technical debt, A-19 missing features, A-20 risk register, A-21 roadmap, A-22 target architecture, A-23 acceptance criteria, A-24 independent review, A-25 final verification.
- IN_PROGRESS: A-01, A-03, A-04, A-07, A-08, A-10, A-16, A-17.
- Blocked: full isolated Playwright run (131 tests; interrupted by owner earlier; do not re-run without authorisation). Positive package-generation test (needs a licence fixture with complete purchase documents and final-party invoices). Browser UI audit (needs a running stack and authenticated session).

## 10. Stale or incorrect items in existing records

- `master-audit-register.md` A-07 says "Agent 6" and "Existing characterization tests" — the characterization test is untracked and not yet committed; it should be listed as evidence with that status.
- `continuation-checkpoint.md` says "3 stashes (unchanged)". Confirmed this session: `git stash list` shows 3.
- ISS-014 count: "three beat entries" should read "four beat entries naming three undefined tasks".
- ISS-003 cut-offs: five values, not three (see §5).
- `discovered-issues.md` refers to `01-audit-scope-and-methodology.md`, which does not exist in `docs/v1/system-audit/`. Missing file recorded. The audit standard (severity, confidence) it describes is therefore not written down anywhere in the audit directory.

## 11. Background work in progress

Two read-only verification agents were started in this session. Their results are not yet received; nothing in this report depends on them.

- Agent 06 (code-reviewer): verify the owner's D2 formula against `balance_calculator.py`, `balance_snapshot.py`, the Customs ledger and the D2 characterization test. Output: `agents/agent-06-d2-formula-verification.md`.
- Agent 05b (security-auditor): re-verify ISS-011, ISS-012, ISS-013 and look for further object-level gaps. Output: `agents/agent-05b-security-verification.md`.

## 12. Exact next actions

1. Ask Q-001 (Null DFIA). Wait.
2. When Agent 06 and Agent 05b report: record verdicts in `discovered-issues.md` and `master-audit-register.md`; save their output files; do not accept results unverified (spot-check file:line for each cited claim).
3. Then ask Q-002 (superuser management) and Q-003 (company sensitive fields), one at a time.
4. Read `docs/v1/execution-log.md` and the three `checkpoint-2026-10-31-*.md` files for earlier product decisions (task R-03).
5. Start A-05 API audit (sample list, detail and export endpoints by request, using the 354-row register) and A-06 database audit (LicenseFlags, LicenseBalance, BOE, billing, allocation tables).
6. Update `continuation-checkpoint.md` after each batch.

## 13. Recovery tasks

| ID | Task | Status |
|---|---|---|
| R-01 | Recover the existing audit state (checkpoint, register, issues, decisions, evidence) | DONE (this report) |
| R-02 | Verify recorded ISS-011 to ISS-018 against source | PARTLY DONE (ISS-014 to ISS-018 done here; ISS-011 to ISS-013 with agents) |
| R-03 | Read older checkpoint and execution-log files for product decisions | NOT STARTED |
| R-04 | Create missing register files | DONE |
| R-05 | Check the untracked characterization tests and whether they are committed evidence | NOT STARTED |
| R-06 | Confirm D2 formula against code | IN PROGRESS (Agent 06) |
