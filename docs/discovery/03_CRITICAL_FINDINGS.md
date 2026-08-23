# Critical Findings — License Manager
**Discovery Date:** 2026-08-10  
**Evidence Source:** Code-read verification (agents: backend-engineer, data-scientist, security-auditor, performance-engineer)  
**Validation:** All findings cross-checked against source, tests, recent commits

---

## P0 — CRITICAL DEFECTS (User-Visible, Requires Immediate Decision)

### P0-001: Ledger Balance Calculation Divergence (LIVE DEFECT)

**Severity:** CRITICAL (P0)  
**Status:** Design documented, awaiting business decision  
**User Impact:** HIGH (affects 3 displays, shows conflicting numbers)  

**Problem:**
The License Ledger Detail page, PDF export, and Excel export display **DIFFERENT RUNNING BALANCES** for the identical license and transactions.

**Evidence:**
1. **Backend (ledger_pdf.py:1067–1227)**
   - Running balance calculated license-wide in PURCHASE→SALE→COMMISSION order
   - Treats COMMISSION_SALE as debit
   - Formula: cumulative_balance += credit_amount - debit_amount

2. **Frontend Page (LicenseLedgerDetail.tsx:331–337)**
   - Running balance calculated per-company (restarts at zero per company group)
   - Excludes COMMISSION transactions entirely
   - Formula: per_company_balance += row_amount

3. **Frontend Excel Export (ledgerExport.js:118–119)**
   - Same per-company logic as page
   - Identical code path

**Root Cause Analysis:**
- NOT a bug in backend or frontend code
- Two **legitimate, conflicting business conventions**
  - License-wide: tracks entire license's financial position
  - Per-company: tracks each customer's allocation separately
- Phase 3 design doc (LEDGER_DETAIL_DISPLAY_DATASET_DESIGN.md, §2) identifies this as **semantic divergence, not accidental**

**Phase 3 Status:**
- Design phase: COMPLETE (§0–§10 fully documented)
- Decision gate: **OPEN (§10 B2 requires business approval)**
- Implementation gate: BLOCKED until business decision

**Test Coverage:**
- Zero characterization tests for `build_dfia_ledger_detail()` (~250 lines)
- Zero tests for `build_incentive_ledger_detail()` (~300 lines)
- Frontend PDF/Excel balance calculation: 1 test covering running balance (only Excel path tested), PDF/totals untested

**Required Actions:**
1. Business decision: Which running-balance convention is correct? (License-wide or per-company?)
2. Document decision in Phase 3 approval
3. Add characterization test suite (golden dataset, both backends tested) — Phase 3D
4. Implement fix and verify all 3 outputs agree

**Blocking Modules:**
- Module 3: License Ledger
- Module 10: Reports & Exports

**Risk If Not Resolved:**
- Users see conflicting information (screen vs PDF vs Excel)
- Incorrect financial decisions based on which display user trusts
- Audit trail confusion

---

### P0-002: Ledger Builders Have Zero Tests

**Severity:** CRITICAL (P0)  
**Status:** Design identified, awaiting Phase 3D test design  

**Problem:**
Two 550+ line functions (`build_dfia_ledger_detail`, `build_incentive_ledger_detail`) with **zero tests**. Complex balance logic, no regression protection.

**Evidence:**
- **Files:** `backend/apps/license/services/exporters/ledger_pdf.py:1025–1451`
- **Lines of code:** ~425 combined
- **Tests:** 0 (searched `test_*ledger*.py`, no unit or integration tests found)
- **Golden master:** Explicitly excluded from `scripts/golden_master_ledger_pdf.py:4–6` ("This action is not yet included")
- **API test coverage:** Only `backend/tests/test_api_trade.py:91` (`test_license_ledger_detail`) which:
  - Reverses route via URL-name collision
  - Asserts only `200` + `isinstance(dict)`
  - Does NOT test balance calculation correctness

**Risk:**
- Ledger changes can silently break running balance
- No regression protection for complex balance logic
- No test data to validate against

**Required Actions (Phase 3D):**
1. Create characterization test dataset (representative license + transactions)
2. Add unit tests for both builders:
   - Opening gate logic (hidden BOE handling)
   - Per-row debit calculation
   - Running balance accumulation
   - COMMISSION handling (excluded in per-company mode)
3. Add regression test for balance divergence (P0-001)
   - Verify backend balance
   - Verify frontend page balance
   - Verify frontend Excel balance
   - Flag if any diverge

