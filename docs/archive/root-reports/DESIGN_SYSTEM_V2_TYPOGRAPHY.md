# Enterprise Typography System V2
## License Manager Design System

**Last Updated:** 2026-09-25  
**Version:** 2.0  
**Status:** Reference Specification

---

## Executive Summary

This document defines a professional, readable typography system optimized for enterprise data-heavy interfaces. The system prioritizes **excellent number readability**, **clear visual hierarchy**, and **consistent typography across light and dark modes** using Inter as the primary font family.

---

## 1. Font Family Selection

### Primary Font Stack
```css
--tb-font: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
```

**Current:** Inter (already deployed globally in `frontend/src/theme/tabler.css`)

**Why Inter:**
- Geometric sans-serif with excellent clarity on screen
- Exceptional number/figure spacing and readability
- OpenType features support (tabular figures for alignment)
- First-class dark mode support
- Deployed via Google Fonts CDN
- Professional, neutral personality (Linear, Stripe, Vercel, Notion use it)

### Monospace (for code/data)
```css
--tb-font-mono: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace;
```

**Use cases:** Code blocks, legal references, ledger hashes, raw data displays.

---

## 2. Font Weight Scale

Keep to three weights. More creates visual clutter and maintenance burden.

| Weight | Value | Use Case |
|--------|-------|----------|
| **Regular** | 400 | Body text, data cells, form inputs, help text |
| **Medium** | 500 | Labels, small headings, breadcrumb items, navigation |
| **Semibold** | 600 | Card titles, section headers, emphasized data, action labels |
| **Bold** | 700 | Page titles, modal headers, critical warnings (use sparingly) |

### Font Weight Token Map
```javascript
// frontend/src/theme/tokens.js
fw: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700
}

// CSS Variables (theme/tabler.css)
--tb-fw-normal: 400;
--tb-fw-medium: 500;
--tb-fw-semibold: 600;
--tb-fw-bold: 700;
```

### Weight Usage Rules
- **Do not use bold for labels** — causes visual tension in forms
- **Medium + uppercase** → field labels, breadcrumbs, "REQUIRED" badges
- **Semibold** → headings and prominent data labels (default for titles)
- **Regular** → all body copy and data

---

## 3. Font Size Scale

### Defined Sizes (pixels)

| Scale | Size | Usage | Line Height |
|-------|------|-------|-------------|
| **xs** | 11px | Meta, timestamps, footnotes, small legend | 1.4 |
| **sm** | 12px | Form labels, table headers, help text, badges | 1.4 |
| **base** | 13.5px | Base paragraph text, table data cells | 1.5 |
| **md** | 14.5px | Body text (slightly larger on high-res), button text | 1.5 |
| **lg** | 16px | Large body text, prominent status, section intro | 1.5 |
| **xl** | 20px | Subsection headers (h3), tall buttons, important notices | 1.3 |
| **2xl** | 26px | Page title (h2), modal headers | 1.2 |

### CSS Variable Names (tokens/tabler.css)
```css
--tb-fs-xs: 11px;      /* Meta, timestamps */
--tb-fs-sm: 12px;      /* Labels, table headers */
--tb-fs-base: 13.5px;  /* Default body text */
--tb-fs-md: 14.5px;    /* Body (slightly large) */
--tb-fs-lg: 16px;      /* Large body, status */
--tb-fs-xl: 20px;      /* Subsection headers */
--tb-fs-2xl: 26px;     /* Page title */
```

### Display / Page Title Sizes

| Context | Size | Weight | Line Height | Example |
|---------|------|--------|-------------|---------|
| **Page Title (h1)** | 26-28px | 600–700 | 1.2 | "Dashboard", "License Management" |
| **Section Title (h2/h3)** | 18-20px | 600 | 1.3 | "Licence health", "Recent activity" |
| **Card Title** | 16px | 600 | 1.3 | Inside Card/CardHeader |
| **Subsection** | 14–15px | 600 | 1.4 | Filter section titles |

---

## 4. Line Height Scale

### Line Height Ratios (unitless)

