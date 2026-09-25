# Visual Regression Testing Guide

**License Manager UI Rebrand 2026**  
**Quick Reference for Screenshots, Comparison, and Quality Assessment**

---

## Quick Start

### 1. Running the Application

```bash
cd /Users/drushahardiksottany/Developer/projects/license-manager
npm install    # if needed
npm run dev    # starts Vite dev server
```

Access at: `http://localhost:5173`

### 2. Taking Screenshots

**Desktop (1440×900):**
1. Open DevTools: F12
2. Click device toggle (top-left of DevTools)
3. Set custom dimensions: 1440 × 900
4. Navigate to page
5. Cmd+Shift+P → "Capture screenshot"

**Mobile (390×844):**
1. Same as above, set to 390 × 844
2. Test portrait orientation primary
3. Verify landscape (390×844 rotated)

**Dark Mode:**
1. Press Cmd+Shift+P
2. Search "Emulate CSS media feature prefers-color-scheme"
3. Select "dark"
4. Take fresh screenshots

### 3. Organizing Screenshots

**Naming Convention:**
```
[PAGE_NAME]_[VIEWPORT]_[THEME]_[DATE].png

Examples:
- dashboard_1440x900_light_2026-09-25.png
- dashboard_390x844_light_2026-09-25.png
- dashboard_390x844_dark_2026-09-25.png
- license-ledger_1440x900_light_2026-09-25.png
```

**Directory Structure:**
```
screenshots/
├── baseline/          # Pre-rebrand (develop branch)
│   ├── dashboard/
│   ├── license-ledger/
│   └── ...
├── post-rebrand/      # Post-rebrand (current branch)
│   ├── dashboard/
│   ├── license-ledger/
│   └── ...
└── comparisons/       # Side-by-side analysis
    ├── dashboard_comparison.md
    └── ...
```

---

## Color Verification Checklist

### Using Browser DevTools Color Picker

1. Open DevTools → Elements tab
2. Click color swatch next to any styled element
3. Verify it matches one of these values:

**Light Mode Primary Colors:**
- `#2563EB` - Brand primary
- `#16A34A` - Success
- `#D97706` - Warning
- `#DC2626` - Danger
- `#0891B2` - Info

**Light Mode Backgrounds:**
- `#F5F6FA` - Body background
- `#FFFFFF` - Card background
- `#F8F9FB` - Sunken background
- `#111827` - Text primary
- `#5E6673` - Text secondary

**If any hardcoded hex found:**
- Flag as issue: "Hardcoded color - should use CSS variable"
- Severity: P2 (Medium - violation of design system)
- Record file and line number

### Testing in Dark Mode

1. Open DevTools console
2. Run: `document.documentElement.setAttribute('data-theme', 'dark')`
3. Verify colors shift appropriately:
   - Background → `#0D1117`
   - Card → `#161B22`
   - Text → `#E6EDF3`
   - Brand → `#3B82F6` (slightly lighter)

---

## Typography Verification

### Font Size Check

Use DevTools inspector to verify:

```
Body text: 13.5px (or 14px with fallback)
Labels: 14.5px (or 15px with fallback)
Headings: Match H1/H2/H3 tags
Small text: 12px
Extra small: 11px
```

**Command line verification:**
```bash
# Search for hardcoded font sizes
grep -r "font-size:" frontend/src/pages/ | grep -v "px" | head -20
```

### Weight Verification

- Normal text: 400 weight
- Labels, buttons: 500 weight
- Headings: 600 weight
- Strong emphasis: 700 weight

---

## Spacing Verification

### Using DevTools

1. Inspect element
2. Look for margin/padding values in Computed tab
3. Verify all are multiples of 4px:
   - 4px, 8px, 12px, 16px, 20px, 24px, 32px

### Automated Check

```bash
# Search for suspicious spacing values
grep -r "margin:" frontend/src/pages/ | grep -E "[0-9]px" | \
  grep -v -E "4px|8px|12px|16px|20px|24px|32px|0px"
```

---

## Component Verification

### Buttons

Checklist:
- [ ] Primary button: Blue solid with white text
- [ ] Secondary button: Light gray with dark text
- [ ] Danger button: Red solid with white text
- [ ] Outline button: No fill, just border
- [ ] Button height: 36px (or 32px small, 40px large)
- [ ] Padding: Left/right consistent
- [ ] Focus ring: Blue outline on tab
- [ ] Hover state: Darker shade or lighter fill
- [ ] Disabled: Reduced opacity (~50%)

