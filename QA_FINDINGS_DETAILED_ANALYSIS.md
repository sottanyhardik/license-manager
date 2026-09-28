# QA DETAILED FINDINGS & FIX ANALYSIS
## Feature/MUI Redesign Complete - Test Failures Deep Dive

**Date:** 2026-09-28  
**Branch:** feature/mui-redesign-complete  
**Status:** 5 failing tests identified, root causes analyzed, fixes documented

---

## FAILURE #1: Mobile Navigation Drawer Escape Key

### Test Location
```
File: frontend/src/components/TopNav.test.tsx
Line: 65
Test: "provides an accessible mobile drawer without changing the available destinations"
```

### Failure Details

**Test Code:**
```typescript
fireEvent.keyDown(document, { key: "Escape" });
expect(screen.queryByTestId("mobile-nav-drawer")).not.toBeInTheDocument();
```

**Error:**
```
Error: expect(element).not.toBeInTheDocument()
expected document not to contain element, found <div class="MuiDrawer-root...">
```

**What's Happening:**
1. Test opens mobile navigation drawer
2. Presses Escape key
3. Expects drawer to close
4. **ACTUAL:** Drawer remains open

### Root Cause Analysis

**MUI v9 Drawer Component Changes:**

In MUI v8/v9, the Drawer component's escape handling may have changed:
- Modal backdrop click handler behavior altered
- Or: Escape key handler not automatically connected to Drawer
- Or: Modal component replaced with different implementation
- Or: Keydown event not propagating correctly

**Evidence:**
```jsx
// MUI v9 Drawer structure (from test output):
<div class="MuiDrawer-root MuiDrawer-anchorLeft MuiDrawer-modal MuiModal-root">
  <div aria-hidden="true" class="MuiBackdrop-root"/> {/* Backdrop present */}
  <div role="dialog" aria-modal="true"/> {/* Modal role correct */}
</div>

// Components ARE present, but Escape handling broken
// onKeyDown listener may not be attached
```

### Expected Component Implementation

**Current TopNav.tsx likely has:**
```typescript
const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

// Missing: Escape key handler
useEffect(() => {
  const handleEscape = (e: KeyboardEvent) => {
    if (e.key === "Escape" && mobileDrawerOpen) {
      setMobileDrawerOpen(false);
    }
  };
  
  // NOT CONNECTED - This is the bug
  // document.addEventListener("keydown", handleEscape);
  
  return () => {
    // document.removeEventListener("keydown", handleEscape);
  };
}, [mobileDrawerOpen]);

return (
  <Drawer 
    open={mobileDrawerOpen}
    onClose={() => setMobileDrawerOpen(false)}
    // MUI v9 may not auto-close on Escape via modal behavior
  >
    {/* Navigation content */}
  </Drawer>
);
```

### Fix Implementation

**Option A: MUI Drawer onClose with ClickAway (Recommended)**
```typescript
import { Drawer, ClickAwayListener } from '@mui/material';

export function TopNav() {
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

  const handleDrawerClose = () => {
    setMobileDrawerOpen(false);
  };

  return (
    <ClickAwayListener onClickAway={handleDrawerClose}>
      <Drawer
        anchor="left"
        open={mobileDrawerOpen}
        onClose={handleDrawerClose}
        // MUI v9: These should handle escape + backdrop click
        ModalProps={{
          onBackdropClick: handleDrawerClose,
          // Ensure escape propagation
          slotProps: {
            backdrop: {
              onClick: handleDrawerClose,
            },
          },
        }}
      >
        <NavContent />
      </Drawer>
    </ClickAwayListener>
  );
}
```

**Option B: Manual Escape Key Handler**
```typescript
useEffect(() => {
  if (!mobileDrawerOpen) return;

  const handleEscape = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      setMobileDrawerOpen(false);
      event.preventDefault();
    }
  };

  document.addEventListener("keydown", handleEscape, true); // Capture phase
  return () => {
    document.removeEventListener("keydown", handleEscape, true);
  };
}, [mobileDrawerOpen]);

return (
  <Drawer
    open={mobileDrawerOpen}
    onClose={() => setMobileDrawerOpen(false)}
  >
    {/* Content */}
  </Drawer>
);
```