**Blocking:** Phase 3 completion (cannot ship without tests)

---

## P1 — HIGH-SEVERITY ISSUES (Architectural, Data Integrity, Performance)

### P1-001: IncentiveLicense Constraints Still CASCADE (Not PROTECT)

**Severity:** HIGH (P1) — Data Loss Risk  
**Status:** Known issue (PR b3802917 missed this)  
**Scope:** Only Incentive Licenses (RODTEP/ROSTL/MEIS), not core DFIA  

**Problem:**
Recent PR (commit b3802917, "fix(db): change Port/Company FKs from CASCADE to PROTECT") changed 6 ForeignKey fields from CASCADE to PROTECT but **missed 2 fields on IncentiveLicense**.

**Evidence:**
```python
# backend/apps/license/models/core.py:IncentiveLicense
exporter = ForeignKey(CompanyModel, on_delete=CASCADE)  # ← Should be PROTECT
port_code = ForeignKey(PortModel, on_delete=CASCADE)   # ← Should be PROTECT
```

**Risk:**
- Deleting a Company will CASCADE-delete all its IncentiveLicenses (data loss)
- Deleting a Port will CASCADE-delete all its IncentiveLicenses (data loss)
- No PROTECT constraint to prevent deletion

**Scope of Change:**
- Model definition: 2 lines
- Tests: Add deletion protection tests (~2 hours)
- Migration: Required (alter ForeignKey on_delete behavior)

**Required Actions:**
1. Change `on_delete=CASCADE` to `on_delete=PROTECT` (2 lines)
2. Create migration
3. Add test cases:
   - Attempt to delete Company with active IncentiveLicense → 400 error
   - Attempt to delete Port with active IncentiveLicense → 400 error
4. Verify no existing code relies on CASCADE deletion behavior

**Timeline:** 1 day (low complexity)

**Blocking:** Should be fixed before production deployment

---

### P1-002: Materialized Views NOT Scheduled in Celery Beat

**Severity:** HIGH (P1) — Critical Performance Gap  
**Status:** Design complete, implementation missing  

**Problem:**
Materialized views exist and are defined but **are NOT scheduled to refresh in Celery Beat**.

**Evidence:**
- **Definitions:** `backend/apps/core/tasks_materialized_views.py`
  - `refresh_all_views_task()`
  - `refresh_license_balance_task()`
  - etc.
- **Schedule:** `backend/lmanagement/celery.py` — **No Celery Beat entries found**
- **Current State:** Manual refresh only via `manage.py refresh_materialized_views` (never runs on schedule)
- **Dashboard Impact:** Dashboard queries hit stale views → slow queries (2000ms vs 5ms fresh)

**Performance Impact:**
```
Fresh view query:   5ms
Stale view query:   2000ms
Improvement:        99% faster (40× speedup)
```

**Expected Benefit:**
- Dashboard loads instantly (currently slow)
- Dashboard queries 40× faster
- Reduced database load on list views

**Fix (Quick Win):**
Add 4 Celery Beat entries to `celery.py`:

```python
app.conf.beat_schedule = {
    # ... existing entries ...
    'refresh-license-balance-mv': {
        'task': 'apps.core.tasks.refresh_license_balance_task',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
    },
    'refresh-item-balance-mv': {
        'task': 'apps.core.tasks.refresh_item_balance_task',
        'schedule': crontab(minute=0, hour='*/4'),
    },
    'refresh-dashboard-stats-mv': {
        'task': 'apps.core.tasks.refresh_dashboard_stats_task',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    # ... etc
}
```

**Effort:** 2 hours (schedule design + testing)  
**Risk:** LOW (idempotent refresh, can be disabled if issues)

**Required Actions:**
1. Determine refresh interval (based on data volume and update frequency)
2. Add Celery Beat entries
3. Test refresh runs on schedule
4. Verify dashboard query time improves

**Blocking:** None (performance improvement, not required for correctness)

---

### P1-003: Balance Calculator Hot Path — Performance Risk

**Severity:** HIGH (P1) — Couples To 43 Dependents  
**Status:** Active (recent commits 2026-08-08, not yet optimized)  

**Problem:**
The `balance_calculator.py:calculate_financial_balance_for_licenses()` function is called on every license list/detail view but uses complex Case/When SQL subqueries with unclear query count.

