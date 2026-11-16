# WCAG 2.1 Level AA Compliance Checklist

License Manager - Accessibility & WCAG Compliance Standard

**Document Version:** 1.0  
**Last Updated:** 2026-09-25  
**Target Level:** WCAG 2.1 Level AA  
**Review Frequency:** Per UI redesign, quarterly full audit

---

## Principles & Pillars (POUR)

### 1. Perceivable
Users must perceive the information being presented.

### 2. Operable
Users must be able to operate all interface components.

### 3. Understandable
Users must understand the information and operations.

### 4. Robust
Content must be robust enough to work with assistive technologies.

---

## Detailed WCAG 2.1 AA Checklist

### 1. PERCEIVABLE - Text Alternatives

#### 1.1.1 Non-text Content (Level A)
- [ ] All images have meaningful alt text or are marked `aria-hidden="true"` if decorative
- [ ] Icons have aria-labels describing their function
- [ ] Charts/graphs have text descriptions or data tables as alternatives
- [ ] PDF documents have proper OCR and structure
- [ ] Videos have captions and audio descriptions

**Acceptable Alt Text Examples:**
```html
<!-- Good -->
<img src="chart.png" alt="Revenue trend: 20% growth Q1-Q4 2026" />
<button aria-label="Open navigation menu">☰</button>

<!-- Bad -->
<img src="chart.png" alt="chart" />
<button>☰</button>
```

---

### 2. PERCEIVABLE - Color & Contrast

#### 1.4.3 Contrast (Minimum) - Level AA
- [ ] **Normal text:** Minimum 4.5:1 contrast ratio (text < 18pt or < 14pt bold)
- [ ] **Large text:** Minimum 3:1 contrast ratio (text ≥ 18pt or ≥ 14pt bold)
- [ ] **UI components:** 3:1 contrast for borders, backgrounds, focus indicators
- [ ] **Dark mode:** Contrast maintained in all color schemes
- [ ] No reliance on color alone to convey information

**Contrast Validation:**
- Use tools: WebAIM, Contrast Ratio, axe DevTools
- Test both light and dark mode
- Test with colorblind filters (Deuteranopia, Protanopia, Tritanopia)

**Remediation Example:**
```css
/* Bad: insufficient contrast */
color: #888; background: #f5f5f5; /* 4.0:1 - fails AA */

/* Good: AA compliant */
color: #666; background: #f5f5f5; /* 4.5:1 - passes AA */
```

#### 1.4.1 Use of Color - Level A
- [ ] Color is not the only means of distinguishing information
- [ ] Status indicators use text + color (e.g., "Status: Active" not just green)
- [ ] Charts use patterns/icons + color
- [ ] Form validation uses icons/text + color

**Example - Form Validation:**
```html
<!-- Bad: color-only indicator -->
<input style="border: 2px solid red;" />

<!-- Good: icon + color + text -->
<input style="border: 2px solid red;" />
<span role="alert" style="color: red;">
  <Icon name="alert-circle" />
  Email format invalid
</span>
```

#### 1.4.8 Visual Presentation - Level AAA (tracked for quality)
- [ ] Line length ≤ 80 characters for better readability
- [ ] Text is not justified (flush left preferred)
- [ ] Spacing between lines ≥ 1.5x font size
- [ ] Spacing between paragraphs ≥ 1.5x line spacing
- [ ] Foreground/background separable without color

---

### 3. PERCEIVABLE - Adaptability

#### 1.3.1 Info & Relationships - Level A
- [ ] Semantic HTML used correctly (buttons vs links, headings hierarchical)
- [ ] Form labels associated with inputs via `<label for>` or `aria-labelledby`
- [ ] Table headers (`<th>`) properly marked
- [ ] Lists use `<ul>`, `<ol>`, `<li>` elements
- [ ] Abbreviations have `<abbr>` with title

