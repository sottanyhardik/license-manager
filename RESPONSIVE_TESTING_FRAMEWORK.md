# Responsive Testing Framework

**Created:** 2026-09-25  
**Status:** Phase 1 - Ready for Continuous Testing

---

## Overview

This framework enables continuous responsive design testing across all redesigned pages and components. The framework tracks:

1. **5 Breakpoints** for systematic testing
2. **Automated Test Suite** for validation
3. **Manual Testing Checklist** for visual inspection
4. **Issue Tracking** for problems found
5. **Daily Testing Log** for progress

---

## Testing Matrix

### Breakpoints by Device Category

| Category | Breakpoint | Width | Height | Device Example | Tailwind |
|----------|-----------|-------|--------|-----------------|----------|
| Mobile | 390×844 | 390 | 844 | iPhone 12 Pro | base (default) |
| Tablet Portrait | 768×1024 | 768 | 1024 | iPad vertical | md: |
| Tablet Landscape | 1024×768 | 1024 | 768 | iPad horizontal | lg: |
| Laptop | 1366×768 | 1366 | 768 | Secondary laptop | xl: |
| Desktop | 1440×900 | 1440 | 900 | Primary desktop | 2xl: |

---

## Quick Test Procedure

### For Each Page Redesigned:

1. **Open Dev Tools** (F12)
2. **Toggle Device Toolbar** (Cmd+Shift+M / Ctrl+Shift+M)
3. **Set Viewport** to each breakpoint in order
4. **Visual Inspection** per checklist
5. **Log Results** in testing log
6. **Report Issues** to RESPONSIVE_ISSUES.md

### Automated Testing

```bash
# Run responsive test suite
cd frontend
npm run test -- responsive.test.ts

# Watch mode (continuous)
npm run test:watch -- responsive.test.ts
```

---

## Manual Testing Checklist

### Layout & Overflow (All Breakpoints)
- [ ] No horizontal scrollbar visible
- [ ] No content overflow off-screen
- [ ] All text fits without truncation
- [ ] Images scale appropriately
- [ ] Containers have proper max-widths
- [ ] Padding/margins appropriate for screen size

### Text & Typography (All Breakpoints)
- [ ] Headings readable (min 24px)
- [ ] Body text readable (min 14px)
- [ ] Link text understandable
- [ ] Code/monospace properly sized
- [ ] Line height adequate for readability (1.5+)
- [ ] Line length not too long (max 80ch ideal)

### Interactive Elements (All Breakpoints)
- [ ] Buttons clickable (44×44px minimum)
- [ ] Links understandable and actionable
- [ ] Dropdowns work without overflow
- [ ] Hover states visible
- [ ] Focus states visible for keyboard nav
- [ ] Tooltips don't extend off-screen

### Forms (All Breakpoints, Especially Mobile)
- [ ] Input fields properly sized
- [ ] Input font >= 16px (prevents iOS zoom)
- [ ] Labels associated and visible
- [ ] Placeholder text readable
- [ ] Error messages visible
- [ ] Submit button accessible
- [ ] Date pickers work on mobile
- [ ] Select dropdowns don't overflow
- [ ] Checkboxes/radios 44px+ touch target
- [ ] Form doesn't require horizontal scroll

### Navigation (All Breakpoints)
- [ ] Header/navigation accessible
- [ ] Menu items clearly visible
- [ ] Active page indicated
- [ ] Breadcrumbs functional if present
- [ ] Logo/branding visible
- [ ] Mobile menu (if hamburger) opens/closes
- [ ] Navigation doesn't block content

### Tables & Data (All Breakpoints)
- [ ] Table doesn't overflow horizontally
- [ ] Horizontal scroll smooth if needed
- [ ] Column headers visible and clear
- [ ] Data rows distinguishable
- [ ] Actions buttons accessible
- [ ] Sorting/filtering controls accessible
- [ ] Pagination visible (if applicable)

