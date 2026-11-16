# Responsive Testing Session Template

**Use this template for each page tested in Phase 2**

---

## Session Header

```
**Page/Component:** [URL or component name]
**Date:** YYYY-MM-DD
**Tested By:** [Your name/agent]
**Dev Server:** http://localhost:5173
**Session Duration:** [e.g., 12 minutes]
```

---

## Testing Matrix

Copy and fill in for each breakpoint:

```
| Breakpoint | Dimensions | Status | Issues | Notes |
|-----------|-----------|--------|--------|-------|
| Mobile | 390×844 | ✓/⚠/✗ | [if any] | [notes] |
| Tablet Portrait | 768×1024 | ✓/⚠/✗ | [if any] | [notes] |
| Tablet Landscape | 1024×768 | ✓/⚠/✗ | [if any] | [notes] |
| Laptop | 1366×768 | ✓/⚠/✗ | [if any] | [notes] |
| Desktop | 1440×900 | ✓/⚠/✗ | [if any] | [notes] |
```

**Legend:**
- ✓ = Pass (no issues)
- ⚠ = Issues found (log below)
- ✗ = Critical failure (blocking)

---

## Checklist by Breakpoint

### Mobile (390×844)

**Layout & Overflow**
- [ ] No horizontal scrollbar
- [ ] Content fits viewport
- [ ] No text clipping
- [ ] Images scale properly

**Typography**
- [ ] Headings readable (min 24px)
- [ ] Body text readable (14px+)
- [ ] Line height adequate (1.5+)
- [ ] No orphaned words

**Interactive Elements**
- [ ] Buttons 44×44px+ (touch targets)
- [ ] Links clearly tappable
- [ ] Form inputs properly sized
- [ ] No overlapping elements

**Forms**
- [ ] Input fields 44px+ height
- [ ] Input font 16px+ (iOS zoom prevention)
- [ ] Labels visible and clear
- [ ] Submit button accessible
- [ ] Error messages visible

**Navigation**
- [ ] Menu accessible (hamburger if needed)
- [ ] Navigation doesn't block content
- [ ] Breadcrumbs work if present
- [ ] Logo/home link accessible

**Tables/Data**
- [ ] No horizontal overflow
- [ ] Horizontal scroll smooth if needed
- [ ] Data distinguishable by row
- [ ] Action buttons accessible

**Filters (if applicable)**
- [ ] Filters stack vertically
- [ ] All filter controls accessible
- [ ] Checkboxes 44px+ touch target
- [ ] Clear/Apply buttons visible

**Modals/Dialogs (if applicable)**
- [ ] Modal full-screen on mobile
- [ ] Close button accessible
- [ ] Content scrollable if tall
- [ ] Backdrop overlay present

**Dark Mode**
- [ ] Text contrast >= 4.5:1
- [ ] All elements visible
- [ ] Icons properly colored
- [ ] Input backgrounds distinct

---

### Tablet Portrait (768×1024)

**Layout**
- [ ] Content properly stacked
- [ ] Margins appropriate
- [ ] No unexpected overflow
- [ ] Two-column layout if applicable

**Typography**
- [ ] Text scales appropriately
- [ ] Readable without zooming
- [ ] Proper line breaks

**Interactive**
- [ ] Touch targets adequate
- [ ] Buttons clearly tappable
- [ ] Forms functional

**Navigation**
- [ ] Menu accessible
- [ ] Links clear and separate
- [ ] Breadcrumbs work

**Tables**
- [ ] Card layout or horizontal scroll
- [ ] Headers clear
- [ ] Data readable

**Dark Mode**
- [ ] Contrast maintained
- [ ] Colors appropriate

---

### Tablet Landscape (1024×768)

**Layout**
- [ ] Multi-column layout works
- [ ] Margins/padding balanced
- [ ] No odd spacing gaps

**Typography**
- [ ] Text scales appropriately
- [ ] Headers at right size

**Interactive**
- [ ] Buttons properly spaced
- [ ] No overlapping elements

**Navigation**
- [ ] Full navigation visible if room
- [ ] Accessible and clear

**Tables**
- [ ] Multiple columns visible if space
- [ ] Horizontal scroll smooth if needed

---

### Laptop (1366×768)

**Layout**
- [ ] Multi-column layout optimal
- [ ] Sidebar width appropriate
- [ ] Content area balanced

**Typography**
- [ ] Text at desktop sizes
- [ ] Headings properly scaled

**Interactive**
- [ ] All buttons accessible
- [ ] Hover states visible

**Navigation**
- [ ] Full navigation visible
- [ ] Desktop menu working

**Tables**
- [ ] Most/all columns visible
- [ ] No unnecessary scrolling

---

### Desktop (1440×900)

**Layout**
- [ ] Full layout optimal
- [ ] Max-width constraints respected
- [ ] Balanced spacing throughout

**Typography**
- [ ] Desktop font sizes correct
- [ ] Readability excellent

**Interactive**
- [ ] All elements interactive
- [ ] Hover states clear

**Navigation**
- [ ] Full navigation functional
- [ ] All menus work

**Tables**
- [ ] All columns visible
- [ ] No horizontal scrolling needed

---

## Issues Found

### Issue #1
```
**Severity:** CRITICAL / HIGH / MEDIUM / LOW
**Affected Breakpoint:** [e.g., mobile, all]
**Component:** [name]
**Description:** [What's wrong?]
**Steps to Reproduce:**
1. [step 1]
2. [step 2]
3. [see issue]

**Expected:** [What should happen]
**Actual:** [What's happening]
**Screenshot:** [path if available]
**Assigned To:** [agent name]
```

### Issue #2
[Repeat as needed]

---

## Summary

**Total Issues:** [number]
- Critical: [number]
- High: [number]
- Medium: [number]
- Low: [number]

**Overall Status:** ✓ PASS / ⚠ ISSUES / ✗ BLOCKING

**Next Steps:** [What needs to happen next]

---

## Sign-Off

**Tested By:** [Name/Agent]  
**Date:** YYYY-MM-DD  
**Time:** HH:MM  
**Verified:** [Yes/No]  

---

## Copy-Paste Quick Start

```markdown
**Page/Component:** 
**Date:** 2026-09-25
**Tested By:** 
**Dev Server:** http://localhost:5173

| Breakpoint | Dimensions | Status | Issues | Notes |
|-----------|-----------|--------|--------|-------|
| Mobile | 390×844 | | | |
| Tablet Portrait | 768×1024 | | | |
| Tablet Landscape | 1024×768 | | | |
| Laptop | 1366×768 | | | |
| Desktop | 1440×900 | | | |

### Issues Found
None yet.

**Overall Status:** ✓ PASS

```