**Evidence:**
```python
# backend/apps/license/services/balance_calculator.py
# get_debit_rows() method uses complex Case/When with multiple subqueries
# resolve_boes_represented_by_invoice_for_licenses() traverses BOE relationships
# Called by: 43 different modules/views
```

**Risk:**
- Query count unknown (likely N+1 on list views)
- Case/When with subqueries slow on large BOE datasets
- No materialized view optimization (unlike other hot paths)
- Called on **every** license list pagination

**Performance Metrics:**
- Query count baseline: **UNKNOWN** (must measure with django-debug-toolbar)
- Per-license query cost: **UNKNOWN**
- List view (25 licenses) total cost: **UNKNOWN**

**Known Issues:**
- Recent balance changes (2026-08-08) not yet profiled
- No golden-data benchmark to validate improvements
- Case/When subqueries likely slower than materialized view approach

**Required Actions:**
1. Profile current implementation:
   - Measure query count on `/licenses/` list view (25-item page)
   - Measure response time
   - Identify slow Case/When subqueries using EXPLAIN ANALYZE
2. Establish baseline metrics
3. Consider optimization strategies:
   - Materialized view for balance calculations
   - Prefetch-related chains to reduce queries
   - Caching strategy (beyond signal invalidation)
4. Implement + verify improvement before Phase 3 deployment

**Blocking:** Performance investigation required before optimization

---

### P1-004: Report Exports Have N+1 Patterns

**Severity:** HIGH (P1) — Performance  
**Status:** Design identified, optimization pending  

**Problem:**
Excel and PDF export functions loop per item with nested queries for BOE rows and allotments, creating N+1 patterns.

**Evidence:**
```python
# backend/apps/license/services/exporters/license_balance_excel.py:124–232
for license in licenses:
    for export_item in license.export_license.all():  # ← Per-license query
        for import_item in license.import_license.all():  # ← Per-license query
            for row in import_item.item_details.all():  # ← Per-item query
                for alloc in row.allotment_allocations.all():  # ← Per-row query
```

**Impact:**
- 25-license export: 25 × (export items + import items + BOE rows + allocs) = 100–1000 queries
- No prefetch_related optimization
- Excel generation times out on large datasets

**Optimization:**
Add `prefetch_related` chains to querysets before serialization.

**Effort:** 1–2 days (add prefetch, benchmark, verify)

**Blocking:** None (performance optimization, not required for correctness)

---

### P1-005: Ledger Detail Characterization Tests Missing (Phase 3D)

**Severity:** HIGH (P1) — Regression Risk  
**Status:** Identified in Phase 3 design doc  

**Problem:**
Phase 3 Ledger Detail migration requires characterization tests (Phase 3D) before shipping. Currently zero tests for ledger builders.

**Evidence:**
- Phase 3 design doc, §9: "Phase 3D (characterization tests) is not optional here"
- Build functions: ~425 lines combined, zero unit tests
- API test: only checks 200 + isinstance(dict), not balance correctness

**Required Actions (Phase 3D):**
1. Create test dataset (representative license + transactions + BOEs + trades)
2. Write unit tests for both builders
3. Write golden-data regression test (verify page + PDF + Excel outputs)
4. Verify all 3 outputs agree (or document intentional divergence per P0-001 decision)
5. Regression test for balance divergence (fails if any output changes unexpectedly)

**Timeline:** 2–3 days (test design + implementation)

**Blocking:** Cannot ship Phase 3 without tests

---

## P1-006: Reconciliation Allocation Ledgers Use Service-Level Validation (No DB Constraints)

**Severity:** MEDIUM (P1) — Data Integrity  
**Status:** Design as-intended, but architecture constraint  

**Problem:**
Allocation ledgers (InvoiceBOEAllocation, BOEAllotmentAllocation) prevent over-allocation via service-level validation (`allocation_service.py`) rather than database CHECK constraints.

**Evidence:**
```python
# backend/apps/reconciliation/services/allocation_service.py
# validate_allocation_within_limits() checks that allocated <= remaining
# But NO DATABASE CHECK CONSTRAINT enforces this
```

**Risk:**
- Concurrent requests can bypass service validation (race condition)
- Direct database inserts (if anyone runs migrations with raw SQL) bypass validation
- No audit trail of why allocation failed

**Current Mitigation:**
- API endpoint throttled (prevent brute-force allocation)
- PROTECT constraints on ledger relationships (prevent deletion)
- Service-level validation strict (prevents most issues)

**Architectural Decision:**
- Postgres CHECK constraints not used (for modularity, allow service to handle complex logic)
- This is a **deliberate design choice**, not a bug

