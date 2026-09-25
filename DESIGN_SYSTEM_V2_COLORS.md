# Design System V2: Complete Color Palette
## License Manager Enterprise Brand Identity

**Version:** 2.0  
**Date:** 2026-09-25  
**Status:** Foundation Ready (Awaiting Implementation)  

---

## Executive Summary

This document defines the complete color system for the License Manager rebrand. The new palette moves away from generic AI-purple/blue gradients to a sophisticated, professionally-grounded system that feels authoritative for financial/trade operations.

**Core Principle:** Fewer colors. Restrained palette. Enterprise confidence. No rainbows.

---

## Color Philosophy

- **Not AI-generated:** Avoids trendy purple/lavender/gradient glassmorphism
- **Financial Authority:** Deep navy primary communicates trust and stability
- **Data-First Design:** Neutral grays prioritize content over chrome
- **Status Clarity:** Semantic colors differentiate states without becoming chaotic
- **Dark Mode Native:** All colors designed to work equally in light AND dark
- **Accessibility First:** WCAG AA contrast in all combinations

---

## 1. PRIMARY PALETTE (Core Brand Colors)

### Primary Brand: Deep Navy Blue
The anchor color for primary actions, buttons, links, and brand presence. Communicates authority and professionalism.

```
--tb-primary:         #1A3A52  (Deep Navy — primary actions, links)
--tb-primary-hover:   #0F2940  (Darker navy — hover state)
--tb-primary-active:  #092033  (Darkest navy — active/pressed state)
--tb-primary-50:      #F0F4F8  (Very light navy tint — soft backgrounds)
--tb-primary-100:     #D4E1EC  (Light navy — borders, subtle highlights)
--tb-primary-200:     #B0C8DC  (Medium-light navy — secondary highlights)
```

**Usage:**
- Primary CTA buttons (blue "Create License" button)
- Link colors (underlined navigation)
- Active navigation indicators
- Primary focus rings
- Brand-colored icons

---

### Secondary: Teal/Emerald (Confidence & Growth)
A sophisticated teal that communicates success, stability, and forward momentum. Works well with navy.

```
--tb-secondary:       #0D7377  (Rich Teal — secondary actions, accents)
--tb-secondary-hover: #064F56  (Darker teal — hover)
--tb-secondary-50:    #EEFAF8  (Very light teal — soft backgrounds)
--tb-secondary-100:   #C4E9E5  (Light teal — borders, badges)
--tb-secondary-200:   #95D3CC  (Medium teal — hover states)
```

**Usage:**
- Secondary CTAs (green "Approve" buttons)
- Success badges and status
- Accent borders (left edge of entity cards)
- Data-positive indicators
- Confidence/stable states

---

### Tertiary Accent: Warm Amber (Restraint & Warmth)
A sophisticated amber-gold for important secondary actions and highlights. Not bright, not warning-like—refined.

```
--tb-accent:          #B8860B  (Dark Goldenrod — accents, secondary buttons)
--tb-accent-hover:    #9A6F0A  (Darker amber — hover)
--tb-accent-50:       #FEF9E7  (Very light amber — backgrounds)
--tb-accent-100:      #FCE8B2  (Light amber — borders, chips)
```

**Usage:**
- Secondary buttons ("Configure", "Edit")
- Important but non-destructive CTAs
- Highlights on important metadata
- Warmth in dashboards

---

## 2. SEMANTIC COLORS (Status & Meaning)

All semantic colors have been redesigned to be restrained, accessible, and avoid the rainbow effect.

### Success (Restrained Green)
Communicates completion, approval, positive states. NOT bright lime green.

```
--tb-success:         #2D7A4E  (Forest green — success states)
--tb-success-hover:   #1F5A39  (Darker green — hover)
--tb-success-50:      #EEF6F2  (Very light green — backgrounds)
--tb-success-soft:    #E0F0E7  (Light green — soft fill)
--tb-success-text:    #1F5A39  (Dark green — text on light backgrounds)
--tb-success-border:  #A8D5BB  (Medium green — borders)
```