| Context | Value | Use |
|---------|-------|-----|
| **Tight** | 1.2 | Headings, display text, labels |
| **Normal** | 1.3 | Subtitles, medium-sized headings |
| **Relaxed** | 1.5 | Body text, longer form content, table cells |
| **Loose** | 1.6 | Very long-form (descriptions, help text) |

### Applied Rules
- **Display/Heading (>20px):** 1.2 line-height
- **Titles (16–20px):** 1.3 line-height
- **Body/Data (<16px):** 1.5 line-height
- **Help text, descriptions:** 1.6 line-height
- **Table data cells:** 1.5 line-height (inherit from base)

### CSS Implementation
```css
html, body {
    line-height: 1.5; /* base */
}
h1, h2, h3, h4 { line-height: 1.2; }
h5, h6 { line-height: 1.3; }
small, .text-sm { line-height: 1.4; }
.prose { line-height: 1.6; }
```

---

## 5. Letter Spacing

### Rules
- **Default:** normal (0) — no change from design
- **All-caps labels:** 0.05em (5% of font size)
- **Badges, tags:** normal
- **Do not** add letter-spacing to body text

### Example
```css
.label-uppercase {
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 12px;
    font-weight: 500;
}
```

---

## 6. Heading Hierarchy

### Standard Heading Structure

| Element | Size | Weight | Line Ht | Usage | Example |
|---------|------|--------|---------|-------|---------|
| **h1** | 26px | 700 | 1.2 | Page title | "Dashboard", "Licenses" |
| **h2** | 20px | 600 | 1.2 | Section header | "Licence health", "Recent activity" |
| **h3** | 18px | 600 | 1.3 | Subsection | "Allotments", "Pending items" |
| **h4** | 16px | 600 | 1.3 | Card title, field group | Inside Card/CardHeader |
| **h5** | 14px | 600 | 1.4 | Small card header | Minor section title |
| **h6** | 12px | 500 | 1.4 | Label-like header | Field group label |

### CSS Rules (in `@layer base`)
```css
h1 { font-size: 26px; font-weight: 700; line-height: 1.2; }
h2 { font-size: 20px; font-weight: 600; line-height: 1.2; }
h3 { font-size: 18px; font-weight: 600; line-height: 1.3; }
h4 { font-size: 16px; font-weight: 600; line-height: 1.3; }
h5 { font-size: 14px; font-weight: 600; line-height: 1.4; }
h6 { font-size: 12px; font-weight: 500; line-height: 1.4; }
```

---

## 7. Body Text & Paragraph

### Default Body
- **Size:** 13.5–14.5px (base or md)
- **Weight:** 400 (regular)
- **Line Height:** 1.5
- **Max width:** 65–75ch (optimal for reading)

### Paragraph Spacing
- **Between paragraphs:** 1rem (16px) or 1.5rem (24px)
- **Inside lists:** 0.5rem (8px) between items

### Code Block
```css
p {
    font-size: var(--tb-fs-base);
    font-weight: 400;
    line-height: 1.5;
    margin-bottom: 1rem;
}
p + p { margin-top: 0.5rem; } /* Tight consecutive paragraphs */
```

---

## 8. Label & Form Text

### Form Field Label
- **Size:** 12px (sm)
- **Weight:** 500 (medium)
- **Transform:** capitalize (existing convention)
- **Color:** var(--tb-text-secondary) (secondary gray)
- **Margin below:** 4–6px

```css
label.form-label,
.form-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--tb-text-secondary);
    margin-bottom: 4px;
    display: block;
    text-transform: capitalize;
    letter-spacing: 0.01em;
}
```

### Required Indicator
```css
label.required::after {
    content: " *";
    color: var(--tb-danger);
    font-weight: 600;
}
```

### Help Text
- **Size:** 12px (xs)
- **Weight:** 400 (regular)
- **Color:** var(--tb-text-tertiary) (muted)
- **Margin top:** 4px
- **Font style:** normal (no italic)

```css
.form-text,
.help-text {
    font-size: 12px;
    color: var(--tb-text-tertiary);
    margin-top: 4px;
}
```

