# 16. Documentation audit

**Agent:** F (documentation, technical debt and missing features audit)
**Evidence snapshot:** branch `version-v1`, working tree as of 2026-11-01, including uncommitted changes (CLAUDE.md, several frontend files, new `docs/v1/` files).
**Method:** read-only. Documentation claims were checked against `requirements.txt`, `frontend/package.json`, `backend/lmanagement/*`, app `urls.py`, models, permissions, middleware, frontend routes and git history. No source file, `CLAUDE.md`, or existing documentation was modified. Secret-bearing files (`.env*`, `auth.json`, `config.toml`, `~/.claude.json`) were not read.
**Finding labels:** documentation findings use `DOC-nn`. The `ISS-070`..`ISS-079` range was split between file 19 (ISS-070..074) and file 20 (ISS-075..079), so no ISS IDs are assigned in this file.

---

## 1. Summary

- The canonical set `docs/01`..`docs/10` is accurate on stack versions, the 15-role model, the API prefix structure, the force-delete absence, JWT storage and the user-management permission. It is wrong or stale on the trade API path, the ACCOUNT_ACCESS permission, the activity log, database table names, database configuration, the allotment entry point, multi-server sync and a few paths.
- 13 documentation findings (DOC-01..DOC-13). The most consequential are the trade path (DOC-01), ACCOUNT_ACCESS documented as read-only (DOC-02), the activity-log description (DOC-03), the undocumented peer-sync layer (DOC-06), and the missing operational runbooks (DOC-13).
- The "Download Merged PDF removed in commit 79a08ac2" statement, repeated in three v1 files, is not supported by git history (DOC-07). Merged-document viewing still exists in three UI places.
- The v1 traceability layer has correct identifiers and counts (354 API operations, 57 routes), but the capability, authorization and existing-test columns are placeholders on every API row (DOC-11). Authorization claims in that layer are therefore not evidenced.
- CLAUDE.md scope amendment is present, correct and consistent with `docs/v1/00-executive-overview/decisions-required.md` (D1..D6). A tracked duplicate rule in `AGENTS.md` was not amended (DOC-08).
- Operational documentation is missing for deployment of the canonical host, backup and restore (tooling exists in `scripts/database/db-tools.sh`, no runbook), and environment variables (26 settings variables are not documented outside `docs/v1`) (DOC-13).

---

## 2. Documentation inventory

Counts are at snapshot time. Other agents are writing `docs/v1/` concurrently, so counts may move.

| Set | Files | Role | Currency |
|---|---:|---|---|
| `docs/01`..`10` | 10 (4,017 lines) | Canonical overview, architecture, features, API, DB, rules, flows, security, integrations, rebuild spec | Mixed; see section 3 |
| `docs/v1/` | 150 | V1 audit layer: `00`..`09`, `system-audit/`, execution logs, registers | Most recent (2026-10-31 to 11-01); self-declares limits |
| `docs/` root status files | about 12 (e.g. `CURRENT_PHASE.md`, `AGENT_STATE.md`, `MODERNIZATION_PROGRESS.md`, `ORCHESTRATOR_HANDOFF.md`, `MODULE_2_FREEZE_READINESS.md`) | Session and handoff state, dated 2026-08-10 | STALE |
| `docs/architecture/` | 28 | Architecture and design notes | Only RBAC doc checked (matches) |
| `docs/modules/` | 74 | Module specifications | Not verified claim by claim |
| `docs/enterprise-rebuild/` | 54 | Rebuild plans | Not verified claim by claim |
| `docs/audit/`, `docs/assessment/`, `docs/discovery/` | 22, 15, 6 | Earlier audit, assessment, discovery reports | Historical |
| `docs/guides/` | 14 | Developer guides | Mixed; commission guide cannot be matched to code |
| `docs/operations/` | 7 | Runbooks and host notes | Narrow; see section 5 |
| `docs/ui-modernization/`, `frontend-migration/`, `orchestrator/`, `decisions/` | 8, 3, 3, 2 | UI and process records | Historical |
| Repository root `*.md` | 258 tracked | Mixed (accessibility logs, A3627 rules, handoffs) | Contradicts `docs/README.md` (DOC-09) |
| `backend/apps/**/*.md` | 17 | Module READMEs and test notes inside source | Unmaintained (DOC-10) |

