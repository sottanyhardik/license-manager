# Licence Management — Known Issues, Business Decisions and Deferred Work

Companion to `licence-management-audit.md`. Each item cites its finding ID there. Verification labels: **[V]** checked by me; **[A]** reported by an explorer agent, not independently re-read.

No code was changed in this stage for the items below, except where noted under *Fixed in the listing work*.

---

## 1. Business decisions required (block implementation)

These change what the system calculates or enforces. They are not engineering choices and will not be made silently.

| ID | Decision | Options | Affects |
|---|---|---|---|
| D-1 | Which balance figure is authoritative for each output? | (a) Canonical financial everywhere, including bulk XLSX and ledger; (b) customs formula for XLSX; (c) keep as is, labelled | F-01: list, detail, PDF, bulk XLSX, Financial Ledger |
| D-2 | Null-balance threshold | ₹200 (live filter, live reports) vs ₹500 (persisted flag, validation); unify or keep both | F-03 |
| D-3 | Expiry rule for allocation and BOE | Date at check time (recommended) vs stored flag | F-02 |
| D-4 | Over-utilisation: should a BOE debit larger than the licence's remaining CIF be rejected for every CIF mode? | Enforce for all modes vs keep `INDIVIDUAL_ITEM`-only | F-04 |
| D-5 | Zero floor | Keep flooring at zero (hides over-utilisation) vs expose a negative balance with an over-utilised status | F-04 |
| D-6 | Is `/masters/licenses` retained? | Redirect to `/licenses` vs keep as labelled legacy | F-07 |
| D-7 | Default for absent `flags__is_null` on the API | Apply `False` (as the UI does) vs keep no filter (current) | BE-10, API callers |
| D-8 | Default list ordering change | Confirm expiry-first default is intended (already applied) and needs release-note wording | BE-08 |

---

## 2. Defects (confirmed or reported, not yet fixed)

| ID | Sev | Status | Summary | Evidence |
|---|---|---|---|---|
| F-01 | High | Open, needs D-1 | Four balance figures in circulation; bulk XLSX and Financial Ledger disagree with the list | `balance_calculator.py:1664-1666` [V]; `license_balance_excel.py:1604` [V]; `license_ledger_filters.py:224-228` [A] |
| F-02 | Med–High | Open, needs repro + D-3 | Expiry checked from stored flag at allocation; BOE and reconciliation reportedly do not check expiry | `validation_service.py:43` [V]; `signals.py:302-305` [A] |
| F-04a | High | Open, needs D-4 | BOE debit balance guard runs only for `INDIVIDUAL_ITEM` licences | `bill_of_entry/serializers.py:84-92` [V] |
| F-04b | High (if confirmed) | Open | No downstream enforcement of the BOE over-debit check was found for other modes | Not verified; needs a test |
| F-04c | Low | Dead code | `allotment/services/allocation_service.allocate_item` has no callers and no lock; the live path locks | `allocation_service.py:152` [V]; `views_actions.py:1098,1192` [V] |
| F-04d | Med | Open, needs D-5 | Balance floored at zero hides over-utilisation | `balance_calculator.py:1666` [V] |
| F-05 | Med | Open | Allocation-row uniqueness lacks DB constraints; relies on app checks | [A] |
| F-06 | Low–Med | Open | Stored-cache filter remains in an unused FilterSet and possibly other callers | `filtersets.py:186` [A] |
| F-07 | Med | Open, needs D-6 | Two licence list implementations; legacy table reachable at `/masters/licenses` | `AppRoutes.tsx:297` [A] |
| F-08 | Low | Open | Legacy `/licenses/:id/balance` redirect still linked | `MasterForm.tsx:1101`, `ReconciliationIssues.tsx:61` [A] |
| F-09 | Low | Open | `balance-excel-unused` endpoint still routed | [A] |
| F-10 | Low | Open | Docstrings describe the wrong balance source | `views/license.py:302`; `serializers/license.py:826-835` [A] |
| F-11 | Low | Open | Redundant index on `license_number`; no constraint on `LicenseExportItemModel` | `models/core.py:158-164, 865` [A] |
| F-12 | Med | Open | Bulk balance XLSX has no tests | grep [A] |
| F-13 | Low | Open | Duplicate helpers and components; unused `BalanceTab.tsx` | [A] |
| F-14 | Med | Open, unmeasured | Report exports compute balance per row | `active_licenses_report.py:113,197`; `expiring_licenses_report.py:105,189` [A] |
| F-15 | Low | Open | Code index references deleted test files | `.claude/index/dependents.tsv` [A] |
| BE-03 | High (perf) | Open | Live-balance filters pull every candidate id into Python; 16–27 queries, 34–51 ms at 200 rows | [V] measured |
| BE-10 | Med | Open, needs D-7 | Absent `flags__is_null` applies no filter; absent `is_expired` applies `False` | `license.py:797` [V] |

---

## 3. Fixed in the listing work (for traceability)

These were fixed during the licence listing repair and are verified by the tests named in `licence-listing.md` §16.

- URL request loop on `/licenses` (1,876 requests in 5 s before, 1 after) [V].
- Scheme-code and notification-number filters sent IDs instead of codes [V].
- Purchase-status labels and per-ID 404s for unknown IDs [V].
- Malformed numeric and date parameters returned 500 (now 400) [V, backend suite].
- `ordering=balance_cif` raised `FieldError` [V, backend test].
- N+1 on list export lines and transfer lookups (25 → 17 queries at page size 25) [V].

---

## 4. Technical limitations and deferred work

- **Stages 3–9 not started.** Architecture, critical repairs beyond the listing, create/edit/detail review, PDF and Excel layout and reconciliation inspection, full licence E2E, and the system-design, UI/UX and test-report documents.
- **Not reviewed in detail:** `LicenseLedger.tsx`, `LicenseLedgerDetail.tsx`, `LicensePlanningWorkspace.tsx`, `LicenseBalanceModal.tsx`, `MasterForm.tsx` licence branch, `LicenseOverviewPage.tsx`, the download-request and package-readiness pages.
- **Permissions:** route guards and endpoint permission classes listed; object-level and export permissions not re-verified this stage.
- **Concurrency:** no concurrency test exists for allocation or BOE debit. Locks are present on the UI allocation path only [V].
- **Performance:** measured for the list endpoint only (200 rows). Export, PDF and detail paths unmeasured.
- **Working tree:** `balance_calculator.py`, `views/license.py` and `models/core.py` have uncommitted dashboard-workstream edits. Any financial fix must coordinate with that work to avoid overwriting it.
- **Existing unrelated failures:** the backend agent reported 8 failures in `apps/license/tests` (item pivot, E1/E132 export ordering, plan utilisation, one overview summary) that also fail on HEAD. Not re-run in this stage; they should be reported separately, not fixed here.
- **Test collection error:** `test_parse_pdf_hs_autocreate.py` has a pre-existing `ImportError` at collection.

---

## 5. Recommended next steps (in priority order)

1. Decide D-1 (authoritative balance) before any financial code change. It determines the scope of F-01.
2. Write reproduction tests for F-02 (expiry with no save) and F-04b (BOE over-debit in non-individual modes). Confirm or refute before deciding fixes.
3. Coordinate with the dashboard workstream on `balance_calculator.py` and `views/license.py`, then proceed with the canonical service work.
4. Add bulk XLSX tests (F-12) so any change to F-01 is measured.
5. Stage 5 onward (create, edit, detail, PDF/Excel inspection, responsive and accessibility review) after the financial decisions are made.