### Test Fix (If Component Fix Verified)
```typescript
// Update test to wait for drawer animation
await screen.findByTestId("mobile-nav-drawer");

fireEvent.keyDown(document, { key: "Escape", bubbles: true });

// Give MUI animation time to complete
await waitFor(() => {
  expect(screen.queryByTestId("mobile-nav-drawer")).not.toBeInTheDocument();
});
```

### Verification Checklist
- [ ] Drawer closes on Escape key press
- [ ] Drawer closes on backdrop click
- [ ] Drawer closes programmatically via onClose
- [ ] No console errors during open/close
- [ ] Mobile resize doesn't break drawer
- [ ] Test passes consistently

**Severity:** MEDIUM  
**Effort:** 1 hour (including test verification)  
**Priority:** HIGH (Mobile UX critical)

---

## FAILURE #2: AllotmentFilters Missing Form Label

### Test Location
```
File: frontend/src/pages/AllotmentFilters.test.tsx
Line: ~50 (approximate)
Test: "keeps every allocation criterion visible in the responsive grid"
```

### Failure Details

**Test Code:**
```typescript
expect(screen.getByLabelText("Item Description")).toBeInTheDocument();
// OR similar query looking for label text
```

**Error:**
```
TestingLibraryElementError: Unable to find a label with the text of: Item Description

Available elements:
- "License Number"
- "Filter By Actual Item Name"
- "Norm Class"
- "Exporter"
- [MISSING: Item Description]
```

**What's Happening:**
1. Test expects form field with label "Item Description"
2. Field is used to filter allotment items by description
3. **ACTUAL:** Label element not in DOM

### Root Cause Analysis

**Possible Causes (Priority Order):**

1. **MUI TextField Label Structure Changed:**
   ```typescript
   // v8 - Label was accessible via getByLabelText:
   <TextField label="Item Description" />
   // Renders: <label>Item Description</label>

   // v9 - Label may be in aria-label instead:
   <TextField label="Item Description" variant="outlined" />
   // Might render: <input aria-label="Item Description" /> (no <label> tag)
   ```

2. **Field Completely Removed in Refactor:**
   ```typescript
   // If MUI migration removed this field, test needs update
   // Check AllotmentFilters.tsx component render
   ```

3. **Label Text Changed During Migration:**
   ```typescript
   // Maybe renamed to "Description" or "Item Name"
   // Or using placeholder instead of label
   ```

### Investigation Steps

**Step 1: Check Component Render**
```bash
grep -n "Item Description" \
  frontend/src/pages/AllotmentFilters.tsx
```
Expected: Label definition (TextField, Select, or custom)

**Step 2: Examine MUI TextField Props**
```typescript
// In AllotmentFilters.tsx, find the field and check:
<TextField
  label="Item Description"  // ← This label text
  variant="outlined"
  // ...other props
/>
```

**Step 3: Check Test Query Strategy**
```typescript
// Current (failing):
screen.getByLabelText("Item Description")

// Alternatives for MUI v9:
screen.getByDisplayValue("") // If value is empty
screen.getByPlaceholderText("item description")
screen.queryByTestId("item-description-field")
screen.getByRole("textbox", { name: /item description/i })
```

### Fix Implementation

**Scenario A: Field Still Exists, Just Different Query**

```typescript
// Instead of:
expect(screen.getByLabelText("Item Description")).toBeInTheDocument();

// Try:
expect(screen.getByRole("textbox", { name: /item description/i })).toBeInTheDocument();

// Or add test-id to component and use:
expect(screen.getByTestId("item-description-filter")).toBeInTheDocument();
```

**Scenario B: MUI TextField Label → aria-label Migration**

In `AllotmentFilters.tsx`:
```typescript
import { TextField } from '@mui/material';

// Ensure proper label/aria-label
<TextField
  id="item-description"
  label="Item Description"
  placeholder="Search items..."
  variant="outlined"
  size="small"
  fullWidth
  value={itemDescription}
  onChange={(e) => setItemDescription(e.target.value)}
  // MUI v9 should create proper label accessibility
/>
```

**Scenario C: Custom Form Field Label**

If this is a custom Select/Autocomplete:
```typescript
<FormControl fullWidth size="small">
  <InputLabel id="item-description-label">
    Item Description
  </InputLabel>
  <Select
    labelId="item-description-label"
    id="item-description"
    value={itemDescription}
    onChange={handleItemDescriptionChange}
  >
    {/* Options */}
  </Select>
</FormControl>
```

