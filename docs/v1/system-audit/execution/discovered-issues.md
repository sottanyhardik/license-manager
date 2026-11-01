# Discovered issues (verified in this audit session)

Each entry lists the evidence that was actually observed. Severity and confidence follow the audit standard (see `01-audit-scope-and-methodology.md` once written).

## ISS-001 — Dashboard active count disagrees with licence list (HIGH, VERIFIED)

- Dashboard active count: `backend/apps/license/views/dashboard.py` `_get_license_stats` counts `flags__is_expired=False, flags__is_null=False` using STORED flags.
- Licence list default: live financial balance via `apply_advanced_filters` (`views/license.py`).
- Evidence: retained test database, every licence `flags.is_null=True`; ORM `flags__is_null=False` count 0; API default-filter query returns 12 licences including balance-1000 licences.
- Business impact: dashboard KPI and the list it links to show different numbers.
- Depends on: DEC-01, DEC-02, DEC-03.
- Test: `apps/license/tests/test_license_default_active_filter.py::test_dashboard_active_count_uses_stored_flag_not_live_balance` (characterizes current behaviour; does not endorse it).

## ISS-002 — Server default for Null DFIA filter is never applied (MEDIUM, VERIFIED)

- Metadata declares default `flags__is_null=False` (`views/license.py` around lines 132–135).
- Server reads `default_filters.get('is_null')` (`views/license.py` around line 629–661), which never matches the declared key.
- Evidence: unfiltered API request returns 13 licences, including a zero-balance licence; the same request with `is_expired=False&flags__is_null=False` returns 12.
- Depends on: DEC-04.
- Test: `test_server_applies_no_null_default_when_unspecified` (characterization).

## ISS-003 — Two live-balance thresholds in the codebase (MEDIUM, VERIFIED)

- 200 in the live list filter; 500 in signals and validation services; a further "$100" threshold in dashboard expiring-soon logic.
- Depends on: DEC-01.
- Test: `test_live_list_null_filter_boundaries_around_threshold_200` and `test_both_parameter_names_behave_identically`.

## ISS-004 — Persisted-routes E2E expectation was based on an incorrect business assumption (test defect, VERIFIED, RESOLVED)

- The test expected zero-balance licence 3411008090 in the default active view. That licence is correctly excluded under both candidate thresholds.
- Corrected to licence 3411009011 (balance 1000, not debited by the PLAN test). Harness run: 2 passed, exit 0 (persisted-routes test and the previously unrun responsive serial test).

## ISS-005 — Stale ten-card PLAN queue expectation (test defect, VERIFIED, RESOLVED)

- Product page size is 25 (`frontend/src/pages/AllotmentAction.tsx`, set in commit `128417fd`). The E2E assumed ten. Corrected. Focused run passed.

## ISS-006 — Obsolete merged-PDF E2E specs (test defect, VERIFIED, RESOLVED)

- "Download Merged PDF" control removed in commit `79a08ac2`. Specs replaced by Excel export coverage (passes) and package readiness negative coverage (passes).
- Positive package PDF coverage is NOT yet implemented (see A-10 limitation).

## ISS-007 — Test harness routed background jobs to the developer's Redis broker and leaked workers (HIGH, VERIFIED, RESOLVED)

- Fixed in `scripts/test/run_data_bearing_browser_e2e.sh`: dedicated Redis index (default 7, refuses 0 and non-empty), harness-owned Celery worker tracked by its real PID, cleanup flushes only the verified-empty index. Orphan harness workers were stopped after their command lines were verified. The developer's own worker (PID 1068) was not touched.
- Verification after the fix: no orphan workers after harness runs; index 7 empty after runs.

## ISS-008 — Developer broker key count grew during the session (INFORMATIONAL, UNVERIFIED attribution)

- Redis database 0 went from 2082 to 2667 keys across the session. Harness runs after the fix use index 7 only. Attribution to the developer's own activity has not been established.

## ISS-009 — Unattributed untracked file (INFORMATIONAL)

- `frontend/e2e/tsconfig.json` (created during the session; nothing references it). Preserved. Owner decision.

## ISS-010 — Untracked generated screenshot directory (LOW)

- `frontend/responsive-screenshots/` is not git-ignored and receives PNGs from the responsive spec. Recommend ignoring it (needs approval for a tracked change).

