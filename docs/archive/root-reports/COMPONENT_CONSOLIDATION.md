# Component Consolidation & Design System Strategy

**Date**: 2026-09-18  
**Phase**: Phase 1 of UI Modernization

---

## CURRENT STATE ANALYSIS

### shadcn/ui Components (CANONICAL - Keep & Enhance)
- **button.tsx** (54 uses) ✓ Primary button implementation
- **card.tsx** (32 uses) ✓ Primary card container
- **input.tsx** (19 uses) ✓ Text input
- **select.tsx** (multiple uses) ✓ Select dropdown
- **badge.tsx** (25 uses) ✓ Status/label badge
- **checkbox.tsx**, **switch.tsx**, **tabs.tsx**, **dialog.tsx** ✓ All in use
- **skeleton.tsx** (11 uses) ✓ Loading skeleton
- **Other**: alert, label, separator, textarea, tooltip, dropdown-menu (all used appropriately)

**Status**: ✅ These are the source of truth for base UI components

### Custom Compound Components (ACTIVE - High Value)
- **PageHeader.tsx** (main/components) — Page structure
- **StatCard.tsx** (main/components) — KPI display
- **DataTable.tsx** (main/components) — Complex data tables
- **EmptyState.tsx** (main/components) — Empty state display
- **LoadingFallback.tsx** (main/components) — Loading states
- **FormField.tsx** (main/components) — Form field wrapper
- **PermissionGate.tsx** (main/components) — Authorization wrapper
- **Other components**: TaskDrawer, CommandPalette, ConfirmDialog, etc.

**Status**: ✅ These are application-specific and actively used

### Custom Primitives (UNUSED - Consolidation Candidates)

| Component | Uses | Status | Action |
|-----------|------|--------|--------|
| primitives/Button.tsx | 0 | Unused | ❌ Remove (shadcn/ui/button is canonical) |
| primitives/Card.tsx | 0 | Unused | ❌ Remove (shadcn/ui/card is canonical) |
| primitives/Skeleton.tsx | 0 | Unused | ❌ Remove (shadcn/ui/skeleton is canonical) |
| primitives/DetailTable.tsx | 3 | Minimal | ⚠️ Audit usage, likely remove |
| primitives/EntityCard.tsx | 3 | Minimal | ⚠️ Audit usage, likely consolidate |
| primitives/EmptyState.tsx | 0 | Unused | ❌ Remove (main/components/EmptyState used instead) |
| primitives/FilterBar.tsx | 0 | Unused | ⚠️ Review - should be created in main/components |
| primitives/IconChip.tsx | 0 | Unused | ❌ Remove |
| primitives/PageHeader.tsx | 0 | Unused | ❌ Remove (main/components/PageHeader used instead) |
| primitives/SectionHeader.tsx | 0 | Unused | ❌ Remove |
| primitives/StatusBadge.tsx | 0 | Unused | ❌ Remove |
| primitives/Surface.tsx | 0 | Unused | ❌ Remove |
| primitives/StatCard.tsx | 0 | Unused | ❌ Remove (main/components/StatCard used instead) |
| primitives/Toolbar.tsx | 0 | Unused | ❌ Remove |

**Status**: ❌ Most are unused duplicates of better implementations elsewhere

---

## CONSOLIDATION STRATEGY

### What We're Doing
1. **Keep shadcn/ui** as the canonical source for base primitives
2. **Keep custom compounds** in `components/` (top level) as application-specific components
3. **Delete unused primitives directory** (consolidate into single directory)
4. **Create cleaner component hierarchy**

### Component Hierarchy (Post-Consolidation)