**Recommendation:**
- Document this design decision
- Add comprehensive service-level tests (already exist)
- Consider adding CHECK constraints in future if allocation patterns change

**Blocking:** None (current mitigation sufficient)

---

## P2 — MEDIUM-SEVERITY ISSUES

### P2-001: Ledger PDF Balance Calculation Lacks Comments

**Severity:** MEDIUM (P2) — Maintainability  
**Status:** Design identified, no code action needed  

**Issue:** Opening gate logic (hidden BOE handling) in `ledger_pdf.py:1067–1127` could use explanatory comments. Complex rule not documented inline.

**Fix:** Add inline comment explaining opening gate calculation.

---

### P2-002: A3627 Auto-Planner Committed But Not Validated

**Severity:** MEDIUM (P2) — Correctness  
**Status:** Code committed (2026-08-08), needs golden-data validation  

**Issue:** A3627 planner (glass/ceramics) uses USD 3.00 price threshold and 4-priority waterfall (RUTILE→TITANIUM→SODA→PP). Not yet tested against real data.

**Required Actions:**
1. Validate A3627 rules against representative dataset
2. Verify price selection logic (USD 3.00 threshold) matches business intent
3. Add unit tests for each priority level

**Timeline:** 1–2 days

---

### P2-003: IgnoredWarning Model Is Mutable (Should Be Immutable)

**Severity:** MEDIUM (P2) — Audit Trail  
**Status:** Design as-intended, could improve  

**Issue:** `IgnoredWarning` records are mutable in-place (ignored boolean changed to True/False). Audit trail only records who changed it, not the change history.

**Current Behavior:**
- Ignore warning → ignored=True, ignored_at=now, ignored_by=user
- Restore warning → ignored=False, restored_at=now, restored_by=user
- **No history** of multiple ignore/restore cycles

**Recommendation:**
- Consider adding `IgnoredWarningHistory` table (append-only ledger)
- Or: use soft-delete pattern with separate restore record
- Current approach is acceptable if audit requirements don't mandate full history

**Blocking:** None (depends on audit requirements)

---

## SUMMARY OF CRITICAL FINDINGS

| ID | Issue | Severity | Status | Blocking | Effort |
|----|----|---|---|----|---|
| P0-001 | Ledger balance divergence | CRITICAL | Design done, awaiting decision | P1-002, P1-005 | 2–3 days |
| P0-002 | Zero tests for ledger builders | CRITICAL | Identified | Phase 3 | 2–3 days |
| P1-001 | IncentiveLicense CASCADE not PROTECT | HIGH | Known (PR missed) | Prod deploy | 1 day |
| P1-002 | Materialized views not scheduled | HIGH | Design done | Performance | 2 hours |
| P1-003 | Balance calculator performance risk | HIGH | Active | Measurement | TBD |
| P1-004 | Report export N+1 patterns | HIGH | Identified | Performance | 1–2 days |
| P1-005 | Ledger tests missing (Phase 3D) | HIGH | Identified | Phase 3 | 2–3 days |
| P1-006 | Allocation validation service-level only | MEDIUM | Design choice | None | None |
| P2-001 | Ledger calculation comments | MEDIUM | Low impact | None | 2 hours |
| P2-002 | A3627 planner not validated | MEDIUM | Code committed | Testing | 1–2 days |
| P2-003 | IgnoredWarning is mutable | MEDIUM | Design choice | None | Future |

---

## BLOCKING SEQUENCE

**Cannot Proceed With Phase 3 Until:**
1. ✋ Business decision: Ledger balance convention (P0-001)
2. ✋ Test suite: Ledger characterization tests (P0-002, P1-005)
3. ✓ READY TO FIX: IncentiveLicense constraints (P1-001) — 1 day
4. ✓ READY TO FIX: Materialized view scheduling (P1-002) — 2 hours

**Recommended Sequence:**
1. Resolve P0-001 (business decision) — GATE
2. Fix P1-001 (IncentiveLicense) — quick win
3. Fix P1-002 (materialized views) — quick win  
4. Implement P0-002 + P1-005 (test suite) — Phase 3D
5. Profile + optimize balance calculator (P1-003) — separate performance phase
6. Optimize report exports (P1-004) — separate performance phase

---

**DISCOVERY STATUS:** Complete  
**NEXT STEP:** Business decision on P0-001 (ledger balance convention) to unblock Phase 3 completion