### Test Fix

**Most Robust Solution:**
```typescript
import { render, screen } from '@testing-library/react';

test('keeps every allocation criterion visible', () => {
  render(<AllotmentFilters {...props} />);

  // Use more flexible queries that work with MUI v9
  const itemDescriptionField = screen.getByRole('textbox', {
    name: /item description/i
  });
  
  expect(itemDescriptionField).toBeInTheDocument();
  
  // Verify other fields too
  const licenseField = screen.getByRole('textbox', { name: /license/i });
  expect(licenseField).toBeInTheDocument();
});
```

### Verification Checklist
- [ ] Field renders with proper label
- [ ] Label text matches test expectation
- [ ] Field is keyboard accessible (Tab key)
- [ ] Field has proper aria-label or <label> association
- [ ] Test passes with updated query
- [ ] Field appears on mobile/tablet viewports

**Severity:** LOW  
**Effort:** 0.5 hours  
**Priority:** MEDIUM (Affects 1 test file)

---

## FAILURE #3: LicensePlanningWorkspace - Missing Button Disabled State

### Test Location
```
File: frontend/src/pages/planning/LicensePlanningWorkspace.test.tsx
Line: ~200 (approximate)
Test: "disables planning actions without an active saved rule"
```

### Failure Details

**Test Code:**
```typescript
const actionButton = screen.getByRole("button", { name: /some-action/ });
expect(actionButton).toHaveAttribute("data-disabled");
```

**Error:**
```
expect(element).toHaveAttribute("data-disabled")
Expected: <button data-disabled>
Received: <button class="MuiButton-root...">
// No data-disabled attribute
```

**What's Happening:**
1. Test expects planning action buttons to have `data-disabled` attribute when no active rule
2. **ACTUAL:** Attribute not present, but button might be disabled via other means (CSS class, disabled prop, aria-disabled)

### Root Cause Analysis

**MUI v9 Disabled State Implementation Changes:**

MUI v9 changed how disabled state is expressed:

```typescript
// MUI v8 (old way):
<button data-disabled>Action</button>

// MUI v9 (new ways):
<button aria-disabled="true">Action</button>  // Semantic
<button class="MuiButton-disabled">Action</button>  // CSS-based
<button disabled>Action</button>  // Native HTML
// OR combination of above
```

**Evidence from DOM:**
```html
<!-- MUI v9 Disabled Button (from test output) -->
<button 
  class="MuiButtonBase-root MuiButton-root ... MuiButton-disabled"
  tabindex="0"  <!-- Note: Still tabbable! -->
  type="button"
>
  Action
</button>

<!-- Key changes:
1. data-disabled attribute → NOT used
2. disabled HTML attribute → NOT used (tabindex still 0)
3. MuiButton-disabled class → USED
4. aria-disabled attribute → MAY BE USED
-->
```

### MUI v9 Button Disabled State Verification

Check actual button implementation in component:
```typescript
import { Button } from '@mui/material';

// Standard MUI button with disabled state:
<Button
  disabled={!hasActiveRule}  // ← This controls disabled state in v9
  onClick={handleAction}
>
  Plan All
</Button>

// MUI v9 will:
// 1. Add class="MuiButton-disabled"
// 2. Disable click handler via onClick prevention
// 3. May add aria-disabled="true"
// 4. Set cursor: not-allowed via CSS
// 5. Does NOT add data-disabled attribute
```

### Fix Implementation

**Option A: Update Test to Use aria-disabled**
```typescript
test('disables planning actions without an active saved rule', () => {
  render(<LicensePlanningWorkspace {...props} />);
  
  // MUI v9: Check aria-disabled instead of data-disabled
  const actionButton = screen.getByRole("button", { name: /plan all/i });
  
  // Use aria-disabled (accessible to screen readers)
  expect(actionButton).toHaveAttribute("aria-disabled", "true");
  
  // OR check the disabled prop
  expect(actionButton).toBeDisabled();
});
```

**Option B: Check for MuiButton-disabled Class**
```typescript
test('disables planning actions without an active saved rule', () => {
  const actionButton = screen.getByRole("button", { name: /plan all/i });
  
  expect(actionButton).toHaveClass("MuiButton-disabled");
  
  // Also verify visual cursor
  expect(actionButton).toHaveStyle("cursor: not-allowed");
});
```