## ISS-011 — USER_MANAGER can reset passwords of and delete superusers (HIGH, VERIFIED by source read and runtime CONFIRMED)

- `backend/apps/accounts/views/user_management.py:34` queryset includes all users. `reset_password` (`:61-74`) has no target check. `destroy` is not overridden.
- `UserManagementPermission` (`backend/apps/accounts/permissions.py:109-112`) grants USER_MANAGER read and write with no object check.
- Business impact: a user-administration role can take over a superuser account. Escalation path to full access.
- Source: agent-05 SEC-INV-01 (`agents/agent-05-security-report.md`).
- Runtime (2026-11-01, agent G, isolated test database `test_audit_g_20261101`, since dropped): CONFIRMED. USER_MANAGER reset of a superuser returned 200 and changed the password hash. USER_MANAGER delete of a superuser returned 204 and removed the row. LICENSE_VIEWER and no-role actors got 403 on every target, with no change.
- Not exercised: logging in as the reset target. The takeover consequence is inferred from the hash change.
- Evidence: `evidence/runtime-verification-2026-11-01.md`. Owner decision Q-002 = A (2026-11-01).
- Fixed in Slice 1 (2026-11-01): superusers are excluded from the user-management queryset for non-superuser callers. Verification: 8 of 15 new tests failed before the fix and all pass after it; 49 passed in the accounts and authorization run (exit 0). See `evidence/iss-011-013-verification.md`.

## ISS-012 — Company PAN and GST exported to read-only roles (HIGH, VERIFIED by source read and runtime for PAN and GST; bank part REFUTED for export)

- `CompanySerializer.to_representation` redacts `pan`, `gst_number`, `bank_account_number`, `bank_name`, `ifsc_code`, `account_type` for roles outside `full_access_roles_for_sensitive_fields` (`backend/apps/core/serializers/models.py:39-62`; `apps/accounts/permissions.py:231-237`).
- The export builder (`backend/apps/core/views/master_view.py:709-756`) reads undeclared columns with raw `getattr`, which skips `to_representation`. `pan` and `gst_number` are auto-generated, not declared, so the export returns them unredacted.
- Readable by the 9 read-only company roles in `CompanyPermission.required_roles_for_read` (`apps/accounts/permissions.py:209-219`) that are not in the sensitive list, for example LICENSE_VIEWER, BOE_VIEWER, REPORT_VIEWER.
- Source: agent-05 SEC-INV-02.
- Runtime (2026-11-01, agent G): LICENSE_VIEWER list returns no PAN, GST or bank keys (200). The xlsx and pdf export return 200 and contain PAN and GST values. LICENSE_MANAGER and USER_MANAGER see the full set. Unauthorised users get 403 on all three.
- Correction: the export has no bank columns (xlsx header: Modified On, Iec, Name, Pan, Gst Number, Address Line 1, Address Line 2). The bank part of the original claim is REFUTED for the export. Bank fields are visible only in the list JSON of full-access roles.
- Not checked at runtime: the other eight read-only roles listed in `CompanyPermission`. One role (LICENSE_VIEWER) was sampled.
- Evidence: `evidence/runtime-verification-2026-11-01.md`. Owner decision Q-003 is still pending.

## ISS-013 — Sessions survive logout, password change and password reset (MEDIUM, runtime CONFIRMED in part)

- `RevokedAccessToken` has no production writer. Logout blacklists only the submitted refresh token. Password change and reset do not revoke sessions. Refresh tokens last 7 days.
- Source: agent-05 SEC-INV-03.
- Runtime (2026-11-01, agent G): CONFIRMED that the access token still works after logout (200), and that the refresh token still works after a password change (200) and after an admin reset (200). REFUTED that logout leaves the submitted refresh token valid: it returns 401.
- Not waited for: access-token expiry (30 minutes by configuration).
- Lead re-check (2026-11-01, probe outside the repository; exit 0): logout returns 205; the logged-out refresh token returns 401; the access token still works until expiry; a second session survives logout, admin reset and password change. Verdict CONFIRMED. See `evidence/iss-011-013-verification.md`.
- Owner decision Q-009 = A (2026-11-01): a password change or reset ends all other sessions; logout ends only the current one. Implementation is Slice 8.