#### 1.4.4 Resize Text - Level AA
- [ ] Text is resizable up to 200% without loss of functionality
- [ ] Use relative units (rem, em, %) not fixed px
- [ ] Layout remains usable at 200% zoom

**CSS Example:**
```css
/* Good: uses relative units */
body { font-size: 1rem; }
.heading { font-size: 2rem; }
.spacing { margin: 1rem; padding: 0.5rem; }

/* Bad: fixed pixel sizes */
body { font-size: 16px; }
.heading { font-size: 32px; }
```

---

### 4. OPERABLE - Keyboard Accessibility

#### 2.1.1 Keyboard - Level A
- [ ] All functionality is keyboard accessible
- [ ] Tab key navigates through focusable elements in logical order
- [ ] No keyboard trap (user can escape with keyboard alone)
- [ ] No device-specific functionality (swipe-only gestures have keyboard alternative)

**Tab Order Testing:**
```bash
# Press Tab repeatedly and verify:
1. Focus moves through elements logically
2. Focus never gets trapped
3. All functionality is reachable
4. Focus order follows visual layout (LTR/RTL aware)
```

#### 2.1.2 No Keyboard Trap - Level A
- [ ] User can escape out of components (modals, dropdowns, etc.)
- [ ] Escape key closes modals/overlays
- [ ] No infinite loops with Tab key

#### 2.1.4 Character Key Shortcuts - Level A (if applicable)
- [ ] If single-character shortcuts exist, user can disable them
- [ ] Shortcuts use modifiers (Ctrl+K, Alt+S) not just letters
- [ ] Shortcuts documented for assistive tech users

#### 2.4.3 Focus Order - Level A
- [ ] Focus order is logical and meaningful
- [ ] Focus order generally left-to-right, top-to-bottom
- [ ] No component loses focus when navigated away

**Example - Modal Focus Management:**
```typescript
// When opening modal, trap focus within it
const openModal = (modal: HTMLElement) => {
  modal.focus();
  // Store previous focus
  const previousFocus = document.activeElement;
  
  // Trap focus within modal
  // Listen to Tab/Shift+Tab and loop focus
  
  // On close, restore previous focus
  previousFocus?.focus();
};
```

#### 2.4.7 Focus Visible - Level AA
- [ ] Focus indicator is always visible
- [ ] Focus indicator has minimum 2px outline
- [ ] Focus indicator has sufficient contrast (3:1 at minimum)
- [ ] Focus is not removed with `outline: none` unless replacement provided

**CSS Example:**
```css
/* Good: visible focus indicator */
button:focus {
  outline: 3px solid #0066cc;
  outline-offset: 2px;
}

/* Bad: focus removed without replacement */
button:focus {
  outline: none;
}

/* Bad: low contrast focus */
button:focus {
  outline: 1px solid #ccc;
}
```

---

### 5. OPERABLE - Input Modalities

#### 2.5.1 Pointer Gestures - Level A
- [ ] Single-pointer operations have keyboard alternative
- [ ] Drag-and-drop has keyboard alternative
- [ ] Multi-touch gestures have keyboard shortcuts

#### 2.5.5 Target Size - Level AAA (tracked, not required for AA)
- [ ] Touch targets are at least 44x44 CSS pixels
- [ ] Click targets for non-touch are at least 44x44 CSS pixels

**Spacing & Sizing:**
```css
/* Button sizing */
button {
  min-height: 44px; /* Touch target minimum */
  min-width: 44px;
  padding: 12px 16px;
}

/* Checkbox/Radio sizing */
input[type="checkbox"],
input[type="radio"] {
  min-width: 44px;
  min-height: 44px;
}
```

---

### 6. UNDERSTANDABLE - Readable & Clear

#### 3.1.1 Language of Page - Level A
- [ ] Page language declared via `<html lang="en">` attribute
- [ ] Page content language is consistent

#### 3.1.4 Abbreviations - Level AAA (tracked for quality)
- [ ] First occurrence of abbreviation is expanded
- [ ] Or abbreviation has definition via `<abbr title="...">`

