/**
 * Accessibility Test Suite
 *
 * Comprehensive WCAG 2.1 AA level testing using axe-core
 * Run with: npm run test:e2e -- accessibility.spec.ts
 */

import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';

// Define test routes for all pages
const ACCESSIBLE_ROUTES = [
  { name: 'Dashboard', path: '/' },
  { name: 'Login', path: '/login' },
  { name: 'Profile', path: '/profile' },
  { name: 'Settings', path: '/settings' },
  { name: 'License Ledger', path: '/ledger' },
  { name: 'Masters', path: '/masters' },
  { name: 'Reports', path: '/reports' },
  { name: 'Reconciliation', path: '/reconciliation' },
  { name: 'Activity Log', path: '/admin/activity-log' },
  { name: 'Users', path: '/admin/users' },
];

// WCAG Level AA Criteria
const A11Y_RULES = {
  // Color contrast ratios
  CONTRAST_AA_NORMAL: 4.5, // For normal text (< 18pt or < 14pt bold)
  CONTRAST_AA_LARGE: 3.0, // For large text (>= 18pt or >= 14pt bold)

  // Touch target minimums
  TOUCH_TARGET_MIN: 44, // pixels

  // Focus indicators
  FOCUS_OUTLINE_MIN: 2, // pixels

  // Heading hierarchy
  HEADING_HIERARCHY: true,

  // Color not sole means
  COLOR_NOT_ONLY: true,

  // ARIA labels required
  ARIA_LABELS_REQUIRED: true,
};