### Filter Cards (All Breakpoints, Especially Tablet/Mobile)
- [ ] Filter panels stack vertically on mobile
- [ ] Filter cards fit without overflow
- [ ] All filter controls accessible
- [ ] Filter buttons properly sized (44px)
- [ ] Date range pickers work on mobile
- [ ] Checkboxes/radios properly sized
- [ ] Clear/Apply buttons clearly visible
- [ ] Filter state persists correctly

### Modals & Dialogs (All Breakpoints)
- [ ] Modal not oversized on mobile
- [ ] Modal scrollable if content tall
- [ ] Close button accessible (44px target)
- [ ] Backdrop doesn't prevent interaction
- [ ] Backdrop color appropriate for dark mode
- [ ] Modal title readable
- [ ] Modal content doesn't extend off-screen

### Sidebar/Drawer (If Applicable)
- [ ] Hidden on mobile by default
- [ ] Hamburger menu to toggle on mobile
- [ ] Full-width drawer on mobile if visible
- [ ] Sidebar items accessible
- [ ] Scroll if content tall
- [ ] Close doesn't require specific position

### Dark Mode (All Breakpoints)
- [ ] Text contrast >= 4.5:1 (WCAG AA)
- [ ] Background colors adjusted appropriately
- [ ] Borders visible in dark mode
- [ ] Icons visible and colored correctly
- [ ] Input backgrounds distinct
- [ ] Buttons have enough contrast
- [ ] Focus states visible
- [ ] Shadows still visible (not lost)
- [ ] Images don't appear washed out
- [ ] All interactive elements clear

### Mobile Specific (390×844)
- [ ] Page fits without horizontal scroll
- [ ] Touch targets all >= 44×44px
- [ ] Status bar doesn't overlap content
- [ ] Bottom navigation (if any) doesn't cover content
- [ ] Hamburger menu accessible (top-right area)
- [ ] Forms don't require zooming
- [ ] Keyboard navigation works (Tab key)
- [ ] Text doesn't exceed 2-3 lines when avoidable
- [ ] Buttons don't cluster (need spacing)
- [ ] Two-column layouts stack to single column

---

## Testing Workflow

### Pre-Test Setup
```bash
# 1. Start dev server
cd frontend
npm run dev

# 2. Dev server runs on http://localhost:5173

# 3. Build test suite (optional)
npm run test -- responsive.test.ts

# 4. Open browser to http://localhost:5173
```

### Testing Session
1. Identify page that was redesigned
2. Note the URL path
3. For each breakpoint (mobile → desktop):
   - Set viewport size in DevTools
   - Navigate to page
   - Run through checklist
   - Note any issues
   - Take screenshot if needed
4. Log results: ✓ (pass), ⚠ (issue), ✗ (failure)
5. If issues found, report to RESPONSIVE_ISSUES.md

### Logging Format
```
**Page:** [URL]
**Date:** 2026-09-25
**Tested By:** [Agent Name]
**Dev Server:** http://localhost:5173

| Breakpoint | Status | Issues |
|------------|--------|--------|
| 390×844 (mobile) | ✓ / ⚠ / ✗ | [if any] |
| 768×1024 (tablet-p) | ✓ / ⚠ / ✗ | [if any] |
| 1024×768 (tablet-l) | ✓ / ⚠ / ✗ | [if any] |
| 1366×768 (laptop) | ✓ / ⚠ / ✗ | [if any] |
| 1440×900 (desktop) | ✓ / ⚠ / ✗ | [if any] |

**Notes:** [Any additional observations]
```

---

## Common Issues Reference

### Issue: Horizontal Overflow
- **Cause:** Fixed-width elements (width: 1200px)
- **Fix:** Use `w-full` or `max-w-*` with responsive variants
- **Prevention:** Test `overflow-x: hidden` on body

### Issue: Touch Targets Too Small
- **Cause:** `h-6 w-6` or similar for buttons
- **Fix:** Use `h-11 w-11` minimum (44×44px)
- **Prevention:** Lint rule: buttons must have class h-10 or larger

