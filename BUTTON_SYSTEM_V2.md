# Button System V2

**Status:** Design Specification (Implementation pending)  
**Date:** 2026-09-25  
**Designer:** Product Design (25yr enterprise SPA specialist)

---

## Overview

The Button System defines a professional, accessible set of button variants used throughout the License Manager SPA. Buttons follow enterprise design patterns: clear visual hierarchy, precise sizing on a 4pt grid, professional interaction states, and full WCAG AA accessibility.

All buttons are built with **shadcn/ui Button component** and driven by **Tabler CSS tokens** (via theme/tokens.js).

---

## Sizing Scale

Buttons follow the operational density contract defined in `--tb-control-*` tokens:

| Size | Height | Use Case | Padding (horizontal) |
|------|--------|----------|----------------------|
| **Compact Small** | 32px | Dense tables, inline actions, mobile | 8px |
| **Compact** | 36px | Form fields, list actions, modals | 12px |
| **Normal** | 40px | Page-level actions, primary CTAs | 16px |
| **Large** | 44px | Hero CTAs, page headers | 20px |

**Gap between icon + text:** 8px (compact) / 10px (normal/large)

---

## Button Variants

### 1. Primary
**Purpose:** Main call-to-action; highest visual emphasis.

```
default = Primary
```

**States:**
- **Default:** `bg-primary text-primary-foreground` + subtle shadow
- **Hover:** Darker shade (`bg-primary/90` or `--tb-brand-hover`), lift shadow
- **Active:** `active:scale-95` (press feedback)
- **Disabled:** `opacity-50 cursor-not-allowed`
- **Focus:** `focus-visible:ring-[3px] focus-visible:ring-ring/40`
- **Loading:** Spinner icon, text → "..." or skeleton