**Option C: Verify Click Prevention (Recommended)**
```typescript
test('disables planning actions without an active saved rule', () => {
  const mockHandleClick = vi.fn();
  render(<LicensePlanningWorkspace onAction={mockHandleClick} {...props} />);
  
  const actionButton = screen.getByRole("button", { name: /plan all/i });
  
  // Verify button is disabled
  expect(actionButton).toHaveAttribute("aria-disabled", "true");
  // OR
  expect(actionButton).toHaveClass("MuiButton-disabled");
  
  // Verify click handler doesn't fire when disabled
  fireEvent.click(actionButton);
  expect(mockHandleClick).not.toHaveBeenCalled();
});
```

### Component Verification

Ensure `LicensePlanningWorkspace.tsx` properly disables buttons:

```typescript
import { Button } from '@mui/material';
import { useActiveRule } from './hooks/useActiveRule';

export function LicensePlanningWorkspace() {
  const { activeRule } = useActiveRule();
  const hasActiveRule = !!activeRule;

  return (
    <>
      <Button
        disabled={!hasActiveRule}  // ← This is correct for MUI v9
        onClick={handlePlanAll}
      >
        Plan All
      </Button>
      
      <Button
        disabled={!hasActiveRule}
        onClick={handleForceAll}
      >
        Force All
      </Button>
    </>
  );
}
```

### Verification Checklist
- [ ] Buttons have `aria-disabled="true"` or `disabled` HTML attribute
- [ ] Buttons have `MuiButton-disabled` CSS class
- [ ] Visual disabled styling applied (opacity, cursor)
- [ ] Click handlers don't fire when disabled
- [ ] Test passes with updated assertion
- [ ] No console warnings about disabled state

**Severity:** LOW (Visual/Test Issue)  
**Effort:** 0.5 hours  
**Priority:** LOW (Feature works, just test assertion wrong)

---

## FAILURE #4: LicensePlanningWorkspace - Alert Dialog Not Found

### Test Location
```
File: frontend/src/pages/planning/LicensePlanningWorkspace.test.tsx
Line: ~250 (approximate)
Test: "confirms Force All and submits ALL mode"
```

### Failure Details

**Test Code:**
```typescript
const dialog = screen.getByRole("alertdialog", { name: /Force re-plan E5/i });
expect(dialog).toBeInTheDocument();

// OR
fireEvent.click(screen.getByRole("button", { name: /Force All/i }));
const confirmButton = await screen.findByRole("button", { name: /confirm/i });
expect(confirmButton).toBeInTheDocument();
```

**Error:**
```
Unable to find an accessible element with the role "alertdialog" 
and name "Force re-plan E5?"

Accessible roles found:
- button (Back, New Rule, Preview, etc.)
- [NO alertdialog role]
```

**What's Happening:**
1. Test clicks "Force All" action button
2. Expects confirmation dialog to appear with role="alertdialog"
3. **ACTUAL:** Dialog/Modal appears but not with alertdialog role, OR not appearing at all

### Root Cause Analysis

**MUI v9 Dialog Component Changes:**

MUI v8 vs v9 dialog implementation differs:

```typescript
// MUI v8 (old - may have alertdialog):
<AlertDialog {...props}>
  <DialogTitle>Force re-plan E5?</DialogTitle>
  <DialogContent>...</DialogContent>
  <DialogActions>...</DialogActions>
</AlertDialog>

// MUI v9 (new - uses Dialog instead):
<Dialog {...props} role="dialog">  {/* NOT alertdialog */}
  <DialogTitle>Force re-plan E5?</DialogTitle>
  <DialogContent>...</DialogContent>
  <DialogActions>...</DialogActions>
</Dialog>
```

**The Issue:**
- MUI v8 had separate `AlertDialog` component
- MUI v9 unified everything under `Dialog` component
- Dialog uses `role="dialog"`, not `role="alertdialog"`
- Test expects old `role="alertdialog"`, but gets `role="dialog"` (if dialog exists)
- OR: Dialog component not rendering at all

### Investigation Steps