---

## 3. Documentation set coverage table

Status key: **MATCHES** (claim agrees with code), **CONTRADICTS** (claim disagrees with code), **STALE** (once true, now out of date or unverifiable from code), **MISSING** (required content absent).

| # | Doc path (line) | Claim | Code evidence | Status |
|---|---|---|---|---|
| 1 | `docs/01-project-overview.md:58-69` | Django 6, DRF 3.17, React 19, Tailwind v4, Celery and Redis, PostgreSQL (psycopg 3) | `backend/requirements.txt` (`Django==6.0.4`, `djangorestframework==3.17.1`, `celery==5.6.3`, `psycopg==3.3.3`); `frontend/package.json` (`react ^19.2.0`, `tailwindcss ^4.3.1`) | MATCHES |
| 2 | `docs/01-project-overview.md:37` | "Granular 15-role permission system" | `backend/apps/accounts/views/user_management.py:13-29` `ROLE_CODES` has 15 entries; `docs/architecture/RBAC_DOCUMENTATION.md:13-27` lists the same 15 | MATCHES |
| 3 | `docs/01-project-overview.md:52`; `docs/03-features.md:567` | ACCOUNT_ACCESS = "Finance-focused read access" / "Finance read access" | `backend/apps/accounts/permissions.py:150-156` `AccountAccessPermission` allows read and the `update-invoice-no` write; `backend/apps/bill_of_entry/views/boe.py:131-132` routes that action to it, `:267-270` performs the write. `docs/architecture/RBAC_DOCUMENTATION.md` describes it correctly as "including invoice-number workflows" | CONTRADICTS |
| 4 | `docs/01-project-overview.md:39` | Dashboard "KPI summary with trend charts" | `frontend/src/pages/Dashboard.tsx` contains no chart component. `recharts` (`frontend/package.json:50`) is referenced only by a test mock (`src/pages/Dashboard.test.tsx:14`) and the Vite chunk list (`vite.config.js:107`) | CONTRADICTS |
| 5 | `docs/01-project-overview.md:35`; `docs/09-integrations.md:157-169` | Multi-server sync is the one-way master-sync shell script | `scripts/maintenance/sync-masters.sh` exists and calls `audit_masters` (line 56) and `auto_import_masters` (line 77). Separately, peer push/pull/peers are live: `backend/lmanagement/urls.py:52` (`api/sync/`), `backend/apps/core/apps.py:14-17`, `backend/apps/core/models.py:20`, `SYNC_*` settings. The peer layer is not described in docs 01, 02, 09 or 10 | STALE |
| 6 | `docs/01-project-overview.md:92` | Canonical server pushes masters to labdhi and tractor | Script present. Host topology cannot be verified from code | MATCHES (script only; topology unverified) |
| 7 | `docs/01-project-overview.md:64` | JWT with refresh rotation and token blacklisting | `rest_framework_simplejwt.token_blacklist` is in `INSTALLED_APPS` (`backend/lmanagement/settings.py`). Rotation flag not checked | MATCHES (blacklist confirmed; rotation unchecked) |
| 8 | `docs/02-architecture.md:306`; `docs/10-rebuild-spec.md:301` | `DATABASE_URL` is the PostgreSQL connection setting | `backend/lmanagement/settings.py:201-216` reads `DB_NAME`, `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT`. `DATABASE_URL` is not referenced | CONTRADICTS |
| 9 | `docs/03-features.md:120`, `:143` | Allotment item "is entered manually in `AllotmentFormModal`" | `frontend/src/components/AllotmentFormModal.tsx` has no importer. Allotment create/edit runs in the routed page `frontend/src/pages/AllotmentAction.tsx` | CONTRADICTS |
| 10 | `docs/03-features.md:384` | Ledger PDF and Excel export in `frontend/src/utils/ledgerExport.ts` | File does not exist. Export is server-side: `backend/apps/license/services/exporters/license_balance_pdf.py`, `license_balance_excel.py`, `financial_ledger_*_renderer.py`; ledger export action at `backend/apps/license/views/ledger.py:643` | STALE |
| 11 | `docs/03-features.md:51`, `:493` | Endpoint `POST /api/licenses/bulk_balance_excel/` | `backend/apps/license/views/license.py:892` declares `url_path='bulk-balance-excel'`, so the route is `/api/licenses/bulk-balance-excel/` (hyphen) | CONTRADICTS |
| 12 | `docs/03-features.md:547` | Admin password reset `POST /api/auth/users/:id/reset-password/` | `backend/apps/accounts/views/user_management.py:61-62`; UI at `frontend/src/pages/admin/UserForm.tsx:120-284` | MATCHES |
| 13 | `docs/03-features.md:161-184` (F-05) | Trade models `LicenseTrade`, `LicenseTradeLine`, `IncentiveTradeLine`, `LicenseTradePayment`; directions PURCHASE, SALE, COMMISSION_PURCHASE, COMMISSION_SALE | `backend/apps/trade/models.py:138`, `:495`, `:581`, `:650`; direction docstring `:79-90` | MATCHES |
| 14 | `docs/03-features.md:396` (F-07) | Ledger upload accepts CSV or HTM, processed asynchronously | `backend/apps/license/urls.py:51,53` (`upload-ledger/`, `ledger-task-status/<id>/`); `backend/apps/license/views/ledger_upload.py:22-70` (`LedgerUploadView`, `_is_htm`, `_is_csv`); `frontend/src/pages/LedgerUpload.tsx` | MATCHES |
| 15 | `docs/09-integrations.md:20` | `LedgerUpload.tsx` polls the task status every second | `frontend/src/pages/LedgerUpload.tsx:164-186` (`setInterval`, 1000 ms) | MATCHES |
| 16 | `docs/04-api.md:152, 182, 188, 211` (24 lines in total); `docs/06-business-rules.md:220`; `docs/07-user-flows.md:245, 348, 402` | Trade API lives at `/api/trade/trades/` | `backend/lmanagement/urls.py:48` includes the trade app under `api/`; `backend/apps/trade/urls.py:11` registers `trades`, so the route is `/api/trades/`. Frontend calls `trades/` (`frontend/src/pages/TradeForm.tsx:67,158,706`). v1 register rows API-333..335 use `/api/trades/` | CONTRADICTS |
| 17 | `docs/04-api.md:145` | `POST /api/trade/trades/:id/generate-transfer-letter/` | Action exists at `backend/apps/trade/views.py:617-618`; route is `/api/trades/...`. Path wrong, feature present | CONTRADICTS |
| 18 | `docs/04-api.md` headings 7-95, 268, 291, 331 | Prefixes `/api/auth/`, `/api/licenses/`, `/api/license-ledger/`, `/api/incentive-licenses/`, `/api/bill-of-entries/`, `/api/allotments/`, `/api/upload-ledger/`, `/api/ledger-task-status/`, `/api/masters/`, `/api/sion-planning-rules/`, `/api/tasks/` | `backend/lmanagement/urls.py:44-52`; `backend/apps/license/urls.py:28-63`; `backend/apps/bill_of_entry/urls.py:10-13`; `backend/apps/allotment/urls.py:10-11`; `backend/apps/tasks/urls.py:9`; `backend/apps/core/urls.py:21-35` | MATCHES |
| 19 | `docs/04-api.md:209-211` | "Force delete: no API endpoint" | No `force` parameter in `backend/apps/trade/views.py` | MATCHES |
| 20 | `docs/05-database.md:162`; `docs/03-features.md:32` | Table `license_licenseexportitemsmodel` | No `db_table` override. `LicenseExportItemModel` (`backend/apps/license/models/core.py:860`) gives `license_licenseexportitemmodel` | CONTRADICTS |
| 21 | `docs/05-database.md:307-309, 328, 345, 354` | Tables `trade_licensetradelineitem`, `trade_incentivetradelineitem`, `trade_licensetradepaymment` | No `db_table`. Models `LicenseTradeLine` (`trade/models.py:495`), `IncentiveTradeLine` (`:581`), `LicenseTradePayment` (`:650`) give `trade_licensetradeline`, `trade_incentivetradeline`, `trade_licensetradepayment`. The migration `CreateModel` names confirm the model names (`backend/apps/trade/migrations/`) | CONTRADICTS |
| 22 | `docs/05-database.md:105`; `docs/08-security.md:106` | `core_activitylog` has a `request_body` (truncated) column | `backend/apps/core/models.py:832` `ActivityLog` has no `request_body` field; no code writes one (only a test name matches) | CONTRADICTS |
| 23 | `docs/08-security.md:110` | Activity log "captures 4xx and 5xx responses" | `backend/apps/core/middleware.py:138-150` writes for every authenticated `/api/` non-OPTIONS request, whatever the status. The claim understates the scope rather than contradicting it | CONTRADICTS |
| 24 | `docs/08-security.md:111` | Body captured for non-GET requests; sensitive fields masked | No body capture in `_write_log_entry` (`middleware.py:112-134`). Field masking exists in a different place: `backend/apps/core/serializers/models.py:32-60` (`SENSITIVE_FIELDS`) | CONTRADICTS |
| 25 | `docs/08-security.md:112` | Activity log queryable at `/admin/activity-log` (superuser) | `backend/apps/core/admin.py:59-72` registers core models in a generic loop, so the URL is `/admin/core/activitylog/`. No custom path found | CONTRADICTS |
| 26 | `docs/08-security.md:37` | `UserManagementPermission`: USER_MANAGER or superuser | `backend/apps/accounts/permissions.py:109-112` | MATCHES |
| 27 | `docs/08-security.md:13`, `:134` | JWT access and refresh tokens stored in `localStorage` | `frontend/src/context/AuthContext.tsx:79, 123, 195` read tokens from `localStorage` | MATCHES |
| 28 | `docs/08-security.md:89` | Throttle status at `/api/masters/throttle-status/` | `backend/apps/core/urls.py:39` under the `api/masters/` include | MATCHES |
| 29 | `docs/v1/09-traceability/api-operation-register.tsv` (354 rows) | 354 API operations with route, authorization and test evidence | Identifiers and count match (354 unique `API-NNN`). `business_capability`, `authorization`, `existing_tests` hold placeholder values on 354 of 354 rows ("Requires source classification", "To reconcile") | STALE (content placeholders) |
| 30 | `docs/v1/09-traceability/traceability-coverage.md:27` | 57 frontend routes, "static route evidence complete" | `frontend-route-register.tsv` has 57 rows; `frontend/src/routes/AppRoutes.tsx` is consistent with that count | MATCHES |
| 31 | `docs/v1/system-audit/inventories/frontend-route-inventory.md:178-184` | Eight frontend modules "VERIFIED dead" | All eight confirmed with no importer (see file 19). Omits `utils/canonicalLedgerAdapter.js`, `components/ui/index.js` and the unused `recharts` dependency | MATCHES (eight confirmed; three omissions) |
| 32 | `docs/v1/system-audit/inventories/backend-app-inventory.md:55` (BE-INV-08) | `apps/accounts/tests.py`, `apps/tasks/tests.py`, `apps/trade/tests.py` never collected | `backend/pytest.ini` `python_files = test_*.py`; the three files exist and are not `test_*.py` | MATCHES |
| 33 | `docs/v1/00-executive-overview/decisions-required.md:5-10` | Owner decisions D1..D6 referenced by CLAUDE.md | Rows D1..D6 present | MATCHES |
| 34 | `CLAUDE.md:3` | Two-line scope amendment for the V1 mission; original rule unchanged | `git diff --stat -- CLAUDE.md`: 2 insertions, 0 deletions. `docs/v1/execution-log.md:97` records the same | MATCHES |
| 35 | `AGENTS.md` (Specialist agents paragraph and `Rules`, lines about 46-50) | Repeats "Never modify source code." and refers to `.Codex/rules.md` and `.Codex/agents/README.md` | No amendment. `.claude/rules.md` exists; `.Codex` (capital) does not exist; `.codex` (lowercase) exists. Case-sensitive filesystems will not resolve the path | CONTRADICTS |
| 36 | `docs/README.md:3` | "All project documentation lives under this docs/ directory. Root is kept clean." | 258 tracked `*.md` files at the repository root (`git ls-files '*.md' \| grep -v /`) | CONTRADICTS |
| 37 | `docs/README.md` (Architecture references) | `RBAC_DOCUMENTATION.md` describes a "12-role permission system" | The RBAC document lists 15 roles; code has 15 | CONTRADICTS |
| 38 | `docs/CURRENT_PHASE.md`, `AGENT_STATE.md`, `MODERNIZATION_PROGRESS.md`, `ORCHESTRATOR_HANDOFF.md`, `MODULE_2_FREEZE_READINESS.md` (line 2-4, "Last Updated 2026-08-10") | Describe the "current" phase and state | Dated about 12 weeks before the 2026-11-01 snapshot. v1 audit has superseded them, but they carry no supersession notice in their headers | STALE |
| 39 | `docs/v1/system-audit/execution/discovered-issues.md:39`; `docs/v1/execution-log.md:141`; `docs/v1/08-implementation/checkpoint-2026-10-31-resume-3.md:24` | "Download Merged PDF" control removed in commit `79a08ac2` | Git: the string first appears in `a4ce8d44` (2026-10-17, sr-only span in the ledger toolbar). `79a08ac2` adds e2e assertions that click "Download Merged PDF (1)" and adds the package back end. HEAD `frontend/src` has no such string. The removing commit was not isolated. Merged-document viewing still exists: `frontend/src/pages/masters/tables/LicensesTable.tsx:1028-1147`, `components/AccordionTable.tsx:489`, `components/LicenseBalanceModal.tsx:449`, backed by `backend/apps/license/views/license.py:965` | CONTRADICTS |
| 40 | `docs/v1/07-quality-and-operations/backup-and-recovery.md:3` | No production backup or restore evidence observed | Consistent. `scripts/database/db-tools.sh` has backup and restore commands (lines 178-181, 191+) but no runbook or verified restore | MATCHES (gap stated honestly) |
| 41 | `docs/v1/07-quality-and-operations/deployment-readiness.md:14`, `:26` | Production deployment and restore not verified | Consistent with `scripts/deployment/*` existing without evidence of execution | MATCHES |
| 42 | `backend/apps/license/services/exporters/GAPS_ANALYSIS.md:5` | "All required fields are present. Zero gaps." | Source-tree document with no maintenance trail; not verifiable from code and sits next to the renderer it describes | STALE |
| 43 | `scripts/maintenance/sync-masters.sh:16` (header cron example) | Path `/Users/drushahardiksottany/PycharmProjects/license-manager` | Current checkout is `.../Developer/projects/license-manager`. `docs/09-integrations.md:169` uses `/path/to` instead | STALE |
| 44 | `docs/03-features.md` (F-08, line 147, 426) | Transfer letters for BOE, trade and allotment | BOE action `backend/apps/bill_of_entry/views/boe.py:225`; trade action `backend/apps/trade/views.py:617`; allotment caller `frontend/src/components/TransferLetterForm.tsx:164` | MATCHES |
| 45 | `docs/03-features.md` (F-02, F-04) | Incentive licences and allotments routed | `backend/apps/license/urls.py:40`; `backend/apps/allotment/urls.py:10-11`; `frontend/src/routes/AppRoutes.tsx:214-224` | MATCHES |