**Example:**
```html
<!-- Good: expanded on first use -->
<p>The Software Development Kit (SDK) is...</p>

<!-- Good: abbreviation with title -->
<p><abbr title="Application Programming Interface">API</abbr> endpoints</p>

<!-- Bad: unexplained abbreviation -->
<p>The SDK is...</p>
```

#### 3.2.4 Consistent Identification - Level AA
- [ ] UI components with same function are consistently identified
- [ ] Navigation menus always appear in same location
- [ ] Buttons with same function have same labels
- [ ] Icons representing same function always look the same

**Consistency Checklist:**
- [ ] All "Save" buttons use same styling, label, icon
- [ ] All "Cancel" buttons use same styling
- [ ] All error messages formatted consistently
- [ ] All form fields use same label styling

#### 3.3.3 Error Suggestion - Level AA
- [ ] When input error is detected, suggestion is provided
- [ ] Error message is clear and specific
- [ ] Error is associated with the field

**Error Message Example:**
```html
<!-- Good -->
<div role="alert" aria-describedby="email-error">
  <input id="email" aria-invalid="true" aria-describedby="email-error" />
  <span id="email-error" style="color: red;">
    Please enter a valid email address (example: user@domain.com)
  </span>
</div>

<!-- Bad -->
<div style="color: red;">Invalid input</div>
<input />
```

#### 3.3.1 Error Identification - Level A
- [ ] Errors are identified clearly
- [ ] Error description in text (not just color)
- [ ] Error message is associated with form field

#### 3.3.4 Error Prevention - Level AA
- [ ] Confirmation for important actions (deletion, submission)
- [ ] Reversible operations where possible
- [ ] Data is validated before submission

---

### 7. ROBUST - Compatibility

#### 4.1.1 Parsing - Level A
- [ ] HTML is valid (no duplicate IDs, properly nested elements)
- [ ] XML is well-formed where applicable
- [ ] Use tools: W3C HTML Validator

#### 4.1.2 Name, Role, Value - Level A
- [ ] All UI components have name, role, and value
- [ ] Dynamic content changes are announced
- [ ] State changes are accessible

**ARIA Implementation:**
```html
<!-- Good: name, role, value all present -->
<button aria-label="Close" aria-pressed="false">✕</button>

<!-- Good: form field with label -->
<label for="username">Username:</label>
<input id="username" type="text" required />

<!-- Good: status message -->
<div role="status" aria-live="polite" aria-atomic="true">
  3 items updated
</div>
```

#### 4.1.3 Status Messages - Level AA
- [ ] Status messages identified programmatically via role or aria-live
- [ ] Users can perceive messages without keyboard focus
- [ ] Messages don't disrupt main content

**Live Region Example:**
```html
<!-- Toast notification -->
<div role="status" aria-live="polite" aria-atomic="true">
  Changes saved successfully
</div>

<!-- Loading state -->
<div role="status" aria-live="polite">
  Loading... <span aria-hidden="true">⏳</span>
</div>
```

---

## Testing Tools & Methods

### Automated Testing
- [ ] **axe-core** (npm: @axe-core/playwright) - Automated violations
- [ ] **Lighthouse** - Chrome DevTools accessibility audit
- [ ] **WAVE Browser Extension** - Detailed feedback
- [ ] **Color Contrast Analyzer** - Precise contrast measurement
- [ ] **ESLint JSX a11y plugin** - Code-level checks

### Manual Testing (Required)
- [ ] **Keyboard Navigation** - Tab through entire application
- [ ] **Screen Reader** - VoiceOver (macOS), NVDA (Windows), JAWS
- [ ] **Zoom Test** - 200% zoom without loss of functionality
- [ ] **Color Blind Simulation** - Deuteranopia, Protanopia, Tritanopia
- [ ] **Focus Indicator Visibility** - Verify at 200% zoom
- [ ] **Dark Mode Testing** - Both light and dark mode accessible