**Test Command:** Navigate through UI, Tab key to each button, verify focus ring visible

### Input Fields

Checklist:
- [ ] Height: 36px exactly
- [ ] Border: Light gray `#E4E7EC`
- [ ] Padding: 8px vertical, 12px horizontal
- [ ] Font size: 13.5px
- [ ] Focus ring: Blue outline
- [ ] Placeholder color: Light gray `#9CA3AF`
- [ ] Error state: Red border + error message below
- [ ] Disabled: Reduced opacity

**Test Command:** Click input → type → Shift+Tab to verify focus ring → press Tab with error

### Cards

Checklist:
- [ ] Background: White `#FFFFFF`
- [ ] Border: Light gray `#E4E7EC` OR subtle shadow
- [ ] Border radius: 8px
- [ ] Padding: 16px or 24px (consistent within page)
- [ ] Hover shadow: Darker shadow appears
- [ ] Header: Darker background or bold text
- [ ] Dividers: Light border between sections

### Tables

Checklist:
- [ ] Header background: `#F8F9FB` (sunken)
- [ ] Row height: 36px exactly
- [ ] Row border: Light `#E4E7EC`
- [ ] Hover row: Light blue `#EFF6FF`
- [ ] Text alignment: Appropriate (left/center/right)
- [ ] Column padding: Minimum 12px
- [ ] Pagination: Styled like buttons
- [ ] Empty state: Centered secondary text

---

## Responsive Verification

### Tablet (768px)
1. Set viewport to 768×1024
2. Check:
   - [ ] Content reflows horizontally
   - [ ] Navigation adapts (hamburger menu if needed)
   - [ ] Tables become scrollable or collapse
   - [ ] Cards stack vertically
   - [ ] Touch targets minimum 44px
   - [ ] No horizontal scrolling

### Mobile (390px)
1. Set viewport to 390×844
2. Check:
   - [ ] Content stacks vertically
   - [ ] Text readable (no zoom needed)
   - [ ] Buttons/inputs full or near-full width
   - [ ] Navigation accessible (burger menu)
   - [ ] Forms single-column
   - [ ] Tables simplified (scroll or collapse)
   - [ ] Images scale proportionally
   - [ ] No horizontal scrolling
   - [ ] Status bar not hidden
   - [ ] Notch-safe area (if applicable)

### Test Emulation
```bash
# Simulate network throttling
DevTools → Network → Throttling → Slow 3G
# This reveals layout shift and performance issues
```

---

## Dark Mode Verification

### Manual Check

1. Toggle dark mode (Cmd+Shift+P → "prefers-color-scheme")
2. For each page verify:
   - [ ] Text readable on dark background
   - [ ] Contrast AA minimum still met
   - [ ] Buttons visible and styled
   - [ ] Cards have dark borders
   - [ ] Input fields styled for dark
   - [ ] Images appropriately styled
   - [ ] No bright whites that hurt eyes
   - [ ] Status colors adjusted

### Automated Contrast Check

Use online tool with exported colors:
- https://webaim.org/resources/contrastchecker/
- Input light mode colors → verify AA+ pass
- Input dark mode colors → verify AA+ pass

---

## Accessibility Verification

### Keyboard Navigation

```bash
# Test without mouse
Tab        - Move forward
Shift+Tab  - Move backward
Enter      - Activate button or link
Space      - Toggle checkbox/radio
Arrow keys - Menu navigation, select options
Escape     - Close modal/dropdown
```

Verify:
- [ ] All interactive elements reachable via Tab
- [ ] Focus ring always visible
- [ ] Focus order logical (left-to-right, top-to-bottom)
- [ ] No keyboard traps
- [ ] Form submission on Enter works
- [ ] Escape closes modals

### Color Contrast

Use DevTools or online checker:

**Minimum Requirements:**
- Normal text: 4.5:1 ratio (AA)
- Large text (18px+): 3:1 ratio (AA)
- UI components (borders, icons): 3:1 ratio (AA)

**Browser Tool:**
1. DevTools → Lighthouse → Accessibility
2. Check for contrast warnings
3. Fix any failed elements

### Screen Reader Testing (VoiceOver)