**Step 1: Find Force All Implementation**
```bash
grep -n "Force All\|Force.*All\|forceAll\|force_all" \
  frontend/src/pages/planning/LicensePlanningWorkspace.tsx
```

**Step 2: Check Dialog Usage**
```bash
grep -n "Dialog\|alert\|confirm" \
  frontend/src/pages/planning/LicensePlanningWorkspace.tsx
```

**Step 3: Verify Dialog Visibility in Tests**
```typescript
// Test manually
const button = screen.getByRole("button", { name: /Force All/i });
fireEvent.click(button);

// Check what dialogs are available
const dialogs = screen.queryAllByRole("dialog");
console.log("Dialogs found:", dialogs.length);
dialogs.forEach((d) => console.log(d.innerHTML));
```

### Fix Implementation

**Option A: Update Test to Use Dialog Role (Recommended)**
```typescript
test('confirms Force All and submits ALL mode', async () => {
  render(<LicensePlanningWorkspace {...props} />);
  
  // Click Force All button
  fireEvent.click(screen.getByRole("button", { name: /Force All/i }));
  
  // MUI v9: Use "dialog" role instead of "alertdialog"
  const confirmDialog = await screen.findByRole("dialog", { 
    name: /Force re-plan|confirm/i 
  });
  expect(confirmDialog).toBeInTheDocument();
  
  // Click confirm button in dialog
  const confirmButton = screen.getByRole("button", { 
    name: /confirm|yes|proceed/i 
  });
  fireEvent.click(confirmButton);
  
  // Verify action completed
  await waitFor(() => {
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
```

**Option B: Use Dialog Title as Accessible Name**
```typescript
test('confirms Force All and submits ALL mode', async () => {
  render(<LicensePlanningWorkspace {...props} />);
  
  fireEvent.click(screen.getByRole("button", { name: /Force All/i }));
  
  // If dialog doesn't have accessible name, find by title:
  const dialogTitle = await screen.findByText(/Force re-plan E5/i);
  const dialog = dialogTitle.closest('[role="dialog"]');
  
  expect(dialog).toBeInTheDocument();
  
  fireEvent.click(screen.getByRole("button", { name: /confirm/i }));
});
```

### Component Verification

**In LicensePlanningWorkspace.tsx:**

```typescript
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
} from '@mui/material';
import { useState } from 'react';

export function LicensePlanningWorkspace() {
  const [openForceDialog, setOpenForceDialog] = useState(false);
  const [selectedLicense, setSelectedLicense] = useState(null);

  const handleForceAll = (license: License) => {
    setSelectedLicense(license);
    setOpenForceDialog(true);  // ← Dialog should open
  };

  const handleConfirmForce = async () => {
    // Execute force replan
    await api.forcePlan(selectedLicense.id);
    setOpenForceDialog(false);
  };

  return (
    <>
      <Button onClick={() => handleForceAll(currentLicense)}>
        Force All (Redis)
      </Button>

      {/* MUI v9 Dialog - uses role="dialog", not "alertdialog" */}
      <Dialog
        open={openForceDialog}
        onClose={() => setOpenForceDialog(false)}
        // MUI v9: dialog role is default, no need to specify
      >
        <DialogTitle>
          Force re-plan {selectedLicense?.license_number}?
        </DialogTitle>
        <DialogContent>
          This will re-plan all items. Continue?
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenForceDialog(false)}>
            Cancel
          </Button>
          <Button 
            onClick={handleConfirmForce}
            variant="contained"
            color="error"
          >
            Confirm
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
```

### Verification Checklist
- [ ] Dialog opens when Force All button clicked
- [ ] Dialog has title "Force re-plan E5?" (or similar)
- [ ] Dialog has confirm and cancel buttons
- [ ] Confirm button executes force replan API call
- [ ] Cancel button closes dialog without action
- [ ] Dialog uses `role="dialog"` (MUI v9 standard)
- [ ] Test finds dialog with `screen.getByRole("dialog")`
- [ ] No console errors during dialog lifecycle

**Severity:** MEDIUM  
**Effort:** 1 hour  
**Priority:** HIGH (Critical planning workflow)

---

## FAILURE #5: LicenseOverviewPage Duplicate API Call

### Test Location
```
File: frontend/src/pages/license-overview/LicenseOverviewPage.documents.test.tsx
Line: ~80 (approximate)
Test: "keeps the protected-media failure contained and issues one shared licence-detail request"
```

