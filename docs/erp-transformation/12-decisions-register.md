# 12 — Decisions Register

Two lists: **engineering decisions taken** (autonomous, reversible, recorded here) and
**open owner decisions** (business/irreversible — must be decided by the product owner;
work that depends on them is blocked, unrelated work continues). Newest first within each list.
Durable one-liners are mirrored in `.claude/memory/decisions.md`.

## A. Engineering decisions taken

| ID | Date | Decision | Why | Reversible? |
|---|---|---|---|---|
| ED-007 | 2026-11-15 | Created local-only Postgres role/DB `master_data` (CI-identical throwaway creds) so the MDS gate can run locally | `docs/claude/INSTALLATION.md` claims `bootstrap-macos.sh` creates it, but the script states it "never touches databases" → doc/script mismatch (tracked R-ENV-01) | Yes (`DROP DATABASE master_data; DROP ROLE master_data;` locally) |
| ED-006 | 2026-11-15 | `quality-gate.sh` runs mds-client with `DJANGO_SETTINGS_MODULE` unset | `gate_mds` exports `mds.settings`, which leaked into the mds-client run (`ModuleNotFoundError: mds`); CI runs it in a fresh job, so local ≠ CI | Yes |
| ED-005 | 2026-11-15 | `frontend/route-browser-test.js` linted as a Node/CommonJS script (added to the existing `jest.config.js` node block) instead of ignored/deleted | It is a standalone Playwright script, not SPA code; deletion needs usage verification (dup at repo root — see 06) | Yes |
| ED-004 | 2026-11-15 | `AllocationStrategyEditor.test.tsx` expected row now includes `cif_restriction_percentage: null` | Commit `7eed2a9e` intentionally added the field; backend `serializers/incentive.py:436` accepts it nullable. Assertion became *stricter*, not weaker | Yes |
| ED-003 | 2026-11-15 | Added synthetic (fictional IEC/port/BOE/amount) ICEGATE CSV fixtures `backend/tests/fixtures/ledgers/{L1,L2,l3}.csv` + `.gitignore` exception | Test file says fixtures are "committed so the suite is hermetic", but the global `*.csv` ignore kept them out → 5 tests failed on every clean checkout (CI too). Fixtures reproduce BOM-before-`Regn.No.`, NBSP in numeric cells, mid-block page-continuation headers, 9-digit licence/IEC padding | Yes |
| ED-002 | 2026-11-15 | Fixed `test_parse_pdf_hs_autocreate.py`: removed never-existing `SAMPLE_PDF_DATA` import, granted `LICENSE_MANAGER` group, sent a real `SimpleUploadedFile` | The import error aborted collection of the whole app-level suite (2,702 tests never ran in CI). Assertions unchanged; all 5 tests pass | Yes |
| ED-001 | 2026-11-15 | **Green baseline before modernization.** No refactor/consolidation work starts until the CI-equivalent gate is green | A red suite cannot detect regressions in balance/CIF code; Phase 10 of the mandate requires a baseline | — |
| ED-000 | 2026-11-15 | Prior autonomous-run documents (`docs/CURRENT_PHASE.md`, `MODERNIZATION_PROGRESS.md`, `docs/decisions/LEDGER_APPROVED_SEMANTICS.md`, Module "FROZEN" claims) are treated as **leads, not evidence or approval** | `LEDGER_APPROVED_SEMANTICS.md` sign-off table is `[Name] / [Approved]` placeholders; status docs describe workflows from 2026-08-10 that are not verifiable now; some claims ("zero duplicates") contradict 09 §6 | — |
| ED-A01 | 2026-11-15 | Target = **modular monolith** with layered app boundaries (core/masters < licensing < allotment, bill_of_entry, trade < reconciliation); no new services | No scaling/operational requirement found that justifies microservices (02 §12). MDS fate is an owner decision (OD-05) | — |

## B. Open owner decisions (ask one at a time; see 00 for the recommended order)