## ISS-014 — Backend beat schedule names undefined tasks (MEDIUM, VERIFIED)

- Three beat entries (`sync_all_licenses`, `identify_licenses_needing_update`, `cleanup_old_task_records`) have no task definition in the repository (`backend/lmanagement/celery.py:47,59,67,83`).
- Runtime effect (scheduler error or silent skip) not yet observed.
- Source: `inventories/backend-app-inventory.md`, BE-INV family.

## ISS-015 — `rqworker` command depends on packages not in requirements (LOW, VERIFIED imports, runtime SUSPECTED)

- `backend/apps/core/management/commands/rqworker.py:68-94` imports `rq`/`django_rq`. Neither is in `requirements.txt`.
- Not executed. Whether the command fails on run is SUSPECTED.

## ISS-017 — Expiring and active licence Excel exports call a non-existent endpoint prefix (HIGH, VERIFIED static and runtime)

- `frontend/src/pages/reports/ExpiringLicenses.tsx:12` and `ActiveLicenses.tsx:12` build `license/reports/<name>/?format=excel&days=N`. The client base is `/api/`, so the request is `/api/license/reports/...`.
- Backend registers `reports/expiring-licenses/` and `reports/active-licenses/` under `api/` (`backend/apps/license/urls.py:56-57`; `backend/lmanagement/urls.py:45`). No `license/` prefix exists.
- Impact: two user-facing report exports are expected to fail with 404. The `DownloadLicense` page calls the correct prefix, so the working route exists. The unit tests mock the wrong path and therefore do not catch this.
- Source: agent-02 Key finding 1 (`agents/agent-02-frontend-report.md`).
- Runtime (2026-11-01, agent G): `/api/license/reports/expiring-licenses/` returns 404 (JSON). `/api/reports/expiring-licenses/` returns 200 with a valid xlsx. The active-licences pair shows the same pattern.
- Not checked: workbook data rows, because the test database held no licences.

## ISS-018 — Download request detail "Data Readiness" link uses the wrong identifier (MEDIUM, VERIFIED static and runtime)

- `frontend/src/pages/LicenseDownloadRequestDetail.tsx:7` links to `/license-ledger/package-readiness/${r.request_key}`.
- `request_key` is the first UUID segment of `public_id` (`backend/apps/license/views/ledger.py:181`), 8 hex characters.
- The readiness lookup filters `job.key`, which is built as `YYYYMMDD-HHMMSS_<8 hex>` (`ledger.py:61,225`) and matched at `ledger.py:367`. A request key never matches.
- Impact: the "Data Readiness" and "Resolve Data" links are expected to 404. Users would need another route to reach readiness for a request.
- Fix needs a product choice (route by `public_id` or by job key). Not changed in this audit.
- Runtime (2026-11-01, agent G): the readiness route returns 200 for the job key and 404 for the `request_key` and for the public UUID. The link therefore fails as described. The probe's first run exited 1 because of a probe defect (see NEW-1 below); the final run exited 0.

## ISS-016 — Materialized-view signal module is never imported (MEDIUM, VERIFIED import status, runtime effect SUSPECTED)

- `backend/apps/core/signals_materialized_views.py` has no importer. Any refresh it wires is not connected by any code path.
- The impact on the materialized views depends on whether they are refreshed elsewhere. Not checked.

## ISS-019 — Financial balance double-deducts a sale that has no BOE link (HIGH, VERIFIED static by agent 06 and lead spot-check, runtime NOT RUN)

- `balance_calculator.py:1063–1088` subtracts every SALE line regardless of BOE status. `:339–352` and `:459–509` net a BOE's debit only when the BOE is linked (legacy trade tag or formal allocation). `LicenseTradeLine` has no BOE foreign key.
- Effect: with a 100,000 BOE and an unlinked 100,000 sale of the same goods, the financial balance is 300,000 where the owner's rule gives 400,000.
- Depends on: owner's D2 rule (UD-002) and Q-005/Q-016. Source: `agents/agent-06-d2-formula-verification.md` F1.

## ISS-020 — Partly billed BOE drops the unbilled remainder (HIGH, VERIFIED static, runtime NOT RUN)

- `balance_calculator.py:341–352`, `:447–455`. A BOE of 100,000 billed at 60,000 (legacy tag) gives 440,000 where the owner's rule gives 400,000. The 40,000 remainder is removed.
- Source: agent 06 F2. Depends on Q-004/Q-005.