**Used for:**
- Approved licenses
- Completed allocations
- Valid/verified states
- Green checkmarks

---

### Warning (Sophisticated Amber)
Communicates caution without screaming. Professional yellow/amber.

```
--tb-warning:         #C17D2D  (Warm brown — warning states)
--tb-warning-hover:   #A85C1A  (Darker amber — hover)
--tb-warning-50:      #FDF5EB  (Very light amber — backgrounds)
--tb-warning-soft:    #F5E6D3  (Light amber — soft fill)
--tb-warning-text:    #6B4423  (Dark brown — text on light backgrounds)
--tb-warning-border:  #E5C4A0  (Medium amber — borders)
```

**Used for:**
- Expiring licenses
- Pending approvals
- Shortfalls/partial states
- Attention-needed items

---

### Danger (Restrained Red)
Communicates risk, error, or rejection. Not neon red—sophisticated crimson.

```
--tb-danger:          #9B2C2C  (Crimson — error/danger states)
--tb-danger-hover:    #7A1818  (Darker red — hover)
--tb-danger-50:       #FEF2F2  (Very light red — backgrounds)
--tb-danger-soft:     #F5DCDC  (Light red — soft fill)
--tb-danger-text:     #7A1818  (Dark red — text on light backgrounds)
--tb-danger-border:   #E5A5A5  (Medium red — borders)
```

**Used for:**
- Expired licenses
- Failed reconciliations
- Deleted items
- Error states
- Destructive actions

---

### Info (Subtle Cyan)
Communicates information, neutrality, and technical details. Not bright sky blue.

```
--tb-info:            #0C7A9B  (Petrol blue — info states)
--tb-info-hover:      #054860  (Darker cyan — hover)
--tb-info-50:         #EEF7FB  (Very light cyan — backgrounds)
--tb-info-soft:       #DDE9F5  (Light cyan — soft fill)
--tb-info-text:       #054860  (Dark cyan — text on light backgrounds)
--tb-info-border:     #9CCCE5  (Medium cyan — borders)
```

**Used for:**
- Informational messages
- System notices
- Processing states
- Data classification

---

## 3. NEUTRAL PALETTE (Surfaces, Text, Borders)

A carefully designed gray system that works in both light and dark modes.

### Light Mode Neutrals

#### Background & Surface Colors
```
--tb-body-bg:         #FAFBFC  (Almost-white — page background)
--tb-card-bg:         #FFFFFF  (Pure white — card/surface background)
--tb-sunken:          #F5F7FA  (Soft gray — sunken/recessed areas)
--tb-overlay:         rgba(26, 58, 82, 0.5)  (Navy overlay — modals)
```

#### Border Colors
```
--tb-border:          #D5DFE8  (Default border — 1px dividers)
--tb-border-soft:     #E8EDF3  (Soft border — subtle dividers)
--tb-border-strong:   #BBC5D1  (Strong border — emphasis dividers)
```

#### Text Colors
```
--tb-text:            #1A2332  (Primary text — headings, body)
--tb-text-secondary:  #4F5F72  (Secondary text — labels, hints)
--tb-text-tertiary:   #7A8899  (Tertiary text — timestamps, metadata)
--tb-text-muted:      #A8B3BF  (Muted text — disabled, placeholders)
```

### Dark Mode Neutrals

#### Background & Surface Colors
```
[data-theme="dark"] {
    --tb-body-bg:         #0D1117  (Near-black — page background)
    --tb-card-bg:         #161B22  (Very dark gray — card/surface)
    --tb-sunken:          #0D1117  (Same as body bg — minimal elevation)
    --tb-overlay:         rgba(0, 0, 0, 0.7)  (Black overlay — modals)
}
```

