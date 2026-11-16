# UI Rebrand Spec V2
## Implementation Guidelines & Standards

**Version:** 2.0  
**Date:** 2026-09-25  
**Status:** Ready for Implementation  
**Target Audience:** Frontend engineers, QA testers

---

## Quick Reference: From Old to New

| Element | Old Token | New Token | Old Value | New Value |
|---------|-----------|-----------|-----------|-----------|
| Primary Brand Color | `--tb-brand` | `--tb-primary` | `#2563EB` | `#1A3A52` |
| Primary Hover | `--tb-brand-hover` | `--tb-primary-hover` | `#1D4ED8` | `#0F2940` |
| Primary Active | `--tb-brand-active` | `--tb-primary-active` | `#1E40AF` | `#092033` |
| Primary Soft BG | `--tb-brand-50` | `--tb-primary-50` | `#EFF6FF` | `#F0F4F8` |
| Primary Light Border | `--tb-brand-100` | `--tb-primary-100` | `#DBEAFE` | `#D4E1EC` |
| Secondary (NEW) | N/A | `--tb-secondary` | N/A | `#0D7377` |
| Accent (NEW) | `--accent-color` | `--tb-accent` | `#7C3AED` | `#B8860B` |
| Body Background | `--tb-body-bg` | `--tb-body-bg` | `#F5F6FA` | `#FAFBFC` |
| Card Background | `--tb-card-bg` | `--tb-card-bg` | `#FFFFFF` | `#FFFFFF` |
| Border | `--tb-border` | `--tb-border` | `#E4E7EC` | `#D5DFE8` |
| Success | `--tb-success` | `--tb-success` | `#16A34A` | `#2D7A4E` |
| Warning | `--tb-warning` | `--tb-warning` | `#D97706` | `#C17D2D` |
| Danger | `--tb-danger` | `--tb-danger` | `#DC2626` | `#9B2C2C` |
| Info | `--tb-info` | `--tb-info` | `#0891B2` | `#0C7A9B` |

---

## Implementation Phases

### Phase 1: Foundation (CSS Variables)
**Duration:** 1-2 days  
**Owner:** Frontend-engineer  
**Acceptance Criteria:** All new hex values in tabler.css, no visual changes yet

1. Update `/frontend/src/theme/tabler.css` with new hex values
2. Create new token names (`--tb-primary`, `--tb-secondary`, `--tb-accent`)
3. Update dark mode variants
4. Verify no compile errors
5. **DO NOT** update component CSS yet

**Files Changed:**
- `frontend/src/theme/tabler.css`

---

### Phase 2: Component CSS (High-Risk)
**Duration:** 3-5 days  
**Owner:** Frontend-engineer  
**Acceptance Criteria:** All components render with new colors, all states tested (default, hover, focus, disabled, loading)

#### 2.1 Button Components
```
.btn-primary:
  FROM: background #2563EB (blue)
  TO:   background #1A3A52 (navy)
  
.btn-secondary:
  FROM: background #6B7280 (gray)
  TO:   background #0D7377 (teal) OR keep gray for neutral actions

.btn-outline-primary:
  FROM: color #2563EB, border #E4E7EC
  TO:   color #1A3A52, border #D5DFE8
```

**Test Matrix:**
- [ ] Default state (light, dark)
- [ ] Hover state (light, dark)
- [ ] Active/pressed state (light, dark)
- [ ] Disabled state (light, dark)
- [ ] Focus ring visible (light, dark)
- [ ] Icon colors correct
- [ ] Text color contrast ≥4.5:1

#### 2.2 Badge & Chip Components
```
.badge.bg-primary:
  FROM: background #EFF6FF, color #1E40AF
  TO:   background #F0F4F8, color #092033

.badge.bg-success:
  FROM: background #DCFCE7, color #14532D
  TO:   background #E0F0E7, color #1F5A39
```

**Test Cases:**
- [ ] All tones render (primary, success, warning, danger, info, neutral)
- [ ] Text readable on backgrounds
- [ ] Dark mode tones correct
- [ ] Border colors visible

#### 2.3 Status & Semantic Colors
Update all status-based UI:
- Success indicators (checkmarks, approved badges)
- Warning indicators (expiry warnings, pending)
- Danger indicators (errors, deletions, expired)
- Info indicators (tooltips, notices)

#### 2.4 Link Colors
```
a {
  color: FROM #2563EB TO #1A3A52
  color (hover): FROM #1D4ED8 TO #0F2940
}
```

