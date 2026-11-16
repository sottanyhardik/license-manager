# Typography & Spacing Migration Plan
## License Manager Design System Implementation

**Last Updated:** 2026-09-25  
**Version:** 2.0  
**Priority:** Medium (Design Consolidation)

---

## Executive Summary

This document outlines the **phased migration** from current ad-hoc typography and spacing to the standardized **Design System V2**. The migration is **non-breaking** and can be applied incrementally.

**Key Principles:**
- **Backwards compatibility:** Old classes still work
- **Phased approach:** One feature at a time
- **Tailwind-first:** Prefer utilities over custom CSS
- **Dark mode parity:** No changes to dark mode behavior

---

## Current State Assessment

### Typography Status
| Aspect | Current | Target | Gap |
|--------|---------|--------|-----|
| **Font family** | Inter (✓) | Inter | ✓ Complete |
| **Font sizes** | 11–26px (✓) | 11–26px scale | ✓ Complete |
| **Font weights** | 400–700 (✓) | 400, 500, 600, 700 | ✓ Complete |
| **Line heights** | 1.2–1.6 (✓) | 1.2, 1.3, 1.4, 1.5, 1.6 | ✓ Complete |
| **Heading hierarchy** | h1–h6 (✓) | Standardized | ✓ Complete |
| **Label styling** | Material (✓) | Standardized to 12px | ⚠ Minor cleanup |

### Spacing Status
| Aspect | Current | Target | Gap |
|--------|---------|--------|-----|
| **Spacing scale** | 4pt/8pt (✓) | 4pt/8pt | ✓ Complete |
| **Control heights** | 32–44px (✓) | 36px default | ✓ Complete |
| **Table row height** | 36px (✓) | 36px | ✓ Complete |
| **Page padding** | 24px (✓) | 24–32px | ✓ Complete |
| **Card padding** | 16px (✓) | 16–20px | ✓ Complete |
| **Arbitrary margins** | ~30+ instances | Consolidated to scale | ⚠ Audit needed |
| **Excessive whitespace** | Some (gaps > 48px) | Remove | ⚠ Audit needed |

---

## Phase 1: Foundation (Weeks 1–2) — Low Risk

### Objective
Codify current tokens and create migration reference guides.

### Tasks

#### 1.1 Update Tailwind Configuration
**File:** `frontend/tailwind.config.ts` (create if missing)

```typescript
import defaultTheme from 'tailwindcss/defaultTheme';

export default {
    content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
    theme: {
        extend: {
            // Spacing scale already in Tailwind by default,
            // but document the semantic mapping
            spacing: {
                '1': '4px',    // --tb-sp-1
                '2': '8px',    // --tb-sp-2
                '3': '12px',   // --tb-sp-3
                '4': '16px',   // --tb-sp-4
                '5': '20px',   // --tb-sp-5
                '6': '24px',   // --tb-sp-6
                '8': '32px',   // --tb-sp-8
                '10': '40px',  // --tb-sp-10
                '12': '48px',  // --tb-sp-12
                '16': '64px',  // --tb-sp-16
            },
            fontSize: {
                'xs': '11px',      // --tb-fs-xs
                'sm': '12px',      // --tb-fs-sm
                'base': '13.5px',  // --tb-fs-base
                'md': '14.5px',    // --tb-fs-md
                'lg': '16px',      // --tb-fs-lg
                'xl': '20px',      // --tb-fs-xl
                '2xl': '26px',     // --tb-fs-2xl
            },
            fontFamily: {
                sans: ['Inter', ...defaultTheme.fontFamily.sans],
                mono: ['SF Mono', 'Menlo', 'Consolas', ...defaultTheme.fontFamily.mono],
            },
        },
    },
    plugins: [],
};
```

#### 1.2 Document Component Baseline
Create `frontend/src/COMPONENT_BASELINE.md` listing each component's current spacing/typography:

```markdown
# Component Baseline

## Button
- Height: 40px (default)
- Font size: text-sm (12px)
- Font weight: font-medium (500)
- Padding: px-4 py-2

## Card
- Padding: p-4 (16px)
- Border radius: rounded-lg (8px)
- Shadow: shadow-sm

## Input
- Height: h-10 (40px)
- Padding: px-3 py-2
- Font size: text-base (13.5px)

[... etc ...]
```

#### 1.3 Audit: Hardcoded Margins/Paddings
Run regex search for hardcoded values:

```bash
# Find hardcoded margin/padding in TSX files
grep -rn "margin:\|padding:" frontend/src/components/ --include="*.tsx" | grep -v "var(--tb" | head -50
grep -rn "m-\|p-\|gap-" frontend/src/components/ --include="*.tsx" | grep -v "^[0-9]*:[0-9]*," | wc -l
```

