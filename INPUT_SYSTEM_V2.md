# Input System V2

**Status:** Design Specification (Implementation pending)  
**Date:** 2026-09-25  
**Designer:** Product Design (25yr enterprise SPA specialist)

---

## Overview

The Input System defines all text, selection, and toggle controls used in the License Manager SPA. All inputs follow the operational density contract (32px, 36px, 40px heights), maintain visual consistency across browsers, and provide clear accessible interaction states.

All inputs are built with **shadcn/ui components** (Input, Select, Checkbox, Switch, Textarea) and driven by **Tabler CSS tokens**.

---

## Input Height Scale

All inputs map to token control heights for consistent rhythm:

| Size | Height | Use Case | Padding (vertical) |
|------|--------|----------|------------------|
| **Compact Small** | 32px | Dense lists, mobile | 4px |
| **Compact** | 36px | Form fields, modals | 6px |
| **Normal** | 40px | Standard forms, primary inputs | 8px |

**Border Radius (all inputs):** `--tb-r-md` (8px) — consistent across all control types.

---

## Text Input

**Component:** `<Input />`

### States

#### Default
```
border border-input bg-card px-3 py-2 h-10 rounded-lg text-sm
```

- **Background:** `--tb-card-bg` (white)
- **Border:** `--tb-border` (#E4E7EC)
- **Text Color:** `--tb-text` (#111827)
- **Padding:** 12px horizontal, 8px vertical
- **Font Size:** 14px (sm via Tailwind)
- **Placeholder:** `--tb-text-tertiary` (#9CA3AF)

#### Hover
```
border-input/80 hover:shadow
```

- **Border:** Slightly darker (`border-input/80`)
- **Shadow:** Subtle shadow (1px blur)
- **Duration:** 200ms transition

#### Focus
```
border-ring focus-visible:ring-ring/30 focus-visible:ring-[3px]
```

- **Border:** Change to `--tb-ring` color
- **Ring:** 3px, 30% opacity
- **Duration:** Instant
- **Outline:** Removed (outline: none)

#### Disabled
```
disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-muted
```

- **Background:** `--tb-muted` (light gray)
- **Opacity:** 50% reduction
- **Cursor:** not-allowed
- **No shadow**

#### Error / Invalid
```
aria-invalid:border-destructive aria-invalid:ring-destructive/30
```

- **Border:** `--tb-danger` (#DC2626)
- **Ring:** Destructive ring when focused
- **Icon:** Use in FormField for visual feedback

#### Readonly
```
data-[state=readonly]:bg-muted data-[state=readonly]:cursor-not-allowed
```

- **Background:** `--tb-muted` (cannot edit)
- **Border:** Retain normal color
- **Cursor:** not-allowed
- **Text:** Retain color (not grayed)

---

## Sizing Variants

### Compact Small (32px)
```tsx
<Input 
  size="compact-small"
  className="h-8 px-2 py-1 text-xs"
/>
```
- Height: 32px
- Padding: 8px horizontal, 4px vertical
- Font: 12px
- Use: Dense lists, mobile forms, toolbars

### Compact (36px)
```tsx
<Input 
  size="compact"
  className="h-9 px-3 py-1.5 text-sm"
/>
```
- Height: 36px
- Padding: 12px horizontal, 6px vertical
- Font: 14px
- Use: Form fields, modals (default for most)

### Normal (40px) — Default
```tsx
<Input />  /* Default */
```
- Height: 40px
- Padding: 12px horizontal, 8px vertical
- Font: 14px
- Use: Primary forms, landing pages

---

## Input Types Supported

| Type | Use | Example |
|------|-----|---------|
| `text` | General text input | Name, description, search |
| `email` | Email validation | User email |
| `password` | Masked password input | Login password |
| `number` | Numeric only | Quantity, price |
| `tel` | Phone numbers | +1-555-0123 |
| `url` | URLs | https://example.com |
| `search` | Search with clear button | DebouncedSearchInput |
| `file` | File upload | Document upload |
| `hidden` | Internal state | Form metadata |

---

## Select Dropdown

**Component:** `<Select>` + `<SelectTrigger>` + `<SelectContent>` + `<SelectItem>`

### SelectTrigger (Closed State)

```
flex items-center justify-between gap-2 rounded-lg border border-input bg-card px-3 py-2 text-sm
h-10 (default) | h-9 (compact) | h-8 (compact-small)
```

- **Layout:** Flex row, space-between (label left, chevron right)
- **Border:** `--tb-border` (#E4E7EC)
- **Background:** `--tb-card-bg` (white)
- **Padding:** 12px horizontal
- **Chevron:** 16px icon, `opacity-60`
- **Text truncation:** `line-clamp-1` (prevent overflow)

#### States
- **Hover:** `hover:border-input/80 hover:shadow`
- **Focus:** `focus-visible:border-ring focus-visible:ring-ring/30 focus-visible:ring-[3px]`
- **Disabled:** `disabled:opacity-50 disabled:cursor-not-allowed`
- **Error:** `aria-invalid:border-destructive`
- **Open:** `data-[state=open]:bg-sunken` (slight bg change)

### SelectContent (Dropdown Menu)

```
rounded-lg border border-border bg-popover text-popover-foreground shadow-lg z-[1060]
max-h-96 overflow-y-auto
```

- **Position:** `z-[1060]` (above modals at z-1050)
- **Animation:** `data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95`
- **Shadow:** `shadow-lg` (deeper than inputs)
- **Max height:** 96 items max (scrollable)
- **Offset:** 4px from trigger (popper positioning)

### SelectItem

```
flex items-center gap-2 rounded-sm py-1.5 pl-2 pr-8 text-sm cursor-pointer
focus:bg-accent focus:text-accent-foreground
```

- **Height:** 36px per item
- **Padding:** 8px left, 32px right (space for checkmark)
- **Selection indicator:** CheckIcon (3.5px) at right
- **Focus:** `focus:bg-accent` (light highlight)
- **Disabled:** `data-[disabled]:opacity-50 data-[disabled]:pointer-events-none`

### SelectLabel & Separator

**Label:**
```
px-2 py-1.5 text-xs text-muted-foreground font-medium
```
- Use for option groups

**Separator:**
```
-mx-1 my-1 h-px bg-border
```
- Divider between groups

---

## Checkbox

**Component:** `<Checkbox />`

### Default States

```
peer size-4 shrink-0 rounded-md border border-input shadow-sm
```

- **Size:** 16px × 16px
- **Border radius:** 4px (md — separate from input radius)
- **Border:** `--tb-border` (#E4E7EC)
- **Background (unchecked):** `--tb-card-bg` (white)
- **Shadow:** Subtle (1px)

#### Checked
```
data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground
```

- **Background:** `--tb-brand` (#2563EB)
- **Border:** `--tb-brand`
- **Check Icon:** `size-3.5` (14px) centered, white
- **Instant transition** (no animation on check)

#### Hover
```
hover:border-input/80 hover:shadow
```

- **Border:** Slightly darker
- **Shadow:** Lifted

#### Focus
```
focus-visible:ring-[3px] focus-visible:ring-ring/40
```

- **Ring:** 3px, 40% opacity
- **Instant focus**

#### Disabled
```
disabled:cursor-not-allowed disabled:opacity-50
```

- **Opacity:** 50% (both checked and unchecked)

---

## Radio Button

**Component:** *To be created* — follows checkbox pattern but circular.

```
size-4 rounded-full border border-input
data-[state=checked]:border-primary data-[state=checked]:bg-primary
```

- **Size:** 16px
- **Border radius:** 50% (circle)
- **Indicator:** Centered dot (6px diameter) when checked
- **All states same as checkbox**

---

## Toggle / Switch

**Component:** `<Switch />`

```
inline-flex h-6 w-10 shrink-0 cursor-pointer items-center rounded-full
border border-transparent shadow-sm
```

- **Size:** 40px wide × 24px tall
- **Border radius:** 50% (pill shape)
- **Background (unchecked):** `--tb-input` (light gray)
- **Background (checked):** `--tb-brand` (#2563EB)
- **Shadow:** 1px subtle

#### Thumb (Toggle)
```
block size-4 rounded-full bg-white shadow-sm
data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0.5
```

- **Size:** 16px circle
- **Color:** White (high contrast)
- **Animation:** Translate on check/uncheck (200ms easing)
- **Offset:** 2px unchecked, 16px checked (leaves 2px margin on each side)

#### States
- **Hover:** `hover:shadow` (subtle lift)
- **Focus:** `focus-visible:ring-[3px] focus-visible:ring-ring/40`
- **Disabled:** `disabled:cursor-not-allowed disabled:opacity-50`

---

## Textarea

**Component:** `<Textarea />`

```
flex min-h-[80px] w-full rounded-lg border border-input bg-card px-3 py-2 text-sm
font-normal leading-relaxed
```

- **Min height:** 80px (5 lines at 14px/line)
- **Border:** Same as text input
- **Padding:** 12px horizontal, 8px vertical
- **Resize:** Both horizontal and vertical
- **Font:** Regular 14px, normal line height

#### States
- **Hover:** Same as Input
- **Focus:** Same as Input
- **Disabled:** Same as Input
- **Placeholder:** Same as Input

---

## Date Input

**Component:** HTML5 `<input type="date">` + formatting wrapper

```html
<Input 
  type="date" 
  className="..."
/>
```

- **Format:** Browser-native (MM/DD/YYYY in US locale)
- **Styling:** Inherits Input styles
- **Picker:** Native OS date picker (mobile: native picker, desktop: calendar widget)
- **Validation:** `aria-invalid` when date out of range

#### States
- Use same Input states (hover, focus, disabled, error)

---

## Date Range

**Component:** *To be created* — two date inputs side-by-side

```tsx
<div className="flex gap-2 items-end">
  <FormField label="From" name="start_date" type="date" />
  <FormField label="To" name="end_date" type="date" />
</div>
```

- **Layout:** Flex row, 8px gap
- **Labels:** "From" and "To"
- **Responsive:** Stack on mobile (flex-col)
- **Validation:** Optional: enforce start <= end

---

## Search Input

**Component:** `<DebouncedSearchInput />`

```
Specialized input with:
- Debounce delay (300ms default)
- Clear button on focus if text present
- Search icon (optional)
- Optimized for list filtering
```

- **Styling:** Inherits Input styles
- **Icon:** Search icon (16px) on left side
- **Clear button:** X icon when text present, click to clear
- **Debounce:** API calls debounced 300ms
- **a11y:** aria-label for search field

---

## Label

**Component:** `<Label />`

```
text-sm font-medium text-foreground
```

- **Font size:** 14px (sm)
- **Font weight:** 500 (medium)
- **Color:** `--tb-text` (#111827)
- **Spacing (below input):** 6px (`mb-1.5` in forms)
- **Required indicator:** Suffix "*" (red, `ml-1`)
- **Accessibility:** `htmlFor={id}` links to input

---

## Help Text

**Pattern:** Text below the input field

```
text-xs text-muted-foreground mt-1
```

- **Font size:** 11px (xs)
- **Color:** `--tb-text-tertiary` (#9CA3AF)
- **Spacing (above):** 4px
- **Use cases:** Placeholder clarification, format hints

---

## Error Message

**Pattern:** Text below the input field (replaces help text on error)

```
text-xs text-destructive mt-1 font-medium
```

- **Font size:** 11px (xs)
- **Color:** `--tb-danger` (#DC2626)
- **Spacing (above):** 4px
- **Icon (optional):** TriangleAlert (12px) before text
- **Accessibility:** `aria-describedby` on input, `role="alert"` on message

---

## Component API

### Input
```typescript
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  type?: 
    | "text"
    | "email"
    | "password"
    | "number"
    | "tel"
    | "url"
    | "search"
    | "date"
    | "file"
    | "hidden";
  
  size?: "compact-small" | "compact" | "default";
}
```

### Select
```typescript
interface SelectProps {
  value: string;
  onValueChange: (value: string) => void;
  disabled?: boolean;
}

interface SelectTriggerProps {
  size?: "sm" | "default";
}

interface SelectItemProps {
  value: string;
  disabled?: boolean;
}
```

### Checkbox
```typescript
interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
  // Inherits from Radix checkbox primitive
}
```

### Switch
```typescript
interface SwitchProps {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
}
```

### Textarea
```typescript
interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  // Standard textarea attributes
  rows?: number;  // default: 3
}
```

---

## Common Patterns

### Required Field Indicator
```tsx
<Label htmlFor="name">
  Full Name
  <span className="text-destructive ml-1" aria-label="required">*</span>
</Label>
<Input id="name" required />
```

### With Help Text
```tsx
<div>
  <Label htmlFor="email">Email</Label>
  <Input id="email" type="email" />
  <p className="text-xs text-muted-foreground mt-1">
    We'll only use this to contact you about your account.
  </p>
</div>
```

### With Error
```tsx
<div>
  <Label htmlFor="qty">Quantity</Label>
  <Input 
    id="qty" 
    type="number" 
    aria-invalid="true"
    aria-describedby="qty-error"
  />
  {error && (
    <p id="qty-error" className="text-xs text-destructive mt-1">
      <TriangleAlert className="inline size-3 mr-1" />
      {error}
    </p>
  )}
</div>
```

### Multi-Select (Future)
```tsx
<Select multiple>
  <SelectTrigger>
    <SelectValue placeholder="Select items..." />
  </SelectTrigger>
  <SelectContent>
    <SelectItem value="opt1">Option 1</SelectItem>
    <SelectItem value="opt2">Option 2</SelectItem>
  </SelectContent>
</Select>
```

---

## Migration Path (From Current)

| Current | V2 | Notes |
|---------|----|----|
| `h-10` (40px) | `size="default"` | Explicit mapping |
| Custom `h-9` | `size="compact"` (36px) | Standardize |
| N/A | `size="compact-small"` (32px) | New for dense UI |
| `rounded-lg` | `rounded-lg` (--tb-r-md 8px) | Keep consistent |
| No variants | Variants for each size | New: standardize sizing |

---

## Accessibility (WCAG AA)

### Labeling
- Every input must have a `<Label>` with `htmlFor={id}`
- `aria-label` or `aria-labelledby` as fallback
- Required fields marked with `aria-required="true"`

### Validation
- Invalid state: `aria-invalid="true"` on input
- Error message: `aria-describedby="error-id"`
- Error text: `role="alert"` for screen readers

### Focus Management
- All inputs: `focus-visible:ring-[3px]` (3px visible focus ring)
- Ring color: Sufficient contrast on light/dark backgrounds
- Keyboard: Tab to focus, Enter/Space for toggles

### Color Contrast
- Text on background: 4.5:1 minimum
- Placeholder: 3:1 minimum (lighter is OK)
- Focus ring: High contrast on all backgrounds

### Touch Targets
- All interactive inputs: Minimum 44px (WCAG AAA)
- Checkboxes: 16px visual, but with padding in forms = 36px+ hit area
- Labels clickable: Extend to label (checkbox labels are clickable)

---

## File Changes

**To implement:**
1. Update `frontend/src/components/ui/input.tsx` with size variants
2. Update `frontend/src/components/ui/select.tsx` with size variants
3. Update `frontend/src/components/ui/checkbox.tsx` (minor styling)
4. Create `frontend/src/components/ui/radio.tsx` (new)
5. Update `frontend/src/components/FormField.tsx` to support sizes

---

## Token References

- `--tb-border`: Input border (#E4E7EC)
- `--tb-card-bg`: Input background (white)
- `--tb-text`: Input text (#111827)
- `--tb-text-tertiary`: Placeholder/help text (#9CA3AF)
- `--tb-brand`: Focus ring color (#2563EB)
- `--tb-danger`: Error/destructive color (#DC2626)
- `--tb-ring`: Focus ring (alias to --tb-brand)
- `--tb-r-md`: Border radius 8px
- `--tb-control-sm`: 32px (compact-small height)
- `--tb-control-md`: 36px (compact height)
- `--tb-control-lg`: 40px (normal height)

---

**END OF SPECIFICATION**