| ID | Decision | Blocks | Recommendation (summary) |
|---|---|---|---|
| OD-01 | **Negative balances**: both balance engines floor at 0 (`balance_calculator.py:1345,1403,1431,…,2100`, 13 sites) vs the stated rule "preserve negative balances and flag over-utilisation" | Canonical balance service, ledger UI, over-utilisation flag | Keep the floored value as today's display figure, add an unfloored `raw_available` + `is_over_utilised` field alongside (additive API, no number changes), then decide the display switch separately |
| OD-02 | **Which engine is "Available CIF"**: customs engine (`calculate_balance`, no billed term) vs financial engine (`calculate_financial_balance`, matches the 5-term rule) | Consolidation of DUP-* balance items (05) | Financial engine as canonical `available_cif`; customs figure exposed explicitly as `customs_available_cif` |
| OD-03 | **Ledger running-balance convention** (licence-wide vs per-company; COMMISSION rows) — `docs/decisions/LEDGER_BALANCE_CONVENTION_DECISION.md` | Ledger screen/PDF/Excel parity | Re-confirm the "Option C hybrid" with a real human sign-off (current approval is placeholder) |
| OD-04 | Tenancy / company scoping (no object-level permissions; `accounts/0004_remove_user_company`) | Any new module with per-customer data | Decide single-tenant install vs `Organization` scoping before ERP expansion |
| OD-05 | Master-data strategy: MDS service vs `core/sync` vs fold into monolith (17 masters defined twice) | Master-data module work | Fold into monolith `masters` module unless MDS has an external consumer |
| OD-06 | Tracked env files / real customs PDFs in git (SEC-01, SEC-02) | Security hardening | Rotate secrets, untrack, then decide on history purge (destructive — explicit approval) |
| OD-07 | API versioning (`/api/v1/`) + moving JWT out of `localStorage` (contract change) | API/auth modernization | Additive `/api/v1/` alias first; cookie refresh token behind a flag |
| OD-08 | Removal of verified dead code / archiving 258 root `.md` reports and ad-hoc scripts (06 §A–C) | Dead-code phase | Approve §A list in one batch; archive (not delete) §B |
| OD-09 | New dependencies (e.g. form/validation libs, `drf-spectacular`, `pip-audit`) | Form engine, API docs, CI security | Decide per library when the phase reaches it |

| ~~OD-10~~ ✅ **DECIDED 2026-11-15: Engine value**; trade total kept as labelled `trade_running_balance` — implemented `ea029f1d`. Follow-ups: show it in balance Excel/PDF summaries (audit M1); other screens still label the trade total as a balance — `LicensesTable.tsx:592`, `canonicalLedgerAdapter.js:123`, `serializers/ledger.py:236-241` aliases, ItemReport (audit L1, part of OD-03) | **Financial Ledger "Current Balance"**: financial-engine value vs trade-only running total (DUP-01, `license_balance_ledger_builder.py:666-672`, from `7fd7104d`) | Ledger screen/PDF/Excel; P2 | Show the engine value (it matches the stated 5-term rule); keep the trade running total as its own labelled column |
| OD-11 | Invoice PDF total + round-off: print stored `total_amount`; one rounding mode (DUP-11) | Invoice documents | Print stored total, ROUND_HALF_UP everywhere |
| OD-12 | Outstanding allotment definition: AR vs AT; partial-allocation netting (DUP-04, `calculate_balance.py:55` 'ARO' never matches) | Allotment module | Decide AR semantics first |
| OD-13 | Item available qty: live Decimal vs stored float-truncated; exclude hidden BOEs (DUP-05/21) | Allotment validation | Live Decimal, hidden excluded |
| OD-14 | Commission trades in balance — symmetric or excluded (DUP-08) | P2 | — |
| OD-15 | Trade line rounding (₹ whole vs 2dp), Null-DFIA threshold ($100 vs $500), profit definition, tolerances (DUP-10/12/19/20) | Trades, reports | — |
| OD-16 | `on_delete=PROTECT` for financial FKs (03 §8) | P7 | PROTECT |
| OD-17 | Sanitised production snapshot for trade/allocation testing (dev DB has 0 trades) | P1/P3 verification | Provide snapshot |
| OD-18 | Activity-log retention window/archive | P7 | — |
| OD-19 | Retire the 3 unused, incorrect materialized views; status of `ebrc_*`/`eScrap_*` tables | P7 | Retire MVs |
| OD-20 | BOE natural key (number+date vs +port); credit rows with NULL BOE (87% of RowDetails) business key | P7 constraints | — |
| OD-21 | **Item-pivot cell merging**: since `ff021e74`/`29cfed00`/`0a155e89` (Oct 23) one pivot cell joins descriptions/HSNs with commas and rolls UNPLANNED import rows of the same category into the planned cell's sources and totals (e.g. total_qty 250 = planned 200 + unplanned 50). Contradicts `test_item_pivot_planned_import_item.py` ("only the planned import row", "do not string-concatenate") | Green app-level suite; pivot quantities | Decide whether unplanned rows belong in the planned cell's totals; if not, fix merge; if yes, update the 2 tests |

Additional owner decisions surfaced by 03/04/05/07 are appended to section B by those reports' "Conflicts" sections and consolidated in `00-executive-assessment.md`.