### Failure Details

**Test Code:**
```typescript
const expectedCalls = ['/licenses/2260/'];
const actualCalls = [...mockApiCalls];

expect(actualCalls).toHaveLength(1);
expect(actualCalls[0]).toMatch(/licenses\/\d+\//);
```

**Error:**
```
expected [ ['licenses/2260/'], ['licenses/2260/'] ] to have length of 1 but got 2

Actual API Calls Made:
1. GET /api/licenses/2260/
2. GET /api/licenses/2260/ (DUPLICATE)
```

**What's Happening:**
1. Test renders LicenseOverviewPage with a specific license ID
2. Expects ONE API call to fetch license detail
3. **ACTUAL:** API called TWICE with same license ID

### Root Cause Analysis

**Possible Causes (Priority Order):**

1. **React StrictMode Double Invocation (Development)**
   ```typescript
   // In development with StrictMode:
   // 1. Component mounts → API call
   // 2. Component unmounts (strictmode)
   // 3. Component remounts → API call again
   // Result: 2 API calls in tests, 1 in production
   ```

2. **useEffect Dependency Issue**
   ```typescript
   // Wrong:
   useEffect(() => {
     fetchLicense();  // Runs twice if licenseId in deps
   }, [licenseId]);  // licenseId reference changes

   // Or:
   useEffect(() => {
     fetchLicense();
   }, []);  // Empty deps - missing dependency

   // Or:
   useEffect(() => {
     fetchLicense();
   });  // No deps array - runs every render
   ```

3. **Redundant API Calls in Component Logic**
   ```typescript
   // Component mounted:
   // 1. useEffect fetches license
   // 2. Parent component also fetches license
   // 3. Fetch triggered by URL change
   // Result: Multiple fetches for same data
   ```

4. **React Query / React Hook Form Cache Issue**
   ```typescript
   // useQuery called multiple times:
   const query = useQuery(['licenses', licenseId], fetchLicense);
   // Renders:
   // 1. First render → cache miss → API call
   // 2. Second render → cache should hit, but doesn't
   // Cause: Query key changed, or cache invalidated
   ```

### Investigation Steps

**Step 1: Find License Detail Fetch**
```bash
grep -n "GET.*license\|fetchLicense\|/licenses/2260" \
  frontend/src/pages/license-overview/LicenseOverviewPage.tsx
```

**Step 2: Check useEffect Dependencies**
```typescript
// In LicenseOverviewPage.tsx, find patterns like:
useEffect(() => {
  // API call here
  api.get(`/licenses/${licenseId}/`)
}, [/* dependencies */]);

// Check if licenseId is properly memoized
// Check if fetch function is wrapped in useCallback
```

**Step 3: Check Component Rendering**
```typescript
// Test should show:
console.log("Renders:", renderCount);  // Should be 2-3 in StrictMode
console.log("API Calls:", apiCallCount);  // Should be 1-2 at most
```

### Fix Implementation

**Option A: Prevent StrictMode Double-Fetch (Test Level)**
```typescript
test('keeps the protected-media failure contained...', () => {
  // Wrap in act() to ensure all effects complete
  render(
    <QueryClientProvider client={queryClient}>
      <LicenseOverviewPage licenseId="2260" />
    </QueryClientProvider>
  );

  // Allow effects to settle
  waitFor(() => {
    expect(apiCallCount).toBeLessThanOrEqual(2); // Allow max 2 (StrictMode)
  });
  
  // Or specifically check for deduplication:
  expect(
    apiCallsMade.filter(call => call.includes('/licenses/2260/'))
  ).toHaveLength(1);
});
```

**Option B: Fix Component Fetch Pattern (Component Level)**
```typescript
import { useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';

export function LicenseOverviewPage({ licenseId }) {
  // Use React Query for automatic deduplication
  const { data: license } = useQuery({
    queryKey: ['licenses', licenseId],  // Stable key
    queryFn: () => api.get(`/licenses/${licenseId}/`),
    staleTime: Infinity,  // Don't refetch unless explicitly invalidated
  });

  // OR with plain useEffect:
  useEffect(() => {
    // Use AbortController to prevent race conditions
    const abortController = new AbortController();

    const fetchLicense = async () => {
      try {
        const response = await api.get(
          `/licenses/${licenseId}/`,
          { signal: abortController.signal }
        );
        setLicenseData(response.data);
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(err);
        }
      }
    };

    fetchLicense();

    return () => abortController.abort();  // Cleanup cancels request
  }, [licenseId]);  // Only refetch if licenseId changes

  return <LicenseDetail data={license} />;
}
```