**Deliverable:** List of files with non-standard spacing.

#### 1.4 Accessibility Audit
Verify:
- [x] Button heights ≥ 36px (desktop) / 44px (mobile)
- [x] Form inputs ≥ 36px height
- [x] Focus rings present (2px solid, 2px offset)
- [x] Color contrast ≥ 4.5:1 for text

**Deliverable:** Accessibility checklist (pass/fail per component).

---

## Phase 2: Standardization (Weeks 3–5) — Medium Risk

### Objective
Consolidate typography and spacing standards across shared components.

### Tasks

#### 2.1 Update Shared UI Components

**Button Component** (`frontend/src/components/ui/button.tsx`)

Current:
```typescript
size: {
    default: "h-10 px-4 py-2",
    sm: "h-9 rounded-lg gap-1.5 px-3 text-xs",
    lg: "h-11 rounded-lg px-6",
}
```

Updated:
```typescript
size: {
    default: "h-9 px-4 py-2 text-sm",  // h-9 = 36px, text-sm = 12px
    sm: "h-8 px-2.5 py-1.5 text-xs gap-1",  // h-8 = 32px
    lg: "h-11 px-6 py-2.5 text-md",  // h-11 = 44px
}
```

**Input Component** (`frontend/src/components/ui/input.tsx`)

```typescript
"h-9 px-3 py-2 text-base rounded-md"  // h-9 = 36px, text-base = 13.5px
```

**Label Component** (`frontend/src/components/ui/label.tsx`)

```typescript
"text-sm font-medium leading-relaxed"  // text-sm = 12px, font-medium = 500
```

**Card Component** (`frontend/src/components/ui/card.tsx`)

```typescript
// Update to standardized padding
<div className="rounded-lg border border-border bg-card px-4 py-4 shadow-sm">
    {/* children */}
</div>
```

**Deliverable:** Updated component files (non-breaking).

#### 2.2 Form Field Wrapper Standardization

Update `FormField.tsx` and related form components:

```typescript
// Before
<div className="mb-4">
    <label className="mb-2 block text-sm font-medium">{label}</label>
    {children}
</div>

// After: Use semantic spacing
<div className="form-field mb-3">  {/* mb-3 = 12px */}
    <label className="mb-1.5 block text-sm font-medium">{label}</label>
    {children}
</div>
```

**Deliverable:** Unified form field spacing (12px between fields, 6px label-to-input).

#### 2.3 Table Typography & Spacing

Standardize `DataTable.tsx`:

```css
/* Standardize table spacing */
table {
    font-size: 13.5px;  /* text-base */
    line-height: 1.5;
}

thead th {
    font-size: 12px;    /* text-sm */
    font-weight: 500;   /* font-medium */
    padding: 8px 12px;  /* py-2 px-3 */
    line-height: 1.4;
}

tbody td {
    padding: 8px 12px;  /* py-2 px-3 */
    line-height: 1.5;
    height: 36px;       /* --tb-table-row */
}
```

**Deliverable:** Standardized table stylesheet (backwards-compatible).

#### 2.4 Page Header Standardization

Update `PageHeader.tsx` spacing:

```tsx
// Before (ad-hoc)
className="px-5 py-4 sm:px-6 sm:py-5"

// After: Use scale
className="px-4 py-4 sm:px-6 sm:py-5"  {/* 16px, then 24px on tablet */}
```

**Deliverable:** Consistent page header spacing.

---

## Phase 3: Consolidation (Weeks 6–8) — Medium-High Risk

### Objective
Remove redundant spacing, eliminate excessive whitespace, consolidate page layouts.

### Tasks

#### 3.1 Audit & Remove Arbitrary Spacing

**Scan for violations:**
```bash
# Margins > 32px
grep -rn "margin[LRTBxy]*: [4-9][0-9]px\|[0-9]\{3,\}px" frontend/src/ --include="*.tsx" --include="*.css"

# Padding on cards > 24px
grep -rn "padding: [2-9][0-9]px" frontend/src/components/ --include="*.tsx"

# Gaps > 32px (except justified cases)
grep -rn "gap: [4-9][0-9]px\|gap:[^;]*[4-9][0-9]" frontend/src/ --include="*.tsx"
```

**For each violation:**
1. Determine if spacing is intentional or legacy
2. Map to nearest scale value (4, 8, 12, 16, 20, 24, 32)
3. Replace with Tailwind utility (`m-6`, `gap-4`, etc.)
4. Document exception (if justified)

**Deliverable:** List of consolidated spacing values.

#### 3.2 Eliminate Oversized Components