### Tools Installation
```bash
# axe DevTools (Chrome/Firefox extension)
# https://www.deque.com/axe/devtools/

# WAVE Browser Extension
# https://wave.webaim.org/extension/

# Color Contrast Analyzer
# https://www.tpgi.com/color-contrast-checker/

# Lighthouse (built into Chrome)
# DevTools > Lighthouse > Accessibility
```

---

## Component-Specific Checklists

### Forms
- [ ] All inputs have associated labels
- [ ] Error messages clearly associated with fields
- [ ] Required fields marked with `required` attribute and visual indicator
- [ ] Form validation errors announced via `role="alert"`
- [ ] Submit button clearly identified
- [ ] Clear instructions for form completion

### Tables
- [ ] Header cells marked with `<th>`
- [ ] `scope` attribute on headers (`scope="col"` or `scope="row"`)
- [ ] Caption provided via `<caption>` or aria-label
- [ ] Complex tables have simplified version or summary
- [ ] Data cells properly associated with headers

**Table Example:**
```html
<table>
  <caption>Q4 2026 Revenue Summary</caption>
  <thead>
    <tr>
      <th scope="col">Product</th>
      <th scope="col">Revenue</th>
      <th scope="col">Growth</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Enterprise</td>
      <td>$2.5M</td>
      <td>+15%</td>
    </tr>
  </tbody>
</table>
```

### Modals & Dialogs
- [ ] Modal labeled with `role="dialog"` and `aria-labelledby`
- [ ] Focus trapped within modal during open
- [ ] Escape key closes modal
- [ ] Focus returned to trigger element on close
- [ ] Modal backdrop prevents interaction with page

### Navigation
- [ ] Skip to main content link (can be hidden, keyboard-accessible)
- [ ] Current page indicated in navigation
- [ ] Navigation structure logical and hierarchical
- [ ] Breadcrumbs labeled and clickable

### Dropdowns & Menus
- [ ] Opened via keyboard (Enter, Space, Arrow Down)
- [ ] Closed via Escape key
- [ ] Arrow keys navigate items
- [ ] First/last items wrap around or stop
- [ ] Typing jumps to matching items

### Buttons
- [ ] Descriptive text (not "Click here" or "OK")
- [ ] Icon buttons have aria-label
- [ ] Button state clearly indicated (disabled, loading, etc.)
- [ ] Button purpose clear without color alone

**Button Examples:**
```html
<!-- Good -->
<button>Save Changes</button>
<button aria-label="Close navigation menu">✕</button>

<!-- Bad -->
<button>Click here</button>
<button>✕</button>
```

### Links
- [ ] Link text is descriptive
- [ ] Links distinguished from buttons
- [ ] "Read more" links have context (aria-label with article title)
- [ ] External links indicated (icon + aria-label)

**Link Examples:**
```html
<!-- Good -->
<a href="/policy">Privacy Policy</a>
<a href="/article" aria-label="Read more about licensing">Read more</a>

<!-- Bad -->
<a href="/policy">Click here</a>
```

### Lists
- [ ] Semantically marked with `<ul>`, `<ol>`, `<li>`
- [ ] Not created with divs or other elements
- [ ] Proper nesting for sublist items

### Images
- [ ] All images have meaningful alt text
- [ ] Decorative images have `alt=""` and/or `aria-hidden="true"`
- [ ] Complex images have long description via `aria-describedby`
- [ ] Images in links have descriptive alt text

**Image Examples:**
```html
<!-- Good: meaningful alt -->
<img src="pie-chart.png" alt="Q4 2026 sales: 60% online, 40% retail" />

<!-- Good: decorative -->
<img src="divider.png" alt="" aria-hidden="true" />

<!-- Good: complex image with description -->
<img src="architecture.png" alt="System architecture diagram" aria-describedby="arch-desc" />
<p id="arch-desc">The system is divided into 4 layers...</p>

<!-- Bad: no alt text -->
<img src="pie-chart.png" />

<!-- Bad: uninformative alt -->
<img src="pie-chart.png" alt="chart" />
```

