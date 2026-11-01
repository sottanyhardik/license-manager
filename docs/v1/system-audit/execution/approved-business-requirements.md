# Approved business requirements

Only requirements the product owner has approved are listed here. Pending items are in `user-questions-register.md`. A requirement is moved here only after its decision is recorded in `user-decisions.md`.

Status values follow `user-questions-register.md`.

## BR-001 — Company access (from UD-001, owner D1)

- **Requirement:** No company-only data-isolation policy. Authenticated users with an authorised role may access eligible records across companies. Role-based permissions, authentication and object-level security apply to every read, write, export, download and background job.
- **Affected modules:** Licence, allotment, BOE, trade, ledger, reports, exports, downloads, invoices, user management.
- **Acceptance criteria:**
  1. A user whose role is authorised for a record type can read records from any company through list, detail and export.
  2. A user whose role is not authorised receives a denial from the API, not only a hidden control in the UI.
  3. Object-level checks (for example, a user cannot modify another user's record where the role does not permit it) still hold.
  4. No new company-only filter is added to any queryset.
- **Required tests:** For each approved role, same-company and cross-company fixtures for read, write, export and download; direct API calls, not UI-only checks.
- **Known evidence:** `backend/apps/accounts/permissions.py` role classes; `backend/tests/test_authorization_permissions.py` (documented legitimate roles read multiple companies); DEC-05 in `unresolved-decisions.md`.
- **Known gap:** Object-level checks for USER_MANAGER on superusers (ISS-011) are a separate defect under Q-002. They are not settled by BR-001.
- **Status:** CONFIRMED (owner).

## BR-003 — Null DFIA definition (from UD-003, answer to Q-001)

- **Requirement:** A licence is Null DFIA when its `balance_cif` is less than 200. The same threshold applies in every place the term is used.
- **Currency:** US dollars, confirmed in UD-004 (Q-011).
- **Affected modules:** Licence list filter (`views/license.py`, `apply_advanced_filters`), stored flag (`signals.py:316`, `services/validation_service.py:322`, `management/commands/sync_licenses.py:193`), maintenance script (`core/scripts/calculate_balance.py:210`, currently 100), DFIA report split (`services/report_service.py:196–255`, currently 1,000 and 20,000), dashboard alert (`Dashboard.tsx` around 415–425).
- **Acceptance criteria:**
  1. For every licence, the list filter, stored flag, dashboard count, report table and export agree on Null DFIA at the threshold.
  2. A licence with `balance_cif` exactly 200 is not Null DFIA; 199.99 is.
  3. The stored flag is recalculated only under DEC-03's approved reconciliation rule. Historical flags are not changed silently.
- **Required tests:** Boundary tests at 199.99, 200 and 200.01 for the list, stored flag, dashboard, report and export.
- **Dependency:** `balance_cif` is the financial engine's output. Its open defects (ISS-019 to ISS-021, Q-016) can change which licences fall below 200.
- **Status:** ANSWERED and currency CONFIRMED (owner). Consumer changes pending, and the report and dashboard follow-ups (Q-017, Q-018) are open.

## BR-002 — Available licence balance (from UD-002, owner D2)

- **Requirement:** Available balance = allotted entitlement − unbilled BOE utilisation − billed utilisation. When a BOE is billed, its utilisation moves from the unbilled bucket to the billed bucket, and is not deducted a second time.
- **Worked example (approved):** Allotted ₹500,000. Unbilled BOE ₹100,000 → available ₹400,000. Bill the same BOE for ₹100,000 → available remains ₹400,000.
- **Affected modules:** Licence balance calculator, balance snapshot, licence list, dashboard, licence ledger (Customs and Financial), allocation, item pivot report, DFIA reports.
- **Acceptance criteria:**
  1. The worked example yields ₹400,000 before and after billing.
  2. Billing a BOE never changes the available balance.
  3. Each displayed balance identifies which engine it comes from (pending Q-005).
- **Open points (not yet approved):** Hidden (OTH / previous-owner) BOEs (Q-004); relationship to the Customs and Financial engines (Q-005).
- **Required tests:** Unit test for the worked example against the balance calculator and the snapshot. Regression test for each open point after it is decided.
- **Status:** CONFIRMED (owner). Code conformance NOT VERIFIED (Agent 06 in progress). Scope OPEN (Q-005).