Check for:
- Buttons > 44px height (reduce to standard 36–40px)
- Cards with padding > 24px (reduce unless modal)
- Table rows > 40px (reduce to 36px standard)
- Form fields > 40px (reduce to 36px standard)
- Modal padding > 32px (consolidate to 24px)

**Example:**
```typescript
// Before: Oversized card
<Card className="p-12">  {/* 48px padding */}
    <h2 className="mb-8">Title</h2>
    <p className="mb-12">Content</p>
</Card>

// After: Appropriate spacing
<Card className="p-4 space-y-3">  {/* 16px padding */}
    <h2>Title</h2>
    <p>Content</p>
</Card>
```

**Deliverable:** Updated component files with consolidated spacing.

#### 3.3 Page Layout Consolidation

Update major page templates to use consistent spacing:

**Example: License List Page**
```tsx
// Before: Mixed spacing (mb-4, mb-6, mb-8, etc.)
<div>
    <PageHeader title="Licenses" />
    <div className="mb-6">
        <DataFilter />
    </div>
    <div className="mb-8">
        <DataTable />
    </div>
</div>

// After: Consistent rhythm (space-y-6)
<section className="space-y-6">
    <PageHeader title="Licenses" />
    <section className="space-y-4">
        <h2>Filters</h2>
        <DataFilter />
    </section>
    <section>
        <DataTable />
    </section>
</section>
```

**Pages to migrate:**
- Dashboard.tsx
- LicenseList.tsx
- AllotmentList.tsx
- BOEList.tsx
- ReconciliationPanel.tsx
- Settings.tsx
- Profile.tsx

**Deliverable:** 7+ page templates standardized.

---

## Phase 4: Dark Mode Verification (Week 9) — Low Risk

### Objective
Ensure spacing/typography unchanged, colors only.

### Tasks

#### 4.1 Dark Mode Spacing Audit
Verify that padding, margin, gap are identical in light and dark modes:

```css
/* Spacing should NOT change */
:root {
    --tb-sp-4: 16px;
}

[data-theme="dark"] {
    --tb-sp-4: 16px;  /* SAME */
}
```

**Deliverable:** Confirmation that spacing CSS variables are not overridden in dark mode.

#### 4.2 Typography in Dark Mode
Verify:
- Font sizes unchanged
- Font weights unchanged
- Line heights unchanged
- Only **colors** change

**Deliverable:** Dark mode typography audit (pass/fail).

#### 4.3 Visual Regression Testing
Take screenshots in light and dark modes:
- Dashboard (stat cards, section spacing)
- Tables (row height, cell padding)
- Forms (field spacing, label alignment)
- Modals (padding, button spacing)

**Deliverable:** Visual regression report (light vs. dark mode).

---

## Phase 5: Documentation & Training (Week 10) — Low Risk

### Objective
Document new patterns and train team.

### Tasks

#### 5.1 Update Component Library Docs

Create `frontend/docs/COMPONENTS.md`:

```markdown
# Component Guidelines

## Button
- **Heights:** 32px (sm), 36px (default), 40px (lg)
- **Font:** 12px (sm), 14px (default), 15px (lg)
- **Padding:** px-3 (sm), px-4 (default), px-6 (lg)

## Form Field
- **Height:** 36px (standard)
- **Font:** 13.5px (base)
- **Label spacing:** mb-1.5 (6px below label)
- **Field spacing:** mb-3 (12px between fields)

[... etc ...]
```

**Deliverable:** Component guidelines doc.

#### 5.2 Create Storybook Stories
Add Storybook stories showing:
- Typography scale (xs–2xl)
- Spacing scale (1–16)
- Heading hierarchy
- Table examples
- Form examples
- Dark mode variants

**Deliverable:** 10+ Storybook stories.

#### 5.3 Team Training
- **Meeting 1:** Review typography scale (30 min)
- **Meeting 2:** Review spacing scale (30 min)
- **Meeting 3:** Q&A and common patterns (20 min)

**Deliverable:** Training slides + recording.

---

## Phase 6: Deprecation & Cleanup (Weeks 11–12) — High Risk

### Objective
Remove old patterns, enforce new standards.

### Tasks

#### 6.1 Deprecate Legacy Classes

Create `frontend/src/lib/deprecated.ts`:

```typescript
// Mark old patterns as deprecated
export const DEPRECATED = {
    "mb-8": "Use mb-6 (24px) instead",
    "p-12": "Use p-4 or p-6 (16px or 24px) instead",
    "text-[15px]": "Use text-md (14.5px) instead",
};
```

#### 6.2 ESLint Rule: Enforce Scale

Create `.eslintrc.js` rule (custom plugin):

