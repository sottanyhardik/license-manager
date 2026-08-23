# Design System — License Manager

## Principles

1. **Clarity over decoration** — operators run high-stakes workflows; every pixel earns its place.
2. **Consistent density** — enterprise data is dense; don't waste space, but don't crowd either.
3. **Progressive disclosure** — default to scan-friendly summary; reveal detail on demand.
4. **Zero ambiguity** — destructive actions need confirmation, errors need context, states need labels.

---

## Token system

All tokens live in two CSS files:
- `frontend/src/theme/tabler.css` — master token definitions (`--tb-*` namespace), component CSS
- `frontend/src/styles/tailwind.css` — bridges tokens into Tailwind's `@theme inline` block

**Never use raw hex colours in component code.** Always use tokens.

### Core colour tokens

| Token | Light | Dark | Use |
|-------|-------|------|-----|
| `--tb-brand` | `#2563EB` | `#3B82F6` | Primary actions, links, active states |
| `--tb-body-bg` | `#F5F6FA` | `#0D1117` | Page canvas |
| `--tb-card-bg` | `#FFFFFF` | `#161B22` | Card/panel backgrounds |
| `--tb-sunken` | `#F8F9FB` | `#0D1117` | Recessed areas, table headers |
| `--tb-border` | `#E4E7EC` | `#21262D` | Default borders |
| `--tb-border-soft` | `#EEF0F4` | `#1E2530` | Subtle dividers |
| `--tb-text` | `#111827` | `#E6EDF3` | Primary text |
| `--tb-text-secondary` | `#6B7280` | `#8D96A0` | Labels, captions |
| `--tb-text-tertiary` | `#9CA3AF` | `#656D76` | Placeholders, hints |

### Semantic colour tokens (Tailwind utilities)

| Tailwind class | Maps to | Use |
|----------------|---------|-----|
| `text-foreground` | `--tb-text` | All body text |
| `text-muted-foreground` | `--tb-text-secondary` | Labels, captions |
| `text-primary` | `--tb-brand` | Brand-coloured text |
| `text-destructive` | `--tb-danger` | Error text, delete actions |
| `text-success` | `--tb-success` | Success text |
| `text-warning` | `--tb-warning` | Warning text |
| `text-info` | `--tb-info` | Informational text |
| `bg-card` | `--tb-card-bg` | Card backgrounds |
| `bg-muted` | `--tb-sunken` | Recessed backgrounds |
| `border-border` | `--tb-border` | Standard borders |

**Never use Bootstrap-origin classes:** `text-danger`, `text-dark`, `text-muted`, `bg-white`,
`bg-secondary`, `d-flex`, `mb-0`, `mt-0`, `mr-*`, `ml-*`, `float-*`.

---

## Typography scale

| Token | Size | Weight | Use |
|-------|------|--------|-----|
| `--tb-fs-xs` | 11px | 400 | Timestamps, meta |
| `--tb-fs-sm` | 12px | 400/500 | Labels, captions |
| `--tb-fs-base` | 13.5px | 400 | Body / table cells |
| `--tb-fs-md` | 14.5px | 500 | Subheadings |
| `--tb-fs-lg` | 16px | 600 | Section titles |
| `--tb-fs-xl` | 20px | 700 | Card headings |
| `--tb-fs-2xl` | 26px | 700 | Page titles |

Font: `Inter` — loaded via Google Fonts.

### Tailwind aliases
- `text-sm` = 14px (shadcn default, close enough)
- `text-xs` = 12px
- `text-[13px]` for body text in tables/forms
- `text-[11px]` / `text-[10.5px]` for meta labels

---

## Spacing

**4-point grid.** Use Tailwind spacing utilities (1 unit = 4px).

| Scale | px | Use |
|-------|-----|-----|
| `gap-1` | 4px | Tight icon+label gaps |
| `gap-2` | 8px | Default inline gaps |
| `gap-3` | 12px | Form field gaps |
| `gap-4` | 16px | Section gaps |
| `gap-5` | 20px | Card padding |
| `gap-6` | 24px | Page section gaps |

---

## Border radius

| Token | Value | Use |
|-------|-------|-----|
| `--tb-r-sm` | 6px | Buttons, badges, inputs |
| `--tb-r-md` | 8px | Cards (inner) |
| `--tb-r-lg` | 10px | Cards (outer), modals |
| `--tb-r-xl` | 14px | Large panels |
| `--tb-r-pill` | 999px | Pills, chips |

Tailwind: `rounded-md` = 8px, `rounded-lg` = 10px, `rounded-xl` = 14px, `rounded-2xl` = 16px.

---

## Shadow / elevation

| Token | Use |
|-------|-----|
| `--tb-shadow-0` | 1px ring — card default |
| `--tb-shadow-1` | Subtle raised card |
| `--tb-shadow-2` | Hover state, dropdown |
| `--tb-shadow-3` | Floating panels, tooltips |
| `--tb-shadow-overlay` | Modals, dialogs |

Tailwind: `shadow-sm` ≈ shadow-1, `shadow-md` ≈ shadow-2.

---

## Component patterns

### Page header
```tsx
<PageHeader
  pretitle="Section name"
  title="Page Title"
  description="Optional context sentence"
  actions={<Button>Primary CTA</Button>}
/>
```

### Stat card
```tsx
<StatCard label="Total Licenses" value={42} icon={FileText} tone="primary" onClick={() => navigate(...)} />
```
Tones: `primary | success | danger | warning | info | neutral`

### Empty state
```tsx
<EmptyState icon={Inbox} title="No records" description="Try adjusting filters" size="default" />
```
Sizes: `default` (table inline) | `page` (full page)

### Confirm dialog
Severity: `danger | warning | info | success`
Uses Lucide icons, Tailwind classes. Always confirm destructive actions.

### Table rows
- Interactive rows: `cursor-pointer hover:bg-accent/40 focus-visible:bg-accent/60`
- Add `rowNav()` helper for keyboard operability (see Dashboard.tsx)
- Add `scope="col"` to all `<th>` elements

### Form fields
- Use `<Label>` + `<Input>` from shadcn
- Use `FormField` / `FormTextArea` / `FormSelect` from `components/FormField.tsx`
- Link label→input via `htmlFor`/`id`
- Use `aria-required`, `aria-invalid`, `aria-describedby`
- Error messages in `<p role="alert">` below the field

### Badges
Use shadcn `<Badge>` variants: `default | secondary | destructive | success | warning | info | outline`

### Toggles / switches
Use shadcn `<Switch>` from `@/components/ui/switch` — never Bootstrap `form-switch`.

### Checkboxes
Use native `<input type="checkbox" className="size-4 rounded accent-primary cursor-pointer">` or shadcn Checkbox.

---

## Navigation

### TopNav
- Height: 52px, `bg-card`, sticky top
- Active trigger: `bg-brand-50 text-brand` + `box-shadow: inset 0 -2px 0 0 var(--tb-brand)` bottom indicator
- Dropdown: click or hover with 150ms close timer; ChevronDown rotates 180° when open
- Command palette: `⌘K` — powered by cmdk v1

### Footer (quick actions)
- Height: 44px, `sticky bottom-0`, `bg-card/95 backdrop-blur-sm`
- Quick links: New License, New Allotment, New BOE, Reports

---

## Dark mode

Driven by `[data-theme="dark"]` on `<html>`. All `--tb-*` tokens flip.
Every component must work in both modes — never hardcode `#ffffff` or `#000000`.
Use `dark:` variant in Tailwind only when the `--tb-*` token approach isn't sufficient.
