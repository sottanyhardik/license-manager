# Accessibility Fixes — Implementation Checklist

**Based on Code Reviewer audit**  
**Status:** READY FOR IMPLEMENTATION

---

## BLOCKING FIXES (Must Apply)

### Fix #1: Add aria-labels to Mobile-Hidden Button Text
**Files:** `LicenseLedger.tsx`, `LicenseLedgerDetail.tsx`

**Issue:** Export buttons with responsive text are icon-only on mobile (no aria-label)

**Lines to Fix:**
```
LicenseLedger.tsx:260-272
- Download button
- Custom Ledger PDF button

LicenseLedgerDetail.tsx:400-420
- PDF export button
- Excel export button
- Other export buttons
```

**Fix Pattern:**
```tsx
// BEFORE:
<button type="button" onClick={() => onDownloadLicense()}>
  <FileSpreadsheet className="size-3.5" aria-hidden="true" />
  <span className="hidden sm:inline">Package</span>
</button>

// AFTER:
<button 
  type="button" 
  onClick={() => onDownloadLicense()}
  aria-label="Download package for this license"
>
  <FileSpreadsheet className="size-3.5" aria-hidden="true" />
  <span className="hidden sm:inline">Package</span>
</button>
```

**Completion:** Apply to all export buttons in both files

---

### Fix #2: Verify Color Contrast on CSS Variables
**File:** `ItemPivotReport.tsx` lines 125-150

**Issue:** ACTION_BUTTON_STYLES uses CSS variables without verified contrast ratios

**Variables to Check:**
```
var(--tb-warning-text)
var(--tb-warning-soft)
var(--tb-info-soft)
var(--tb-info-text)
var(--tb-success-soft)
var(--tb-success-text)
```

**Options:**
1. Replace with Design System colors (WCAG AA verified)
2. Or: Document design system token contrast verification

**Replace with:**
```javascript
// Deep Slate system colors (verified WCAG AA)
color: '#E2E8F0',           // Primary Text
backgroundColor: '#1E293B', // Surface
// OR use Tailwind classes: text-slate-200 bg-slate-700
```

**Completion:** Verify all color combinations meet 4.5:1 ratio

---

### Fix #3: Remove Redundant Title Attributes
**File:** `LicenseLedger.tsx` lines 596-605

**Issue:** Both `title` AND `aria-label` with identical text (redundant)

**Fix:**
```tsx
// BEFORE:
<button 
  title="Choose destination folder and start package download"
  aria-label="Choose destination folder and start package download"
>

// AFTER:
<button 
  aria-label="Choose destination folder and start package download"
>
```

**Completion:** Remove all redundant title attributes from buttons

---

## NON-BLOCKING IMPROVEMENTS

### Improvement #1: Add Context to Generic Export Buttons
**Files:** `ItemReport.tsx`, `UserList.tsx`

**Pattern:**
```tsx
aria-label={downloading ? "Exporting..." : "Export to Excel"}
```

**Completion:** Make aria-labels more specific (not blocking)

---

### Improvement #2: Verify Focus Indicators
**Check:** All interactive elements have visible focus styles
```bash
grep -r "focus-visible\|focus:ring" frontend/src/pages/*.tsx
```

**Completion:** Spot-check visible focus rings on several buttons

---

## VERIFICATION CHECKLIST

After applying all fixes:

- [ ] All mobile-hidden buttons have aria-labels
- [ ] Color variables verified for WCAG AA contrast
- [ ] No redundant title attributes
- [ ] Build still passes
- [ ] Lint passes
- [ ] Tests pass (522/522)
- [ ] Accessibility compliance ≥80%

---

## EXPECTED TIMELINE

- **Fix #1 (aria-labels):** 10-15 minutes (pattern-based, multiple instances)
- **Fix #2 (colors):** 5-10 minutes (variable replacement)
- **Fix #3 (redundant titles):** 2-3 minutes (simple deletion)

**Total estimated time:** 20-30 minutes (after other agents complete)

---

## SIGN-OFF

When all fixes applied and verified:
- [ ] LicenseLedger exports are accessible
- [ ] LicenseLedgerDetail exports are accessible
- [ ] ItemPivotReport colors verified
- [ ] No accessibility regressions introduced
- [ ] Ready for browser accessibility testing