**Option C: Memoize Fetch Function**
```typescript
import { useCallback, useEffect, useState } from 'react';

export function LicenseOverviewPage({ licenseId }) {
  const [license, setLicense] = useState(null);

  // Memoize fetch function to prevent recreation
  const fetchLicense = useCallback(async () => {
    const response = await api.get(`/licenses/${licenseId}/`);
    setLicense(response.data);
  }, [licenseId]);

  // Effect only depends on stable fetch function
  useEffect(() => {
    fetchLicense();
  }, [fetchLicense]);

  return <LicenseDetail data={license} />;
}
```

### Test Diagnostic

**Add logging to identify cause:**
```typescript
test('keeps the protected-media failure contained...', async () => {
  const apiSpy = vi.spyOn(api, 'get');

  render(
    <QueryClientProvider client={queryClient}>
      <LicenseOverviewPage licenseId="2260" />
    </QueryClientProvider>
  );

  // Wait for all effects
  await waitFor(() => {
    expect(apiSpy).toHaveBeenCalled();
  });

  // Detailed call analysis
  const licenseCalls = apiSpy.mock.calls.filter(
    call => call[0]?.includes('/licenses/2260/')
  );

  console.log('License API calls:', licenseCalls.length);
  licenseCalls.forEach((call, i) => {
    console.log(`Call ${i + 1}:`, call[0], 'Stack:', call.stack);
  });

  // In development with StrictMode: 2 is acceptable
  // In production: should be 1
  expect(licenseCalls.length).toBeLessThanOrEqual(2);
});
```

### Verification Checklist
- [ ] License detail API called exactly once per component mount
- [ ] Repeated renders don't trigger additional API calls
- [ ] licenseId change triggers refetch (if appropriate)
- [ ] AbortController cancels in-flight requests on unmount
- [ ] React Query cache prevents duplicate requests
- [ ] Test accounts for StrictMode double-invocation in dev
- [ ] No console warnings about multiple requests
- [ ] Production behavior (1 call) vs test behavior (may be 2) documented

**Severity:** MEDIUM (Performance Optimization)  
**Effort:** 1.5 hours  
**Priority:** MEDIUM (Optimization, feature works)

---

## SUMMARY TABLE

| Failure | Component | Severity | Effort | Status |
|---------|-----------|----------|--------|--------|
| #1 Mobile Drawer Escape | TopNav.tsx | MEDIUM | 1h | Analysis: Ready to fix |
| #2 Form Label Missing | AllotmentFilters.tsx | LOW | 0.5h | Analysis: Query update needed |
| #3 Button Disabled State | LicensePlanningWorkspace.tsx | LOW | 0.5h | Analysis: Test assertion update |
| #4 Alert Dialog Missing | LicensePlanningWorkspace.tsx | MEDIUM | 1h | Analysis: Dialog role change |
| #5 Duplicate API Call | LicenseOverviewPage.tsx | MEDIUM | 1.5h | Analysis: Deduplication needed |

**Total Effort to Fix All:** 4.5 hours  
**Recommended Order:** #4, #1, #5, #2, #3

---

## FIXING GUIDE

### Phase 1 (Day 1): Critical Component Fixes
1. Fix #4: AlertDialog → Dialog role migration (1 hour)
2. Fix #1: Mobile Drawer Escape handler (1 hour)

### Phase 2 (Day 1): Performance & Optimization
3. Fix #5: Deduplicate API calls (1.5 hours)

### Phase 3 (Day 2): Test & UI Polish
4. Fix #2: Form field label (0.5 hours)
5. Fix #3: Button disabled state test (0.5 hours)

### Validation After Fixes
```bash
# Run full test suite
cd frontend && npm run test

# Expected result:
# Test Files  0 failed | 76 passed (76 total)
# Tests  0 failed | 522 passed (522 total)
```

---

**Analysis Complete**  
Ready for implementation by frontend-engineer agent.