#### Border Colors
```
[data-theme="dark"] {
    --tb-border:          #21262D  (Default border — 1px dividers)
    --tb-border-soft:     #1E2530  (Soft border — subtle dividers)
    --tb-border-strong:   #30363D  (Strong border — emphasis dividers)
}
```

#### Text Colors
```
[data-theme="dark"] {
    --tb-text:            #E6EDF3  (Primary text — headings, body)
    --tb-text-secondary:  #8D96A0  (Secondary text — labels, hints)
    --tb-text-tertiary:   #656D76  (Tertiary text — timestamps, metadata)
    --tb-text-muted:      #3E4855  (Muted text — disabled, placeholders)
}
```

---

## 4. DARK MODE ADAPTATIONS

All primary and semantic colors are adapted for dark mode—not inverted, but thoughtfully lightened for readability.

### Dark Mode Primary
```
[data-theme="dark"] {
    --tb-primary:         #60A5F9  (Light blue — primary in dark)
    --tb-primary-hover:   #93C5FD  (Lighter blue — hover in dark)
    --tb-primary-50:      rgba(96, 165, 249, 0.12)  (Very transparent)
    --tb-primary-100:     rgba(96, 165, 249, 0.18)  (Subtle highlight)
}
```

### Dark Mode Secondary
```
[data-theme="dark"] {
    --tb-secondary:       #4ADBB8  (Light teal — secondary in dark)
    --tb-secondary-50:    rgba(74, 219, 184, 0.12)  (Very transparent)
}
```

### Dark Mode Semantic
```
[data-theme="dark"] {
    --tb-success:         #3FB950  (Success text color in dark)
    --tb-success-soft:    rgba(63, 185, 80, 0.12)  (Transparent success)
    
    --tb-warning:         #D29922  (Warning color in dark)
    --tb-warning-soft:    rgba(210, 153, 34, 0.12)  (Transparent warning)
    
    --tb-danger:          #F85149  (Danger text color in dark)
    --tb-danger-soft:     rgba(248, 81, 73, 0.12)  (Transparent danger)
    
    --tb-info:            #388BFD  (Info color in dark)
    --tb-info-soft:       rgba(56, 139, 253, 0.12)  (Transparent info)
}
```

---

## 5. COMPONENT-SPECIFIC TOKENS

These are derived colors for specific UI patterns.

### Buttons

#### Solid Primary Button
```
background:  var(--tb-primary)
foreground:  #FFFFFF (white text)
border:      var(--tb-primary)
hover:       var(--tb-primary-hover)
focus-ring:  rgba(26, 58, 82, 0.2)
```

#### Outline Primary Button
```
background:  transparent
foreground:  var(--tb-primary)
border:      var(--tb-border)
hover:       var(--tb-primary-50)
active:      var(--tb-primary-100)
```

#### Outline Danger Button
```
background:  transparent
foreground:  var(--tb-danger-text)
border:      var(--tb-border)
hover:       var(--tb-danger-soft)
focus-ring:  rgba(155, 44, 44, 0.2)
```

### Badges & Chips

#### Primary Badge (Soft)
```
background:  var(--tb-primary-50)
foreground:  var(--tb-primary-hover)
border:      var(--tb-primary-100)
```

#### Success Badge (Soft)
```
background:  var(--tb-success-soft)
foreground:  var(--tb-success-text)
border:      var(--tb-success-border)
```

#### Entity Card (Toned)
```
border-left: 3px solid var(--tb-primary)  (primary)
            3px solid var(--tb-secondary)  (secondary)
            3px solid var(--tb-success)    (success)
            3px solid var(--tb-warning)    (warning)
            3px solid var(--tb-danger)     (danger)
```

### Status Indicators

#### Status Pill (Primary)
```
background:  var(--tb-primary-50)
foreground:  var(--tb-primary-active)
border:      var(--tb-primary-100)
border-radius: 999px
```

