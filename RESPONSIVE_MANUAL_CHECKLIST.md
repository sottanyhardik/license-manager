# Responsive Design - Manual Testing Checklist
**Branch:** hotfix/ui-consistency-2026-09-25

## Dashboard (PRIORITY: P0)
### Desktop 1440×900
- [ ] Page header "Dashboard" is properly formatted
- [ ] Stat cards (Licence health) display in 5-column grid
- [ ] "Operational activity" stat cards display in 3-column grid
- [ ] Attention card (expiring licenses) is readable
- [ ] BOE trend chart is visible and readable
- [ ] Recent BOE table displays with all columns visible
- [ ] Recent allotments table displays properly
- [ ] No horizontal scrolling on page
- [ ] Spacing between sections is consistent (space-y-6)
- [ ] All buttons are clickable (Refresh, New Allotment, New BOE)

### Tablet 768×1024
- [ ] All stat cards are visible (may wrap to 2-3 columns)
- [ ] Attention card content is scrollable if needed
- [ ] Charts are sized appropriately
- [ ] Text is not clipped or truncated
- [ ] Buttons stack or remain side-by-side appropriately
- [ ] No horizontal scrolling

### Mobile 390×844
- [ ] Stat cards stack to 2-column layout
- [ ] Attention section is readable
- [ ] Charts are readable (may need zoom)
- [ ] All content is accessible
- [ ] No horizontal scrolling
- [ ] Buttons are touch-friendly (minimum 44px height)

---

## Item Pivot Report (PRIORITY: P0 - Recently refactored)
### Desktop 1440×900
- [ ] PageHeader displays with proper breadcrumb
- [ ] Title "Item Pivot Report" is visible
- [ ] Description shows report date and active norm
- [ ] Filter button is visible in header
- [ ] Update Balance button is visible
- [ ] Excel export button is visible
- [ ] Header doesn't overlap content
- [ ] No horizontal scrolling
- [ ] Filter panel can be shown/hidden

### Tablet 1024×768
- [ ] PageHeader is compact but readable
- [ ] Action buttons may stack vertically
- [ ] Filter content is accessible
- [ ] Main table/content is scrollable if needed
- [ ] Header is sticky at top

### Mobile 390×844
- [ ] PageHeader is minimal but readable
- [ ] Breadcrumb is visible (may wrap)
- [ ] Action buttons stack vertically
- [ ] "Show/Hide" button works
- [ ] Filter panel stacks below header
- [ ] Main content is scrollable
- [ ] No horizontal scrolling

---

## License Master List (PRIORITY: P1)
### Desktop 1440×900
- [ ] Filter panel is visible on left
- [ ] Table columns are all visible
- [ ] Pagination controls are visible
- [ ] Search/filter boxes are functional
- [ ] No horizontal scrolling of page

### Tablet 1024×768
- [ ] Filters may be collapsed or reduced
- [ ] Table can scroll horizontally (OK) but page doesn't
- [ ] Filter toggleable or accessible

### Mobile 390×844
- [ ] Filter panel is hidden or stacked
- [ ] Table is in a scrollable container
- [ ] Search/filter is accessible
- [ ] List items are readable
- [ ] No page-level horizontal scroll

---

## Forms (MasterForm, TradeForm) (PRIORITY: P1)
### Desktop 1440×900
- [ ] All input fields are visible
- [ ] Labels are clear
- [ ] Validation messages are visible
- [ ] Submit buttons are visible
- [ ] No horizontal scrolling

### Tablet 768×1024
- [ ] Form fields stack properly
- [ ] Labels and inputs are aligned
- [ ] Buttons are accessible
- [ ] No horizontal scrolling

### Mobile 390×844
- [ ] Form fields are full width or appropriately sized
- [ ] Labels are above or beside inputs (readable)
- [ ] Inputs are large enough to interact with
- [ ] Buttons are full width or stacked
- [ ] No horizontal scrolling

---

## Reports (Item Report, SION Reports) (PRIORITY: P1)
### Desktop 1440×900
- [ ] Header displays properly
- [ ] Content/tables are visible
- [ ] All columns are visible (table may be wide)
- [ ] Charts display correctly

### Tablet 1024×768
- [ ] Header is readable
- [ ] Content is accessible
- [ ] Horizontal scroll OK for tables, but not for page

### Mobile 390×844
- [ ] Header is readable
- [ ] Content is in a scrollable container
- [ ] Tables are scrollable
- [ ] No page-level horizontal scroll
- [ ] Critical information is visible first

---

## Navigation & Layout (ALL PAGES) (PRIORITY: P0)
### Desktop
- [ ] Sidebar/nav is visible
- [ ] Main content area has proper margins
- [ ] No horizontal scrolling

### Tablet
- [ ] Nav may be collapsed or hamburger menu
- [ ] Main content area is properly sized
- [ ] Touch targets are large enough (44px)

### Mobile
- [ ] Nav is in hamburger menu or bottom nav
- [ ] Content is full width with proper padding
- [ ] No horizontal scrolling
- [ ] Bottom nav doesn't overlap content

---

## Spacing Consistency (NEW: From hotfix changes) (PRIORITY: P1)
- [ ] Section spacing is consistent (space-y-4 or space-y-6)
- [ ] Title-description spacing is uniform (space-y-1)
- [ ] Card padding is consistent
- [ ] Button spacing is uniform
- [ ] Visual hierarchy is clear (h2 text-lg)

---

## Testing Results Summary
| Page | Desktop | Tablet | Mobile | Status |
|------|---------|--------|--------|--------|
| Dashboard | [ ] | [ ] | [ ] | Pending |
| Item Pivot Report | [ ] | [ ] | [ ] | Pending |
| License List | [ ] | [ ] | [ ] | Pending |
| Trades List | [ ] | [ ] | [ ] | Pending |
| Reports | [ ] | [ ] | [ ] | Pending |
| Forms | [ ] | [ ] | [ ] | Pending |
| Navigation | [ ] | [ ] | [ ] | Pending |
| Spacing | [ ] | [ ] | [ ] | Pending |

---

## Issues Found
### Critical (P0)
- [ ] [To be filled during testing]

### High (P1)
- [ ] [To be filled during testing]

### Medium (P2)
- [ ] [To be filled during testing]

---

**Last Updated:** Ready for manual testing  
**Tester:** Responsive Design Specialist  
**Date:** 2026-09-25