**Tally (rows 1-45, recounted from the table):** MATCHES 22; CONTRADICTS 17 (rows 3, 4, 8, 9, 11, 16, 17, 20, 21, 22, 23, 24, 25, 35, 36, 37, 39); STALE 6 (rows 5, 10, 29, 38, 42, 43); MISSING 0 in this table. Missing operational content is recorded in section 5 and DOC-13 instead. Rows 6 and 7 are MATCHES with qualifiers stated in the row.

---

## 4. Route, API, role and business-rule claim checks

Method: prefixes and router registrations were checked for every heading in `docs/04-api.md`. Permission classes were checked for each role named in `docs/01` and `docs/03`. The v1 register was sampled (identifiers, counts, and the trade path).

- **Routes:** 11 documented prefixes match registrations. One documented family (trade) does not (DOC-01).
- **Roles:** 15 roles match between `ROLE_CODES` and `docs/architecture/RBAC_DOCUMENTATION.md`. One role's documented capability is incomplete (ACCOUNT_ACCESS, DOC-02).
- **Business rules:** Business-rule claims in `docs/06-business-rules.md` were not verified one by one. The sale-quantity guard described in `docs/03-features.md:232-239` was not traced to code in this pass. Status: UNVERIFIED for individual rules.
- **Permissions:** `docs/08-security.md:37-41` (superuser bypass, user-management gate) matches `BaseRolePermission` in `backend/apps/accounts/permissions.py:5-31`.

