# IMMEDIATE ACTION PROTOCOL — When Agents Report Issues

**Purpose:** Exact steps to follow the moment any blocking issue is identified

---

## UPON AGENT COMPLETION (First Agent Reports)

**Immediately upon receiving completion notification:**

1. **Read Agent Output Completely**
   - Don't skim, read entire report
   - Note all findings, not just failures
   - Understand root causes

2. **Extract Issues to List**
   ```
   CRITICAL:
   - Issue 1: [description] [pages affected]
   - Issue 2: [description]
   
   HIGH:
   - Issue 3
   - Issue 4
   
   MEDIUM/LOW:
   - Issue 5
   ```

3. **Prioritize Fixes**
   - CRITICAL: Fix immediately
   - HIGH: Fix before next agent completion
   - MEDIUM: Can defer if time-constrained
   - LOW: Post-release OK

4. **Launch Fix Agents**
   - For CRITICAL: Launch immediately
   - For HIGH: Queue to launch after CRITICAL
   - For MEDIUM/LOW: Document for later

---

## WHEN CRITICAL ISSUE FOUND

**Example: Tests Failing in LicenseLedger**

### Step 1: Understand the Issue (5 min)
```
What tests are failing?
├─ LicenseLedger.test.tsx — 5 tests
├─ LicenseLedgerDetail.test.tsx — 3 tests
└─ Root cause: DOM changed with ActiveFilters

What's the blocker?
├─ Tests must pass before production
└─ Without fix: Cannot ship
```

### Step 2: Determine Fix Owner (1 min)
```
Who can fix this fastest?
├─ Frontend engineer (who made the change) — BEST
├─ QA engineer (can update tests)
└─ Orchestrator (can coordinate)

Decision: Launch frontend engineer with fix directive
```

### Step 3: Launch Fix Agent (2 min)
```
Agent directive:
- Problem: Tests failing because DOM changed
- Root cause: ActiveFilters changes layout
- Solution: Update test fixtures to match new DOM
- Constraints: Must not change application logic
- Acceptance: All tests passing
```

### Step 4: Verify Fix (10-15 min)
```
Once agent completes:
1. npm run test  # Must show all passing
2. npm run lint  # Must show 0 errors
3. npm run build # Must succeed
4. If passes: Mark CRITICAL as RESOLVED
5. If fails: Launch fix again with new directive
```

### Step 5: Continue to Next Issue (1 min)
```
Move to next blocking issue
If no more blocking:
  → Re-evaluate all gates
  → Proceed to HIGH priority fixes
```

---

## WHEN HIGH PRIORITY ISSUE FOUND

**Example: Pages Missing ActiveFilters**

### Quick Decision:
```
Is agent still working on these?
├─ YES → Wait for agent completion
└─ NO → Launch new agent to implement on remaining pages

Pages missing ActiveFilters:
├─ SionE1, SionE5, SionE126, SionE132 (4 pages)
├─ LicenseOverviewPage
├─ ReconciliationPanel
├─ ReconciliationIssues
└─ And 5-10 others

If frontend agent is done:
→ Launch new frontend engineer agent to complete remaining

If frontend agent still working:
→ Wait (agent should deliver all at once)
```

---

## WHEN MEDIUM PRIORITY ISSUE FOUND

**Example: Design System Violations**

### Decision:
```
Can we defer to post-release?
├─ YES → Document and move on
└─ NO → Fix before production

Typical MEDIUM issues:
├─ Hardcoded color in one component → FIX (takes 1 min)
├─ Missing ARIA label → FIX (takes 2 min)
├─ Unused import → DEFER (post-release cleanup)
└─ Layout shift on hover → FIX (takes 5 min)

Strategy: Fix issues < 5 min immediately
         Defer issues > 5 min to post-release
```

---

## IF MULTIPLE CRITICAL ISSUES

**Sequence:**
1. Fix issue #1
2. While fix agent works on #1 → Launch parallel agents for issues #2, #3
3. Verify all fixes together
4. Re-evaluate gates

**Example Timeline:**
```
15:50 - Issue #1 identified (tests failing)
        Launch fix agent for #1

15:55 - Issue #2 identified (routes broken)
        Launch fix agent for #2 (parallel with #1)

16:00 - Issue #3 identified (a11y violations)
        Launch fix agent for #3 (parallel)

16:20 - All 3 fix agents complete
        Verify all fixes together
        Re-evaluate gates
```

