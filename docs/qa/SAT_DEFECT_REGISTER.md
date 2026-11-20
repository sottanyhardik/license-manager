# SAT Defect Register (consolidated)

Branch `feature/v5` @ `ec3604cb` + 178 peer-owned uncommitted paths (diff hash `6f1712e03000`). Audit only: **no defect
has been fixed**. Source IDs point to the phase reports, which hold the full repro steps and evidence:
`SAT-FIN-Dnn` → `SAT_FINANCIAL_AUDIT.md` §5 · `SAT-EXP-Dnn` → `SAT_EXPORT_AUDIT.md` §7 · `SAT-API-Dnn` →
`SAT_API_DATABASE_AUDIT.md` · `SAT-SEC-Dnn` → `SAT_SECURITY_PERFORMANCE.md` · `SAT-UX-Dnn` → `SAT_UI_UX_AUDIT.md`.
Classes: CD = confirmed defect · SD = suspected defect · DQ = data quality · BRA = business-rule ambiguity ·
ENV = environment limitation. "Appr." = business approval needed before remediation.

Raw logs for the Phase 3/6 IDs were in `/tmp/sat/`, which was wiped between sessions. The figures below are taken
from the reports, and Phase 9 re-derives a sample (`SAT_INDEPENDENT_REVIEW.md`).

## Financial (Phase 3)

| ID | Source | Sev | Class | Module | Defect | Scope / financial impact | Root cause | Remediation | Appr. |
|---|---|---|---|---|---|---|---|---|---|
| SAT-DEF-001 | SAT-FIN-D01 | High | CD | Licence item balance | ARO (`AR`) allotment qty is never deducted from item available qty. The writer filters `type='ARO'` on a 2-char field, and the live calculator deducts AT only | 157 items / 156 licences. Available qty overstated by 40,992,712.93 kg. Item-level CIF omits 17,934,272.36 vs licence level | `core/scripts/calculate_balance.py:79-81`; `license/services/balance_calculator.py:919,957` | Use `'AR'`; deduct AR outstanding in the live item calculator | Y (confirm AR = consumption, DEC-01) |
| SAT-DEF-002 | SAT-FIN-D02 | High | CD + DQ | Allotment reservation | Two definitions of "consumed". The engine treats `is_boe=True` with no M2M link as outstanding; the planning reconciliation treats it as consumed. **Phase 9 correction:** a double count is *proven* for 235,475.75 and plausible for 76,000 of the 1,160,224.05 flagged. The headline pair 8357 ↔ BOE 25789 is **refuted**: BOE 25789 is linked to twin allotment 8369, so 8357 is a **duplicate allotment**. Only 2 of the 4 over-utilised flags are supported | 12 allotments / 15 items / 13 licences, Σ 1,160,224.05 flagged | `balance_calculator._annotate_allotment_contribution` vs `planning_usage_reconciliation.aggregate_license_usage:119-125` | One rule (DEC-02), then a per-case data fix: delete duplicate allotments (8357), and link only where a matching unlinked BOE exists. **No bulk linking** | Y |
| SAT-DEF-003 | SAT-FIN-D03 | Medium | SD / DQ | BOE | BOE 8391561 is stored twice (ids 28686 and 27109): same port, company, invoice, item, CIF and qty, different dates. Both are debited | 1 licence (5211018767), 14,835.86 CIF | `unique_together=(number,date)` allows it | Owner confirms it is a duplicate; remove it through the UI | Y (DEC-03) |
| SAT-DEF-004 | SAT-FIN-D04 | Medium | DQ / rule gap | Allotment ↔ BOE | An allotment linked only to a rowless BOE (including placeholder `1234567`) releases its reservation, and nothing is debited | 10 allotments / 16 items, 665,624.43 CIF (net 477,524.43 after the real twin BOE) | M2M full-consumption rule | Rule decision (DEC-03); fix the data | Y |
| SAT-DEF-005 | SAT-FIN-D09 | Medium | CD | Item balance (shared-ceiling) | For `cif_fc=0` items the item cap ignores sibling allotments, AR and hidden BOEs, so it can exceed the licence balance | Not measured on the DB. Used by INDIVIDUAL mode, legacy `allocation_service:73` and `sion_planning_execution:1585` | `ItemBalanceCalculator.calculate_item_credit_debit` | Cap at the licence balance (owner D-A already decided "capped at licence bal.") | N (D-A decided) |
| SAT-DEF-006 | SAT-FIN-D08 | Low | SD (latent) | Allotment items | The RELEASED/COMPLETED status is never written and never read, so a released item would still reserve CIF | 0 rows today | `AllotmentItems.status` | Honour the status or remove it | Y (DEC-07) |
| SAT-DEF-007 | SAT-FIN-D06 | Low | **BRA** (latent). Phase 9: `LEDGER_APPROVED_SEMANTICS` governs the ledger, not explicitly the CIF engine | Financial engine purchase credit | COMMISSION_PURCHASE counts as purchase credit and zeroes the opening balance; COMMISSION_SALE is ignored | 0 trades locally, so latent | `get_purchase_trade_rows`, `has_purchase_for_licenses`, `calculate_trade` | Owner rules (DEC-06) | Y |