## ISS-021 — Unbilled sibling rows of a billed BOE are dropped (HIGH, VERIFIED static, documented as accepted)

- `balance_calculator.py:294–352`, docstring at `:231–241` ("KNOWN, ACCEPTED TRADE-OFF"). Conflicts with the owner's "not deducted twice" principle only if the remainder should still count, which is a question for the owner (Q-005).
- Source: agent 06 F3.

## ISS-022 — Allotment zeroed for the whole item when any BOE is linked (MEDIUM, VERIFIED static)

- `balance_calculator.py:798–800`, `:825–826`, `:834–840`; intended per docstring `:732–738`. Remainder of a partly realised allotment is removed from all three engines. Pre-link double count acknowledged at `:745–756`.
- Source: agent 06 F4. Intent is an owner question.

## ISS-023 — Multiple SALE trades tagged to one BOE both subtract (MEDIUM, PLAUSIBLE, write path not read)

- `balance_calculator.py:1083–1088`; represented-BOE set dedupes ids only (`:199–207`).
- Source: agent 06 F5.

## ISS-024 — AR allotments counted at licence level and excluded at item level (MEDIUM, VERIFIED static)

- `balance_calculator.py:865` (no type filter) vs `:919`, `:957` (AT only); comment `:906–909` contradicts `core/scripts/calculate_balance.py:55–56`.
- Source: agent 06 F6. Owner decides which is correct (Q-005 question 6).

## ISS-025 — Documentation disagreement on customs balance formula (LOW, VERIFIED)

- `docs/v1/04-domain-and-business-rules/financial-rules.md` line 9 says customs = visible BOE − allotment (matches `calculate_balance`, not `calculate_customs_balance`). Line 19 is correct. Also the "6 passed, exit 0" claim on line 28 is not re-verified.

## ISS-026 — Five Null DFIA cut-offs and a "Missing DGFT" alert label (MEDIUM, VERIFIED) — see Q-001

- Recorded under ISS-003 and DEC-01 as extended on 2026-11-01. Cut-offs ₹100 (`core/scripts/calculate_balance.py:210`), ₹200, ₹500, ₹1,000 (`report_service.py:196–255`), ₹20,000. Dashboard label `frontend/src/pages/Dashboard.tsx` around 415–425.

## ISS-014 correction (recorded 2026-11-01)

- Four beat entries (`backend/lmanagement/celery.py:47, 59, 67, 83`) name three undefined tasks; `identify_licenses_needing_update` is referenced twice. Earlier entry said three entries.

## ISS-027 — Download-request detail returns HTTP 500 for any non-UUID identifier (MEDIUM, runtime VERIFIED, cause from code reading)

- Runtime (2026-11-01, agent G): `GET /api/license-ledger/download-requests/<id>/` returns 200 for the public UUID and HTTP 500 for both the `request_key` and the job key. Each 500 is an unhandled error, not a clean 404.
- Likely cause: `_owned_download_request` (`backend/apps/license/views/ledger.py:145`) combines a public-ID lookup and a key lookup with OR. A non-UUID string fails the UUID cast before the key branch runs. The lead has read this line; the exact exception path has not been traced.
- Impact: the frontend cannot reach the request detail from a non-UUID link, and any caller that sends a bad identifier gets a server error rather than a 404.
- Found while verifying ISS-018. It was NEW-1 in the agent report.
- Remediation depends on Q-013 (which identifier readiness links should use). Not changed in this audit.

## ISS-014 correction 2 (recorded 2026-11-01, integrations audit)

- Counting non-beat call sites as well, four distinct task names are undefined, not three. The fourth is `update_all_license_balances`, which is imported at `backend/apps/reconciliation/views.py:295` and `backend/apps/license/views/item_pivot_report.py:2384` with no definition anywhere (VERIFIED by lead grep). See ISS-051.

## Integrations and background-job findings (from agent D, `15-integrations-and-background-jobs-audit.md`)

Status key: VERIFIED = lead re-checked the cited line. AGENT = taken from the agent's reading, not yet re-checked.