```
frontend/src/components/
├── ui/                          (shadcn/ui - base primitives)
│   ├── button.tsx
│   ├── card.tsx
│   ├── input.tsx
│   ├── select.tsx
│   ├── badge.tsx
│   ├── dialog.tsx
│   ├── tabs.tsx
│   ├── checkbox.tsx
│   ├── switch.tsx
│   ├── skeleton.tsx
│   └── [etc.]
│
├── compound/                     (NEW: Complex composites built from ui/)
│   ├── PageHeader.tsx           (Keep as-is, improve styling)
│   ├── StatCard.tsx             (Keep as-is, improve styling)
│   ├── DataTable.tsx            (Keep as-is, enhance)
│   ├── FilterBar.tsx            (Consolidate/improve)
│   ├── EmptyState.tsx           (Keep as-is, improve)
│   ├── LoadingFallback.tsx       (Keep as-is)
│   ├── FormField.tsx            (Keep as-is)
│   └── [etc.]
│
├── (top-level custom components)
│   ├── TopNav.tsx
│   ├── Sidebar.tsx
│   ├── TaskDrawer.tsx
│   ├── CommandPalette.tsx
│   ├── ConfirmDialog.tsx
│   └── [etc.]
│
└── (DELETE)
    └── primitives/              (REMOVE - unused duplicates)
```

### Files to Delete
```
frontend/src/components/primitives/Button.tsx
frontend/src/components/primitives/Card.tsx
frontend/src/components/primitives/Skeleton.tsx
frontend/src/components/primitives/DetailTable.tsx
frontend/src/components/primitives/EmptyState.tsx
frontend/src/components/primitives/EntityCard.tsx
frontend/src/components/primitives/FilterBar.tsx
frontend/src/components/primitives/IconChip.tsx
frontend/src/components/primitives/PageHeader.tsx
frontend/src/components/primitives/SectionHeader.tsx
frontend/src/components/primitives/StatusBadge.tsx
frontend/src/components/primitives/Surface.tsx
frontend/src/components/primitives/StatCard.tsx
frontend/src/components/primitives/Toolbar.tsx
```

### Files to Relocate (if kept)
- DetailTable.tsx → check usage, either delete or move to compound/
- EntityCard.tsx → check usage, either delete or move to compound/

---

## DESIGN TOKENS CONSOLIDATION

### Current State
- **tokens.js**: Defines tone maps (TONE_MAP, CHIP_TONE_MAP, ACTION_TONE_MAP) and spacing scale
- **tabler.css**: Defines CSS variables for colors, typography, spacing, shadows, etc.

### Action Items
1. ✓ Keep both files (they complement each other)
2. Create **component-specific token usage guide**
3. Document which tone maps to use in which contexts
4. Create **typography scale documentation**
5. Create **spacing scale documentation**
6. Add **color palette reference** with usage rules

---

## BUTTON VARIANT MATRIX

### Current shadcn/ui Button
- variant: solid (default), outline, ghost, secondary, destructive, link
- size: default, sm, lg
- status: default, disabled, loading

### Enhancements Needed
- [ ] Add "subtle" variant (for secondary actions in cards)
- [ ] Add consistent icon support (icon + text combos)
- [ ] Improve loading state styling
- [ ] Better disabled state contrast
- [ ] Consistent sizing alignment

### Usage Rules
- **Primary Action**: solid, brand color
- **Secondary Action**: outline or ghost
- **Destructive**: destructive variant (red)
- **Tertiary**: ghost (in cards, toolbars)

---

## FORM COMPONENTS CONSOLIDATION

### Current FormField.tsx
- Wraps input with label, error, help text
- Good implementation, needs styling enhancements

### Needed Additions
- FormSelect wrapper
- FormTextarea wrapper
- FormCheckbox wrapper
- Form grouping patterns
- Better spacing

---

## NEXT STEPS

1. ✅ Analyze component usage (DONE)
2. ⏭️ Delete unused primitives
3. ⏭️ Create compound/ directory and reorganize
4. ⏭️ Update all imports (if reorganizing)
5. ⏭️ Create component documentation
6. ⏭️ Enhance base UI components' styling
7. ⏭️ Document design token usage

---

**Prepared**: 2026-09-18  
**Phase**: Phase 1  
**Owner**: Frontend Modernization