---

## 9. Table Typography

### Header (th)
- **Size:** 12px
- **Weight:** 500 (medium) — stands out as column label
- **Line Height:** 1.4
- **Text transform:** none (preserve as-is)
- **Color:** var(--tb-text-secondary)

### Data Cell (td)
- **Size:** 13.5px
- **Weight:** 400 (regular)
- **Line Height:** 1.5
- **Color:** var(--tb-text)

### Row Height
- **Default:** 36–40px (includes padding)
- **Compact:** 32px (for dense lists)
- **Relaxed:** 44–48px (for touch-friendly mobile)

### CSS
```css
table {
    font-size: 13.5px;
    line-height: 1.5;
}
thead th {
    font-size: 12px;
    font-weight: 500;
    color: var(--tb-text-secondary);
    line-height: 1.4;
    padding: 8px 12px;
}
tbody td {
    font-size: 13.5px;
    font-weight: 400;
    color: var(--tb-text);
    line-height: 1.5;
    padding: 10px 12px;
}
```

---

## 10. Button Text

### Button Typography
- **Size:** 14px (md)
- **Weight:** 500 (medium) — buttons need visual weight
- **Line Height:** 1.4
- **Transform:** none
- **Variant:**
  - **Primary/Solid:** white text (#fff)
  - **Outline/Ghost:** inherit text color

```css
button, .btn {
    font-size: 14px;
    font-weight: 500;
    line-height: 1.4;
    text-transform: none;
}
```

### Button Sizes
| Size | Height | Font | Padding |
|------|--------|------|---------|
| **sm** | 32–36px | 13px | 6–8px v, 12px h |
| **md (default)** | 36–40px | 14px | 8–10px v, 16px h |
| **lg** | 40–44px | 15px | 10–12px v, 20px h |
| **icon** | 36–40px | n/a | centered |

---

## 11. Badge & Status Labels

### Badge/Chip Typography
- **Size:** 12px
- **Weight:** 500 (medium)
- **Transform:** none (unless specific use case like all-caps status)
- **Line Height:** 1.2

```css
.badge, .chip {
    font-size: 12px;
    font-weight: 500;
    line-height: 1.2;
    display: inline-block;
}
```

---

## 12. Dark Mode Considerations

### Font Rendering
- **Anti-aliasing:** -webkit-font-smoothing: antialiased; applied globally
- **Rendering difference:** Inter renders slightly lighter on dark backgrounds; no adjustment needed (by design)

### Color Contrast (Dark Mode)
- **Body text:** var(--tb-text) (#E6EDF3) on var(--tb-card-bg) (#161B22) = **10.2:1 ratio** ✓ AAA
- **Secondary text:** var(--tb-text-secondary) (#8D96A0) on var(--tb-card-bg) = **5.1:1 ratio** ✓ AA
- **Tertiary text:** var(--tb-text-tertiary) (#656D76) on dark bg = **3.5:1 ratio** ⚠ AA minimum (avoid for small text <12px)

### Font Weight in Dark Mode
- **No change** — weights remain identical
- **Optical adjustment:** Inter's variable font can auto-adjust optical size, but not implemented (static instance)

---

## 13. Typography Utilities (Tailwind)

### Text Sizes (Tailwind classes)
```css
/* Map to CSS variables or Tailwind preset */
.text-xs { font-size: 11px; }      /* --tb-fs-xs */
.text-sm { font-size: 12px; }      /* --tb-fs-sm */
.text-base { font-size: 13.5px; }  /* --tb-fs-base */
.text-md { font-size: 14.5px; }    /* --tb-fs-md */
.text-lg { font-size: 16px; }      /* --tb-fs-lg */
.text-xl { font-size: 20px; }      /* --tb-fs-xl */
.text-2xl { font-size: 26px; }     /* --tb-fs-2xl */
```

### Font Weights (Tailwind classes)
```css
.font-normal { font-weight: 400; }
.font-medium { font-weight: 500; }
.font-semibold { font-weight: 600; }
.font-bold { font-weight: 700; }
```

### Line Heights (Tailwind)
```css
.leading-tight { line-height: 1.2; }
.leading-snug { line-height: 1.3; }
.leading-normal { line-height: 1.5; }
.leading-relaxed { line-height: 1.6; }
```

---

## 14. Number Readability (Critical for License Manager)

### Table Numbers: Tabular Figures
- **Use:** All numeric columns (quantity, price, weight, balance)
- **CSS:** `font-feature-settings: "tnum"` (not yet implemented, but Inter supports)

```css
.table td {
    font-feature-settings: "tnum"; /* Tabular figures for alignment */
}
```

### Decimal Alignment
- **CSS:** text-align: right; for numeric columns
- **Font:** Monospace for very large/complex numbers (ledger hashes)

### Money Formatting
- **Size:** Match table cell (13.5px)
- **Alignment:** right
- **Thousand separator:** comma (,)
- **Decimal places:** 2 (₹1,23,456.78)

---

## 15. Accessible Typography

### Color Contrast
- **Body on light bg:** #111827 on #FFFFFF = **21:1** ✓ AAA
- **Secondary on light bg:** #5E6673 on #FFFFFF = **8.4:1** ✓ AAA
- **Body on dark bg:** #E6EDF3 on #161B22 = **10.2:1** ✓ AAA

### Focus Indicators
- **Outline:** 2px solid var(--tb-brand)
- **Offset:** 2px
- **Applies to:** Links, buttons, form inputs, focusable elements

### Touch Targets
- **Minimum:** 44px (mobile, per WCAG 2.5.5)
- **Desktop buttons:** 36–40px (acceptable)
- **Form inputs:** 36–44px height

---

## 16. Special Cases

### Breadcrumbs
- **Size:** 11–12px
- **Weight:** 400 or 500
- **Separator:** `/` or `>` (visual, not semantic)

### Metadata / Timestamps
- **Size:** 11px
- **Weight:** 400
- **Color:** var(--tb-text-tertiary)
- **Format:** "Updated 2 hours ago" or "Sep 25, 2026"

### Error Messages
- **Size:** 12px
- **Weight:** 400 or 500
- **Color:** var(--tb-danger-text)
- **Icon:** ⚠ or ✕ (12–14px)

### Success / Confirmation
- **Size:** 12–14px
- **Weight:** 500 (medium)
- **Color:** var(--tb-success-text)
- **Icon:** ✓ (12–14px)

### Tooltips
- **Size:** 12px
- **Weight:** 400
- **Max width:** 200–300px
- **Line height:** 1.4

---

## 17. Legacy Overrides (Deprecation Path)

The following are **in use but marked for consolidation**:

| Old | New | Status |
|-----|-----|--------|
| Bootstrap h1–h6 | Use standard h1–h6 sizing | Keep compatible |
| Material Design 12.5px labels | Use 12px standard labels | Transition to 12px |
| Poppins font (old backend) | Inter (modern frontend) | ✓ Migrated |
| Custom font sizes (inline) | Use token scale | Audit & consolidate |

---

## 18. Implementation Checklist

- [x] Audit: All fonts are Inter (already deployed)
- [x] Audit: Sizes and weights defined in tabler.css
- [x] Audit: Line heights and letter spacing documented
- [ ] Standardize: All custom/inline font-size → token scale
- [ ] Add: Tabular figures CSS for numeric data
- [ ] Test: Dark mode contrast on all text color combos
- [ ] Test: Touch targets on mobile (44px minimum)
- [ ] Test: Readability at 1.2x and 2x zoom levels
- [ ] Audit: Remove hardcoded font family from components
- [ ] Update: Tailwind config to reference tokens

---

## References

- **Font:** [Inter (Google Fonts)](https://fonts.google.com/specimen/Inter)
- **Line height:** [Modular Scale by Tim Brown](https://www.modularscale.com/)
- **Contrast:** [WCAG 2.1 AA/AAA](https://www.w3.org/WAI/WCAG21/quickref/)
- **Touch targets:** [WCAG 2.5.5 Target Size](https://www.w3.org/WAI/WCAG21/Understanding/target-size.html)