---

## RE-EVALUATION PROTOCOL (After Each Fix)

**After every fix agent completes:**

1. **Verify Fix Worked**
   ```bash
   npm run lint  # 0 errors?
   npm run build # Success?
   npm run test  # All passing?
   # Test in browser
   ```

2. **Check for Regressions**
   ```
   Did fixing #1 break anything else?
   ├─ Run affected tests again
   ├─ Test related routes
   └─ Check related components
   ```

3. **Update Gates**
   ```
   Which gates changed?
   ├─ Gate #10 now PASS (was FAIL)
   └─ Did any other gates break?
   ```

4. **Continue or Next Issue?**
   ```
   ├─ More CRITICAL issues? → Fix next
   ├─ No CRITICAL left? → Fix HIGH issues
   └─ All CRITICAL/HIGH done? → Final verification
   ```

---

## FINAL GATE RE-EVALUATION

**When all fix agents complete:**

1. **Run Full Quality Check**
   ```bash
   npm run lint    # 0 errors
   npm run build   # Success
   npm run test    # 100% passing
   npm run typecheck # 0 errors
   ```

2. **Test Sample Routes**
   ```
   For each:
   - /licenses (master)
   - /license-ledger (detail)
   - /reports/item-report (complex)
   - /admin/users (admin)
   - /reconciliation (complex)
   
   Verify:
   ├─ Loads without error
   ├─ Filters work
   ├─ ActiveFilters displays
   ├─ No console errors
   └─ Responsive on mobile
   ```

3. **Evaluate All 30 Gates**
   ```
   Gate evaluation report shows:
   ├─ All 30 gates? PASS
   ├─ 29/30? Which is failing? Fix it.
   └─ < 29/30? More work needed
   ```

---

## PRODUCTION SIGN-OFF

**When all 30 gates = PASS:**

1. **Create PRODUCTION_READY.md**
   - Date/time of sign-off
   - List all 30 gates = PASS
   - Verification checklist
   - Stakeholder sign-off

2. **Prepare Commit**
   ```bash
   git add .
   git commit -m "chore: UI rebrand Phase 2b complete - all 30 gates passing"
   ```

3. **Create PR**
   ```bash
   gh pr create --title "UI Rebrand: ActiveFilters + Design System (Phase 2b)" \
     --body "All 30 production gates passing. Ready for production deployment."
   ```

4. **Notify Stakeholders**
   - Engineering lead
   - Product manager
   - DevOps team
   - Ready for merge and deploy

---

## ABORT SCENARIO

**If CRITICAL issue cannot be fixed in reasonable time:**

1. **Assess Impact**
   ```
   Can we:
   ├─ Revert the change? (Undo recent commit)
   ├─ Work around the issue? (Alternative approach)
   └─ Fix in post-release? (If not blocking production)
   ```

2. **If Must Revert**
   ```bash
   git revert [commit-hash]
   npm run build  # Verify builds
   # Return to previous state
   ```

3. **Document Lesson**
   ```
   Why did this issue occur?
   How can we prevent it next time?
   What changed in process?
   ```

---

## EMERGENCY PROTOCOL

**If build suddenly fails:**

1. Immediately check what changed
2. Identify breaking change
3. Contact responsible agent/engineer
4. Revert recent changes if needed
5. Fix root cause
6. Re-test

**If tests suddenly fail (mass failure):**

1. Check if it's test environment issue
2. Check if dependency issue
3. Identify pattern (all tests? one component?)
4. Revert to last known good state if critical
5. Debug methodically

---

## KEY PRINCIPLES

1. **Do NOT pause for status reports** — Continue working
2. **Do NOT skip quality checks** — Always verify fixes
3. **Do NOT ignore regressions** — Test after every change
4. **Do NOT defer CRITICAL issues** — Fix immediately
5. **Do NOT compromise on 30 gates** — All must pass
6. **Do NOT stop until 100%** — Keep going until production ready

---

**READINESS:** Protocol prepared and ready for immediate execution  
**CONFIDENCE:** All scenarios covered  
**STATUS:** Awaiting agent completions to activate this protocol