---

## 5. Operational documentation gaps

| Area | What exists | What is missing | Status |
|---|---|---|---|
| Deployment (canonical host) | `scripts/deployment/` has 8 scripts (`auto-deploy.sh`, `deploy-license-manager.sh`, `deploy-indexes.sh`, `run-deploy.sh`, `verify-deployment.sh`, `setup-ssl-tractor.sh`, `license-manager-watchdog.sh`, `license-manager-celery.conf`); `backend/deploy/celery.service`; `docs/operations/` has host notes for the tractor server and `mds-deployment.md` | No consolidated deployment runbook for the license-manager host outside `docs/v1`. `docs/v1/07-quality-and-operations/deployment-readiness.md` says production deployment is not verified | MISSING |
| Backup and restore | `scripts/database/db-tools.sh` (backup, restore, sync; line 178-181); `scripts/database/audit-db-integrity.sh`; `docs/v1/07-quality-and-operations/backup-and-recovery.md` (states no evidence) | Operator runbook, restore test record, recovery objectives | PARTIAL tooling; MISSING runbook |
| Environment variables | `backend/lmanagement/settings.py` reads at least 52 literal variable names. `docs/v1/07-quality-and-operations/operational-configuration-contracts.md` names only `MDS_ENABLED` and `SYNC_ENABLED` among them | 26 literal names are not mentioned in any non-v1 document, e.g. `ACCESS_TOKEN_MINUTES`, `EMAIL_HOST`, `EMAIL_HOST_USER`, `FRONTEND_URL`, `DEFAULT_FROM_EMAIL`, `DJANGO_ENVIRONMENT`, `LICENSE_PACKAGE_*_TIME_LIMIT`, `LICENSE_REPLAN_*_TIME_LIMIT`, `RECONCILIATION_CIF_TOLERANCE`, `RECONCILIATION_QTY_TOLERANCE`, `SYNC_ENABLED`, `SYNC_PEER_TOKENS`, `SYNC_PUSH_ON_SAVE`, `SYNC_SERVER_ID`, `CELERY_WORKER_PREFETCH_MULTIPLIER`, `DGFT_*` and others. Two docs cite `DATABASE_URL`, which the code does not read | MISSING (reference); CONTRADICTS (DATABASE_URL) |
| Runbooks | `docs/operations/auth-user-fk-repoint-runbook.md` (one explicit runbook); `docs/media-security-cutover.md` | Sync failure handling for `scripts/maintenance/sync-masters.sh` (failed rows written to `/tmp`), Celery worker and beat operation, incident response | MISSING |
| Observability | `docs/v1/07-quality-and-operations/observability.md` | Not verified against code in this pass | UNVERIFIED |
| Master sync | `scripts/maintenance/sync-masters.sh`; `scripts/maintenance/_master_sync_lib.sh`; `docs/09-integrations.md:157-169` | Current peer-sync operation (`apps/core/sync`) has no operator document; the script header path is stale (DOC-12) | PARTIAL |