### Issue: Text Too Small on Mobile
- **Cause:** `text-xs` for body, no responsive scaling
- **Fix:** `text-xs md:text-sm lg:text-base`
- **Prevention:** Never use text-xs for body text on mobile

### Issue: Tables Overflow
- **Cause:** Table not wrapped in scroll container
- **Fix:** `<div className="overflow-x-auto"><table>...</table></div>`
- **Prevention:** Always wrap tables

### Issue: Forms Don't Work on Mobile
- **Cause:** Inputs not sized for touch, labels missing
- **Fix:** `h-11` for inputs, labels above inputs, 16px+ font
- **Prevention:** Always test form submission on 390×844

### Issue: Dark Mode Contrast Fails
- **Cause:** Hardcoded colors without dark: variants
- **Fix:** `bg-white dark:bg-slate-950 text-black dark:text-white`
- **Prevention:** Always add dark: variant for colors

### Issue: Modals Oversized on Mobile
- **Cause:** Fixed width not adjusted for mobile
- **Fix:** `w-screen h-screen md:w-96 md:h-auto`
- **Prevention:** Modals should be full-screen on mobile

---

## Tools & Resources

### Browser DevTools
- **Chrome:** F12 → Device Toolbar toggle (Cmd+Shift+M)
- **Firefox:** F12 → Responsive Design Mode (Cmd+Shift+M)
- **Safari:** Develop → Enter Responsive Design Mode
- **Browser.dev:** Free responsive test tool

### Automated Testing
- **Playwright:** E2E testing with viewport sizes
- **Vitest:** Unit tests (responsive.test.ts)
- **Axe-core:** Accessibility + responsive testing

### Lint Rules
- ESLint rules for touch targets
- Stylelint for responsive design patterns
- Custom rules in `.eslintrc.json`

### Documentation
- [Tailwind Responsive Design](https://tailwindcss.com/docs/responsive-design)
- [WCAG 2.1 Target Size](https://www.w3.org/WAI/WCAG21/Understanding/target-size.html)
- [MDN: Responsive Design](https://developer.mozilla.org/en-US/docs/Learn/CSS/CSS_layout/Responsive_Design)
- [Web.dev: Mobile Performance](https://web.dev/mobile/)

---

## Phase 1 Checklist (Complete)

- [x] Dev server running (port 5173)
- [x] 5 breakpoints defined and documented
- [x] Testing checklist created
- [x] Automated test suite created (responsive.test.ts)
- [x] Issue tracking framework (RESPONSIVE_ISSUES.md)
- [x] Mobile optimization guide (MOBILE_OPTIMIZATION_GUIDE.md)
- [x] Testing log created (RESPONSIVE_TESTING_LOG.md)
- [x] Testing framework documented (this file)

---

## Phase 2 Status

**AWAITING:** Pages redesigned by other agents

When pages become available for testing:
1. Test immediately at all 5 breakpoints
2. Log results in RESPONSIVE_TESTING_LOG.md
3. Report any issues in RESPONSIVE_ISSUES.md
4. Coordinate fixes with agent teams

---

## Continuous Testing Mode

The framework is now in **continuous testing mode**. Any time a page is redesigned:

1. **Alert:** Notify coordinator of redesign ready for testing
2. **Test:** Run through all breakpoints
3. **Report:** Update logs and issue tracker
4. **Iterate:** Request fixes if issues found
5. **Verify:** Re-test after fixes

**Target:** < 15 minutes per page for full responsive validation

---

## Key Metrics

- **Mobile (390×844):** Primary concern - must have zero overflow
- **Touch targets:** 100% of interactive elements >= 44×44px
- **Typography:** 100% readable without zooming
- **Dark mode:** 100% WCAG AA contrast (4.5:1+)
- **Forms:** 100% functional on mobile keyboard
- **Tables:** 100% accessible (scroll or responsive layout)

