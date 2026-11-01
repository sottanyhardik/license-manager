# Unresolved business decisions

These decisions block specific implementation work. The audit does not choose any of them. Work that does not depend on a decision continues.

## DEC-01 — Canonical Null DFIA threshold

Status: ANSWERED 2026-11-01 (UD-003, UD-004): Null DFIA is `balance_cif` < US$200 everywhere. Consumer changes are not yet made; they need approval under the audit scope rule. Follow-ups: Q-017 (DFIA report split), Q-018 (dashboard label).

Original evidence below is kept for the record.

Evidence (verified by reading code and running the API):
- Live list filter: `backend/apps/license/views/license.py`, `apply_advanced_filters`, `is_null` branch. `is_null=True` means live financial balance < 200; `is_null=False` means balance >= 200. Pinned by `apps/license/tests/test_license_advanced_filters_live_balance.py` and `apps/license/tests/test_license_default_active_filter.py::test_live_list_null_filter_boundaries_around_threshold_200`.
- Stored flag: `backend/apps/license/signals.py` (around line 316) computes `is_null = balance < 500`, commented "Null DFIA = balance < $500". `backend/apps/license/services/validation_service.py` (around line 322) uses 500.
- Added in the session of 2026-11-01: `backend/apps/core/scripts/calculate_balance.py:210` sets `is_null` below ₹100; `backend/apps/license/services/report_service.py:196–255` splits DFIA reports into "All DFIA" and "NULL DFIA" at ₹1,000 (active) and ₹20,000 (expired); `frontend/src/pages/Dashboard.tsx` (around lines 415–425) labels the stored count "Missing DGFT — Require data entry". The term therefore has five balance cut-offs and one data-completeness meaning.
- Question asked to the owner: `execution/user-questions-register.md` Q-001 (pending).
- The viewset docstring (`views/license.py` around line 219) says 200.

Options:
- A. Adopt 200 everywhere (matches the live list; changes the stored-flag computation and signal).
- B. Adopt 500 everywhere (matches the stored flag; changes the live list filter and every API consumer of `is_null`).
- C. Keep two named concepts with distinct labels (e.g. "Low balance" for list filtering, "Null DFIA" for the stored flag). Requires a documented rule for each consumer.

Impact: list counts, dashboard counts, export contents and any report that depends on `is_null` change under A or B.

## DEC-02 — Source of truth for dashboard classification

Status: OPEN. Owner: business owner with the lead architect.

Evidence:
- Dashboard `_get_license_stats` (`backend/apps/license/views/dashboard.py` around lines 103–150) counts `active`, `expired`, `null_dfia` from the STORED `LicenseFlags` fields.
- The licence list classifies from LIVE financial balance.
- In the retained test database, every licence had `flags.is_null = True` while live balances were 0 or 1000. The dashboard active count therefore evaluates to 0 while the list shows 12 active licences (verified by ORM query and by the API).
- Dashboard "expiring soon" uses a separate balance threshold (code comment: "$100 threshold"), resolved against live balance.

Options:
- A. Live balance everywhere (consistent with the list; more expensive per request; can use the existing batched calculator).
- B. Maintained stored flag everywhere (requires reliable recalculation on every balance-affecting change; currently not reliable as the database evidence shows).

## DEC-03 — Historical flag reconciliation

Status: OPEN. Owner: business owner with data governance.

Evidence: stored `LicenseFlags.is_null` values disagree with live balances for existing licences in the retained test database. The same kind of disagreement is expected in any database where signals did not run (for example bulk loads or seeded data).

Requirement before any change: a read-only reconciliation report, an approved correction rule, an audit record for each changed flag, and a rollback plan. No flag may be rebuilt silently.

## DEC-04 — Server-side default filter for the licence list

Status: OPEN. Owner: product owner with the API consumers.

Evidence: the licence viewset metadata declares `default_filters = {"is_expired": "False", "flags__is_null": "False"}`. The server applies `is_expired` defaults (the key matches) but never applies the null default, because the code looks up `default_filters.get('is_null')`. The UI sends the defaults itself, so the UI is correct and an unfiltered API call returns every licence. Existing tests `apps/license/tests/test_license_validity_api.py` and `apps/license/tests/test_license_list_balance_consistency.py` depend on the unfiltered list.

Options:
- A. Keep the unfiltered API contract; document it; fix only the dead key lookup for clarity. (Lowest risk; current tests keep passing.)
- B. Apply the declared default server-side. (Changes the response of an unfiltered API call; requires updating the two tests and checking every API consumer first.)

## DEC-05 — Company-level access (resolved for the audit)

Status: RESOLVED by the business owner. There is no company-level data-isolation policy. Authenticated users with the appropriate role may access eligible records across companies. Authentication, role-based permissions and object-level security still apply. Recorded here so future audits do not re-open it.
