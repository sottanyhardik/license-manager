# Responsive Testing Quick Reference

**Quick Lookup for Phase 2 Continuous Testing**

---

## Dev Server

```
URL:  http://localhost:5173
Port: 5173
```

---

## 5 Breakpoints (Copy-Paste for DevTools)

```
Mobile         → 390 × 844   (iPhone 12 Pro)
Tablet Portrait → 768 × 1024  (iPad Vertical)
Tablet Land.   → 1024 × 768  (iPad Horizontal)
Laptop         → 1366 × 768  (Secondary Laptop)
Desktop        → 1440 × 900  (Primary Desktop)
```

---

## Chrome DevTools Quick Steps

1. **Open DevTools:** F12
2. **Toggle Device Toolbar:** Cmd+Shift+M (Mac) or Ctrl+Shift+M (Windows)
3. **Edit Dimensions:** Click dropdown → Edit
4. **Paste dimensions** from above
5. **Test page** at each breakpoint

---

## Testing Checklist (Minimal)

For each page at each breakpoint:

- [ ] **No horizontal scroll**
- [ ] **Text readable**
- [ ] **Buttons clickable** (44px+)
- [ ] **Forms work**
- [ ] **Dark mode OK** (contrast 4.5:1)

---

## Run Automated Tests

```bash
cd frontend

# Run once
npm run test -- responsive.test.ts

# Watch mode
npm run test:watch -- responsive.test.ts
```

**Last Run:** All 36 tests passing ✓

---

## Report Issues

1. **Save:** RESPONSIVE_ISSUES.md
2. **Format:** Use template in file
3. **Severity:** CRITICAL | HIGH | MEDIUM | LOW
4. **Status:** OPEN | IN PROGRESS | FIXED

---

## Key Constraints

| Item | Minimum |
|------|---------|
| Touch Target Size | 44×44 px |
| Font Size (body) | 14 px |
| Font Size (minimum) | 12 px |
| Contrast Ratio (dark) | 4.5:1 (WCAG AA) |
| Input Font (iOS) | 16 px (prevents zoom) |
| Line Height | 1.5 |

---

## Common Fixes

| Issue | Fix |
|-------|-----|
| Overflow | Use `w-full` instead of fixed width |
| Small buttons | Change `h-6` to `h-11` |
| Text too small | Add responsive: `text-xs md:text-sm` |
| Table overflow | Wrap in `overflow-x-auto` |
| Dark mode | Add `dark:` variant to colors |
| Form issues | Use `h-11` inputs, `16px` font |

---

## Logging Format

```
**Page:** /path
**Date:** 2026-09-25
**Breakpoint:** 390×844
**Status:** ✓ (pass) or ⚠ (issue) or ✗ (fail)
**Notes:** [details]
```

---

## Files to Know

| File | Purpose |
|------|---------|
| RESPONSIVE_TESTING_LOG.md | Track daily progress |
| RESPONSIVE_ISSUES.md | Log found problems |
| MOBILE_OPTIMIZATION_GUIDE.md | Design guidelines |
| responsive.test.ts | Automated tests |
| RESPONSIVE_TESTING_FRAMEWORK.md | Detailed procedure |

---

## Phase Status

**Phase 1: ✓ COMPLETE**
- Dev server running
- 5 breakpoints configured
- Test suite created (36 tests passing)
- Framework documented

**Phase 2: 🔴 AWAITING**
- Awaiting page redesigns from other agents
- Ready to test immediately

**Phase 3: ⏳ PENDING**
- Mobile-specific fixes (when issues found)

**Phase 4: ⏳ PENDING**
- Dark mode testing

---

## Next Action

**MONITOR for page redesigns → TEST immediately → LOG results**

Coordinator will assign pages. Test each at all 5 breakpoints using the framework.