---

## 6. CLAUDE.md scope amendment and conflicting references

- `CLAUDE.md:3` carries the amendment for the V1 implementation mission. It is two inserted lines and leaves the original rule at `CLAUDE.md:52` unchanged, as `docs/v1/07-quality-and-operations/ecc-project-rules-draft.md` describes. The amendment's conditions reference `docs/v1/00-executive-overview/decisions-required.md` (D1..D6), which exists.
- `.claude/agents/technical-writer.md` and `.claude/agents/README.md` say the technical writer edits `docs/` only. This is consistent with both the original rule and the amendment.
- `AGENTS.md` (tracked, root) still carries the unamended "Never modify source code." rule and points to `.Codex/` paths. It contradicts the amendment and is the only remaining conflicting reference found (DOC-08).
- `docs/v1/09-traceability/documentation-consistency-audit.md` restricts its own scope to documentation integrity. This is a scope statement for that audit, not a conflict.

Verdict: the amendment is correctly scoped and resolved in the authoritative file. One tracked duplicate remains and needs an owner decision on whether to amend it.

---

## 7. Findings

Severity reflects impact on someone rebuilding or operating the system from the documents.

### DOC-01: Trade API path documented incorrectly (High)
- Evidence: `docs/04-api.md` (24 occurrences, e.g. 152, 182, 188, 211, 145), `docs/06-business-rules.md:220`, `docs/07-user-flows.md:245, 348, 402`. Code: `backend/lmanagement/urls.py:48`, `backend/apps/trade/urls.py:11`, `frontend/src/pages/TradeForm.tsx:67`.
- Code path is `/api/trades/`; the register (API-333..335) and the frontend agree with the code.
- Correction direction: documents should use `/api/trades/`.

