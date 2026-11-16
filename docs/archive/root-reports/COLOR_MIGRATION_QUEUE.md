# Color Migration Queue
## 51+ Routes Priority Migration Plan

**Version:** 2.0  
**Date:** 2026-09-25  
**Total Routes:** 51+  
**Estimated Effort:** 7-10 days (Phase 2-3 combined)

---

## Summary

This document lists all 51+ routes/pages in the License Manager application, organized by priority for color migration. The priority is based on:

1. **User Impact** — How many users see this page daily?
2. **Visual Prominence** — How much color is used?
3. **Color Complexity** — How many colors need updating?
4. **Accessibility Risk** — Does it use problematic color combinations?

---

## Priority Tiers

### 🔴 P1 (Critical) — Ship First
**Effort:** 2-3 days  
**User Impact:** Very High  
**Description:** Core workflows, highest visibility, most color usage

10 routes. These are the "faces" of the application.

### 🟠 P2 (High) — Ship Second
**Effort:** 2-3 days  
**User Impact:** High  
**Description:** Common pages, secondary workflows, moderate color usage

20 routes. User hits these daily.

### 🟡 P3 (Medium) — Ship Third
**Effort:** 2-3 days  
**User Impact:** Medium  
**Description:** Less common pages, admin/settings, minimal color impact

15 routes. Occasional use or background functionality.

### 🟢 P4 (Low) — Polish Last
**Effort:** 1-2 days  
**User Impact:** Low  
**Description:** Rare pages, error states, modals, edge cases

10+ routes. Rarely seen, but must still look professional.

---

## P1: CRITICAL (Highest Priority)

### 1. Dashboard `/dashboard`
**User Impact:** Every session starts here  
**Color Usage:** Heavy (stat cards, charts, badges)  
**Complexity:** High (status colors, success/warning/danger)

**Current Colors:**
- Primary CTA buttons: `#2563EB` → `#1A3A52`
- Stat card icons: `#EFF6FF` bg, `#1E40AF` text → `#F0F4F8` bg, `#092033` text
- Status badges: Multiple semantic colors on stat cards
- Chart colors (if any): Should NOT use primary, use categorical palette

**Migration Work:**
- [ ] Update stat card icon backgrounds from `#EFF6FF` to `#F0F4F8`
- [ ] Update stat card icon foreground colors to new semantic palette
- [ ] Update CTA buttons on dashboard: "Create", "Export", etc.
- [ ] Update status badge colors (success/warning/danger/info)
- [ ] Verify focus rings on card hover states
- [ ] Test in light AND dark mode

**Estimated Effort:** 4-6 hours

---

### 2. License Ledger `/licenses`
**User Impact:** Most-visited page  
**Color Usage:** Heavy (table status colors, filter badges, entity cards)  
**Complexity:** Very High (complex table with 20+ status combinations)

**Current Colors:**
- Table header: `#F5F6FA` bg → `#FAFBFC`
- Row hover: Uses primary color → Update to new primary
- Status badges: Green/yellow/red/blue → New semantic palette
- Filter pills: Primary color borders
- Entity cards: Left border in primary → Update to new primary
- Links: `#2563EB` → `#1A3A52`

**Migration Work:**
- [ ] Update table header background color
- [ ] Update row hover background to use new primary tint
- [ ] Update all status badge colors (Licensed, Pending, Expired, etc.)
- [ ] Update filter pill styles (background, border, text)
- [ ] Update entity card left borders
- [ ] Update link colors
- [ ] Verify focus rings on table rows
- [ ] Test with 20+ items in different states (not chaotic?)
- [ ] Test in dark mode (text still readable?)

**Estimated Effort:** 6-8 hours

---

### 3. Allotment Actions `/allotments/:id/actions`
**User Impact:** Core workflow  
**Color Usage:** Heavy (status colors, form validation, action buttons)  
**Complexity:** High (allocation states, validation states)

**Current Colors:**
- Primary button (Allocate): `#2563EB` → `#1A3A52`
- Success badge (Allocated): Green → New forest green
- Warning badge (Pending): Yellow → New amber
- Danger badge (Insufficient): Red → New crimson
- Form validation: Red borders, red text → New danger colors
- Focus rings: Blue → Navy