#### 2.5 Form Controls
```
.form-control:focus {
  border-color: FROM #2563EB TO #1A3A52
  box-shadow: FROM rgba(37,99,235,.2) TO rgba(26,58,82,.2)
}

input[type="checkbox"]:checked {
  background: FROM #2563EB TO #1A3A52
  border: FROM #2563EB TO #1A3A52
}
```

#### 2.6 Navigation
```
.tb-nav-trigger.is-active {
  color: FROM #2563EB TO #1A3A52
  background: FROM #EFF6FF TO #F0F4F8
  box-shadow: inset 0 -2px 0 FROM #2563EB TO #1A3A52
}
```

**Files Changed:**
- `frontend/src/theme/tabler.css` (CSS rules)
- All component-specific CSS files

---

### Phase 3: Visual Testing (QA Intensive)
**Duration:** 2-3 days  
**Owner:** QA + Designer  
**Acceptance Criteria:** All 51+ pages visually approved, no regressions

#### 3.1 Light Mode Spot Checks
- [ ] Dashboard (stat cards, charts, metrics)
- [ ] License Ledger (table, filters, status badges)
- [ ] Allotment (forms, action buttons, status)
- [ ] Bill of Entry (data-heavy table, entity cards)
- [ ] Trade (form fields, validation states)
- [ ] Admin (user list, action buttons)
- [ ] Settings (toggle switches, forms)
- [ ] Modals (header, buttons, focus rings)
- [ ] Dropdowns (active item highlight, hover)
- [ ] Empty States (icon color, text color)

#### 3.2 Dark Mode Spot Checks
- [ ] Same pages as 3.1, in dark theme
- [ ] Contrast verified in both modes
- [ ] No colors lost or distorted
- [ ] Borders visible (not too dark)

#### 3.3 Accessibility Checks
- [ ] Color Contrast Analyzer on key elements
- [ ] Focus ring visible on all interactive elements
- [ ] Color-blind simulation (Protanopia, Deuteranopia, Tritanopia)
- [ ] No color-only information (always has text/icon backup)

#### 3.4 Responsive Checks
- [ ] Mobile (320px, 480px)
- [ ] Tablet (768px, 1024px)
- [ ] Desktop (1280px, 1920px)
- [ ] Colors consistent across breakpoints

---

### Phase 4: Regression Testing
**Duration:** 1-2 days  
**Owner:** QA  
**Acceptance Criteria:** E2E tests pass, no color-related bugs

#### 4.1 Component Tests
```bash
cd frontend && npm run test:unit
```

Ensure all component color-related tests pass.

#### 4.2 E2E Tests
```bash
cd frontend && npm run test:e2e
```

Run full E2E test suite on:
- Login flow
- License creation
- License ledger navigation
- Allotment allocation
- Bill of Entry creation
- Trade form submission

#### 4.3 Visual Regression
```bash
npm run test:visual
```

(If using Percy or similar tool)

---

## Component-by-Component Guidelines

### Buttons

#### Primary Button (Navy)
```tsx
.btn-primary {
  background-color: var(--tb-primary);     /* #1A3A52 */
  border-color: var(--tb-primary);
  color: #FFFFFF;
  box-shadow: 0 1px 2px rgba(26, 58, 82, 0.2);
}

.btn-primary:hover {
  background-color: var(--tb-primary-hover);  /* #0F2940 */
  border-color: var(--tb-primary-hover);
  box-shadow: 0 3px 8px rgba(26, 58, 82, 0.3);
}

.btn-primary:focus-visible {
  outline: none;
  box-shadow: var(--tb-ring);  /* Navy focus ring */
}
```

#### Secondary Button (Teal)
Use ONLY for "approve/success" actions:

```tsx
.btn-secondary {
  background-color: var(--tb-secondary);   /* #0D7377 */
  border-color: var(--tb-secondary);
  color: #FFFFFF;
}
```

#### Outline Primary Button (Navy Border + Text)
```tsx
.btn-outline-primary {
  background-color: transparent;
  color: var(--tb-primary);                /* #1A3A52 */
  border-color: var(--tb-border);          /* #D5DFE8 */
}

.btn-outline-primary:hover {
  background-color: var(--tb-primary-50);  /* #F0F4F8 */
  border-color: var(--tb-primary-100);     /* #D4E1EC */
  color: var(--tb-primary-hover);          /* #0F2940 */
}
```

#### Danger Button (Red)
```tsx
.btn-danger {
  background-color: var(--tb-danger);      /* #9B2C2C */
  border-color: var(--tb-danger);
  color: #FFFFFF;
}

.btn-danger:focus-visible {
  box-shadow: var(--tb-ring-danger);  /* Red focus ring */
}
```

### Badges