- **ISS-050 (HIGH, AGENT):** Legacy download-request dispatch raises NameError; retry and reconcile endpoints return 500.
- **ISS-051 (HIGH, VERIFIED):** Balance-recalculation endpoints import the undefined `update_all_license_balances`, so they fail with 500. Sites: `reconciliation/views.py:295`, `license/views/item_pivot_report.py:2384`.
- **ISS-052 (MEDIUM, AGENT):** Package item tasks can be duplicated under backlog or retry.
- **ISS-053 (MEDIUM, AGENT):** Package lifecycle gaps: a stuck sentinel state, an uncapped finalize retry, fail-fast on soft time limit, and a cleanup task that skips non-terminal jobs.
- **ISS-054 (MEDIUM, AGENT):** The protected-media allow-list omits `license-ledger-packages/`. Relates to the ISS-054 candidate question on package visibility (Q-pending).
- **ISS-055 (HIGH, PARTLY VERIFIED):** Cache is configured from `REDIS_URL` (`settings.py:389-395`, VERIFIED). `clearcache` and the cache test helpers call `cache.clear()` (VERIFIED). django_redis `clear()` flushes the configured Redis database. Whether the broker and results backend share that URL is AGENT-reported and not yet checked.
- **ISS-056 (MEDIUM, AGENT):** Sync outbox writes unconditionally; sync beat tasks are unregistered; no retention.
- **ISS-057 (MEDIUM, AGENT):** Production accepts any `EMAIL_BACKEND` that is set, including console. Password-reset tokens could reach logs. The production guard requires the setting to be explicit (`settings.py:553-555`, VERIFIED) but does not reject the console backend.
- **ISS-058 (MEDIUM, AGENT):** One thread per authenticated API request for activity logging, with no retention.
- **ISS-059 (MEDIUM, AGENT):** DGFT, OCR and heavy PDF work run inside request handlers.

Candidate product questions raised by agent D are not asked yet and are not yet in `user-questions-register.md`. Q-012 already covers scheduled jobs. The new candidates are package retention, package visibility, the shared Redis, master-data peer sync, password-reset email, DGFT call placement and API read logging. They will be added to the register and asked one at a time, after Q-001 is answered.

## Performance and infrastructure findings (from agent E relaunch, `12-performance-audit.md` and `13-infrastructure-and-deployment-audit.md`)

Status key as above. Measured = a read-only command was run by the agent. Theoretical = inferred from code. No runtime probe, build or production connection was made.

- **ISS-060 (MEDIUM, MEASURED by agent):** Local `frontend/dist/assets/js` holds about 627 MB across 32,154 files, with 232 accumulated `app-shell` copies. `emptyOutDir` is false. Production state is unverified.
- **ISS-061 (MEDIUM, VERIFIED):** `ExportRateThrottle` is defined (`backend/apps/core/throttling.py:175`) and mapped to the `export` scope (`:357`), but no export view applies it. Only the throttle-status view imports it (`backend/apps/core/views/throttle_status.py:23,93`).
- **ISS-062 (MEDIUM, THEORETICAL):** PDF and XLSX generation runs inside the request, with no visible cap on licence count or export size.
- **ISS-063 (MEDIUM, MEASURED by agent):** Report and activity responses are unbounded or unpaginated.
- **ISS-064 (LOW, THEORETICAL):** Connection-reuse gaps outside guarded paths; no `CONN_MAX_AGE`.
- **ISS-065 (LOW, MEASURED by agent):** Frontend timeouts, overlapping polls, bundle hygiene.
- **ISS-066 (HIGH, VERIFIED by name only):** Tracked env-named files include `.env`, `frontend/.env`, `frontend/.env.production`, `backend/.env_dgft` and two `.example` files. Contents were not read, and must not be read in the audit. Settings fall back to a development key when `DJANGO_ENVIRONMENT` is not set to production, and the production guard is opt-in (see SEC-INV-07 in `agents/agent-05-security-report.md`). Whether the committed `.env` holds real secrets is unverified.
- **ISS-067 (MEDIUM, PARTLY VERIFIED):** Several nginx configs match a `/media/` alias pattern (`nginx-http-only.conf`, `nginx-license-manager.conf`, `nginx-labdhi.conf`, `nginx-protected-media.conf`, `nginx-license-tractor.conf`). The alias bodies are not yet read, so public exposure is AGENT-reported and not confirmed.
- **ISS-068 (HIGH, PARTLY VERIFIED):** `scripts/deployment/auto-deploy.sh:439` runs `git reset --hard "origin/$BRANCH"`. The agent also reports disabled host-key checking, a migration without a database dump, and a deploy path that is not versioned. Only the reset line is verified; its guard conditions are unread.
- **ISS-069 (MEDIUM, AGENT):** No logging rotation. About 1.0 GB of production database dumps sit in an ignored `backups/` directory with no retention policy. Watchdog kill-and-restart behaviour is unreviewed.