### DOC-02: ACCOUNT_ACCESS documented as read-only (High)
- Evidence: `docs/01-project-overview.md:52`, `docs/03-features.md:567`. Code: `backend/apps/accounts/permissions.py:150-156`, `backend/apps/bill_of_entry/views/boe.py:131-132, 267-270`.
- The architecture RBAC document is correct; the overview and features documents understate ACCOUNT_ACCESS. Any permission review built from the overview would miss the `invoice_no` write.
- Correction direction: state read access plus the `invoice_no` write. The product question is recorded in file 20.

### DOC-03: Activity log described beyond what the code does (High)
- Evidence: `docs/08-security.md:106, 110-112`, `docs/05-database.md:105`. Code: `backend/apps/core/models.py:832` (no `request_body`), `backend/apps/core/middleware.py:112-150`, `backend/apps/core/serializers/models.py:32-60`, `backend/apps/core/admin.py:59-72`.
- Three claims are wrong: a `request_body` column, a 4xx/5xx-only capture (understated), and the admin URL. The masking claim is right but attributed to the wrong mechanism.
- Correction direction: describe the middleware as writing one row per authenticated `/api/` request, with the serializer masking, and remove the `request_body` column.

### DOC-04: Table names and database configuration documented incorrectly (Medium)
- Evidence: `docs/05-database.md:162, 307-309, 328, 345, 354`; `docs/03-features.md:32`; `docs/02-architecture.md:306`; `docs/10-rebuild-spec.md:301`. Code: `backend/apps/license/models/core.py:860`, `backend/apps/trade/models.py:495, 581, 650`, `backend/lmanagement/settings.py:201-216`.
- A rebuilder following `docs/10` would configure `DATABASE_URL` (not read) and create tables with the wrong names. `trade_licensetradepaymment` has a spelling error.
- Correction direction: use the derived table names and `DB_*` variables.