Business-rule ambiguities from Phase 3 (no defect until the owner rules): FIN-D05 cross-licence M2M (8,133,632.89)
and FIN-D07 disputed rows still debited (131,125.49). See
`SAT_USER_DECISION_REGISTER.md`.

Carried, decided but not implemented (not new): RC3, RC4a/b, RC7, RC11–RC16, N1–N4. Owner decisions D-A…D-F and
D1–D4 are in `docs/decisions/2026-11-20-*`. Cross-surface re-run: 4,831 discrepancies on 2,071 licences, identical to
the prior report.

## Phase 9 new findings (independent reviewer, `SAT_INDEPENDENT_REVIEW.md` §10; evidence `~/lm_sat_evidence/review/`)

| ID | Source | Sev | Class | Module | Defect | Scope / impact | Root cause | Appr. |
|---|---|---|---|---|---|---|---|---|
| SAT-DEF-070 | NEW-01 | **High** | CD (committed code, in HEAD) | Bulk Balance Excel | "Balance CIF $" comes from the customs engine **without the hidden-BOE deduction**, so it overstates available CIF by the full previous-owner total. The code comment claims it equals `get_balance_cif`. Controller re-checked the code and the reviewer's cell dump | 11 hidden-BOE licences, Σ +4,412,937.86. e.g. 0311002454: Excel 328,985.02 vs licence 7,926.03; 0311052122: 5,427,238.15 vs 2,649,495.02 | `exporters/license_balance_excel_bulk.py:375` (HEAD `:361`) `calculate_balance_for_licenses`; `float()` at `:160` | N (`get_balance_cif` = financial is established) |
| SAT-DEF-071 | NEW-02 | Medium | CD | Stored `LicenseBalance.balance_cif` cache | Stale on 38 licences: all 36 negatives stored as 0.00 (pre-2026-11-16 floor), plus 2 stale positives. The `balance_cif_min/max` and `has_balance` filters, the `is_null` flag and the materialized views read it. `balance_cif_max=-1` returns none of the 36 over-utilised licences | 3411008583: stored 1,639,086.95 vs live 1,895,326.95 (Δ 256,240) | `core/filtersets.py:136-137,184-186`; `materialized_views.py:419` | N (D-D "one writer" decided) |
| SAT-DEF-072 | NEW-03 | Medium | Process risk | Item screens | Implementing D-D (live values) before SAT-DEF-001 would make 157 item screens jump to the overstated quantities (up to +3.84 M kg each) | 0310825235/2393: stored 10 → live 3,838,607 | sequencing | N: fix DEF-001 first |
| SAT-DEF-073 | NEW-04 | Low | CD | Exports / dashboard | `float` on money: `license_balance_excel_bulk.py:160`, `dashboard.py:282`, `item_pivot_row.py:213` | — | Decimal invariant | N |
| SAT-DEF-074 | NEW-05 | Low (latent) | CD | Balance engine | Single/bulk parity gap: `bill_of_entry__isnull=False` exists only on the single path | 0 rows today | `balance_calculator.py` | N |

Phase 9 status corrections (they override the phase reports):
- X03 bulk Balance Excel: PASS-EXC → **FAIL** (SAT-DEF-070).
- X07 ledger package PDF: BLOCKED → **NOT-RUN** (it was never retried with one licence id).
- SAT-FIN-004/005: PASS on test DB → **NOT VERIFIED ON REAL DATA** (0 trades locally).
- Identical-row BOE pairs: 2,170 pairs. The "consecutive containers" claim fails for 1,258, and **461 manual pairs (33.8 M CIF) are unproven possible duplicates**. They need an owner / DGFT-ledger check (DEC-03).

## Exports (Phase 6)