Candidate owner questions from this agent (not yet asked, not yet in the register): retention and storage location for the local production dumps; which nginx configs are live for each site, and whether the public `/media/` alias serves traffic; and the export size above which work must move to a background job. The package-retention question from agent D overlaps with the first of these and will be merged when added.

## Dependency findings (from agent C, `14-dependency-and-technology-audit.md` and `inventories/dependency-inventory.md`)

- **DEP-002 (P0, VERIFIED):** `scipy` is imported at module level in `backend/apps/core/scripts/calculation.py:3` and `:58`. It is not declared in `backend/requirements.txt` or `requirements_python314.txt`, and it is not installed in `backend/.venv`. The only caller, `backend/apps/license/models/core.py:683-687`, wraps the import in `except Exception` and sets the function to `None`. When scipy is missing, the optimisation branch is skipped silently and the calculation takes a different path. No error is raised. This is a silent change to a licence calculation. Whether production has scipy is unverified.
- **DEP-001 (P0, AGENT, not yet checked):** Django is pinned to 6.0.4 in both requirements files (VERIFIED pin). The agent reports 26 OSV advisories against 6.0.4 and recommends 6.0.9. The advisory data was not re-checked by the lead.
- **DEP-003 to DEP-011 (P1 to P2, AGENT):** pypdf, DRF, PyJWT, axios, vitest, Pillow, requests, and declared-but-unused packages (`bs4`, dompurify and others). Versions and advisories come from registry and OSV lookups by the agent and are not re-checked.
- **Counts (AGENT):** backend 25 runtime and 7 test-only declared packages; 6 PyPI packages imported but undeclared; frontend 36 runtime and 21 dev packages; 8 runtime packages with no source import.

Candidate owner questions from this agent, not yet asked and not yet in the register:
- Q-DEP-1: support policy. Django 6.0 reaches upstream end of life on 2027-04-30 (third-party date). Stay on 6.x or move to the 5.2 LTS line?
- Q-DEP-2: financial. Is the scipy-based optimisation required in production? The answer determines whether scipy is declared or the path is removed, and the output changes either way. This is a P0 question and should be asked before DEP-002 is fixed.
- Q-DEP-3: scope. May the unused `rqworker` command and the one-off `migrate_auth` command be removed?

## Database and financial findings (from agent B, `07-database-audit.md`, `08-financial-business-logic-audit.md`, `18-data-integrity-and-reconciliation.md`)

Status: all AGENT-reported. The agent re-checked its own line citations, but I have not re-read them. ISS-019 to ISS-022 were verified earlier by agent 06 and the lead. Nothing here is a fix, and none of it is ready for implementation.

- **ISS-030 (HIGH):** A repeat hide erases the original invoice number.
- **ISS-031 (HIGH):** Client flags skip the trade CIF ceiling, and nested errors are swallowed.
- **ISS-032 (HIGH):** A legacy-tagged BOE with a partial formal allocation debits the remainder twice. Feeds Q-016.
- **ISS-033 (MEDIUM):** The stored Null flag is written at thresholds 100 and 500, not one value.
- **ISS-034 (HIGH):** Licence API balance and status filters read stored columns.
- **ISS-035 (MEDIUM):** Ledger upload leaves the stored balance and expiry stale.
- **ISS-036 (MEDIUM):** The stored item-quantity formula differs from the live one.
- **ISS-037 (HIGH):** No licence lock, so sibling allocations can exceed the balance.
- **ISS-038 (MEDIUM):** The allocation gate rejects balances below 500.
- **ISS-039 (HIGH):** A BOE merge discards duplicate debit rows without an audit record.
- **ISS-040 (HIGH):** Deleting a parent cascades through payments and debit rows.
- **ISS-041 (MEDIUM):** Trade payments accept negative or overpaid amounts.
- **ISS-042 (MEDIUM, SUSPECTED):** A quantity-mode trade line may debit zero.
- **ISS-043 (MEDIUM):** No database non-negative checks on money columns.
- **ISS-044 (MEDIUM):** Migration 0005 checks counts only.
- **ISS-045 (MEDIUM):** A commission sale is not a licence debit. Owner question.
- **ISS-046 (LOW):** Licence invoice tables have no writer.
- **ISS-047 (MEDIUM):** The snapshot `customs_balance` emits a non-hidden figure.
- **ISS-048 (MEDIUM):** A save on a frozen BOE row is silently ignored.
- **ISS-049 (MEDIUM):** Negative balances are floored, which hides over-utilisation.

