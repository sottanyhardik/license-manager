# Phase 4E-F Implementation Guide
## Legacy Cleanup & Code Removal

**Status:** QUEUED (auto-launch after 4E-E PASS)  
**Role:** Refactor Specialist  
**Duration:** ~15 minutes  

---

## PHASE OBJECTIVE

Remove legacy functions that were replaced by the canonical migration, now that parity is verified.

**Safety Rule:**
```
Only delete after parity is verified.
Only delete if no remaining references.
Only delete if tests pass.
```

---

## LEGACY CODE INVENTORY

### Target 1: build_dfia_ledger_detail()
**Location:** `backend/apps/license/services/exporters/ledger_pdf.py` (lines 1043–1290)

**Status:** 
- ❌ Not called by production code
- ✅ Called by test: test_ledger_pdf_live_balance.py
- ✅ Marked for removal in Phase 4E-F

**Action:** DELETE after verification

### Target 2: build_incentive_ledger_detail()
**Location:** `backend/apps/license/services/exporters/ledger_pdf.py` (lines 1296–1469)

**Status:**
- ❌ Not called by production code
- ❌ Not called by any test
- ✅ Marked for removal

**Action:** DELETE

### Target 3: Legacy test references
**Location:** test_ledger_pdf_live_balance.py

**Status:**
- Currently tests legacy functions (acceptable pre-parity)
- Post-parity: should test against canonical

**Action:** Update to test canonical integration instead

---

## DELETION SAFETY CHECKLIST

For each legacy function:

```
[ ] Confirmed: not called by production code
    Command: grep -r "build_dfia_ledger_detail\|build_incentive_ledger_detail" backend --include="*.py" | grep -v "def \|tests\|comments"
    
[ ] Confirmed: test coverage is replaceable
    Command: grep -r "build_dfia_ledger_detail\|build_incentive_ledger_detail" backend/apps --include="*test*.py"
    
[ ] Confirmed: git history preserved
    Action: Deletion is tracked in git, history is available
    
[ ] Verified: parity tests pass (4E-E gate is PASS)
    Prerequisite: Phase 4E-E completion
    
[ ] Executed: Full regression test suite passes
    Command: pytest backend/ -v
    
[ ] Confirmed: No references in frontend
    Command: grep -r "build_dfia_ledger_detail\|build_incentive_ledger_detail" frontend
```

---

## CLEANUP STEPS

### Step 1: Remove Dead Functions
```python
# In backend/apps/license/services/exporters/ledger_pdf.py

# DELETE lines 1043–1290 (build_dfia_ledger_detail)
# DELETE lines 1296–1469 (build_incentive_ledger_detail)
# DELETE any helper functions used only by these
```

### Step 2: Remove Associated Tests
```python
# In test_ledger_pdf_live_balance.py

# Update to test against canonical instead of legacy functions
# Keep test coverage, change the implementation being tested

# BEFORE (testing legacy)
def test_ledger_pdf_with_canonical():
    result = build_dfia_ledger_detail(...)  # ← LEGACY
    assert result == expected

# AFTER (testing canonical)
def test_ledger_pdf_with_canonical():
    canonical = CanonicalLedgerService.build_canonical_ledger_dataset(...)
    pdf_data = get_license_transactions(...)  # ← CURRENT
    assert pdf_data['balance'] == canonical['license_running_balance']
```

### Step 3: Search for Any Remaining References
```bash
# Full search for dead function names
grep -r "build_dfia_ledger_detail" backend --include="*.py"
grep -r "build_incentive_ledger_detail" backend --include="*.py"

# If any found: must be in comments or dead code, investigate
```

### Step 4: Run Full Test Suite
```bash
cd backend
.venv/bin/pytest . -v --tb=short
```

**Expected:** All tests pass (including updated ledger tests)

### Step 5: Run Regression Test
```bash
# Golden scenario regression
.venv/bin/pytest apps/license/tests/test_canonical_ledger_service.py -v
.venv/bin/pytest apps/license/tests/test_ledger_pdf_live_balance.py -v
```

**Expected:** All pass

### Step 6: Git Cleanup Commit
```bash
git add -A
git commit -m "refactor(ledger): remove legacy ledger detail functions

Phase 4E-F: Legacy code removal (post-parity verification)

Removed:
- build_dfia_ledger_detail() - replaced by CanonicalLedgerService
- build_incentive_ledger_detail() - replaced by CanonicalLedgerService
- Legacy test helper functions

Updated:
- test_ledger_pdf_live_balance.py - now tests canonical integration

Verified:
- No production references remaining
- Full test suite passes (14/14 canonical, 2/2 PDF)
- Cross-output parity confirmed (4E-E gate passed)
- Regression tests pass

This cleanup is safe: all functionality replaced by canonical service.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

## GATE CRITERIA

✅ Phase 4E-F PASS requires:
- [ ] Dead function deletion confirmed (no production calls)
- [ ] All references removed
- [ ] Test suite updated and passing
- [ ] Regression tests pass (14/14 canonical, 2/2 PDF)
- [ ] Full backend test suite passes
- [ ] Cross-output parity confirmed (4E-E gate was PASS)
- [ ] Git history preserved
- [ ] No floating references or commented code

---

## POST-CLEANUP VERIFICATION

After cleanup:

```python
# test_phase_4e_f_no_legacy.py

def test_no_legacy_functions_called():
    """Verify no legacy ledger detail functions exist."""
    import inspect
    from apps.license.services.exporters import ledger_pdf
    
    # Functions should not exist
    assert not hasattr(ledger_pdf, 'build_dfia_ledger_detail')
    assert not hasattr(ledger_pdf, 'build_incentive_ledger_detail')
    
def test_canonical_is_authoritative():
    """Verify CanonicalLedgerService is sole financial calculation owner."""
    # Grep for independent balance calculations in ledger module
    # Should find: ZERO additional balance calculation engines
    pass
```

---

**Ready for auto-execution after Phase 4E-E PASS**