| ID | Source | Sev | Class | Module | Defect | Scope / impact | Root cause | Remediation | Appr. |
|---|---|---|---|---|---|---|---|---|---|
| SAT-DEF-010 | SAT-EXP-D01 | High | CD (cross-surface contradiction) | Balance Excel / balance-ledger screen / ledger statements | For the same licence, the Financial Ledger sheet prints "MISMATCH vs Balance Engine / RECONCILIATION FAILED" while the Balance PDF says MATCHED. "Current Balance" is the invoice-only canonical ledger, which **is the approved definition** (`LEDGER_APPROVED_SEMANTICS.md`, Phase 9). The defect is the false FAILED verdict and the PDF/Excel contradiction, not the number. Phase 9 correction: 0310827509 showing 0.00 is not a floor; its original CIF is 0 | 15/16 sampled licences with BOEs. e.g. 0310815822: 978,259.87 vs 223.72; 0310827509: 0.00 vs −3,447,851.40 | `license_balance_ledger_builder.py:664-671` | Decide the ledger semantics (DEC-04), then use one source for PDF and Excel | Y |
| SAT-DEF-011 | SAT-EXP-D02 | **Medium** (was High; Phase 9: no value is wrong) | CD | Item Pivot Excel | Every numeric and date cell on the per-licence sheets is text, so SUM, sort and filter don't work | All norms (X18); values themselves match the screen (0 numeric diffs) | `item_pivot_excel.py:283-360` | Convert to Decimal/date and apply number formats | N |
| SAT-DEF-012 | SAT-EXP-D10 | Medium | CD | License-ledger export | Single-licence xlsx: the summary has no licence row (GRAND TOTAL 0) while the trade sheet totals 978,259.87. The default scope returns 404 | BOE-only licences | Summary lists only licences with trade rows | Depends on DEC-04 | Y |
| SAT-DEF-013 | SAT-EXP-D03 | Medium | CD | Master list export | Licence list export dates are `DD-MM-YYYY` text, not date cells | ~950 cells | master `_export_xlsx` uses serializer strings | Write real dates | N |
| SAT-DEF-014 | SAT-EXP-D05 | Low | CD (known) | Customs Ledger PDF | N4 unit totals split by case (`kg`/`KG`); RC13 floor; RC14 tautological "PASS", including on over-utilised licences | Reproduced on 3411007247, 5211019110, 5211018767, 0310827509 | `custom_ledger_pdf.py:90-99` | Already decided (D-A…D-F) | Y (RC14 wording) |
| SAT-DEF-015 | SAT-EXP-D06 | Low | SD | Allotment letter PDF | The subject shows the required qty, not the allotted qty (2,500,000 vs 2,082,810 Kgs) and doesn't signal the shortfall; `int()` truncation; header CIF 0.00 | 12/12 letters checked | allotment PDF script | Show the allocated total / flag the shortfall | Y (letter content) |
| SAT-DEF-016 | SAT-EXP-D07 | Low | CD | Balance PDF | The Export Items table prints the literal `None` | 0310815822 | renderer | Render "-" | N |
| SAT-DEF-017 | SAT-EXP-D08 | Low | CD | Balance Excel Timeline | "BOE Filed" shows the record creation timestamp, not the BOE date | all | timeline builder | Use the BOE date | N |
| SAT-DEF-018 | SAT-EXP-D09 | Low | CD | Customs Ledger PDF layout | Date and header wrap mid-value; wide empty column | visual | column widths | Adjust widths | N |
| SAT-DEF-019 | SAT-EXP-D11 | Low | BRA | Item Report Excel | Items sharing HSN + item name are merged without a label (2,198 rows vs 3,233 screen items) | X19 | exporter grouping | Label the merge or don't merge (DEC-08) | Y |
| SAT-DEF-020 | SAT-EXP-D12 | Low | CD | Balance Excel / PDF formatting | Qty 2dp on ledger sheets (owner D-F says 3dp); no autofilter; PDF has no thousands separators | 6,283 BOE rows have a non-zero 3rd decimal | formats | Apply D-F | N (D-F decided) |
| SAT-DEF-021 | SAT-EXP-D13 | Low | CD (dead code) | Allotment API client | `exportAllotmentExcel` calls a non-existent endpoint (404); no UI caller | none | frontend api | Remove the client or add the endpoint | N |
| SAT-DEF-022 | SAT-EXP-D14 | Low | Perf | Item Report / allotment export | `item-report` JSON is 65 MB; the default allotment xlsx takes ~33 s | — | — | Paginate / stream | N |

Export data-quality notes: DQ-1 allotment invoice date `34/04/2025`; DQ-2 0310827509 original CIF 0 with 30 BOEs.

## API / database / performance (Phases 1, 2, 8)

Source: `SAT_API_DATABASE_AUDIT.md` §4 (full repro steps, file:line, remediation) · evidence `~/lm_sat_evidence/api/`.
Write-path pytest: 77 tests, 70 passed, 7 failed (the failures are the findings), exit 1. Probes and perf runs: exit 0.

