# Known Issues — UI Rebrand Phase 2b

**Updated:** 2026-09-25 14:45 UTC  
**Status:** Tracking during scale-out and QA phases

---

## ISSUE TRACKER

### Issue #1: Test Failures in LicenseLedgerDetail.test.tsx

**Severity:** MEDIUM  
**Status:** IDENTIFIED  
**Date Found:** 2026-09-25 14:45 UTC

**Description:**
Test file `src/pages/LicenseLedgerDetail.test.tsx` has 9 failing assertions:
- `expect(await screen.findByText("License Ledger")).toBeInTheDocument()` — timeout
- Likely caused by substantial layout changes in LicenseLedgerDetail.tsx

**Root Cause:**
LicenseLedgerDetail page was restructured with new components/layout. Test fixture expectations no longer match DOM structure.

**Impact:**
- Tests don't pass: `npm run test` shows 5 failed | 72 passed
- Build still passes (not blocking)
- Functionality not necessarily broken

**Resolution:**
1. Update test fixture to match new DOM structure
2. Or update LicenseLedgerDetail to match test expectations
3. Priority: Fix before production merge

**Assigned To:** QA Test Engineer (post-scale-out)

**Acceptance Criteria:**
- `npm run test` shows 77 passed, 0 failed
- All LicenseLedgerDetail tests pass
- No test regressions in other files

---

### Issue #2: ESLint Warnings in ActiveFilters.tsx

**Severity:** LOW  
**Status:** IDENTIFIED  
**Date Found:** 2026-09-25 14:00 UTC

**Description:**
Two unused variable warnings in new ActiveFilters.tsx:
```
frontend/src/components/ActiveFilters.tsx
   1:17  warning  'useMemo' is defined but never used
  63:3   warning  'position' is assigned but never used
```

**Root Cause:**
- `useMemo` imported but not used in initial implementation
- `position` prop parameter not used in component logic

**Impact:**
- Lint warnings (acceptable per code quality policy)
- No functional impact

**Resolution:**
1. Remove unused `useMemo` import, or
2. Remove unused `position` parameter, or
3. Implement usage of these props if future feature planned

**Assigned To:** Frontend Engineer (during scale-out)

**Priority:** LOW (post-scale-out cleanup)

---

### Issue #3: Test Warnings in Other Files

**Severity:** LOW  
**Status:** IDENTIFIED  
**Date Found:** 2026-09-25 14:45 UTC

**Description:**
Additional unused variable warnings in test files:
- `e2e/responsive.spec.ts` — 2 warnings ('devices', 'inputs')
- `src/tests/responsive.test.ts` — 2 warnings ('beforeAll', 'key')

**Root Cause:**
Test helper code has unused variables/parameters.

**Impact:**
- Lint warnings only
- Tests run successfully
- No functional impact

**Resolution:**
- Clean up test files (post-scale-out, not blocking)

**Priority:** LOW

---

## ISSUE SEVERITY SCALE

| Severity | Definition | Resolution Time |
|----------|-----------|-----------------|
| CRITICAL | Blocks build or breaks functionality | Must fix before merge (same turn) |
| HIGH | Breaks feature or causes regression | Must fix before production (within 1-2 hours) |
| MEDIUM | Breaks some workflows, needs fixing | Should fix before production (optional for hotfix) |
| LOW | Nice to have, not blocking | Fix in next cleanup sprint |

---

## RESOLUTION TRACKING

### Ready to Fix Immediately
1. ✅ Issue #1 (Test failures) — Can be fixed by QA or Frontend Engineer
2. ⏳ Issue #2 (ESLint warnings) — Can be fixed during scale-out
3. ⏳ Issue #3 (Test warnings) — Can be fixed during cleanup

### Blocking Criteria
- **None currently identified**

### Nice-to-Have Fixes
- Remove unused imports/variables (Issues #2, #3)

---

## QA SIGN-OFF

When all issues are resolved, mark as:
- [  ] Issue #1: FIXED & TESTED
- [  ] Issue #2: FIXED
- [  ] Issue #3: FIXED (optional)

**Production Gate:** Can proceed with Issue #3 unresolved (LOW priority)

---

**Tracking by:** Orchestrator  
**Next Review:** After Phase 2b scale-out completes