**Migration Work:**
- [ ] Update "Allocate" button color
- [ ] Update status badges (Allocated, Pending, Insufficient, etc.)
- [ ] Update validation error colors
- [ ] Update form input focus rings
- [ ] Update action card borders
- [ ] Test allocation success flow (colors support user confidence?)
- [ ] Test validation errors (clear and readable?)

**Estimated Effort:** 4-6 hours

---

### 4. Bill of Entry (`/bill-of-entries`)
**User Impact:** Core workflow  
**Color Usage:** Heavy (entity cards, status colors, table data)  
**Complexity:** Very High (nested data structure, multiple status levels)

**Current Colors:**
- Entity cards: Left border + tone colors
- Status indicators: Multiple semantic colors
- Table status colors: Good/warning/error states
- Primary buttons: Create, Import, etc.

**Migration Work:**
- [ ] Update entity card tone colors (primary, secondary, success, warning, danger)
- [ ] Update table status colors
- [ ] Update all primary buttons
- [ ] Update validation states
- [ ] Test nested data rendering (clear hierarchy?)
- [ ] Test dark mode (borders visible?)

**Estimated Effort:** 6-8 hours

---

### 5. License Ledger Detail `/licenses/:id`
**User Impact:** Heavy use  
**Color Usage:** Moderate-Heavy (detail table, status sections)  
**Complexity:** High (multi-section layout, status indicators)

**Current Colors:**
- Detail table headers: Primary color
- Status sections: Toned backgrounds
- Action buttons: Primary color
- Status badges: Semantic colors

**Migration Work:**
- [ ] Update detail table header colors
- [ ] Update status section backgrounds
- [ ] Update action buttons
- [ ] Update badges and status indicators
- [ ] Verify section visual hierarchy
- [ ] Test focus states on detail table

**Estimated Effort:** 4-6 hours

---

### 6. Trade Form `/trades/:id`
**User Impact:** Core workflow for trade operations  
**Color Usage:** Moderate (form validation, action buttons)  
**Complexity:** Medium (form states, validation)

**Current Colors:**
- Submit button: `#2563EB` → `#1A3A52`
- Form validation: Red borders/text → New danger
- Form focus rings: Blue → Navy
- Status badges: Multiple semantic colors

**Migration Work:**
- [ ] Update submit/save button colors
- [ ] Update validation error styling
- [ ] Update form focus rings
- [ ] Update any status badges on form
- [ ] Test form submission flow
- [ ] Test validation error visibility

**Estimated Effort:** 3-4 hours

---

### 7. Reconciliation Panel `/reconciliation`
**User Impact:** Critical operational page  
**Color Usage:** Heavy (status indicators, issue badges)  
**Complexity:** Very High (multiple status types, warnings)

**Current Colors:**
- Issue badges: Red/yellow/blue
- Status indicators: Semantic colors
- Action buttons: Primary color
- Match/mismatch indicators: Green/red

**Migration Work:**
- [ ] Update all issue type badges
- [ ] Update match/mismatch colors
- [ ] Update status indicators
- [ ] Update action buttons
- [ ] Test issue visualization (clear?)
- [ ] Test in dark mode

**Estimated Effort:** 5-7 hours

---

### 8. Admin Users Page `/admin/users`
**User Impact:** Admin workflow  
**Color Usage:** Moderate (action buttons, status badges)  
**Complexity:** Medium (user list, role indicators)

**Current Colors:**
- Primary buttons: Invite, Add, etc.
- Role badges: Status colors
- Action buttons: Delete (danger), Edit (primary)

**Migration Work:**
- [ ] Update primary buttons
- [ ] Update role/status badges
- [ ] Update danger delete buttons
- [ ] Verify role colors are clear

**Estimated Effort:** 3-4 hours

---

### 9. Ledger Upload `/ledger-upload`
**User Impact:** Data import workflow  
**Color Usage:** Moderate (form, validation, progress)  
**Complexity:** Medium (multi-step, validation states)

**Current Colors:**
- Upload button: Primary color
- Validation states: Red for error, green for success
- Progress indicator: Primary color

**Migration Work:**
- [ ] Update upload button colors
- [ ] Update validation state colors
- [ ] Update progress indicator colors
- [ ] Test upload flow visibility

**Estimated Effort:** 2-3 hours

---

