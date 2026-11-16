# Responsive Design Testing Plan
**Hotfix Branch:** hotfix/ui-consistency-2026-09-25  
**Dev Server:** http://localhost:5175/  
**Testing Date:** 2026-09-25

## Viewport Sizes to Test
1. **1440×900** - Desktop, full width
2. **1366×768** - Desktop, common
3. **1024×768** - Tablet landscape
4. **768×1024** - Tablet portrait
5. **390×844** - Mobile (iPhone 12/13)

## High-Priority Routes to Test
- `/` - Dashboard/Home
- `/licenses` - License Master List
- `/licenses/:id` - License Detail
- `/trades` - Trade Master List
- `/trades/:id` - Trade Detail
- `/reports/item-pivot` - Item Pivot Report (recent fix)
- `/reports/monthly` - Monthly Report
- `/settings` - Settings

## Testing Checklist per Route
- [ ] No horizontal overflow at any breakpoint
- [ ] Text not clipped or truncated unexpectedly
- [ ] Buttons not cut off or unclickable
- [ ] Filters stack appropriately on mobile
- [ ] Tables scroll horizontally on mobile (with proper scroll area)
- [ ] Spacing adapts appropriately to screen size
- [ ] Empty states scale properly
- [ ] Cards/panels stack at mobile width
- [ ] Bottom navigation/footer doesn't overlap content
- [ ] Forms are usable on all sizes

## Testing Status
- [ ] Phase 1: Setup complete
- [ ] Phase 2: Responsive testing underway
- [ ] Phase 3: Regression testing complete
- [ ] Phase 4: Visual comparisons done
- [ ] Phase 5: Final sweep complete

---