#### Primary Badge (Navy Soft)
```tsx
.badge.bg-primary {
  background-color: var(--tb-primary-50);    /* #F0F4F8 */
  color: var(--tb-primary-active);           /* #092033 */
  border-color: var(--tb-primary-100);       /* #D4E1EC */
  border: 1px solid;
}
```

#### Success Badge (Forest Green)
```tsx
.badge.bg-success {
  background-color: var(--tb-success-soft);  /* #E0F0E7 */
  color: var(--tb-success-text);             /* #1F5A39 */
  border-color: var(--tb-success-border);    /* #A8D5BB */
  border: 1px solid;
}
```

#### Warning Badge (Amber)
```tsx
.badge.bg-warning {
  background-color: var(--tb-warning-soft);  /* #F5E6D3 */
  color: var(--tb-warning-text);             /* #6B4423 */
  border-color: var(--tb-warning-border);    /* #E5C4A0 */
  border: 1px solid;
}
```

#### Danger Badge (Crimson)
```tsx
.badge.bg-danger {
  background-color: var(--tb-danger-soft);   /* #F5DCDC */
  color: var(--tb-danger-text);              /* #7A1818 */
  border-color: var(--tb-danger-border);     /* #E5A5A5 */
  border: 1px solid;
}
```

### Entity Cards

Left border color communicates status:

```tsx
.entity-card.tone-primary {
  border-left-color: var(--tb-primary);      /* #1A3A52 */
}

.entity-card.tone-success {
  border-left-color: var(--tb-success);      /* #2D7A4E */
}

.entity-card.tone-warning {
  border-left-color: var(--tb-warning);      /* #C17D2D */
}

.entity-card.tone-danger {
  border-left-color: var(--tb-danger);       /* #9B2C2C */
}
```

### Status Pills

```tsx
.tb-status.tone-primary {
  background-color: var(--tb-primary-50);    /* #F0F4F8 */
  color: var(--tb-primary-active);           /* #092033 */
  border-color: var(--tb-primary-100);       /* #D4E1EC */
}

.tb-status.tone-success {
  background-color: var(--tb-success-soft);  /* #E0F0E7 */
  color: var(--tb-success-text);             /* #1F5A39 */
  border-color: var(--tb-success-border);    /* #A8D5BB */
}
```

### Navigation

Active navigation item:

```tsx
.tb-nav-trigger.is-active {
  color: var(--tb-primary);                  /* #1A3A52 */
  background-color: var(--tb-primary-50);    /* #F0F4F8 */
  box-shadow: inset 0 -2px 0 0 var(--tb-primary);
}
```

### Form Controls

Input focus:

```tsx
.form-control:focus {
  border-color: var(--tb-primary);           /* #1A3A52 */
  box-shadow: var(--tb-ring);                /* Navy shadow */
}

.form-control.is-invalid:focus {
  border-color: var(--tb-danger);            /* #9B2C2C */
  box-shadow: var(--tb-ring-danger);         /* Red shadow */
}
```

Checkbox/Radio checked:

```tsx
.form-check-input:checked {
  background-color: var(--tb-primary);       /* #1A3A52 */
  border-color: var(--tb-primary);
}
```

---

## Dark Mode Specific Rules

### Rule 1: Use Semantic Variables, Never Hardcode

```tsx
/* GOOD */
background-color: var(--tb-card-bg);

/* BAD */
background-color: #FFFFFF;  /* Only white in light mode, wrong in dark */
```

### Rule 2: Test Both Modes

Every component must be tested:
- Light mode (light theme)
- Dark mode (data-theme="dark")

```bash
# In browser DevTools
document.documentElement.setAttribute('data-theme', 'dark');
```

### Rule 3: Lighter Accent Colors in Dark Mode

In dark mode, use lighter versions:

```css
:root {
  --tb-primary: #1A3A52;        /* dark navy for light mode */
}

[data-theme="dark"] {
  --tb-primary: #60A5F9;        /* light blue for dark mode */
}
```

### Rule 4: Borders Must Be Visible

Border colors must be light enough to see on dark surfaces:

```css
[data-theme="dark"] {
  --tb-border: #21262D;  /* NOT too dark, visible on #161B22 card */
}
```

---

## Accessibility Checklist

### Color Contrast
- [ ] Run WebAIM Contrast Checker on all text/background combinations
- [ ] Minimum: 4.5:1 for normal text (WCAG AA)
- [ ] Minimum: 3:1 for large text (WCAG AA)
- [ ] Target: 7:1+ for regular text (WCAG AAA — gold standard)