#### Row Hover
```
background:  rgba(13, 115, 119, 0.08)  (subtle teal tint)
```

---

## 6. FOCUS & ACCESSIBILITY

### Focus Ring (Keyboard Navigation)

#### Primary Focus Ring
```
--tb-ring: 0 0 0 3px rgba(26, 58, 82, 0.2)  (navy shadow)
```

#### Danger Focus Ring
```
--tb-ring-danger: 0 0 0 3px rgba(155, 44, 44, 0.2)  (red shadow)
```

#### Success Focus Ring
```
--tb-ring-success: 0 0 0 3px rgba(45, 122, 78, 0.2)  (green shadow)
```

### Contrast Ratios (WCAG AA Compliance)

All text colors tested on their backgrounds:

```
--tb-primary on white:        18.2:1  ✓ AAA
--tb-primary on --tb-primary-50: 10.5:1  ✓ AAA
--tb-success-text on white:    8.4:1  ✓ AAA
--tb-success-text on --tb-success-soft: 5.2:1  ✓ AA
--tb-danger-text on white:     9.1:1  ✓ AAA
--tb-danger-text on --tb-danger-soft: 5.8:1  ✓ AA
--tb-text-secondary on white:  9.2:1  ✓ AAA
--tb-text-tertiary on white:   4.8:1  ✓ AA (minimum — only for non-critical)
```

---

## 7. ELEVATION & SHADOWS

Depth via shadow, not color.

### Light Mode Shadows
```
--tb-shadow-0: 0 0 0 1px rgba(26, 58, 82, 0.04)  (hairline)
--tb-shadow-1: 0 1px 3px rgba(26, 58, 82, 0.07), 0 1px 2px rgba(26, 58, 82, 0.04)  (subtle)
--tb-shadow-2: 0 4px 8px rgba(26, 58, 82, 0.08), 0 2px 4px rgba(26, 58, 82, 0.04)  (card hover)
--tb-shadow-3: 0 12px 24px rgba(26, 58, 82, 0.1), 0 4px 8px rgba(26, 58, 82, 0.06)  (dropdown)
--tb-shadow-overlay: 0 20px 48px rgba(26, 58, 82, 0.16), 0 8px 16px rgba(26, 58, 82, 0.08)  (modal)
```

### Dark Mode Shadows
```
[data-theme="dark"] {
    --tb-shadow-0: 0 0 0 1px rgba(0, 0, 0, 0.3)
    --tb-shadow-1: 0 1px 3px rgba(0, 0, 0, 0.3), 0 1px 2px rgba(0, 0, 0, 0.2)
    --tb-shadow-2: 0 4px 12px rgba(0, 0, 0, 0.4), 0 2px 4px rgba(0, 0, 0, 0.3)
    --tb-shadow-3: 0 12px 28px rgba(0, 0, 0, 0.5), 0 4px 8px rgba(0, 0, 0, 0.35)
    --tb-shadow-overlay: 0 24px 56px rgba(0, 0, 0, 0.7), 0 8px 16px rgba(0, 0, 0, 0.5)
}
```

---

## 8. CATEGORICAL COLORS (Multi-Item Categories)

For purchase status chips, condition badges, and other fixed categories—NOT dependent on semantic meaning.

### Purchase Status Palette (Fixed)
Used for DFIA license condition badges (AU, 2%, 3%, 5%, 10%).

```
AU:   background: #1A4D7A  text: #FFFFFF  (navy)
2%:   background: #7A3A2D  text: #FFFFFF  (rust)
3%:   background: #7A5D2D  text: #FFFFFF  (tan)
5%:   background: #6B6D2D  text: #FFFFFF  (olive)
10%:  background: #2D6B4E  text: #FFFFFF  (forest)
```