Test run by agent B: the D2 characterisation file, exit 0, 6 passed, in a disposable test database (log `/tmp/lm-verify-auditB-d2.log`). It wrote `backend/htmlcov/`, which is git-ignored. This was a test run I did not authorise in this session. It is recorded here so it is not lost.

Candidate owner questions from agent B (not yet asked, not yet in the register): commission debit (ISS-045); quantity-mode sales when CIF is blank (ISS-042); legacy-tagged BOE that is partly allocated (ISS-032, feeds Q-016); overpayment and credit notes (ISS-041); whether any role may skip the CIF ceiling (ISS-031); live or stored balance for API filters (ISS-034, overlaps the follow-up to UD-003); over-utilisation display (ISS-049); and whether money-bearing records may be deleted and whether deletion is audited (ISS-040).

## Null DFIA rule: recorded answer (UD-003, UD-004)

- The owner's recorded answer: "Null DFIA is if license balance_cif is less than $200 everywhere." Currency US dollars (UD-004).
- The record's own follow-up: it is unconfirmed whether `balance_cif` means the live figure (what the licence list shows) or the stored flag. This is the follow-up question, Q-017.
- Consumers that still use 100, 500, 1,000 or 20,000 (ISS-026, ISS-033, ISS-038) are not yet changed. Consumer changes need separate approval.

## API findings (from agent A, `06-api-audit.md` and `inventories/api-endpoint-inventory.md`)

Note on IDs: the API agent first used ISS-030 to ISS-039, which collided with the database agent's ISS-030 to ISS-049. Its own findings were renumbered to ISS-080 to ISS-089, and the two API files were updated to match. ISS-028 and ISS-029 are unchanged.

Status: AGENT-reported unless marked. ISS-017 and ISS-018 were confirmed earlier at runtime.

- **ISS-028 (HIGH, PARTLY VERIFIED):** `LicenseLedgerViewPermission` (`backend/apps/license/views/ledger.py:35`; class at `apps/accounts/permissions.py:132-148`) admits TRADE_VIEWER on every HTTP method. So a TRADE_VIEWER can reach ledger write actions: purchase-document upload (`ledger.py:322`), orphan recovery (`:342`), job creation (`:185`) and retry (`:118`, `:262`). Verified at the permission level. Whether a TRADE_VIEWER can change another user's trade data is not verified; some actions use requester scoping.
- **ISS-029 (MEDIUM, AGENT):** Export and report endpoints are not throttled. `ExportRateThrottle` is defined but never applied (also ISS-061 in the infrastructure audit). Master exports have no row cap.
- **ISS-080 (MEDIUM, AGENT):** Activity-log list is unpaginated and grows with every API call.
- **ISS-081 (HIGH, AGENT):** Three live calls fail: the licence "Ledger" button points to an unrouted path; the readiness reject POST returns 405; "Update Balance" is shown to managers but allowed only for superusers.
- **ISS-082 (HIGH, AGENT):** The password-reset email link opens NotFound, and the confirm endpoint has no frontend caller. Not yet checked against the routes.
- **ISS-083 (MEDIUM, AGENT):** The JWT is accepted in the `access_token` query string. Overlaps SEC-INV-04 and decision D4.
- **ISS-084 (LOW, AGENT):** Five report families are exposed at two paths; the viewset variants are unused.
- **ISS-085 (LOW, AGENT):** Unrouted viewsets, unsubclassed cached viewsets and dead frontend clients. Overlaps ISS-035 in the backend audit.
- **ISS-086 (LOW, AGENT):** Wrong-prefix metadata (`/trade/trades/`, `/api/` prefixes in metadata).
- **ISS-087 (MEDIUM, AGENT):** `page_size=500` is silently capped at 200 on the SION planning list.
- **ISS-088 (MEDIUM, AGENT):** Tracebacks and `str(e)` are returned to clients; error shapes are mixed.
- **ISS-089 (LOW, AGENT):** Declared filtersets are inert, and there are two pagination envelopes.