### Color Blindness
- [ ] Simulate Protanopia (red-green blind, 1% of males)
- [ ] Simulate Deuteranopia (red-green blind, 1% of males)
- [ ] Simulate Tritanopia (blue-yellow blind, 0.001%)
- [ ] Tool: https://www.color-blindness.com/coblis-color-blindness-simulator/

### Keyboard Navigation
- [ ] Focus rings visible on all interactive elements
- [ ] Focus order logical (tabbing left-to-right, top-to-bottom)
- [ ] Focus ring color has sufficient contrast against background

### Labels & Icons
- [ ] Colors NOT used as only means of conveying information
- [ ] Status always has text label + icon (not just color)
- [ ] Example: ✅ "Approved (green checkmark)" vs. ❌ "green background only"

---

## Testing Checklist

### Before Commit

```bash
# 1. No build errors
npm run build

# 2. No TypeScript errors
npm run typecheck

# 3. No linting issues
npm run lint

# 4. Unit tests pass
npm run test:unit

# 5. Visual spot-check (manual)
npm run dev
# Open http://localhost:5173
# Browse key pages in light mode
# Toggle dark mode
# Verify colors look professional
```

### Before PR Merge

```bash
# 1. E2E tests pass
npm run test:e2e

# 2. Visual regression check
npm run test:visual  # if available

# 3. Accessibility audit
npm run test:a11y    # if available

# 4. QA sign-off
# Designer verifies: "Looks professional, matches spec"
```

---

## Common Pitfalls to Avoid

### ❌ Pitfall 1: Hardcoded Colors
```tsx
/* BAD */
color: #2563EB;  /* Old blue, doesn't update with theme */

/* GOOD */
color: var(--tb-primary);  /* Uses new navy, updates with theme */
```

### ❌ Pitfall 2: Status Colors on Status Backgrounds
```tsx
/* BAD */
background: var(--tb-danger-soft);
color: var(--tb-warning);  /* Red bg + orange text = unreadable */

/* GOOD */
background: var(--tb-danger-soft);
color: var(--tb-danger-text);  /* Red bg + dark red text = readable */
```

### ❌ Pitfall 3: Forgetting Dark Mode
```tsx
/* BAD */
.card {
  background: #FFFFFF;  /* White in light, white in dark = invisible */
}

/* GOOD */
.card {
  background: var(--tb-card-bg);  /* White in light, gray in dark */
}
```

### ❌ Pitfall 4: Using Color As Only Information
```tsx
/* BAD */
<span style={{color: 'red'}}>Invalid</span>  /* Color-blind users can't see */

/* GOOD */
<span style={{color: 'var(--tb-danger)'}}>❌ Invalid</span>  /* Icon + color */
```

### ❌ Pitfall 5: Low Contrast Text
```tsx
/* BAD */
color: var(--tb-text-tertiary);  /* Too light on white background */
font-size: 12px;

/* GOOD */
color: var(--tb-text-secondary);  /* Darker, better contrast */
font-size: 14px;
```

---

## Success Metrics

### Visual Quality
- [ ] All pages render with new palette
- [ ] No color regressions vs. old design
- [ ] Professional, authoritative feeling
- [ ] Designer approval: "Looks professional"

### Accessibility
- [ ] 0 WCAG contrast failures
- [ ] All interactive elements have focus rings
- [ ] Readable in color-blind mode
- [ ] Accessible testing passes (axe, Lighthouse)

### Performance
- [ ] No color-related performance regressions
- [ ] CSS file size unchanged (same variables, just new values)
- [ ] No JavaScript color calculations

### User Feedback
- [ ] QA: No bug reports related to colors
- [ ] Users: "Looks more professional than before"
- [ ] Support: No complaints about visibility/readability

---

## Rollout & Communication

### To Design Team
"We're moving to a sophisticated, restrained palette that feels authoritative for financial operations."

### To Engineering Team
"Update color values in CSS variables. No behavior changes. All tests must pass."

### To QA Team
"Test light mode, dark mode, and accessibility. Verify all 51+ pages look professional."

### To Stakeholders
"Brand update reflects our positioning as a professional financial operations system."

---

## References

- **WCAG 2.1 Contrast:** https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum
- **Color Blindness Simulator:** https://www.color-blindness.com/coblis-color-blindness-simulator/
- **WebAIM Contrast Checker:** https://webaim.org/resources/contrastchecker/
- **Design System V2 Colors:** See `DESIGN_SYSTEM_V2_COLORS.md`
- **Visual Philosophy:** See `VISUAL_PHILOSOPHY.md`

---

**Status:** Ready for Implementation  
**Owner:** Frontend-engineer (Phase 2+), QA (Phase 3+)  
**Timeline:** 1 week from start to ship