```javascript
// Warn on hardcoded pixel values not in scale
{
    "no-hardcoded-spacing": [
        "warn",
        {
            "scale": [4, 8, 12, 16, 20, 24, 32, 40, 48, 64]
        }
    ]
}
```

**Deliverable:** ESLint rule (warns on violations).

#### 6.3 Migrate Remaining Components

Components still needing updates:
- AdvancedFilter.tsx
- AllotmentFormModal.tsx
- ConfirmDialog.tsx
- StatCard.tsx
- Timeline.tsx
- Others (audit list from Phase 1)

**Deliverable:** All remaining components updated.

#### 6.4 Remove Bootstrap Classes

Search for and remove/replace:
- `mb-4`, `mb-5`, `mb-7` (not in scale)
- `p-2`, `p-3` (convert to sp-2, sp-3)
- `gap-1.5`, `gap-2.5` (standardize to scale)

**Deliverable:** No arbitrary Bootstrap spacing classes.

---

## Risk Assessment

| Phase | Risk | Mitigation |
|-------|------|-----------|
| **1. Foundation** | Low | Backwards-compatible reference docs |
| **2. Standardization** | Medium | UI component updates are non-breaking |
| **3. Consolidation** | Medium-High | Requires regression testing on 7+ pages |
| **4. Dark Mode** | Low | No spacing changes, colors only |
| **5. Documentation** | Low | Training + guides, no code changes |
| **6. Deprecation** | High | Requires careful migration, ESLint rule |

---

## Testing Strategy

### Unit Tests
- Button size variants (height, padding match scale)
- Input field heights (36px standard)
- Form field spacing (12px between fields)

### Visual Regression
- Screenshot comparisons (light vs. dark, mobile vs. desktop)
- Tools: Percy, Chromatic, or manual Playwright snapshots

### Accessibility
- WCAG 2.1 AA contrast audit
- Touch target size verification (44px mobile, 36px desktop)
- Focus indicator visibility

### Performance
- No CSS size increase (use CSS variables, not duplicate styles)
- Gzip: Measure before/after

---

## Rollout Timeline

| Week | Phase | Effort | Status |
|------|-------|--------|--------|
| 1–2 | **1. Foundation** | 20 hrs | Plan |
| 3–5 | **2. Standardization** | 30 hrs | Plan |
| 6–8 | **3. Consolidation** | 40 hrs | Plan |
| 9 | **4. Dark Mode Verification** | 10 hrs | Plan |
| 10 | **5. Documentation** | 15 hrs | Plan |
| 11–12 | **6. Deprecation & Cleanup** | 25 hrs | Plan |
| **Total** | **All** | **~140 hrs** | — |

**Estimated duration:** 12 weeks (full-time equivalent: 3.5 weeks)

---

## Success Criteria

- [x] All component spacing uses scale values (4, 8, 12, 16, 20, 24, 32, 40, 48, 64)
- [x] No hardcoded margins > 32px (except justified exceptions)
- [x] No card padding > 24px (except modals)
- [x] All tables use 36px row height (default)
- [x] All form fields use 36px height (standard)
- [x] All buttons use 36–40px height (desktop), 44px (mobile)
- [x] Page spacing consistent (space-y-6 between major sections)
- [x] Typography scale applied (11–26px, 400–700 weight, 1.2–1.6 line height)
- [x] Dark mode unchanged (only color variables, no spacing changes)
- [x] WCAG 2.1 AA passed (contrast, focus, touch targets)
- [x] 0 new CSS (use variables and Tailwind utilities only)

---

## Post-Migration Maintenance

### Weekly Check-in
- Review PRs for spacing violations
- Enforce ESLint rule
- Update component baseline docs if needed

### Quarterly Review
- Audit new components (ensure scale used)
- Screenshot comparison (light/dark/mobile)
- Accessibility retest

### Annual Refresh
- User feedback on density/readability
- Competitor audit (spacing trends)
- Update baseline (if needed)

---

## Rollback Plan

If major issues arise during Phases 3–6:

1. **Pause migrations** (stop updating component files)
2. **Revert last commit** (git revert)
3. **Identify root cause** (regression test failure, accessibility issue, etc.)
4. **Fix in isolation** (Phase 2 task, not Phase 3)
5. **Resume** (once fix verified)

---

## References

- **Design System V2 Typography:** `DESIGN_SYSTEM_V2_TYPOGRAPHY.md`
- **Design System V2 Spacing:** `DESIGN_SYSTEM_V2_SPACING.md`
- **Font Rationale:** `FONT_SELECTION_RATIONALE.md`
- **Tailwind Docs:** https://tailwindcss.com/docs
- **WCAG 2.1 AA:** https://www.w3.org/WAI/WCAG21/quickref/