| ID | Source | Sev | Class | Module | Defect (one line) | Appr. |
|---|---|---|---|---|---|---|
| SAT-DEF-030 | SAT-API-D13 | High | CD (perf) | BOE list | N+1 query pattern: 431 queries for 10 rows; 3,578 queries and 9.5–11 s for 73 rows (~43–49 queries per row) | N |
| SAT-DEF-031 | SAT-API-D04 | **Medium** (agent: High) | CD | trade `/api/payments/` | Any standalone POST returns HTTP 500 (IntegrityError): the serializer has no `trade` field (`trade/api/serializers.py:54-60`), and the unhandled 500 returns an HTML page. **Controller downgrade:** no UI caller (frontend `payments/` calls go to the accounting API), and trade payments are created nested through the trade serializer. Still a public endpoint that always fails | N |
| SAT-DEF-032 | SAT-API-D10 | Medium | CD (resilience) | dashboard, item-pivot | HTTP 500 when Redis is unreachable (`django_redis`, no `IGNORE_EXCEPTIONS`); other endpoints degrade gracefully | N |
| SAT-DEF-033 | SAT-API-D15 | Medium | CD (perf) | licence detail | 143–290 queries, growing with the import-item count (id 1775: 290 queries, 0.85 s) | N |
| SAT-DEF-034 | SAT-API-D16 | Medium | CD (perf) | item-report | 65.3 MB unpaginated response, 229.8 MB peak memory, 4.4 s (same issue as SAT-DEF-022) | N |
| SAT-DEF-035 | SAT-API-D08 | Medium | CD (contract) | BOE, trade serializers | Input accepts ISO dates only, while output is `DD-MM-YYYY` (a round-trip of the API's own output fails); licence input accepts both | N |
| SAT-DEF-036 | SAT-API-D05 | Medium | CD / BRA | core masters delete | Deleting a company returns 204 and silently NULLs trade parties and the licence exporter (`SET_NULL`) | Y (DEC-30) |
| SAT-DEF-037 | SAT-API-D03 | **Low** (was Medium; Phase 9: environment state of a local copy, not a product defect) | Environment | local DB schema | Migration `license.0067` is unapplied on `lmanagement`, so the mapping-approval tables are missing (the owner applies it; SAT does not migrate) | N |
| SAT-DEF-038 | SAT-API-D11 | Medium | DQ | licence data | Licence 2101 has number `'0'` with NULL dates and exporter; licence 2107 has expiry year 0011; 46 licences with NULL expiry, 4 with NULL exporter, 24 rowless BOEs | Y (DEC-33) |
| SAT-DEF-039 | SAT-API-D14 | Low | CD (perf) | allotment list | ~1.7 queries per row (30 queries at page size 10, 179 at 100) | N |
| SAT-DEF-040 | SAT-API-D06 | Low | Design gap | licence update | No optimistic locking: concurrent PATCHes give last write wins, silently (no 500s, no deadlock) | N |
| SAT-DEF-041 | SAT-API-D07 | Low | CD | error envelope | Accounting voucher 400/404 shapes deviate from the rest of the API; unhandled 500s return HTML instead of JSON | N |
| SAT-DEF-042 | SAT-API-D09 | Low | CD | Celery license tasks | `finalize_license_ledger_package_job` raises an unhandled DoesNotExist for a missing job, while its sibling tasks are graceful | N |
| SAT-DEF-043 | SAT-API-D12 | Low | BRA | BOE rows | Row CIF stored at 3 dp vs 2 dp elsewhere | Y (DEC-31) |
| SAT-DEF-044 | SAT-API-D01 | Low | Dead code | frontend `licenseApi.ts`, `allotmentApi.ts` | 14 client functions target non-existent endpoints, with no callers (includes SAT-DEF-021) | N |
| SAT-DEF-045 | SAT-API-D02 | Low | Dead code | backend urls | 28 strict-orphan endpoints, plus duplicate legacy report routes | Y (DEC-32) |

No defect found for:
- Licence list N+1: 16 queries at every page size.
- 401 handling, pagination, ordering, duplicate prevention (400, never 500) and mid-operation rollback.
- FK integrity: 0 orphans over 371 FK columns.
- Negative or NULL CIF/qty values.
- Indexes on hot filter columns.
- Celery idempotence of the recovery and cleanup tasks.

## Security (Phase 7)

Source: `SAT_SECURITY_PERFORMANCE.md` (Security part: repro steps, file:line, remediation) · evidence `~/lm_sat_evidence/sec/`.
- Status counts: 40 IDs: 13 PASS, 14 PASS-EXC, 10 FAIL, 0 BLOCKED, 3 NOT-RUN (021 no per-entity scoping exists; 039 pip-audit not installed; 040 npm audit needs network).
- Role × endpoint matrix: 21 principals × 493 route-methods.
- Unauthenticated sweep: 463 × 401, 21 × 403, 1 × 400, 8 intentional public routes, 0 2xx, 0 5xx.
- Final pytest: 20 passed / 1 failed, exit 1. The failure is the harness's own over-strict "401 only" assertion: the 21 responses it flagged are correct 403 denials. Targeted reruns of B03, F01 and B04 all exit 0.

**Controller spot-checks:**
- D01: `accounts/permissions.py:146-155` grants TRADE_VIEWER every method, and `license/api/views/ledger.py:322-340` has no write-role check. Confirmed.
- D14: `git ls-files` lists `.env`, `backend/.env_dgft`, `frontend/.env` and `frontend/.env.production`. Contents not read, by policy.

| ID | Source | Sev | Class | Module | Defect (one line) | Appr. |
|---|---|---|---|---|---|---|
| SAT-DEF-050 | SAT-SEC-D02 | High | CD (authz) | licence-ledger package recover-orphan | Client-supplied `source_storage_key` is not validated against the orphan candidates. A TRADE_VIEWER attached an accounting voucher file to a trade and could then download it (`ledger.py:342-363`, `ledger_package_recovery.py:106-136`) | N |
| SAT-DEF-051 | SAT-SEC-D01 | High | CD (authz) | licence-ledger package upload | A read-only TRADE_VIEWER can replace supplier purchase-invoice documents: the permission class ignores the HTTP method | Y (DEC-35, which roles may upload) |
| SAT-DEF-052 | SAT-SEC-D03 | High | CD (stored XSS → privilege escalation) | licence document upload / media | Any type and size accepted; HTML/SVG served inline on the app origin, where it can read the localStorage JWT. A LICENSE_MANAGER can escalate to superuser (`license.py:1196-1245`, `media.py:194-197`) | N |
| SAT-DEF-053 | SAT-SEC-D14 | **Low** (owner attestation DEC-40 B, 2026-11-20: placeholders only; SAT did not read the files). Was Medium by default | Secrets hygiene | repo | `.env`, `backend/.env_dgft`, `frontend/.env` and `frontend/.env.production` are tracked in git. Phase 9: `settings.py:24-33` describes the DGFT file as holding session credentials, so Low is unlikely. **The owner must check the contents** (SAT did not read them). If they are live: rotate, untrack, purge the history | Y (DEC-40) |
| SAT-DEF-054 | SAT-SEC-D04 | Medium | CD (authz) | media | Files under `accounting/`, `tl/`, `exports/`, `entity_*` and `avatars/` can be downloaded by any authenticated user, including one with no roles (`media.py:41-108`) | N |
| SAT-DEF-055 | SAT-SEC-D05 | Medium | CD (injection) | XLSX/CSV exporters | User text starting with `=` (and `+ - @`) is written as a live formula (CSV/formula injection) | N |
| SAT-DEF-056 | SAT-SEC-D06 | Medium | CD (injection/SSRF) | allotment PDF | User text goes into reportlab markup unescaped: tags break the PDF, and `<img src>` makes the server read local files or URLs (`allotment_pdf.py:41-58`; the file is peer-modified, so this is reported only) | N |
| SAT-DEF-057 | SAT-SEC-D07 | Medium | CD (session) | auth | A password change or reset does not revoke issued tokens, and logout leaves the access token valid until it expires | N |
| SAT-DEF-058 | SAT-SEC-D08 | Medium | CD (brute force) | `/admin/login/` | No throttle (15 failed attempts, never blocked) | N |
| SAT-DEF-059 | SAT-SEC-D09 | Low | CD (robustness) | list endpoints / upload | A non-integer `id` filter returns 500 on 21 list endpoints (not SQL injection); a corrupt PNG upload returns 500. Controller Phase 4: `GET /api/allotments/?is_approved=all` → 500 (unhandled `ValidationError`; `~/lm_sat_evidence/int/pytest_allot_filter.log`) | N |
| SAT-DEF-060 | SAT-SEC-D10 | Low | Design risk | ItemPivot | 23 actions set `permission_classes=[]` and check roles inside the handler only | N |
| SAT-DEF-061 | SAT-SEC-D11 | Low | Info disclosure | several views | Exception text returned to the client (related to SAT-DEF-041) | N |
| SAT-DEF-062 | SAT-SEC-D12 | Low | Audit | ActivityLog | Failed logins are not logged; a superuser can edit or delete ActivityLog rows in admin | Y (DEC-39) |
| SAT-DEF-063 | SAT-SEC-D13 | Low | Session | export/download URLs | JWT accepted in the query string (it leaks into logs and history) | N |
| SAT-DEF-064 | SAT-SEC-D15 | Low | Config | settings | Production security checks run only when `DJANGO_ENVIRONMENT=production`; otherwise the repo's default `SECRET_KEY` is accepted | N |
| SAT-DEF-065 | SAT-SEC-D16 | Low | Authz | users | Users can rename their own username; any authenticated user can list all users and read the API schema | Y (DEC-38) |

No defect found for: SQL injection (ordering/filter payloads → 400 or ignored, never an SQL error), password hashes
absent from all serializers, CSRF (JWT-only API), and the 401 coverage described above.

## UI / E2E (Phases 4, 5, 7)

Source: `SAT_UI_UX_AUDIT.md` (repro, screenshots) · evidence `~/lm_sat_evidence/e2e/` (155 screenshots, jsonl).

- **Page audit:** 45 pages × 3 viewports = 135 loads. 0 page errors, 0 console errors, 0 failed API calls, 0 horizontal overflow, 0 clipped tables.
- **SAT workflows:** final run 24 passed / 2 failed. The trade failure was a spec bug; its rerun passed, exit 0. The open failure is UX-D01.
- **Regression suite:** 25 passed, 4 failed, 13 skipped, 16 did not run, exit 1. Classified test/harness: login throttle, 401s in a long serial run. `reports-menu.spec.ts:91` is unclassified.

| ID | Source | Sev | Class | Module | Defect (one line) | Appr. |
|---|---|---|---|---|---|---|
| SAT-DEF-080 | SAT-UX-D01 | Medium | CD (a11y) | Login | Login and throttle errors are not announced (no `role="alert"`/`aria-live`), at `pages/Login.tsx:163-167` | N |
| SAT-DEF-081 | SAT-UX-D02 | Medium | CD (a11y) | Trades, trade create, allotment allocate, item/planned report, licence create/edit, masters create | Unlabelled inputs (axe `label` serious: trade-create 13, trades 8, allocate 7, …); list search inputs unlabelled | N |
| SAT-DEF-082 | SAT-UX-D03 | Medium | CD (a11y) | App shell at 820/390 px | Unnamed link on every authenticated page at tablet/mobile widths | N |
| SAT-DEF-083 | SAT-UX-D04 | Medium | CD (a11y) | Dashboard (390), admin users and user create (21), allotment create/edit, ledger upload | Buttons without an accessible name | N |
| SAT-DEF-084 | SAT-UX-D05 | Low | CD (a11y) | Item names master (100 nodes), activity log, companies, others | Colour contrast below WCAG AA | N |
| SAT-DEF-085 | SAT-UX-D06 | Low | CD (a11y) | Licence edit/create, overview/detail, others | ARIA structure errors; scrollable regions not keyboard-focusable | N |
| SAT-DEF-086 | SAT-UX-D07 | Low | UX | Trades, licences, allotments, BOE, masters, dashboard | On a 500, the error appears only after retries; trades shows skeleton + "Updating…"; no retry control on 6/7 pages | N |
| SAT-DEF-087 | SAT-UX-D08 | Low | UX | Admin users | Search text is not kept in the URL on reload, unlike other lists | N |
| SAT-DEF-088 | SAT-UX-D09 | Low | UX / BRA | Reports | Purchase-profit report has no export control; planned export disabled when empty (probably by design) | Y (confirm) |
| SAT-DEF-089 | SAT-UX-D10 | **Closed: not a product defect** (Phase 9 §13) | Seed artifact | Allotments | `seed_browser_2509.py:308-325,361` creates the allotment `is_allotted=False`, with no items, linked to the seed BOE. The list (`allotment/api/views.py:290-293`, server default `is_allotted=True`; UI "Not BOE" view) correctly hides a BOE-consumed allotment; `is_allotted=all` returns it (1 row, `review/d10_triage.log`, exit 0). Residual Low note: the raw API default (`is_allotted=True`) differs from the UI default (`all`) | N |

Gap-closing runs by the controller (isolated reruns, `~/lm_sat_evidence/e2e/harness-gap1|gap2.log`, both exit 1; `int/pytest_x07.log`):

| ID | Source | Sev | Class | Module | Defect (one line) | Appr. |
|---|---|---|---|---|---|---|
| SAT-DEF-090 | X07 retry | Medium | CD | Licence-ledger package PDF (`POST license-ledger/download-package-pdf/`) | With exactly one licence (the valid input), it returns an **HTML 500** when a purchase trade has no main purchase invoice document: `PackageDocumentError("MISSING_MAIN_PURCHASE_INVOICE transaction 1")`, raised at `services/license_ledger_package.py:141` and not caught in `api/views/ledger.py:414-432`. The async package path reports the same condition as "blocked". Reproduced in the browser (harness) and in pytest (seed_browser_2509) | N |
| SAT-DEF-091 | Regression `reports-menu.spec.ts:73` | Low | SD (peer WIP or stale spec) | Reports menu | Fails **reproducibly in isolation** at the Item Report entry: the `is-active` class is not found. Correlates with the peer's uncommitted `navConfig.ts` change, which now passes `roles` through to the Reports items (Phase 9 §13). The test/harness classification is withdrawn | N |
| SAT-DEF-092 | Regression masters specs (isolated) | Low | SD | Auth/session in the real-backend UI | In isolation, `masters-seven-pages.real.spec.ts:188` and `masters-workspace.real.spec.ts:58` end on the **sign-in page** mid-run: the session is lost, and the API helper's non-OK response hides the status. Different tests fail than in the long run. Causes not separated: login throttle at sign-in vs token refresh/rotation (`ROTATE_REFRESH`/blacklist). Not proven to be harness-only. `masters-detail.real` passed in isolation | N |

Harness defect (test infra, not product): the default `PYTHON_BIN` of `scripts/test/run_data_bearing_browser_e2e.sh` (`$ROOT/.venv`)
has no Django, so the run fails unless `PYTHON_BIN=backend/.venv/bin/python` is set. Login rate-limiting also breaks long serial
real-backend runs.

## Peer addendum defects (`license-manager-2c`), merged as reported

Reported by the peer session. The SAT controller has not reproduced them; Phase 9 review status is in
`SAT_INDEPENDENT_REVIEW.md` or the peer's own review. Headline: independent SQL = engine on 26,818 items / 2,185
licences (0 diffs); API live fields = engine on 6,679 items. Invoice-qty rule scenarios Q01–Q28 on the test DB (`SAT_INVOICE_BOE_QUANTITY_AUDIT.md` §7): the scenario table
marks expected-vs-actual FAILs (e.g. Q02, Q03, Q05, Q07, Q09, Q10c, Q13, Q15b). The probe pytest ran 31 tests, exit 0
(`pytest_run2.log`/`.exit`); the tests record the current behaviour. Peer note on SAT-DEF-001: 153 stored rows equal "live − AR", so they are stale rows from an earlier writer.
DEC-01 still stands.

| ID | Sev (peer) | Class | Defect | Evidence / ref |
|---|---|---|---|---|
| SAT-DEF-120 | Medium | CD | Missing invoice qty silently stored as 0, with no flag | Q02, Q03 |
| SAT-DEF-121 | Low–Med | CD | Negative `qty_kg` accepted (no validator) | `trade/models.py:536` |
| SAT-DEF-122 | Medium | CD | SALE update path skips the qty availability guard | Q24 |
| SAT-DEF-123 | High (latent: 0 trades locally) | CD | CIF-only formal allocation (`allocated_qty=0`) double counts qty | Q13, DEC-22 |
| SAT-DEF-124 | Medium (latent) | CD | Hidden BOE tagged to a SALE zeroes the invoice qty | Q18, DEC-23 |
| SAT-DEF-125 | Medium | CD | `billed_no_boe_qty` predicate differs from the engine (trade-level, ignores formal allocation and paired transfers); feeds Customs Ledger and Item Pivot `balance_qty` | Q09, Q25, Q26 |
| SAT-DEF-126 | Low | CD | `qty_comparison` is not item-level and gives the full BOE qty to each invoice | Q27, Q28 |
| SAT-DEF-127 | High (data) | DQ | 43 BOE debit rows with qty 0 and CIF > 0 (5,056,539.16), across 12 BOEs | DEC-26 |
| SAT-DEF-128 | High (data) | DQ | 2 BOE rows with CIF FC 0 and qty 0 but CIF INR 1,881,509.08 (0311010085 item 26456) | §5 |
| SAT-DEF-129 | Medium (data) | DQ | 35 items with BOE qty > licensed qty (+3,613,764.872); 6 items with licensed qty 0 but BOE debits | §5 |
| SAT-DEF-130 | Low (latent) | CD | No unit on trade line or BOE row; 34 unit case variants; PDFs hard-code "Kg" | DEC-25 |
| SAT-DEF-131 | Low | CD | Ledger invoice status ignores qty; `get_billed_no_boe_qty` swallows exceptions → 0.0 | `license.py:451-452` |
| SAT-DEF-132 | Low | CD | A blank invoice number lets duplicate SALE records both consume | Q15b |
| SAT-DEF-140 | Medium | CD | `is_null` has several thresholds (< 100 / < 200 / < 500 across `calculate_balance.py:238`, `signals.py:357`, `views/license.py:723`, `validation_service.py:322`, dashboard), giving 189 wrong flags | DEC-52 |
| SAT-DEF-141 | Medium | CD (extends RC3) | Stored `debited_value` includes hidden BOEs and is a float: +4,412,937.86 on 30 items' API `debited_value` | Covered by D-D |
| SAT-DEF-142 | Low | CD | Import item API returns qty/CIF as float (`api/serializers/license.py:304-358`); no difference at current magnitudes | API contract change → approval |

Planning balance audit (`SAT_PLANNING_BALANCE_AUDIT.md` §7; evidence in the peer's run log; 21 characterisation tests
+ 114 pinned planning tests passed, exit 0). Results: planning = engine for BOE CIF on 81 licences; 71/71 preview
ceilings ≤ max(bal, 0) (over-allocation prevented); D02 confirmed on the planning side.

| ID | Sev (peer) | Class | Defect | Ref |
|---|---|---|---|---|
| SAT-DEF-100 | Medium → **BRA** (controller) | Deliberate design | Snapshot plan remaining CIF not capped by the live balance: 42 licences, +633,992.65. The code comment says it is intentional, so it is an owner question (DEC-11), not a defect | E-01 |
| SAT-DEF-101 | Medium (latent) | CD | Planning usage ignores billed-without-BOE CIF/qty | E-02 |
| SAT-DEF-102 | Medium | CD | `operational_reconciliation.actual_balance_cif` ignores the hidden-BOE opening rule: 11 licences, +4,412,937.86 vs the engine (`views/license.py:450-458`) | E-03, DEC-12 |
| SAT-DEF-103 | Medium | CD / BRA | Plan "used" drops BOE-converted PLAN allotments (`plan_enforcement.py:25-28`): 9,257.14 | E-04, DEC-13 |
| SAT-DEF-104 | Low (latent) | CD | No partial-allocation netting in planning usage | E-05, DEC-14 |
| SAT-DEF-105 | Low | CD | `remaining_cif` not quantized | E-06 |
| SAT-DEF-106 | Low | CD | Float arithmetic in the Plan tab totals | E-07 |

Peer independent review (`SAT_CIF_RECON_INDEPENDENT_REVIEW.md`): 0 figure disagreements (19 items × 17 fields,
3/3 licences). No tests were run (no code changed); its scripts are listed in that report.

| ID | Sev | Class | Defect | Ref |
|---|---|---|---|---|
| SAT-DEF-150 | Medium | DQ (double count) | An unlinked allotment stays outstanding although a later, visible, unlinked BOE exists for the same item, company and qty, so the licence is debited twice. 8 items, 420,407.75 CIF / 215,552 kg. 7 of them are SAT-DEF-002 scope; **1 has `is_boe=False`, so the SAT-DEF-002 measure misses it**: 0910065986 allotment 10178 ↔ BOE 4849356 | Fix = UI M2M link; heuristic usable as a reconciliation warning |
| SAT-DEF-151 | Low | CD | `%`-condition item `available_value` / `balance_cif_fc` returned unquantized at 3 dp (5211006995/19712: 291.133) | Related to SAT-DEF-142 |

Update to **SAT-DEF-005** (shared-ceiling item cap): now measured. The item cap exceeds the licence balance by up to
**+459,135.24** (item 36928; peer review §4, challenge 9).

## Owner decisions 2026-11-20 (SAT closure)

Owner options recorded in `SAT_USER_DECISION_REGISTER.md` § "Owner decisions — SAT decision closure": SAT-DEF-100 → DEC-11 B
· SAT-DEF-102 B · SAT-DEF-120…132 A · SAT-DEF-150 A · DEC-50 D · SAT-DEF-140 D · RC3/RC13 C. **No defect closed.** All
of them stay OPEN until they are implemented and verified with test evidence.

All owner questions were answered on 2026-11-20 (question log in `SAT_USER_DECISION_REGISTER.md`). Severity changes from the decisions: SAT-DEF-053 → **Low** (DEC-40 B, owner attests to placeholders only); SAT-DEF-100 → decision DEC-11 B. Every defect stays **OPEN** until it is implemented and verified.