### DOC-05: Allotment entry point, ledger export file and bulk Excel route (Medium)
- Evidence: `docs/03-features.md:120, 143` (`AllotmentFormModal`), `:384` (`ledgerExport.ts`), `:51, 493` (`bulk_balance_excel`). Code: `frontend/src/components/AllotmentFormModal.tsx` (no importer), `frontend/src/pages/AllotmentAction.tsx`, `backend/apps/license/views/license.py:892`.
- Correction direction: name the routed allotment page, drop the missing file path, and use `bulk-balance-excel`.

### DOC-06: Peer sync layer undocumented (High)
- Evidence: `docs/09-integrations.md:157-169`, `docs/01-project-overview.md:35, 92`. Code: `backend/lmanagement/urls.py:52`, `backend/apps/core/sync/` (`urls.py`, `views.py`, `push.py`, `tasks.py`, `service.py`), `backend/apps/core/apps.py:14-17`, `backend/apps/core/models.py:20`, `SYNC_*` settings.
- The sync app is not in `INSTALLED_APPS` by design, but its models are registered under `core` (`app_label = "core"`). It is live code. The v1 documents mention it in 15 files, but the canonical integration document does not.
- Correction direction: document the peer layer, its endpoints and its configuration, or record why it is out of scope.

### DOC-07: "Download Merged PDF removed in commit 79a08ac2" not supported (Medium)
- Evidence: `docs/v1/system-audit/execution/discovered-issues.md:39`, `docs/v1/execution-log.md:141`, `docs/v1/08-implementation/checkpoint-2026-10-31-resume-3.md:24`. Git: `a4ce8d44` added the control; `79a08ac2` added e2e assertions for it and the package back end (`git show 79a08ac2 | grep "Download Merged PDF"` shows only added test lines). HEAD `frontend/src` no longer contains the string.
- The removal commit was not isolated. Three UI paths still open merged documents (see row 39). The E2E spec `frontend/e2e/package-download.spec.ts:6` repeats the claim.
- Correction direction: restate what was removed and in which commit, once verified.