**Tokens:**
- Background: `--tb-brand` (#2563EB)
- Hover: `--tb-brand-hover` (#1D4ED8)
- Text: white/primary-foreground
- Border: none (solid fill)

---

### 2. Secondary
**Purpose:** Supporting actions; lower visual weight than Primary.

**States:**
- **Default:** `bg-secondary text-secondary-foreground` + shadow
- **Hover:** `bg-secondary/80` + lift shadow
- **Active:** `active:scale-95`
- **Disabled:** `opacity-50`
- **Focus:** `focus-visible:ring-[3px] focus-visible:ring-ring/40`

**Tokens:**
- Background: `--tb-sunken` (#F8F9FB) or neutral-soft
- Border: `--tb-border` (#E4E7EC)
- Text: `--tb-text-secondary` (#5E6673)

---

### 3. Tertiary
**Purpose:** Low-emphasis actions; often used in lists, tables, secondary positions.

```
variant="ghost"
```

**States:**
- **Default:** Transparent background, text color
- **Hover:** `hover:bg-accent hover:text-accent-foreground`
- **Active:** `active:scale-95`
- **Disabled:** `opacity-50`
- **Focus:** `focus-visible:ring-[3px] focus-visible:ring-ring/40`

**Tokens:**
- Background: transparent
- Hover: `--tb-sunken` (#F8F9FB)
- Text: `--tb-text-secondary` (#5E6673)
- Border: none

---

### 4. Outline
**Purpose:** Secondary actions with equal emphasis to Primary; often paired with Primary.

```
variant="outline"
```

**States:**
- **Default:** `border-input bg-card` + subtle shadow
- **Hover:** `hover:bg-accent hover:shadow`
- **Active:** `active:scale-95`
- **Disabled:** `opacity-50`
- **Focus:** `focus-visible:ring-[3px] focus-visible:ring-ring/40`

**Tokens:**
- Background: `--tb-card-bg` (white)
- Border: `--tb-border` (#E4E7EC)
- Text: `--tb-text` (#111827)
- Hover BG: `--tb-sunken` (#F8F9FB)

---

### 5. Ghost
**Purpose:** Minimal, transparent actions; used extensively in menus, toolbars.

```
variant="ghost"
```

**States:**
- **Default:** Transparent, text only
- **Hover:** Subtle background, text emphasize
- **Active:** `active:scale-95`
- **Disabled:** `opacity-50`
- **Focus:** `focus-visible:ring-[3px] focus-visible:ring-ring/40`

**Tokens:**
- Background: transparent
- Hover: `--tb-sunken` + text emphasis

---

### 6. Danger / Destructive
**Purpose:** Destructive actions (delete, remove); warns user of irreversible action.

```
variant="destructive"
```

**States:**
- **Default:** `bg-destructive text-destructive-foreground` + shadow
- **Hover:** `bg-destructive/80` or `bg-destructive/90` + lift shadow
- **Active:** `active:scale-95`
- **Disabled:** `opacity-50`
- **Focus:** `focus-visible:ring-[3px] focus-visible:ring-destructive/40`

**Tokens:**
- Background: `--tb-danger` (#DC2626)
- Hover: `--tb-danger-hover` or `/80` variant
- Text: white
- Border: none

---

### 7. Success
**Purpose:** Positive action confirmation, approval, acceptance.

```
variant="success" (new variant to add)
```

**States:**
- **Default:** `bg-success text-success-foreground` + shadow
- **Hover:** `bg-success/80` + lift shadow
- **Active:** `active:scale-95`
- **Disabled:** `opacity-50`
- **Focus:** `focus-visible:ring-[3px] focus-visible:ring-success/40`

**Tokens:**
- Background: `--tb-success` (#16A34A)
- Text: white
- Border: none

---

### 8. Icon Button
**Purpose:** Standalone icons, no text; used in toolbars, header actions, close buttons.

```
size="icon"
```

**Size:** 40px (default), 36px (compact), 32px (compact-small)

**States:**
- Same as Primary/Secondary/Ghost depending on variant
- Icon size: 20px (default), 16px (compact), 14px (compact-small)
- Icon centering: `inline-flex items-center justify-center`

---

### 9. Split Button
**Purpose:** Primary action + menu; button + dropdown separator.

```
// Example structure:
<div className="inline-flex gap-px rounded-lg border border-border overflow-hidden">
  <Button variant="default" size="default" className="rounded-r-none">Action</Button>
  <DropdownMenu>
    <DropdownMenuTrigger asChild>
      <Button variant="default" size="icon" className="rounded-l-none"><ChevronDown /></Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent>...</DropdownMenuContent>
  </DropdownMenu>
</div>
```

---

## Loading State

When a button is performing an async action:

```tsx
<Button disabled={isLoading}>
  {isLoading ? (
    <>
      <Loader2 className="size-4 animate-spin" />
      Saving...
    </>
  ) : (
    <>
      <Save className="size-4" />
      Save
    </>
  )}
</Button>
```

**Visual Treatment:**
- Replace icon with spinner (lucide-react: `Loader2`)
- Text changes to action descriptor ("Saving...", "Uploading...")
- Button disabled to prevent double-click
- Spinner uses `animate-spin` with `motion-reduce:animate-none` for a11y

---

## Interaction States

### Focus Ring
- **Ring width:** 3px
- **Ring color:** `--tb-ring` at 40% opacity
- **Offset:** 2px (built into ring width)
- **Motion:** Instant on focus, fade out on blur (no transition)

### Active Press
- **Scale:** `active:scale-95` (5% reduction)
- **Duration:** ~50ms
- **Motion:** Uses CSS default transition (instant CSS)

### Hover
- **Shadow lift:** Add shadow or increase shadow
- **Border:** Optionally lighten for outline variant
- **Duration:** 200ms transition-all

---

## Icon Usage

**Icons:** lucide-react only (no bootstrap-icons)

**Icon Sizing:**
- Inline with text: 16px (compact), 18px (normal), 20px (large)
- Icon-only buttons: 20px (compact), 22px (normal), 24px (large)
- Apply via `[&_svg:not([class*='size-'])]:size-4` selector in button base

**Icon + Text Spacing:**
- Compact: 6px gap
- Normal: 8px gap
- Large: 10px gap

---

## Accessibility (WCAG AA)

### Focus & Navigation
- All buttons have `focus-visible:ring-[3px]` visible focus indicator
- Focus ring is visible on dark and light backgrounds (high contrast)
- Keyboard navigation: Tab to focus, Enter/Space to activate

### Color & Contrast
- All button text/background combos meet WCAG AA (4.5:1 contrast minimum)
- Do not rely solely on color to convey state (icons + text)
- Disabled state uses `opacity-50` but retains text color (not true gray to preserve hue)

### Semantics
- Use `<button>` for actions, not `<a>` (exception: if button is truly a link, use `asChild` to compose with router `<Link>`)
- `disabled` attribute for disabled state (not `aria-disabled`)
- Use `type="button"` to prevent form submission in modals/dialogs

### Loading & Feedback
- Use `aria-busy="true"` when loading
- Loading spinner uses `role="status"` to announce to screen readers
- Provide text change ("Saving...") for context

---

## Component API

```typescript
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 
    | "default"          // Primary (brand blue)
    | "secondary"        // Neutral secondary
    | "tertiary"         // Ghost (transparent)
    | "outline"          // Outlined secondary
    | "ghost"            // Fully transparent
    | "destructive"      // Danger (red)
    | "success"          // Positive (green) — NEW
    | "link";            // Text link
  
  size?: 
    | "compact-small"    // 32px — NEW
    | "compact"          // 36px — NEW
    | "default"          // 40px
    | "lg"               // 44px — rename from "lg"
    | "icon";            // square, size-based
  
  asChild?: boolean;     // Slot composition (e.g., <Link>)
}
```

---

## Common Patterns

### Form Actions (Save/Cancel/Delete)
```tsx
<div className="flex gap-2 justify-end pt-4 border-t">
  <Button variant="ghost" onClick={onCancel}>
    Cancel
  </Button>
  <Button variant="outline" onClick={onDelete}>
    <Trash2 className="size-4" />
    Delete
  </Button>
  <Button onClick={onSave}>
    <Save className="size-4" />
    Save
  </Button>
</div>
```

### Toolbar / Inline Actions
```tsx
<div className="flex gap-1 items-center">
  <Button variant="ghost" size="compact-small">
    <Edit className="size-4" />
  </Button>
  <Button variant="ghost" size="compact-small">
    <Trash2 className="size-4" />
  </Button>
</div>
```

### Page Header CTA
```tsx
<div className="flex justify-between items-center">
  <h1>Allotments</h1>
  <Button size="lg">
    <Plus className="size-5" />
    New Allotment
  </Button>
</div>
```

---

## Migration Path (From Current)

| Current | V2 | Notes |
|---------|----|----|
| `variant="default"` | `variant="default"` | No change |
| `variant="secondary"` | `variant="secondary"` | No change |
| `variant="outline"` | `variant="outline"` | No change |
| `variant="ghost"` | `variant="ghost"` | No change |
| `variant="destructive"` | `variant="destructive"` | No change |
| `size="default"` (h-10) | `size="default"` (h-10=40px) | Explicit mapping |
| `size="sm"` (h-9) | `size="compact"` (36px) | Rename for clarity |
| N/A | `size="compact-small"` | New: 32px for dense UI |
| `size="lg"` (h-11) | `size="lg"` (44px) | Bump to 44px for hero CTAs |
| N/A | `variant="success"` | New: for approval/positive actions |
| N/A | Split button pattern | New: documented |

---

## File Changes

**To implement:**
1. Update `frontend/src/components/ui/button.tsx` with new variants
2. Add size mappings to match token control heights
3. Create `Button.stories.tsx` for Storybook (future)
4. Update all button usages across app (frontend-engineer task)

---

## Token References

- `--tb-brand`: Primary color (#2563EB)
- `--tb-brand-hover`: Hover state (#1D4ED8)
- `--tb-success`: Success color (#16A34A)
- `--tb-danger`: Danger color (#DC2626)
- `--tb-text`: Primary text (#111827)
- `--tb-text-secondary`: Secondary text (#5E6673)
- `--tb-sunken`: Soft background (#F8F9FB)
- `--tb-card-bg`: Card background (white)
- `--tb-border`: Border color (#E4E7EC)
- `--tb-control-sm`: 32px
- `--tb-control-md`: 36px
- `--tb-control-lg`: 40px
- `--tb-r-md`: 8px (button border-radius)

---

## Q&A

**Q: Why no icon-button variant? Instead, use size="icon" with any variant.**
A: Icon buttons are fundamentally buttons that happen to only contain an icon. They inherit variant styling from their parent variant (primary/secondary/ghost). No separate "icon-variant" needed.

**Q: Why 4 button sizes? Isn't 3 enough?**
A: Large (44px) serves hero CTAs and page headers. Normal (40px) for primary form/modal actions. Compact (36px) for form fields and list actions. Compact-Small (32px) for dense tables and toolbars. Each fills a distinct UX niche without overlap.

**Q: What about "Link" variant?**
A: Kept as-is (text-primary underline-offset-4 hover:underline). Use only for in-text links that truly act like links (navigation). For icon-only navigation, use `variant="ghost"`.

**Q: How do I build a loading state?**
A: Disable the button, swap the icon to a spinner (Loader2), and update the text ("Saving..."). See Loading State section for details.

---

**END OF SPECIFICATION**