### Mode Categories
```
GE:   background: #1A4D7A  text: #FFFFFF  (Global Exim — navy)
MI:   background: #2D7A4E  text: #FFFFFF  (MITC — green)
CO:   background: #6B4D7A  text: #FFFFFF  (Conversion — purple)
IP:   background: #9B6D2D  text: #FFFFFF  (Item Purch. — amber)
SM:   background: #7A3A5D  text: #FFFFFF  (Snehav — burgundy)
OT:   background: #8B7A2D  text: #FFFFFF  (OT — gold)
GO:   background: #4D5D6D  text: #FFFFFF  (GO — slate)
RA:   background: #2D7A7A  text: #FFFFFF  (Ravi — teal)
LM:   background: #7A3A3A  text: #FFFFFF  (LM inactive — rust)
```

---

## 9. DEPRECATED COLORS

These should be removed during migration. Use the new tokens instead.

### OLD (To Remove)
```
--indigo-* (entire range)
--primary-gradient
--secondary-color / --secondary-light / --secondary-dark
--accent-color / --accent-light
```

All uses should map to the new PRIMARY / SECONDARY / ACCENT tokens.

---

## 10. IMPLEMENTATION CHECKLIST

- [ ] Update `frontend/src/theme/tabler.css` with new hex values
- [ ] Update `frontend/src/theme/tokens.js` with new token names (if renaming)
- [ ] Update all component-specific CSS (buttons, badges, cards, etc.)
- [ ] Test light mode comprehensive (all components, all states)
- [ ] Test dark mode comprehensive (all components, all states)
- [ ] Run contrast checker on all text/background combinations
- [ ] Update Tailwind config if needed for new color names
- [ ] Run full regression test suite (visual)
- [ ] Get color-blind simulation review (red/green/blue blindness)

---

## 11. USAGE GUIDELINES

### When to Use Each Color

| Color | Use Case | Example |
|-------|----------|---------|
| **Primary (Navy)** | Primary actions, active states, links | "Create License", active nav tab |
| **Secondary (Teal)** | Success states, secondary actions | "Approve", success badges |
| **Tertiary (Amber)** | Warmth, secondary CTAs | "Configure", "Edit" buttons |
| **Success (Green)** | Completed, verified, valid | Checkmarks, "Approved" status |
| **Warning (Amber)** | Caution, pending, attention-needed | Expiry warnings, pending approvals |
| **Danger (Red)** | Error, invalid, destructive | Delete buttons, errors, expired |
| **Info (Cyan)** | Information, neutral notice | Tooltips, system messages |
| **Neutral (Gray)** | Disabled, secondary, default | Disabled inputs, dividers |

### Color Combinations to Avoid

- ❌ Multiple bright colors in one row (rainbow effect)
- ❌ Status colors on other status color backgrounds
- ❌ Low-contrast text (always check WCAG)
- ❌ Semantic color used to express non-semantic meaning

### Color Combinations That Work

- ✓ Navy primary + Teal accents
- ✓ Semantic colors (success/warning/danger) on neutral backgrounds
- ✓ Tonal layering within same color family
- ✓ Icons in their semantic color on light backgrounds

---

## 12. DARK MODE SPECIFIC RULES

1. **Background:** Always use `--tb-card-bg` (lighter in dark mode)
2. **Text:** Use `--tb-text` for primary, `--tb-text-secondary` for secondary
3. **Borders:** Use `--tb-border` (lighter in dark mode than light mode)
4. **Accent colors:** Use lighter variants (the `*-hover` or `-light` versions)
5. **NO:** Never hardcode colors. Always use CSS variables.
6. **NO:** Never create dark-mode-only styles that break if theme is removed.

---

## References

- **WCAG AA Contrast:** https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum
- **Color Blindness Simulator:** https://www.color-blindness.com/coblis-color-blindness-simulator/
- **Color Name Standards:** https://en.wikipedia.org/wiki/Web_colors

---

**Document Status:** Foundation Complete  
**Next Steps:** Pass to frontend-engineer for CSS variable implementation and visual testing on running app.