### DOC-08: Tracked AGENTS.md conflicts with the CLAUDE.md amendment (Medium)
- Evidence: `AGENTS.md` (rule line about 50; `.Codex/` paths about 43-46). Amendment: `CLAUDE.md:3`.
- Correction direction: owner decision whether to amend `AGENTS.md` and correct the `.Codex/` paths (repository uses `.claude/` and `.codex/`).

### DOC-09: Root sprawl and the docs index contradict themselves (Low)
- Evidence: `docs/README.md:3` ("Root is kept clean"); 258 tracked root `*.md` files; `docs/README.md` (Architecture references) "12-role" versus the RBAC document's 15 roles.
- Correction direction: owner decision on whether root reports belong under `docs/`; the index wording should match the RBAC document.

### DOC-10: Stale status files and source-tree documents (Low)
- Evidence: `docs/CURRENT_PHASE.md`, `AGENT_STATE.md`, `MODERNIZATION_PROGRESS.md`, `ORCHESTRATOR_HANDOFF.md`, `MODULE_2_FREEZE_READINESS.md` (dated 2026-08-10); `backend/apps/license/services/exporters/GAPS_ANALYSIS.md:5`; 17 `*.md` files under `backend/apps/`.
- Correction direction: add supersession notices or move historical state files; remove "zero gaps" claims that are not maintained.

### DOC-11: Traceability register content is placeholder (Medium)
- Evidence: `docs/v1/09-traceability/api-operation-register.tsv` (354 rows; columns 9, 11, 12 hold "Requires source classification" and "To reconcile"). `traceability-coverage.md` counts identifiers and says so ("fields supported by current evidence"), but the authorization column is what a reader would rely on.
- Consistent with the consistency audit's own limits. The issue is that authorization evidence is not yet present for any API operation.
- Correction direction: populate per-operation authorization and test evidence, or label the columns as not yet assessed.
- Related: the frontend route inventory omits `utils/canonicalLedgerAdapter.js`, `components/ui/index.js` and `recharts` (file 19).

### DOC-12: Stale path in the sync script header (Low)
- Evidence: `scripts/maintenance/sync-masters.sh:16` (`/Users/drushahardiksottany/PycharmProjects/license-manager`).
- Correction direction: update to the current checkout location or use a placeholder, as `docs/09-integrations.md:169` does.

### DOC-13: Operational documentation missing (High for V1 completion)
- Evidence: section 5. Environment variables: 26 literal settings names undocumented outside v1. Backup and restore: tooling only. Deployment: scripts only. Runbooks: one.
- Correction direction: the owner's V1 gates (`docs/v1/07-quality-and-operations/backup-and-recovery.md`, `deployment-readiness.md`) need a runbook and an environment reference before they can be closed.

---

## 8. Limits

- Static reading and grep only. No runtime checks, no browser, pytest and npm were not run.
- Sampled rather than exhaustive: about 300 files across `docs/architecture`, `modules`, `enterprise-rebuild`, `audit`, `assessment`, `discovery`, `ui-modernization`, `orchestrator`, `frontend-migration` and most guides were classified by header, date and sampling, not claim by claim.
- `docs/04-api.md` was checked at the prefix and path level. Per-endpoint request and response contracts were not verified. The v1 register was checked for identifiers, counts and the trade path, not row by row.
- The merged-PDF removal commit was not isolated; the `79a08ac2` finding is about the claim's provenance, not its truth.
- Line numbers refer to the working tree on 2026-11-01, including uncommitted changes.
- `docs/v1/` is being written by other agents; counts in section 2 may change.