---

## Page-Specific Audit Tracking

### Dashboard
- [ ] Metrics cards have proper heading hierarchy
- [ ] Charts have data alternatives
- [ ] Status indicators use color + text + icon
- [ ] Navigation to detail pages is keyboard-accessible

### License Ledger
- [ ] Table headers properly marked
- [ ] Filter controls keyboard-accessible
- [ ] Sorting and pagination instructions provided
- [ ] Current sort indicator announced

### Trade Form
- [ ] Form fields have labels
- [ ] Validation messages clear and associated
- [ ] Multi-step form progress indicated accessibly
- [ ] Submit button clearly identified

### Reports
- [ ] Report tables have headers and scope attributes
- [ ] Generated data announced via live region if updated
- [ ] Chart data available in table format
- [ ] Export functionality keyboard-accessible

### Admin Sections
- [ ] User management forms accessible
- [ ] Sensitive actions (delete) have confirmation
- [ ] Activity log content announced
- [ ] Role/permission information clear

---

## Dark Mode Accessibility

### Critical Requirements
- [ ] All text meets 4.5:1 contrast in dark mode
- [ ] Images/charts visible and distinct
- [ ] Focus indicators visible on dark backgrounds
- [ ] Color relationships maintained (status colors distinct)
- [ ] No elements become invisible

### Dark Mode Testing
```css
/* Test media query */
@media (prefers-color-scheme: dark) {
  /* Verify all colors meet contrast */
  /* Verify all images visible */
  /* Verify focus indicators visible */
}
```

---

## Remediation Priority

### Critical (Fix Immediately)
1. Color contrast below WCAG AA
2. Keyboard navigation not functional
3. Focus indicator invisible or missing
4. Form validation without error association
5. Images missing alt text

### High (Fix in Current Sprint)
1. Heading hierarchy broken
2. Missing form labels
3. Focus trapped in component
4. Low contrast in dark mode
5. Decorative elements announced

### Medium (Fix in Next Sprint)
1. Inconsistent ARIA labeling
2. Touch targets < 44px (non-critical)
3. Missing skip links
4. Error messages not in role="alert"
5. Complex images missing descriptions

### Low (Backlog - Quality)
1. WCAG AAA enhancements
2. Advanced keyboard shortcuts
3. Extra sign language content
4. AAA color contrast (7:1)

---

## Sign-Off & Review

### Quarterly Full Audit
- [ ] All pages tested with automated tools
- [ ] Keyboard navigation verified
- [ ] Screen reader testing completed
- [ ] Dark mode verified
- [ ] Touch target sizes confirmed
- [ ] Focus indicators checked
- [ ] Color contrast validated
- [ ] ARIA labels verified
- [ ] Form accessibility confirmed
- [ ] Remediation issues logged

### Pre-Release Checklist
- [ ] Critical issues resolved
- [ ] High priority issues resolved
- [ ] New pages audited
- [ ] Existing pages re-validated
- [ ] Dark mode tested
- [ ] Mobile/touch tested
- [ ] Screen reader testing done
- [ ] Accessibility audit logged

---

## Responsible Parties

- **Frontend Engineer:** Implement accessible HTML/CSS, maintain ARIA
- **Product Designer:** Ensure color contrast, touch targets, visual hierarchy
- **QA/Test Engineer:** Verify keyboard navigation, screen reader compatibility
- **Accessibility Specialist:** Lead audits, track compliance, prioritize fixes

---

## Compliance Statement

This application aims to meet **WCAG 2.1 Level AA** standards. We are committed to:
- Accessibility for all users
- Regular audits and improvement
- User feedback integration
- Remediation of identified issues

**For accessibility issues or accommodations, contact:** [contact email]

---

**Last Updated:** 2026-09-25  
**Next Review:** 2026-12-25  
**Document Owner:** Accessibility Specialist