```bash
# macOS
Cmd+F5              - Toggle VoiceOver
Ctrl+Alt+U          - Open VoiceOver Utility
Ctrl+Alt+Right      - Next item
Ctrl+Alt+Left       - Previous item
Ctrl+Alt+Space      - Activate item
```

Verify:
- [ ] Page title announced
- [ ] Form labels associated with inputs
- [ ] Buttons have accessible names
- [ ] Images have alt text
- [ ] Headings have proper hierarchy
- [ ] Links have descriptive text (not "click here")
- [ ] Tables have headers

---

## Issue Reporting Template

```markdown
### [SEVERITY] [Page Name] - [Issue Title]

**Severity:** P0 (Critical) | P1 (High) | P2 (Medium) | P3 (Low)

**Location:** Page name, section, component

**Description:**
What is visually wrong?

**Expected Behavior:**
How should this look/behave?

**Actual Behavior:**
What is currently happening?

**Design System Violation:**
Which token/rule is violated?

**Steps to Reproduce:**
1. Navigate to [page]
2. [Action]
3. Observe [issue]

**Affected Viewports:**
- [ ] Desktop (1440px)
- [ ] Tablet (768px)
- [ ] Mobile (390px)

**Affected Themes:**
- [ ] Light mode
- [ ] Dark mode

**Screenshot:**
[Attach before/after]

**Suggested Fix:**
[Recommend solution]

**Status:** Open | In Review | Fixed | Verified
```

---

## Batch Testing Commands

### Find All Pages
```bash
find frontend/src/pages -name "*.tsx" | grep -v test | wc -l
# Should return 95 pages
```

### Check for Hardcoded Colors
```bash
grep -r "#[0-9A-Fa-f]\{6\}" frontend/src/pages/ | grep -v ".test.tsx" | \
  grep -v "node_modules" | grep -v "design-system" | wc -l
# Should return 0 (all colors from design system)
```

### Check for Inline Styles
```bash
grep -r "style={{" frontend/src/pages/ | grep -v ".test.tsx" | head -20
# Flag any inline styles not using tokens
```

### Verify Token Usage
```bash
grep -r "var(--tb-" frontend/src/pages/ | wc -l
# Should show high count (design system in use)
```

---

## Performance Notes

### Lighthouse Audit

Run for each page:
1. DevTools → Lighthouse tab
2. Click "Analyze page load"
3. Target metrics:
   - Performance: 90+
   - Accessibility: 95+
   - Best Practices: 90+
   - SEO: 90+

### Visual Regression Performance

Large viewports take more time. Prioritize:
1. **P0 Pages** (20 min):
   - Dashboard
   - License Ledger
   - License Overview
   - MasterForm
   - Reports index

2. **P1 Pages** (30 min):
   - Trade Form
   - Allotment Action
   - All reports detail pages
   - Login/Auth pages

3. **P2 Pages** (remaining time):
   - Admin pages
   - Settings
   - Error pages
   - Less-used features

---

## Tips & Tricks

### Screenshot Comparison

Use online image compare tools:
- https://www.diffchecker.com/image-compare (simple)
- ImageMagick: `compare before.png after.png diff.png`
- Inspect pixel differences

### Color Extraction

```bash
# Get all CSS colors from a file
grep -oE "#[0-9A-Fa-f]{6}|rgb\([^)]+\)" frontend/src/theme/tabler.css
```

### Font Verification

```bash
# Check which fonts are loaded
# In browser console:
window.getComputedStyle(document.body).fontFamily
# Should show: "Inter", sans-serif, ...
```

### Layout Debugging

```bash
# In browser console, highlight spacing issues:
document.querySelectorAll('*').forEach(el => {
  el.style.outline = '1px solid hsl(200, 100%, 50%)';
});
```

---

## Documentation

- **VISUAL_REGRESSION_LOG.md** - Session history and issue tracking
- **DESIGN_SYSTEM_ADHERENCE_REPORT.md** - Token compliance verification
- **BEFORE_AFTER_COMPARISON.md** - Screenshot analysis and changes
- **VISUAL_QUALITY_GATE_REPORT.md** - Professional quality assessment

---

## Sign-Off

```
Framework Ready:  ✅
Screenshots:      ⏳ In Progress
Analysis:         ⏳ In Progress
Quality Gate:     ⏳ In Progress

Last Updated: 2026-09-25 13:45 UTC
Reviewer: Design QA Specialist
```

