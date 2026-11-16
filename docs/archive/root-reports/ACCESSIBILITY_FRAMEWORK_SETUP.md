# Accessibility Framework Setup & Usage Guide

License Manager - WCAG 2.1 Level AA Compliance Testing & Auditing

**Setup Date:** 2026-09-25  
**Framework Version:** 1.0  
**Status:** Ready for Use

---

## Quick Start

### 1. Framework Files Created

```
/
├── WCAG_COMPLIANCE_CHECKLIST.md          # WCAG 2.1 AA reference guide
├── ACCESSIBILITY_AUDIT_LOG.md            # Page-by-page audit tracking
├── ACCESSIBILITY_FIXES_LOG.md            # Remediation progress
├── ACCESSIBILITY_FRAMEWORK_SETUP.md      # This file
│
frontend/
├── src/
│   ├── lib/
│   │   └── accessibility.ts              # Testing utilities & helpers
│   │
│   └── test/
│       └── accessibility.test.ts         # Automated test suite (Playwright)
│
package.json                              # Already includes axe-core/playwright
```

### 2. Tools Already Installed

```json
{
  "devDependencies": {
    "@axe-core/playwright": "^4.13.0",
    "@playwright/test": "^1.62.1",
    "@testing-library/react": "^16.3.2",
    "@testing-library/user-event": "^14.6.1"
  }
}
```

No additional installations needed! The framework leverages existing tools.

### 3. Running Accessibility Tests

```bash
# Run all accessibility tests
cd frontend
npm run test:e2e -- accessibility.test.ts

# Run specific test suite
npm run test:e2e -- accessibility.test.ts -g "Color Contrast"

# Run with debugging
npm run test:e2e -- --debug accessibility.test.ts

# Run tests in headed mode (see browser)
npm run test:e2e -- --headed accessibility.test.ts

# Generate HTML report
npm run test:e2e -- accessibility.test.ts --reporter=html
```

---

## Testing Phases

### PHASE 1: Automated Scanning
**Duration:** Continuous  
**Tool:** axe-core + Playwright  
**Coverage:** All pages, WCAG AA level

```bash
npm run test:e2e -- accessibility.test.ts -g "Automated Axe-Core"
```

**What's Tested:**
- Color contrast (4.5:1 normal, 3:1 large)
- Heading hierarchy
- Form labels
- Image alt text
- ARIA attributes
- Button descriptions
- Element nesting

---

### PHASE 2: Keyboard Navigation
**Duration:** Per page redesign  
**Tool:** Playwright keyboard simulation  
**Manual:** Tab through entire application

```bash
npm run test:e2e -- accessibility.test.ts -g "Keyboard Navigation"
```