### 10. Settings Page `/settings`
**User Impact:** User settings  
**Color Usage:** Light (toggle switches, save button)  
**Complexity:** Low (mostly forms)

**Current Colors:**
- Toggle switches: Primary color when on
- Save button: Primary color
- Validation: Red for error

**Migration Work:**
- [ ] Update toggle switch colors
- [ ] Update save button color
- [ ] Update validation colors

**Estimated Effort:** 2-3 hours

---

## P2: HIGH PRIORITY

### 11-30. Secondary Pages

**Routes:**
```
11. Planning Workspace — /planning
12. License Download Requests — /licenses/download-requests
13. License Download Request Detail — /licenses/download-requests/:id
14. License Package Readiness — /licenses/:id/readiness
15. Profile — /profile
16. Password Reset — /auth/password-reset
17. BOE Transfer Letter — /bill-of-entries/:id/transfer-letter
18. Trade Transfer Letter — /trades/:id/transfer-letter
19. Allotment Filters — /allotments/filters
20. Allotment List — /allotments
21. Trade List — /trades (if exists)
22. Reconciliation Issues — /reconciliation/issues
23. Reconciliation Audit Log — /reconciliation/audit-log
24. Reconciliation Comparison — /reconciliation/comparison
25. Reconciliation Multi-Link Tab — /reconciliation/multi-link
26. Reconciliation Duplicate BOEs — /reconciliation/duplicates/boe
27. Reconciliation Missing Invoice — /reconciliation/missing/invoice
28. Reconciliation Missing BOE — /reconciliation/missing/boe
29. Reconciliation Duplicate Debits — /reconciliation/duplicates/debits
30. MDS Status Card — /settings/mds-status
```

**Common Pattern:**
- Primary buttons: Update to navy
- Status colors: Update to new semantic palette
- Links: Update to navy
- Focus rings: Update to navy

**Estimated Effort (Total):** 8-12 hours

---

## P3: MEDIUM PRIORITY

### 31-45. Admin & Settings Pages

**Routes:**
```
31. Activity Log — /admin/activity-log
32. User Form — /admin/users/create or /admin/users/:id/edit
33. User List — /admin/users (separate page)
34. MDS Status — /settings/mds-status
35. Forbidden Page — /403
36. Login Page — /auth/login
37. Logout Handler — /auth/logout
38. Profile Edit — /profile/edit
39. PDFViewer — /files/:id or similar
40. LicenseDownloadRequests Detail — /licenses/download-requests/:id
41. Allotment Filters Modal — Modal component
42. Trade Config Card — Component in trade page
43. Empty State Fallback — Various routes
44. Error State Fallback — Various routes
45. Loading Skeleton — Various routes
```

**Common Pattern:**
- Admin pages: Mostly form colors, less color usage
- Auth pages: Simple form + button colors
- Error/Empty states: Icon colors, text colors
- Modals: Focus on contrast and visibility

**Estimated Effort (Total):** 6-8 hours

---

## P4: LOW PRIORITY (Polish)

### 46-51+. Edge Cases & Modals

**Routes/Components:**
```
46. Command Palette — Floating search
47. Toast Notifications — Toast styles
48. Dropdown Menus — Menu item hover, active
49. Tooltips — Background, text colors
50. Modal Backdrops — Overlay colors
51. Focus Rings — All interactive elements
52. Disabled States — Opacity, text color
53. Loading States — Skeleton colors
54. Error Dialogs — Dialog colors, error icons
55. Success Dialogs — Dialog colors, success icons
```

**Common Pattern:**
- Minor visual elements
- Usually inherit from primary component colors
- Low user impact

**Estimated Effort (Total):** 2-3 hours

---

## Migration Strategy by Phase

### Phase 1: Foundation (Day 1)
- Update CSS variables in `tabler.css`
- NO visual changes yet
- Build succeeds with new hex values
- **Git Commit:** "chore(colors): update design system V2 tokens"

### Phase 2A: P1 Pages (Days 2-3)
- Migrate critical pages (1-10)
- Daily visual review
- QA spot-checks each page
- Dark mode testing at end of day
- **Git Commits:** One per major page group

### Phase 2B: P2-P3 Pages (Days 4-5)
- Migrate secondary pages (11-45)
- Less intensive testing (patterns are clear)
- Focus on edge cases
- **Git Commits:** Grouped by feature area