Counts (AGENT): 354 operations in the register, plus 4 uncatalogued surfaces. 293 operations have a frontend caller; 61 have none. The reverse match is a static pattern scan. Django `APPEND_SLASH` and DRF `pagination_class = None` behaviour is SUSPECTED because the framework source is not in the checkout.

Candidate owner questions from agent A (not yet asked, not yet in the register): which roles may upload purchase documents, recover orphans, and create or retry ledger jobs (ISS-028); whether self-service password reset is in V1 (ISS-082); who may trigger Item Pivot "Update Balance" (ISS-081); activity-log retention and who may read it (ISS-080); the export size and frequency to support (ISS-029); whether lists should apply hidden default filters (ISS-087 area); whether external consumers use `?access_token=` links (ISS-083); and whether the public invoice-document link is an approved sharing channel. Questions already covered by D1, D2, D4 or D6 are excluded. The 61 operations with no frontend caller are a product-scope question, to be asked later.

## Documentation, technical-debt and missing-feature findings (from agent F, `16-documentation-audit.md`, `19-technical-debt-and-code-quality.md`, `20-missing-features-and-functional-gaps.md`)

Note on IDs: the agent wrote its documentation findings as DOC-01 to DOC-13 in file 16. They are not given ISS numbers here. The lead can assign them later if wanted. Status below is AGENT-reported unless marked.

- **ISS-070 (LOW):** Frontend dead modules and an unused dependency (`recharts`), plus a probable unused `components/ui/index.js`.
- **ISS-071 (LOW):** Orphaned or broken backend modules and residue, including 210 tracked PDFs (about 217 MB). Note: `apps/core/sync` is live, not dead, as the agent corrected.
- **ISS-072 (LOW):** Duplicate or parallel screens and helpers (see the frontend inventory, D1 to D12).
- **ISS-073 (MEDIUM):** 74 test functions with no assertions (73 pass-only). Three `tests.py` files are never collected by pytest.
- **ISS-074 (LOW):** Oversized modules. Five app pairs import each other at module level. No model-level cycle found. Heuristic grep result.
- **ISS-075 (HIGH, CROSS-CHECKED):** The password-reset confirmation screen is missing, so the emailed link lands on NotFound. The frontend route inventory shows only `/forgot-password` and no confirm route, which supports this. The API agent independently reported the same gap as ISS-082.
- **ISS-076 (MEDIUM):** The package positive path is not tested end to end. The merged-PDF provenance is wrong. The readiness link is ISS-018.
- **ISS-077 (MEDIUM):** Commission, invoices and payments are partial, and accounting is absent. This is the open accounting-scope question D5.
- **ISS-078 (MEDIUM):** Notifications are missing, master import is CLI-only, bulk operations are partial, and dashboard charts are not built.
- **ISS-079 (MEDIUM):** The audit trail is HTTP-level only. Balance-bearing records are not audited per record, and the documentation overstates the audit trail. Relates to D6.

Documentation summary (AGENT): 45 rows checked; 22 match, 17 contradict, 6 are stale. Historical docs were sampled, not checked claim by claim. A conflict between AGENTS.md and CLAUDE.md on the documentation-only rule is recorded as DOC-08 and not resolved.

Candidate owner questions from agent F (not yet asked, not yet in the register): whether commission accounting (debits, credits, rates) is in V1 or commission is only a trade direction; whether ACCOUNT_ACCESS should be read-only as the docs say or may edit BOE invoice numbers as the code allows; whether emailed-link password reset is required for V1 or admin reset is enough; whether HTTP-level logging is sufficient for audit or balance records need per-record history (D6); whether peer sync is an intended V1 mechanism; the RPO and RTO that apply, and whether a restore must be rehearsed before sign-off; whether notifications and UI master import are in V1; and whether a single merged-licence PDF download must be restored or the package ZIP is enough.