**Testing Checklist:**
- [ ] Tab key moves through elements logically
- [ ] Shift+Tab moves backward
- [ ] No keyboard traps (can't escape any element)
- [ ] Arrow keys work in dropdowns/menus
- [ ] Enter/Space activate buttons
- [ ] Escape closes modals
- [ ] All functionality reachable without mouse

**Manual Testing:**
```
1. Open application
2. Press Tab repeatedly
3. Verify focus moves logically left-to-right, top-to-bottom
4. Try Escape on modals
5. Try Arrow keys in dropdowns
6. Try Ctrl+F (browser find) - should work on all text
```

---

### PHASE 3: Focus Indicators
**Duration:** During component development  
**Requirement:** Visible focus outline on all interactive elements

**CSS Requirement:**
```css
/* Every interactive element needs visible focus */
button:focus-visible,
input:focus-visible,
[tabindex]:focus-visible {
  outline: 3px solid #0066cc;     /* Or your brand color */
  outline-offset: 2px;
}
```

**Verification:**
```bash
# Tab to any element and verify 3px outline appears
# Outline should have high contrast to background
# Outline should not be removed with outline: none
```

---

### PHASE 4: Screen Reader Testing
**Duration:** Quarterly  
**Tools:** VoiceOver (macOS), NVDA (Windows), JAWS  
**Manual Testing:** Required

**macOS VoiceOver Testing:**

```bash
# Enable VoiceOver
Cmd+F5

# Basic navigation
VO = Control+Option

VO+Right Arrow   = Move to next element
VO+Left Arrow    = Move to previous element
VO+Space         = Activate/click element
VO+U             = Open rotor (navigation panel)
VO+Home          = Move to top of page
VO+End           = Move to bottom of page

# Exit VoiceOver
Cmd+F5
```

**Windows NVDA Testing:**

```bash
# Download & install NVDA (free): https://www.nvaccess.org/

# Basic navigation
Insert+Tab       = Next element
Insert+Shift+Tab = Previous element
Enter            = Activate element
Space            = Activate button
Insert+H         = Next heading
Insert+F         = Next form field
Insert+B         = Next button
```

**What to Test:**
- [ ] Page structure announced correctly (headings, landmarks)
- [ ] Form labels announced with inputs
- [ ] Error messages associated with fields
- [ ] Button purposes clear
- [ ] Tables have header associations
- [ ] Charts have data alternatives
- [ ] Status updates announced
- [ ] Navigation structure logical

---

### PHASE 5: Dark Mode Testing
**Duration:** Every UI change  
**Requirement:** Full accessibility in both light and dark modes

```bash
# Test in dark mode (browser DevTools)
# DevTools > Rendering > CSS Media Feature Prefers-Color-Scheme
# Select "Prefers-dark-color-scheme"

# Run contrast tests in dark mode
npm run test:e2e -- accessibility.test.ts -g "Dark Mode"
```

**Checklist:**
- [ ] All text readable (4.5:1 contrast maintained)
- [ ] Images/icons visible
- [ ] Focus indicators visible on dark backgrounds
- [ ] No elements become invisible
- [ ] Color meanings preserved (red still indicates error, green success, etc.)

---

### PHASE 6: Mobile & Touch Testing
**Duration:** During mobile work  
**Tool:** Browser device emulation + real devices  
**Requirement:** 44x44px minimum touch targets

```bash
npm run test:e2e -- accessibility.test.ts -g "Touch Targets"
```

**Manual Testing:**
```
1. Open DevTools → Device Emulation
2. Test common devices (iPhone 12, Pixel 5, etc.)
3. Verify buttons/links are at least 44x44px
4. Test touch gestures:
   - Tap buttons/links
   - Swipe navigation
   - Pinch zoom (should work, not disabled)
   - Double-tap zoom (should work)
5. Test with actual devices if possible
```

---

## Integration with Development Workflow

### Pre-Commit Hook (Optional)

```bash
# Add to .husky/pre-commit
#!/bin/sh
. "$(dirname "$0")/_/husky.sh"

npm run test:e2e -- accessibility.test.ts --grep "Critical"
```

### CI/CD Integration

```yaml
# .github/workflows/a11y.yml (if using GitHub Actions)
name: Accessibility Tests
on: [push, pull_request]
jobs:
  a11y:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-node@v2
      - run: npm install
      - run: npm run test:e2e -- accessibility.test.ts
```

### Pre-Release Checklist

Before releasing any version:

```bash
# 1. Run all accessibility tests
npm run test:e2e -- accessibility.test.ts

# 2. Test keyboard navigation on each new page
# 3. Test in dark mode
# 4. Test on mobile devices
# 5. Run Lighthouse audit:
#    - DevTools → Lighthouse → Accessibility
# 6. Verify no critical issues in ACCESSIBILITY_AUDIT_LOG.md
# 7. Sign off: accessibility specialist
```

---

## Using the Testing Utilities

### In Component Tests

```typescript
import { render, screen } from '@testing-library/react';
import { validateFormFieldAccessibility, getAccessibleName } from '@/lib/accessibility';
import { LoginForm } from '@/pages/Login';

describe('LoginForm Accessibility', () => {
  test('email input has associated label', () => {
    render(<LoginForm />);
    const emailInput = screen.getByRole('textbox', { name: /email/i });
    
    const issues = validateFormFieldAccessibility(emailInput);
    expect(issues).toHaveLength(0);
  });

  test('submit button has accessible name', () => {
    render(<LoginForm />);
    const button = screen.getByRole('button', { name: /sign in/i });
    const name = getAccessibleName(button);
    
    expect(name).toBeTruthy();
  });
});
```

### In E2E Tests

```typescript
import { checkA11y } from 'axe-playwright';
import { getFocusableElements, getTabOrder } from '@/lib/accessibility';

test('Dashboard keyboard navigation', async ({ page }) => {
  await page.goto('/');
  
  // Check all elements in tab order
  const tabOrder = await page.evaluate(() => {
    const selector = 'button, [href], input, [tabindex]:not([tabindex="-1"])';
    return Array.from(document.querySelectorAll(selector))
      .map(el => el.textContent?.trim())
      .filter(Boolean);
  });
  
  expect(tabOrder.length).toBeGreaterThan(0);
  
  // Run axe scan
  const violations = await checkA11y(page);
  expect(violations).toHaveLength(0);
});
```

### In Visual Tests

```typescript
import { getContrastRatio, meetsContrastStandard } from '@/lib/accessibility';

test('button colors meet WCAG AA', () => {
  const foreground = '#ffffff'; // white text
  const background = '#0066cc'; // blue background
  
  const ratio = getContrastRatio(foreground, background);
  const meetsAA = meetsContrastStandard(ratio);
  
  expect(meetsAA).toBe(true);
  console.log(`Contrast ratio: ${ratio.toFixed(2)}:1`);
});
```

---

## Common Testing Patterns

### Testing Form Accessibility

```typescript
test('form fields are keyboard accessible and labeled', async ({ page }) => {
  await page.goto('/login');
  
  // Check all inputs have labels
  const inputs = await page.locator('input').all();
  for (const input of inputs) {
    const id = await input.getAttribute('id');
    const ariaLabel = await input.getAttribute('aria-label');
    
    let hasLabel = !!ariaLabel;
    if (id && !hasLabel) {
      const label = await page.locator(`label[for="${id}"]`);
      hasLabel = await label.count().then(c => c > 0);
    }
    
    expect(hasLabel).toBeTruthy();
  }
  
  // Tab through form
  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');
  
  const focused = page.locator(':focus');
  expect(await focused.count()).toBe(1);
});
```

### Testing Color Contrast

```typescript
test('page has sufficient color contrast', async ({ page }) => {
  await page.goto('/');
  
  // Method 1: Use axe-core
  const violations = await checkA11y(page, null, {
    rules: {
      'color-contrast': { enabled: true },
    },
  });
  expect(violations.length).toBe(0);
  
  // Method 2: Manual check for specific elements
  const textColor = await page.locator('p').first().evaluate(el => {
    return window.getComputedStyle(el).color;
  });
  
  // Verify text is not too light or too dark
  expect(textColor).not.toMatch(/rgba?\(255,\s*255,\s*255/); // Not white
});
```

### Testing Modal Accessibility

```typescript
test('modal traps focus and closes with Escape', async ({ page }) => {
  await page.goto('/profile');
  
  // Open modal
  const openButton = await page.locator('button:has-text("Edit")');
  await openButton.click();
  
  // Modal should exist
  const modal = page.locator('[role="dialog"]');
  await expect(modal).toBeVisible();
  
  // Close with Escape
  await page.keyboard.press('Escape');
  await expect(modal).toBeHidden();
});
```

---

## Accessibility Audit Process

### Monthly Audit

**Time Required:** 2-3 hours  
**Required Participants:** Frontend engineer, QA, accessibility specialist

1. **Automated Scan (15 min)**
   ```bash
   npm run test:e2e -- accessibility.test.ts
   ```
   - Review any new violations
   - Note which pages have issues
   - Update ACCESSIBILITY_AUDIT_LOG.md

2. **Keyboard Testing (30 min)**
   - Manual tab through each major page
   - Check for keyboard traps
   - Verify focus order is logical
   - Document any issues

3. **Screen Reader Testing (45 min)**
   - Enable VoiceOver/NVDA
   - Navigate through key user flows
   - Verify announcements are correct
   - Check heading structure
   - Verify form labels

4. **Dark Mode Testing (15 min)**
   - Enable dark mode preference
   - Verify all text readable
   - Check focus indicators visible
   - Look for invisible elements

5. **Mobile Testing (15 min)**
   - Test on iPhone and Android devices
   - Check touch target sizes
   - Verify zoom works
   - Test common gestures

6. **Report & Remediation (30 min)**
   - Compile findings
   - Prioritize issues by severity
   - Update ACCESSIBILITY_AUDIT_LOG.md
   - Update ACCESSIBILITY_FIXES_LOG.md with new issues

---

## Tools & Extensions

### Browser Extensions (Install These)

**Chrome/Edge:**
1. **axe DevTools** - Automated scanning
   - https://chrome.google.com/webstore
   - Search: "axe DevTools"

2. **WAVE** - Visual feedback
   - https://chrome.google.com/webstore
   - Search: "WAVE Evaluation Tool"

3. **ChromeVox** - Screen reader
   - Built into Chrome (Ctrl+Alt+Z)

**Firefox:**
1. **axe DevTools** - Automated scanning
2. **WAVE** - Visual feedback
3. **ARIA DevTools** - ARIA debugging

### Desktop Tools

**Color Contrast:**
- Contrast Ratio: https://contrast-ratio.com/
- Color Contrast Analyzer: https://www.tpgi.com/color-contrast-checker/
- WebAIM Color Contrast Checker: https://webaim.org/resources/contrastchecker/

**Screen Readers:**
- **macOS:** VoiceOver (built-in, Cmd+F5)
- **Windows:** NVDA (free) - https://www.nvaccess.org/
- **Windows:** JAWS (paid) - https://www.freedomscientific.com/products/software/jaws/

**Other Tools:**
- Lighthouse (Chrome DevTools → Lighthouse)
- HTML Validator: https://validator.w3.org/
- ARIA Validator: https://www.w3.org/WAI/test-evaluate/

---

## Documentation

### Reference Docs
- **WCAG_COMPLIANCE_CHECKLIST.md** - Complete AA checklist
- **ACCESSIBILITY_AUDIT_LOG.md** - Audit results by page
- **ACCESSIBILITY_FIXES_LOG.md** - Issue tracking & remediation
- **frontend/src/lib/accessibility.ts** - Testing utilities

### Resources
- [WCAG 2.1 Specification](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [WebAIM Blog](https://webaim.org/blog/)
- [A11y Cast Videos](https://www.youtube.com/playlist?list=PLNYkxOF6rcICWx0C9Xc-RgEzwLvePy7KY)

---

## Responsibilities

### Frontend Engineer
- Implement accessible HTML/CSS/ARIA
- Run automated tests regularly
- Perform keyboard navigation testing
- Maintain focus indicators and form labels
- Test new components with axe-core

### QA/Test Engineer
- Perform manual keyboard navigation testing
- Test keyboard shortcuts
- Verify form error handling
- Document edge cases
- Assist with screen reader testing

### Accessibility Specialist
- Lead quarterly audits
- Review code for accessibility
- Perform screen reader testing
- Prioritize remediation work
- Update compliance documentation

### Product/Design
- Ensure color contrast in designs
- Design visible focus states
- Specify heading hierarchy
- Ensure touch targets ≥ 44px
- Review error message placement

---

## Checklist for New Pages/Features

Before releasing any new page or feature:

```markdown
## Accessibility Pre-Release Checklist

### Page: _______________
### Date: _______________
### Engineer: _______________

### Automated Testing
- [ ] Ran axe-core scan - no violations
- [ ] All color contrasts ≥ 4.5:1 (3:1 large text)
- [ ] All form fields labeled
- [ ] All buttons have descriptive text or aria-label
- [ ] All images have alt text or aria-hidden
- [ ] Heading hierarchy is sequential (h1, h2, h3, etc.)

### Keyboard Navigation
- [ ] Tab key navigates all interactive elements
- [ ] Shift+Tab navigates backward
- [ ] No keyboard traps
- [ ] Focus order follows visual layout
- [ ] Focus indicator visible on all focused elements
- [ ] Escape closes modals/dropdowns

### Screen Reader (Manual)
- [ ] Page structure logical
- [ ] Headings announced correctly
- [ ] Form labels announced
- [ ] Error messages announced
- [ ] Button purposes clear
- [ ] Tables have header associations
- [ ] Links have descriptive text

### Dark Mode
- [ ] Text readable in dark mode (≥ 4.5:1)
- [ ] Images/icons visible
- [ ] Focus indicators visible
- [ ] No elements invisible

### Mobile
- [ ] Touch targets ≥ 44x44px
- [ ] Zoom works (not disabled)
- [ ] Touch gestures have keyboard alternative

### Sign-Off
- [ ] Engineer verified: _________________
- [ ] QA verified: _________________
- [ ] Accessibility specialist verified: _________________
```

---

## Questions?

### Common Issues

**Q: Test fails on localhost but passes in CI?**  
A: Build and deploy to staging, then test. Some issues only appear in production bundles.

**Q: How do I test focus indicator visibility?**  
A: Tab to element, then take screenshot. Or manually inspect in DevTools.

**Q: Colors look different in dark mode - is that bad?**  
A: No, colors should adapt to dark mode. Just ensure contrast is maintained.

**Q: What about keyboard shortcuts?**  
A: They're optional for AA but recommended. If using shortcuts, use modifiers (Ctrl+K, not just K).

**Q: Do I need WCAG AAA?**  
A: No, AA is the standard. AAA is aspirational and can be added later.

---

## Document Maintenance

- **Last Updated:** 2026-09-25
- **Next Review:** 2026-12-25
- **Owner:** Accessibility Specialist
- **Contributors:** Frontend Team, QA Team