### Phase 3: P4 + Polish (Days 6-7)
- Migrate edge cases (46-51+)
- Full accessibility pass
- Full dark mode pass
- Color-blind simulation
- **Git Commit:** "chore(colors): complete design system V2 migration"

### Phase 4: QA & Regression (Days 8-10)
- E2E test suite (ensure no regressions)
- Visual regression testing
- Browser compatibility check
- User feedback collection
- **Status:** Ready to ship

---

## Per-Page Checklist Template

Use this for each page:

```
Route: /path/to/page
Priority: P1/P2/P3/P4
Components: List of main components
Colors to Update:
  - [ ] Primary button: #2563EB → #1A3A52
  - [ ] Status badges: Check all types
  - [ ] Text links: #2563EB → #1A3A52
  - [ ] Focus rings: Update color
  - [ ] Borders: Update color
Accessibility:
  - [ ] Contrast check (WCAG AA)
  - [ ] Focus ring visible
  - [ ] Dark mode tested
Dark Mode:
  - [ ] Colors visible
  - [ ] Text readable
  - [ ] Borders visible
QA:
  - [ ] Light mode approved
  - [ ] Dark mode approved
  - [ ] Color-blind simulation passed
Status: Not Started / In Progress / QA Approved / ✅ Complete
```

---

## Dependency Graph (What to Update When)

### Foundation Level (Must Do First)
```
tabler.css
  ↓
Component CSS files (buttons, badges, cards, etc.)
  ↓
Page-specific overrides (if any)
```

### Testing Level (Do in Parallel)
```
Light mode testing
  ↓
Dark mode testing (wait for light mode done)
  ↓
Accessibility testing (ongoing)
```

### QA Level (After Code)
```
Visual regression
  ↓
E2E testing
  ↓
User acceptance
```

---

## Risk Areas (Monitor Closely)

### ❌ High Risk
- **Table status colors:** Complex combinations, must look professional
- **Badge colors:** Multiple semantic meanings, must be clear
- **Dark mode contrast:** Can easily become unreadable

### ⚠️ Medium Risk
- **Form validation:** Red colors must be clear but not aggressive
- **Focus rings:** Must be visible on all backgrounds
- **Navigation active states:** Must be clearly distinguished

### ✓ Low Risk
- **Simple buttons:** One color per button type
- **Text links:** Simple color change
- **Icons:** Usually inherit from text color

---

## Rollback Plan

If colors look wrong:

1. **Revert CSS file:** `git checkout -- frontend/src/theme/tabler.css`
2. **Rebuild:** `npm run build`
3. **Restart dev server:** `npm run dev`
4. **Verify:** Old colors are back

Or, cherry-pick specific color changes:

```bash
git revert <commit-hash>
```

---

## Success Criteria (Per Page)

### Visual Quality
- [ ] Looks professional and authoritative
- [ ] No color clashing
- [ ] Status colors are clear without being chaotic
- [ ] Designer approves: "Looks good"

### Accessibility
- [ ] WCAG AA contrast on all text
- [ ] Focus rings visible
- [ ] Works in color-blind mode
- [ ] Works in dark mode

### Functionality
- [ ] No broken links or buttons
- [ ] No JavaScript errors in console
- [ ] Same interaction model as before
- [ ] QA approves: "No regressions"

---

## Timeline & Ownership

| Phase | Dates | Owner | Status |
|-------|-------|-------|--------|
| Foundation | Day 1 | Frontend-engineer | Ready to start |
| P1 Pages | Days 2-3 | Frontend-engineer | Ready to start |
| P2-P3 Pages | Days 4-5 | Frontend-engineer | Queued |
| P4 Polish | Days 6-7 | Frontend-engineer | Queued |
| QA & Regression | Days 8-10 | QA-test-engineer | Queued |

---

## Notes

- **Total Routes:** 51+ (includes pages, modals, components)
- **Estimated Effort:** 7-10 days
- **Parallel Work:** Designer can start on next feature while engineering implements
- **Testing Strategy:** Spot-check daily, full regression at end
- **Risk Level:** Low-Medium (no behavior changes, only CSS colors)

---

**Document Status:** Ready for Implementation  
**Owner:** Frontend-engineer + QA-test-engineer  
**Next Action:** Begin Phase 1 (Foundation) on Day 1