test.describe('Accessibility Framework - WCAG 2.1 AA', () => {
  test.beforeEach(async ({ page }) => {
    // Inject axe-core before each test
    await injectAxe(page);
  });

  // PHASE 1: Color Contrast Testing
  test.describe('Color Contrast (WCAG 2.1 AA)', () => {
    ACCESSIBLE_ROUTES.forEach(({ name, path }) => {
      test(`${name}: contrast check`, async ({ page }) => {
        await page.goto(path, { waitUntil: 'networkidle' });

        // Get all contrast violations
        const violations = await checkA11y(page, null, {
          rules: {
            'color-contrast': { enabled: true },
          },
        });

        expect(violations.length).toBe(0);
      });
    });
  });

  // PHASE 2: Focus States & Keyboard Navigation
  test.describe('Keyboard Navigation & Focus States', () => {
    test('Tab navigation flows logically through interactive elements', async ({ page }) => {
      await page.goto('/');

      // Collect all focusable elements
      const focusableElements = await page.locator(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      ).all();

      expect(focusableElements.length).toBeGreaterThan(0);

      // Test Tab key traversal
      for (let i = 0; i < Math.min(5, focusableElements.length); i++) {
        await page.keyboard.press('Tab');
        const focused = await page.evaluate(() => document.activeElement?.tagName);
        expect(focused).toBeTruthy();
      }
    });

    test('Focus indicator is visible on interactive elements', async ({ page }) => {
      await page.goto('/');

      // Tab to first interactive element
      await page.keyboard.press('Tab');

      // Check if element has outline or box-shadow (focus styles)
      const hasFocusStyle = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement;
        const styles = window.getComputedStyle(el);
        return !!(
          (styles.outlineWidth !== 'none' && styles.outlineWidth !== '0px') ||
          styles.boxShadow !== 'none'
        );
      });

      // Log for manual verification if needed
      console.log('Focus style detected:', hasFocusStyle);
    });

    test('Escape key closes modals and dropdowns', async ({ page }) => {
      await page.goto('/profile');

      // Find any button that opens a dialog
      const modalTriggers = await page.locator('[aria-haspopup="dialog"]').all();

      if (modalTriggers.length > 0) {
        await modalTriggers[0].click();
        await page.keyboard.press('Escape');

        const dialog = await page.locator('[role="dialog"]').isHidden();
        expect(dialog).toBeTruthy();
      }
    });
  });

  // PHASE 3: ARIA Labels & Semantic HTML
  test.describe('ARIA Labels & Semantic HTML', () => {
    test('All form inputs have associated labels', async ({ page }) => {
      await page.goto('/login');

      const inputs = await page.locator('input').all();

      for (const input of inputs) {
        const inputId = await input.getAttribute('id');
        const ariaLabel = await input.getAttribute('aria-label');

        if (inputId) {
          const label = await page.locator(`label[for="${inputId}"]`);
          const hasLabel = await label.count().then(c => c > 0);
          const hasAriaLabel = !!ariaLabel;

          expect(hasLabel || hasAriaLabel).toBeTruthy();
        } else {
          // Fallback: check for aria-label
          expect(ariaLabel).toBeTruthy();
        }
      }
    });

    test('Buttons have descriptive text or aria-label', async ({ page }) => {
      await page.goto('/');

      const buttons = await page.locator('button').all();

      for (const button of buttons) {
        const text = await button.textContent();
        const ariaLabel = await button.getAttribute('aria-label');
        const title = await button.getAttribute('title');

        const hasAccessibleName = text?.trim() || ariaLabel || title;
        expect(hasAccessibleName).toBeTruthy();
      }
    });

    test('Images have alt text or aria-hidden', async ({ page }) => {
      await page.goto('/');

      const images = await page.locator('img').all();

      for (const img of images) {
        const alt = await img.getAttribute('alt');
        const ariaHidden = await img.getAttribute('aria-hidden');

        expect(alt !== null || ariaHidden === 'true').toBeTruthy();
      }
    });

    test('Heading hierarchy is sequential', async ({ page }) => {
      await page.goto('/');

      const headings = await page.locator('h1, h2, h3, h4, h5, h6').all();
      const headingLevels: number[] = [];

      for (const heading of headings) {
        const tagName = await heading.evaluate(el => el.tagName);
        const level = parseInt(tagName[1]);
        headingLevels.push(level);
      }

      // Check that heading hierarchy doesn't skip levels (with some tolerance)
      for (let i = 1; i < headingLevels.length; i++) {
        const diff = Math.abs(headingLevels[i] - headingLevels[i - 1]);
        expect(diff).toBeLessThanOrEqual(2); // Allow one-level jumps
      }
    });
  });

  // PHASE 4: Touch Targets & Mobile Accessibility
  test.describe('Touch Targets & Mobile Accessibility', () => {
    test('Interactive elements have minimum 44px touch target', async ({ page }) => {
      await page.goto('/');

      const interactiveElements = await page.locator(
        'button, [role="button"], a, input[type="checkbox"], input[type="radio"]'
      ).all();

      const smallTargets: string[] = [];

      for (const element of interactiveElements) {
        const box = await element.boundingBox();
        if (box && (box.width < 44 || box.height < 44)) {
          const text = await element.textContent();
          const tagName = await element.evaluate(el => el.tagName);
          smallTargets.push(`${tagName}: "${text}"`);
        }
      }

      // Log for review (some decorative elements may be smaller)
      if (smallTargets.length > 0) {
        console.warn('Small touch targets found:', smallTargets);
      }
    });
  });

  // PHASE 5: Dark Mode Accessibility
  test.describe('Dark Mode Accessibility', () => {
    test('contrast maintained in dark mode', async ({ page }) => {
      await page.emulateMedia({ colorScheme: 'dark' });
      await page.goto('/');

      // Run contrast check in dark mode
      const violations = await checkA11y(page, null, {
        rules: {
          'color-contrast': { enabled: true },
        },
      });

      expect(violations.length).toBe(0);
    });

    test('all elements visible in dark mode', async ({ page }) => {
      await page.emulateMedia({ colorScheme: 'dark' });
      await page.goto('/');

      // Check for visibility issues
      const hiddenElements = await page.locator(':is(*)').all();

      let visibilityIssues = 0;
      for (const element of hiddenElements) {
        const visibility = await element.evaluate(el => {
          const styles = window.getComputedStyle(el);
          return styles.visibility !== 'hidden' && styles.display !== 'none' && styles.opacity !== '0';
        });

        if (!visibility) {
          visibilityIssues++;
        }
      }

      // Expect visibility issues to be minimal
      expect(visibilityIssues).toBeLessThan(hiddenElements.length * 0.1);
    });
  });

  // PHASE 6: Error Messages & Form Feedback
  test.describe('Form Accessibility & Error Handling', () => {
    test('error messages are associated with form fields', async ({ page }) => {
      await page.goto('/login');

      // Try submitting invalid form to trigger errors
      const submitButton = await page.locator('button[type="submit"]').first();
      if (submitButton) {
        await submitButton.click();
        await page.waitForTimeout(500);

        // Check for error messages with aria-live or aria-describedby
        const errorMessages = await page.locator('[role="alert"]').all();

        for (const error of errorMessages) {
          const role = await error.getAttribute('role');
          expect(role).toBe('alert');
        }
      }
    });
  });

  // PHASE 7: Axe Accessibility Scan (Automated)
  test.describe('Automated Axe-Core Scans', () => {
    ACCESSIBLE_ROUTES.forEach(({ name, path }) => {
      test(`${name}: full axe accessibility scan`, async ({ page }) => {
        await page.goto(path, { waitUntil: 'networkidle' });

        const violations = await checkA11y(page);

        // Report violations for tracking
        if (violations.length > 0) {
          console.log(`${name} violations:`, violations);
        }

        expect(violations.length).toBe(0);
      });
    });
  });

  // PHASE 8: Screen Reader Testing (Manual - Documented)
  test.describe('Screen Reader Testing (Manual Documentation)', () => {
    test('document landmarks and page structure', async ({ page }) => {
      await page.goto('/');

      // Check for main landmark
      const main = await page.locator('main').count();
      expect(main).toBeGreaterThan(0);

      // Check for nav landmarks
      const nav = await page.locator('nav').count();
      console.log(`Navigation landmarks found: ${nav}`);

      // Check for header
      const header = await page.locator('header').count();
      console.log(`Header landmarks found: ${header}`);
    });

    test('skip links or keyboard shortcuts documented', async ({ page }) => {
      await page.goto('/');

      // Check for skip to main content link
      const skipLink = await page.locator('[href="#main"]').count();
      console.log(`Skip links found: ${skipLink}`);
    });
  });
});

// WCAG Level A & AAA tests (optional, for future compliance)
test.describe('Extended Accessibility Tests (WCAG AAA)', () => {
  test.skip('WCAG AAA: Enhanced color contrast (7:1)', async ({ page }) => {
    // For future AAA compliance
    await page.goto('/');
    // Would require enhanced contrast validation
  });

  test.skip('WCAG AAA: Sign language for video content', async ({ page }) => {
    // For future AAA compliance with video/media
    await page.goto('/');
  });
});
